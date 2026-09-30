"""
Mock draft API'si.

Draft durumu sunucu belleginde tutulur (tek surec). Tarayici her hamlede
bir istek atar; yapay zeka rakiplerin secimleri ayni istekte yapilip
liste olarak doner ve istemci onlari sirayla canlandirir. Streamlit
surumunde "canli" akis her secimde 0.3 saniye uyuyup sayfayi yeniden
ciziyordu; butun sayfa o sure boyunca kilitliydi.

Durum bellekte oldugu icin sunucu yeniden baslarsa suren draft kaybolur;
giris yapmis kullanici draftini kaydedip sonra acabilir.
"""
import json
import secrets
import threading
import time

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from services.database import FREE_SAVED_DRAFT_LIMIT, db
from services.draft_data import get_draft_board
from services.draft_engine import (SLOT_ELIGIBILITY, create_draft, current_round,
                                   current_team, deserialize, draft_board_grid,
                                   finalize_nomination, grade_draft, is_user_turn,
                                   make_pick, max_affordable_bid, nominate,
                                   pick_in_round, picks_until_user_turn,
                                   roster_needs, run_ai_until_user, serialize,
                                   team_summary, total_picks, upcoming_picks,
                                   user_bid, user_pass, user_team)
from services.nba_season import get_season_label
from web.core import current_user, is_pro, render

router = APIRouter()

GUEST_COOKIE = "hl_guest"
_DRAFTS = {}
_LOCK = threading.Lock()
_IDLE_LIMIT = 8 * 3600
_MAX_DRAFTS = 400

RANDOMNESS = {"board": 0.12, "balanced": 0.35, "wild": 0.7}


# ==================== SAHIPLIK ====================

def _owner(request):
    user = current_user(request)
    if user:
        return f"u{user['id']}"
    guest = request.cookies.get(GUEST_COOKIE)
    return f"g{guest}" if guest else None


def _prune():
    now = time.time()
    stale = [k for k, v in _DRAFTS.items() if now - v["touched"] > _IDLE_LIMIT]
    for key in stale:
        _DRAFTS.pop(key, None)
    if len(_DRAFTS) > _MAX_DRAFTS:
        for key, _ in sorted(_DRAFTS.items(), key=lambda kv: kv[1]["touched"])[:len(_DRAFTS) - _MAX_DRAFTS]:
            _DRAFTS.pop(key, None)


def _get(request, draft_id):
    entry = _DRAFTS.get(draft_id)
    if not entry or entry["owner"] != _owner(request):
        return None
    entry["touched"] = time.time()
    return entry


def _missing():
    return JSONResponse({"error": "That draft is no longer running. Start a new one "
                                  "or open a saved draft."}, 404)


# ==================== GORUNUM ====================

def _compact(p):
    return {"id": p["id"], "name": p["name"], "team": p["team"], "pos": p["pos"],
            "positions": p.get("positions") or [p["pos"]], "adp": p["adp"],
            "auction": p["auction"], "owned": round(p.get("owned", 0)),
            "injury": p.get("injury") or "ACTIVE", "fpts": round(p["fpts"], 1),
            "pts": round(p["pts"], 1), "reb": round(p["reb"], 1), "ast": round(p["ast"], 1),
            "stl": round(p["stl"], 1), "blk": round(p["blk"], 1), "gp": int(p.get("gp") or 0),
            "rookie": bool(p.get("rookie"))}


def _view(state, entry):
    teams = []
    for t in state["teams"]:
        summary = team_summary(state, t)
        teams.append({
            "slot": t["slot"], "name": t["name"], "is_user": t["is_user"],
            "budget": t["budget"], "spent": t["spent"], "remaining": summary["remaining"],
            "fpts": summary["fpts"], "players": summary["players"],
            "needs": roster_needs(t, state["rounds"]),
            "picks": [{"round": p["round"], "overall": p["overall"], "price": p["price"],
                       "player": {k: p["player"][k] for k in ("id", "name", "pos", "team", "fpts", "adp")}}
                      for p in t["picks"]],
        })
    team = current_team(state)
    nom = state.get("current_nomination")
    nomination = None
    if nom:
        high = next((t for t in state["teams"] if t["slot"] == nom["high_slot"]), None)
        me = user_team(state)
        nomination = {
            "player": _compact(nom["player"]), "high_bid": nom["high_bid"],
            "high_team": high["name"] if high else "?",
            "awaiting_user": bool(nom.get("awaiting_user")),
            "history": nom.get("history", [])[-5:],
            "max_bid": max_affordable_bid(state, me) if me and me["is_user"] else 0,
        }
    grades = grade_draft(state) if state["complete"] else {}
    headers, rows = draft_board_grid(state)
    return {
        "id": entry["id"], "format": state["format"], "opponent_mode": state["opponent_mode"],
        "team_count": state["team_count"], "rounds": state["rounds"],
        "user_slot": state["user_slot"], "budget": state["budget"],
        "complete": state["complete"], "pick_number": state["pick_number"],
        "total": total_picks(state), "made": len(state["log"]),
        "round": current_round(state) if not state["complete"] else state["rounds"],
        "pick_in_round": pick_in_round(state) if not state["complete"] else None,
        "on_clock": {"name": team["name"], "slot": team["slot"], "is_user": team["is_user"]} if team else None,
        "user_turn": is_user_turn(state),
        "waiting": picks_until_user_turn(state) if not is_user_turn(state) else 0,
        "teams": teams, "log": state["log"], "drafted": state["drafted_ids"],
        "nomination": nomination,
        "grades": {str(k): v for k, v in grades.items()},
        "upcoming": upcoming_picks(state, 6),
        "board": {"headers": headers, "rows": rows},
        "saved_id": entry.get("saved_id"),
        "slot_eligibility": {k: sorted(v) for k, v in SLOT_ELIGIBILITY.items()},
    }


def _payload(entry, ai=None, message=None, pool=False, ok=True):
    state = entry["state"]
    out = {"view": _view(state, entry), "ai": ai or [], "ok": ok}
    if message:
        out["message"] = message
    if pool:
        out["pool"] = [_compact(p) for p in state["pool"]]
    return out


def _advance(state):
    """Yapay zeka rakipler, kullanicinin sirasi gelene kadar oynar."""
    if state["opponent_mode"] != "ai" or state["complete"]:
        return []
    return run_ai_until_user(state)


# ==================== SAYFA ====================

@router.get("/mock-draft")
def page(request: Request):
    user = current_user(request)
    saved = db.list_mock_drafts(user["id"]) if (user and db.available) else []
    board = get_draft_board()
    response = render(request, "mock_draft.html", active="mock", saved=saved,
                      pool_size=len(board), pool_ok=not board.empty,
                      season=get_season_label(), limit=FREE_SAVED_DRAFT_LIMIT)
    if not user and not request.cookies.get(GUEST_COOKIE):
        response.set_cookie(GUEST_COOKIE, secrets.token_urlsafe(18), max_age=30 * 86400,
                            httponly=True, samesite="lax", path="/")
    return response


# ==================== API ====================

@router.post("/api/mock")
def start(request: Request, body: dict = Body(...)):
    owner = _owner(request)
    if not owner:
        return JSONResponse({"error": "Reload the page and try again."}, 400)
    board = get_draft_board()
    if board.empty:
        return JSONResponse({"error": "The draft pool is unavailable - ESPN did not answer. "
                                      "Try again in a moment."}, 503)
    fmt = "auction" if body.get("format") == "auction" else "snake"
    mode = "manual" if body.get("opponent_mode") == "manual" else "ai"
    try:
        teams = max(4, min(16, int(body.get("team_count", 10))))
        rounds = max(5, min(16, int(body.get("rounds", 13))))
        slot = max(1, min(teams, int(body.get("user_slot", 1))))
        budget = max(50, min(500, int(body.get("budget", 200))))
    except (TypeError, ValueError):
        return JSONResponse({"error": "Check the draft settings."}, 400)
    if fmt == "auction" and budget < rounds:
        return JSONResponse({"error": f"The budget must be at least ${rounds} - every player "
                                      "costs at least $1."}, 400)
    state = create_draft(board, team_count=teams, rounds=rounds, user_slot=slot, fmt=fmt,
                         opponent_mode=mode, budget=budget,
                         ai_randomness=RANDOMNESS.get(body.get("difficulty"), 0.35))
    draft_id = secrets.token_urlsafe(9)
    entry = {"id": draft_id, "state": state, "owner": owner, "touched": time.time(),
             "saved_id": None, "lock": threading.Lock()}
    with _LOCK:
        _prune()
        _DRAFTS[draft_id] = entry
    with entry["lock"]:
        made = _advance(state)
        return _payload(entry, ai=made, pool=True)


@router.get("/api/mock/{draft_id}")
def get(request: Request, draft_id: str):
    entry = _get(request, draft_id)
    if not entry:
        return _missing()
    return _payload(entry, pool=True)


def _act(request, draft_id, action):
    entry = _get(request, draft_id)
    if not entry:
        return _missing()
    with entry["lock"]:
        state = entry["state"]
        ok, message, made = action(state)
        code = 200 if ok else 400
        return JSONResponse(_payload(entry, ai=made, message=message, ok=ok), status_code=code)


@router.post("/api/mock/{draft_id}/pick")
def pick(request: Request, draft_id: str, body: dict = Body(...)):
    def action(state):
        if not is_user_turn(state):
            return False, "It is not your turn.", []
        if state.get("current_nomination"):
            return False, "Finish the current auction first.", []
        try:
            player_id = int(body.get("player_id"))
        except (TypeError, ValueError):
            return False, "Pick a player.", []
        if state["format"] == "auction":
            ok, message = nominate(state, player_id)
            made = []
            if ok and not is_user_turn(state):
                finalize_nomination(state)
                made = _advance(state)
            return ok, message, made
        ok, message = make_pick(state, player_id)
        return ok, message, (_advance(state) if ok else [])
    return _act(request, draft_id, action)


@router.post("/api/mock/{draft_id}/bid")
def bid(request: Request, draft_id: str, body: dict = Body(...)):
    def action(state):
        try:
            amount = int(body.get("amount"))
        except (TypeError, ValueError):
            return False, "Enter a bid.", []
        ok, message = user_bid(state, amount)
        made = []
        if ok and not (state.get("current_nomination") or {}).get("awaiting_user"):
            finalize_nomination(state)
            made = _advance(state)
        return ok, message, made
    return _act(request, draft_id, action)


@router.post("/api/mock/{draft_id}/pass")
def pass_(request: Request, draft_id: str):
    def action(state):
        ok, message = user_pass(state)
        return ok, message, (_advance(state) if ok else [])
    return _act(request, draft_id, action)


@router.post("/api/mock/{draft_id}/close")
def close(request: Request, draft_id: str):
    def action(state):
        ok, message = finalize_nomination(state)
        return ok, message, (_advance(state) if ok else [])
    return _act(request, draft_id, action)


@router.post("/api/mock/{draft_id}/save")
def save(request: Request, draft_id: str, body: dict = Body(...)):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "Sign in to save drafts."}, 401)
    entry = _get(request, draft_id)
    if not entry:
        return _missing()
    state = entry["state"]
    if not entry.get("saved_id") and not is_pro(user) and \
            db.saved_draft_count(user["id"]) >= FREE_SAVED_DRAFT_LIMIT:
        return JSONResponse({"error": f"Free accounts keep {FREE_SAVED_DRAFT_LIMIT} saved drafts. "
                                      "Delete one first."}, 403)
    grades = grade_draft(state)
    me = user_team(state)
    grade = grades.get(me["slot"], {}).get("grade") if me and state["complete"] else None
    name = str(body.get("name") or "").strip()[:80] or \
        f"{state['format'].title()} · {state['team_count']} teams · {state['created_at'][:10]}"
    db.ensure_draft_table()
    saved_id = db.save_mock_draft(user["id"], name, serialize(state), grade=grade,
                                  draft_id=entry.get("saved_id"))
    if not saved_id:
        return JSONResponse({"error": "Could not save the draft. Try again."}, 500)
    entry["saved_id"] = saved_id
    return {"ok": True, "saved_id": saved_id, "message": "Draft saved."}


@router.post("/api/mock/load/{saved_id}")
def load(request: Request, saved_id: int):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "Sign in first."}, 401)
    record = db.load_mock_draft(user["id"], saved_id)
    if not record:
        return JSONResponse({"error": "That draft was not found."}, 404)
    saved = record["state"]
    if isinstance(saved, str):
        saved = json.loads(saved)
    board = get_draft_board()
    state = deserialize(saved, board if not board.empty else None)
    draft_id = secrets.token_urlsafe(9)
    entry = {"id": draft_id, "state": state, "owner": _owner(request), "touched": time.time(),
             "saved_id": saved_id, "lock": threading.Lock()}
    with _LOCK:
        _prune()
        _DRAFTS[draft_id] = entry
    with entry["lock"]:
        made = _advance(state)
        return _payload(entry, ai=made, pool=True)


@router.post("/api/mock/saved/{saved_id}/delete")
def delete_saved(request: Request, saved_id: int):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "Sign in first."}, 401)
    if not db.delete_mock_draft(user["id"], saved_id):
        return JSONResponse({"error": "Could not delete that draft."}, 400)
    return {"ok": True}

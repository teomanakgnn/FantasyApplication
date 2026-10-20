"""
Watch party (yonetici, deneme): ikinci ekran maç odasi. Video yok; herkes
maci kendi yayinindan izler, oda canli skor, oyunlar, fantezi liderleri,
sohbet ve tepkiler verir.
"""
import time
from datetime import timedelta

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import config
from services import watch_party as wp
from services.database import db
from web import stats
from web.core import current_user, login_required, redirect, render

router = APIRouter()

REACTIONS = ["🔥", "😂", "😱", "👏", "💀", "🧊", "😤", "🐐"]
_last_post = {}


def _admin(request):
    u = current_user(request)
    return u if u and u.get("username") in config.ADMIN_USERNAMES else None


def _gate(request):
    gate = login_required(request)
    if gate:
        return gate
    if not _admin(request):
        return redirect("/", "Not available.", "error")
    return None


@router.get("/admin/watch")
def lobby(request: Request):
    gate = _gate(request)
    if gate:
        return gate
    day = wp.today_et()
    days = []
    for d in (day, day - timedelta(days=1)):
        try:
            games = stats.scoreboard(d)
        except Exception:
            games = []
        if games:
            days.append((d, games))
    return render(request, "watch_lobby.html", active="home", days=days)


@router.get("/admin/watch/{game_id}")
def room(request: Request, game_id: str):
    gate = _gate(request)
    if gate:
        return gate
    try:
        g = wp.game_state(game_id)
    except Exception:
        return redirect("/admin/watch", "Game not found.", "error")
    return render(request, "watch_room.html", active="home", game_id=game_id, g=g, reactions=REACTIONS)


def _msg(r):
    return {"id": r["id"], "user": r["username"], "kind": r["kind"], "body": r["body"],
            "at": r["created_at"].isoformat() + "Z" if r.get("created_at") else ""}


@router.get("/api/watch/{game_id}/feed")
def feed(request: Request, game_id: str, after: int = 0, board: int = 0):
    if not _admin(request):
        return JSONResponse({"error": "Not available."}, 403)
    out = {"messages": [_msg(r) for r in db.watch_messages(game_id, after)]}
    try:
        g = wp.game_state(game_id)
        out["game"] = g
        if board:
            out["leaders"] = wp.fantasy_leaders(game_id, final=g["final"])
    except Exception as exc:
        out["game_error"] = str(exc)[:120]
    return out


@router.post("/api/watch/{game_id}/post")
async def post(request: Request, game_id: str):
    u = _admin(request)
    if not u:
        return JSONResponse({"error": "Not available."}, 403)
    b = await request.json()
    kind = "react" if b.get("kind") == "react" else "msg"
    body = str(b.get("body") or "").strip()[:280]
    if kind == "react" and body not in REACTIONS:
        return JSONResponse({"error": "Unknown reaction."}, 400)
    if not body:
        return JSONResponse({"error": "Empty message."}, 400)
    now = time.time()
    if now - _last_post.get(u["id"], 0) < (0.25 if kind == "react" else 0.8):
        return JSONResponse({"error": "Slow down a little."}, 429)
    _last_post[u["id"]] = now
    mid = db.add_watch_message(game_id, u["id"], u["username"], kind, body)
    return {"id": mid}

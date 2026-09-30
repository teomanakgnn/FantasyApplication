"""
Alt/ust tahmini: 30 takimin Las Vegas sezonluk galibiyet baremi.

Baremler veritabaninda donduruluyor ki herkes ayni sayiya oynasin; Vegas
cizgileri gelince model cizgileri bir kez degistirildi (bkz.
_switch_to_vegas). Paylasim karti sunucuda PNG olarak ciziliyor
(utils/share_card.py) ve telefonda dogrudan WhatsApp'a gonderilebiliyor.
"""
import csv
import io
import threading
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse, Response

from services.database import db
from services.nba_season import get_current_season_year, get_season_label
from services.win_totals import (get_team_identity, implied_over,
                                 project_win_totals, vegas_lines)
from utils.share_card import over_under_card
from web.core import current_user, render

router = APIRouter()

# Sezonun ilk maci 20 Ekim 2026, 23:00 UTC (19:00 ET). Tahminler ondan bir
# dakika once kapaniyor. Eski surum 20 Ekim 23:59 sunucu saatinde
# kapaniyordu: ilk mac basladiktan sonra bir saat daha tahmin
# degistirilebiliyordu.
DEADLINE = datetime(2026, 10, 20, 22, 59, 0, tzinfo=timezone.utc)

OVER, UNDER = "over", "under"

_lines_cache = {}
_lines_lock = threading.Lock()


def deadline_state():
    now = datetime.now(timezone.utc)
    if now >= DEADLINE:
        return False, "Picks are locked"
    left = DEADLINE - now
    if left.days > 0:
        return True, f"{left.days}d {left.seconds // 3600}h left"
    return True, f"{left.seconds // 3600}h {(left.seconds % 3600) // 60}m left"


def _odds(value):
    try:
        return None if value is None or value != value else int(value)
    except (TypeError, ValueError):
        return None


def _switch_to_vegas(season, rows):
    """Donmus cizgiler Vegas'inkiyle ayni degilse bir kez degistirir."""
    vegas = vegas_lines(season)
    if not vegas:
        return
    stale = [r for r in rows if r["team"] in vegas and (
        r["line"] != vegas[r["team"]][0] or r.get("over_odds") != vegas[r["team"]][1]
        or r.get("under_odds") != vegas[r["team"]][2])]
    if not stale:
        return
    if db.replace_win_lines(season, {r["team"]: vegas[r["team"]] for r in stale}) is None:
        return
    for r in stale:
        r["line"], r["over_odds"], r["under_odds"] = vegas[r["team"]]


def load_lines(season):
    """Donmus baremler; ilk acilista uretilip dondurulur. 5 dk bellekte."""
    hit = _lines_cache.get(season)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    with _lines_lock:
        hit = _lines_cache.get(season)
        if hit and time.time() - hit[0] < 300:
            return hit[1]
        rows = []
        if db.available and db.win_lines_frozen(season):
            rows = [{"team": r["team"], "team_name": r["team_name"], "line": float(r["line"]),
                     "projected": None if r["projected"] is None else float(r["projected"]),
                     "conf": r["conf"] or "",
                     "last_wins": None if r["last_wins"] is None else float(r["last_wins"]),
                     "over_odds": r.get("over_odds"), "under_odds": r.get("under_odds")}
                    for r in db.get_win_lines(season)]
            _switch_to_vegas(season, rows)
        if not rows:
            table = project_win_totals()
            rows = [{"team": r.TEAM, "team_name": r.NAME, "line": float(r.LINE),
                     "projected": float(r.PROJECTED), "conf": r.CONF,
                     "last_wins": float(r.LAST_WINS), "over_odds": _odds(r.OVER_ODDS),
                     "under_odds": _odds(r.UNDER_ODDS)} for r in table.itertuples()]
            if rows and db.available:
                db.freeze_win_lines(season, rows)
        if rows:
            _lines_cache[season] = (time.time(), rows)
        return rows


_crowd_cache = {}


def crowd_counts(season, fresh=False):
    """Kalabalik dagilimi. Her ziyaretcide sorgulamamak icin 30 sn bellekte."""
    hit = _crowd_cache.get(season)
    if not fresh and hit and time.time() - hit[0] < 30:
        return hit[1]
    counts = db.win_pick_counts(season) if db.available else {}
    _crowd_cache[season] = (time.time(), counts)
    return counts


def _american(odds):
    return f"+{odds}" if odds and odds > 0 else str(odds)


def _card_rows(rows, picks, crowd, identity):
    out = []
    for r in rows:
        look = identity.get(r["team"], {})
        counts = crowd.get(r["team"], {})
        votes = counts.get(OVER, 0) + counts.get(UNDER, 0)
        lean = None
        if r.get("over_odds") is not None and r.get("under_odds") is not None:
            p = implied_over(r["over_odds"], r["under_odds"])
            if p is not None and abs(p - 0.5) >= 0.015:
                lean = ("over", round(p * 100)) if p > 0.5 else ("under", round((1 - p) * 100))
        out.append({
            **r, "short": look.get("short") or r["team_name"], "logo": look.get("logo") or "",
            "color": look.get("color") or "#3987e5", "pick": picks.get(r["team"]),
            "over_share": round(100 * counts.get(OVER, 0) / votes) if votes else None,
            "votes": votes, "lean": lean,
            "over_label": _american(r["over_odds"]) if r.get("over_odds") is not None else None,
            "under_label": _american(r["under_odds"]) if r.get("under_odds") is not None else None,
            "conf_short": "East" if (r.get("conf") or "").startswith("East") else
                          "West" if (r.get("conf") or "").startswith("West") else "",
        })
    return out


@router.get("/over-under")
def page(request: Request):
    season = get_current_season_year()
    user = current_user(request)
    is_open, clock = deadline_state()
    rows = load_lines(season)
    picks = db.get_win_picks(user["id"], season) if (user and db.available) else {}
    crowd = crowd_counts(season)
    identity = get_team_identity()
    cards = sorted(_card_rows(rows, picks, crowd, identity), key=lambda r: -r["line"])
    overs = sum(1 for v in picks.values() if v == OVER)
    return render(request, "over_under.html", active="ou", cards=cards, picks=picks,
                  is_open=is_open, clock=clock, season_label=get_season_label(season),
                  overs=overs, unders=len(picks) - overs, total=len(rows),
                  db_ok=db.available)


@router.post("/api/ou/pick")
def pick(request: Request, payload: dict = Body(...)):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "Sign in to make picks."}, 401)
    is_open, _ = deadline_state()
    if not is_open:
        return JSONResponse({"error": "Picks are locked - the season has started."}, 403)
    season = get_current_season_year()
    team = str(payload.get("team") or "")
    choice = payload.get("pick")
    line = next((r["line"] for r in load_lines(season) if r["team"] == team), None)
    if line is None:
        return JSONResponse({"error": "Unknown team."}, 400)
    if choice in (None, "", "clear"):
        db.clear_win_pick(user["id"], season, team)
        return {"ok": True, "pick": None}
    if choice not in (OVER, UNDER):
        return JSONResponse({"error": "Pick over or under."}, 400)
    if not db.save_win_pick(user["id"], season, team, choice, line):
        return JSONResponse({"error": "That pick could not be saved. Try again."}, 500)
    return {"ok": True, "pick": choice}


def _user_picks(request):
    user = current_user(request)
    season = get_current_season_year()
    if not user:
        return None, season, {}
    return user, season, db.get_win_picks(user["id"], season)


@router.get("/over-under/card.png")
def card(request: Request):
    user, season, picks = _user_picks(request)
    if not user:
        return JSONResponse({"error": "Sign in first."}, 401)
    rows = load_lines(season)
    png = over_under_card(get_season_label(season), rows, picks, get_team_identity(),
                          owner=user.get("username"))
    return Response(png, media_type="image/png", headers={
        "Content-Disposition": f'inline; filename="over-under-{get_season_label(season)}.png"',
        "Cache-Control": "no-store"})


@router.get("/over-under/picks.csv")
def picks_csv(request: Request):
    user, season, picks = _user_picks(request)
    if not user:
        return JSONResponse({"error": "Sign in first."}, 401)
    crowd = crowd_counts(season)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["team", "team_name", "conference", "line", "over_odds", "under_odds",
                     "last_season_wins", "my_pick", "crowd_over_pct"])
    for r in sorted(load_lines(season), key=lambda r: -r["line"]):
        counts = crowd.get(r["team"], {})
        votes = counts.get(OVER, 0) + counts.get(UNDER, 0)
        writer.writerow([r["team"], r["team_name"], r.get("conf") or "", f'{r["line"]:.1f}',
                         _american(r["over_odds"]) if r.get("over_odds") is not None else "",
                         _american(r["under_odds"]) if r.get("under_odds") is not None else "",
                         "" if r.get("last_wins") is None else f'{r["last_wins"]:.0f}',
                         picks.get(r["team"], ""),
                         "" if not votes else round(100 * counts.get(OVER, 0) / votes)])
    return Response(buffer.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="over-under-{get_season_label(season)}.csv"'})

"""Ana sayfa: maclar, fantasy tablolari, oyuncu analizi, kutu skoru, trivia."""
import json
from datetime import date, datetime, timedelta

import pandas as pd
from fastapi import APIRouter, Body, Request
from fastapi.responses import HTMLResponse, JSONResponse

from services.database import FREE_WATCHLIST_LIMIT, db
from services.espn_api import calculate_game_score, get_injuries, get_score_color
from services.nba_season import (get_season_label, get_season_start_date,
                                 is_offseason)
from web import stats
from web.core import current_user, is_pro, render, templates

router = APIRouter()


def _parse_day(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _weight_overrides(request):
    out = {}
    for key in stats.BASE_WEIGHTS:
        raw = request.query_params.get(f"w_{key}")
        if raw in (None, ""):
            continue
        try:
            out[key] = float(raw)
        except ValueError:
            continue
    return out


@router.get("/")
def home(request: Request):
    user = current_user(request)
    pro = is_pro(user)
    q = request.query_params

    period = q.get("period", "today")
    if period not in stats.PERIODS:
        period = "today"
    build = q.get("build", "default")
    if build not in stats.PUNT_BUILDS and build not in stats.PRO_PUNT_BUILDS:
        build = "default"
    overrides = _weight_overrides(request)
    weights, locked = stats.weights_for(build, overrides, pro)

    # Istenen gun (varsayilan dun: bugunun maclari genelde henuz bitmedi)
    requested = _parse_day(q.get("date")) or (date.today() - timedelta(days=1))
    resolved, game_ids = stats.resolve_game_day(requested)
    games = stats.scoreboard(resolved) if resolved else []

    spoiler = False
    if user:
        mode = db.get_score_display_preference(user["id"])
        spoiler = mode in ("spoiler_protected", "hidden")

    game_cards = []
    for g in games:
        excitement = calculate_game_score(g.get("home_score"), g.get("away_score"), g.get("status"))
        game_cards.append({**g, "excitement": excitement,
                           "excite_color": get_score_color(excitement) if excitement else None,
                           "final": stats.is_final(g.get("status"))})

    # --- fantasy tablolari ---
    error = None
    daily = pd.DataFrame()
    try:
        if period == "today":
            table = stats.today_table(games, weights) if games else pd.DataFrame()
        elif period == "season":
            table = stats.season_table(weights)
        else:
            table, daily = stats.period_table(period, weights)
    except Exception as exc:
        print(f"home table failed: {exc}")
        table, error = pd.DataFrame(), "Stats could not be loaded from ESPN. Try again shortly."

    decimals = 0 if period == "today" else 1
    top = low = rows = []
    if not table.empty:
        ordered = table.sort_values("SCORE", ascending=False)
        rows = stats.table_rows(ordered, decimals)
        top = rows[:10]
        pool = table[table["MIN_INT"] >= 20] if "MIN_INT" in table.columns else table
        if len(pool) < 5 and "MIN_INT" in table.columns:
            pool = table[table["MIN_INT"] >= 5]
        low = stats.table_rows(pool.sort_values("SCORE", ascending=True).head(10), decimals)

    mvp, lvp, mvp_days = ([], [], 0)
    if period in ("week", "month") and not daily.empty:
        mvp, lvp, mvp_days = stats.mvp_lvp(daily, weights)

    offseason_note = None
    if is_offseason():
        start = get_season_start_date()
        days = (start.date() - date.today()).days
        if days > 0:
            offseason_note = (f"The {get_season_label()} season tips off in {days} days "
                              f"({start:%B %d, %Y}). Until then this page shows the most "
                              "recent completed games.")

    range_start, range_end = stats.date_range(period)
    return render(
        request, "home.html", active="home",
        period=period, periods=stats.PERIODS, build=build, locked=locked,
        builds=stats.PUNT_BUILDS, pro_builds=stats.PRO_PUNT_BUILDS,
        weights=weights, base_weights=stats.BASE_WEIGHTS, overrides=overrides,
        requested=requested, resolved=resolved, games=game_cards, spoiler=spoiler,
        top=top, low=low, rows=rows, mvp=mvp, lvp=lvp, mvp_days=mvp_days,
        range_start=range_start, range_end=range_end, error=error,
        offseason_note=offseason_note, decimals=decimals,
        query=request.url.query,
    )


@router.get("/api/boxscore/{game_id}", response_class=HTMLResponse)
def boxscore(request: Request, game_id: str, final: int = 1):
    user = current_user(request)
    players = stats.boxscore(game_id, final=bool(final))
    teams = {}
    for p in players or []:
        teams.setdefault(p.get("TEAM", "?"), []).append(p)
    for team_players in teams.values():
        team_players.sort(key=lambda p: -_minutes(p.get("MIN")))
    watch = set()
    if user:
        watch = {w["player_name"] for w in db.get_watchlist(user["id"])}
    return templates.TemplateResponse(request, "partials/boxscore.html", {
        "teams": teams, "user": user, "watch": watch})


def _minutes(value):
    try:
        return float(str(value).split(":")[0])
    except (TypeError, ValueError):
        return 0.0


@router.post("/api/insight", response_class=HTMLResponse)
def insight(request: Request, row: dict = Body(...)):
    user = current_user(request)
    try:
        info = stats.player_insight(row)
    except (KeyError, TypeError, ValueError):
        return HTMLResponse("<p class='bad'>That player could not be analysed.</p>")
    team = str(row.get("team") or "")
    out = []
    try:
        out = [i for i in get_injuries()
               if (i.get("team") or "").upper() == team.upper()
               and "out" in (i.get("status") or "").lower()
               and i.get("player") != row.get("player")]
    except Exception:
        pass
    watching = False
    if user:
        watching = any(w["player_name"] == row.get("player") for w in db.get_watchlist(user["id"]))
    return templates.TemplateResponse(request, "partials/insight.html", {
        "p": row, "info": info, "team_name": stats.TEAM_NAMES.get(team.upper(), team),
        "teammates_out": out[:4], "user": user, "watching": watching})


# ==================== TRIVIA ====================

@router.get("/api/trivia")
def trivia(request: Request):
    """Bugunun sorusu (dogru cevap GONDERILMEZ) ve oynanip oynanmadigi."""
    question = db.get_daily_trivia() if db.available else None
    if not question:
        return {"question": None}
    user = current_user(request)
    played = bool(user and db.check_user_played_trivia_today(user["id"]))
    return {
        "question": {
            "id": question["id"], "text": question["question"],
            "options": {k: question[f"option_{k.lower()}"] for k in "ABCD"},
        },
        "played": played,
        "streak": db.get_user_streak(user["id"]) if user else None,
        "signed_in": bool(user),
    }


@router.post("/api/trivia")
def trivia_answer(request: Request, payload: dict = Body(...)):
    question = db.get_daily_trivia() if db.available else None
    if not question or str(payload.get("id")) != str(question["id"]):
        return JSONResponse({"error": "Today's question has changed. Reload the page."}, 409)
    choice = str(payload.get("choice", "")).upper()[:1]
    if choice not in "ABCD" or not choice:
        return JSONResponse({"error": "Pick an answer."}, 400)
    user = current_user(request)
    correct = choice == str(question["correct_option"]).strip().upper()
    streak = None
    if user:
        if db.check_user_played_trivia_today(user["id"]):
            return JSONResponse({"error": "You already answered today's question."}, 409)
        db.mark_user_trivia_played(user["id"], correct=correct)
        streak = db.get_user_streak(user["id"])
    answer = str(question["correct_option"]).strip().upper()
    return {"correct": correct, "answer": answer,
            "answer_text": question.get(f"option_{answer.lower()}"),
            "explanation": question.get("explanation") or "", "streak": streak}


# ==================== IZLEME LISTESI (hizli ekleme) ====================

@router.post("/api/watchlist")
def watch_add(request: Request, payload: dict = Body(...)):
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "Sign in to track players."}, 401)
    name = str(payload.get("player") or "").strip()[:80]
    if not name:
        return JSONResponse({"error": "No player given."}, 400)
    existing = db.get_watchlist(user["id"])
    if any(w["player_name"] == name for w in existing):
        return {"ok": True, "message": f"{name} is already on your watchlist."}
    if not is_pro(user) and len(existing) >= FREE_WATCHLIST_LIMIT:
        return JSONResponse({"error": f"Free accounts hold {FREE_WATCHLIST_LIMIT} players. "
                                      "Remove one first."}, 403)
    note = str(payload.get("note") or "")[:200]
    if not db.add_to_watchlist(user["id"], name, note):
        return JSONResponse({"error": "Could not save. Try again."}, 500)
    return {"ok": True, "message": f"{name} added to your watchlist."}

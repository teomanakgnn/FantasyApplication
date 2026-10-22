"""Herkese acik NBA sayfalari: /nba/scores, /nba/game/{id}/{slug}, /nba/standings."""
from datetime import date, timedelta

from fastapi import APIRouter, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse

from services import nba_pages as nb
from services import player_pages as pp
from web import stats
from web.core import current_user, render

router = APIRouter()


def _parse(day):
    try:
        return date.fromisoformat(day)
    except (TypeError, ValueError):
        return None


@router.get("/nba/scores")
def scores(request: Request, date: str = ""):
    today = nb.today_et()
    day = _parse(date) or today
    games = nb.games_on(day)
    # Bugun mac yoksa en yakin gecmis mac gunu (sezon arasi, All-Star tatili)
    if not games and not date:
        for back in range(1, 8):
            games = nb.games_on(today - timedelta(days=back))
            if games:
                day = today - timedelta(days=back)
                break
    return render(request, "nba_scores.html", active="scores", day=day, today=today, games=games,
                  prev=day - timedelta(days=1), next=day + timedelta(days=1),
                  canonical="/nba/scores" if day == today or not date else f"/nba/scores?date={day.isoformat()}")


@router.get("/nba/game/{game_id}")
def game_short(game_id: str):
    g = _game(game_id)
    return RedirectResponse(g["path"], 301)


def _game(game_id):
    if not game_id.isdigit():
        raise HTTPException(404, "Game not found")
    try:
        g = nb.game(game_id)
    except Exception:
        g = None
    if not g:
        raise HTTPException(404, "Game not found")
    return g


@router.get("/nba/game/{game_id}/{slug}")
def game_page(request: Request, game_id: str, slug: str):
    g = _game(game_id)
    if request.url.path != g["path"]:
        return RedirectResponse(g["path"], 301)
    _, by_slug = pp.table()
    rows = [r for _, lst in g["box"] for r in lst]
    return render(request, "nba_game.html", active="scores", g=g,
                  open_ids=None if current_user(request) else stats.top_scorer_ids(rows),
                  player_slug=lambda name: pp.slugify(name or "") if pp.slugify(name or "") in by_slug else None)


@router.get("/nba/standings")
def standings(request: Request):
    try:
        confs = nb.standings()
    except Exception:
        confs = []
    return render(request, "nba_standings.html", active="standings", confs=confs, today=nb.today_et())

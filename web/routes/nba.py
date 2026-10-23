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
    from services.database import db
    simmed = db.sim_ids([g["game_id"] for g in games]) if db.available and games else set()
    for g in games:
        g["sim"] = g["game_id"] in simmed
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
    from services.database import db
    sim = db.get_sim(game_id) if db.available else None
    u = current_user(request)
    from services import game_sim
    from services import team_pages as tp
    g["away"]["page"], g["home"]["page"] = tp.path(g["away"]["abbr"]), tp.path(g["home"]["abbr"])
    return render(request, "nba_game.html", active="scores", g=g, sim=sim,
                  sim_record=game_sim.record() if sim and db.available else None,
                  is_admin=bool(u and u.get("username") in __import__("config").ADMIN_USERNAMES),
                  open_ids=None if current_user(request) else stats.top_scorer_ids(rows),
                  player_slug=lambda name: pp.slugify(name or "") if pp.slugify(name or "") in by_slug else None)


@router.get("/nba/teams")
def teams_index(request: Request):
    from services import team_pages as tp
    try:
        confs = nb.standings()
    except Exception:
        confs = []
    return render(request, "nba_teams.html", active="teams", confs=confs, all_teams=tp.teams(), team_of=tp.by_abbr)


@router.get("/nba/teams/{slug}")
def team_page(request: Request, slug: str):
    from services import team_pages as tp
    t = tp.team(slug.lower())
    if not t:
        raise HTTPException(404, "Team not found")
    _, by_slug = pp.table()
    return render(request, "nba_team.html", active="teams", t=t,
                  player_slug=lambda name: pp.slugify(name or "") if pp.slugify(name or "") in by_slug else None)


@router.get("/nba/simulations")
def simulations(request: Request):
    """Butun simulasyonlar ve modelin karnesi."""
    from services import game_sim
    from services.database import db
    rows = db.all_sims(120) if db.available else []
    items = []
    for r in rows:
        s = r["sim"]
        fav_home = s["p_home"] >= 0.5
        items.append({"day": r["day"], "s": s, "fav": s["home"] if fav_home else s["away"],
                      "p_fav": s["p_home"] if fav_home else s["p_away"],
                      "path": f"/nba/game/{r['game_id']}/{nb.game_slug(s['away'], s['home'])}",
                      "away_nick": nb.nick(s["away"]), "home_nick": nb.nick(s["home"])})
    return render(request, "nba_sims.html", active="scores", items=items, rec=game_sim.record() if db.available else None)


@router.post("/api/admin/sim/{game_id}")
def admin_sim(request: Request, game_id: str):
    """Yonetici: herhangi bir maci simdi simule et (gunluk secimden bagimsiz)."""
    import json

    import config
    from fastapi.responses import JSONResponse

    from services import game_sim
    from services.database import db
    from services.nba_season import get_current_season_year
    u = current_user(request)
    if not (u and u.get("username") in config.ADMIN_USERNAMES):
        return JSONResponse({"error": "Not available."}, 403)
    g = _game(game_id)
    day = g["when"].date() if g["when"] else nb.today_et()
    res = game_sim.simulate(game_id, g["away"]["abbr"], g["home"]["abbr"], get_current_season_year(), day=day)
    if not res:
        return JSONResponse({"error": "Not enough roster data to simulate."}, 400)
    db.save_sim(game_id, day, json.dumps(res))
    return {"ok": True, "p_home": res["p_home"]}


@router.get("/nba/standings")
def standings(request: Request):
    try:
        confs = nb.standings()
    except Exception:
        confs = []
    from services import team_pages as tp
    for c in confs:
        for r in c["rows"]:
            r["page"] = tp.path(r["abbr"])
    return render(request, "nba_standings.html", active="standings", confs=confs, today=nb.today_et())

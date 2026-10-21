"""Arama motoru sayfalari: /rankings, /players/{slug} ve /waiver-wire."""
from fastapi import APIRouter, Request
from fastapi.exceptions import HTTPException

from services import player_pages as pp
from services.trade_values import CATS
from web.core import current_user, render

router = APIRouter()
POSITIONS = {"": "All", "G": "Guards", "F": "Forwards", "C": "Centers"}


def _group(pos):
    pos = pos or ""
    if "C" in pos:
        return "C"
    return "G" if ("PG" in pos or "SG" in pos) and "PF" not in pos else "F"


@router.get("/rankings")
def rankings(request: Request, pos: str = "", punt: str = ""):
    rows, _ = pp.table()
    pos = pos if pos in POSITIONS else ""
    punt = punt if punt in pp.PUNTS else ""
    view = rows
    if punt:
        view = sorted(rows, key=lambda p: p["punt_rank"][punt])
    if pos:
        view = [p for p in view if _group(p["pos"]) == pos]
    return render(request, "rankings.html", active="rankings", rows=view[:300], cats=CATS, pos=pos, punt=punt,
                  positions=POSITIONS, punts=pp.PUNTS, tier=pp.tier, signed_in=bool(current_user(request)))


@router.get("/players/{slug}")
def player(request: Request, slug: str):
    rows, by_slug = pp.table()
    p = by_slug.get(slug.lower())
    if not p:
        raise HTTPException(404, "Player not found")
    log = None
    try:
        from services.nba_pages import player_log
        from services.nba_season import get_current_season_year
        log = player_log(str(p["id"]), get_current_season_year())
    except Exception as exc:
        print(f"game log failed for {slug}: {exc}")
    return render(request, "player.html", active="rankings", p=p, cats=CATS, outlook=pp.outlook(p), log=log,
                  similar=pp.similar(p, rows), adp=pp.adp_of(p["name"]), tier=pp.tier(p["rank"]),
                  punts=pp.PUNTS, signed_in=bool(current_user(request)))


def sitemap_paths():
    try:
        rows, _ = pp.table()
    except Exception:
        return []
    return [f"/players/{p['slug']}" for p in rows[:400]]


@router.get("/waiver-wire")
def waiver_wire(request: Request, window: str = "15", owned: int = 50, cat: str = ""):
    from services import waiver
    window = window if window in waiver.WINDOWS else "15"
    owned = owned if owned in (10, 25, 50) else 50
    cat = cat if cat in CATS else ""
    try:
        rows, hot = waiver.pickups(window, owned, cat or None), waiver.risers()
    except Exception as exc:
        print(f"waiver wire failed: {exc}")
        rows, hot = [], []
    _, by_slug = pp.table()
    slug = lambda name: pp.slugify(name or "") if pp.slugify(name or "") in by_slug else None
    from services.nba_pages import today_et
    return render(request, "waiver.html", active="waiver", rows=rows, hot=hot, cats=CATS, window=window,
                  windows=waiver.WINDOWS, owned=owned, cat=cat, week=waiver.week_number(), slug=slug,
                  today=today_et(), signed_in=bool(current_user(request)))

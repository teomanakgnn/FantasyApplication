"""
Takim sayfalari (/nba/teams, /nba/teams/{slug}): kadro ve sezon ortalamalari,
son ve siradaki maclar (mac sayfalarina bagli), istatistik liderleri, sakatlar,
puan durumundaki yer. Hepsi ESPN'in acik uclarindan, onbellekte.
"""
from datetime import datetime

from services.cache import cache_data
from services.nba_pages import EASTERN, game_slug, nick
from services.nba_season import espn_get, get_current_season_year

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"


@cache_data(ttl=24 * 3600, show_spinner=False, copy_result=False)
def teams():
    """30 takim: kisaltma, slug, ad, logo, renk."""
    d = espn_get(BASE, timeout=12).json()
    out = []
    for item in ((d.get("sports") or [{}])[0].get("leagues") or [{}])[0].get("teams") or []:
        t = item.get("team") or {}
        abbr = t.get("abbreviation")
        out.append({"abbr": abbr, "slug": t.get("slug"), "name": t.get("displayName"), "nick": t.get("name") or nick(abbr),
                    "location": t.get("location"), "id": t.get("id"), "color": "#" + (t.get("color") or "9AA6BD"),
                    "logo": f"https://a.espncdn.com/i/teamlogos/nba/500/{abbr}.png"})
    out.sort(key=lambda t: t["name"] or "")
    return out


def by_slug(slug):
    return next((t for t in teams() if t["slug"] == slug), None)


def by_abbr(abbr):
    return next((t for t in teams() if (t["abbr"] or "").upper() == (abbr or "").upper()), None)


def path(abbr):
    t = by_abbr(abbr)
    return f"/nba/teams/{t['slug']}" if t else None


def _f(v):
    try:
        f = float(v)
        return 0.0 if f != f else f
    except (TypeError, ValueError):
        return 0.0


@cache_data(ttl=600, show_spinner=False, copy_result=False)
def _schedule(abbr, season):
    d = espn_get(f"{BASE}/{abbr.lower()}/schedule?season={season}", timeout=12).json()
    games = []
    for e in d.get("events") or []:
        c = (e.get("competitions") or [{}])[0]
        me = next((x for x in c.get("competitors") or [] if (x.get("team") or {}).get("abbreviation") == abbr), None)
        opp = next((x for x in c.get("competitors") or [] if x is not me), None)
        if not me or not opp:
            continue
        score = lambda x: (x.get("score") or {}).get("displayValue") if isinstance(x.get("score"), dict) else x.get("score")
        try:
            when = datetime.fromisoformat(e["date"].replace("Z", "+00:00")).astimezone(EASTERN)
        except (KeyError, ValueError):
            when = None
        st = ((c.get("status") or {}).get("type") or {})
        oa = (opp.get("team") or {}).get("abbreviation")
        home = me.get("homeAway") == "home"
        games.append({"id": e.get("id"), "when": when, "home": home, "opp": oa, "opp_nick": nick(oa),
                      "opp_logo": f"https://a.espncdn.com/i/teamlogos/nba/500/{oa}.png",
                      "state": st.get("state"), "detail": st.get("shortDetail") or "",
                      "us": score(me), "them": score(opp), "won": me.get("winner"),
                      "path": f"/nba/game/{e.get('id')}/{game_slug(abbr if not home else oa, oa if not home else abbr)}"})
    games.sort(key=lambda g: g["when"] or datetime.min.replace(tzinfo=EASTERN))
    return games


@cache_data(ttl=3600, show_spinner=False, copy_result=False)
def _roster(team_id):
    d = espn_get(f"{BASE}/{team_id}/roster", timeout=12).json()
    out = []
    for a in d.get("athletes") or []:
        out.append({"id": str(a.get("id") or ""), "name": a.get("displayName"), "jersey": a.get("jersey") or "",
                    "pos": (a.get("position") or {}).get("abbreviation") or "", "age": a.get("age"),
                    "height": a.get("displayHeight") or "", "weight": a.get("displayWeight") or "",
                    "college": (a.get("college") or {}).get("name") or "", "exp": (a.get("experience") or {}).get("years")})
    return out


def team(slug):
    t = by_slug(slug)
    if not t:
        return None
    from services import nba_pages
    from services.espn_api import get_injuries, get_nba_season_stats_official
    season = get_current_season_year()
    games = _schedule(t["abbr"], season)
    played = [g for g in games if g["state"] == "post"]
    upcoming = [g for g in games if g["state"] != "post"]

    cur = get_nba_season_stats_official(season)
    last = get_nba_season_stats_official(season - 1)
    by_id = lambda df: {str(r["PLAYER_ID"]): r for _, r in df.iterrows()} if df is not None and not df.empty else {}
    C, L = by_id(cur), by_id(last)
    roster = _roster(t["id"])
    for p in roster:
        c, l = C.get(p["id"]), L.get(p["id"])
        src, label = (c, "2026-27") if c is not None and (_f(c["GP"]) >= 5 or l is None) else (l, "2025-26") if l is not None else (None, "")
        p["season"] = label
        p["s"] = {k: _f(src[k]) for k in ("GP", "MIN", "PTS", "REB", "AST", "STL", "BLK", "3Pts", "FG%", "FT%")} if src is not None else None
    roster.sort(key=lambda p: -(p["s"]["MIN"] if p["s"] else 0))

    with_stats = [p for p in roster if p["s"] and p["s"]["GP"] >= 1]
    leaders = []
    for key, label in (("PTS", "Points"), ("REB", "Rebounds"), ("AST", "Assists"), ("STL", "Steals"), ("BLK", "Blocks"), ("3Pts", "3-pointers")):
        if with_stats:
            best = max(with_stats, key=lambda p: p["s"][key])
            leaders.append({"label": label, "p": best, "value": best["s"][key]})

    injuries = [i for i in get_injuries() or [] if (i.get("team") or "").upper() == t["abbr"].upper()]
    rank = None
    try:
        for conf in nba_pages.standings():
            for i, r in enumerate(conf["rows"], 1):
                if r["abbr"] == t["abbr"]:
                    rank = {"conf": conf["name"], "seed": i, **r}
    except Exception:
        pass
    w = sum(1 for g in played if g["won"])
    return {**t, "season": season, "played": played[-8:][::-1], "upcoming": upcoming[:6], "roster": roster,
            "leaders": leaders, "injuries": injuries, "rank": rank, "wins": w, "losses": len(played) - w,
            "next": upcoming[0] if upcoming else None}


def sitemap_paths():
    try:
        return ["/nba/teams"] + [f"/nba/teams/{t['slug']}" for t in teams()]
    except Exception:
        return []

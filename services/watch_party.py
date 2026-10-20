"""
Watch party (ikinci ekran): herkes maci kendi yayinindan izler, oda canli
skor, play-by-play, canli fantezi liderleri ve sohbet verir. Video yok.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from services.cache import cache_data
from services.espn_api import SUMMARY_URL
from services.nba_season import espn_get

EASTERN = ZoneInfo("America/New_York")


def today_et():
    return datetime.now(EASTERN).date()


@cache_data(ttl=8, show_spinner=False)
def game_state(game_id):
    """Skor, saat, ceyrek ve son oyunlar. Canli macta birkac saniyede bir tazelenir."""
    data = espn_get(f"{SUMMARY_URL}?event={game_id}", timeout=10).json()
    comp = ((data.get("header") or {}).get("competitions") or [{}])[0]
    st = (comp.get("status") or {})
    stype = st.get("type") or {}
    teams = {}
    for c in comp.get("competitors") or []:
        t = c.get("team") or {}
        teams[c.get("homeAway")] = {
            "id": str(t.get("id") or ""), "abbr": t.get("abbreviation"), "name": t.get("displayName"),
            "score": c.get("score") or "0",
            "logo": f"https://a.espncdn.com/i/teamlogos/nba/500/{t.get('abbreviation')}.png"}
    by_team = {v["id"]: v["abbr"] for v in teams.values()}
    plays = []
    for p in (data.get("plays") or [])[-30:]:
        plays.append({
            "id": str(p.get("id")), "text": p.get("text") or "", "q": (p.get("period") or {}).get("number"),
            "clock": (p.get("clock") or {}).get("displayValue", ""), "team": by_team.get(str((p.get("team") or {}).get("id"))),
            "scoring": bool(p.get("scoringPlay")), "home": p.get("homeScore"), "away": p.get("awayScore")})
    plays.reverse()
    return {
        "home": teams.get("home"), "away": teams.get("away"),
        "state": stype.get("state"),  # pre / in / post
        "detail": stype.get("shortDetail") or stype.get("description") or "",
        "final": stype.get("state") == "post", "plays": plays,
    }


def fantasy_leaders(game_id, final, n=8):
    from web import stats
    rows = stats.boxscore(game_id, final=final) or []
    out = []
    for r in rows:
        score = stats.fantasy_score(r, stats.BASE_WEIGHTS)
        out.append({"id": r.get("ID"), "name": r.get("PLAYER"), "team": r.get("TEAM"), "fp": round(score, 1),
                    "line": f"{r.get('PTS')} pts · {r.get('REB')} reb · {r.get('AST')} ast"
                            f"{' · ' + str(r.get('STL')) + ' stl' if str(r.get('STL')) not in ('0', '') else ''}"
                            f"{' · ' + str(r.get('BLK')) + ' blk' if str(r.get('BLK')) not in ('0', '') else ''}"})
    out.sort(key=lambda x: -x["fp"])
    return out[:n]

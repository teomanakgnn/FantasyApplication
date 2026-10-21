"""
Herkese acik NBA sayfalari (arama motorlari icin): gunun skorlari, mac
sayfasi (kutu skor + sut haritasi + ozet), puan durumu, oyuncu mac kaydi.
Hepsi ESPN'in acik uc noktalarindan; sonuclar onbellekte.
"""
import re
import threading
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from services.cache import cache_data
from services.espn_api import SUMMARY_URL
from services.nba_season import espn_get, get_season_start_date

EASTERN = ZoneInfo("America/New_York")
STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
GAMELOG_URL = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{id}/gamelog"

# ESPN kisaltmasi -> takma ad (adres ve metin icin)
NICK = {
    "ATL": "Hawks", "BOS": "Celtics", "BKN": "Nets", "CHA": "Hornets", "CHI": "Bulls", "CLE": "Cavaliers",
    "DAL": "Mavericks", "DEN": "Nuggets", "DET": "Pistons", "GS": "Warriors", "GSW": "Warriors", "HOU": "Rockets",
    "IND": "Pacers", "LAC": "Clippers", "LAL": "Lakers", "MEM": "Grizzlies", "MIA": "Heat", "MIL": "Bucks",
    "MIN": "Timberwolves", "NO": "Pelicans", "NOP": "Pelicans", "NY": "Knicks", "NYK": "Knicks", "OKC": "Thunder",
    "ORL": "Magic", "PHI": "76ers", "PHX": "Suns", "POR": "Trail Blazers", "SAC": "Kings", "SA": "Spurs",
    "SAS": "Spurs", "TOR": "Raptors", "UTA": "Jazz", "UTAH": "Jazz", "WSH": "Wizards", "WAS": "Wizards",
}


def today_et():
    return datetime.now(EASTERN).date()


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def nick(abbr):
    return NICK.get((abbr or "").upper(), abbr or "")


def game_slug(away, home):
    return f"{_slug(nick(away))}-vs-{_slug(nick(home))}"


def game_path(g):
    """Skor tablosu satirindan (game_id, away_team, home_team) mac sayfasi adresi."""
    return f"/nba/game/{g['game_id']}/{game_slug(g.get('away_team'), g.get('home_team'))}"


# ==================== GUNUN MACLARI ====================

@cache_data(ttl=45, show_spinner=False)
def _day_live(day):
    from services.espn_api import get_scoreboard
    return get_scoreboard(datetime.combine(day, datetime.min.time()))


@cache_data(ttl=6 * 3600, show_spinner=False)
def _day_past(day):
    from services.espn_api import get_scoreboard
    return get_scoreboard(datetime.combine(day, datetime.min.time()))


def games_on(day):
    """Bir gunun maclari (ABD Dogu tarihi). Iki gunden eskiler uzun sure saklanir."""
    games = _day_past(day) if day < today_et() - timedelta(days=1) else _day_live(day)
    out = []
    for g in games or []:
        q = dict(g)
        q["final"] = str(g.get("status", "")).lower().startswith("final")
        q["live"] = not q["final"] and str(g.get("status", "")) not in ("Scheduled", "Postponed", "Canceled", "Delayed")
        q["page"] = game_path(g)
        q["away_nick"], q["home_nick"] = nick(g.get("away_team")), nick(g.get("home_team"))
        out.append(q)
    return out


# ==================== MAC SAYFASI ====================

@cache_data(ttl=60, show_spinner=False)
def _summary(game_id):
    return espn_get(f"{SUMMARY_URL}?event={game_id}", timeout=10).json()


def path_for(game_id):
    """Yalnizca kimlikten mac sayfasi adresi (takim kisaltmalari ozetten)."""
    comp = ((_summary(game_id).get("header") or {}).get("competitions") or [{}])[0]
    side = {c.get("homeAway"): (c.get("team") or {}).get("abbreviation") for c in comp.get("competitors") or []}
    return f"/nba/game/{game_id}/{game_slug(side.get('away'), side.get('home'))}"


def game(game_id):
    """Mac sayfasi verisi: takimlar, ceyrekler, liderler, kutu skor, takim sut haritalari, ozet."""
    from web import stats
    d = _summary(game_id)
    comp = ((d.get("header") or {}).get("competitions") or [None])[0]
    if not comp:
        return None
    st = (comp.get("status") or {}).get("type") or {}
    teams = {}
    for c in comp.get("competitors") or []:
        t = c.get("team") or {}
        rec = next((r.get("displayValue") for r in c.get("record") or [] if r.get("type") == "total"), "")
        abbr = t.get("abbreviation")
        teams[c.get("homeAway")] = {
            "abbr": abbr, "name": t.get("displayName"), "nick": t.get("name") or nick(abbr), "record": rec,
            "score": int(c.get("score") or 0) if str(c.get("score") or "").isdigit() else None,
            "winner": bool(c.get("winner")), "logo": f"https://a.espncdn.com/i/teamlogos/nba/500/{abbr}.png",
            "quarters": [l.get("displayValue") for l in c.get("linescores") or []]}
    away, home = teams.get("away"), teams.get("home")
    if not away or not home:
        return None
    when = None
    try:
        when = datetime.fromisoformat(comp["date"].replace("Z", "+00:00")).astimezone(EASTERN)
    except (KeyError, ValueError):
        pass
    venue = ((d.get("gameInfo") or {}).get("venue") or {})
    final = st.get("state") == "post"
    started = st.get("state") in ("in", "post")

    rows = stats.boxscore(game_id, final=final) if started else []
    by_team = {}
    for r in rows or []:
        r = dict(r)
        r["FP"] = round(stats.fantasy_score(r, stats.BASE_WEIGHTS), 1)
        by_team.setdefault(r.get("TEAM"), []).append(r)
    for lst in by_team.values():
        lst.sort(key=lambda r: -_mins(r.get("MIN")))
    leaders = sorted((r for lst in by_team.values() for r in lst), key=lambda r: -r["FP"])[:6]

    # Takim sut haritalari
    team_of = {str(r.get("ID")): r.get("TEAM") for r in rows or []}
    charts = {}
    if started:
        try:
            from services.espn_api import get_cached_shots
            from web.stats import _live_shots
            shots = get_cached_shots(game_id) if final else _live_shots(game_id)
        except Exception:
            shots = {}
        for pid, lst in (shots or {}).items():
            t = team_of.get(pid)
            if not t:
                continue
            ch = charts.setdefault(t, {"shots": [], "zones": {"Paint": [0, 0], "Mid-range": [0, 0], "3PT": [0, 0]}})
            for s in lst:
                s = dict(s)
                dist = ((s["x"] - 25) ** 2 + s["y"] ** 2) ** .5
                z = "3PT" if s["three"] else "Paint" if dist <= 8 else "Mid-range"
                ch["zones"][z][1] += 1
                ch["zones"][z][0] += s["made"]
                s["sx"] = round(min(49.5, max(.5, s["x"])), 2)
                s["sy"] = round(min(35.5, max(.5, s["y"] + 5.25)), 2)
                ch["shots"].append(s)

    return {"id": str(game_id), "away": away, "home": home, "when": when, "final": final, "started": started,
            "detail": st.get("shortDetail") or st.get("description") or "", "state": st.get("state"),
            "venue": venue.get("fullName"), "city": ", ".join(x for x in ((venue.get("address") or {}).get("city"),
                                                                         (venue.get("address") or {}).get("state")) if x),
            "box": [(away["abbr"], by_team.get(away["abbr"], [])), (home["abbr"], by_team.get(home["abbr"], []))],
            "leaders": leaders, "charts": charts, "path": f"/nba/game/{game_id}/{game_slug(away['abbr'], home['abbr'])}",
            "recap": _recap(away, home, when, final, by_team)}


def _mins(v):
    try:
        return float(str(v).split(":")[0])
    except (TypeError, ValueError):
        return 0.0


def _line(r):
    parts = [f"{r.get('PTS')} points"]
    for key, word in (("REB", "rebounds"), ("AST", "assists"), ("STL", "steals"), ("BLK", "blocks")):
        try:
            if int(r.get(key) or 0) >= (8 if key in ("REB", "AST") else 3):
                parts.append(f"{r.get(key)} {word}")
        except ValueError:
            pass
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _recap(away, home, when, final, by_team):
    """Kisa, olgusal mac ozeti (arama motorlari ve yapay zeka asistanlari alintilasin)."""
    day = f"{when:%A, %B} {when.day}, {when.year}" if when else ""
    if not final or away["score"] is None:
        return (f"The {away['name']} visit the {home['name']}{' on ' + day if day else ''}. "
                "Box score, shot charts and fantasy stats update live once the game tips off.")
    win, lose = (home, away) if home["score"] > away["score"] else (away, home)
    text = (f"The {win['name']} beat the {lose['name']} {win['score']}-{lose['score']}"
            f"{' on ' + day if day else ''}{' at home' if win is home else ' on the road'}.")
    for t in (win, lose):
        lst = sorted(by_team.get(t["abbr"], []), key=lambda r: -int(r.get("PTS") or 0))
        if lst:
            text += f" {lst[0]['PLAYER']} led the {t['nick'] or t['name']} with {_line(lst[0])}."
    if win.get("record") and lose.get("record"):
        text += f" The {win['nick']} are {win['record']} and the {lose['nick']} {lose['record']}."
    return text


# ==================== PUAN DURUMU ====================

@cache_data(ttl=600, show_spinner=False)
def standings():
    d = espn_get(STANDINGS_URL, timeout=12).json()
    out = []
    for conf in d.get("children") or []:
        rows = []
        for e in (conf.get("standings") or {}).get("entries") or []:
            s = {x.get("name") or x.get("type"): x.get("displayValue") for x in e.get("stats") or []}
            t = e.get("team") or {}
            abbr = t.get("abbreviation")
            rows.append({"name": t.get("displayName"), "abbr": abbr, "logo": f"https://a.espncdn.com/i/teamlogos/nba/500/{abbr}.png",
                         "w": int(s.get("wins") or 0), "l": int(s.get("losses") or 0), "pct": s.get("winPercent"),
                         "gb": s.get("gamesBehind"), "home": s.get("Home"), "road": s.get("Road"),
                         "l10": s.get("Last Ten Games"), "streak": s.get("streak"), "diff": s.get("differential"),
                         "seed": int(s.get("playoffSeed") or 99)})
        rows.sort(key=lambda r: r["seed"])
        out.append({"name": conf.get("name"), "rows": rows})
    return out


# ==================== OYUNCU MAC KAYDI ====================

@cache_data(ttl=1800, show_spinner=False)
def player_log(espn_id, season):
    """Bu sezonun normal sezon maclari (yeniden eskiye) ve ortalamalar."""
    d = espn_get(GAMELOG_URL.format(id=espn_id) + f"?season={season}", timeout=10).json()
    labels = d.get("labels") or []
    meta = d.get("events") or {}
    games = []
    for stype in d.get("seasonTypes") or []:
        if "regular" not in (stype.get("displayName") or "").lower():
            continue
        for cat in stype.get("categories") or []:
            for ev in cat.get("events") or []:
                s = dict(zip(labels, ev.get("stats") or []))
                m = meta.get(ev.get("eventId")) or {}
                opp = (m.get("opponent") or {}).get("abbreviation")
                team = (m.get("team") or {}).get("abbreviation")
                try:
                    when = datetime.fromisoformat(m["gameDate"].replace("Z", "+00:00")).astimezone(EASTERN)
                except (KeyError, ValueError):
                    when = None
                at_home = m.get("atVs") == "vs"
                away, home = (opp, team) if at_home else (team, opp)
                games.append({"id": ev.get("eventId"), "when": when, "at": m.get("atVs"), "opp": opp,
                              "result": m.get("gameResult"), "score": m.get("score"), "s": s,
                              "path": f"/nba/game/{ev.get('eventId')}/{game_slug(away, home)}"})
    games.sort(key=lambda g: g["when"] or datetime.min.replace(tzinfo=EASTERN), reverse=True)
    avg = None
    if games:
        def tot(key):
            t = 0.0
            for g in games:
                try:
                    t += float(g["s"].get(key) or 0)
                except ValueError:
                    pass
            return t

        def made(key):
            m = a = 0
            for g in games:
                try:
                    x, y = str(g["s"].get(key) or "0-0").split("-")
                    m, a = m + int(x), a + int(y)
                except ValueError:
                    pass
            return m, a
        n = len(games)
        fg, tp, ft = made("FG"), made("3PT"), made("FT")
        avg = {"gp": n, "min": tot("MIN") / n, "pts": tot("PTS") / n, "reb": tot("REB") / n, "ast": tot("AST") / n,
               "stl": tot("STL") / n, "blk": tot("BLK") / n, "to": tot("TO") / n, "tpm": tp[0] / n,
               "fg": 100 * fg[0] / fg[1] if fg[1] else None, "ft": 100 * ft[0] / ft[1] if ft[1] else None,
               "tp": 100 * tp[0] / tp[1] if tp[1] else None}
    return {"games": games, "avg": avg}


# ==================== SITE HARITASI DIZINI ====================
# Sezonun biten maclari arka planda toplanir; site haritasi ve IndexNow
# bildirimleri buradan okur (istekte ESPN'e 170 gun sorgu atilmasin).

_INDEX = {"games": [], "built": None}
_LOCK = threading.Lock()


def refresh_index():
    start = get_season_start_date().date()
    today = today_et()
    if start > today:
        start = today - timedelta(days=3)
    found = []
    day = start
    while day <= today:
        for g in games_on(day):
            # Hazirlik maclari haritaya girmez (1 = preseason)
            if g["final"] and g.get("season_type") != 1:
                found.append((g["page"], day))
        day += timedelta(days=1)
    with _LOCK:
        old = {p for p, _ in _INDEX["games"]}
        _INDEX["games"] = found
        _INDEX["built"] = datetime.now(EASTERN)
    return [p for p, _ in found if p not in old]


def indexed_games():
    with _LOCK:
        return list(_INDEX["games"])

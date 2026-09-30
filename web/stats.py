"""
Ana sayfanin istatistik mantigi: puanlama, donem toplama, MVP/LVP ve
oyuncu yorumlari.

Eskiden components/tables.py ve components/mvp_lvp.py icinde Streamlit
cizimiyle ic iceydi. Burada yalnizca veri var; cizim sablonlarda.
"""
from collections import Counter
from datetime import date, datetime, timedelta

import pandas as pd

from services.cache import cache_data
from services.espn_api import (get_boxscore, get_cached_boxscore,
                               get_current_team_rosters, get_game_ids_in_range,
                               get_last_available_game_date,
                               get_nba_season_stats_official, get_scoreboard)
from services.nba_season import get_season_start_date
from utils.helpers import parse_minutes
from utils.images import headshot

# ==================== PUANLAMA ====================

BASE_WEIGHTS = {
    "PTS": 0.75, "REB": 0.5, "AST": 0.8, "STL": 1.7, "BLK": 1.6, "TO": -1.5,
    "FGA": -0.9, "FGM": 1.2, "FTA": -0.55, "FTM": 1.1, "3Pts": 0.6,
}

# Punt build = bir kategoriden vazgecip digerlerinde one gecmek.
PUNT_BUILDS = {
    "default": ("Default", ()),
    "punt-ft": ("Punt FT%", ("FTM", "FTA")),
    "punt-fg": ("Punt FG%", ("FGM", "FGA")),
    "punt-to": ("Punt turnovers", ("TO",)),
}
PRO_PUNT_BUILDS = {
    "punt-pts": ("Punt points", ("PTS",)),
    "punt-ast": ("Punt assists", ("AST",)),
    "punt-reb": ("Punt rebounds", ("REB",)),
    "punt-3": ("Punt threes", ("3Pts",)),
}

PERIODS = {"today": "Today", "week": "This Week", "month": "This Month",
           "season": "Season"}

TEAM_NAMES = {
    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
    'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
    'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
    'GSW': 'Golden State Warriors', 'GS': 'Golden State Warriors',
    'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
    'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
    'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
    'NOP': 'New Orleans Pelicans', 'NO': 'New Orleans Pelicans',
    'NYK': 'New York Knicks', 'NY': 'New York Knicks',
    'OKC': 'Oklahoma City Thunder', 'ORL': 'Orlando Magic',
    'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings',
    'SAS': 'San Antonio Spurs', 'SA': 'San Antonio Spurs',
    'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'UTAH': 'Utah Jazz',
    'WSH': 'Washington Wizards',
}

STAT_KEYS = ["PTS", "REB", "AST", "STL", "BLK", "TO", "FGM", "FGA", "3Pts",
             "3PTA", "FTM", "FTA", "+/-"]


def weights_for(build, overrides=None, pro=False):
    """
    Secilen build ve (varsa) elle girilen katsayilarla puanlama tablosu.

    Pro build'i Pro olmayan kullanici secerse varsayilana duser;
    ``locked`` bunu ekranda soylemek icin doner.
    """
    weights = dict(BASE_WEIGHTS)
    for key, value in (overrides or {}).items():
        if key in weights and value is not None:
            weights[key] = float(value)
    locked = build in PRO_PUNT_BUILDS and not pro
    if not locked:
        _, punted = PUNT_BUILDS.get(build) or PRO_PUNT_BUILDS.get(build) or ("", ())
        for stat in punted:
            weights[stat] = 0.0
    return weights, locked


def fantasy_score(stats, weights):
    score = 0.0
    for stat, weight in weights.items():
        try:
            score += float(stats.get(stat, 0) or 0) * float(weight)
        except (TypeError, ValueError):
            pass
    return score


def _norm(name):
    if not name:
        return ""
    return name.replace(".", "").replace("'", "").replace("-", " ").lower().strip()


def _roster_index():
    """{normallesmis ad: {team, id, name}} - guncel kadrolar."""
    try:
        rosters = get_current_team_rosters()
    except Exception:
        rosters = {}
    index = {}
    for name, info in (rosters or {}).items():
        if isinstance(info, dict):
            index[_norm(name)] = {"team": info.get("team"), "id": info.get("id"),
                                  "name": name}
        else:
            index[_norm(name)] = {"team": info, "id": None, "name": name}
    return index


# ==================== MACLAR ====================

@cache_data(ttl=30, show_spinner=False)
def scoreboard(day):
    """Gunun maclari. Canli skor oldugu icin kisa sure onbellekte."""
    return get_scoreboard(datetime.combine(day, datetime.min.time()))


@cache_data(ttl=60, show_spinner=False)
def _live_boxscore(game_id):
    return get_boxscore(game_id)


def boxscore(game_id, final=True):
    """
    Bir macin kutu skoru.

    Biten mac degismez, uzun sure saklanir. Suren macin skoru dakika
    dakika degistigi icin en fazla bir dakika onbellekte kalir. (Eski
    surum her maci 24 saat sakliyordu: canli maca bakan kullanici
    ertesi gune kadar ilk gordugu sayilari goruyordu.)
    """
    if final:
        return get_cached_boxscore(game_id)
    return _live_boxscore(game_id)


def is_final(status):
    return str(status or "").lower().startswith("final")


@cache_data(ttl=60, show_spinner=False)
def resolve_game_day(day):
    """Istenen gune en yakin mac gunu ve o gunun mac kimlikleri."""
    resolved, ids = get_last_available_game_date(datetime.combine(day, datetime.min.time()))
    if isinstance(resolved, datetime):
        resolved = resolved.date()
    return resolved, ids


# ==================== DONEM TABLOLARI ====================

def date_range(period, today=None):
    today = today or date.today()
    if period == "week":
        return today - timedelta(days=today.weekday()), today
    if period == "month":
        return today.replace(day=1), today
    if period == "season":
        start = get_season_start_date()
        if start.date() > today:
            start = get_season_start_date(start.year)
        return start.date(), today
    return today, today


def _day_rows(games):
    """Bir gunun tum kutu skorlari -> oyuncu satirlari."""
    rows = []
    for game in games:
        players = boxscore(game["game_id"], final=is_final(game.get("status")))
        for p in players or []:
            row = dict(p)
            row["GAME_ID"] = game["game_id"]
            rows.append(row)
    return rows


def _numeric(df, columns):
    for col in columns:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def today_table(games, weights):
    """Tek mac gunu: her oyuncunun o gunku satiri."""
    rows = _day_rows(games)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = _numeric(df, STAT_KEYS)
    df["MIN_INT"] = df["MIN"].apply(parse_minutes) if "MIN" in df.columns else 0
    df = df[df["MIN_INT"] > 0].copy() if (df["MIN_INT"] > 0).any() else df
    index = _roster_index()
    df["PLAYER_ID"] = df["PLAYER"].map(lambda n: (index.get(_norm(n)) or {}).get("id"))
    df["GAMES"] = 1
    df["SCORE"] = df.apply(lambda r: fantasy_score(r, weights), axis=1)
    return df


@cache_data(ttl=900, show_spinner=False)
def _period_games(start, end):
    """Donemdeki her gunun oyuncu satirlari (tarihli)."""
    import concurrent.futures

    date_game_map = get_game_ids_in_range(start, end)
    tasks = [(d, gid) for d, ids in date_game_map.items() for gid in ids]
    today = date.today()

    def fetch(task):
        day, gid = task
        # Bugunun maclari surebilir; gecmis gunler kesin bitmistir.
        players = boxscore(gid, final=day < today)
        return [dict(p, DATE=day) for p in players or []]

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        for chunk in pool.map(fetch, tasks):
            rows.extend(chunk)
    return rows


def period_table(period, weights):
    """
    Hafta / ay: gunluk satirlar ve oyuncu basi ortalamalar.

    Returns:
        (ortalama tablo, gunluk tablo)
    """
    start, end = date_range(period)
    rows = _period_games(start, end)
    if not rows:
        return pd.DataFrame(), pd.DataFrame()
    daily = pd.DataFrame(rows)
    daily = _numeric(daily, STAT_KEYS)
    daily["MIN_INT"] = daily["MIN"].apply(parse_minutes) if "MIN" in daily.columns else 0
    daily = daily[daily["MIN_INT"] > 0].copy()
    if daily.empty:
        return pd.DataFrame(), pd.DataFrame()

    index = _roster_index()
    info = daily["PLAYER"].map(lambda n: index.get(_norm(n)) or {})
    daily["PLAYER"] = [i.get("name") or n for i, n in zip(info, daily["PLAYER"])]
    daily["CUR_TEAM"] = [i.get("team") or t for i, t in zip(info, daily["TEAM"])]
    daily["PLAYER_ID"] = [i.get("id") for i in info]
    daily["SCORE"] = daily.apply(lambda r: fantasy_score(r, weights), axis=1)

    agg = daily.groupby("PLAYER").agg(
        TEAM=("CUR_TEAM", "last"), PLAYER_ID=("PLAYER_ID", "first"),
        GAMES=("PLAYER", "size"), MIN_INT=("MIN_INT", "mean"),
        **{k: (k, "mean") for k in STAT_KEYS}).reset_index()
    teams_played = daily.groupby("PLAYER")["TEAM"].agg(lambda s: sorted(set(s)))
    agg["TRADED"] = agg["PLAYER"].map(
        lambda n: " → ".join(teams_played.get(n, [])) if len(teams_played.get(n, [])) > 1 else "")
    agg["SCORE"] = agg.apply(lambda r: fantasy_score(r, weights), axis=1)
    return agg, daily


# Sezon basinda anlamli siralama icin gereken asgari mac sayisi.
MIN_GAMES_FLOOR, MIN_GAMES_CAP = 3, 10


def season_table(weights):
    """Resmi sezon ortalamalari (tek istek)."""
    df = get_nba_season_stats_official()
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    games = pd.to_numeric(df.get("GP"), errors="coerce").fillna(0)
    played = int(games.max() or 0)
    if played > MIN_GAMES_FLOOR:
        threshold = max(MIN_GAMES_FLOOR, min(MIN_GAMES_CAP, played // 3))
        kept = df[games >= threshold]
        df = kept if not kept.empty else df
    df = _numeric(df, STAT_KEYS)
    df["GAMES"] = pd.to_numeric(df.get("GP"), errors="coerce").fillna(0).astype(int)
    df["MIN_INT"] = pd.to_numeric(df.get("MIN"), errors="coerce").fillna(0)
    index = _roster_index()
    info = df["PLAYER"].map(lambda n: index.get(_norm(n)) or {})
    df["TEAM"] = [i.get("team") or t for i, t in zip(info, df.get("TEAM", ""))]
    if "PLAYER_ID" not in df.columns or df["PLAYER_ID"].isna().all():
        df["PLAYER_ID"] = [i.get("id") for i in info]
    df["SCORE"] = df.apply(lambda r: fantasy_score(r, weights), axis=1)
    return df


# ==================== MVP / LVP ====================

def mvp_lvp(daily, weights, top=10, min_minutes=20):
    """
    Donemdeki her mac gununun ilk ve son 10'una kac kez girildi.

    Yalnizca gercek gunluk veride anlamli. Eski surum sezon icin ayni
    sezon ortalamasini 82 "gun" olarak cogaltip ayni siralamayi 82 kez
    sayiyordu; o yuzden sezon icin hesaplanmiyor.
    """
    if daily is None or daily.empty or "DATE" not in daily.columns:
        return [], [], 0
    best, worst, teams = Counter(), Counter(), {}
    days = 0
    for _, day_df in daily.groupby("DATE"):
        pool = day_df[day_df["MIN_INT"] >= min_minutes]
        if pool.empty:
            continue
        days += 1
        for _, r in pool.iterrows():
            teams.setdefault(r["PLAYER"], (r.get("CUR_TEAM") or r.get("TEAM"), r.get("PLAYER_ID")))
        for name in pool.nlargest(top, "SCORE")["PLAYER"]:
            best[name] += 1
        for name in pool.nsmallest(top, "SCORE")["PLAYER"]:
            worst[name] += 1

    def rows(counter):
        return [{"player": n, "team": teams.get(n, ("", None))[0],
                 "photo": headshot(teams.get(n, ("", None))[1]), "count": c}
                for n, c in counter.most_common(12)]
    return rows(best), rows(worst), days


# ==================== TABLO SATIRLARI ====================

def table_rows(df, decimals):
    """DataFrame -> sablonun kullandigi sade sozlukler."""
    out = []
    for _, r in df.iterrows():
        def num(key):
            try:
                return float(r.get(key, 0) or 0)
            except (TypeError, ValueError):
                return 0.0
        out.append({
            "player": r.get("PLAYER", ""),
            "team": r.get("TEAM", "") if not isinstance(r.get("TEAM"), dict) else r["TEAM"].get("team", ""),
            "id": None if pd.isna(r.get("PLAYER_ID")) else r.get("PLAYER_ID"),
            "photo": headshot(None if pd.isna(r.get("PLAYER_ID")) else r.get("PLAYER_ID")),
            "games": int(num("GAMES") or 1),
            "score": round(num("SCORE"), 1),
            "min": round(num("MIN_INT"), 1),
            "pts": num("PTS"), "reb": num("REB"), "ast": num("AST"),
            "stl": num("STL"), "blk": num("BLK"), "to": num("TO"),
            "fgm": num("FGM"), "fga": num("FGA"), "tpm": num("3Pts"),
            "tpa": num("3PTA"), "ftm": num("FTM"), "fta": num("FTA"),
            "pm": num("+/-"), "traded": r.get("TRADED", "") or "",
            "decimals": decimals,
        })
    return out


# ==================== OYUNCU YORUMU ====================

def player_insight(p, weights_score=None):
    """
    Bir oyuncu satiri icin yorumlar (eski 'Player Insights' penceresi).

    p: table_rows ciktisindaki sozluk (ortalama veya tek mac).
    """
    single = int(p.get("games", 1)) == 1
    games = int(p.get("games", 1))
    score = float(p.get("score", 0))
    mins = float(p.get("min", 0))
    pts, reb, ast = p["pts"], p["reb"], p["ast"]
    stl, blk, to = p["stl"], p["blk"], p["to"]
    fgm, fga, ftm, fta = p["fgm"], p["fga"], p["ftm"], p["fta"]
    tpm, tpa, pm = p["tpm"], p["tpa"], p["pm"]

    stocks = stl + blk
    fp_min = score / mins if mins > 0 else 0
    fg_pct = fgm / fga * 100 if fga > 0 else 0
    ft_pct = ftm / fta * 100 if fta > 0 else 0
    tp_pct = tpm / tpa * 100 if tpa > 0 else 0
    ts_att = fga + 0.44 * fta
    ts_pct = pts / (2 * ts_att) * 100 if ts_att > 0 else 0
    ast_to = ast / to if to > 0 else ast
    impact = pts + reb + ast + stl + blk - to
    per = "in this game" if single else "per game"

    notes = []

    def add(kind, title, text):
        notes.append({"kind": kind, "title": title, "text": text})

    if fp_min >= 1.5:
        add("good", "Elite efficiency", f"{fp_min:.2f} fantasy points per minute is elite territory.")
    elif fp_min >= 1.2:
        add("good", "Strong efficiency", f"{fp_min:.2f} FP/min is well above league average.")
    elif fp_min < 0.8 and mins > 20:
        add("bad", "Inefficient", f"Only {fp_min:.2f} FP/min across {mins:.0f} minutes.")

    if pts >= 30:
        add("good", "Dominant scoring", f"{pts:.1f} points {per} - carrying the offence.")
    elif pts >= 20 and fg_pct >= 50:
        add("good", "Efficient scoring", f"{pts:.1f} points on {fg_pct:.1f}% shooting.")
    elif pts >= 20 and fg_pct < 40:
        add("warn", "Volume scorer", f"{pts:.1f} points but only {fg_pct:.1f}% from the field.")
    elif fga >= 15 and pts < 15:
        add("bad", "Shot selection", f"{fga:.0f} attempts for {pts:.1f} points.")

    if ast >= 10 and ast_to >= 2.5:
        add("good", "Elite playmaking", f"{ast:.1f} assists at {ast_to:.1f} assists per turnover.")
    elif ast >= 7:
        add("good", "Facilitator", f"{ast:.1f} assists {per}.")
    elif ast >= 5 and to > ast:
        add("warn", "Turnovers", f"{to:.1f} turnovers against {ast:.1f} assists.")

    if reb >= 15:
        add("good", "Owning the glass", f"{reb:.1f} rebounds {per}.")
    elif reb >= 10:
        add("good", "Strong rebounder", f"{reb:.1f} rebounds {per}.")

    if stocks >= 5:
        add("good", "Defensive menace", f"{stl:.1f} steals + {blk:.1f} blocks.")
    elif stocks >= 3:
        add("good", "Active defender", f"{stocks:.1f} steals plus blocks.")

    if ts_pct >= 65:
        add("good", "Exceptional shooting", f"{ts_pct:.1f}% true shooting.")
    elif ts_pct < 50 and fga >= 12:
        add("bad", "Poor shooting", f"{ts_pct:.1f}% true shooting on {fga:.0f} attempts.")

    if tpm >= 5:
        add("good", "Sharpshooting", f"{tpm:.0f} threes made.")
    elif tpa >= 8 and tp_pct < 30:
        add("warn", "Cold from three", f"{tpm:.0f}/{tpa:.0f} from deep ({tp_pct:.1f}%).")

    if mins >= 38 and single:
        add("info", "Heavy minutes", f"{mins:.0f} minutes - trusted in crunch time.")
    elif mins < 20 and score >= 25:
        add("good", "Ultra-efficient", f"{score:.1f} fantasy points in {mins:.0f} minutes.")
    elif mins < 15 and single:
        add("warn", "Limited role", f"Only {mins:.0f} minutes.")

    if pm >= 15:
        add("good", "Game changer", f"+{pm:.0f} plus/minus.")
    elif pm <= -10:
        add("bad", "Negative impact", f"{pm:.0f} plus/minus.")

    if single:
        ladder = [(60, "elite", "Historic game"), (45, "elite", "Elite production"),
                  (35, "good", "Strong performance"), (25, "good", "Solid contributor"),
                  (18, "neutral", "Decent output"), (10, "warn", "Below expectations"),
                  (-999, "bad", "Poor output")]
    else:
        ladder = [(50, "elite", "MVP calibre"), (40, "elite", "All-Star level"),
                  (32, "good", "High-end starter"), (25, "good", "Solid starter"),
                  (18, "neutral", "Flex / streamer"), (12, "warn", "Deep leagues only"),
                  (-999, "bad", "Not fantasy relevant")]
    for floor, rating, title in ladder:
        if score >= floor:
            outlook = {"rating": rating, "title": title}
            break

    return {
        "single": single, "games": games, "notes": notes[:5], "outlook": outlook,
        "kpis": [("FP / min", f"{fp_min:.2f}"), ("TS%", f"{ts_pct:.1f}%"),
                 ("Impact", f"{impact:.0f}"), ("AST/TO", f"{ast_to:.1f}"),
                 ("+/-", f"{pm:+.0f}")],
        "shooting": {"fg": f"{fgm:.1f}/{fga:.1f} ({fg_pct:.1f}%)",
                     "tp": f"{tpm:.1f}/{tpa:.1f} ({tp_pct:.1f}%)",
                     "ft": f"{ftm:.1f}/{fta:.1f} ({ft_pct:.1f}%)"},
    }

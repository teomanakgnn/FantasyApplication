"""
Sezonluk galibiyet baremleri (alt/ust tahmini icin).

Baremler Las Vegas'in sezonluk galibiyet cizgileri (VEGAS_LINES). Bu
pazar ucretsiz bir uctan alinamiyor (ESPN'in futures ucu yalnizca
sampiyon, konferans ve odul pazarlarini veriyor), o yuzden cizgiler elle
giriliyor.

Uygulamanin kendi modeli de duruyor: cizgi degil, kartta "bizim tahminimiz"
olarak Vegas'in yaninda gosteriliyor. Model iki sinyali birlestiriyor:

  1. Gecen sezonun galibiyet sayisi, ortalamaya dogru cekilerek. NBA'de
     takimlar yil bazinda ortalamaya doner; ham gecen sezon tek basina
     iyi takimi fazla iyi, kotu takimi fazla kotu gosterir.
  2. Kadro gucu: ESPN'in gelecek sezon oyuncu projeksiyonlarindan her
     takimin en iyi sekiz oyuncusunun beklenen uretimi. Takas ve serbest
     oyuncu hareketleri gecen sezonun rekoruna yansimadigi icin bu sinyal
     gerekli.

Iki sinyalin agirligi sabit degil, veriden cikiyor: kadro gucunun gecen
sezon galibiyetleriyle korelasyonu olculup regresyon egimi oradan
aliniyor.
"""

import pandas as pd
from services.cache import cache_data

from services.draft_data import get_draft_board
from services.nba_season import espn_get, get_current_season_year

STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
TEAMS_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"

# Las Vegas sezonluk galibiyet baremleri ve iki tarafin oranlari
# (Amerikan oran: -115 = 100 kazanmak icin 115 yatir). Anahtar ESPN'in
# takim kisaltmasi. Kaynak: kullanicinin verdigi Vegas tablosu, 30 Eylul 2026.
VEGAS_SEASON = 2027   # 2026-27 sezonu (ESPN sezon yili)
VEGAS_LINES = {
    "ATL": (43.5, -105, -115), "BOS": (51.5, -115, -105),
    "BKN": (24.5, +100, -120), "CHA": (39.5, +100, -120),
    "CHI": (29.5, -105, -115), "CLE": (47.5, -115, -105),
    "DAL": (34.5, -110, -110), "DEN": (49.5, +105, -125),
    "DET": (49.5, -105, -115), "GS": (40.5, +100, -130),
    "HOU": (47.5, -110, -110), "IND": (44.5, -125, +105),
    "LAC": (30.5, +100, -120), "LAL": (46.5, -105, -115),
    "MEM": (29.5, -120, +100), "MIA": (46.5, +105, -125),
    "MIL": (25.5, -115, -105), "MIN": (48.5, -110, -110),
    "NO": (27.5, -115, -105), "NY": (52.5, +100, -120),
    "OKC": (62.5, -105, -115), "ORL": (43.5, -130, +110),
    "PHI": (50.5, +100, -120), "PHX": (40.5, -110, -110),
    "POR": (42.5, +100, -120), "SA": (59.5, -115, -105),
    "SAC": (21.5, -105, -115), "TOR": (45.5, -125, +105),
    "UTAH": (37.5, -120, +100), "WSH": (34.5, -110, -110),
}


def vegas_lines(season):
    """{takim: (barem, ust orani, alt orani)}; o sezon icin cizgi yoksa bos."""
    return VEGAS_LINES if season == VEGAS_SEASON else {}


def implied_over(over_odds, under_odds):
    """
    Oranlardan, bahis sirketinin payi (vig) cikarilmis 'ust' olasiligi.

    -130 / +110 gibi bir cift piyasanin ust tarafa egildigini soyler;
    iki tarafin ham olasiliklari toplami 1'i gectigi icin normalize edilir.
    """
    def raw(odds):
        odds = float(odds)
        return -odds / (-odds + 100) if odds < 0 else 100 / (odds + 100)
    try:
        over, under = raw(over_odds), raw(under_odds)
    except (TypeError, ValueError):
        return None
    return over / (over + under) if over + under else None


GAMES_IN_SEASON = 82
AVERAGE_WINS = GAMES_IN_SEASON / 2

# Gecen sezonun ne kadari tasiniyor. NBA'de yil bazinda galibiyet
# korelasyonu ~0.6-0.7 bandinda; ortasi aliniyor.
CARRYOVER = 0.65

# Kadro gucu sinyalinin nihai tahmindeki payi.
ROSTER_WEIGHT = 0.45

# Her takimdan kac oyuncu sayilsin. Fantasy havuzu derin bench'i
# icermiyor; sekiz oyuncu rotasyonun agirligini temsil ediyor.
ROSTER_DEPTH = 8


@cache_data(ttl=86400, show_spinner=False)
def get_last_season_records(season_year=None):
    """
    Gecen sezonun takim rekorlari.

    Returns:
        DataFrame - TEAM, NAME, WINS, LOSSES. Ulasilamazsa bos.
    """
    season = (season_year or get_current_season_year()) - 1
    try:
        resp = espn_get(STANDINGS_URL, params={"season": season}, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        print(f"NBA klasmani alinamadi: {exc}")
        return pd.DataFrame(columns=["TEAM", "NAME", "WINS", "LOSSES"])

    rows = []
    for group in payload.get("children") or []:
        conference = group.get("abbreviation") or group.get("name") or "?"
        for entry in (group.get("standings") or {}).get("entries") or []:
            team = entry.get("team") or {}
            stats = {s.get("name"): s.get("value") for s in entry.get("stats") or []}
            if stats.get("wins") is None:
                continue
            rows.append({
                "TEAM": team.get("abbreviation") or "?",
                "NAME": team.get("displayName") or team.get("abbreviation") or "?",
                "CONF": conference,
                "WINS": float(stats["wins"]),
                "LOSSES": float(stats.get("losses") or 0),
            })
    return pd.DataFrame(rows)


@cache_data(ttl=604800, show_spinner=False)
def get_team_identity():
    """
    Takim logosu ve renkleri: {ABBR: {logo, color, alt}}.

    Koyu zeminli logo varyanti tercih ediliyor; uygulamanin arka plani
    koyu ve bazi takimlarin normal logosu orada kayboluyor.
    """
    try:
        resp = espn_get(TEAMS_URL, timeout=20)
        resp.raise_for_status()
        teams = resp.json()["sports"][0]["leagues"][0]["teams"]
    except Exception as exc:
        print(f"Takim kimlikleri alinamadi: {exc}")
        return {}

    out = {}
    for wrapper in teams:
        team = wrapper.get("team") or {}
        abbr = team.get("abbreviation")
        if not abbr:
            continue
        logos = team.get("logos") or []
        dark = [l["href"] for l in logos if "dark" in (l.get("rel") or [])]
        default = [l["href"] for l in logos if "default" in (l.get("rel") or [])]
        out[abbr] = {
            "logo": (dark or default or [l.get("href") for l in logos] or [""])[0],
            "color": f"#{team.get('color') or '3987e5'}",
            "alt": f"#{team.get('alternateColor') or 'ffffff'}",
            "short": team.get("shortDisplayName") or abbr,
        }
    return out


def _roster_strength(board, depth=ROSTER_DEPTH):
    """
    Her NBA takiminin projeksiyona dayali kadro gucu.

    Oyuncunun beklenen sezonluk katkisi = mac basi fantasy uretimi x
    oynamasi beklenen mac sayisi. Sakat bir yildiz kadroyu, sahada
    gecirdigi kadar guclendirir.
    """
    if board.empty:
        return pd.Series(dtype="float64")

    df = board.copy()
    points = pd.to_numeric(df.get("FPTS"), errors="coerce").fillna(0.0)
    games = pd.to_numeric(df.get("PROJ_GP"), errors="coerce")
    games = games.where(games > 0)
    played = pd.to_numeric(df.get("GP"), errors="coerce")
    games = games.fillna(played.where(played > 0))
    games = games.fillna(float(games.median()) if games.notna().any() else 65.0)

    df = df.assign(_CONTRIB=points * games)
    df = df[df["TEAM"].notna() & (df["TEAM"] != "FA")]
    return (df.sort_values("_CONTRIB", ascending=False)
              .groupby("TEAM")
              .head(depth)
              .groupby("TEAM")["_CONTRIB"]
              .sum())


@cache_data(ttl=86400, show_spinner=False)
def project_win_totals(season_year=None):
    """
    Takim basina projekte galibiyet sayisi ve alt/ust baremi.

    Barem her zaman .5 ile bitiyor: beraberlik (push) olmasin diye.

    Returns:
        DataFrame - TEAM, NAME, LAST_WINS, PROJECTED, LINE, kaynak notu ile.
        Veri yoksa bos DataFrame.
    """
    records = get_last_season_records(season_year)
    if records.empty:
        return pd.DataFrame(columns=["TEAM", "NAME", "CONF", "LAST_WINS",
                                     "PROJECTED", "LINE"])

    strength = _roster_strength(get_draft_board())
    table = records.copy()
    table["STRENGTH"] = table["TEAM"].map(strength)

    # Kadrosu eslesmeyen takim olursa ligin ortasina oturt.
    if table["STRENGTH"].notna().any():
        table["STRENGTH"] = table["STRENGTH"].fillna(table["STRENGTH"].median())
    else:
        table["STRENGTH"] = 0.0

    # Gecen sezon, ortalamaya dogru cekilmis hali.
    regressed = AVERAGE_WINS + CARRYOVER * (table["WINS"] - AVERAGE_WINS)

    # Kadro gucunu galibiyete cevir. Egim veriden: standartlastirilmis
    # kadro gucunun gecen sezon galibiyetleriyle korelasyonu x galibiyet
    # dagiliminin std'si (regresyon katsayisinin ta kendisi).
    strength_sd = float(table["STRENGTH"].std(ddof=0))
    wins_sd = float(table["WINS"].std(ddof=0))
    if strength_sd > 0 and wins_sd > 0:
        z_strength = (table["STRENGTH"] - table["STRENGTH"].mean()) / strength_sd
        correlation = float(table["STRENGTH"].corr(table["WINS"]) or 0.0)
        roster_wins = AVERAGE_WINS + z_strength * correlation * wins_sd
    else:
        correlation = 0.0
        roster_wins = pd.Series(AVERAGE_WINS, index=table.index)

    projected = (1 - ROSTER_WEIGHT) * regressed + ROSTER_WEIGHT * roster_wins

    # Lig toplami 82*30/2 = 1230 galibiyet olmak zorunda; modelin toplami
    # kaymissa hepsini ayni miktarda kaydirip toplami duzeltiyoruz.
    projected = projected + (AVERAGE_WINS - projected.mean())
    projected = projected.clip(lower=15.0, upper=68.0)

    table["PROJECTED"] = projected.round(1)
    # .5'e yuvarla: alt/ust tahmininde beraberlik olmasin.
    table["LINE"] = (projected.round(0) - 0.5).clip(lower=14.5, upper=67.5)
    table["CORRELATION"] = round(correlation, 3)

    # Vegas cizgisi varsa barem odur; model yalnizca kiyas icin kalir.
    vegas = vegas_lines(season_year or get_current_season_year())
    table["OVER_ODDS"] = table["TEAM"].map(lambda t: vegas.get(t, (None,) * 3)[1])
    table["UNDER_ODDS"] = table["TEAM"].map(lambda t: vegas.get(t, (None,) * 3)[2])
    table["LINE"] = [vegas[t][0] if t in vegas else line
                     for t, line in zip(table["TEAM"], table["LINE"])]

    table["LAST_WINS"] = table["WINS"]
    columns = ["TEAM", "NAME", "CONF", "LAST_WINS", "PROJECTED", "LINE",
               "OVER_ODDS", "UNDER_ODDS", "CORRELATION"]
    return (table[columns]
            .sort_values("LINE", ascending=False)
            .reset_index(drop=True))

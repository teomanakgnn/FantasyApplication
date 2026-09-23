"""
ESPN fantasy ligi okuyucusu.

Bu modul, daha once headless Chromium'la ESPN'in HTML sayfasini kaziyan
``selenium_scraper``in yerini aliyor. Kazima yaklasimi her soguk
baslangicta surucu indiriyordu, ``/usr/bin/chromium`` yolunu sabit
kodladigi icin gelistirme makinesinde hic calismiyordu ve ESPN sayfa
yapisini her degistirdiginde kiriliyordu.

Burada draft havuzunun zaten kullandigi fantasy API'si okunuyor:
tek bir JSON istegi, tarayici yok.

API'nin gercekten verdigi sey: sezon basindan bugune kategori
toplamlari, takim puan durumu ve hafta hafta eslesmeler. Haftalik
kategori kirilimi gecmis haftalar icin donmuyor (``statBySlot`` bos
geliyor); o yuzden kategori tablosu sezon toplami olarak etiketleniyor.
"""
import pandas as pd
import requests
import streamlit as st

from services.nba_season import get_current_season_year

BASE = ("https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba"
        "/seasons/{season}/segments/0/leagues/{league_id}")

# ESPN kategori kimlikleri -> uygulamanin kullandigi etiketler
STAT_IDS = {
    0: "PTS", 1: "BLK", 2: "ST", 3: "AST", 6: "REB", 11: "TO",
    13: "FGM", 14: "FGA", 15: "FTM", 16: "FTA", 17: "3PTM",
    19: "FG%", 20: "FT%",
}

# Roto/H2H hesaplarinin bekledigi dokuz kategori
NINE_CAT = ["FG%", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK", "TO"]


class LeagueError(Exception):
    """Kullaniciya gosterilebilecek, anlasilir lig hatasi."""


def _cookies():
    """
    Ozel ligler icin ESPN oturum cerezleri.

    Herkese acik liglerde gerekmiyor. Tanimli degilse sessizce bos
    donuyor; istek yine denenir ve ozel ligse 401 ile anlasilir bir
    hata uretilir.
    """
    try:
        return {"espn_s2": st.secrets["espn_s2"], "SWID": st.secrets["swid"]}
    except Exception:
        return {}


@st.cache_data(ttl=600, show_spinner=False)
def fetch_league(league_id, season=None, views=("mTeam", "mSettings")):
    """Lig verisini ceker. On bellek 10 dakika."""
    season = int(season or get_current_season_year())
    url = BASE.format(season=season, league_id=int(league_id))
    params = [("view", v) for v in views]
    try:
        response = requests.get(url, params=params, cookies=_cookies(), timeout=20)
    except requests.RequestException as exc:
        raise LeagueError("Could not reach ESPN. Check your connection and try "
                          "again.") from exc

    if response.status_code == 401:
        raise LeagueError("This league is private. Sign-in cookies are needed to "
                          "read it.")
    if response.status_code == 404:
        raise LeagueError(f"No league {league_id} in the {season} season. Check "
                          "the league ID and the season.")
    if response.status_code != 200:
        raise LeagueError(f"ESPN returned {response.status_code}. Try again in a "
                          "moment.")
    try:
        return response.json()
    except ValueError as exc:
        raise LeagueError("ESPN sent a response we could not read.") from exc


def league_info(league_id, season=None):
    data = fetch_league(league_id, season)
    settings = data.get("settings") or {}
    return {
        "name": settings.get("name") or f"League {league_id}",
        "teams": len(data.get("teams") or []),
        "scoring": (settings.get("scoringSettings") or {}).get("scoringType"),
        "season": int(season or get_current_season_year()),
    }


def league_categories(league_id, season=None):
    """Ligin gercekten oynadigi kategoriler, ESPN ayarlarindan."""
    data = fetch_league(league_id, season)
    items = ((data.get("settings") or {}).get("scoringSettings") or {}).get(
        "scoringItems") or []
    cats = [STAT_IDS.get(item.get("statId")) for item in items]
    cats = [c for c in cats if c]
    return cats or list(NINE_CAT)


def _team_name(team):
    name = (team.get("name") or "").strip()
    if name:
        return name
    # Eski liglerde ad iki parcaya bolunmus olabiliyor
    parts = [team.get("location"), team.get("nickname")]
    joined = " ".join(p for p in parts if p).strip()
    return joined or team.get("abbrev") or f"Team {team.get('id')}"


def get_league_standings(league_id, season=None):
    """
    Puan durumu tablosu.

    Kazima surumuyle ayni sekilde bir DataFrame donuyor ki cagiran
    taraf degismek zorunda kalmasin.
    """
    data = fetch_league(league_id, season)
    rows = []
    for team in data.get("teams") or []:
        record = ((team.get("record") or {}).get("overall") or {})
        rows.append({
            "Team": _team_name(team),
            "W": int(record.get("wins") or 0),
            "L": int(record.get("losses") or 0),
            "T": int(record.get("ties") or 0),
            "PCT": round(float(record.get("percentage") or 0.0), 3),
            "GB": round(float(record.get("gamesBack") or 0.0), 1),
        })
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows).sort_values(
        ["W", "PCT"], ascending=[False, False]).reset_index(drop=True)
    frame.insert(0, "Rank", range(1, len(frame) + 1))
    return frame


def _stats_for(team, categories):
    """Takimin sezon basindan bugune kategori toplamlari."""
    values = team.get("valuesByStat") or {}
    out = {}
    for stat_id, label in STAT_IDS.items():
        if label not in categories:
            continue
        value = values.get(str(stat_id))
        if value is None:
            continue
        out[label] = round(float(value), 3) if label in ("FG%", "FT%") else float(value)
    return out


def matchup_periods(league_id, season=None):
    data = fetch_league(league_id, season, views=("mMatchupScore",))
    periods = {m.get("matchupPeriodId") for m in (data.get("schedule") or [])}
    return sorted(p for p in periods if p)


def get_league_matchups(league_id, season=None, matchup_period=None):
    """
    Bir haftanin eslesmeleri, takim kategori toplamlariyla.

    Donen sekil kazima surumuyle ayni: her eslesme icin ``home_team`` ve
    ``away_team``, her birinde ``name`` ve ``stats``.

    Not: ESPN gecmis haftalar icin haftalik kategori kirilimi vermiyor,
    bu yuzden ``stats`` sezon basindan bugune toplamdir. Eslesmenin
    kendi hafta sonucu (galibiyet/beraberlik/maglubiyet) ayrica
    ``period_score`` altinda dondurulur.
    """
    data = fetch_league(league_id, season,
                        views=("mTeam", "mSettings", "mMatchupScore"))
    categories = league_categories(league_id, season)
    teams = {t.get("id"): t for t in (data.get("teams") or [])}
    schedule = data.get("schedule") or []
    if not schedule:
        return []

    if matchup_period is None:
        matchup_period = max((m.get("matchupPeriodId") or 0) for m in schedule)

    out = []
    for match in schedule:
        if match.get("matchupPeriodId") != matchup_period:
            continue
        pair = {}
        for side in ("home", "away"):
            entry = match.get(side) or {}
            team = teams.get(entry.get("teamId"))
            if not team:
                pair = {}
                break
            score = entry.get("cumulativeScore") or {}
            pair[f"{side}_team"] = {
                "id": team.get("id"),
                "name": _team_name(team),
                "abbrev": team.get("abbrev"),
                "stats": _stats_for(team, categories),
                "period_score": {
                    "wins": score.get("wins") or 0,
                    "losses": score.get("losses") or 0,
                    "ties": score.get("ties") or 0,
                },
            }
        if pair:
            pair["matchup_period"] = matchup_period
            out.append(pair)
    return out

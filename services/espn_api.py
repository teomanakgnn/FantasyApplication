import requests
from datetime import datetime, timedelta
import streamlit as st
from functools import lru_cache
import concurrent.futures
from typing import Dict, List, Optional, Union
import pandas as pd

from services.nba_season import (
    SEASON_TYPE_REGULAR,
    espn_get,
    get_current_season_year,
    get_season_label,
    get_season_start_date,
    get_session,
    season_candidates,
)


# =================================================================
# NBA SCOREBOARD & BOXSCORE FONKSİYONLARI (MEVCUT - DEĞİŞMEDİ)
# =================================================================

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"

@st.cache_data(ttl=86400) # 24 saat cache
def get_nba_teams_dynamic():
    """
    ESPN API'den güncel NBA takımlarını ve ID'lerini dinamik olarak çeker.
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams?limit=100"
    try:
        data = espn_get(url, timeout=10).json()
        teams_map = {} # {id: abbreviation} örn: {'13': 'LAL'}
        
        # JSON yolu: sports -> leagues -> teams -> team
        for sport in data.get('sports', []):
            for league in sport.get('leagues', []):
                for team_entry in league.get('teams', []):
                    team = team_entry.get('team', {})
                    t_id = team.get('id')
                    t_abbr = team.get('abbreviation')
                    t_name = team.get('displayName')
                    
                    if t_id and t_abbr:
                        teams_map[t_id] = {
                            'abbr': t_abbr,
                            'name': t_name
                        }
        return teams_map
    except Exception as e:
        print(f"Takım listesi çekilemedi: {e}")
        return {}

@st.cache_data(ttl=3600)
def get_game_ids(date):
    date_str = date.strftime("%Y%m%d")
    url = f"{SCOREBOARD_URL}?dates={date_str}"
    try:
        data = espn_get(url, timeout=10).json()
        return [e["id"] for e in data.get("events", [])]
    except Exception as e:
        print(f"Hata (get_game_ids): {e}")
        return []

def get_last_available_game_date(date, lookback_days=210, lookahead_days=90):
    """
    Verilen tarihe en yakın maç gününü bulur.

    Önce geriye doğru (o güne kadar oynanmış son maç günü), bulunamazsa
    ileriye doğru (sıradaki maç günü) bakar. Sezon arasında geriye 7 gün
    bakmak yetmiyordu ve ana sayfa tamamen boş kalıyordu; bu yüzden
    aralık bir sezonu kapsayacak kadar geniş tutuldu.

    Returns:
        (tarih, [maç_id]) - hiçbir şey bulunamazsa (None, [])
    """
    # Hızlı yol: tam o günde maç var mı?
    ids = get_game_ids(date)
    if ids:
        return date, ids

    day = date.date() if isinstance(date, datetime) else date

    # 1) Geriye doğru en son oynanan maç günü
    past = get_game_ids_in_range(day - timedelta(days=lookback_days), day)
    if past:
        latest = max(past)
        return latest, past[latest]

    # 2) İleriye doğru sıradaki maç günü (sezon öncesi dönem)
    future = get_game_ids_in_range(day, day + timedelta(days=lookahead_days))
    if future:
        soonest = min(future)
        return soonest, future[soonest]

    return None, []

def get_scoreboard(date):
    """GÜNÜN MAÇLARI + SKOR + OT KONTROLÜ"""
    date_str = date.strftime("%Y%m%d")
    url = f"{SCOREBOARD_URL}?dates={date_str}"
    try:
        data = espn_get(url, timeout=10).json()
    except Exception:
        return []

    games = []
    for event in data.get("events", []):
        try:
            comp = event["competitions"][0]
            home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
            away = next(c for c in comp["competitors"] if c["homeAway"] == "away")

            status_obj = comp["status"]
            status_desc = status_obj["type"]["description"]
            period = status_obj.get("period", 0)

            if status_desc == "Final" and period > 4:
                ot_count = period - 4
                if ot_count == 1:
                    status_desc = "Final/OT"
                else:
                    status_desc = f"Final/{ot_count}OT"

            games.append({
                "game_id": event["id"],
                "home_team": home["team"]["abbreviation"],
                "away_team": away["team"]["abbreviation"],
                "home_score": home.get("score", "0"),
                "away_score": away.get("score", "0"),
                "home_logo": f"https://a.espncdn.com/i/teamlogos/nba/500/{home['team']['abbreviation']}.png",
                "away_logo": f"https://a.espncdn.com/i/teamlogos/nba/500/{away['team']['abbreviation']}.png",
                "status": status_desc
            })
        except (KeyError, IndexError):
            continue
    return games

@st.cache_data(ttl=86400)
def get_cached_boxscore(game_id):
    return get_boxscore(game_id)

def get_boxscore(game_id):
    url = f"{SUMMARY_URL}?event={game_id}"
    try:
        data = espn_get(url, timeout=10).json()
    except Exception:
        return []

    players = []

    if "boxscore" not in data or "players" not in data["boxscore"]:
        return []

    for team in data["boxscore"]["players"]:
        team_abbr = (team.get("team") or {}).get("abbreviation", "UNK")

        for group in team.get("statistics", []):
            if "athletes" not in group:
                continue

            labels = group.get("labels") or []

            for athlete in group["athletes"]:
                # Bazı kayıtlarda oyuncu adı veya istatistik bloğu eksik
                # geliyor; tek bozuk satır yüzünden tüm maç kaybedilmesin.
                player_name = ((athlete.get("athlete") or {}).get("displayName")
                               or (athlete.get("athlete") or {}).get("fullName"))
                raw_stats = athlete.get("stats")
                if not player_name or not raw_stats:
                    continue

                stats = dict(zip(labels, raw_stats))
                stats["PLAYER"] = player_name
                stats["TEAM"] = team_abbr

                stats["FGM"] = 0; stats["FGA"] = 0
                stats["3Pts"] = 0; stats["3PTA"] = 0
                stats["FTM"] = 0; stats["FTA"] = 0

                if "FG" in stats:
                    val = str(stats["FG"])
                    if "-" in val:
                        m, a = val.split("-")
                        stats["FGM"] = int(m)
                        stats["FGA"] = int(a)

                t_val = None
                if "3PT" in stats: t_val = str(stats["3PT"])
                elif "3Pt" in stats: t_val = str(stats["3Pt"])
                elif "3P" in stats: t_val = str(stats["3P"])
                
                if t_val and "-" in t_val:
                    m, a = t_val.split("-")
                    stats["3Pts"] = int(m)
                    stats["3PTA"] = int(a)

                if "FT" in stats:
                    val = str(stats["FT"])
                    if "-" in val:
                        m, a = val.split("-")
                        stats["FTM"] = int(m)
                        stats["FTA"] = int(a)
                
                if "MIN" not in stats:
                    stats["MIN"] = "--"

                players.append(stats)

    return players

@st.cache_data(ttl=3600)
def get_injuries():
    """TÜM TAKIM SAKATLIKLARI"""
    try:
        response = espn_get(INJURIES_URL, timeout=10)
        data = response.json()
        
        if "injuries" not in data:
            print(f"'injuries' key bulunamadı. Mevcut keys: {list(data.keys())}")
            return []
            
    except Exception as e:
        print(f"Hata (get_injuries): {e}")
        import traceback
        traceback.print_exc()
        return []

    all_injuries = []
    
    for team_data in data.get("injuries", []):
        try:
            team_name = team_data.get("displayName", "Unknown Team")
            team_id = team_data.get("id", "")
            
            team_injuries = team_data.get("injuries", [])
            
            if not team_injuries:
                continue
                
            first_athlete = team_injuries[0].get("athlete", {})
            team_info = first_athlete.get("team", {})
            team_abbr = team_info.get("abbreviation", team_name[:3].upper())
            team_logos = team_info.get("logos", [])
            team_logo = team_logos[0]["href"] if team_logos else ""
            
            for injury in team_injuries:
                athlete = injury.get("athlete", {})
                
                player_photo = ""
                if "headshot" in athlete:
                    player_photo = athlete["headshot"].get("href", "")
                
                position_info = athlete.get("position", {})
                position = position_info.get("abbreviation", "N/A")
                
                all_injuries.append({
                    "team": team_abbr,
                    "team_name": team_name,
                    "team_logo": team_logo,
                    "player": athlete.get("displayName", "Unknown"),
                    "player_photo": player_photo,
                    "position": position,
                    "status": injury.get("status", "Unknown"),
                    "injury_type": injury.get("shortComment", "Unknown"),
                    "details": injury.get("longComment", "No details"),
                    "date": injury.get("date", "")
                })
                
        except (KeyError, IndexError) as e:
            print(f"Parse hatası ({team_name}): {e}")
            import traceback
            traceback.print_exc()
            continue
    
    return all_injuries


# services/espn_api.py

# byathlete yanıtındaki istatistik adlarını uygulama sütunlarına eşler.
# API artık oyuncu kaydı içinde 'names' göndermiyor ama yanıtın kökündeki
# 'categories' bloğunda tam şemayı veriyor; index tahmini yerine o kullanılır.
_STAT_NAME_TO_COLUMN = {
    "gamesPlayed": "GP",
    "avgMinutes": "MIN",
    "avgRebounds": "REB",
    "avgPoints": "PTS",
    "avgAssists": "AST",
    "avgTurnovers": "TO",
    "avgSteals": "STL",
    "avgBlocks": "BLK",
    "avgFieldGoalsMade": "FGM",
    "avgFieldGoalsAttempted": "FGA",
    "avgFreeThrowsMade": "FTM",
    "avgFreeThrowsAttempted": "FTA",
    "avgThreePointFieldGoalsMade": "3Pts",
    "avgThreePointFieldGoalsAttempted": "3PTA",
    "fieldGoalPct": "FG%",
    "freeThrowPct": "FT%",
    "threePointFieldGoalPct": "3P%",
    "avgFouls": "PF",
    "doubleDouble": "DD2",
    "tripleDouble": "TD3",
    "plusMinus": "+/-",
    "avgPlusMinus": "+/-",
}

_SEASON_STATS_COLUMNS = [
    "PLAYER", "PLAYER_ID", "TEAM", "POS", "GP", "MIN", "PTS", "REB", "AST",
    "STL", "BLK", "TO", "FGM", "FGA", "FTM", "FTA",
    "3Pts", "3PTA", "FG%", "FT%", "3P%", "PF", "DD2", "TD3", "+/-",
]

# Kategori bazlı index yedeği: API kökünde 'categories' şeması gelmezse
# kullanılır (2026 başında gözlemlenen sıralama).
_FALLBACK_INDEX_MAP = {
    "general": {0: "GP", 1: "MIN", 2: "PF", 6: "DD2", 7: "TD3", 11: "REB"},
    "offensive": {
        0: "PTS", 1: "FGM", 2: "FGA", 3: "FG%", 4: "3Pts", 5: "3PTA",
        6: "3P%", 7: "FTM", 8: "FTA", 9: "FT%", 10: "AST", 11: "TO",
    },
    "defensive": {0: "STL", 1: "BLK"},
}


def _build_category_index_map(payload):
    """
    Yanıtın kökündeki 'categories' şemasından
    {kategori_adı: {index: sütun}} haritası üretir.
    """
    index_map = {}
    for category in payload.get("categories") or []:
        name = category.get("name")
        names = category.get("names")
        if not name or not names:
            continue
        mapping = {}
        for idx, stat_name in enumerate(names):
            column = _STAT_NAME_TO_COLUMN.get(stat_name)
            # Aynı sütuna birden çok isim eşleşirse ilkini (ortalama) koru.
            if column and column not in mapping.values():
                mapping[idx] = column
        if mapping:
            index_map[name] = mapping
    return index_map or dict(_FALLBACK_INDEX_MAP)


def _fetch_byathlete_page(season_year, page, limit, season_type):
    params = {
        "region": "us", "lang": "en", "contentorigin": "espn",
        "isqualified": "false", "page": page, "limit": limit,
        "sort": "offensive.avgPoints:desc",
        "season": season_year,
        # KRİTİK: seasontype verilmezse ESPN, sezon bittiğinde playoff
        # istatistiklerini döndürüyor (582 yerine 230 oyuncu).
        "seasontype": season_type,
    }
    response = get_session().get(
        "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete",
        params=params,
        headers={"Referer": "https://www.espn.com/"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=3600, show_spinner=False)
def get_nba_season_stats_official(season_year=None, season_type=SEASON_TYPE_REGULAR):
    """
    Resmî ESPN sezon ortalamalarını çeker.

    Args:
        season_year: ESPN sezon yılı (2026-27 için 2027). None ise güncel
                     sezondan başlayıp veri bulunana kadar geri düşer.
        season_type: 2 = düzenli sezon (varsayılan), 3 = playoff.

    Returns:
        DataFrame - PLAYER, PLAYER_ID, TEAM, POS ve ortalama istatistikler.
        Veri bulunamazsa beklenen sütunlarla boş DataFrame.
    """
    attempts = [season_year] if season_year else season_candidates()

    payload = None
    used_season = None
    for candidate in attempts:
        try:
            data = _fetch_byathlete_page(candidate, page=1, limit=1000, season_type=season_type)
            if data.get("athletes"):
                payload = data
                used_season = candidate
                break
            print(f"   · {candidate} sezonunda veri yok, geri düşülüyor...")
        except Exception as exc:
            print(f"   · {candidate} sezonu çekilemedi: {exc}")

    if not payload:
        print("❌ Sezon istatistiği bulunamadı.")
        return pd.DataFrame(columns=_SEASON_STATS_COLUMNS)

    athletes = list(payload["athletes"])

    # Sayfalama: 1000 satırlık tek istek çoğu zaman yetiyor ama
    # kadro genişlerse kalan sayfaları da al.
    pagination = payload.get("pagination") or {}
    total_pages = int(pagination.get("pages") or 1)
    for page in range(2, min(total_pages, 5) + 1):
        try:
            extra = _fetch_byathlete_page(used_season, page, 1000, season_type)
            athletes.extend(extra.get("athletes") or [])
        except Exception as exc:
            print(f"   · sayfa {page} alınamadı: {exc}")
            break

    print(f"✓ {get_season_label(used_season)} sezonu: {len(athletes)} oyuncu")

    index_map = _build_category_index_map(payload)
    rows = []

    for entry in athletes:
        try:
            row = {col: 0.0 for col in _SEASON_STATS_COLUMNS}
            athlete = entry.get("athlete") or {}

            row["PLAYER"] = athlete.get("displayName") or "Unknown"
            row["PLAYER_ID"] = athlete.get("id")
            # ESPN artık 'team' nesnesi yerine teamShortName gönderiyor.
            row["TEAM"] = (
                athlete.get("teamShortName")
                or (athlete.get("teams") or [{}])[0].get("abbreviation")
                or (athlete.get("team") or {}).get("abbreviation")
                or "FA"
            )
            row["POS"] = (athlete.get("position") or {}).get("abbreviation") or ""

            for category in entry.get("categories") or []:
                mapping = index_map.get(category.get("name"))
                if not mapping:
                    continue
                values = category.get("values") or []
                for idx, column in mapping.items():
                    if idx < len(values) and values[idx] is not None:
                        row[column] = float(values[idx])

            # Yüzdeler kaynağa göre 0-1 veya 0-100 gelebiliyor; normalize et.
            for pct in ("FG%", "FT%", "3P%"):
                if 0 < row[pct] <= 1.0:
                    row[pct] *= 100

            if row["GP"] > 0:
                rows.append(row)
        except Exception:
            continue

    if not rows:
        return pd.DataFrame(columns=_SEASON_STATS_COLUMNS)

    df = pd.DataFrame(rows)
    for col in _SEASON_STATS_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0

    return df.sort_values(by="PTS", ascending=False).reset_index(drop=True)

@st.cache_data(ttl=86400)
def get_current_team_rosters():
    """
    Tüm NBA takımlarının güncel rosterlerini çeker.
    Dinamik ID listesi kullanır.
    Returns: Dict[player_name] = team_abbreviation
    """
    # Önce takımları API'den al
    nba_teams = get_nba_teams_dynamic()
    
    if not nba_teams:
        st.error("NBA takım listesi API'den çekilemedi.")
        return {}

    player_team_map = {}
    
    print(f"Rosterlar taranıyor: {len(nba_teams)} takım bulundu.")
    
# services/espn_api.py içindeki ilgili bölüm

    def fetch_single_roster(team_id, team_info):
        t_abbr = team_info['abbr']
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"
        try:
            resp = espn_get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                athletes = data.get('athletes', [])
                
                if not athletes and 'entries' in data:
                    athletes = [e.get('athlete', {}) for e in data['entries']]
                
                local_map = {}
                for ath in athletes:
                    p_name = ath.get('displayName') or ath.get('fullName')
                    p_id = ath.get('id')  # <--- ID BURADA ALINIYOR
                    
                    if p_name:
                        # Sadece takım ismini değil, sözlük döndürüyoruz
                        local_map[p_name] = {
                            'team': t_abbr,
                            'id': p_id
                        }
                return local_map
        except Exception:
            return {}
        return {}

    # Paralel istek at
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_team = {
            executor.submit(fetch_single_roster, t_id, info): t_id 
            for t_id, info in nba_teams.items()
        }
        
        for future in concurrent.futures.as_completed(future_to_team):
            result = future.result()
            if result:
                player_team_map.update(result)

    print(f"✓ Toplam {len(player_team_map)} oyuncu haritalandı.")
    return player_team_map
# =================================================================
# FANTASY LEAGUE FONKSİYONLARI - Basitleştirilmiş
# =================================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9"
}

def call_espn_api(league_id: int, views: list = None):
    """
    ESPN Fantasy lig verisini çeker.

    Önce leagueHistory (sezondan bağımsız) denenir; olmazsa güncel sezondan
    başlayarak sezon bazlı endpoint'e düşülür. Sezon yılları sabit değil,
    ESPN takviminden gelir.
    """
    if views is None:
        views = ['mMatchupScore', 'mScoreboard', 'mSettings', 'mTeam', 'modular', 'mNav']

    params = {'view': views}

    # 1) leagueHistory - sezon parametresi gerektirmez
    base_url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/leagueHistory/{league_id}"
    try:
        response = get_session().get(base_url, headers=HEADERS, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            # leagueHistory bir dizi döndürür, en son sezonu al
            if isinstance(data, list) and data:
                print(f"✓ leagueHistory: {len(data)} sezon bulundu, en yenisi kullanılıyor")
                return data[0]
    except Exception as e:
        print(f"leagueHistory başarısız: {e}")

    # 2) Sezon bazlı endpoint - güncel sezondan geriye doğru dene
    last_status = None
    for season in season_candidates():
        url = (f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba"
               f"/seasons/{season}/segments/0/leagues/{league_id}")
        try:
            response = get_session().get(url, headers=HEADERS, params=params, timeout=15)
            last_status = response.status_code

            if response.status_code == 401:
                raise PermissionError("Bu lig private. Sadece public ligler destekleniyor.")

            if response.status_code == 200:
                data = response.json()
                if 'teams' in data:
                    print(f"✓ {get_season_label(season)} sezonu - {len(data['teams'])} takım")
                    return data
        except PermissionError:
            raise
        except requests.exceptions.RequestException as e:
            print(f"{season} sezonu istenirken hata: {e}")

    raise RuntimeError(f"Lig verisi alınamadı (son durum: {last_status}). "
                       f"Lig ID'sinin doğru ve ligin public olduğundan emin olun.")

def get_team_dict(league_id: int):
    """Takım ID'lerini kısaltmalarıyla eşleştirir"""
    data = call_espn_api(league_id, views=['mTeam'])
    
    team_dict = {}
    for team in data.get('teams', []):
        team_dict[team['id']] = {
            'abbrev': team.get('abbrev', f"T{team['id']}"),
            'name': team.get('name', f"Team {team['id']}"),
            'logo': team.get('logo', '')
        }
    
    return team_dict

def get_teams(league_id: int, season: int = None) -> Dict:
    """
    Lig takımlarını çeker - season parametresi artık kullanılmıyor
    """
    print(f"\n{'='*60}")
    print(f"Fetching league {league_id}")
    print(f"{'='*60}\n")
    
    try:
        data = call_espn_api(league_id)
        
        teams = {}
        for team in data.get('teams', []):
            team_id = team['id']
            record = team.get('record', {}).get('overall', {})
            
            teams[team_id] = {
                "id": team_id,
                "name": team.get('name', f"Team {team_id}"),
                "abbrev": team.get('abbrev', f"T{team_id}"),
                "logo": team.get('logo', ''),
                "wins": record.get('wins', 0),
                "losses": record.get('losses', 0),
                "ties": record.get('ties', 0),
                "points_for": record.get('pointsFor', 0),
                "points_against": record.get('pointsAgainst', 0),
            }
        
        print(f"✓ Successfully retrieved {len(teams)} teams\n")
        return teams
        
    except PermissionError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"Liga verileri alınamadı.\n\n"
            f"Kontrol edin:\n"
            f"  • League ID doğru mu? (Girilen: {league_id})\n"
            f"  • Lig public mu? (Private ligler desteklenmiyor)\n"
            f"  • Liga aktif mi?\n\n"
            f"Hata: {str(e)}"
        )

def get_current_matchups(league_id: int, season: int = None) -> List[Dict]:
    """
    Bu haftanın maçlarını çeker
    """
    try:
        data = call_espn_api(league_id, views=['mMatchupScore', 'mScoreboard'])
        
        # Get current week
        current_week = data.get('status', {}).get('currentMatchupPeriod', 1)
        
        # Get team info
        team_dict = get_team_dict(league_id)
        
        # Get schedule
        schedule = data.get('schedule', [])
        
        matchups = []
        for matchup in schedule:
            # Only current week matchups
            if matchup.get('matchupPeriodId') != current_week:
                continue
            
            home_data = matchup.get('home', {})
            away_data = matchup.get('away', {})
            
            home_id = home_data.get('teamId')
            away_id = away_data.get('teamId')
            
            if not home_id or not away_id:
                continue
            
            home_team = team_dict.get(home_id, {})
            away_team = team_dict.get(away_id, {})
            
            matchups.append({
                "home_team": {
                    "name": home_team.get('name', 'Unknown'),
                    "abbrev": home_team.get('abbrev', '???'),
                    "logo": home_team.get('logo', '')
                },
                "away_team": {
                    "name": away_team.get('name', 'Unknown'),
                    "abbrev": away_team.get('abbrev', '???'),
                    "logo": away_team.get('logo', '')
                },
                "home_score": home_data.get('totalPoints', 0),
                "away_score": away_data.get('totalPoints', 0)
            })
        
        print(f"✓ Found {len(matchups)} matchups for week {current_week}")
        return matchups
        
    except Exception as e:
        print(f"Could not get matchups: {str(e)}")
        return []

def get_standings(league_id: int, season: int = None) -> List[Dict]:
    """Lig sıralamasını getirir"""
    teams = get_teams(league_id)
    
    return sorted(
        teams.values(),
        key=lambda t: (-t["wins"], -t["points_for"])
    )

# services/espn_api.py dosyasının en altına ekle:

_ACTIVE_STATS_COLUMNS = [
    'PLAYER', 'TEAM', 'PLAYER_ID', 'GP', 'MIN', 'PTS', 'REB', 'AST',
    'STL', 'BLK', 'TO', 'FGM', 'FGA', 'FTM', 'FTA', '3Pts', '3PM', '3PTA',
    'FG%', 'FT%', '3P%',
]


@st.cache_data(ttl=3600)
def get_active_players_stats(days=None, season_stats=True):
    """
    Aktif oyuncuların maç loglarından toplanmış ortalamalarını çeker.

    Args:
        days: Kaç günlük veri alınacak (None ise sezon başından itibaren)
        season_stats: True ise sezon başından, False ise son X gün
    """
    end_date = datetime.now()

    if season_stats or days is None:
        # Sezon başlangıcı ESPN takviminden gelir (bkz. services/nba_season.py).
        start_date = get_season_start_date()
        if start_date > end_date:
            # Sezon henüz başlamadı; bir önceki sezonun verisini göster.
            start_date = get_season_start_date(get_current_season_year() - 1)
        print(f"📊 Sezon istatistikleri: {start_date:%Y-%m-%d} - {end_date:%Y-%m-%d}")
    else:
        start_date = end_date - timedelta(days=days)
        print(f"📊 Son {days} gün istatistikleri")

    # GÜNCEL ROSTER BİLGİSİNİ ÇEK
    current_rosters = get_current_team_rosters()

    # İsim normalleştirme için yardımcı fonksiyon
    def normalize_name(name):
        """İsimleri karşılaştırma için normalize eder"""
        if not name:
            return ""
        return name.replace(".", "").replace("'", "").replace("-", " ").lower().strip()

    # Normalize edilmiş roster dictionary oluştur.
    # get_current_team_rosters() {'team': ..., 'id': ...} sözlüğü döndürür;
    # eski sürümlerde düz string dönebildiği için ikisi de desteklenir.
    normalized_rosters = {}
    for player_name, info in current_rosters.items():
        norm_name = normalize_name(player_name)
        if isinstance(info, dict):
            team_code, player_id = info.get('team'), info.get('id')
        else:
            team_code, player_id = info, None
        normalized_rosters[norm_name] = {
            'team': team_code,
            'id': player_id,
            'original_name': player_name
        }

    games_data = get_historical_boxscores(start_date, end_date)
    
    player_stats = {}
    
    # Güvenli sayı çevirme fonksiyonu
    def to_num(val):
        try:
            if val == '' or val is None or val == '--':
                return 0.0
            return float(val)
        except (ValueError, TypeError):
            return 0.0
    
    # Dakika parse fonksiyonu
    def parse_minutes(min_str):
        try:
            if min_str == '' or min_str is None or min_str == '--':
                return 0.0
            if isinstance(min_str, (int, float)):
                return float(min_str)
            if isinstance(min_str, str):
                if ':' in min_str:
                    parts = min_str.split(':')
                    return float(parts[0]) + float(parts[1]) / 60
                else:
                    return float(min_str)
            return 0.0
        except (ValueError, TypeError):
            return 0.0

    # Her maçtaki her oyuncu için istatistikleri topla
    for game in games_data:
        for p in game['players']:
            name = p.get('PLAYER', '')
            if not name:
                continue
            
            # Dakikayı parse et - 0 ise atla
            minutes_played = parse_minutes(p.get('MIN', 0))
            if minutes_played == 0:
                continue
            
            # Güncel takımı bul (normalize edilmiş isimle)
            norm_name = normalize_name(name)
            roster_info = normalized_rosters.get(norm_name)
            
            if roster_info:
                current_team = roster_info['team']
                player_id = roster_info['id']
                display_name = roster_info['original_name']
            else:
                current_team = p.get('TEAM', 'UNK')
                player_id = None
                display_name = name

            if display_name not in player_stats:
                player_stats[display_name] = {
                    'GP': 0, 'PTS': 0, 'REB': 0, 'AST': 0,
                    'STL': 0, 'BLK': 0, 'TO': 0,
                    'FGM': 0, 'FGA': 0, 'FTM': 0, 'FTA': 0,
                    '3Pts': 0, '3PTA': 0,
                    'TEAM': current_team,
                    'PLAYER_ID': player_id,
                    'MIN': 0,
                    'last_game_date': game['date']
                }
            
            stats = player_stats[display_name]
            stats['TEAM'] = current_team
            stats['GP'] += 1
            stats['MIN'] += minutes_played
            
            if game['date'] > stats['last_game_date']:
                stats['last_game_date'] = game['date']
            
            # İstatistikleri topla
            stats['PTS'] += to_num(p.get('PTS', 0))
            stats['REB'] += to_num(p.get('REB', 0))
            stats['AST'] += to_num(p.get('AST', 0))
            stats['STL'] += to_num(p.get('STL', 0))
            stats['BLK'] += to_num(p.get('BLK', 0))
            stats['TO']  += to_num(p.get('TO', 0))
            
            # FG istatistikleri - get_boxscore'dan gelen değerleri kullan
            stats['FGM'] += to_num(p.get('FGM', 0))
            stats['FGA'] += to_num(p.get('FGA', 0))
            stats['FTM'] += to_num(p.get('FTM', 0))
            stats['FTA'] += to_num(p.get('FTA', 0))
            stats['3Pts'] += to_num(p.get('3Pts', 0))
            stats['3PTA'] += to_num(p.get('3PTA', 0))

    # Ortalamaları hesapla - Sadece maç başına 10+ dakika oynayanlar
    final_list = []
    for name, s in player_stats.items():
        if s['GP'] == 0:
            continue
            
        avg_minutes = s['MIN'] / s['GP']
        
        # MAÇBAŞI 10 DAKİKADAN AZ OYNAYANLAR HARİÇ
        if avg_minutes < 10:
            continue
        
        # Yüzdeleri hesapla
        fg_pct = round((s['FGM'] / s['FGA'] * 100) if s['FGA'] > 0 else 0, 1)
        ft_pct = round((s['FTM'] / s['FTA'] * 100) if s['FTA'] > 0 else 0, 1)
        three_pct = round((s['3Pts'] / s['3PTA'] * 100) if s['3PTA'] > 0 else 0, 1)
        
        final_list.append({
            'PLAYER': name,
            'TEAM': s['TEAM'],
            'PLAYER_ID': s.get('PLAYER_ID'),
            'GP': s['GP'],
            'MIN': round(avg_minutes, 1),
            'PTS': round(s['PTS'] / s['GP'], 1),
            'REB': round(s['REB'] / s['GP'], 1),
            'AST': round(s['AST'] / s['GP'], 1),
            'STL': round(s['STL'] / s['GP'], 1),
            'BLK': round(s['BLK'] / s['GP'], 1),
            'TO': round(s['TO'] / s['GP'], 1),
            'FGM': round(s['FGM'] / s['GP'], 1),
            'FGA': round(s['FGA'] / s['GP'], 1),
            'FTM': round(s['FTM'] / s['GP'], 1),
            'FTA': round(s['FTA'] / s['GP'], 1),
            '3Pts': round(s['3Pts'] / s['GP'], 1),
            '3PM': round(s['3Pts'] / s['GP'], 1),  # Duplicate for compatibility
            '3PTA': round(s['3PTA'] / s['GP'], 1),
            'FG%': fg_pct,
            'FT%': ft_pct,
            '3P%': three_pct,
        })
    
    print(f"✓ {len(final_list)} aktif oyuncu bulundu (10+ dakika ortalaması)")

    if not final_list:
        # Seçilen aralıkta hiç maç yoksa (ör. sezon arası) boş ama
        # sütunları tam bir DataFrame döndür; çağıranlar .empty ile
        # kontrol ediyor ve sort_values sütun bulamayınca patlıyordu.
        return pd.DataFrame(columns=_ACTIVE_STATS_COLUMNS)

    return pd.DataFrame(final_list).sort_values(by="PTS", ascending=False)



def calculate_game_score(home_score, away_score, status_desc, 
                        home_offensive_rating=None, away_offensive_rating=None,
                        home_defensive_rating=None, away_defensive_rating=None,
                        lead_changes=None, home_team_stats=None, away_team_stats=None):
    """
    Maçın heyecan düzeyini 10 üzerinden hesaplar.
    
    Parametreler:
        home_score, away_score: Maç skoru
        status_desc: Maç durumu ("OT", "Final" vb.)
        home_offensive_rating, away_offensive_rating: Takım sezon ortalaması offensive rating
        home_defensive_rating, away_defensive_rating: Takım sezon ortalaması defensive rating
        lead_changes: Maçtaki liderlik değişim sayısı
        home_team_stats, away_team_stats: Takım sezon istatistikleri (dict: {'offensive_rating': x, 'defensive_rating': y})
    
    Kriterler:
        - Skor farkı (40%)
        - Tempo/Toplam skor (15%)
        - Liderlik değişimleri (25%)
        - Offensive/Defensive performans (15%)
        - Uzatma bonusu (5%)
    """
    try:
        h = int(home_score)
        a = int(away_score)
    except (ValueError, TypeError):
        return None  # Maç başlamamış

    # Stats'ten rating'leri al (eğer dict olarak gönderildiyse)
    if home_team_stats:
        home_offensive_rating = home_team_stats.get('offensive_rating', home_offensive_rating)
        home_defensive_rating = home_team_stats.get('defensive_rating', home_defensive_rating)
    if away_team_stats:
        away_offensive_rating = away_team_stats.get('offensive_rating', away_offensive_rating)
        away_defensive_rating = away_team_stats.get('defensive_rating', away_defensive_rating)

    # ============================================
    # 1. TEMEL PUAN
    # ============================================
    score = 5.0
    
    diff = abs(h - a)
    total_points = h + a
    
    # ============================================
    # 2. FARK FAKTÖRÜ (%40 Etki - En Önemli)
    # ============================================
    if diff == 0:
        score += 4.0       # Berabere (Canlı maç için)
    elif diff <= 3:
        score += 3.5       # Tek sayı farkı - kritik
    elif diff <= 6:
        score += 3.0       # İki top maçı
    elif diff <= 10:
        score += 2.0       # Yakın maç
    elif diff <= 15:
        score += 0.8       # Normal
    elif diff <= 20:
        score -= 0.5       # Fark açılıyor
    elif diff <= 30:
        score -= 2.0       # Blowout
    else:
        score -= 3.5       # Çok sıkıcı
    
    # ============================================
    # 3. TEMPO/OFFENSIVE RATING FAKTÖRÜ (%15 Etki)
    # ============================================
    # NBA 2024-25 sezonu ortalamaları:
    # - Maç başı toplam skor: ~225-235
    # - Offensive Rating: ~114-116
    
    if total_points > 260:
        score += 1.5       # All-Star seviyesi tempo
    elif total_points > 245:
        score += 1.2       # Çok yüksek tempo
    elif total_points > 230:
        score += 0.8       # Yüksek tempo
    elif total_points > 215:
        score += 0.3       # Ortalama
    elif total_points < 200:
        score -= 0.8       # Düşük tempo
    elif total_points < 185:
        score -= 1.5       # Çok kısır oyun
    
    # ============================================
    # 4. LİDERLİK DEĞİŞİMLERİ (%25 Etki - ÇOK ÖNEMLİ)
    # ============================================
    if lead_changes is not None:
        if lead_changes >= 20:
            score += 2.5       # Sürekli değişen liderlik
        elif lead_changes >= 15:
            score += 2.0       # Çok heyecanlı
        elif lead_changes >= 10:
            score += 1.5       # Heyecanlı
        elif lead_changes >= 6:
            score += 1.0       # İyi mücadele
        elif lead_changes >= 3:
            score += 0.5       # Ortalama
        else:
            score -= 0.5       # Tek taraflı oyun
    
    # ============================================
    # 5. OFFENSIVE/DEFENSIVE PERFORMANS (%15 Etki)
    # ============================================
    # Her iki takımın da sezon ortalamasının üstünde oynaması
    
    performance_bonus = 0
    
    # Offensive Rating kontrolü
    if home_offensive_rating and away_offensive_rating:
        # Maçtaki ortalama offensive rating (basitleştirilmiş hesaplama)
        # Gerçek ORtg = 100 * (Sayılar / Possessions) ama biz yaklaşık hesap yapalım
        # Ortalama 48 dakika için ~100 possession varsayalım
        estimated_possessions = (total_points / 2.2)  # Yaklaşık
        avg_ortg_in_game = (total_points / estimated_possessions) * 100
        avg_season_ortg = (home_offensive_rating + away_offensive_rating) / 2
        
        if avg_ortg_in_game > avg_season_ortg + 5:
            performance_bonus += 1.0      # Çok iyi hücum performansı
        elif avg_ortg_in_game > avg_season_ortg + 2:
            performance_bonus += 0.5      # İyi hücum
        elif avg_ortg_in_game < avg_season_ortg - 5:
            performance_bonus -= 0.8      # Kötü hücum
    
    # Defensive Rating kontrolü (düşük = iyi savunma)
    if home_defensive_rating and away_defensive_rating:
        avg_season_drtg = (home_defensive_rating + away_defensive_rating) / 2
        # Eğer maçta az sayı var ama takımlar normalde kötü savunma yapıyorsa bu iyi savunma demek
        if total_points < 210 and avg_season_drtg > 115:
            performance_bonus += 0.8      # Beklenmedik savunma şovu
        elif total_points < 200 and avg_season_drtg > 113:
            performance_bonus += 0.5      # İyi savunma
    
    # Performans bonusunu ekle
    score += performance_bonus
    
    # ============================================
    # 6. UZATMA FAKTÖRÜ (%5 Bonus)
    # ============================================
    if "OT" in status_desc:
        ot_count = status_desc.count("OT")
        if ot_count >= 2:
            score += 2.5      # Çift/üçlü uzatma - efsane
        else:
            score += 1.5      # Tek uzatma
    
    # ============================================
    # FINAL: Puanı 1-10 arasına sabitle
    # ============================================
    final_score = min(max(score, 1.0), 10.0)
    
    return round(final_score, 1)


def get_score_color(score):
    """Puana göre renk kodu döndürür"""
    if score >= 8.5: return "#22c55e" # Yeşil (Harika)
    elif score >= 7.0: return "#eab308" # Sarı (İyi)
    elif score >= 5.0: return "#f97316" # Turuncu (Eh)
    return "#ef4444" # Kırmızı (Sıkıcı)

@st.cache_data(ttl=3600, show_spinner=False)
def get_game_ids_in_range(start_date, end_date):
    """
    Bir tarih aralığındaki tüm maç ID'lerini {tarih: [id, ...]} olarak döndürür.

    ESPN scoreboard'u 'dates=YYYYMMDD-YYYYMMDD' aralığını destekliyor; günde
    bir istek atmak yerine ~30 günlük bloklar hâlinde çekilir. Tam bir sezon
    için ~170 istek yerine ~6 istek yeterli oluyor.
    """
    CHUNK_DAYS = 30
    # Çağıranlar hem datetime hem date gönderebiliyor; tek tipe indir.
    start_date = start_date.date() if isinstance(start_date, datetime) else start_date
    end_date = end_date.date() if isinstance(end_date, datetime) else end_date

    chunks = []
    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(cursor + timedelta(days=CHUNK_DAYS - 1), end_date)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)

    def fetch_chunk(bounds):
        c_start, c_end = bounds
        url = f"{SCOREBOARD_URL}?dates={c_start:%Y%m%d}-{c_end:%Y%m%d}&limit=1000"
        try:
            data = espn_get(url, timeout=25).json()
        except Exception as exc:
            print(f"Hata (get_game_ids_in_range {c_start:%Y-%m-%d}): {exc}")
            return {}

        by_date = {}
        for event in data.get("events", []):
            event_date = _parse_event_date(event.get("date"))
            if event_date:
                by_date.setdefault(event_date, []).append(event["id"])
        return by_date

    date_game_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        for partial in executor.map(fetch_chunk, chunks):
            for day, ids in partial.items():
                date_game_map.setdefault(day, []).extend(ids)

    return date_game_map


def _parse_event_date(value):
    """
    ESPN event tarihini (UTC ISO) maç gününe çevirir.

    Maç saatleri UTC geldiği için akşam maçları ertesi güne kayıyor
    (19:00 ET = 00:00 UTC). 8 saat geri alınca ESPN'in kendi günlük
    gruplamasıyla birebir örtüşüyor - doğrulandı.
    """
    if not value:
        return None
    try:
        return (datetime.strptime(value[:16], "%Y-%m-%dT%H:%M") - timedelta(hours=8)).date()
    except ValueError:
        return None


def get_historical_boxscores(start_date, end_date):
    """
    Belirtilen tarih aralığındaki TÜM maçların boxscore'larını çeker.
    Maç ID'leri toplu, boxscore'lar paralel ve cache'li olarak alınır.
    """
    date_game_map = get_game_ids_in_range(start_date, end_date)
    print(f"Fetching data from {start_date:%Y-%m-%d} to {end_date:%Y-%m-%d} "
          f"({len(date_game_map)} maç günü)")

    # Tüm Game ID'leri düzleştir
    all_game_ids = []
    game_id_to_date = {}
    for d, ids in date_game_map.items():
        for gid in ids:
            all_game_ids.append(gid)
            game_id_to_date[gid] = d

    # Boxscore'ları paralel çek (cache'li sürümle - aynı maç bir daha çekilmez)
    results = []
    def fetch_box_with_date(gid):
        return game_id_to_date[gid], get_cached_boxscore(gid)

    # İlerleme çubuğu (Streamlit context'inde ise)
    total_games = len(all_game_ids)
    if total_games == 0:
        return []

    # UI kilitlenmesin diye progress bar opsiyonel
    # (Burada basitçe çekiyoruz)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_game = {executor.submit(fetch_box_with_date, gid): gid for gid in all_game_ids}
        
        for future in concurrent.futures.as_completed(future_to_game):
            try:
                g_date, players = future.result()
                if players:
                    results.append({
                        "date": g_date,
                        "players": players
                    })
            except Exception as e:
                print(f"Error fetching historical game: {e}")
                
    return results
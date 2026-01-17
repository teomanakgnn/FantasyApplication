import requests
from datetime import datetime, timedelta
import streamlit as st
from functools import lru_cache
import concurrent.futures 
from typing import Dict, List, Optional, Union
import pandas as pd


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
        data = requests.get(url, timeout=10).json()
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

def get_game_ids(date):
    date_str = date.strftime("%Y%m%d")
    url = f"{SCOREBOARD_URL}?dates={date_str}"
    try:
        data = requests.get(url, timeout=10).json()
        return [e["id"] for e in data.get("events", [])]
    except Exception as e:
        print(f"Hata (get_game_ids): {e}")
        return []

def get_last_available_game_date(date):
    for _ in range(7):
        ids = get_game_ids(date)
        if ids:
            return date, ids
        date -= timedelta(days=1)
    return None, []

def get_scoreboard(date):
    """GÜNÜN MAÇLARI + SKOR + OT KONTROLÜ"""
    date_str = date.strftime("%Y%m%d")
    url = f"{SCOREBOARD_URL}?dates={date_str}"
    try:
        data = requests.get(url, timeout=10).json()
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

@st.cache_data(ttl=600)
def get_cached_boxscore(game_id):
    return get_boxscore(game_id)

def get_boxscore(game_id):
    url = f"{SUMMARY_URL}?event={game_id}"
    try:
        data = requests.get(url, timeout=10).json()
    except Exception:
        return []

    players = []

    if "boxscore" not in data or "players" not in data["boxscore"]:
        return []

    for team in data["boxscore"]["players"]:
        for group in team.get("statistics", []):
            if "athletes" not in group:
                continue
            
            labels = group["labels"]

            for athlete in group["athletes"]:
                raw_stats = athlete["stats"]
                stats = dict(zip(labels, raw_stats))
                
                stats["PLAYER"] = athlete["athlete"]["displayName"]
                stats["TEAM"] = team["team"]["abbreviation"]
                
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
        response = requests.get(INJURIES_URL, timeout=10)
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
    
    # Threading ile hızlandıralım (tek tek 30 istek atmak yavaş olur)
    def fetch_single_roster(team_id, team_info):
        t_abbr = team_info['abbr']
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                # Roster yapısı: data['athletes'] -> list of players
                athletes = data.get('athletes', [])
                
                # Bazen yapı 'entries' içinde olabilir, kontrol edelim
                if not athletes and 'entries' in data:
                     athletes = [e.get('athlete', {}) for e in data['entries']]
                
                local_map = {}
                for ath in athletes:
                    # İsimleri alalım
                    p_name = ath.get('displayName') or ath.get('fullName')
                    if p_name:
                        # İsmi temizle (normalize et)
                        clean_name = p_name.replace(".", "").replace("'", "").lower().strip()
                        # Normal ismi kaydet ama temizlenmiş halini anahtarda kullanmak daha iyidir
                        # Ancak şimdilik orijinal ismi key yapıyoruz, display için.
                        local_map[p_name] = t_abbr
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
    ESPN Fantasy API'yi çağırır - Season parametresi YOK
    """
    if views is None:
        views = ['mMatchupScore', 'mScoreboard', 'mSettings', 'mTeam', 'modular', 'mNav']
    
    # Season parametresi olmadan direkt league endpoint
    base_url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/leagueHistory/{league_id}"
    
    params = {'view': views}
    
    # Önce leagueHistory dene
    try:
        print(f"Trying leagueHistory: {base_url}")
        response = requests.get(base_url, headers=HEADERS, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # leagueHistory bir array döndürür, en son sezonu al
            if isinstance(data, list) and len(data) > 0:
                print(f"✓ Found {len(data)} seasons, using latest")
                return data[0]  # En son sezon
        
    except Exception as e:
        print(f"leagueHistory failed: {str(e)}")
    
    # Alternatif: Direkt league endpoint (bazı ligler için)
    alt_url = f"https://fantasy.espn.com/apis/v3/games/fba/seasons/2026/segments/0/leagues/{league_id}"
    
    try:
        print(f"Trying direct endpoint: {alt_url}")
        response = requests.get(alt_url, headers=HEADERS, params=params, timeout=10)
        
        if response.status_code == 401:
            raise PermissionError("Bu lig private. Sadece public ligler destekleniyor.")
        
        if response.status_code == 200:
            data = response.json()
            if 'teams' in data:
                print(f"✓ API call successful - Found {len(data.get('teams', []))} teams")
                return data
        
        # 2024'ü de dene
        alt_url_2024 = f"https://fantasy.espn.com/apis/v3/games/fba/seasons/2025/segments/0/leagues/{league_id}"
        print(f"Trying 2024: {alt_url_2024}")
        response = requests.get(alt_url_2024, headers=HEADERS, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'teams' in data:
                print(f"✓ Found 2024 season - {len(data.get('teams', []))} teams")
                return data
        
        raise RuntimeError(f"Hiçbir endpoint çalışmadı. Son status: {response.status_code}")
        
    except PermissionError:
        raise
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {str(e)}")
        raise RuntimeError(f"ESPN API'ye bağlanılamadı: {str(e)}")

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

# services/espn_api.py dosyasında get_active_players_stats fonksiyonunu bununla değiştirin:

@st.cache_data(ttl=3600)
def get_active_players_stats(days=15):
    """
    Son X günün maçlarını tarayıp aktif oyuncuların ortalamalarını çıkarır.
    Sadece maç başına ortalama 10+ dakika oynayan oyuncular dahil edilir.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # GÜNCEL ROSTER BİLGİSİNİ ÇEK
    current_rosters = get_current_team_rosters()
    
    games_data = get_historical_boxscores(start_date, end_date)
    
    player_stats = {}
    
    # Güvenli sayı çevirme fonksiyonu
    def to_num(val):
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0
    
    # Dakika parse fonksiyonu (MIN formatı: "25:30" veya "25" olabilir)
    def parse_minutes(min_str):
        try:
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

    for game in games_data:
        for p in game['players']:
            name = p['PLAYER']
            
            # Dakikayı parse et
            minutes_played = parse_minutes(p.get('MIN', 0))
            
            if name not in player_stats:
                # GÜNCEL TAKIMI KULLAN
                current_team = current_rosters.get(name, p.get('TEAM', ''))
                
                player_stats[name] = {
                    'GP': 0, 'PTS': 0, 'REB': 0, 'AST': 0, 
                    'STL': 0, 'BLK': 0, 'TO': 0, 
                    'FGM': 0, 'FGA': 0, 'FTM': 0, 'FTA': 0, 
                    '3Pts': 0, 'TEAM': current_team,
                    'MIN': 0  # Toplam dakika ekle
                }
            
            stats = player_stats[name]
            stats['GP'] += 1
            stats['MIN'] += minutes_played  # Dakikayı ekle
            
            stats['PTS'] += to_num(p.get('PTS', 0))
            stats['REB'] += to_num(p.get('REB', 0))
            stats['AST'] += to_num(p.get('AST', 0))
            stats['STL'] += to_num(p.get('STL', 0))
            stats['BLK'] += to_num(p.get('BLK', 0))
            stats['TO']  += to_num(p.get('TO', 0))
            stats['FGM'] += to_num(p.get('FGM', 0))
            stats['FGA'] += to_num(p.get('FGA', 0))
            stats['FTM'] += to_num(p.get('FTM', 0))
            stats['FTA'] += to_num(p.get('FTA', 0))
            stats['3Pts'] += to_num(p.get('3Pts', 0))

    # Ortalamaları hesapla - Sadece maç başına 10+ dakika oynayanlar
    final_list = []
    for name, s in player_stats.items():
        if s['GP'] > 0:
            avg_minutes = s['MIN'] / s['GP']
            
            # MAÇBAŞI 10 DAKİKADAN AZ OYNAYANLAR HARİÇ
            if avg_minutes < 10:
                continue
            
            final_list.append({
                'PLAYER': name,
                'TEAM': s['TEAM'],  # Güncel takım
                'GP': s['GP'],
                'MIN': round(avg_minutes, 1),  # Ortalama dakika
                'PTS': round(s['PTS'] / s['GP'], 1),
                'REB': round(s['REB'] / s['GP'], 1),
                'AST': round(s['AST'] / s['GP'], 1),
                'STL': round(s['STL'] / s['GP'], 1),
                'BLK': round(s['BLK'] / s['GP'], 1),
                'TO': round(s['TO'] / s['GP'], 1),
                '3Pts': round(s['3Pts'] / s['GP'], 1),
                'FG%': round((s['FGM'] / s['FGA'] * 100) if s['FGA'] > 0 else 0, 1),
                'FT%': round((s['FTM'] / s['FTA'] * 100) if s['FTA'] > 0 else 0, 1),
            })
            
    return pd.DataFrame(final_list).sort_values(by="PTS", ascending=False)

def get_historical_boxscores(start_date, end_date):
    """
    Belirtilen tarih aralığındaki TÜM maçların boxscore'larını çeker.
    Performans için Threading kullanır.
    """
    all_game_data = []
    
    # Tarih listesi oluştur
    date_list = []
    curr = start_date
    while curr <= end_date:
        date_list.append(curr)
        curr += timedelta(days=1)
        
    print(f"Fetching data from {start_date} to {end_date} ({len(date_list)} days)")

    # 1. Adım: Tüm günlerin Game ID'lerini topla
    # Threading ile çok daha hızlı
    date_game_map = {} # {date: [game_ids]}
    
    def fetch_ids_for_date(d):
        return d, get_game_ids(d)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_date = {executor.submit(fetch_ids_for_date, d): d for d in date_list}
        for future in concurrent.futures.as_completed(future_to_date):
            d, ids = future.result()
            if ids:
                date_game_map[d] = ids

    # 2. Adım: Tüm Game ID'ler için Boxscore çek
    all_game_ids = []
    game_id_to_date = {}
    
    for d, ids in date_game_map.items():
        for gid in ids:
            all_game_ids.append(gid)
            game_id_to_date[gid] = d
            
    # Boxscore'ları paralel çek
    results = []
    def fetch_box_with_date(gid):
        return game_id_to_date[gid], get_boxscore(gid)

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
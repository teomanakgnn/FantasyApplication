import requests
from datetime import datetime, timedelta
import streamlit as st
from functools import lru_cache
from typing import Dict, List

# =================================================================
# NBA SCOREBOARD & BOXSCORE FONKSİYONLARI (MEVCUT - DEĞİŞMEDİ)
# =================================================================

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"

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
    
import streamlit as st
import espn_api
from trade_analyzer import TradeAnalyzer

st.title("🏀 NBA Fantasy Trade Analyzer")

league_id = 12345678 # ID'nizi buraya girin veya input alın

# 1. Verileri Çek
with st.spinner('Lig verileri çekiliyor...'):
    roster_df = espn_api.get_all_rosters(league_id)
    analyzer = TradeAnalyzer(roster_df)

# 2. Takım Seçimi
teams = roster_df[['team_id', 'team_name']].drop_duplicates()
team_options = {row['team_name']: row['team_id'] for index, row in teams.iterrows()}

col1, col2 = st.columns(2)

with col1:
    st.subheader("Sizin Takımınız")
    my_team_name = st.selectbox("Takım Seç", list(team_options.keys()), key="team_a")
    my_team_id = team_options[my_team_name]
    
    # O takımın oyuncularını filtrele
    my_players = roster_df[roster_df['team_id'] == my_team_id]
    players_out = st.multiselect("Gönderilecek Oyuncular", my_players['player_name'].tolist())
    # Seçilen isimlerin ID'lerini bul
    players_out_ids = my_players[my_players['player_name'].isin(players_out)]['player_id'].tolist()

with col2:
    st.subheader("Karşı Takım")
    other_team_name = st.selectbox("Takım Seç", list(team_options.keys()), index=1, key="team_b")
    other_team_id = team_options[other_team_name]
    
    other_players = roster_df[roster_df['team_id'] == other_team_id]
    players_in = st.multiselect("Alınacak Oyuncular", other_players['player_name'].tolist())
    players_in_ids = other_players[other_players['player_name'].isin(players_in)]['player_id'].tolist()

# 3. Analiz Butonu
if st.button("Takası Analiz Et"):
    if not players_out or not players_in:
        st.warning("Lütfen her iki taraftan da oyuncu seçin.")
    else:
        result = analyzer.analyze_trade(my_team_id, players_out_ids, other_team_id, players_in_ids)
        
        st.write("### Takas Etkisi (Sizin Takımınız)")
        
        # Sonuçları Tablo Halinde Göster
        cols = st.columns(len(result))
        for i, (cat, data) in enumerate(result.items()):
            color = "green" if data['impact'] == "positive" else "red"
            diff_str = f"{data['diff']:+.1f}"
            
            with cols[i]:
                st.metric(
                    label=cat, 
                    value=f"{data['new']}", 
                    delta=diff_str,
                    delta_color="normal" if cat != 'TO' else "inverse" 
                )


def get_standings(league_id: int, season: int = None) -> List[Dict]:
    """Lig sıralamasını getirir"""
    teams = get_teams(league_id)
    
    return sorted(
        teams.values(),
        key=lambda t: (-t["wins"], -t["points_for"])
    )
    

# =================================================================
# ROSTER & TRADE ANALYZER HELPERS
# =================================================================

def get_all_rosters(league_id: int):
    """
    Tüm takımların kadrolarını ve oyuncu istatistiklerini çeker.
    Returns:
        pd.DataFrame: Tüm oyuncuların listesi
    """
    # mRoster: Kadrolar, mSettings: Ayarlar, mTeam: Takım bilgileri
    data = call_espn_api(league_id, views=['mRoster', 'mSettings', 'mTeam'])
    
    if not data:
        return pd.DataFrame()

    all_players = []
    
    # ESPN Stat ID Eşleştirmesi (NBA Standart)
    STAT_MAP = {
        '0': 'PTS', '1': 'BLK', '2': 'STL', '3': 'AST', '6': 'REB', 
        '11': 'TO', '17': '3PM', '19': 'FG%', '20': 'FT%'
    }
    
    teams = data.get('teams', [])
    
    for team in teams:
        team_id = team['id']
        team_name = team.get('name', 'Unknown')
        team_abbrev = team.get('abbrev', 'UNK')
        
        roster = team.get('roster', {}).get('entries', [])
        
        for entry in roster:
            player_data = entry.get('playerPoolEntry', {}).get('player', {})
            
            player_name = player_data.get('fullName', 'Unknown Player')
            player_id = player_data.get('id')
            injury_status = player_data.get('injuryStatus', 'ACTIVE')
            
            # İstatistikleri Çekme
            stats_list = player_data.get('stats', [])
            season_stats = {v: 0.0 for v in STAT_MAP.values()} # Default 0
            
            # 002026 (veya mevcut sezon) ve statSourceId=0 (Real stats)
            real_stats = next((s for s in stats_list if s.get('statSourceId') == 0 and s.get('statSplitTypeId') == 0), None)
            
            if real_stats and 'averageStats' in real_stats:
                avgs = real_stats['averageStats']
                for stat_id, val in avgs.items():
                    if str(stat_id) in STAT_MAP:
                        season_stats[STAT_MAP[str(stat_id)]] = round(val, 2)

            all_players.append({
                "team_id": team_id,
                "team_name": team_name,
                "team_abbrev": team_abbrev,
                "player_id": player_id,
                "player_name": player_name,
                "injury_status": injury_status,
                **season_stats
            })
            
    return pd.DataFrame(all_players)
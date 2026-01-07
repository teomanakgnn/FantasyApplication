import requests
from datetime import datetime, timedelta
import streamlit as st

# URL TANIMLARI
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
    """GÜNÜN MAÇLARI + SKOR"""
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

            games.append({
                "game_id": event["id"],
                "home_team": home["team"]["abbreviation"],
                "away_team": away["team"]["abbreviation"],
                "home_score": home.get("score", "0"),
                "away_score": away.get("score", "0"),
                "home_logo": f"https://a.espncdn.com/i/teamlogos/nba/500/{home['team']['abbreviation']}.png",
                "away_logo": f"https://a.espncdn.com/i/teamlogos/nba/500/{away['team']['abbreviation']}.png",
                "status": comp["status"]["type"]["description"]
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

# ----------------------------------------------------------------
# INJURY REPORT FONKSİYONLARI
# ----------------------------------------------------------------
@st.cache_data(ttl=3600)  # 1 saatlik cache
def get_injuries():
    """TÜM TAKIM SAKATLIKLARI"""
    try:
        response = requests.get(INJURIES_URL, timeout=10)
        data = response.json()
        
        # API yanıtını kontrol et
        if "injuries" not in data:
            print(f"'injuries' key bulunamadı. Mevcut keys: {list(data.keys())}")
            return []
            
    except Exception as e:
        print(f"Hata (get_injuries): {e}")
        import traceback
        traceback.print_exc()
        return []

    all_injuries = []
    
    # Ana injuries listesi içindeki her takım
    for team_data in data.get("injuries", []):
        try:
            team_name = team_data.get("displayName", "Unknown Team")
            team_id = team_data.get("id", "")
            
            # Takım logosunu ve kısaltmasını almak için injuries içindeki ilk oyuncudan çekelim
            team_injuries = team_data.get("injuries", [])
            
            if not team_injuries:
                continue
                
            # İlk oyuncudan takım bilgilerini al
            first_athlete = team_injuries[0].get("athlete", {})
            team_info = first_athlete.get("team", {})
            team_abbr = team_info.get("abbreviation", team_name[:3].upper())
            team_logos = team_info.get("logos", [])
            team_logo = team_logos[0]["href"] if team_logos else ""
            
            for injury in team_injuries:
                athlete = injury.get("athlete", {})
                
                # Oyuncu fotoğrafı
                player_photo = ""
                if "headshot" in athlete:
                    player_photo = athlete["headshot"].get("href", "")
                
                # Pozisyon
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
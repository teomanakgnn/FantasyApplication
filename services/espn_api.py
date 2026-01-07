import requests
from datetime import datetime, timedelta
import streamlit as st

# URL TANIMLARI
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"

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

# ----------------------------------------------------------------
# BURASI KRİTİK: get_cached_boxscore
# ----------------------------------------------------------------
# Eğer veriler güncellenmiyorsa, TTL süresini kısabilir veya cache'i silebilirsin.
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

    # Bazen API "3PT" bazen "3Pt" gönderebilir. Kontrol için.
    # Terminalde çıktı görmek istersen print'i açabilirsin:
    # print(f"Game ID: {game_id} data fetching...")

    for team in data["boxscore"]["players"]:
        for group in team.get("statistics", []):
            if "athletes" not in group:
                continue
            
            labels = group["labels"]  # Örn: ['MIN', 'FG', '3PT', 'FT', ...]

            for athlete in group["athletes"]:
                raw_stats = athlete["stats"]
                stats = dict(zip(labels, raw_stats))
                
                # Temel Bilgiler
                stats["PLAYER"] = athlete["athlete"]["displayName"]
                stats["TEAM"] = team["team"]["abbreviation"]
                
                # --- PARSING MANTIĞI (GÜÇLENDİRİLMİŞ) ---
                
                # Varsayılan değerler (Hata olmaması için)
                stats["FGM"] = 0; stats["FGA"] = 0
                stats["3Pts"] = 0; stats["3PTA"] = 0
                stats["FTM"] = 0; stats["FTA"] = 0

                # 1. FIELD GOALS (Etiket: "FG")
                if "FG" in stats:
                    val = str(stats["FG"])
                    if "-" in val:
                        m, a = val.split("-")
                        stats["FGM"] = int(m)
                        stats["FGA"] = int(a)

                # 2. 3 POINTERS (Etiket: "3PT", "3Pt" veya "3P" olabilir)
                # Olası tüm etiketleri kontrol edelim
                t_val = None
                if "3PT" in stats: t_val = str(stats["3PT"])
                elif "3Pt" in stats: t_val = str(stats["3Pt"])
                elif "3P" in stats: t_val = str(stats["3P"])
                
                if t_val and "-" in t_val:
                    m, a = t_val.split("-")
                    stats["3Pts"] = int(m)
                    stats["3PTA"] = int(a)

                # 3. FREE THROWS (Etiket: "FT")
                if "FT" in stats:
                    val = str(stats["FT"])
                    if "-" in val:
                        m, a = val.split("-")
                        stats["FTM"] = int(m)
                        stats["FTA"] = int(a)
                
                # 4. MIN (Dakika)
                if "MIN" not in stats:
                    stats["MIN"] = "--"

                players.append(stats)

    return players
import time
import pandas as pd
from io import StringIO
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    try:
        service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
        return webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"❌ Driver başlatılamadı: {e}")
        return None

def scrape_team_rosters(league_id: int):
    """
    ESPN Fantasy Basketball roster sayfasından tüm takımların oyuncularını çeker.
    Her takım için ayrı sayfa ziyaret edilir.
    """
    print(f"🔗 Kadrolar çekiliyor: League ID {league_id}")
    
    driver = get_driver()
    if not driver:
        return {}

    rosters = {}
    
    try:
        # Ana takımlar sayfasına git
        teams_url = f"https://fantasy.espn.com/basketball/league/teams?leagueId={league_id}"
        driver.get(teams_url)
        time.sleep(4)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Tüm takım linklerini bul
        team_links = soup.find_all("a", href=lambda x: x and "teamId=" in x)
        team_data = {}
        
        for link in team_links:
            team_name = link.get_text(strip=True)
            if len(team_name) < 2:
                continue
            
            # teamId'yi çıkar
            href = link.get('href', '')
            if 'teamId=' in href:
                team_id = href.split('teamId=')[1].split('&')[0]
                if team_name not in team_data:
                    team_data[team_name] = team_id
        
        print(f"🔎 {len(team_data)} takım bulundu: {list(team_data.keys())}")
        
        # Her takım için ayrı roster sayfasını ziyaret et
        for team_name, team_id in team_data.items():
            try:
                roster_url = f"https://fantasy.espn.com/basketball/team?leagueId={league_id}&teamId={team_id}"
                print(f"  → {team_name} roster'ı çekiliyor...")
                
                driver.get(roster_url)
                time.sleep(3)
                
                # Sayfayı scroll et (lazy loading için)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                soup = BeautifulSoup(driver.page_source, "html.parser")
                
                # Oyuncu tablolarını bul
                players = []
                tables = soup.find_all("table")
                
                for table in tables:
                    # Tablo içeriğine bak
                    txt = table.get_text()
                    if "PLAYER" not in txt.upper() and "NAME" not in txt.upper():
                        continue
                    
                    rows = table.find_all("tr")
                    
                    for row in rows:
                        # Oyuncu linkini bul
                        player_link = row.find("a", href=lambda x: x and "playerId=" in x)
                        if not player_link:
                            continue
                        
                        player_name = player_link.get_text(strip=True)
                        
                        # İstatistikleri çek
                        cells = row.find_all("td")
                        stat_values = []
                        
                        for cell in cells:
                            cell_text = cell.get_text(strip=True)
                            # Sayısal veya yüzde değerleri al
                            if any(c.isdigit() for c in cell_text) or cell_text in ["--", "-"]:
                                stat_values.append(cell_text)
                        
                        # Son 9 değer bizim istatistiklerimiz olmalı
                        if len(stat_values) >= 9:
                            relevant_stats = stat_values[-9:]
                            
                            stats_data = {
                                'FG%': relevant_stats[0],
                                'FT%': relevant_stats[1],
                                '3PM': relevant_stats[2],
                                'REB': relevant_stats[3],
                                'AST': relevant_stats[4],
                                'STL': relevant_stats[5],
                                'BLK': relevant_stats[6],
                                'TO': relevant_stats[7],
                                'PTS': relevant_stats[8]
                            }
                            
                            players.append({
                                "name": player_name,
                                "stats": stats_data
                            })
                
                if players:
                    rosters[team_name] = players
                    print(f"    ✅ {len(players)} oyuncu eklendi")
                else:
                    print(f"    ⚠️ Oyuncu bulunamadı")
                    
            except Exception as e:
                print(f"    ❌ {team_name} hatası: {e}")
                continue
        
        driver.quit()
        print(f"\n✅ Toplam {len(rosters)} takımın roster'ı çekildi")
        return rosters
        
    except Exception as e:
        print(f"❌ Genel roster hatası: {e}")
        if driver:
            driver.quit()
        return {}

def scrape_league_standings(league_id: int):
    url = f"https://fantasy.espn.com/basketball/league/standings?leagueId={league_id}"
    driver = get_driver()
    if not driver:
        return None
    try:
        driver.get(url)
        time.sleep(5)
        html_io = StringIO(driver.page_source)
        dfs = pd.read_html(html_io)
        driver.quit()
        for df in dfs:
            headers = " ".join([str(col).upper() for col in df.columns])
            if ("W" in headers or "WIN" in headers) and len(df) >= 4:
                return df.astype(str)
        return pd.DataFrame()
    except Exception as e:
        print(f"❌ Standings hatası: {e}")
        if driver:
            driver.quit()
        return None

def extract_team_names_from_card(card):
    team_links = card.find_all("a", href=lambda x: x and "teamId=" in x)
    names = [link.get_text(strip=True) for link in team_links if len(link.get_text(strip=True)) > 0]
    names = list(dict.fromkeys(names))
    if len(names) >= 2:
        return names[0], names[1]
    return "Away Team", "Home Team"

def get_scoring_period_params(time_filter: str):
    if time_filter == "week":
        return ""
    elif time_filter == "month":
        return "&view=mMatchupScore"
    elif time_filter == "season":
        return "&view=mTeam"
    else:
        return ""

def parse_row_stats(row):
    cells = row.find_all("td")
    values = []
    for cell in cells:
        txt = cell.get_text(strip=True)
        if any(char.isdigit() for char in txt):
            values.append(txt)
    categories = ['FG%', 'FT%', '3PM', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS']
    if len(values) >= 9:
        relevant = values[-9:]
        return dict(zip(categories, relevant))
    return None

def calculate_category_wins(team_a_stats, team_b_stats):
    if not team_a_stats or not team_b_stats:
        return "0-0-0"
    wins, losses, ties = 0, 0, 0
    inverse_cats = ['TO']
    for cat, val_a in team_a_stats.items():
        if cat not in team_b_stats:
            continue
        try:
            val_a_clean = float(val_a.replace('%', ''))
            val_b_clean = float(team_b_stats[cat].replace('%', ''))
            if cat in inverse_cats:
                if val_a_clean < val_b_clean:
                    wins += 1
                elif val_a_clean > val_b_clean:
                    losses += 1
                else:
                    ties += 1
            else:
                if val_a_clean > val_b_clean:
                    wins += 1
                elif val_a_clean < val_b_clean:
                    losses += 1
                else:
                    ties += 1
        except:
            continue
    return f"{wins}-{losses}-{ties}"

def scrape_matchups(league_id: int, time_filter: str = "week"):
    base_url = f"https://fantasy.espn.com/basketball/league/scoreboard?leagueId={league_id}"
    url = base_url + get_scoring_period_params(time_filter)
    print(f"🔗 Matchups URL: {url}")
    driver = get_driver()
    if not driver:
        return []
    matchups = []
    try:
        driver.get(url)
        time.sleep(6)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        cards = soup.find_all("section", class_="Scoreboard")
        if not cards:
            cards = soup.find_all("div", class_="MatchupCard")
        
        if not cards:
            tables = soup.find_all("table")
            for table in tables:
                txt = table.get_text()
                if not all(x in txt for x in ["FG%", "FT%", "PTS"]):
                    continue
                rows = table.find_all("tr")
                if len(rows) < 3:
                    continue
                away_data = parse_row_stats(rows[1])
                home_data = parse_row_stats(rows[2])
                if not away_data or not home_data:
                    continue
                
                card_container = table.find_parent("section") or table.find_parent("div")
                if card_container:
                    away_name, home_name = extract_team_names_from_card(card_container)
                    matchups.append({
                        "away_team": {"name": away_name, "stats": away_data},
                        "home_team": {"name": home_name, "stats": home_data},
                        "away_score": calculate_category_wins(away_data, home_data),
                        "home_score": calculate_category_wins(home_data, away_data)
                    })
        driver.quit()
        return matchups
    except Exception as e:
        print(f"❌ Matchup hatası: {e}")
        if driver:
            driver.quit()
        return []
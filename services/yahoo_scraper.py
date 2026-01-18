"""
Yahoo Fantasy Basketball API Scraper
Yahoo Fantasy Sports için veri çekme modülü
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import pandas as pd
import time

def get_driver():
    """Chrome driver'ı yapılandırır ve döner"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def scrape_league_standings(league_id):
    """Yahoo liginin standings tablosunu çeker"""
    driver = None
    try:
        driver = get_driver()
        url = f"https://basketball.fantasysports.yahoo.com/nba/{league_id}/standings"
        driver.get(url)
        
        # Tabloyu bekle
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
        time.sleep(3)
        
        # Tablo verilerini çek
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        
        standings_data = []
        for row in rows:
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 3:
                    continue
                
                # Yahoo'da rank genelde ilk sütunda
                rank = cells[0].text.strip()
                team_name = cells[1].text.strip()
                record = cells[2].text.strip()
                
                standings_data.append({
                    "Rank": rank,
                    "Team": team_name,
                    "Record": record
                })
            except Exception as e:
                continue
        
        df = pd.DataFrame(standings_data)
        return df
        
    except Exception as e:
        print(f"Yahoo Standings Error: {str(e)}")
        return pd.DataFrame()
    finally:
        if driver:
            driver.quit()

def scrape_matchups(league_id, time_filter="week"):
    """Yahoo liginin matchup verilerini çeker"""
    driver = None
    try:
        driver = get_driver()
        url = f"https://basketball.fantasysports.yahoo.com/nba/{league_id}/matchup"
        driver.get(url)
        
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".matchup")))
        time.sleep(3)
        
        matchups = []
        
        # Yahoo'nun matchup yapısına göre özelleştir
        matchup_containers = driver.find_elements(By.CSS_SELECTOR, ".matchup")
        
        for container in matchup_containers:
            try:
                # Takım isimlerini bul
                teams = container.find_elements(By.CSS_SELECTOR, ".team-name")
                
                if len(teams) >= 2:
                    away_team = teams[0].text.strip()
                    home_team = teams[1].text.strip()
                    
                    # Skorları bul
                    scores = container.find_elements(By.CSS_SELECTOR, ".score")
                    away_score = scores[0].text.strip() if len(scores) > 0 else "0"
                    home_score = scores[1].text.strip() if len(scores) > 1 else "0"
                    
                    # İstatistikleri çek
                    away_stats = extract_yahoo_team_stats(container, 0)
                    home_stats = extract_yahoo_team_stats(container, 1)
                    
                    matchups.append({
                        "away_team": {
                            "name": away_team,
                            "stats": away_stats
                        },
                        "home_team": {
                            "name": home_team,
                            "stats": home_stats
                        },
                        "away_score": away_score,
                        "home_score": home_score
                    })
            except Exception as e:
                continue
        
        return matchups
        
    except Exception as e:
        print(f"Yahoo Matchups Error: {str(e)}")
        return []
    finally:
        if driver:
            driver.quit()

def extract_yahoo_team_stats(container, team_index):
    """Yahoo matchup kartından takım istatistiklerini çıkarır"""
    stats = {}
    try:
        # Yahoo'nun stat yapısına göre özelleştir
        stat_rows = container.find_elements(By.CSS_SELECTOR, ".stat-row")
        
        # Yahoo genelde kategori bazlı gösterir
        stat_categories = ['FG%', 'FT%', '3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO']
        
        for row in stat_rows:
            try:
                category = row.find_element(By.CSS_SELECTOR, ".stat-label").text.strip()
                values = row.find_elements(By.CSS_SELECTOR, ".stat-value")
                
                if team_index < len(values):
                    value = values[team_index].text.strip()
                    
                    # Kategori eşleştirmesi
                    if 'FG%' in category:
                        stats['FG%'] = value
                    elif 'FT%' in category:
                        stats['FT%'] = value
                    elif '3PT' in category or '3PM' in category:
                        stats['3PTM'] = value
                    elif 'PTS' in category or 'Points' in category:
                        stats['PTS'] = value
                    elif 'REB' in category or 'Rebounds' in category:
                        stats['REB'] = value
                    elif 'AST' in category or 'Assists' in category:
                        stats['AST'] = value
                    elif 'ST' in category or 'Steals' in category:
                        stats['ST'] = value
                    elif 'BLK' in category or 'Blocks' in category:
                        stats['BLK'] = value
                    elif 'TO' in category or 'Turnovers' in category:
                        stats['TO'] = value
            except:
                continue
        
    except Exception as e:
        pass
    
    return stats

def scrape_team_rosters(league_id):
    """Yahoo liginin tüm takım kadroları çeker"""
    driver = None
    try:
        driver = get_driver()
        url = f"https://basketball.fantasysports.yahoo.com/nba/{league_id}/standings"
        driver.get(url)
        
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
        time.sleep(2)
        
        # Takım linklerini al
        team_links = driver.find_elements(By.CSS_SELECTOR, "table tbody tr td a.team-name")
        team_data = {}
        
        for link in team_links:
            try:
                team_name = link.text.strip()
                team_url = link.get_attribute("href")
                
                if team_name and team_url:
                    # Roster sayfasına git
                    roster_url = team_url.replace("/team", "/roster")
                    driver.get(roster_url)
                    time.sleep(2)
                    
                    # Oyuncuları çek
                    players = []
                    player_rows = driver.find_elements(By.CSS_SELECTOR, "table.player-table tbody tr")
                    
                    for row in player_rows:
                        try:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            if len(cells) < 2:
                                continue
                            
                            player_name_elem = cells[1].find_element(By.CSS_SELECTOR, ".player-name")
                            player_name = player_name_elem.text.strip()
                            
                            # İstatistikleri çek (Yahoo genelde ayrı stat sütunları kullanır)
                            player_stats = {}
                            
                            # Yahoo'nun stat sütun yapısına göre özelleştir
                            if len(cells) > 10:
                                stat_indices = {
                                    'FG%': 3, 'FT%': 4, '3PM': 5,
                                    'PTS': 6, 'REB': 7, 'AST': 8,
                                    'STL': 9, 'BLK': 10, 'TO': 11
                                }
                                
                                for stat, idx in stat_indices.items():
                                    try:
                                        if idx < len(cells):
                                            player_stats[stat] = cells[idx].text.strip()
                                    except:
                                        player_stats[stat] = "0"
                            
                            players.append({
                                "name": player_name,
                                "stats": player_stats
                            })
                        except:
                            continue
                    
                    team_data[team_name] = players
                    
                    # Standings sayfasına geri dön
                    driver.back()
                    time.sleep(1)
                    
            except Exception as e:
                continue
        
        return team_data
        
    except Exception as e:
        print(f"Yahoo Rosters Error: {str(e)}")
        return {}
    finally:
        if driver:
            driver.quit()

def get_league_info(league_id):
    """Yahoo liginin genel bilgilerini çeker"""
    driver = None
    try:
        driver = get_driver()
        url = f"https://basketball.fantasysports.yahoo.com/nba/{league_id}"
        driver.get(url)
        
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".league-name")))
        time.sleep(2)
        
        league_info = {}
        
        try:
            league_name = driver.find_element(By.CSS_SELECTOR, ".league-name").text.strip()
            league_info['name'] = league_name
        except:
            league_info['name'] = "Unknown League"
        
        try:
            league_type = driver.find_element(By.CSS_SELECTOR, ".league-type").text.strip()
            league_info['type'] = league_type
        except:
            league_info['type'] = "H2H"
        
        return league_info
        
    except Exception as e:
        print(f"Yahoo League Info Error: {str(e)}")
        return {"name": "Unknown League", "type": "H2H"}
    finally:
        if driver:
            driver.quit()
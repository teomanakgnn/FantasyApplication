"""
ESPN Fantasy Basketball API Scraper
Mevcut Selenium scraper'ınızın ESPN versiyonu
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
    """ESPN liginin standings tablosunu çeker"""
    driver = None
    try:
        driver = get_driver()
        url = f"https://fantasy.espn.com/basketball/league/standings?leagueId={league_id}"
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
                
                team_name = cells[0].text.strip()
                wins_losses = cells[1].text.strip()
                
                standings_data.append({
                    "Team": team_name,
                    "Record": wins_losses
                })
            except Exception as e:
                continue
        
        df = pd.DataFrame(standings_data)
        return df
        
    except Exception as e:
        print(f"ESPN Standings Error: {str(e)}")
        return pd.DataFrame()
    finally:
        if driver:
            driver.quit()

def scrape_matchups(league_id, time_filter="week"):
    """ESPN liginin matchup verilerini çeker"""
    driver = None
    try:
        driver = get_driver()
        url = f"https://fantasy.espn.com/basketball/league/scoreboard?leagueId={league_id}"
        driver.get(url)
        
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".Scoreboard")))
        time.sleep(3)
        
        matchups = []
        
        # Matchup kartlarını bul
        matchup_cards = driver.find_elements(By.CSS_SELECTOR, ".Scoreboard__Row")
        
        for card in matchup_cards:
            try:
                # Takım isimlerini bul
                teams = card.find_elements(By.CSS_SELECTOR, ".ScoreCell__TeamName")
                scores = card.find_elements(By.CSS_SELECTOR, ".ScoreCell__Score")
                
                if len(teams) >= 2 and len(scores) >= 2:
                    away_team = teams[0].text.strip()
                    home_team = teams[1].text.strip()
                    away_score = scores[0].text.strip()
                    home_score = scores[1].text.strip()
                    
                    # İstatistikleri çek (varsa)
                    away_stats = extract_team_stats(card, 0)
                    home_stats = extract_team_stats(card, 1)
                    
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
        print(f"ESPN Matchups Error: {str(e)}")
        return []
    finally:
        if driver:
            driver.quit()

def extract_team_stats(card, team_index):
    """Bir takımın istatistiklerini matchup kartından çıkarır"""
    stats = {}
    try:
        stat_rows = card.find_elements(By.CSS_SELECTOR, ".Scoreboard__Competitor")[team_index].find_elements(By.CSS_SELECTOR, ".stat")
        
        stat_categories = ['FG%', 'FT%', '3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO']
        
        for i, row in enumerate(stat_rows):
            if i < len(stat_categories):
                try:
                    value = row.text.strip()
                    stats[stat_categories[i]] = value
                except:
                    stats[stat_categories[i]] = "0"
    except Exception as e:
        pass
    
    return stats

def scrape_team_rosters(league_id):
    """ESPN liginin tüm takım kadroları çeker"""
    driver = None
    try:
        driver = get_driver()
        url = f"https://fantasy.espn.com/basketball/league/standings?leagueId={league_id}"
        driver.get(url)
        
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
        time.sleep(2)
        
        # Takım isimlerini al
        team_links = driver.find_elements(By.CSS_SELECTOR, "table tbody tr td a")
        team_data = {}
        
        for link in team_links:
            try:
                team_name = link.text.strip()
                team_url = link.get_attribute("href")
                
                if team_name and "teamId=" in team_url:
                    # Her takımın roster sayfasına git
                    roster_url = team_url.replace("/team", "/roster")
                    driver.get(roster_url)
                    time.sleep(2)
                    
                    # Oyuncuları çek
                    players = []
                    player_rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                    
                    for row in player_rows:
                        try:
                            cells = row.find_elements(By.TAG_NAME, "td")
                            if len(cells) < 2:
                                continue
                            
                            player_name = cells[0].text.strip()
                            
                            # İstatistikleri çek
                            player_stats = {}
                            if len(cells) > 10:  # Stat sütunları varsa
                                stat_map = {
                                    'FG%': 3, 'FT%': 4, '3PM': 5, 
                                    'PTS': 6, 'REB': 7, 'AST': 8,
                                    'STL': 9, 'BLK': 10, 'TO': 11
                                }
                                
                                for stat, idx in stat_map.items():
                                    try:
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
                    
                    # Geri standings sayfasına dön
                    driver.back()
                    time.sleep(1)
                    
            except Exception as e:
                continue
        
        return team_data
        
    except Exception as e:
        print(f"ESPN Rosters Error: {str(e)}")
        return {}
    finally:
        if driver:
            driver.quit()
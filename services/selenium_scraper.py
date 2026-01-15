import time
import pandas as pd
from io import StringIO
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

def get_driver():
    chrome_options = Options()
    # Update binary location if needed, otherwise comment out
    # chrome_options.binary_location = "/usr/bin/chromium"
    
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
    return webdriver.Chrome(service=service, options=chrome_options)

def scrape_team_rosters(league_id: int):
    """
    Revised Scraper: Finds Team Headers first, then grabs the associated table.
    """
    url = f"https://fantasy.espn.com/basketball/league/teams?leagueId={league_id}"
    print(f"🔗 Fetching rosters from: {url}")
    
    driver = get_driver()
    rosters = {}
    
    try:
        driver.get(url)
        time.sleep(5)
        
        # --- ROBUST SCROLLING ---
        # Scroll down in increments to trigger lazy loading
        total_height = driver.execute_script("return document.body.scrollHeight")
        for i in range(0, total_height, 700):
            driver.execute_script(f"window.scrollTo(0, {i});")
            time.sleep(0.5)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # --- NEW STRATEGY: Find Team Headers (.Table__Title) ---
        # ESPN organizes teams into sections. Each section has a header with class "Table__Title"
        team_headers = soup.find_all("div", class_="Table__Title")
        
        print(f"🔎 Found {len(team_headers)} team headers. Parsing...")

        for header in team_headers:
            # 1. Extract Team Name
            # The header usually contains a link with the team name or just text
            team_link = header.find("a", href=lambda x: x and "teamId=" in x)
            if team_link:
                team_name = team_link.get_text(strip=True)
            else:
                # Fallback: Just get text if no link
                team_name = header.get_text(strip=True)
                
            # Clean up name (remove "Team Info", "Roster", etc if present)
            if not team_name: continue

            # 2. Find the Associated Table
            # The table is usually in the parent container of the header
            parent_container = header.find_parent("div", class_="Table__Wrapper") 
            if not parent_container:
                # Fallback: Look at the parent of the header
                parent_container = header.parent
            
            table = parent_container.find("table")
            if not table:
                continue

            # 3. Parse Players from Table
            players = []
            rows = table.find_all("tr")
            
            for row in rows:
                # We need rows with player data. Usually these have specific classes or links.
                # Find player name link
                player_link = row.find("a", href=lambda x: x and "playerId=" in x)
                if not player_link:
                    continue
                
                player_name = player_link.get_text(strip=True)
                
                # Extract Stats
                cells = row.find_all("td")
                values = []
                for cell in cells:
                    txt = cell.get_text(strip=True)
                    # Filter for stat-like values (digits, --, %)
                    if (any(c.isdigit() for c in txt) or txt == '--'):
                        values.append(txt)
                
                # 9-CAT mapping (Reverse mapping: usually the last 9 columns are the cats)
                # Standard ESPN format: ... | FG% | FT% | 3PM | REB | AST | STL | BLK | TO | PTS
                if len(values) >= 9:
                    relevant = values[-9:]
                    stats_data = {
                        'FG%': relevant[0],
                        'FT%': relevant[1],
                        '3PM': relevant[2],
                        'REB': relevant[3],
                        'AST': relevant[4],
                        'STL': relevant[5],
                        'BLK': relevant[6],
                        'TO': relevant[7],
                        'PTS': relevant[8]
                    }
                    players.append({"name": player_name, "stats": stats_data})

            if players:
                rosters[team_name] = players
                print(f"✅ Extracted {team_name}: {len(players)} players")

        driver.quit()
        return rosters
        
    except Exception as e:
        print(f"❌ Roster scrape error: {e}")
        if driver: driver.quit()
        return {}

def scrape_league_standings(league_id: int):
    url = f"https://fantasy.espn.com/basketball/league/standings?leagueId={league_id}"
    driver = get_driver()
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
    except:
        if driver: driver.quit()
        return None

def extract_team_names_from_card(card):
    team_links = card.find_all("a", href=lambda x: x and "teamId=" in x)
    names = [link.get_text(strip=True) for link in team_links if len(link.get_text(strip=True)) > 0]
    # Filter duplicates and empty strings
    names = list(dict.fromkeys(names))
    
    if len(names) >= 2: return names[0], names[1]
    return "Away Team", "Home Team"

def get_scoring_period_params(time_filter: str):
    if time_filter == "week": return ""
    elif time_filter == "month": return "&view=mMatchupScore"
    elif time_filter == "season": return "&view=mTeam"
    else: return ""

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
    if not team_a_stats or not team_b_stats: return "0-0-0"
    wins, losses, ties = 0, 0, 0
    inverse_cats = ['TO']
    for cat, val_a in team_a_stats.items():
        if cat not in team_b_stats: continue
        try:
            val_a_clean = float(val_a.replace('%', ''))
            val_b_clean = float(team_b_stats[cat].replace('%', ''))
            
            if cat in inverse_cats:
                if val_a_clean < val_b_clean: wins += 1
                elif val_a_clean > val_b_clean: losses += 1
                else: ties += 1
            else:
                if val_a_clean > val_b_clean: wins += 1
                elif val_a_clean < val_b_clean: losses += 1
                else: ties += 1
        except: continue
    return f"{wins}-{losses}-{ties}"

def scrape_matchups(league_id: int, time_filter: str = "week"):
    base_url = f"https://fantasy.espn.com/basketball/league/scoreboard?leagueId={league_id}"
    url = base_url + get_scoring_period_params(time_filter)
    print(f"🔗 Fetching URL: {url}")
    
    driver = get_driver()
    matchups = []
    try:
        driver.get(url)
        time.sleep(6)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        # Find matchup cards (sections)
        cards = soup.find_all("section", class_="Scoreboard")
        if not cards: cards = soup.find_all("div", class_="MatchupCard") # Fallback
        
        # If no cards found, try iterating tables like before
        if not cards:
            tables = soup.find_all("table")
            # ... (Your existing table logic works fine for matchups, keeping it brief here)
            # Reverting to table logic as it was working for you:
            for table in tables:
                txt = table.get_text()
                if not all(x in txt for x in ["FG%", "FT%", "PTS"]): continue
                rows = table.find_all("tr")
                if len(rows) < 3: continue
                
                away_data = parse_row_stats(rows[1])
                home_data = parse_row_stats(rows[2])
                if not away_data or not home_data: continue
                
                card_container = table.find_parent("section") or table.find_parent("div")
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
        print(f"❌ Matchup error: {e}")
        if driver: driver.quit()
        return []
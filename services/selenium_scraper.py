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
    
    # Hata mesajındaki binary yolunu açıkça belirtiyoruz
    chrome_options.binary_location = "/usr/bin/chromium"
    
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
    )

    # ÖNEMLİ DÜZELTME: ChromeType.CHROMIUM kullanarak sürüm eşleşmesini sağlıyoruz
    service = Service(
        ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
    )

    return webdriver.Chrome(service=service, options=chrome_options)


def scrape_league_standings(league_id: int):
    url = f"https://fantasy.espn.com/basketball/league/standings?leagueId={league_id}"
    driver = get_driver()
    
    try:
        driver.get(url)
        time.sleep(5)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        html_io = StringIO(driver.page_source)
        dfs = pd.read_html(html_io)
        
        target_df = pd.DataFrame()
        for df in dfs:
            headers = " ".join([str(col).upper() for col in df.columns])
            if ("W" in headers or "WIN" in headers) and len(df) >= 4:
                target_df = df
                break
        
        driver.quit()
        
        if not target_df.empty:
            target_df = target_df.loc[:, ~target_df.columns.str.contains('^Unnamed', case=False)]
            return target_df.astype(str)
            
        return pd.DataFrame()

    except Exception as e:
        if driver: driver.quit()
        return None


def scrape_team_rosters(league_id: int):
    """
    Tüm takımların roster bilgilerini çeker.
    Geliştirilmiş Scroll ve Fallback mekanizması içerir.
    """
    url = f"https://fantasy.espn.com/basketball/league/teams?leagueId={league_id}"
    print(f"🔗 Fetching rosters from: {url}")
    
    driver = get_driver()
    rosters = {}
    
    try:
        driver.get(url)
        time.sleep(5) 
        
        # --- SCROLL MEKANİZMASI ---
        total_height = driver.execute_script("return document.body.scrollHeight")
        for i in range(0, total_height, 700):
            driver.execute_script(f"window.scrollTo(0, {i});")
            time.sleep(0.5)
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        # ---------------------------
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # YÖNTEM 1: Standart "Team" sectionlarını bul
        team_sections = soup.find_all("div", class_=lambda x: x and "team" in x.lower())
        
        # YÖNTEM 2 (Fallback): Tablo tarama
        if len(team_sections) < 2:
            print("⚠️ Standart section bulunamadı, tablo tarama moduna geçiliyor...")
            all_tables = soup.find_all("table")
            team_sections = []
            for tbl in all_tables:
                if "Player" in tbl.get_text():
                    parent = tbl.find_parent("div", class_=lambda x: x and "Body" in x) or tbl.parent
                    if parent:
                        team_sections.append(parent)

        print(f"🔎 {len(team_sections)} potansiyel takım alanı bulundu.")

        for section in team_sections:
            team_link = section.find("a", href=lambda x: x and "teamId=" in x)
            
            if not team_link:
                prev = section.find_previous("div", class_=lambda x: x and "Header" in x)
                if prev:
                    team_link = prev.find("a", href=lambda x: x and "teamId=" in x)

            if not team_link: continue
                
            team_name = team_link.get_text(strip=True)
            player_table = section.find("table")
            if not player_table: continue
            
            players = []
            rows = player_table.find_all("tr")
            
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 2: continue
                
                player_name_div = row.find("div", {"title": True})
                if player_name_div:
                     player_name = player_name_div['title']
                else:
                    p_link = row.find("a", href=lambda x: x and "playerId" in x)
                    if p_link: player_name = p_link.get_text(strip=True)
                    else: continue

                if not player_name or player_name == "Player": continue

                stats_data = {}
                stat_values = []
                
                for cell in cells:
                    txt = cell.get_text(strip=True)
                    if (txt.replace('.', '', 1).isdigit() or txt == '--' or '%' in txt) and len(txt) < 8:
                        stat_values.append(txt)
                
                if len(stat_values) >= 9:
                    relevant = stat_values[-9:] 
                    cats = ['FG%', 'FT%', '3PM', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS']
                    for i, cat in enumerate(cats):
                        stats_data[cat] = relevant[i]

                    players.append({"name": player_name, "stats": stats_data})
            
            if players:
                rosters[team_name] = players
                print(f"✅ {team_name}: {len(players)} oyuncu")
        
        driver.quit()
        return rosters
        
    except Exception as e:
        print(f"❌ Roster çekme hatası: {e}")
        if driver: driver.quit()
        return {}


def extract_team_names_from_card(card):
    team_links = card.find_all("a", href=lambda x: x and "teamId=" in x)
    names = []
    for link in team_links:
        text = link.get_text(strip=True)
        if text and len(text) > 3:
            names.append(text)
    if len(names) >= 2: return names[0], names[1]
    return "Away Team", "Home Team"


def get_scoring_period_params(time_filter: str):
    if time_filter == "week": return ""
    elif time_filter == "month": return "&view=mMatchupScore"
    elif time_filter == "season": return "&view=mTeam"
    else: return ""

        
def scrape_matchups(league_id: int, time_filter: str = "week"):
    base_url = f"https://fantasy.espn.com/basketball/league/scoreboard?leagueId={league_id}"
    params = get_scoring_period_params(time_filter)
    url = base_url + params
    
    print(f"🔗 Fetching URL: {url}")
    driver = get_driver()
    matchups = []

    try:
        driver.get(url)
        time.sleep(6) 
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        tables = soup.find_all("table")
        stat_tables = []

        for table in tables:
            txt = table.get_text()
            if all(x in txt for x in ["FG%", "FT%", "REB", "AST", "PTS"]):
                stat_tables.append(table)

        print(f"✅ {len(stat_tables)} stat tablosu bulundu ({time_filter})")

        for table in stat_tables:
            rows = table.find_all("tr")
            if len(rows) < 3: continue

            away_data = parse_row_stats(rows[1])
            home_data = parse_row_stats(rows[2])

            if not away_data or not home_data: continue

            card = table.find_parent("section") or table.find_parent("div")
            if not card: continue

            away_name, home_name = extract_team_names_from_card(card)

            matchups.append({
                "away_team": {"name": away_name, "stats": away_data},
                "home_team": {"name": home_name, "stats": home_data},
                "away_score": calculate_category_wins(away_data, home_data),
                "home_score": calculate_category_wins(home_data, away_data)
            })

        driver.quit()
        return matchups

    except Exception as e:
        print(f"❌ Hata: {e}")
        if driver: driver.quit()
        return []


def parse_row_stats(row):
    cells = row.find_all("td")
    stats = {}
    values = []
    
    for cell in cells:
        txt = cell.get_text(strip=True)
        if any(char.isdigit() for char in txt):
            values.append(txt)
    
    categories = ['FG%', 'FT%', '3PM', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS']
    if len(values) >= 9:
        relevant_values = values[-9:] 
        for i, cat in enumerate(categories):
            stats_data = {} 
            stats[cat] = relevant_values[i]
        return stats
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
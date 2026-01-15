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
    # Eğer sisteminizde Chromium farklı bir yerdeyse burayı güncelleyin:
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
    Takım kadrolarını çeker. 
    Yöntem: Sayfadaki tüm tabloları bul -> İstatistik tablosu mu kontrol et -> Takım ismini bul.
    """
    url = f"https://fantasy.espn.com/basketball/league/teams?leagueId={league_id}"
    print(f"🔗 Fetching rosters from: {url}")
    
    driver = get_driver()
    rosters = {}
    
    try:
        driver.get(url)
        time.sleep(5)
        
        # --- SCROLL (Aşağı Kaydırma) ---
        last_height = driver.execute_script("return document.body.scrollHeight")
        # Yavaş yavaş aşağı in
        for i in range(0, last_height, 500):
            driver.execute_script(f"window.scrollTo(0, {i});")
            time.sleep(0.2)
        
        # En sona git ve bekle
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        # -------------------------------
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Sayfadaki TÜM tabloları bul
        all_tables = soup.find_all("table")
        print(f"🔎 Sayfada {len(all_tables)} adet tablo bulundu. Kadrolar aranıyor...")

        for table in all_tables:
            # 1. Bu tablo bir istatistik tablosu mu? (Header kontrolü)
            header_text = table.get_text().upper()
            if not ("PTS" in header_text and "FG%" in header_text):
                continue

            # 2. Takım İsmini Bul (Tablonun üstündeki containerlarda ara)
            # Genelde yapı: Section -> Header (İsim) + Body (Tablo)
            team_name = "Unknown Team"
            
            # Tablonun ebeveynlerine tırmanarak içinde 'teamId' linki olan ilk yapıyı bul
            parent = table.parent
            found_name = False
            
            # 5 seviye yukarı çıkıp takım ismi arayalım
            for _ in range(5):
                if not parent: break
                
                # Önce bu seviyedeki veya önceki kardeşlerdeki Header'a bak
                # ESPN yapısı genelde: div (Header) -> div (Body/Table)
                header_div = parent.find_previous_sibling("div")
                if header_div:
                    link = header_div.find("a", href=lambda x: x and "teamId=" in x)
                    if link:
                        team_name = link.get_text(strip=True)
                        found_name = True
                        break
                
                # Eğer sibling'de yoksa, parent'ın kendi içinde link var mı?
                link = parent.find("a", href=lambda x: x and "teamId=" in x)
                if link:
                     team_name = link.get_text(strip=True)
                     found_name = True
                     break
                
                parent = parent.parent
            
            if not found_name:
                continue # Takım ismi bulunamadıysa bu tabloyu atla (muhtemelen başka bir stats tablosu)

            # 3. Tablodaki Oyuncuları Çek
            players = []
            rows = table.find_all("tr")
            
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 2: continue
                
                # Oyuncu ismi bulma
                player_name = None
                
                # Yöntem A: title attribute'u
                div_title = row.find("div", {"title": True})
                if div_title: player_name = div_title['title']
                
                # Yöntem B: Link
                if not player_name:
                    a_tag = row.find("a", href=lambda x: x and "playerId" in x)
                    if a_tag: player_name = a_tag.get_text(strip=True)
                
                if not player_name or player_name == "Player": continue

                # İstatistikleri bulma
                stats_data = {}
                values = []
                for cell in cells:
                    txt = cell.get_text(strip=True)
                    # Sayı, yüzde veya -- içeren hücreleri al
                    if (txt.replace('.', '', 1).isdigit() or txt == '--' or '%' in txt) and len(txt) < 8:
                        values.append(txt)
                
                # 9-Cat eşleştirme (Sondan başa)
                if len(values) >= 9:
                    relevant = values[-9:]
                    cats = ['FG%', 'FT%', '3PM', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS']
                    for i, cat in enumerate(cats):
                        stats_data[cat] = relevant[i]
                    
                    players.append({"name": player_name, "stats": stats_data})
            
            if players:
                rosters[team_name] = players
                print(f"✅ {team_name}: {len(players)} oyuncu bulundu")

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

        # Skor tablolarını filtrele
        for table in tables:
            txt = table.get_text()
            if all(x in txt for x in ["FG%", "FT%", "REB", "AST", "PTS"]):
                stat_tables.append(table)

        print(f"✅ {len(stat_tables)} stat tablosu bulundu ({time_filter})")

        for table in stat_tables:
            rows = table.find_all("tr")
            if len(rows) < 3: continue # Header + 2 takım yoksa geç

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
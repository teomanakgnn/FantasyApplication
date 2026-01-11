import time
import pandas as pd
from io import StringIO
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def get_driver():
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium"
    
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    )

    service = Service(
        ChromeDriverManager(
            chrome_type="chromium"
        ).install()
    )

    return webdriver.Chrome(service=service, options=chrome_options)


def scrape_league_standings(league_id: int):
    """
    Lig Puan Durumunu çeker.
    
    Args:
        league_id: ESPN League ID
    """
    # Standings her zaman sezonluk olduğu için time_filter parametresini kaldırdık
    url = f"https://fantasy.espn.com/basketball/league/standings?leagueId={league_id}"
    
    driver = get_driver()
    
    try:
        driver.get(url)
        time.sleep(4)
        
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
    

def extract_team_names_from_card(card):
    """
    Aynı matchup kartı içinden GERÇEK takım isimlerini
    teamId içeren linklerden çeker (STABİL YÖNTEM)
    """
    team_links = card.find_all("a", href=lambda x: x and "teamId=" in x)

    names = []
    for link in team_links:
        text = link.get_text(strip=True)
        if text and len(text) > 3:
            names.append(text)

    if len(names) >= 2:
        return names[0], names[1]

    return "Away Team", "Home Team"


def get_scoring_period_params(time_filter: str):
    """
    Time filter'a göre scoringPeriodId parametrelerini döndürür.
    
    Args:
        time_filter: "week", "month", "season"
    
    Returns:
        str: URL parametreleri
    """
    # ESPN Fantasy Basketball için:
    # Haftalık view için herhangi bir parametre eklemeye gerek yok (default mevcut hafta)
    # Aylık ve sezonluk için "view" parametresi kullanılır
    
    if time_filter == "week":
        # Mevcut hafta (default)
        return ""
    elif time_filter == "month":
        # Matchup history view (genelde son birkaç hafta)
        return "&view=mMatchupScore"
    elif time_filter == "season":
        # Sezon geneli görünüm
        return "&view=mTeam"
    else:
        return ""

        
def scrape_matchups(league_id: int, time_filter: str = "week"):
    """
    Matchup verilerini çeker.
    
    Args:
        league_id: ESPN League ID
        time_filter: "week" (mevcut hafta), "month" (son 4 hafta), "season" (tüm sezon)
    """
    base_url = f"https://fantasy.espn.com/basketball/league/scoreboard?leagueId={league_id}"
    
    # Time filter parametrelerini ekle
    params = get_scoring_period_params(time_filter)
    url = base_url + params
    
    print(f"🔗 Fetching URL: {url}")
    
    driver = get_driver()
    matchups = []

    try:
        driver.get(url)
        time.sleep(8)  # Daha uzun bekleme süresi

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # GERÇEK 9-CAT STAT TABLOLARI
        tables = soup.find_all("table")
        stat_tables = []

        for table in tables:
            txt = table.get_text()
            if all(x in txt for x in ["FG%", "FT%", "REB", "AST", "PTS"]):
                stat_tables.append(table)

        print(f"✅ {len(stat_tables)} stat tablosu bulundu ({time_filter})")

        for table in stat_tables:
            rows = table.find_all("tr")
            if len(rows) < 3:
                continue

            away_data = parse_row_stats(rows[1])
            home_data = parse_row_stats(rows[2])

            if not away_data or not home_data:
                continue

            # TABLOYU SARAN MATCHUP CARD
            card = table.find_parent("section") or table.find_parent("div")
            if not card:
                continue

            # STABİL TAKIM İSİMLERİ
            away_name, home_name = extract_team_names_from_card(card)

            matchups.append({
                "away_team": {
                    "name": away_name,
                    "stats": away_data
                },
                "home_team": {
                    "name": home_name,
                    "stats": home_data
                },
                "away_score": calculate_category_wins(away_data, home_data),
                "home_score": calculate_category_wins(home_data, away_data)
            })

        driver.quit()
        print(f"✅ Toplam {len(matchups)} matchup çekildi")
        return matchups

    except Exception as e:
        print(f"❌ Hata: {e}")
        if driver:
            driver.quit()
        return []


def parse_row_stats(row):
    """
    Bir HTML tablosu satırındaki (tr) hücreleri (td) okur ve 9-Cat sözlüğü oluşturur.
    Beklenen Sıra: FG%, FT%, 3PM, REB, AST, STL, BLK, TO, PTS
    """
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


def extract_team_names_from_matchup(card):
    """
    Scoreboard matchup kartından GERÇEK takım isimlerini çeker
    """
    team_names = []

    possible_headers = card.find_all(
        ["h1", "h2", "h3", "span"],
        string=True
    )

    for h in possible_headers:
        text = h.get_text(strip=True)
        if (
            len(text) > 5 and
            not text.isupper() and
            not any(x in text.upper() for x in ["FG%", "PTS", "REB", "AST"])
        ):
            team_names.append(text)

    if len(team_names) >= 2:
        return team_names[0], team_names[1]

    return "Away Team", "Home Team"


def calculate_category_wins(team_a_stats, team_b_stats):
    """9-Cat kazanma hesaplaması"""
    if not team_a_stats or not team_b_stats:
        return "0-0-0"
    
    wins = 0
    losses = 0
    ties = 0
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
        except:
            continue
            
    return f"{wins}-{losses}-{ties}"
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
    

def get_team_upcoming_games(league_id: int, team_id: int):
    """
    Takımın roster'ındaki oyuncuların o hafta oynayacağı toplam maç sayısını hesaplar
    """
    url = f"https://fantasy.espn.com/basketball/team?leagueId={league_id}&teamId={team_id}"
    driver = get_driver()
    
    try:
        driver.get(url)
        time.sleep(4)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Roster tablosunu bul
        roster_table = None
        for table in soup.find_all('table'):
            if 'Opp' in table.get_text() and 'Status' in table.get_text():
                roster_table = table
                break
        
        if not roster_table:
            driver.quit()
            return 0
            
        total_games = 0
        rows = roster_table.find_all('tr')
        
        for row in rows[1:]:  # Header'ı atla
            cells = row.find_all('td')
            if len(cells) < 3:
                continue
                
            # Oyuncu durumunu kontrol et (Bench'teki oyuncuları say)
            player_text = row.get_text()
            
            # O hafta kaç maç oynayacağını bul
            # ESPN'de genelde "@ LAL, vs BOS" gibi gösterilir
            for cell in cells:
                text = cell.get_text(strip=True)
                # Virgül sayısı = maç sayısı - 1
                if '@' in text or 'vs' in text:
                    games_this_week = text.count(',') + 1
                    total_games += games_this_week
                    break
        
        driver.quit()
        return total_games
        
    except Exception as e:
        if driver:
            driver.quit()
        return 0    

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

        
def extract_team_games_count(card, team_index=0):
    """
    Matchup kartından takımın o hafta toplam maç sayısını çeker.
    ESPN'de genellikle takım adının yanında veya altında gösterilir.
    Örn: "4-0 (12 GP)" veya sadece "GP: 12"
    """
    try:
        # Tüm text'i al ve GP bilgisini ara
        card_text = card.get_text()
        
        # "GP" içeren tüm span/div elementlerini bul
        gp_elements = card.find_all(text=lambda t: t and 'GP' in t.upper())
        
        if gp_elements and len(gp_elements) > team_index:
            gp_text = gp_elements[team_index]
            # Sayıyı çıkar (örn: "12 GP" -> 12)
            import re
            numbers = re.findall(r'\d+', gp_text)
            if numbers:
                return int(numbers[0])
        
        # Alternatif: Parent container'da ara
        team_containers = card.find_all("div", class_=lambda x: x and "team" in x.lower())
        if len(team_containers) > team_index:
            container_text = team_containers[team_index].get_text()
            import re
            gp_match = re.search(r'(\d+)\s*GP', container_text, re.IGNORECASE)
            if gp_match:
                return int(gp_match.group(1))
        
        return 0
        
    except Exception as e:
        print(f"⚠️ GP extraction error: {e}")
        return 0


def scrape_matchups(league_id: int, time_filter: str = "week"):
    """
    Matchup verilerini çeker + her takımın o hafta toplam maç sayısını ekler
    """
    base_url = f"https://fantasy.espn.com/basketball/league/scoreboard?leagueId={league_id}"
    params = get_scoring_period_params(time_filter)
    url = base_url + params
    
    print(f"🔗 Fetching URL: {url}")
    
    driver = get_driver()
    matchups = []

    try:
        driver.get(url)
        time.sleep(8)

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

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

            # Takım isimleri
            away_name, home_name = extract_team_names_from_card(card)
            
            # GP bilgisini karttan çek
            away_gp = extract_team_games_count(card, team_index=0)
            home_gp = extract_team_games_count(card, team_index=1)
            
            # Eğer bulamazsa, stats içinden al (yedek)
            if away_gp == 0 and 'GP' in away_data:
                try:
                    away_gp = int(away_data['GP'])
                except:
                    away_gp = 0
                    
            if home_gp == 0 and 'GP' in home_data:
                try:
                    home_gp = int(home_data['GP'])
                except:
                    home_gp = 0

            matchups.append({
                "away_team": {
                    "name": away_name,
                    "stats": away_data,
                    "games_played": away_gp
                },
                "home_team": {
                    "name": home_name,
                    "stats": home_data,
                    "games_played": home_gp
                },
                "away_score": calculate_category_wins(away_data, home_data),
                "home_score": calculate_category_wins(home_data, away_data)
            })
            
            print(f"  📊 {away_name} ({away_gp} GP) vs {home_name} ({home_gp} GP)")

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
    Bir HTML tablosu satırındaki (tr) hücreleri (td) okur ve 9-Cat + GP sözlüğü oluşturur.
    Beklenen Sıra: FG%, FT%, 3PM, REB, AST, STL, BLK, TO, PTS (ve muhtemelen GP)
    """
    cells = row.find_all("td")
    stats = {}
    values = []
    
    for cell in cells:
        txt = cell.get_text(strip=True)
        if any(char.isdigit() for char in txt):
            values.append(txt)
    
    # GP genellikle ilk sütun olabilir, kontrol edelim
    if len(values) >= 10:  # GP + 9 kategori
        stats['GP'] = values[0]
        categories = ['FG%', 'FT%', '3PM', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS']
        for i, cat in enumerate(categories):
            stats[cat] = values[i + 1]
    elif len(values) >= 9:  # Sadece 9 kategori
        categories = ['FG%', 'FT%', '3PM', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS']
        relevant_values = values[-9:]
        for i, cat in enumerate(categories):
            stats[cat] = relevant_values[i]
    else:
        return None
    
    return stats


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
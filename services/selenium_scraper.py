import time
import pandas as pd
from io import StringIO
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

# Global driver pool for reuse
_driver_pool = []

def get_driver():
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium"
    
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-images")  # Resimleri yükleme
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    )

    service = Service(
        ChromeDriverManager(
            chrome_type="chromium"
        ).install()
    )

    return webdriver.Chrome(service=service, options=chrome_options)

def get_team_id_from_matchup_card(card, team_index=0):
    """
    Matchup kartından takım ID'sini çeker
    """
    try:
        team_links = card.find_all("a", href=lambda x: x and "teamId=" in x)
        if len(team_links) > team_index:
            href = team_links[team_index]['href']
            team_id = href.split('teamId=')[1].split('&')[0]
            return team_id
        return None
    except Exception as e:
        print(f"⚠️ Team ID extraction error: {e}")
        return None


def get_current_scoring_period(league_id: int):
    """
    Mevcut scoring period'u (hafta numarası) çeker - OPTIMIZED
    """
    url = f"https://fantasy.espn.com/basketball/league/scoreboard?leagueId={league_id}"
    driver = get_driver()
    
    try:
        driver.get(url)
        time.sleep(1.5)  # 3'ten 1.5'e düşürüldü
        
        soup = BeautifulSoup(driver.page_source, 'lxml')  # html.parser yerine lxml (daha hızlı)
        
        # "Week X" veya "Matchup Period X" gibi text'i ara
        text = soup.get_text()
        week_match = re.search(r'Week\s+(\d+)|Matchup Period\s+(\d+)', text, re.IGNORECASE)
        
        if week_match:
            period = week_match.group(1) or week_match.group(2)
            driver.quit()
            return int(period)
        
        driver.quit()
        return 1  # Default
        
    except Exception as e:
        print(f"⚠️ Scoring period error: {e}")
        if driver:
            driver.quit()
        return 1


def get_team_weekly_games(league_id: int, team_id: str, scoring_period: int = None):
    """
    Takımın roster'ındaki oyuncuların o hafta toplam kaç maç oynayacağını hesaplar - OPTIMIZED
    """
    if scoring_period:
        url = f"https://fantasy.espn.com/basketball/team?leagueId={league_id}&teamId={team_id}&scoringPeriodId={scoring_period}"
    else:
        url = f"https://fantasy.espn.com/basketball/team?leagueId={league_id}&teamId={team_id}"
    
    driver = get_driver()
    
    try:
        driver.get(url)
        time.sleep(2)  # 5'ten 2'ye düşürüldü
        
        soup = BeautifulSoup(driver.page_source, 'lxml')  # lxml kullanımı
        
        # Roster tablosunu bul - optimize edilmiş selector
        roster_table = soup.find('table', text=re.compile(r'OPPONENT|OPP|MATCHUP', re.I))
        
        if not roster_table:
            # Fallback: tüm tablolarda ara
            tables = soup.find_all('table')
            for table in tables:
                headers = table.find_all('th')
                header_text = ' '.join([h.get_text() for h in headers])
                
                if any(keyword in header_text.upper() for keyword in ['OPPONENT', 'OPP', 'MATCHUP']):
                    roster_table = table
                    break
        
        if not roster_table:
            print(f"⚠️ Roster table not found for team {team_id}")
            driver.quit()
            return 0
        
        # Oyuncuları parse et - optimize edilmiş
        rows = roster_table.find_all('tr')
        total_games = 0
        player_count = 0
        
        # Pre-compile regex
        matchup_pattern = re.compile(r'@|vs', re.I)
        
        for row in rows[1:]:  # İlk satır header
            cells = row.find_all('td')
            if len(cells) < 3:
                continue
            
            player_name = cells[0].get_text(strip=True)
            
            if not player_name or player_name == '-':
                continue
            
            # OPPONENT/MATCHUP sütununu bul
            matchup_text = ""
            for cell in cells:
                text = cell.get_text(strip=True)
                if matchup_pattern.search(text):
                    matchup_text = text
                    break
            
            if matchup_text:
                games_this_week = 0
                
                if ',' in matchup_text:
                    games_this_week = matchup_text.count(',') + 1
                elif matchup_pattern.search(matchup_text):
                    games_this_week = 1
                
                total_games += games_this_week
                player_count += 1
                
                if games_this_week > 0:
                    print(f"    👤 {player_name}: {games_this_week} games ({matchup_text})")
        
        driver.quit()
        print(f"  ✅ Team {team_id}: {player_count} players, {total_games} total games")
        return total_games
        
    except Exception as e:
        print(f"❌ Error fetching team {team_id} games: {e}")
        if driver:
            driver.quit()
        return 0

def scrape_league_standings(league_id: int):
    """
    Lig Puan Durumunu çeker - OPTIMIZED
    """
    url = f"https://fantasy.espn.com/basketball/league/standings?leagueId={league_id}"
    
    driver = get_driver()
    
    try:
        driver.get(url)
        time.sleep(2)  # 4'ten 2'ye düşürüldü
        
        soup = BeautifulSoup(driver.page_source, 'lxml')
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
    Takımın roster'ındaki oyuncuların o hafta oynayacağı toplam maç sayısını hesaplar - OPTIMIZED
    """
    url = f"https://fantasy.espn.com/basketball/team?leagueId={league_id}&teamId={team_id}"
    driver = get_driver()
    
    try:
        driver.get(url)
        time.sleep(2)  # 4'ten 2'ye düşürüldü
        
        soup = BeautifulSoup(driver.page_source, 'lxml')
        
        # Optimize edilmiş table arama
        roster_table = None
        for table in soup.find_all('table', limit=5):  # İlk 5 tablo yeterli
            table_text = table.get_text()
            if 'Opp' in table_text and 'Status' in table_text:
                roster_table = table
                break
        
        if not roster_table:
            driver.quit()
            return 0
            
        total_games = 0
        rows = roster_table.find_all('tr')
        
        matchup_pattern = re.compile(r'@|vs')
        
        for row in rows[1:]:
            cells = row.find_all('td')
            if len(cells) < 3:
                continue
                
            for cell in cells:
                text = cell.get_text(strip=True)
                if matchup_pattern.search(text):
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
    team_links = card.find_all("a", href=lambda x: x and "teamId=" in x, limit=2)  # Limit eklendi

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
    """
    if time_filter == "week":
        return ""
    elif time_filter == "month":
        return "&view=mMatchupScore"
    elif time_filter == "season":
        return "&view=mTeam"
    else:
        return ""

        
def extract_team_games_count(card, team_index=0):
    """
    Matchup kartından takımın o hafta toplam maç sayısını çeker - OPTIMIZED
    """
    try:
        card_text = card.get_text()
        
        # Pre-compiled regex
        gp_pattern = re.compile(r'(\d+)\s*GP', re.IGNORECASE)
        
        gp_elements = card.find_all(text=gp_pattern)
        
        if gp_elements and len(gp_elements) > team_index:
            gp_text = gp_elements[team_index]
            numbers = re.findall(r'\d+', gp_text)
            if numbers:
                return int(numbers[0])
        
        team_containers = card.find_all("div", class_=lambda x: x and "team" in x.lower(), limit=3)
        if len(team_containers) > team_index:
            container_text = team_containers[team_index].get_text()
            gp_match = gp_pattern.search(container_text)
            if gp_match:
                return int(gp_match.group(1))
        
        return 0
        
    except Exception as e:
        print(f"⚠️ GP extraction error: {e}")
        return 0


def _fetch_team_games_worker(args):
    """Worker function for parallel team games fetching"""
    league_id, team_id, current_period, time_filter, team_name = args
    
    if not team_id:
        return team_name, 0
    
    games = get_team_weekly_games(
        league_id, 
        team_id,
        current_period if time_filter == "week" else None
    )
    return team_name, games


def scrape_matchups(league_id: int, time_filter: str = "week"):
    """
    Matchup verilerini çeker + her takımın o hafta toplam maç sayısını hesaplar - PARALLEL OPTIMIZED
    """
    base_url = f"https://fantasy.espn.com/basketball/league/scoreboard?leagueId={league_id}"
    params = get_scoring_period_params(time_filter)
    url = base_url + params
    
    print(f"🔗 Fetching URL: {url}")
    
    driver = get_driver()
    matchups = []

    try:
        driver.get(url)
        time.sleep(4)  # 8'den 4'e düşürüldü

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)  # 3'ten 1.5'e düşürüldü

        soup = BeautifulSoup(driver.page_source, "lxml")  # lxml kullanımı

        # Mevcut scoring period'u al
        current_period = get_current_scoring_period(league_id)
        print(f"📅 Current Scoring Period: Week {current_period}")

        tables = soup.find_all("table")
        stat_tables = []

        # Pre-compile pattern
        stat_pattern = re.compile(r'FG%.*FT%.*REB.*AST.*PTS', re.DOTALL)
        
        for table in tables:
            txt = table.get_text()
            if stat_pattern.search(txt):
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

            card = table.find_parent("section") or table.find_parent("div")
            if not card:
                continue

            away_name, home_name = extract_team_names_from_card(card)
            
            away_team_id = get_team_id_from_matchup_card(card, team_index=0)
            home_team_id = get_team_id_from_matchup_card(card, team_index=1)

            matchups.append({
                "away_team": {
                    "name": away_name,
                    "stats": away_data,
                    "team_id": away_team_id
                },
                "home_team": {
                    "name": home_name,
                    "stats": home_data,
                    "team_id": home_team_id
                },
                "away_score": calculate_category_wins(away_data, home_data),
                "home_score": calculate_category_wins(home_data, away_data)
            })

        driver.quit()
        
        # PARALEL İŞLEM: Tüm takımların maçlarını aynı anda çek
        print("\n🔄 Calculating weekly games for each team (PARALLEL)...")
        
        # Tüm takım bilgilerini topla
        team_tasks = []
        for match in matchups:
            team_tasks.append((
                league_id,
                match['away_team']['team_id'],
                current_period,
                time_filter,
                match['away_team']['name']
            ))
            team_tasks.append((
                league_id,
                match['home_team']['team_id'],
                current_period,
                time_filter,
                match['home_team']['name']
            ))
        
        # Paralel olarak tüm takımları işle (max 4 thread)
        team_games_dict = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(_fetch_team_games_worker, task): task for task in team_tasks}
            
            for future in as_completed(futures):
                team_name, games = future.result()
                team_games_dict[team_name] = games
        
        # Sonuçları matchup'lara ata
        for match in matchups:
            match['away_team']['weekly_games'] = team_games_dict.get(match['away_team']['name'], 0)
            match['home_team']['weekly_games'] = team_games_dict.get(match['home_team']['name'], 0)
        
        print(f"\n✅ Toplam {len(matchups)} matchup çekildi")
        return matchups

    except Exception as e:
        print(f"❌ Hata: {e}")
        if driver:
            driver.quit()
        return []
    
def parse_row_stats(row):
    """
    Bir HTML tablosu satırındaki (tr) hücreleri (td) okur ve 9-Cat + GP sözlüğü oluşturur - OPTIMIZED
    """
    cells = row.find_all("td")
    stats = {}
    values = []
    
    # Optimize edilmiş text extraction
    for cell in cells:
        txt = cell.get_text(strip=True)
        if txt and any(c.isdigit() for c in txt):
            values.append(txt)
    
    if len(values) >= 10:
        stats['GP'] = values[0]
        categories = ['FG%', 'FT%', '3PM', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS']
        for i, cat in enumerate(categories):
            stats[cat] = values[i + 1]
    elif len(values) >= 9:
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
        string=True,
        limit=10  # Limit eklendi
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
    """9-Cat kazanma hesaplaması - OPTIMIZED"""
    if not team_a_stats or not team_b_stats:
        return "0-0-0"
    
    wins = 0
    losses = 0
    ties = 0
    inverse_cats = {'TO'}  # Set kullanımı (daha hızlı lookup)
    
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
        except (ValueError, AttributeError):
            continue
            
    return f"{wins}-{losses}-{ties}"
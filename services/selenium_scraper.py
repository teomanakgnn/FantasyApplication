import time
import pandas as pd
from io import StringIO
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def get_driver():
    """Chrome WebDriver'ı başlatır"""
    chrome_options = Options()
    
    # Windows için chromium path'ini otomatik algıla
    try:
        chrome_options.binary_location = "/usr/bin/chromium"  # Linux
    except:
        pass  # Windows için varsayılan Chrome kullanılacak
    
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
        service = Service(ChromeDriverManager(chrome_type="chromium").install())
    except:
        # Fallback to regular Chrome
        service = Service(ChromeDriverManager().install())

    return webdriver.Chrome(service=service, options=chrome_options)


def scrape_all_rosters(league_id: int):
    """
    TÜM TAKIMLARIN KADROLARINI VE OYUNCU İSTATİSTİKLERİNİ ÇEKER
    
    Args:
        league_id: ESPN League ID
    
    Returns:
        pd.DataFrame: Tüm oyuncuların listesi (team_name, player_name, stats)
    """
    url = f"https://fantasy.espn.com/basketball/league/rosters?leagueId={league_id}"
    
    print(f"\n{'='*60}")
    print(f"🔗 Scraping Rosters from League ID: {league_id}")
    print(f"{'='*60}\n")
    
    driver = get_driver()
    all_players = []
    
    try:
        driver.get(url)
        print(f"✅ Page loaded: {url}")
        time.sleep(6)  # Sayfanın yüklenmesini bekle
        
        # Sayfayı scroll et (lazy loading için)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # TAKIMLARI BUL - Farklı CSS selector'lar dene
        team_sections = []
        
        # Yöntem 1: Class isimlerinde "team" geçen div/section
        team_sections = soup.find_all("div", class_=lambda x: x and ("team" in x.lower() or "roster" in x.lower()))
        
        if not team_sections:
            # Yöntem 2: Tablo bazlı yaklaşım
            team_sections = soup.find_all("table")
        
        print(f"✅ {len(team_sections)} takım bölümü bulundu\n")
        
        if len(team_sections) == 0:
            print("❌ Hiç takım bulunamadı! HTML yapısı:")
            print(soup.prettify()[:1000])
            driver.quit()
            return pd.DataFrame()
        
        for team_idx, section in enumerate(team_sections, 1):
            # TAKIM İSMİNİ BUL
            team_name = None
            
            # Yöntem 1: Önceki header elementini bul
            team_header = section.find_previous(["h1", "h2", "h3", "h4", "div"], 
                                               class_=lambda x: x and "team" in x.lower())
            if team_header:
                team_name = team_header.get_text(strip=True)
            
            # Yöntem 2: Link içindeki teamId'yi bul
            if not team_name or len(team_name) < 3:
                team_link = section.find("a", href=lambda x: x and "teamId=" in x)
                if team_link:
                    team_name = team_link.get_text(strip=True)
            
            # Yöntem 3: Section içindeki ilk anlamlı text
            if not team_name or len(team_name) < 3:
                first_text = section.find(string=True, recursive=False)
                if first_text:
                    team_name = first_text.strip()
            
            if not team_name or len(team_name) < 3:
                team_name = f"Team {team_idx}"
            
            print(f"📋 Scraping: {team_name}")
            
            # ROSTER TABLOSUNU BUL
            roster_table = section.find("table") if section.name != "table" else section
            
            if not roster_table:
                print(f"   ⚠️  Roster tablosu bulunamadı")
                continue
            
            rows = roster_table.find_all("tr")
            
            # Header satırını bul
            header_row = None
            for row in rows:
                txt = row.get_text()
                if any(stat in txt for stat in ["PTS", "REB", "AST"]):
                    header_row = row
                    break
            
            if not header_row:
                print(f"   ⚠️  İstatistik header'ı bulunamadı")
                continue
            
            # HEADER'DAN KATEGORİLERİ ÇEK
            headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
            
            # Kategori indexlerini bul
            stat_indices = {}
            for i, h in enumerate(headers):
                h_upper = h.upper()
                if h_upper in ['FG%', 'FT%', '3PM', '3PT', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS']:
                    if h_upper == '3PT':
                        stat_indices['3PM'] = i
                    else:
                        stat_indices[h_upper] = i
            
            if not stat_indices:
                print(f"   ⚠️  Hiç stat kategorisi bulunamadı. Headers: {headers}")
                continue
            
            print(f"   📊 Stats found: {list(stat_indices.keys())}")
            
            # OYUNCU SATIRLARINI PARSE ET
            player_count = 0
            for row in rows:
                if row == header_row:
                    continue
                
                cells = row.find_all(["td", "th"])
                
                if len(cells) < 5:
                    continue
                
                # OYUNCU İSMİNİ BUL
                player_name = None
                
                # Yöntem 1: playerId içeren link
                for cell in cells[:5]:
                    player_link = cell.find("a", href=lambda x: x and "playerId=" in x)
                    if player_link:
                        player_name = player_link.get_text(strip=True)
                        break
                
                # Yöntem 2: "player" class'ı olan span
                if not player_name:
                    for cell in cells[:5]:
                        player_span = cell.find("span", class_=lambda x: x and "player" in x.lower())
                        if player_span:
                            player_name = player_span.get_text(strip=True)
                            break
                
                # Yöntem 3: İlk anlamlı text
                if not player_name or len(player_name) < 3:
                    for cell in cells[:5]:
                        txt = cell.get_text(strip=True)
                        # Stat değerlerini hariç tut
                        if len(txt) > 3 and not any(x in txt for x in ['FG%', 'PTS', 'REB', '---', 'SLOT']):
                            player_name = txt.split('\n')[0]  # İlk satırı al
                            break
                
                if not player_name or len(player_name) < 3:
                    continue
                
                # İSTATİSTİKLERİ ÇEK
                player_stats = {
                    'team_name': team_name,
                    'player_name': player_name,
                    'FG%': 0.0,
                    'FT%': 0.0,
                    '3PM': 0.0,
                    'REB': 0.0,
                    'AST': 0.0,
                    'STL': 0.0,
                    'BLK': 0.0,
                    'TO': 0.0,
                    'PTS': 0.0
                }
                
                # Her kategori için değeri çek
                for stat, idx in stat_indices.items():
                    if idx < len(cells):
                        val_text = cells[idx].get_text(strip=True)
                        try:
                            # % işaretini kaldır, float'a çevir
                            val_clean = val_text.replace('%', '').replace(',', '').replace('--', '0')
                            player_stats[stat] = float(val_clean) if val_clean else 0.0
                        except ValueError:
                            player_stats[stat] = 0.0
                
                # Sadece gerçek oyuncuları ekle (tüm statları 0 olanları atla)
                if sum(player_stats.values()) > 0:
                    all_players.append(player_stats)
                    player_count += 1
            
            print(f"   ✅ {player_count} oyuncu eklendi\n")
        
        driver.quit()
        
        # DataFrame'e çevir
        df = pd.DataFrame(all_players)
        
        if not df.empty:
            print(f"\n{'='*60}")
            print(f"🎉 BAŞARILI! Toplam {len(df)} oyuncu çekildi")
            print(f"📊 {df['team_name'].nunique()} farklı takımdan")
            print(f"{'='*60}\n")
            
            # Team ID ekle (trade analyzer için)
            df['team_id'] = df.groupby('team_name').ngroup() + 1
            
            # Sütun sırasını düzenle
            cols = ['team_id', 'team_name', 'player_name', 'PTS', 'REB', 'AST', 
                   'STL', 'BLK', '3PM', 'FG%', 'FT%', 'TO']
            df = df[cols]
            
            return df
        else:
            print("❌ Hiç oyuncu bulunamadı")
            return pd.DataFrame()
    
    except Exception as e:
        print(f"\n❌ HATA: {e}")
        import traceback
        traceback.print_exc()
        
        if driver:
            driver.quit()
        
        return pd.DataFrame()


def scrape_league_standings(league_id: int):
    """Lig Puan Durumunu çeker"""
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
    """Matchup kartından takım isimlerini çeker"""
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
    """Time filter'a göre URL parametrelerini döndürür"""
    if time_filter == "week":
        return ""
    elif time_filter == "month":
        return "&view=mMatchupScore"
    elif time_filter == "season":
        return "&view=mTeam"
    else:
        return ""

        
def scrape_matchups(league_id: int, time_filter: str = "week"):
    """Matchup verilerini çeker"""
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

            card = table.find_parent("section") or table.find_parent("div")
            if not card:
                continue

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
    """HTML tablosundan 9-Cat statları çeker"""
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
    """Scoreboard matchup kartından takım isimlerini çeker"""
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
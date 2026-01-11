import time
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import concurrent.futures

def get_driver():
    """Chrome WebDriver'ı başlatır - Güçlendirilmiş Ayarlar"""
    chrome_options = Options()
    
    # Performans ve Anti-Detection ayarları
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    
    # Gerçek kullanıcı gibi görünmek için user-agent
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    )
    # Otomasyon bayraklarını gizle
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def get_team_ids_and_names(league_id: int):
    """Takım isimlerini temizleyerek çeker"""
    url = f"https://fantasy.espn.com/basketball/league/rosters?leagueId={league_id}"
    driver = get_driver()
    teams = []
    
    try:
        print(f"🌍 Bağlanılıyor: {url}")
        driver.get(url)
        
        # Tablonun yüklenmesini bekle (Maksimum 15 saniye)
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "Table"))
            )
        except:
            print("⚠️ Takım listesi tablosu geç yüklendi veya bulunamadı.")

        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Linkleri bul
        team_links = soup.find_all("a", href=lambda x: x and "teamId=" in x)
        seen_ids = set()

        for link in team_links:
            href = link.get("href", "")
            match = re.search(r"teamId=(\d+)", href)
            
            if match:
                team_id = int(match.group(1))
                if team_id in seen_ids: continue

                # Ham metni al: "NEEMIAS QUETA (BSTN)Umut Akbaş"
                raw_text = link.get_text(strip=True)
                
                # Temizlik: İlk paranteze kadar olan kısmı al
                clean_name = raw_text.split('(')[0].strip()
                
                # Eğer isim çok kısaysa (bazen sadece logo linki gelir), title'a bak
                if len(clean_name) < 2:
                    clean_name = link.get("title", "")

                # İstenmeyen kelimeleri filtrele
                ignore_list = ["View Team", "Edit Lineup", "Move to", "Team"]
                if len(clean_name) > 2 and clean_name not in ignore_list:
                    seen_ids.add(team_id)
                    teams.append({"team_id": team_id, "team_name": clean_name})
                    print(f"  ✅ Takım: {clean_name} (ID: {team_id})")
        
        return teams
    finally:
        driver.quit()

def process_single_team(league_id, team):
    """Oyuncuları çeker - Akıllı Bekleme ve Alternatif Seçiciler Ekli"""
    team_id = team['team_id']
    team_name = team['team_name']
    
    driver = get_driver()
    # URL sonuna &view=scoringPeriodId ekleyerek bazen görünümü sabitleyebiliriz ama standart URL kalsın
    url = f"https://fantasy.espn.com/basketball/team?leagueId={league_id}&teamId={team_id}"
    
    players = []
    try:
        driver.get(url)
        
        # 1. AKILLI BEKLEME: "PTS" yazısını görene kadar bekle (Tablo başlığı)
        try:
            WebDriverWait(driver, 20).until(
                EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "PTS")
            )
        except:
            print(f"  ⚠️ Zaman aşımı: {team_name} sayfası tam yüklenmedi.")
            return []

        # Biraz scroll yap (lazy load için)
        driver.execute_script("window.scrollBy(0, 400);")
        time.sleep(2) # Scroll sonrası kısa bekleme

        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # 2. TABLO SEÇİMİ (Daha esnek)
        # Sadece class="Table" değil, içinde "PTS" geçen herhangi bir tabloyu ara
        all_tables = soup.find_all("table")
        roster_table = None
        
        for tbl in all_tables:
            if "PTS" in tbl.get_text():
                roster_table = tbl
                break
        
        if not roster_table:
            print(f"  ⚠️ Tablo yapısı bulunamadı: {team_name}")
            return []

        rows = roster_table.find_all("tr")
        
        # Header satırını bul
        header_row = None
        col_indices = {}
        
        for row in rows:
            if "PTS" in row.get_text():
                header_row = row
                cols = row.find_all(["th", "td"])
                for i, col in enumerate(cols):
                    txt = col.get_text(strip=True).upper()
                    if txt in ['FG%', 'FT%', '3PM', '3PT', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS']:
                        col_indices[txt if txt != '3PT' else '3PM'] = i
                break
        
        if not header_row: return []

        # Oyuncuları işle
        for row in rows:
            if row == header_row: continue
            
            cells = row.find_all("td")
            if not cells: continue
            
            # İsim Alma
            player_cell = cells[0]
            player_name_div = player_cell.select_one(".player-column__athlete")
            
            player_name = ""
            if player_name_div:
                player_name = player_name_div.get("title") or player_name_div.get_text(strip=True)
            else:
                # Fallback: Resim title'ı veya düz metin
                img = player_cell.find("img")
                if img: player_name = img.get("title")
                if not player_name: player_name = player_cell.get_text(strip=True)

            # Temizlik
            if not player_name or "Empty" in player_name or "Slot" in player_name: 
                continue

            # ID Alma
            player_id = None
            link = player_cell.find("a", href=True)
            if link:
                match = re.search(r"playerId=(\d+)", link['href'])
                if match: player_id = int(match.group(1))

            p_stats = {
                'team_id': team_id,
                'team_name': team_name,
                'player_name': player_name,
                'player_id': player_id if player_id else 0
            }

            # İstatistikleri Eşle
            for stat in ['FG%', 'FT%', '3PM', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS']:
                p_stats[stat] = 0.0
                if stat in col_indices and col_indices[stat] < len(cells):
                    val = cells[col_indices[stat]].get_text(strip=True)
                    try:
                        if val != "--":
                            p_stats[stat] = float(val.replace(',', ''))
                    except: pass
            
            players.append(p_stats)

        print(f"  --> {team_name}: {len(players)} oyuncu çekildi.")
        return players

    except Exception as e:
        print(f"  ❌ Hata ({team_name}): {e}")
        return []
    finally:
        driver.quit()

def scrape_all_rosters(league_id: int):
    """Ana Fonksiyon: Threading ile çeker"""
    start_time = time.time()
    print(f"🚀 Scraping başlatılıyor... ID: {league_id}")
    
    # 1. Takımları al
    teams = get_team_ids_and_names(league_id)
    if not teams:
        return pd.DataFrame()

    all_players = []
    
    # 2. Paralel işlem (Worker sayısını 3'e düşürdüm stabilite için)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda t: process_single_team(league_id, t), teams))
    
    for res in results:
        all_players.extend(res)

    elapsed = time.time() - start_time
    print(f"🏁 Bitti! Süre: {elapsed:.2f} sn - Toplam Oyuncu: {len(all_players)}")
    
    return pd.DataFrame(all_players)



# DİĞER FONKSİYONLAR (DEĞİŞMEDİ)

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

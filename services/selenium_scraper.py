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
    # Eğer sunucuda çalışıyorsanız bu ayarlar hayat kurtarır:
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3")
    
    # User Agent'ı gerçek bir tarayıcı gibi gösterelim
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    try:
        service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
        return webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"❌ Driver başlatılamadı: {e}")
        return None

def scrape_team_rosters(league_id: int):
    """
    Daha dayanıklı (Robust) Kadro Çekme Fonksiyonu.
    Spesifik class isimleri yerine sayfa yapısını analiz eder.
    """
    url = f"https://fantasy.espn.com/basketball/league/teams?leagueId={league_id}"
    print(f"🔗 Kadrolar çekiliyor: {url}")
    
    driver = get_driver()
    if not driver: return {}

    rosters = {}
    
    try:
        driver.get(url)
        time.sleep(5) # İlk yükleme beklemesi
        
        # --- AGRESİF SCROLL ---
        # Sayfanın en altına kadar yavaş yavaş iniyoruz (Lazy load tetiklensin)
        last_height = driver.execute_script("return document.body.scrollHeight")
        for i in range(0, last_height, 500):
            driver.execute_script(f"window.scrollTo(0, {i});")
            time.sleep(0.3)
        
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3) # Son render için bekle
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # --- YÖNTEM: Sayfadaki TÜM tabloları bul ve analiz et ---
        all_tables = soup.find_all("table")
        print(f"🔎 Sayfada {len(all_tables)} tablo bulundu. Analiz ediliyor...")

        for index, table in enumerate(all_tables):
            # 1. Tablonun içeriğine bak: "PTS", "FG%" ve oyuncu linki var mı?
            txt = table.get_text()
            if "PTS" not in txt or "FG%" not in txt:
                continue

            # 2. Takım ismini bulmaya çalış
            # Tablonun hemen üstündeki veya içindeki linkleri arayalım
            team_name = "Unknown Team"
            
            # Yöntem A: Tablonun içinde takım linki var mı? (Bazı görünümlerde olur)
            internal_team_link = table.find("a", href=lambda x: x and "teamId=" in x)
            
            # Yöntem B: Tablonun üst (parent) elementlerinde takım başlığı arama
            parent = table.parent
            header_team_link = None
            
            # 5 seviye yukarı çıkarak takım ismi içeren bir link arıyoruz
            for _ in range(5):
                if parent:
                    # Parent'ın önceki kardeşlerinde (header kısmında) link var mı?
                    prev = parent.find_previous_sibling()
                    if prev:
                        header_team_link = prev.find("a", href=lambda x: x and "teamId=" in x)
                        if header_team_link: break
                    
                    # Parent'ın kendi içinde (başlık div'i) link var mı?
                    header_team_link = parent.find("a", href=lambda x: x and "teamId=" in x)
                    if header_team_link: break
                    
                    parent = parent.parent
            
            # Linklerden ismi çek
            if header_team_link:
                team_name = header_team_link.get_text(strip=True)
            elif internal_team_link:
                team_name = internal_team_link.get_text(strip=True)
            else:
                # İsmi bulamazsak bile, eğer istatistik tablosuysa bunu "Team X" diye kaydedebiliriz
                # ama genelde yukarıdaki yöntemler bulur.
                continue 

            # Takım ismi çok kısaysa (örn: "L") veya boşsa geç
            if len(team_name) < 2: continue

            # 3. Oyuncuları Çek
            players = []
            rows = table.find_all("tr")
            
            for row in rows:
                # Oyuncu linki (playerId) olan satırları al
                player_link = row.find("a", href=lambda x: x and "playerId=" in x)
                if not player_link: continue
                
                player_name = player_link.get_text(strip=True)
                
                # İstatistik hücrelerini al
                cells = row.find_all("td")
                values = []
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    # Sadece sayısal değerleri, yüzdeleri veya "--" işaretini al
                    if any(c.isdigit() for c in cell_text) or cell_text == "--":
                        values.append(cell_text)
                
                # ESPN Standart: Son 9 sütun genelde bizim istatistiklerdir
                # [FG%, FT%, 3PM, REB, AST, STL, BLK, TO, PTS]
                if len(values) >= 9:
                    relevant = values[-9:]
                    stats_data = {
                        'FG%': relevant[0], 'FT%': relevant[1], '3PM': relevant[2],
                        'REB': relevant[3], 'AST': relevant[4], 'STL': relevant[5],
                        'BLK': relevant[6], 'TO': relevant[7], 'PTS': relevant[8]
                    }
                    players.append({"name": player_name, "stats": stats_data})
            
            if players:
                # Takım ismi zaten varsa (bazen bench ve starter ayrı tablolarda olabilir), birleştir
                if team_name in rosters:
                    rosters[team_name].extend(players)
                else:
                    rosters[team_name] = players
                print(f"✅ {team_name}: {len(players)} oyuncu eklendi.")

        driver.quit()
        return rosters
        
    except Exception as e:
        print(f"❌ Roster hatası: {e}")
        if driver: driver.quit()
        return {}

# --- DİĞER FONKSİYONLAR (AYNI KALABİLİR, BURADA TEKRAR EDİYORUM KOPYALA-YAPIŞTIR KOLAY OLSUN) ---

def scrape_league_standings(league_id: int):
    url = f"https://fantasy.espn.com/basketball/league/standings?leagueId={league_id}"
    driver = get_driver()
    if not driver: return None
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
    names = list(dict.fromkeys(names)) # Duplicate sil
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
    print(f"🔗 Matchups URL: {url}")
    driver = get_driver()
    if not driver: return []
    matchups = []
    try:
        driver.get(url)
        time.sleep(6)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Matchup kartlarını bulmayı dene
        cards = soup.find_all("section", class_="Scoreboard")
        if not cards: cards = soup.find_all("div", class_="MatchupCard")
        
        # Kart bulamazsa tablo yöntemine geç
        if not cards:
            tables = soup.find_all("table")
            for table in tables:
                txt = table.get_text()
                if not all(x in txt for x in ["FG%", "FT%", "PTS"]): continue
                rows = table.find_all("tr")
                if len(rows) < 3: continue
                away_data = parse_row_stats(rows[1])
                home_data = parse_row_stats(rows[2])
                if not away_data or not home_data: continue
                
                # Tablonun ebeveyninden isim bul
                card_container = table.find_parent("section") or table.find_parent("div")
                if card_container:
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
        print(f"❌ Matchup hatası: {e}")
        if driver: driver.quit()
        return []
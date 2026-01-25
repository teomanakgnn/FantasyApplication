import streamlit as st
import pandas as pd
import os
# ESPN ve Yahoo servisleri import edilecek
# from services.selenium_scraper import scrape_league_standings as espn_standings, scrape_matchups as espn_matchups
# from yahoo_fantasy_service import YahooFantasyService, save_yahoo_token, load_yahoo_token

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
# Yahoo credentials (Yahoo kullanıyorsanız doldurun)
YAHOO_CLIENT_ID = "dj0yJmk9N3k5WWhIRldhZ2x4JmQ9WVdrOWVtTkxkVGh4TW5jbWNHbzlNQT09JnM9Y29uc3VtZXJzZWNyZXQmc3Y9MCZ4PTc2"
YAHOO_CLIENT_SECRET = "ceb078c034cdfe589aa23d04f38a3c9f11267669"

# ---------------- CONFIG & CSS ----------------

def apply_custom_style():
    background_url = "https://wallpaper-house.com/data/out/12/wallpaper2you_489438.jpg" 
    
    st.markdown(f"""
    <style>
        /* --- HEADER VE SIDEBAR BUTONU DÜZELTMESİ --- */
        
        /* 1. Header'ı tamamen yok etme, şeffaf yap (Menü butonları için) */
        header[data-testid="stHeader"] {{
            background: transparent !important;
            visibility: visible !important; /* Görünür yap */
        }}
        
        /* 2. Header içindeki sadece dekorasyonu gizle ama butonları bırak */
        header[data-testid="stHeader"] > div:first-child {{
            display: none; /* Üstteki renkli şeridi gizle */
        }}
        
        /* 3. Hamburger menü ikonunun rengini beyaz yap (Koyu tema için) */
        button[data-testid="baseButton-header"] {{
            color: white !important;
        }}
        
        /* 4. Sidebar açıldığında z-index ayarı (Mobilde üstte kalsın) */
        section[data-testid="stSidebar"] {{
            z-index: 99999 !important;
        }}

        /* --- DİĞER CSS AYARLARI --- */
        
        .block-container {{ 
            padding-top: 3rem !important; /* Header görünür olduğu için biraz daha aşağı */
            padding-bottom: 5rem !important; 
        }}
        
        footer {{ visibility: hidden; display: none; }}
        
        .stApp {{
            background-image: url("{background_url}");
            background-attachment: fixed;
            background-position: center;
            background-size: cover;
        }}
        
        /* CONTAINER VE TABLO STİLLERİ */
        .stDataFrame, .stContainer, div[data-testid="stExpander"] {{
            background-color: rgba(15, 23, 42, 0.95); 
            border-radius: 8px;
            border: 1px solid #334155;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        
        h1, h2, h3, h4, h5, h6, p, span, div, label {{
            color: #e2e8f0 !important;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}

        /* --- MOBİL İÇİN KRİTİK DÜZELTMELER (@MEDIA) --- */
        @media only screen and (max-width: 768px) {{
            /* Header mobilde çok yer kaplamasın */
            header[data-testid="stHeader"] {{
                height: 3rem !important;
            }}
            
            /* Mobilde scroll alanı */
            .block-container {{
                padding-bottom: 15rem !important; 
                padding-top: 1rem !important;
            }}
            
            /* Kartlar */
            .platform-selector {{
                height: auto !important;
                min-height: 180px !important;
                margin: 10px 0 !important;
                padding: 10px !important;
            }}
            
            div[class='platform-selector'] > div {{
                font-size: 32px !important; 
                margin-bottom: 0px !important;
            }}
            h3 {{ font-size: 1.2rem !important; margin: 5px 0 !important; }}
            
            /* Matchup */
            .matchup-row {{
                flex-direction: column !important;
                align-items: flex-start !important;
                gap: 5px !important;
            }}
            .result-badge {{
                width: 100% !important;
                justify-content: center !important;
            }}
        }}

        /* BUTONLAR */
        button[kind="primary"] {{
            background-color: #2563eb;
            color: white;
            border: none;
            transition: 0.3s;
        }}
        button[kind="primary"]:hover {{ background-color: #1d4ed8; }}

        /* MATCHUP ROW (MASAÜSTÜ) */
        .matchup-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(30, 41, 59, 0.6);
            padding: 14px 24px;
            margin-bottom: 10px;
            border-radius: 6px;
            border: 1px solid #334155;
            transition: all 0.2s ease-in-out;
        }}
        .matchup-row:hover {{
            background: rgba(30, 41, 59, 0.95);
            border-color: #475569;
            transform: translateX(2px);
        }}
        
        .platform-selector {{
            background: rgba(30, 41, 59, 0.6);
            border: 2px solid #475569;
            border-radius: 12px;
            padding: 16px;
            margin: 16px 0;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        .platform-selector:hover {{
            border-color: #60a5fa;
            background: rgba(37, 99, 235, 0.1);
        }}
    </style>
    """, unsafe_allow_html=True)

# ---------------- HELPER FUNCTIONS ----------------

def clean_stat_value(val):
    try:
        if isinstance(val, (int, float)): return float(val)
        val = str(val).strip()
        if val == '--': return 0.0
        if '%' in val: return float(val.replace('%', ''))
        return float(val)
    except: return 0.0

def get_stat_val(stats, key):
    return stats.get(key, 0)

def calculate_roto_score(matchups):
    data = []
    for m in matchups:
        h_stats = m['home_team'].get('stats', {}).copy()
        h_stats['Team'] = m['home_team']['name']
        data.append(h_stats)
        
        a_stats = m['away_team'].get('stats', {}).copy()
        a_stats['Team'] = m['away_team']['name']
        data.append(a_stats)
    
    if not data:
        return None, None
    
    df = pd.DataFrame(data)
    target_cols = ['Team', 'FG%', 'FT%', '3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO']
    
    for col in target_cols:
        if col not in df.columns:
            df[col] = 0.0
    
    df = df[target_cols]
    stat_cols = [c for c in target_cols if c != 'Team']
    
    for col in stat_cols:
        df[col] = df[col].apply(clean_stat_value)
    
    points_df = df[['Team']].copy()
    
    for col in stat_cols:
        if col == 'TO':
            points_df[col] = df[col].rank(ascending=False, method='min')
        else:
            points_df[col] = df[col].rank(ascending=True, method='min')
    
    points_df['Total Score'] = points_df[stat_cols].sum(axis=1)
    points_df = points_df.sort_values('Total Score', ascending=False).reset_index(drop=True)
    
    df_sorted = df.set_index('Team').loc[points_df['Team']].reset_index()
    
    return df_sorted, points_df

def compare_teams_detailed(team_a_stats, team_b_stats):
    wins, losses, ties = 0, 0, 0
    cats = ['FG%', 'FT%', '3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO']
    inverse_cats = ['TO']
    
    for cat in cats:
        val_a = clean_stat_value(get_stat_val(team_a_stats, cat))
        val_b = clean_stat_value(get_stat_val(team_b_stats, cat))
        
        if cat in inverse_cats:
            if val_a < val_b: wins += 1
            elif val_a > val_b: losses += 1
            else: ties += 1
        else:
            if val_a > val_b: wins += 1
            elif val_a < val_b: losses += 1
            else: ties += 1
    
    return wins, losses, ties

def run_h2h_simulation_detailed(matchups):
    team_pool = []
    for m in matchups:
        team_pool.append({"name": m['home_team']['name'], "stats": m['home_team'].get('stats', {})})
        team_pool.append({"name": m['away_team']['name'], "stats": m['away_team'].get('stats', {})})
    
    sim_results = []
    for team_a in team_pool:
        total_wins, total_losses, total_ties = 0, 0, 0
        match_details = []
        
        for team_b in team_pool:
            if team_a['name'] == team_b['name']:
                continue
            
            w, l, t = compare_teams_detailed(team_a['stats'], team_b['stats'])
            total_wins += w
            total_losses += l
            total_ties += t
            
            if w > l: res = "WIN"
            elif l > w: res = "LOSS"
            else: res = "TIE"
            
            match_details.append({
                "opponent": team_b['name'],
                "record": f"{w}-{l}-{t}",
                "result": res
            })
        
        total_cats = total_wins + total_losses + total_ties
        win_pct = total_wins / total_cats if total_cats > 0 else 0
        
        sim_results.append({
            "team": team_a['name'],
            "total_wins": total_wins,
            "total_losses": total_losses,
            "win_pct": win_pct,
            "details": match_details,
            "opponents_beaten": sum(1 for d in match_details if d['result'] == 'WIN'),
            "opponents_lost": sum(1 for d in match_details if d['result'] == 'LOSS')
        })
    
    sim_results.sort(key=lambda x: (-x['total_wins'], -x['win_pct']))
    return sim_results

def rename_display_columns(df):
    display_map = {
        "3PTM": "3PT",
        "ST": "STL",
        "TO": "TOV"
    }
    return df.rename(columns=display_map)

# ---------------- PLATFORM HANDLERS ----------------

def load_espn_data(league_id, time_filter):
    """ESPN verilerini yükler"""
    try:
        from services.selenium_scraper import scrape_league_standings, scrape_matchups
        
        df_standings = scrape_league_standings(int(league_id))
        matchups = scrape_matchups(int(league_id), time_filter)
        
        return df_standings, matchups, None
    except Exception as e:
        return None, None, str(e)

def load_yahoo_data(league_key, week_number):
    """Yahoo verilerini yükler"""
    try:
        from services.yahoo_api import YahooFantasyService
        
        yahoo_service = st.session_state.get('yahoo_service')
        
        if not yahoo_service:
            return None, None, "Yahoo authentication required"
        
        df_standings = yahoo_service.get_league_standings(league_key)
        week_param = week_number if week_number > 0 else None
        matchups = yahoo_service.get_league_matchups(league_key, week_param)
        
        return df_standings, matchups, None
    except ImportError:
        return None, None, "requests-oauthlib package not installed. Run: pip install requests-oauthlib"
    except Exception as e:
        return None, None, str(e)

def handle_yahoo_auth():
    """Yahoo OAuth işlemlerini yönetir"""
    
    # requests-oauthlib kontrolü
    try:
        from services.yahoo_api import YahooFantasyService, load_yahoo_token
    except ImportError as e:
        st.error("""
        ❌ **Missing Required Package**
        
        Yahoo integration requires `requests-oauthlib` package.
        
        Please install it by running:
        ```bash
        pip install requests-oauthlib
        ```
        
        Then restart the application.
        """)
        return False
    
    if 'yahoo_service' not in st.session_state:
        st.session_state.yahoo_service = YahooFantasyService(
            client_id=YAHOO_CLIENT_ID,
            client_secret=YAHOO_CLIENT_SECRET
        )
    
    if 'yahoo_authenticated' not in st.session_state:
        st.session_state.yahoo_authenticated = False
        

    
    return st.session_state.yahoo_authenticated

# ---------------- MAIN APP ----------------

def render_fantasy_league_page():
    st.set_page_config(page_title="Fantasy Basketball Analytics", layout="wide", initial_sidebar_state="expanded")
    apply_custom_style()
    
    # Header
    c1, c2 = st.columns([3, 1])
    with c1:
        st.title("🏀 FANTASY BASKETBALL ANALYTICS")
        
        # Platform badge
        if 'selected_platform' in st.session_state:
            platform = st.session_state.selected_platform
            if platform == 'ESPN':
                badge_class = 'espn-badge'
                icon = '🔴'
            else:
                badge_class = 'yahoo-badge'
                icon = '🟣'
            
            time_filter = st.session_state.get('time_filter', 'week')
            filter_display = {"week": "CURRENT WEEK", "month": "LAST MONTH", "season": "FULL SEASON"}
            
            st.markdown(f"""
            <div style='color: #94a3b8; margin-top: -15px; margin-bottom: 20px;'>
                <span class='platform-badge {badge_class}'>{icon} {platform}</span>
                ADVANCED DATA INTELLIGENCE // 9-CAT 
                <span class='time-badge'>{filter_display.get(time_filter, 'CURRENT WEEK')}</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color: #94a3b8; margin-top: -15px; margin-bottom: 20px;'>SELECT A PLATFORM TO BEGIN</div>", unsafe_allow_html=True)
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown("### 🎯 PLATFORM SELECTION")
        
        # Platform seçimi
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔴 ESPN", use_container_width=True, 
                        type="primary" if st.session_state.get('selected_platform') == 'ESPN' else "secondary"):
                st.session_state.selected_platform = 'ESPN'
                st.session_state.pop('df_standings', None)
                st.session_state.pop('matchups', None)
                st.rerun()
        
        with col2:
            if st.button("🟣 YAHOO", use_container_width=True,
                        type="primary" if st.session_state.get('selected_platform') == 'YAHOO' else "secondary"):
                st.session_state.selected_platform = 'YAHOO'
                st.session_state.pop('df_standings', None)
                st.session_state.pop('matchups', None)
                st.rerun()
        
        st.markdown("---")
        
        # Platform bazlı input alanları
        if st.session_state.get('selected_platform') == 'ESPN':
            st.markdown("### 🔴 ESPN CONFIGURATION")
            
            league_input = st.text_input("LEAGUE ID", value="987023001", key="espn_league_id")
            if "leagueId=" in league_input:
                league_id = league_input.split("leagueId=")[1].split("&")[0]
            else:
                league_id = league_input.strip()
            
            st.markdown("---")
            
            # Time filter (ESPN için)
            st.markdown("**TIME PERIOD**")
            time_filter = st.radio(
                "Select Data Range:",
                options=["week", "month", "season"],
                format_func=lambda x: {
                    "week": "📅 Current Week",
                    "month": "🔒 Last Month (PRO)",
                    "season": "🔒 Full Season (PRO)"
                }[x],
                index=0,
                key="espn_time_filter",
                disabled=True,
                label_visibility="collapsed"
            )
            time_filter = "week"
            st.session_state['time_filter'] = "week"
            
            st.markdown("---")
            
            if st.button("⚡ LOAD ESPN DATA", type="primary", use_container_width=True):
                with st.spinner("CONNECTING TO ESPN SERVERS..."):
                    df_standings, matchups, error = load_espn_data(league_id, time_filter)
                    
                    if error:
                        st.error(f"❌ ESPN ERROR: {error}")
                    else:
                        st.session_state['df_standings'] = df_standings
                        st.session_state['matchups'] = matchups
                        st.session_state['current_league_id'] = league_id
                        st.success("✅ ESPN data loaded successfully!")
                        st.rerun()
        
        elif st.session_state.get('selected_platform') == 'YAHOO':
            st.markdown("### 🟣 YAHOO CONFIGURATION")
            
            # Yahoo authentication kontrolü
            is_authenticated = handle_yahoo_auth()
            
            if not is_authenticated:
                st.warning("🔐 Authentication Required")
                
                if st.button("🔗 Get Authorization URL", use_container_width=True):
                    auth_url = st.session_state.yahoo_service.get_authorization_url()
                    st.session_state.auth_url = auth_url
                
                if 'auth_url' in st.session_state:
                    st.markdown(f"**1. [Click here]({st.session_state.auth_url})**")
                    st.markdown("**2. Authorize on Yahoo**")
                    st.markdown("**3. Enter code below:**")
                    
                    auth_code = st.text_input("Authorization Code", type="password", key="yahoo_auth_code")
                    
                    if st.button("✅ Complete Auth", use_container_width=True) and auth_code:
                        try:
                            from services.yahoo_api import save_yahoo_token
                            token = st.session_state.yahoo_service.fetch_token(auth_code)
                            save_yahoo_token(token)
                            st.session_state.yahoo_authenticated = True
                            st.success("✅ Authentication successful!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Auth failed: {str(e)}")
            else:
                st.success("✅ Authenticated")
                
                # League listesi yükle
                if st.button("🔄 Load My Leagues", use_container_width=True):
                    with st.spinner("Fetching leagues..."):
                        try:
                            leagues = st.session_state.yahoo_service.get_user_leagues('nba')
                            st.session_state.user_leagues = leagues
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
                
                # League seçimi
                if 'user_leagues' in st.session_state and st.session_state.user_leagues:
                    league_options = {f"{league['name']} ({league['season']})": league['league_key'] 
                                    for league in st.session_state.user_leagues}
                    
                    selected_league_name = st.selectbox("Select League", list(league_options.keys()), key="yahoo_league_select")
                    league_key = league_options[selected_league_name]
                else:
                    league_key = st.text_input("League Key", placeholder="428.l.123456", key="yahoo_league_key")
                
                week_number = st.number_input("Week (0 = current)", min_value=0, max_value=25, value=0, key="yahoo_week")
                
                st.markdown("---")
                
                # 1. LOAD DATA BUTONU
                if st.button("⚡ LOAD YAHOO DATA", type="primary", use_container_width=True):
                    if league_key:
                        with st.spinner("CONNECTING TO YAHOO SERVERS..."):
                            df_standings, matchups, error = load_yahoo_data(league_key, week_number)
                            
                            if error:
                                st.error(f"❌ YAHOO ERROR: {error}")
                            else:
                                st.session_state['df_standings'] = df_standings
                                st.session_state['matchups'] = matchups
                                st.session_state['current_league_key'] = league_key
                                st.success("✅ Yahoo data loaded successfully!")
                                st.rerun()

                # 2. LOAD ROSTERS BUTONU (YENİ EKLENEN KISIM)
                if st.button("👥 Load Rosters (For Trade)", use_container_width=True):
                    if league_key:
                        with st.spinner("Fetching all rosters..."):
                            try:
                                # yahoo_api.py içindeki get_league_rosters fonksiyonunu çağırıyoruz
                                rosters = st.session_state.yahoo_service.get_league_rosters(league_key)
                                st.session_state['rosters'] = rosters
                                st.success(f"✅ Loaded {len(rosters)} teams!")
                            except Exception as e:
                                st.error(f"Error loading rosters: {str(e)}")
                    else:
                        st.warning("Please select a league first.")

                st.markdown("---")
                
                if st.button("🚪 Logout Yahoo", use_container_width=True):
                    st.session_state.yahoo_authenticated = False
                    st.session_state.pop('yahoo_service', None)
                    st.rerun()
    
    # --- DATA DISPLAY ---
    df_standings = st.session_state.get('df_standings')
    matchups = st.session_state.get('matchups')
    selected_platform = st.session_state.get('selected_platform')
    
# Sadece platform seçilmemişse welcome screen göster
    if not selected_platform:
        # Başlık alanı
        st.markdown("""
        <div style='text-align: center; padding: 40px 20px 20px 20px;'>
            <h2 style='color: #60a5fa; margin-bottom: 10px;'>Welcome to Fantasy Basketball Analytics</h2>
            <p style='font-size: 18px; color: #94a3b8;'>
                Choose your platform to get started
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Ortalı bir alan oluşturmak için kolonlar (Sol boşluk - Kart 1 - Boşluk - Kart 2 - Sağ boşluk)
        c_space1, c_espn, c_space2, c_yahoo, c_space3 = st.columns([1, 4, 1, 4, 1])
        
        # --- ESPN KARTI ---
        with c_espn:
            # Görsel Kısım (HTML)
            st.markdown("""
            <div class='platform-selector' style='text-align: center; padding: 20px; height: 250px; display: flex; flex-direction: column; justify-content: center;'>
                <div style='font-size: 48px; margin-bottom: 10px;'>🔴</div>
                <h3 style='color: #ef4444; margin: 0 0 10px 0;'>ESPN</h3>
                <p style='font-size: 14px; color: #94a3b8; line-height: 1.6;'>
                    • Easy setup with League ID<br>
                    • No authentication required<br>
                    • Weekly stats & rankings
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Aksiyon Butonu
            if st.button("SELECT ESPN", use_container_width=True, type="primary"):
                st.session_state.selected_platform = 'ESPN'
                st.session_state.pop('df_standings', None)
                st.session_state.pop('matchups', None)
                st.rerun()

        # --- YAHOO KARTI ---
        with c_yahoo:
            # Görsel Kısım (HTML)
            st.markdown("""
            <div class='platform-selector' style='text-align: center; padding: 20px; height: 250px; display: flex; flex-direction: column; justify-content: center;'>
                <div style='font-size: 48px; margin-bottom: 10px;'>🟣</div>
                <h3 style='color: #8b5cf6; margin: 0 0 10px 0;'>YAHOO</h3>
                <p style='font-size: 14px; color: #94a3b8; line-height: 1.6;'>
                    • OAuth authentication<br>
                    • Full API access<br>
                    • Advanced analytics
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Aksiyon Butonu
            if st.button("SELECT YAHOO", use_container_width=True, type="primary"):
                st.session_state.selected_platform = 'YAHOO'
                st.session_state.pop('df_standings', None)
                st.session_state.pop('matchups', None)
                st.rerun()
        
        return
    
    # Platform seçilmiş ama veri yüklenmemişse bilgilendirme mesajı
    if df_standings is None and matchups is None:
        platform_name = "ESPN" if selected_platform == "ESPN" else "Yahoo"
        icon = "🔴" if selected_platform == "ESPN" else "🟣"
        
        st.markdown(f"""
        <div style='text-align: center; padding: 60px 20px;'>
            <div style='font-size: 72px; margin-bottom: 20px;'>{icon}</div>
            <h2 style='color: #60a5fa; margin-bottom: 20px;'>{platform_name} Platform Selected</h2>
            <p style='font-size: 18px; color: #94a3b8; margin-bottom: 20px;'>
                Configure your league settings in the sidebar and click the load button
            </p>
            <div style='background: rgba(59, 130, 246, 0.1); border: 2px solid #3b82f6; border-radius: 12px; padding: 20px; max-width: 500px; margin: 0 auto;'>
                <p style='font-size: 14px; color: #94a3b8; margin: 0;'>
                    👈 Check the sidebar for configuration options
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # Veri yüklendiyse tabs göster
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 STANDINGS", "⚔️ MATCHUPS", "💪 H2H POWER RANK", "🎯 ROTO SIMULATION", "TRADE ANALYZER"])
    
    # TAB 1: STANDINGS
    with tab1:
        if df_standings is not None and not df_standings.empty:
            st.dataframe(df_standings, use_container_width=True, hide_index=True)
        else:
            st.info("NO STANDINGS DATA AVAILABLE")
    
    # TAB 2: MATCHUPS
    with tab2:
        if matchups:
            # --- DEBUG BAŞLANGIÇ (Sorun çözülünce silin) ---
            with st.expander("🛠️ DEBUG: Raw Matchup Data Check"):
                st.write("First Matchup Stats:", matchups[0]['home_team']['stats'])
                
                required_cats = ['FG%', 'FT%', '3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO']
                missing = [cat for cat in required_cats if cat not in matchups[0]['home_team']['stats']]
                
                if missing:
                    st.error(f"⚠️ Missing Categories for Simulation: {missing}")
                    st.info("Yahoo API'den bu kategoriler gelmiyor. Lig ayarlarınız standart 9-cat olmayabilir veya Stat ID'ler farklıdır.")
                else:
                    st.success("✅ All required stats are present!")
            st.markdown(f"### ⚔️ WEEKLY HEAD-TO-HEAD ({len(matchups)} Matchups)")
            
            for match in matchups:
                games_away = match['away_team'].get('weekly_games', 0)
                games_home = match['home_team'].get('weekly_games', 0)
                
                with st.container(border=True):
                    col1, col2, col3 = st.columns([1, 0.2, 1])
                    
                    with col1:
                        st.markdown(f"<h3 style='text-align:right; margin:0'>{match['away_team']['name']}</h3>", unsafe_allow_html=True)
                        st.markdown(f"""
                        <div style='display:flex; justify-content:flex-end; margin-bottom:5px;'>
                            <span style='background:#10b981; color:white; padding:4px 10px; border-radius:6px; font-size:12px; font-weight:bold;'>
                                📅 WEEKLY GAMES: {games_away}
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
                        st.markdown(f"<h1 style='text-align:right; color:#3b82f6; margin:0; font-size: 3rem;'>{match['away_score']}</h1>", unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown("<div style='display:flex; align-items:center; justify-content:center; height:100%;'><h3 style='color:#64748b; margin-top:20px'>VS</h3></div>", unsafe_allow_html=True)
                    
                    with col3:
                        st.markdown(f"<h3 style='text-align:left; margin:0'>{match['home_team']['name']}</h3>", unsafe_allow_html=True)
                        st.markdown(f"""
                        <div style='display:flex; justify-content:flex-start; margin-bottom:5px;'>
                            <span style='background:#10b981; color:white; padding:4px 10px; border-radius:6px; font-size:12px; font-weight:bold;'>
                                📅 WEEKLY GAMES: {games_home}
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
                        st.markdown(f"<h1 style='text-align:left; color:#ef4444; margin:0; font-size: 3rem;'>{match['home_score']}</h1>", unsafe_allow_html=True)
        else:
            st.info("NO MATCHUP DATA AVAILABLE")
    
    # TAB 3: H2H POWER RANKINGS
    with tab3:
        if matchups:
            st.markdown("### ALL-PLAY-ALL SIMULATION (H2H)")
            sim_data = run_h2h_simulation_detailed(matchups)
            
            total_opponents = len(sim_data) - 1
            best_teams = [t for t in sim_data if t['opponents_beaten'] == total_opponents]
            worst_teams = [t for t in sim_data if t['opponents_lost'] == total_opponents]
            
            if best_teams:
                for t in best_teams:
                    st.markdown(f"""<div style='background: rgba(34, 197, 94, 0.2); border-left: 4px solid #22c55e; padding: 10px; margin-bottom: 10px;'>
                    👑 <b>DOMINATION ALERT:</b> {t['team']} beats everyone!</div>""", unsafe_allow_html=True)
            
            if worst_teams:
                for t in worst_teams:
                    st.markdown(f"""<div style='background: rgba(239, 68, 68, 0.2); border-left: 4px solid #ef4444; padding: 10px; margin-bottom: 10px;'>
                    💀 <b>CRITICAL:</b> {t['team']} loses to everyone.</div>""", unsafe_allow_html=True)
            
            st.divider()
            
            summary_df = pd.DataFrame(sim_data)[['team', 'total_wins', 'total_losses', 'win_pct']]
            summary_df.columns = ["Team", "Cat Wins", "Cat Losses", "Win %"]
            st.dataframe(summary_df.style.background_gradient(subset=['Win %'], cmap="Blues"), use_container_width=True, hide_index=True)
            
            st.divider()
            
            st.subheader("🕵️ Detailed Matchup Analysis")
            selected_team = st.selectbox("Select a team to analyze:", [t['team'] for t in sim_data])
            
            if selected_team:
                team_stats = next(t for t in sim_data if t['team'] == selected_team)
                
                st.markdown(f"##### Results for {selected_team}")
                
                icon_win = """<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>"""
                icon_loss = """<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>"""
                icon_tie = """<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14" /></svg>"""
                
                for detail in team_stats['details']:
                    if detail['result'] == "WIN":
                        border_color = "#22c55e"
                        badge_bg = "rgba(34, 197, 94, 0.2)"
                        badge_text = "#22c55e"
                        icon = icon_win
                    elif detail['result'] == "LOSS":
                        border_color = "#ef4444"
                        badge_bg = "rgba(239, 68, 68, 0.2)"
                        badge_text = "#ef4444"
                        icon = icon_loss
                    else:
                        border_color = "#94a3b8"
                        badge_bg = "rgba(148, 163, 184, 0.2)"
                        badge_text = "#cbd5e1"
                        icon = icon_tie
                    
                    st.markdown(f"""
                    <div class="matchup-row" style="border-left: 4px solid {border_color};">
                        <div style="font-weight: 600; font-size: 16px;">
                            <span style="color: #64748b; margin-right: 10px; font-size: 14px;">VS</span> {detail['opponent']}
                        </div>
                        <div style="display: flex; align-items: center; gap: 20px;">
                            <div style="color: #94a3b8; font-family: 'Consolas', monospace; font-size: 15px; letter-spacing: 1px;">{detail['record']}</div>
                            <div class="result-badge" style="background: {badge_bg}; color: {badge_text};">
                                {icon} {detail['result']}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("NO MATCHUP DATA AVAILABLE")
    
    # TAB 4: ROTO SIMULATION
    with tab4:
        if matchups:
            st.markdown("### ROTISSERIE (ROTO) ANALYSIS")
            raw_df, points_df = calculate_roto_score(matchups)
            
            if raw_df is not None:
                st.markdown("#### RAW STATS")
                format_dict = {}
                for col in ['FG%', 'FT%']:
                    if col in raw_df.columns:
                        format_dict[col] = "{:.3f}"
                for col in ['3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO']:
                    if col in raw_df.columns:
                        format_dict[col] = "{:.0f}"
                
                raw_df_display = rename_display_columns(raw_df)
                
                for col in ['3PT', 'STL', 'TOV']:
                    if col in raw_df_display.columns:
                        raw_df_display[col] = raw_df_display[col].astype(float).astype(int)
                
                st.dataframe(raw_df_display.style.format(format_dict), use_container_width=True, hide_index=True)
                
                st.divider()
                st.markdown("#### SCORING TABLE (POINTS 1-10)")
                points_df_display = rename_display_columns(points_df)
                
                st.dataframe(
                    points_df_display.style
                    .background_gradient(subset=['Total Score'], cmap="Greens")
                    .format("{:.0f}", subset=points_df_display.columns.drop('Team')),
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.info("NO MATCHUP DATA AVAILABLE")

    # TAB 5: TRADE ANALYZER
    with tab5:
        st.markdown("### 🔄 TRADE ANALYZER")
        
        rosters = st.session_state.get('rosters')
        
        if not rosters:
            st.info("⚠️ Please click '👥 Load Rosters' in the sidebar to use the Trade Analyzer.")
        else:
            # Takım Seçimi
            team_names = list(rosters.keys())
            
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("Team A")
                team_a_name = st.selectbox("Select Team A", team_names, key="trade_team_a")
                team_a_players = rosters[team_a_name]['players']
                
                # Oyuncu listesi oluştur (İsim - Pozisyon)
                p_list_a = {f"{p['name']} ({p['position']})": p['player_key'] for p in team_a_players}
                
                # Multiselect ile gönderilecek oyuncuları seç
                trade_p_a = st.multiselect("Players giving away:", options=list(p_list_a.keys()))
                
            with c2:
                st.subheader("Team B")
                # Team A seçildiyse Team B listesinden onu çıkaralım
                remaining_teams = [t for t in team_names if t != team_a_name]
                team_b_name = st.selectbox("Select Team B", remaining_teams, key="trade_team_b")
                team_b_players = rosters[team_b_name]['players']
                
                p_list_b = {f"{p['name']} ({p['position']})": p['player_key'] for p in team_b_players}
                
                trade_p_b = st.multiselect("Players receiving:", options=list(p_list_b.keys()))

            st.markdown("---")
            
            # Analyze Butonu
            if st.button("🚀 Analyze Trade Impact", type="primary", use_container_width=True):
                if not trade_p_a and not trade_p_b:
                    st.warning("Please select at least one player to trade.")
                else:
                    with st.spinner("Calculating stats impact..."):
                        # Seçilen oyuncuların Key'lerini al
                        keys_a = [p_list_a[name] for name in trade_p_a]
                        keys_b = [p_list_b[name] for name in trade_p_b]
                        
                        # API'den bu oyuncuların istatistiklerini çek
                        all_keys = keys_a + keys_b
                        
                        # Yahoo Service üzerinden stats çekme
                        player_stats = st.session_state.yahoo_service.get_players_stats(
                            st.session_state['current_league_key'], 
                            all_keys
                        )
                        
                        if not player_stats:
                            st.error("Could not fetch player stats.")
                        else:
                            # İstatistikleri ayır
                            stats_a = [p for p in player_stats if p['name'] in [n.split(' (')[0] for n in trade_p_a]]
                            stats_b = [p for p in player_stats if p['name'] in [n.split(' (')[0] for n in trade_p_b]]
                            
                            # Gösterim
                            res_c1, res_c2 = st.columns(2)
                            
                            with res_c1:
                                st.markdown(f"**{team_a_name} Receives:**")
                                for p in stats_b:
                                    st.write(f"🔹 {p['name']}")
                                    st.dataframe(pd.DataFrame([p['stats']]), hide_index=True)

                            with res_c2:
                                st.markdown(f"**{team_b_name} Receives:**")
                                for p in stats_a:
                                    st.write(f"🔸 {p['name']}")
                                    st.dataframe(pd.DataFrame([p['stats']]), hide_index=True)
                            
                            # Net Impact Tablosu (Basit toplama)
                            st.markdown("#### 📊 Net Statistical Impact (Season Average)")
                            
                            # Basit bir impact hesaplama (Gelen - Giden)
                            impact_stats = {}
                            cats = ['FG%', 'FT%', '3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO']
                            
                            # Team A için Impact (Aldıkları - Verdikleri)
                            total_in_a = {k: sum(p['stats'].get(k, 0) for p in stats_b) for k in cats}
                            total_out_a = {k: sum(p['stats'].get(k, 0) for p in stats_a) for k in cats}
                            
                            # Yüzdeler için toplama yapılmaz, ortalama alınır
                            for cat in ['FG%', 'FT%']:
                                if stats_b: total_in_a[cat] /= len(stats_b)
                                if stats_a: total_out_a[cat] /= len(stats_a)
                            
                            diff_a = {k: total_in_a[k] - total_out_a[k] for k in cats}
                            
                            # DataFrame oluştur
                            impact_df = pd.DataFrame([diff_a])
                            
                            # Renklendirme
                            def color_vals(val):
                                color = 'green' if val > 0 else 'red' if val < 0 else 'grey'
                                return f'color: {color}; font-weight: bold'
                            
                            st.markdown(f"**Impact for {team_a_name}:**")
                            st.dataframe(impact_df.style.map(color_vals).format("{:+.2f}"), hide_index=True)        

if __name__ == "__main__":

    render_fantasy_league_page()
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import textwrap
import extra_streamlit_components as stx

# --------------------
# 1. CONFIG (EN BAŞA EKLENMELİ)
# --------------------
st.set_page_config(
    page_title="HoopLife NBA", 
    layout="wide",
    page_icon="🏀",
    initial_sidebar_state="expanded"
)


# Çerez Yöneticisini Önbelleğe Alarak Başlat
# --- ESKİ HALİNDEKİ @st.cache_resource SATIRINI SİLİN ---
# Sadece şu fonksiyonu kullanın:
def get_cookie_manager():
    # Eğer session state içinde manager zaten varsa onu döndür (Tekrar oluşturma)
    if 'cookie_manager' in st.session_state:
        return st.session_state.cookie_manager
    
    # Yoksa yeni oluştur ve session state'e kaydet
    # key="nba_cookies" ekleyerek benzersiz olmasını sağlıyoruz
    manager = stx.CookieManager(key="nba_cookies")
    st.session_state.cookie_manager = manager
    return manager

# --------------------
# TRIVIA LOGIC (GÜNCELLENMİŞ - COOKIE DESTEKLİ)
# --------------------
@st.dialog("🏀 Günün NBA Sorusu", width="small")
def show_trivia_modal(question, user_id=None, current_streak=0):
    
    # --- 1. OTURUM KONTROLÜ (CEVAPLANDI MI?) ---
    # Eğer kullanıcı az önce cevapladıysa ve pencere yenilendiyse,
    # formu tekrar göstermek yerine direkt başarı mesajını gösteriyoruz.
    if st.session_state.get('trivia_success_state', False):
        st.success("✅ Correct Answer!")
        st.info(f"ℹ️ {question.get('explanation', '')}")
        st.caption("See you on tomorrow! 👋")
        
        # Kapat butonu (Opsiyonel, zaten dışarı tıklayınca kapanır)
        if st.button("Kapat", type="primary"):
            # Durumu sıfırla ve sayfayı yenile
            del st.session_state['trivia_success_state']
            if 'trivia_force_open' in st.session_state:
                del st.session_state['trivia_force_open']
            st.rerun()
        return

    # --- 2. HTML BAŞLIK KISMI ---
    if user_id:
        # Giriş yapmış: Alevli
        badge_style = "background-color: rgba(255, 75, 75, 0.15); border: 1px solid rgba(255, 75, 75, 0.3); color: #ff4b4b;"
        icon = "🔥"
        text = f"{current_streak} Day"
    else:
        # Misafir: Kilitli
        badge_style = "background-color: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.1); color: #e0e0e0;"
        icon = "🔒"
        text = "Login to save your daily streak."

    html_content = f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.1);">
        <div style="font-weight: 600; font-size: 1rem;">
            📅 {datetime.now().strftime('%d %B')}
        </div>
        <div style="{badge_style} padding: 5px 10px; border-radius: 12px; font-size: 0.85em; display: flex; align-items: center; gap: 5px;">
            <span>{icon}</span> {text}
        </div>
    </div>
    """
    st.markdown(textwrap.dedent(html_content), unsafe_allow_html=True)
    
    # --- 3. SORU VE FORM ---
    st.markdown(f"#### {question['question']}")
    
    with st.form("trivia_form", border=False):
        options = {"A": question['option_a'], "B": question['option_b'], "C": question['option_c'], "D": question['option_d']}
        choice = st.radio("Your answer:", list(options.keys()), format_func=lambda x: f"{x}) {options[x]}", index=None)
        submitted = st.form_submit_button("Answer", use_container_width=True, type="primary")
        
    if submitted:
        if not choice:
            st.warning("Please select an option.")
        else:
            is_correct = (choice == question['correct_option'])
            if is_correct:
                # --- DOĞRU CEVAP İŞLEMLERİ ---
                st.balloons()
                
                # Veritabanı/Cookie İşlemleri
                today_str = str(datetime.now().date())
                if user_id:
                    db.mark_user_trivia_played(user_id)
                    st.toast(f"Daily streak updated!", icon="🔥")
                else:
                    cookie_manager = get_cookie_manager()
                    cookie_manager.set('guest_trivia_date', today_str, key="set_trivia_cookie")

                # ÖNEMLİ: "Pencereyi Açık Tut" bayrağını kaldırıyoruz
                # Çünkü "Success State" bayrağını dikiyoruz.
                st.session_state['trivia_success_state'] = True
                st.session_state['trivia_force_open'] = True # Handle fonksiyonu için ipucu
                st.rerun() # Sayfayı yenile ki "Başarı Modu" (en üstteki blok) çalışsın
                
            else:
                # --- YANLIŞ CEVAP ---
                correct_text = options[question['correct_option']]
                st.error(f"❌ Wrong. Correct Answer: {question['correct_option']}) {correct_text}")
                if question.get('explanation'):
                    st.info(f"ℹ️ {question['explanation']}")

def handle_daily_trivia():
    # Soru verisini çek
    trivia = db.get_daily_trivia()
    if not trivia:
        return

    current_user = st.session_state.get('user')
    today_str = str(datetime.now().date())
    
    # Pencere açılmalı mı? Varsayılan: Hayır
    should_show = False
    streak = 0
    u_id = None

    if current_user:
        u_id = current_user['id']
        has_played = db.check_user_played_trivia_today(u_id)
        # Eğer oynamadıysa VEYA az önce oynayıp başarı ekranındaysa göster
        if not has_played or st.session_state.get('trivia_force_open', False):
            should_show = True
            streak = db.get_user_streak(u_id)
    else:
        # Misafir
        cookie_manager = get_cookie_manager()
        last_played_cookie = cookie_manager.get('guest_trivia_date')
        
        # Eğer cookie yoksa VEYA az önce oynayıp başarı ekranındaysa göster
        if last_played_cookie != today_str or st.session_state.get('trivia_force_open', False):
            should_show = True
            streak = 0

    # Karar verildiyse Modalı Aç
    if should_show:
        show_trivia_modal(trivia, u_id, streak)

def render_adsense():
    try:
        with open("adsense.html", 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # Height'i artıralım ki reklam görünsün
        components.html(source_code, height=300, scrolling=False)
        
    except FileNotFoundError:
        st.error("adsense.html dosyası bulunamadı!")


# Authentication kontrolü (opsiyonel)
from auth import check_authentication, logout

from components.styles import load_styles
from components.header import render_header
from components.sidebar import render_sidebar
from components.tables import render_tables
from components.mvp_lvp import render_mvp_lvp_section

from services.espn_api import (
    get_last_available_game_date,
    get_cached_boxscore,
    get_scoreboard
)
from services.database import db

try:
    from services.scoring import calculate_scores
except ImportError:
    pass 

def is_embedded():
    return st.query_params.get("embed") == "true"

# --------------------
# INIT & STYLES
# --------------------
embed_mode = is_embedded()

# Embed modunda ekstra stil ekle
extra_styles = ""
if embed_mode:
    extra_styles = """
        /* EMBED MODE - Her şeyi gizle */
        [data-testid="stHeader"] {display: none !important;}
        [data-testid="stToolbar"] {display: none !important;}
        header {display: none !important;}
        #MainMenu {display: none !important;}
        footer {display: none !important;}
        .stDeployButton {display: none !important;}
        
        /* Üst padding'i kaldır */
        .main .block-container {
            padding-top: 0.5rem !important;
        }
        
        /* Streamlit watermark */
        [data-testid="stStatusWidget"] {display: none !important;}
        
        /* ALTTAKI FOOTER KISMI */
        [data-testid="stBottom"] {display: none !important;}
        .reportview-container .main footer {display: none !important;}
    """

st.markdown(f"""
    <style>
        /* 1. GENEL AYARLAR */
        .stApp {{ 
            background-image: none !important;
            background-color: #0e1117;
        }}
        
        /* ----------------------------------------------------------- */
        /* 2. HEADER GİZLEME VE BUTONU KURTARMA (VISIBILITY YÖNTEMİ) */
        /* ----------------------------------------------------------- */
        
        /* Header'ı tamamen görünmez yap (yer kaplamasın diye height 0 değil, visibility kullanıyoruz) */
        [data-testid="stHeader"] {{
            visibility: hidden !important;  /* Görünmez yap */
            height: 0px !important;         /* Yer kaplamasın */
            padding-top: 0px !important;
        }}

        /* Süslemeleri gizle */
        [data-testid="stDecoration"] {{
            display: none !important;
        }}

        /* BUTONU ZORLA GÖRÜNÜR YAP (Çocuğu ebeveynden kurtar) */
        [data-testid="stSidebarCollapsedControl"] {{
            visibility: visible !important; /* Ebeveyni gizli olsa bile sen görün! */
            display: block !important;
            
            /* Konumlandırma - Ekranın sol üst köşesine çivile */
            position: fixed !important;
            top: 20px !important;
            left: 20px !important;
            z-index: 1000005 !important; /* Her şeyin üstünde */
            
            /* Stil - Rahat görünsün */
            background-color: rgba(255, 255, 255, 0.1) !important;
            color: white !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            border-radius: 8px !important;
            padding: 0.5rem !important;
            width: 44px !important;
            height: 44px !important;
        }}
        
        /* Hover efekti */
        [data-testid="stSidebarCollapsedControl"]:hover {{
            background-color: rgba(255, 255, 255, 0.3) !important;
            cursor: pointer;
        }}

        /* İKON RENGİNİ GARANTİLEME (Bazen ikon siyah kalabiliyor) */
        [data-testid="stSidebarCollapsedControl"] svg {{
            fill: white !important;
            stroke: white !important;
        }}

        /* ----------------------------------------------------------- */
        /* 3. LOGOYU EN ÜSTE ALMA (FLEX ORDER) */
        /* ----------------------------------------------------------- */
        [data-testid="stSidebarContent"] {{
            display: flex;
            flex-direction: column;
        }}
        [data-testid="stSidebarUserContent"] {{
            order: 1;
            padding-top: 20px;
        }}
        [data-testid="stSidebarNav"] {{
            order: 2;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            margin-top: 1rem;
            padding-top: 1rem;
        }}

        /* ----------------------------------------------------------- */
        /* 4. DİĞER GİZLEMELER */
        /* ----------------------------------------------------------- */
        [data-testid="stToolbar"] {{ display: none !important; }}
        .stDeployButton {{ display: none !important; }}
        #MainMenu {{ display: none !important; }}
        footer {{ display: none !important; }}
        [data-testid="stBottom"] {{ display: none !important; }}
        
        {extra_styles}
    </style>
""", unsafe_allow_html=True)

load_styles()

if "auto_loaded" not in st.session_state:
    st.session_state.auto_loaded = True

if "page" not in st.session_state:
    st.session_state.page = "home"

if "show_all_games" not in st.session_state:
    st.session_state.show_all_games = False

if "slider_index" not in st.session_state:
    st.session_state.slider_index = 0

# Check if user is authenticated (opsiyonel)
is_authenticated = check_authentication()
user = st.session_state.get('user', None)
is_pro = user.get('is_pro', False) if user else False


st.sidebar.image(
        "HoopLifeNBA_logo.png",             # Resim yolu veya URL'si
        use_container_width=True   # Sidebar genişliğine otomatik sığdırır
    )

# Sidebar - User Section
with st.sidebar:
    st.markdown("---")
    
    if is_authenticated and user:
        # Logged in user
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
                <div style='color: white; font-weight: 600; font-size: 1.1rem;'>
                    👤 {user.get('username', 'User')}
                </div>
                <div style='color: rgba(255,255,255,0.8); font-size: 0.85rem;'>
                    {user.get('email', '')}
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Pro status
        if is_pro:
            st.success("⭐ PRO Member")
            
            # Watchlist quick access
            watchlist_count = len(db.get_watchlist(user['id']))
            if st.button(f"📋 My Watchlist ({watchlist_count})", use_container_width=True):
                st.session_state.page = "watchlist"
                st.rerun()
        else:
            st.info("🆓 Free Account")
            if st.button("⭐ Upgrade to PRO", use_container_width=True):
                st.info("Contact admin for PRO upgrade")
        
        # Logout button
        if st.button("🚪 Logout", use_container_width=True, type="secondary"):
            logout()
    else:
        # Not logged in - show login/register option
        st.markdown("""
            <div style='background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); 
                        padding: 1rem; border-radius: 10px; margin-bottom: 1rem; text-align: center;'>
                <div style='color: white; font-weight: 600; font-size: 1.1rem; margin-bottom: 0.5rem;'>
                    🎯 Get More Features
                </div>
                <div style='color: rgba(255,255,255,0.9); font-size: 0.85rem;'>
                    Login to unlock PRO features
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔐 Login / Register", use_container_width=True, type="primary"):
            st.session_state.page = "login"
            st.rerun()
        
        # Quick feature preview
        with st.expander("⭐ PRO Features"):
            st.markdown("""
                - 📋 Player Watchlists
                - 📊 Advanced Analytics
                - 📈 Player Trends
                - 🔔 Custom Alerts
                - 💾 Save Preferences
                - 📥 Export Data
            """)

# Sayfa yönlendirmesi
if st.session_state.page == "login":
    from auth import render_auth_page
    render_auth_page()
    st.stop()

if st.session_state.page == "injury":
    from pages.injury_report import render_injury_page
    render_injury_page()
    if st.sidebar.button("⬅️ Back to Home", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()
    st.stop()


if st.session_state.page == "trends":
    # PRO kontrolü
    if not is_pro:
        st.warning("⭐ This is a PRO feature. Login and upgrade to access player trends.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔐 Login / Register", use_container_width=True, type="primary"):
                st.session_state.page = "login"
                st.rerun()
        with col2:
            if st.button("⬅️ Back to Home", use_container_width=True):
                st.session_state.page = "home"
                st.rerun()
        st.stop()
    
    from pages.player_trends import render_player_trends_page
    render_player_trends_page()
    st.stop()
    
if st.session_state.page == "fantasy_league":
    from pages.fantasy_league import render_fantasy_league_page
    render_fantasy_league_page()
    st.stop()

if st.session_state.page == "watchlist":
    # PRO kontrolü
    if not is_pro:
        st.warning("⭐ Watchlist is a PRO feature. Login and upgrade to access.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔐 Login / Register", use_container_width=True, type="primary"):
                st.session_state.page = "login"
                st.rerun()
        with col2:
            if st.button("⬅️ Back to Home", use_container_width=True):
                st.session_state.page = "home"
                st.rerun()
        st.stop()
    
    from pages.watchlist import render_watchlist_page
    render_watchlist_page()
    st.stop()

# Custom CSS for the Modal/Dialog
st.markdown("""
    <style>
    .game-header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        border: 1px solid #e0e0e0;
        color: #000;
    }
    .team-info {
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 30%;
    }
    .team-name {
        font-weight: 700;
        font-size: 1.1rem;
        margin-top: 8px;
        text-align: center;
    }
    .score-board {
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 40%;
    }
    .main-score {
        font-size: 2.5rem;
        font-weight: 800;
        font-family: 'Arial', sans-serif;
        color: #333;
    }
    .game-status {
        background-color: #e3f2fd;
        color: #1565c0;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-top: 5px;
    }
    .watchlist-btn {
        background-color: #fbbf24;
        color: #000;
        border: none;
        padding: 0.3rem 0.6rem;
        border-radius: 4px;
        font-size: 0.75rem;
        cursor: pointer;
        font-weight: 600;
    }
    .watchlist-btn:hover {
        background-color: #f59e0b;
    }
    .pro-feature-badge {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }
    @media (prefers-color-scheme: dark) {
        .game-header-container { background-color: #262730; border-color: #444; color: #fff; }
        .main-score { color: #fff; }
        .game-status { background-color: #333; color: #90caf9; }
    }
    </style>
""", unsafe_allow_html=True)


# --------------------
# POP-UP (DIALOG) FUNCTION WITH WATCHLIST
# --------------------
@st.dialog("Game Details", width="large")
def show_boxscore_dialog(game_info):
    game_id = game_info['game_id']
    
    # 1. Header
    html_header = f"""
    <div class="game-header-container">
        <div class="team-info">
            <img src="{game_info.get('away_logo')}" width="60">
            <div class="team-name">{game_info.get('away_team')}</div>
        </div>
        <div class="score-board">
            <div class="main-score">
                {game_info.get('away_score')} - {game_info.get('home_score')}
            </div>
            <div class="game-status">{game_info.get('status')}</div>
        </div>
        <div class="team-info">
            <img src="{game_info.get('home_logo')}" width="60">
            <div class="team-name">{game_info.get('home_team')}</div>
        </div>
    </div>
    """
    st.markdown(html_header, unsafe_allow_html=True)

    # 2. Data Loading
    with st.spinner("Loading stats..."):
        players = get_cached_boxscore(game_id)
    
    if not players:
        st.warning("Box score details are not available yet.")
        return

    # 3. Data Processing
    df = pd.DataFrame(players)
    
    numeric_cols = ["PTS", "REB", "AST", "STL", "BLK", "TO", "FGM", "FGA", "3Pts", "3PTA", "FTM", "FTA"]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        else:
            df[c] = 0

    df["FG"] = df.apply(lambda x: f"{int(x['FGM'])}-{int(x['FGA'])}", axis=1)
    df["3PT"] = df.apply(lambda x: f"{int(x['3Pts'])}-{int(x['3PTA'])}", axis=1)
    df["FT"] = df.apply(lambda x: f"{int(x['FTM'])}-{int(x['FTA'])}", axis=1)

    if "MIN" not in df.columns:
        df["MIN"] = "--"

    display_cols = ["PLAYER", "MIN", "FG", "3PT", "FT", "PTS", "REB", "AST", "STL", "BLK", "TO"]
    final_cols = [c for c in display_cols if c in df.columns]

    # 4. PRO FEATURE: Add to Watchlist
    if is_pro and user:
        st.markdown("#### ⭐ Quick Add to Watchlist")
        
        # Get existing watchlist
        watchlist = db.get_watchlist(user['id'])
        watchlist_names = [w['player_name'] for w in watchlist]
        
        # Select players to add
        available_players = df['PLAYER'].unique().tolist()
        players_to_add = [p for p in available_players if p not in watchlist_names]
        
        if players_to_add:
            col1, col2 = st.columns([3, 1])
            with col1:
                selected_players = st.multiselect(
                    "Select players to add",
                    players_to_add,
                    help="Players already in your watchlist are not shown"
                )
            with col2:
                st.write("")
                st.write("")
                if st.button("➕ Add Selected", disabled=not selected_players):
                    added_count = 0
                    for player in selected_players:
                        if db.add_to_watchlist(user['id'], player, f"Added from {game_info.get('away_team')} vs {game_info.get('home_team')}"):
                            added_count += 1
                    
                    if added_count > 0:
                        st.success(f"✅ Added {added_count} player(s) to watchlist!")
                        st.balloons()
        else:
            st.info("All players from this game are already in your watchlist!")
        
        st.markdown("---")
    elif not is_pro:
        # Show PRO teaser
        st.info("⭐ Login with a PRO account to add players to your watchlist directly from here!")

    # 5. Tabs & Tables
    if "TEAM" in df.columns:
        teams = df["TEAM"].unique()
        
        tab1, tab2 = st.tabs([f"Away: {game_info.get('away_team')}", f"Home: {game_info.get('home_team')}"])
        
        def render_team_table(container, team_name):
            with container:
                team_df = df[df["TEAM"].astype(str).str.contains(team_name, case=False, na=False)].copy()
                
                if not team_df.empty:
                    if "MIN" in team_df.columns:
                        team_df = team_df.sort_values(
                            by="MIN", 
                            ascending=False,
                            key=lambda x: pd.to_numeric(x, errors='coerce').fillna(0)
                        )
                    
                    # Add watchlist indicators for PRO users
                    if is_pro and user:
                        watchlist = db.get_watchlist(user['id'])
                        watchlist_names = [w['player_name'] for w in watchlist]
                        team_df['⭐'] = team_df['PLAYER'].apply(lambda x: '⭐' if x in watchlist_names else '')
                        display_cols_with_star = ['⭐'] + final_cols
                    else:
                        display_cols_with_star = final_cols
                    
                    st.dataframe(
                        team_df[display_cols_with_star],
                        use_container_width=True,
                        hide_index=True,
                        height=400,
                        column_config={
                            "⭐": st.column_config.TextColumn("", width="small"),
                            "PTS": st.column_config.NumberColumn("PTS", format="%d"),
                            "MIN": st.column_config.TextColumn("MIN", width="small"),
                            "FG": st.column_config.TextColumn("FG (M-A)", width="small"),
                            "3PT": st.column_config.TextColumn("3PT (M-A)", width="small"),
                            "FT": st.column_config.TextColumn("FT (M-A)", width="small"),
                            "PLAYER": st.column_config.TextColumn("Player", width="medium"),
                        }
                    )
                else:
                    st.info(f"No stats available for {team_name}")

        if len(teams) > 0:
            render_team_table(tab1, teams[0])
            if len(teams) > 1:
                render_team_table(tab2, teams[1])
            else:
                with tab2: st.info("Waiting for data...")
    else:
        st.dataframe(df[final_cols], use_container_width=True)


# --------------------
# MAIN PAGE
# --------------------
def home_page():
    handle_daily_trivia()
    render_header()
    
    # Load user preferences if logged in
    if user:
        user_id = user['id']
        prefs = db.get_user_preferences(user_id)
    else:
        prefs = None

    if not is_pro:
        st.markdown("---")
        render_adsense()
        st.markdown("---")    
    
    # Sidebar'dan weights'i de alıyoruz
    date, weights, run = render_sidebar()
    st.session_state['last_weights'] = weights
    
    # Override with saved preferences if available
    if prefs and prefs.get('default_weights'):
        import json
        saved_weights = json.loads(prefs['default_weights']) if isinstance(prefs['default_weights'], str) else prefs['default_weights']

    if st.session_state.auto_loaded:
        run = True

    if not run:
        st.info("Select parameters and click Run.")
        return

    # 1. LOAD GAMES
    resolved_date, game_ids = get_last_available_game_date(date)
    if not game_ids:
        st.warning("No NBA games found.")
        return

    games = get_scoreboard(resolved_date)
    st.caption(f"Games from {resolved_date.strftime('%B %d, %Y')}")

    # 2. SCOREBOARD GRID
    st.subheader("Games")
    
    games_to_show = 3
    total_games = len(games)

    if st.session_state.page == "trade_analyzer":
        from pages.trade_analyzer import render_trade_analyzer_page
        # Home'dan weights alınmadıysa default oluşturmamız gerekebilir,
        # ama genelde home bir kere render olduğu için session_state'de vardır.
        render_trade_analyzer_page()
        st.stop()
    
    if st.session_state.show_all_games:
        visible_games = games
        cols_per_row = 3
    else:
        visible_games = games[:games_to_show]
        cols_per_row = 3
    
    num_visible = len(visible_games)
    
    if num_visible == 0:
         st.info("No games to display.")
    else:
        for row_start in range(0, num_visible, cols_per_row):
            row_games = visible_games[row_start:row_start + cols_per_row]
            cols = st.columns(len(row_games))
            
            for i, g in enumerate(row_games):
                with cols[i]:
                    with st.container(border=True):
                        st.markdown(f"<div style='text-align:center; color:grey; font-size:0.8em; margin-bottom:10px;'>{g.get('status')}</div>", unsafe_allow_html=True)
                        
                        c_away, c_score, c_home = st.columns([1, 1.5, 1])
                        
                        with c_away:
                            st.markdown(f"""
                            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center;">
                                <img src="{g.get('away_logo')}" style="width: 50px; height: 50px; object-fit: contain;">
                                <div style="font-size:0.9em; font-weight:bold; margin-top: 5px;">{g.get('away_team')}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with c_score:
                            st.markdown(f"<div style='font-size:1.4em; font-weight:800; text-align:center; line-height: 2.5; white-space: nowrap;'>{g.get('away_score')}&nbsp;&nbsp;-&nbsp;&nbsp;{g.get('home_score')}</div>", unsafe_allow_html=True)

                        with c_home:
                            st.markdown(f"""
                            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center;">
                                <img src="{g.get('home_logo')}" style="width: 50px; height: 50px; object-fit: contain;">
                                <div style="font-size:0.9em; font-weight:bold; margin-top: 5px;">{g.get('home_team')}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.markdown("---")
                        
                        if st.button("📊 Box Score", key=f"btn_{g['game_id']}", use_container_width=True):
                            show_boxscore_dialog(g)
    
    if total_games > games_to_show:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.session_state.show_all_games:
                if st.button("⬆️ Show Less", use_container_width=True, type="secondary"):
                    st.session_state.show_all_games = False
                    st.rerun()
            else:
                remaining = total_games - games_to_show
                if st.button(f"⬇️ Show All Games (+{remaining} more)", use_container_width=True, type="primary"):
                    st.session_state.show_all_games = True
                    st.rerun()

    st.divider()

    # 3. FANTASY TABLE (All Players) WITH WATCHLIST ACTIONS
    st.subheader("Daily Fantasy Stats")
    
    all_players = []
    for gid in game_ids:
        box = get_cached_boxscore(gid)
        if box: all_players.extend(box)

    if all_players:
        df = pd.DataFrame(all_players)
        
        num_cols = ["PTS", "REB", "AST", "STL", "BLK", "TO", "FGA", "FGM", "FTA", "FTM", "3Pts"]
        for c in num_cols:
            if c not in df.columns: df[c] = 0
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        st.session_state["period_df"] = df.copy()
            

        # PRO FEATURE: Quick add from main table
        if is_pro and user:
            with st.expander("⭐ Add Players to Watchlist", expanded=False):
                watchlist = db.get_watchlist(user['id'])
                watchlist_names = [w['player_name'] for w in watchlist]
                
                available_players = [p for p in df['PLAYER'].unique() if p not in watchlist_names]
                
                if available_players:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        quick_add_players = st.multiselect(
                            "Select players",
                            available_players,
                            key="quick_add_main"
                        )
                    with col2:
                        st.write("")
                        st.write("")
                        if st.button("➕ Add", disabled=not quick_add_players, key="quick_add_btn"):
                            for player in quick_add_players:
                                db.add_to_watchlist(user['id'], player, f"Added from Daily Stats - {resolved_date.strftime('%Y-%m-%d')}")
                            st.success(f"✅ Added {len(quick_add_players)} player(s)!")
                            st.rerun()
                else:
                    st.info("All players are already in your watchlist!")
        elif not is_pro:
            # Show PRO teaser
            st.info("⭐ **PRO Feature:** Login with a PRO account to add players to your watchlist and track their performance!")

        render_tables(df, weights=weights) 
    else:
        st.info("No stats available for the selected date.")

    current_period = st.session_state.get("stats_period", "Today")
    
    # Only show MVP/LVP for periods longer than "Today"
    if current_period != "Today":
        from components.tables import get_date_range
        date_range = get_date_range(current_period)
        render_mvp_lvp_section(date_range, weights, current_period)
    

home_page()


# En altta - home_page() fonksiyonundan sonra
st.markdown("""
<script>
    // Footer'ı tamamen kaldır
    const hideFooter = () => {
        const footer = window.parent.document.querySelector('footer');
        if (footer) footer.style.display = 'none';
        
        const stBottom = window.parent.document.querySelector('[data-testid="stBottom"]');
        if (stBottom) stBottom.style.display = 'none';
        
        const viewerBadge = window.parent.document.querySelector('[class*="viewerBadge"]');
        if (viewerBadge) viewerBadge.style.display = 'none';
    };
    
    // Sayfa yüklendiğinde ve her 1 saniyede kontrol et
    hideFooter();
    setInterval(hideFooter, 1000);
</script>
""", unsafe_allow_html=True)
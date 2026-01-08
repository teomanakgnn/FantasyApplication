import pandas as pd
import streamlit as st

# --------------------
# 1. CONFIG (EN BAŞA EKLENMELİ)
# --------------------
# Bu satır sayfanın genişliğini sabitler ve kaymaları önler.
st.set_page_config(
    page_title="NBA Dashboard", 
    layout="wide",  # "centered" isterseniz burayı değiştirin
    page_icon="🏀",
    initial_sidebar_state="expanded"
)

from components.styles import load_styles
from components.header import render_header
from components.sidebar import render_sidebar
from components.tables import render_tables

from services.espn_api import (
    get_last_available_game_date,
    get_cached_boxscore,
    get_scoreboard
)
from services.scoring import calculate_scores

# --------------------
# INIT & STYLES
# --------------------
# Injury sayfasından dönüşte kalan stilleri (arka plan vb.) temizlemek için reset CSS'i
st.markdown("""
    <style>
        /* Injury sayfasından kalan arka plan resmini kaldır */
        .stApp {
            background-image: none !important;
        }
        /* Container genişliğini standartlaştır */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 2rem !important;
        }
    </style>
""", unsafe_allow_html=True)

load_styles()

if "auto_loaded" not in st.session_state:
    st.session_state.auto_loaded = True

if "page" not in st.session_state:
    st.session_state.page = "home"

if "show_all_games" not in st.session_state:
    st.session_state.show_all_games = False

# Slider state (Eğer kullanıyorsanız)
if "slider_index" not in st.session_state:
    st.session_state.slider_index = 0

# Sayfa yönlendirmesi
if st.session_state.page == "injury":
    from pages.injury_report import render_injury_page
    render_injury_page()
    
    # Ana sayfaya dön butonu
    if st.sidebar.button("⬅️ Back to Home", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()
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
    /* Dark mode adjustments */
    @media (prefers-color-scheme: dark) {
        .game-header-container { background-color: #262730; border-color: #444; color: #fff; }
        .main-score { color: #fff; }
        .game-status { background-color: #333; color: #90caf9; }
    }
    </style>
""", unsafe_allow_html=True)


# --------------------
# POP-UP (DIALOG) FUNCTION
# --------------------
@st.dialog("Game Details", width="large")
def show_boxscore_dialog(game_info):
    """
    game_info: get_scoreboard'dan gelen tek bir oyun sözlüğü (dict)
    """
    game_id = game_info['game_id']
    
    # 1. Header (Scoreboard Design)
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

    # Field Goals (FGM-FGA)
    df["FG"] = df.apply(lambda x: f"{int(x['FGM'])}-{int(x['FGA'])}", axis=1)
    
    # 3 Pointers (3PM-3PA)
    df["3PT"] = df.apply(lambda x: f"{int(x['3Pts'])}-{int(x['3PTA'])}", axis=1)
    
    # Free Throws (FTM-FTA)
    df["FT"] = df.apply(lambda x: f"{int(x['FTM'])}-{int(x['FTA'])}", axis=1)

    # Minutes (MIN)
    if "MIN" not in df.columns:
        df["MIN"] = "--"

    # Görüntülenecek Sütun Sırası
    display_cols = ["PLAYER", "MIN", "FG", "3PT", "FT", "PTS", "REB", "AST", "STL", "BLK", "TO"]
    final_cols = [c for c in display_cols if c in df.columns]

    # 4. Tabs & Tables
    if "TEAM" in df.columns:
        teams = df["TEAM"].unique()
        
        tab1, tab2 = st.tabs([f"Away: {game_info.get('away_team')}", f"Home: {game_info.get('home_team')}"])
        
        def render_team_table(container, team_name):
            with container:
                team_df = df[df["TEAM"].astype(str).str.contains(team_name, case=False, na=False)].copy()
                
                if not team_df.empty:
                    if "MIN" in team_df.columns:
                        # Sıralama düzeltmesi: Sayısal değere göre sırala
                        team_df = team_df.sort_values(
                            by="MIN", 
                            ascending=False,
                            key=lambda x: pd.to_numeric(x, errors='coerce').fillna(0)
                        )
                    
                    st.dataframe(
                        team_df[final_cols],
                        use_container_width=True,
                        hide_index=True,
                        height=400,
                        column_config={
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
    render_header()
    
    date, weights, run = render_sidebar()

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
    
    # Kaç maç gösterilecek?
    games_to_show = 3
    total_games = len(games)
    
    # Gösterilecek maçları belirle
    if st.session_state.show_all_games:
        visible_games = games
        cols_per_row = 3
    else:
        visible_games = games[:games_to_show]
        cols_per_row = 3
    
    # Maçları göster
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
                        # Status
                        st.markdown(f"<div style='text-align:center; color:grey; font-size:0.8em; margin-bottom:10px;'>{g.get('status')}</div>", unsafe_allow_html=True)
                        
# Score Row
                        c_away, c_score, c_home = st.columns([1, 1.5, 1])
                        
                        # DEPLASMAN TAKIMI (HTML Flexbox ile ortalanmış)
                        with c_away:
                            st.markdown(f"""
                            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center;">
                                <img src="{g.get('away_logo')}" style="width: 50px; height: 50px; object-fit: contain;">
                                <div style="font-size:0.9em; font-weight:bold; margin-top: 5px;">{g.get('away_team')}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        # SKOR (Mevcut haliyle kalabilir veya aynı mantıkla düzenlenebilir)
                        with c_score:
                            st.markdown(f"<div style='font-size:1.4em; font-weight:800; text-align:center; line-height: 2.5; white-space: nowrap;'>{g.get('away_score')}&nbsp;&nbsp;-&nbsp;&nbsp;{g.get('home_score')}</div>", unsafe_allow_html=True)

                        # EV SAHİBİ TAKIMI (HTML Flexbox ile ortalanmış)
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
    
    # "Tüm Maçları Gör" / "Daha Az Göster" butonu
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

    # 3. FANTASY TABLE (All Players)
    st.subheader("🔥 Daily Fantasy Stats")
    
    all_players = []
    for gid in game_ids:
        box = get_cached_boxscore(gid)
        if box: all_players.extend(box)

    if all_players:
        df = pd.DataFrame(all_players)
        
        # Temizlik
        num_cols = ["PTS", "REB", "AST", "STL", "BLK", "TO", "FGA", "FGM", "FTA", "FTM", "3Pts"]
        for c in num_cols:
            if c not in df.columns: df[c] = 0
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

        df = calculate_scores(df, weights)
        render_tables(df)

home_page()
import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime

# Üst dizini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.espn_api import get_injuries

# -----------------------------------------------------------------------------
# CSS & STYLING (NBA PROFESSIONAL THEME)
# -----------------------------------------------------------------------------
def load_professional_styles():
    st.markdown("""
    <style>
        /* GENEL AYARLAR */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        
        /* METRIC KARTLARI */
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            padding: 15px;
            border-radius: 4px; /* Keskin köşe */
            border-left: 4px solid #17408B; /* NBA Blue */
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        div[data-testid="stMetric"] label {
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.8rem;
            color: #6c757d;
        }

        /* TEAM HEADER */
        .team-header-container {
            display: flex;
            align-items: center;
            background-color: #1d1d1d; /* Deep Black */
            color: white;
            padding: 15px 20px;
            margin-top: 30px;
            margin-bottom: 15px;
            border-radius: 2px;
            border-bottom: 3px solid #C9082A; /* NBA Red */
        }
        .team-logo-img {
            width: 45px;
            height: 45px;
            margin-right: 15px;
            filter: drop-shadow(0 0 2px rgba(255,255,255,0.2));
        }
        .team-title {
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-size: 1.4rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin: 0;
        }

        /* PLAYER CARD */
        .player-card {
            background-color: #ffffff;
            border: 1px solid #e1e4e8;
            border-radius: 3px;
            padding: 0;
            margin-bottom: 15px;
            transition: transform 0.2s, box-shadow 0.2s;
            height: 100%;
        }
        .player-card:hover {
            border-color: #b0b0b0;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }
        
        .card-top {
            display: flex;
            padding: 15px;
            border-bottom: 1px solid #f0f0f0;
        }
        .p-photo {
            width: 60px;
            height: 60px;
            border-radius: 2px; /* Kareye yakın */
            object-fit: cover;
            border: 1px solid #ddd;
            background-color: #f9f9f9;
        }
        .p-info {
            margin-left: 15px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .p-name {
            font-size: 1.05rem;
            font-weight: 700;
            color: #212529;
            line-height: 1.2;
        }
        .p-meta {
            font-size: 0.8rem;
            color: #6c757d;
            margin-top: 4px;
            font-weight: 500;
            text-transform: uppercase;
        }

        /* STATUS BADGES - SHARP LOOK */
        .status-badge {
            display: inline-block;
            padding: 4px 10px;
            font-size: 0.75rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: white;
            margin-top: 10px;
            width: 100%;
            text-align: center;
        }
        .bg-out { background-color: #C9082A; } /* Red */
        .bg-questionable { background-color: #E0A800; color: black; } /* Warning Gold */
        .bg-doubtful { background-color: #FD7E14; } /* Orange */
        .bg-day-to-day { background-color: #17408B; } /* Blue */
        
        .card-details {
            padding: 12px 15px;
            background-color: #f8f9fa;
            font-size: 0.85rem;
            color: #495057;
            line-height: 1.4;
            border-top: 1px solid #eee;
            min-height: 60px;
        }
        
        /* PAGE HEADER */
        .main-header {
            font-family: 'Helvetica Neue', sans-serif;
            font-weight: 900;
            font-size: 2.2rem;
            text-transform: uppercase;
            color: #1d1d1d;
            border-bottom: 4px solid #17408B;
            padding-bottom: 10px;
            margin-bottom: 20px;
            letter-spacing: -0.5px;
        }
        .sub-header {
            color: #666;
            font-size: 1rem;
            margin-top: -15px;
            margin-bottom: 30px;
            font-weight: 400;
        }
        
        /* DARK MODE OVERRIDES */
        @media (prefers-color-scheme: dark) {
            .player-card { background-color: #262730; border-color: #444; }
            .p-name { color: #fff; }
            .card-details { background-color: #1f2026; color: #bbb; border-top-color: #333; }
            .main-header { color: white; }
            div[data-testid="stMetric"] { background-color: #262730; border-color: #444; }
        }
    </style>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def get_status_style(status):
    s = status.lower()
    if "out" in s: return "bg-out"
    if "questionable" in s: return "bg-questionable"
    if "doubtful" in s: return "bg-doubtful"
    if "day" in s: return "bg-day-to-day"
    return "bg-out" # Default

# -----------------------------------------------------------------------------
# MAIN RENDERER
# -----------------------------------------------------------------------------
def render_injury_page():
    load_professional_styles()
    
    # 1. Header Area
    st.markdown('<div class="main-header">OFFICIAL INJURY REPORT</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">NBA LEAGUE UPDATE • {datetime.now().strftime("%B %d, %Y")}</div>', unsafe_allow_html=True)

    # 2. Controls & Metrics
    top_col1, top_col2 = st.columns([3, 1])
    
    with top_col2:
        if st.button("UPDATE DATA", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Data Loading
    with st.spinner("FETCHING LEAGUE DATA..."):
        injuries = get_injuries()

    if not injuries:
        st.error("SYSTEM MESSAGE: NO INJURY DATA AVAILABLE.")
        return

    df = pd.DataFrame(injuries)

    # 3. Filters (Clean & Minimal)
    with st.container():
        c1, c2, c3 = st.columns(3)
        with c1:
            teams = ["ALL TEAMS"] + sorted(df["team"].unique().tolist())
            selected_team = st.selectbox("TEAM FILTER", teams, label_visibility="collapsed", index=0, placeholder="Select Team")
        with c2:
            statuses = ["ALL STATUSES"] + sorted(df["status"].unique().tolist())
            selected_status = st.selectbox("STATUS FILTER", statuses, label_visibility="collapsed", index=0, placeholder="Select Status")
        with c3:
            search = st.text_input("PLAYER SEARCH", placeholder="SEARCH PLAYER...", label_visibility="collapsed")

    # Filtering Logic
    filtered_df = df.copy()
    if selected_team != "ALL TEAMS":
        filtered_df = filtered_df[filtered_df["team"] == selected_team]
    if selected_status != "ALL STATUSES":
        filtered_df = filtered_df[filtered_df["status"] == selected_status]
    if search:
        filtered_df = filtered_df[filtered_df["player"].str.contains(search, case=False, na=False)]

    st.markdown("---")

    # 4. Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("TOTAL REPORTED", len(filtered_df))
    with m2: st.metric("CONFIRMED OUT", len(filtered_df[filtered_df["status"].str.lower().str.contains("out", na=False)]))
    with m3: st.metric("DAY-TO-DAY", len(filtered_df[filtered_df["status"].str.lower().str.contains("day", na=False)]))

    st.markdown("<br>", unsafe_allow_html=True)

    # 5. Grid Layout Content
    if filtered_df.empty:
        st.info("NO MATCHING RECORDS FOUND.")
    else:
        teams_list = sorted(filtered_df["team"].unique())
        
        for team in teams_list:
            team_data = filtered_df[filtered_df["team"] == team]
            first_rec = team_data.iloc[0]
            
            # Team Header
            st.markdown(f"""
            <div class="team-header-container">
                <img src="{first_rec['team_logo']}" class="team-logo-img">
                <div class="team-title">{first_rec['team_name']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Grid System for Players (2 Players per row for density)
            # Daha modern bir grid yapısı
            player_cols = st.columns(2) 
            
            for idx, (_, player) in enumerate(team_data.iterrows()):
                col_idx = idx % 2
                with player_cols[col_idx]:
                    
                    status_cls = get_status_style(player['status'])
                    photo_url = player['player_photo'] if player['player_photo'] else "https://a.espncdn.com/combiner/i?img=/i/headshots/nophoto.png"
                    
                    st.markdown(f"""
                    <div class="player-card">
                        <div class="card-top">
                            <img src="{photo_url}" class="p-photo">
                            <div class="p-info">
                                <div class="p-name">{player['player']}</div>
                                <div class="p-meta">{player['position']}</div>
                            </div>
                        </div>
                        <div class="status-badge {status_cls}">{player['status']}</div>
                        <div class="card-details">
                            <strong>INJURY:</strong> {player['injury_type']}<br>
                            <span style="opacity:0.8">{player['details']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

if __name__ == "__main__":
    st.set_page_config(page_title="NBA Injury Report", layout="wide", page_icon="🏀")
    render_injury_page()
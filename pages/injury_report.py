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
        /* STREAMLIT HEADER GIZLE */
        header[data-testid="stHeader"] {
            display: none;
        }
        
        /* BACKGROUND IMAGE */
        .stApp {
            background-image: linear-gradient(rgba(0, 0, 0, 0.85), rgba(0, 0, 0, 0.85)), 
                              url('https://cloudfront-us-east-1.images.arcpublishing.com/opb/TRWU3XOQHNHHBLKLDFZIC42W7A.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            background-repeat: no-repeat;
        }
        
        /* GENEL AYARLAR */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            background-color: transparent;
        }
        
        /* METRIC KARTLARI */
        div[data-testid="stMetric"] {
            background-color: rgba(255, 255, 255, 0.95);
            border: 1px solid rgba(224, 224, 224, 0.5);
            padding: 15px;
            border-radius: 4px;
            border-left: 4px solid #17408B;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            backdrop-filter: blur(10px);
        }
        div[data-testid="stMetric"] label {
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.8rem;
            color: #6c757d;
        }

        /* SIDEBAR TEAM CARD */
        .sidebar-team-card {
            background-color: rgba(248, 249, 250, 0.95);
            border: 1px solid rgba(222, 226, 230, 0.6);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            transition: all 0.2s;
            cursor: pointer;
            backdrop-filter: blur(10px);
        }
        .sidebar-team-card:hover {
            background-color: rgba(233, 236, 239, 0.95);
            border-color: #17408B;
            transform: translateX(3px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        .sidebar-team-logo {
            width: 35px;
            height: 35px;
            margin-right: 12px;
        }
        .sidebar-team-info {
            flex: 1;
        }
        .sidebar-team-name {
            font-weight: 700;
            font-size: 0.9rem;
            color: #212529;
            margin: 0;
        }
        .sidebar-team-count {
            font-size: 0.75rem;
            color: #6c757d;
            margin-top: 2px;
        }
        .sidebar-injury-badge {
            background-color: #C9082A;
            color: white;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.7rem;
            font-weight: 700;
        }

        /* TEAM HEADER */
        .team-header-container {
            display: flex;
            align-items: center;
            background-color: rgba(29, 29, 29, 0.95);
            color: white;
            padding: 15px 20px;
            margin-top: 30px;
            margin-bottom: 15px;
            border-radius: 2px;
            border-bottom: 3px solid #C9082A;
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
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
            background-color: rgba(255, 255, 255, 0.95);
            border: 1px solid rgba(225, 228, 232, 0.6);
            border-radius: 3px;
            padding: 0;
            margin-bottom: 15px;
            transition: transform 0.2s, box-shadow 0.2s;
            height: 100%;
            backdrop-filter: blur(10px);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
        }
        .player-card:hover {
            border-color: #b0b0b0;
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.25);
            transform: translateY(-2px);
        }
        
        .card-top {
            display: flex;
            padding: 15px;
            border-bottom: 1px solid #f0f0f0;
        }
        .p-photo {
            width: 60px;
            height: 60px;
            border-radius: 2px;
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

        /* STATUS BADGES */
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
        .bg-out { background-color: #C9082A; }
        .bg-questionable { background-color: #E0A800; color: black; }
        .bg-doubtful { background-color: #FD7E14; }
        .bg-day-to-day { background-color: #17408B; }
        
        .card-details {
            padding: 12px 15px;
            background-color: rgba(248, 249, 250, 0.95);
            font-size: 0.85rem;
            color: #495057;
            line-height: 1.4;
            border-top: 1px solid rgba(238, 238, 238, 0.5);
            min-height: 60px;
        }
        
        .injury-date {
            font-size: 0.75rem;
            color: #868e96;
            font-style: italic;
            margin-top: 8px;
            display: block;
        }
        
        /* PAGE HEADER */
        .main-header {
            font-family: 'Helvetica Neue', sans-serif;
            font-weight: 900;
            font-size: 2.2rem;
            text-transform: uppercase;
            color: #ffffff;
            
            padding: 20px;
            border-radius: 2px;
            border-left: 6px solid #17408B;
            margin-bottom: 10px;
            letter-spacing: 1px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.7);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
          
        }
        .sub-header {
            color: #e9ecef;
            font-size: 0.95rem;
            margin-top: 0px;
            margin-bottom: 30px;
            font-weight: 500;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.7);
            padding-left: 26px;
            letter-spacing: 0.5px;
        }
        
        /* DARK MODE */
        @media (prefers-color-scheme: dark) {
            .player-card { background-color: #262730; border-color: #444; }
            .p-name { color: #fff; }
            .card-details { background-color: #1f2026; color: #bbb; border-top-color: #333; }
            .main-header { color: white; }
            div[data-testid="stMetric"] { background-color: #262730; border-color: #444; }
            .sidebar-team-card { background-color: #262730; border-color: #444; }
            .sidebar-team-card:hover { background-color: #1f2026; }
            .sidebar-team-name { color: #fff; }
        }
    </style>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SIDEBAR
# -----------------------------------------------------------------------------
def render_injury_sidebar(df):
    """Sidebar with team filters and stats"""
    
    # Quick Stats
    total_injuries = len(df)
    st.sidebar.markdown("### 📋 Team Breakdown")
    
    # Team grouping with injury counts
    team_stats = df.groupby(['team', 'team_name', 'team_logo']).size().reset_index(name='count')
    team_stats = team_stats.sort_values('team')  # Alfabetik sıralama
    
    # Initialize selected team in session state
    if 'selected_injury_team' not in st.session_state:
        st.session_state.selected_injury_team = "ALL TEAMS"
    
    # "All Teams" option
    all_teams_html = f"""
    <div class="sidebar-team-card" style="border-left: 4px solid #17408B;">
        <div class="sidebar-team-info">
            <div class="sidebar-team-name">ALL TEAMS</div>
            <div class="sidebar-team-count">{total_injuries} total injuries</div>
        </div>
        <div class="sidebar-injury-badge">{total_injuries}</div>
    </div>
    """
    
    if st.sidebar.button("All Teams", key="all_teams_btn", use_container_width=True, 
                         type="primary" if st.session_state.selected_injury_team == "ALL TEAMS" else "secondary"):
        st.session_state.selected_injury_team = "ALL TEAMS"
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Individual team cards
    for _, row in team_stats.iterrows():
        team_abbr = row['team']
        team_name = row['team_name']
        team_logo = row['team_logo']
        injury_count = row['count']
        
        # Display team card
        st.sidebar.markdown(f"""
        <div class="sidebar-team-card">
            <img src="{team_logo}" class="sidebar-team-logo">
            <div class="sidebar-team-info">
                <div class="sidebar-team-name">{team_abbr}</div>
                <div class="sidebar-team-count">{team_name}</div>
            </div>
            <div class="sidebar-injury-badge">{injury_count}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Button for filtering
        button_type = "primary" if st.session_state.selected_injury_team == team_abbr else "secondary"
        if st.sidebar.button(f"View {team_abbr}", key=f"team_{team_abbr}", 
                             use_container_width=True, type=button_type):
            st.session_state.selected_injury_team = team_abbr
            st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ℹ️ Status Legend")
    st.sidebar.markdown("""
    - 🔴 **Out**: Will not play
    - 🟡 **Questionable**: Game-time decision
    - 🟠 **Doubtful**: Unlikely to play
    - 🔵 **Day-to-Day**: Status pending
    """)
    
    return st.session_state.selected_injury_team

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def get_status_style(status):
    s = status.lower()
    if "out" in s: return "bg-out"
    if "questionable" in s: return "bg-questionable"
    if "doubtful" in s: return "bg-doubtful"
    if "day" in s: return "bg-day-to-day"
    return "bg-out"

def format_injury_date(date_str):
    """Format injury update date to readable format"""
    if not date_str:
        return "Date unknown"
    
    try:
        # ESPN API'den gelen tarih formatı genelde ISO format
        injury_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        now = datetime.now(injury_date.tzinfo)
        
        diff = now - injury_date
        
        # Bugün mü?
        if diff.days == 0:
            hours = diff.seconds // 3600
            if hours == 0:
                minutes = diff.seconds // 60
                return f"{minutes}m ago" if minutes > 0 else "Just now"
            return f"{hours}h ago"
        
        # Dün mü?
        elif diff.days == 1:
            return "Yesterday"
        
        # Bu hafta mı?
        elif diff.days < 7:
            return f"{diff.days}d ago"
        
        # Daha eski
        else:
            return injury_date.strftime("%b %d, %Y")
            
    except Exception:
        # Tarih parse edilemezse sadece tarihi göster
        try:
            injury_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return injury_date.strftime("%b %d, %Y")
        except:
            return "Date unknown"

# -----------------------------------------------------------------------------
# MAIN RENDERER
# -----------------------------------------------------------------------------
def render_injury_page():
    load_professional_styles()
    
    # Data Loading
    with st.spinner("FETCHING LEAGUE DATA..."):
        injuries = get_injuries()

    if not injuries:
        st.error("SYSTEM MESSAGE: NO INJURY DATA AVAILABLE.")
        return

    df = pd.DataFrame(injuries)
    
    # Sidebar with team selection
    selected_team = render_injury_sidebar(df)
    
    # 1. Header Area
    st.markdown('<div class="main-header">OFFICIAL INJURY REPORT</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">NBA LEAGUE UPDATE • {datetime.now().strftime("%B %d, %Y")}</div>', unsafe_allow_html=True)

    # 2. Controls
    top_col1, top_col2 = st.columns([3, 1])
    
    with top_col2:
        if st.button("🔄 UPDATE DATA", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # 3. Additional Filters
    with st.container():
        c1, c2 = st.columns(2)
        with c1:
            statuses = ["ALL STATUSES"] + sorted(df["status"].unique().tolist())
            selected_status = st.selectbox("STATUS FILTER", statuses, label_visibility="collapsed", 
                                          index=0, placeholder="Select Status")
        with c2:
            search = st.text_input("PLAYER SEARCH", placeholder="SEARCH PLAYER...", 
                                  label_visibility="collapsed")

    # Filtering Logic
    filtered_df = df.copy()
    
    # Apply team filter from sidebar
    if selected_team != "ALL TEAMS":
        filtered_df = filtered_df[filtered_df["team"] == selected_team]
    
    if selected_status != "ALL STATUSES":
        filtered_df = filtered_df[filtered_df["status"] == selected_status]
    
    if search:
        filtered_df = filtered_df[filtered_df["player"].str.contains(search, case=False, na=False)]

    st.markdown("---")

    # 4. Metrics Row
    m1, m2, m3 = st.columns(3)
    with m1: 
        st.metric("TOTAL REPORTED", len(filtered_df))
    with m2: 
        st.metric("CONFIRMED OUT", len(filtered_df[filtered_df["status"].str.lower().str.contains("out", na=False)]))
    with m3: 
        st.metric("DAY-TO-DAY", len(filtered_df[filtered_df["status"].str.lower().str.contains("day", na=False)]))

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
            
            # Grid System for Players
            player_cols = st.columns(2) 
            
            for idx, (_, player) in enumerate(team_data.iterrows()):
                col_idx = idx % 2
                with player_cols[col_idx]:
                    
                    status_cls = get_status_style(player['status'])
                    photo_url = player['player_photo'] if player['player_photo'] else "https://a.espncdn.com/combiner/i?img=/i/headshots/nophoto.png"
                    injury_date_formatted = format_injury_date(player['date'])
                    
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
                            <span class="injury-date">📅 Updated: {injury_date_formatted}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

if __name__ == "__main__":
    st.set_page_config(page_title="NBA Injury Report", layout="wide", page_icon="🏀")
    render_injury_page()
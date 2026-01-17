import streamlit as st
import pandas as pd
from services.espn_api import get_active_players_stats
from datetime import datetime

# --- TEAM MAP ---
TEAM_MAP = {
    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
    'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
    'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
    'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
    'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
    'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
    'NOP': 'New Orleans Pelicans', 'NYK': 'New York Knicks', 'OKC': 'Oklahoma City Thunder',
    'ORL': 'Orlando Magic', 'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs',
    'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards'
}

WEIGHTS = {"PTS": 1, "REB": 1.2, "AST": 1.5, "STL": 3, "BLK": 3, "TO": -1, "3Pts": 1}

def calculate_avg_fp(df):
    """Calculate average fantasy points per player"""
    avg_stats = df[['PTS', 'REB', 'AST', 'STL', 'BLK', '3Pts', 'TO']].mean()
    return (
        avg_stats['PTS'] * WEIGHTS['PTS'] +
        avg_stats['REB'] * WEIGHTS['REB'] +
        avg_stats['AST'] * WEIGHTS['AST'] +
        avg_stats['STL'] * WEIGHTS['STL'] +
        avg_stats['BLK'] * WEIGHTS['BLK'] +
        avg_stats['3Pts'] * WEIGHTS['3Pts'] +
        avg_stats['TO'] * WEIGHTS['TO']
    )

def render_trade_analyzer_page():
    st.set_page_config(layout="wide", page_title="NBA Trade Machine", initial_sidebar_state="collapsed")

    st.markdown("""
        <style>
        /* Streamlit header gizle */
        header {visibility: hidden;}
        
        /* Background image alanı */
        .stApp {
            background-image: url('https://wallpapercave.com/wp/wp3402220.jpg');
            background-size: cover;
            background-attachment: fixed;
            background-position: center;
            
        }
        
        .roster-card {
            background-color: rgba(255,255,255,0.08);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            transition: all 0.2s;
        }
        .roster-card:hover {
            background-color: rgba(255,255,255,0.12);
        }
        .info-box {
            background-color: rgba(59, 130, 246, 0.1);
            border-left: 4px solid #3b82f6;
            padding: 12px;
            border-radius: 4px;
            margin: 16px 0;
        }
        .stat-comparison {
            display: flex;
            align-items: center;
            margin: 10px 0;
            padding: 8px;
            border-radius: 6px;
            background-color: rgba(255,255,255,0.05);
        }
        .stat-label {
            width: 80px;
            font-weight: bold;
            text-align: center;
        }
        .stat-bar-container {
            flex: 1;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .stat-bar {
            height: 25px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 0.85em;
            transition: all 0.3s;
        }
        .team-a-bar {
            background: linear-gradient(90deg, #3b82f6, #60a5fa);
            justify-content: flex-end;
            padding-right: 8px;
        }
        .team-b-bar {
            background: linear-gradient(90deg, #f87171, #ef4444);
            justify-content: flex-start;
            padding-left: 8px;
        }
        .winner-badge {
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: bold;
            margin-left: 8px;
        }
        .badge-a {
            background-color: #3b82f6;
            color: white;
        }
        .badge-b {
            background-color: #ef4444;
            color: white;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("NBA Trade Analyzer")
    st.markdown("Compare fantasy value of potential trades and see who wins the deal")
    
    # Initialize session state
    for k in ["cached_data", "team_a_selected", "team_b_selected", "prev_side_a", "prev_side_b"]:
        if k not in st.session_state:
            st.session_state[k] = [] if "selected" in k or "prev" in k else {}

    # Settings section
    with st.expander("Settings - Choose Your Stats Period", expanded=False):
        st.markdown("Select which time period to use for player statistics:")
        period = st.selectbox(
            "Stats Period",
            ["Season Average", "Last 15 Days", "Last 30 Days"],
            help="Recent performance (15/30 days) or full season averages"
        )
        st.info("Tip: Use recent stats to capture hot streaks or slumps, season average for overall consistency")

    # Load data
    # NBA 2024-25 sezonu 22 Ekim 2025'te başladı
    season_start = datetime(2024, 10, 22)
    days_since_season = (datetime.now() - season_start).days
    
    days_map = {
        "Last 15 Days": 15, 
        "Last 30 Days": 30, 
        "Season Average": max(days_since_season, 1)  # Sezon başından bu yana
    }
    days = days_map[period]
    cache_key = f"data_{period}"  # Cache key'i period'a göre yap

    if cache_key not in st.session_state.cached_data:
        with st.spinner("Loading player statistics..."):
            st.session_state.cached_data[cache_key] = get_active_players_stats(days=days)

    df_players = st.session_state.cached_data[cache_key]
    if df_players.empty:
        st.error("Unable to load player data. Please refresh the page or try again later.")
        return

    df_players['TEAM_FULL'] = df_players['TEAM'].map(TEAM_MAP).fillna(df_players['TEAM'])
    all_teams = ["All Teams"] + sorted(df_players['TEAM_FULL'].unique().tolist())

    def render_trade_side(side_key, title, state_key, other_state_key, color):
        st.markdown(f"### {title}")
        box = st.container(border=True)

        with box:
            # Team filter with better label
            team_filter = st.selectbox(
                "Filter players by team (optional)",
                all_teams,
                key=f"filter_{side_key}",
                help="Narrow down the player list to a specific team"
            )

            # Filter players
            filtered = df_players if team_filter == "All Teams" else df_players[df_players['TEAM_FULL'] == team_filter]
            filtered_players = [p for p in filtered['PLAYER'].tolist() if p not in st.session_state[other_state_key]]

            current = st.session_state[state_key]
            options = sorted(set(filtered_players + current))

            # Player selection with better label
            selected = st.multiselect(
                "Select players for this side of the trade",
                options=options,
                default=current,
                key=f"select_{side_key}",
                help="Search by typing a player's name, then click to add"
            )

            # Toast notifications for changes
            prev = st.session_state[f"prev_{side_key}"]
            if set(selected) - set(prev):
                st.toast("Player added to trade", icon="✅")
            if set(prev) - set(selected):
                st.toast("Player removed from trade", icon="ℹ️")

            st.session_state[state_key] = selected
            st.session_state[f"prev_{side_key}"] = selected

            # Show preview stats
            if selected:
                fp_preview = calculate_avg_fp(df_players[df_players['PLAYER'].isin(selected)])
                st.markdown(f"**Average Fantasy Points: {fp_preview:.1f}** per player")
                st.caption(f"{len(selected)} player{'s' if len(selected) != 1 else ''} selected")
            else:
                st.info("Start by selecting players above")

            # Display selected players
            if selected:
                st.markdown("---")
                st.markdown("**Players in this trade:**")
                
                for p in selected:
                    d = df_players[df_players['PLAYER'] == p].iloc[0]
                    team = d.get("TEAM", "")
                    pos = d.get("POS") or d.get("POSITION") or "—"
                    
                    # Show key stats inline
                    pts = d.get("PTS", 0)
                    reb = d.get("REB", 0)
                    ast = d.get("AST", 0)
                    
                    st.markdown(
                        f"<div class='roster-card' style='border-left:4px solid {color}'>"
                        f"<div><b>{p}</b> <span style='color:#aaa'>({team} – {pos})</span></div>"
                        f"<div style='color:#aaa; font-size:0.9em; margin-top:4px'>"
                        f"{pts:.1f} PTS · {reb:.1f} REB · {ast:.1f} AST"
                        f"</div>"
                        "</div>",
                        unsafe_allow_html=True
                    )

        return selected

    # Instructions for first-time users
    if not st.session_state.team_a_selected and not st.session_state.team_b_selected:
        st.markdown(
            "<div class='info-box'>"
            "<b>How to use:</b><br>"
            "1. Select players for Team A (who receives these players)<br>"
            "2. Select players for Team B (who receives these players)<br>"
            "3. See instant analysis of who wins the trade based on average fantasy value per player"
            "</div>",
            unsafe_allow_html=True
        )

    # Two-column layout for the trade sides
    st.markdown("---")
    c1, c2 = st.columns(2, gap="large")

    with c1:
        side_a = render_trade_side(
            "side_a", 
            "Team A Receives",
            "team_a_selected", 
            "team_b_selected", 
            "#3b82f6"
        )

    with c2:
        side_b = render_trade_side(
            "side_b", 
            "Team B Receives",
            "team_b_selected", 
            "team_a_selected", 
            "#ef4444"
        )

    # Show analysis only when both sides have players
    if not side_a or not side_b:
        st.markdown("---")
        missing = []
        if not side_a:
            missing.append("Team A")
        if not side_b:
            missing.append("Team B")
        
        st.info(f"Next step: Add at least one player to {' and '.join(missing)} to see the trade analysis")
        return

    # Analysis function
    def analyze(players):
        df = df_players[df_players['PLAYER'].isin(players)].copy()
        avg_fp = calculate_avg_fp(df)
        avg_stats = df[['PTS', 'REB', 'AST', 'STL', 'BLK', '3Pts', 'TO']].mean()
        return df, avg_fp, avg_stats

    df_a, fp_a, avg_a = analyze(side_a)
    df_b, fp_b, avg_b = analyze(side_b)

    diff = fp_a - fp_b
    confidence = min(100, abs(diff) * 10)

    # Trade results section
    st.markdown("---")
    with st.container(border=True):
        st.markdown("## Trade Analysis Results")
        st.caption("Based on average stats per player")
        
        # Metrics row
        r1, r2, r3 = st.columns([1, 2, 1])
        
        with r1:
            st.metric(
                "Team A Avg FP", 
                f"{fp_a:.1f}",
                delta=f"{diff:.1f}" if diff != 0 else None,
                delta_color="normal" if diff > 0 else "inverse"
            )
        
        with r3:
            st.markdown(
                f"""
                <div style="text-align: right;">
                    <div style="color: rgba(255, 255, 255, 0.6); font-size: 0.875rem;">Team B Avg FP</div>
                    <div style="font-size: 2.25rem; font-weight: 600; line-height: 1.2;">{fp_b:.1f}</div>
                    <div style="color: {'rgb(34, 197, 94)' if diff > 0 else 'rgb(239, 68, 68)'}; font-size: 0.875rem;">
                        {'↓' if diff > 0 else '↑'} {abs(diff):.1f}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        # Winner announcement
        with r2:
            if abs(diff) < 2:
                st.success("FAIR TRADE")
                st.caption("Both teams get similar average value")
            elif diff > 0:
                st.success(f"TEAM A WINS")
                st.caption(f"{diff:.1f} more avg fantasy points per player")
            else:
                st.error(f"TEAM B WINS")
                st.caption(f"{abs(diff):.1f} more avg fantasy points per player")

        # Confidence indicator
        st.markdown("**Trade Confidence Score:**")
        st.progress(confidence / 100, text=f"{confidence:.0f}% confident in this analysis")
        st.caption("Based on average fantasy points per player. Does not include salaries, contracts, or team fit.")

    # Visual stat comparison
    st.markdown("---")
    st.markdown("### Average Stats Comparison")
    st.caption("Visual breakdown showing which team wins each statistical category")
    
    stats_to_compare = [
        ('PTS', 'Points', False),
        ('REB', 'Rebounds', False),
        ('AST', 'Assists', False),
        ('STL', 'Steals', False),
        ('BLK', 'Blocks', False),
        ('3Pts', '3-Pointers', False),
        ('TO', 'Turnovers', True)  # True means lower is better
    ]
    
    for stat_key, stat_name, lower_is_better in stats_to_compare:
        val_a = avg_a[stat_key]
        val_b = avg_b[stat_key]
        
        # Determine winner (accounting for turnovers where lower is better)
        if lower_is_better:
            team_a_wins = val_a < val_b
            diff_val = val_b - val_a  # For turnovers, show how much better (lower)
        else:
            team_a_wins = val_a > val_b
            diff_val = val_a - val_b
        
        # Calculate bar widths (max 50% each side)
        max_val = max(abs(val_a), abs(val_b))
        if max_val > 0:
            width_a = (abs(val_a) / max_val) * 50
            width_b = (abs(val_b) / max_val) * 50
        else:
            width_a = width_b = 0
        
        # Create the comparison bar
        st.markdown(
            f"""
            <div class='stat-comparison'>
                <div class='stat-label'>{stat_name}</div>
                <div class='stat-bar-container'>
                    <div style='flex: 1; text-align: right;'>
                        <div class='stat-bar team-a-bar' style='width: {width_a}%; margin-left: auto;'>
                            {val_a:.1f}
                        </div>
                    </div>
                    <div style='width: 60px; text-align: center; font-weight: bold;'>
                        {"A" if team_a_wins else "B"}
                    </div>
                    <div style='flex: 1;'>
                        <div class='stat-bar team-b-bar' style='width: {width_b}%;'>
                            {val_b:.1f}
                        </div>
                    </div>
                </div>
                <div style='width: 100px; text-align: center;'>
                    <span class='winner-badge {"badge-a" if team_a_wins else "badge-b"}'>
                        {"+" if not lower_is_better else "-"}{abs(diff_val):.1f}
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Detailed stats tables
    st.markdown("---")
    st.markdown("### Individual Player Stats")
    cols = ['PLAYER', 'PTS', 'REB', 'AST', 'STL', 'BLK', '3Pts', 'TO']
    
    t1, t2 = st.columns(2, gap="large")

    with t1:
        st.markdown("**Team A Players**")
        st.dataframe(
            df_a[cols], 
            use_container_width=True, 
            hide_index=True
        )
        st.caption(f"Average: {fp_a:.1f} FP per player ({len(side_a)} players)")

    with t2:
        st.markdown("**Team B Players**")
        st.dataframe(
            df_b[cols], 
            use_container_width=True, 
            hide_index=True
        )
        st.caption(f"Average: {fp_b:.1f} FP per player ({len(side_b)} players)")

    # Footer tips
    st.markdown("---")
    with st.expander("Tips for Better Trade Analysis"):
        st.markdown("""
        - **Average FP** = Total fantasy points divided by number of players
        - This ensures fair comparison even when trading different numbers of players (e.g., 2-for-1 trades)
        - Blue badge = Team A wins that stat category
        - Red badge = Team B wins that stat category
        - For turnovers (TO), **lower is better**
        - Consider recent form vs season averages based on your league
        - This tool focuses on fantasy value only - real NBA trades consider salaries, fit, and team needs
        """)

if __name__ == "__main__":
    render_trade_analyzer_page()
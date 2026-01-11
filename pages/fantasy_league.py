import streamlit as st
import pandas as pd
from services.selenium_scraper import scrape_league_standings, scrape_matchups

# ---------------- CONFIG & CSS ----------------

def apply_custom_style():
    background_url = "https://wallpaper-house.com/data/out/12/wallpaper2you_489438.jpg" 
    
    st.markdown(f"""
    <style>
        /* --- HEADER GİZLEME VE ALAN AYARLARI --- */
        
        header[data-testid="stHeader"] {{
            visibility: hidden;
            display: none;
        }}
        
        .block-container {{
            padding-top: 2rem !important;
        }}
        
        footer {{
            visibility: hidden;
            display: none;
        }}

        /* --- MEVCUT TASARIM AYARLARI --- */
        
        .stApp {{
            background-image: url("{background_url}");
            background-attachment: fixed;
            background-size: cover;
        }}
        .stDataFrame, .stContainer, div[data-testid="stExpander"] {{
            background-color: rgba(15, 23, 42, 0.90); 
            border-radius: 4px;
            border: 1px solid #334155;
        }}
        h1, h2, h3, h4, h5, h6, p, span, div, label {{
            color: #e2e8f0 !important;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        thead tr th {{
            background-color: #0f172a !important;
            color: #94a3b8 !important;
            border-bottom: 2px solid #334155;
            text-align: center !important;
        }}
        tbody tr td {{
            color: #f8fafc !important;
            text-align: center !important;
        }}
        div[data-baseweb="select"] > div {{
            background-color: #1e293b;
            color: white;
            border-color: #475569;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 10px;
        }}
        .stTabs [data-baseweb="tab"] {{
            background-color: rgba(30, 41, 59, 0.9);
            border: 1px solid #475569;
            color: #cbd5e1;
            padding: 10px 20px;
        }}
        .stTabs [aria-selected="true"] {{
            background-color: #2563eb !important;
            color: white !important;
            border-bottom: none;
        }}
        button[kind="primary"] {{
            background-color: #2563eb;
            color: white;
            border: none;
            transition: 0.3s;
        }}
        button[kind="primary"]:hover {{
            background-color: #1d4ed8;
        }}
        
        /* --- LİSTE TASARIMI (SVG İkonlu) --- */
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
            transform: translateX(4px);
        }}
        .result-badge {{
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            line-height: 1;
        }}
        .result-badge svg {{
            width: 16px;
            height: 16px;
        }}
        
        /* Time filter badge */
        .time-badge {{
            display: inline-block;
            background: rgba(37, 99, 235, 0.2);
            border: 1px solid #2563eb;
            color: #60a5fa;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 1px;
            margin-left: 10px;
        }}
    </style>
    """, unsafe_allow_html=True)

# ---------------- YARDIMCI FONKSİYONLAR ----------------

def clean_stat_value(val):
    try:
        if isinstance(val, (int, float)): return float(val)
        val = str(val).strip()
        if val == '--': return 0.0
        if '%' in val: return float(val.replace('%', ''))
        return float(val)
    except: return 0.0

def normalize_column_names(df):
    mapping = {'3PM': '3PTM', 'ThreePM': '3PTM', 'STL': 'ST', 'Steals': 'ST', 'TOV': 'TO', 'Turnovers': 'TO', 'BLK': 'BLK', 'Blocks': 'BLK', 'FGM': 'FG%', 'FTM': 'FT%'}
    return df.rename(columns=mapping)

def get_stat_val(stats, key):
    if key in stats: return stats[key]
    mapping = {'3PTM': ['3PM', '3PTM'], 'ST': ['STL', 'ST'], 'TO': ['TOV', 'TO']}
    if key in mapping:
        for possible_key in mapping[key]:
            if possible_key in stats: return stats[possible_key]
    return 0

# --- ROTO HESAPLAMASI ---
def calculate_roto_score(matchups):
    data = []
    for m in matchups:
        h_stats = m['home_team'].get('stats', {}).copy(); h_stats['Team'] = m['home_team']['name']; data.append(h_stats)
        a_stats = m['away_team'].get('stats', {}).copy(); a_stats['Team'] = m['away_team']['name']; data.append(a_stats)
    if not data: return None, None
    df = pd.DataFrame(data)
    df = normalize_column_names(df)
    target_cols = ['Team', 'FG%', 'FT%', '3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO']
    for col in target_cols:
        if col not in df.columns: df[col] = 0.0
    df = df[target_cols]
    stat_cols = [c for c in target_cols if c != 'Team']
    for col in stat_cols: df[col] = df[col].apply(clean_stat_value)
    points_df = df[['Team']].copy()
    for col in stat_cols:
        if col == 'TO': points_df[col] = df[col].rank(ascending=False, method='min')
        else: points_df[col] = df[col].rank(ascending=True, method='min')
    points_df['Total Score'] = points_df[stat_cols].sum(axis=1)
    points_df = points_df.sort_values('Total Score', ascending=False).reset_index(drop=True)
    df_sorted = df.set_index('Team').loc[points_df['Team']].reset_index()
    return df_sorted, points_df

# --- H2H SİMÜLASYONU (Detaylı) ---
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
            if team_a['name'] == team_b['name']: continue
            w, l, t = compare_teams_detailed(team_a['stats'], team_b['stats'])
            total_wins += w; total_losses += l; total_ties += t
            if w > l: res = "WIN"
            elif l > w: res = "LOSS"
            else: res = "TIE"
            match_details.append({"opponent": team_b['name'], "record": f"{w}-{l}-{t}", "result": res})
        total_cats = total_wins + total_losses + total_ties
        win_pct = total_wins / total_cats if total_cats > 0 else 0
        sim_results.append({
            "team": team_a['name'], "total_wins": total_wins, "total_losses": total_losses, "win_pct": win_pct,
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

# ---------------- ANA SAYFA ----------------

def render_fantasy_league_page():
    st.set_page_config(page_title="Pro Fantasy Analytics", layout="wide", initial_sidebar_state="expanded")
    apply_custom_style()

    # --- SESSION STATE INITIALIZATION ---
    if 'matchups' not in st.session_state:
        st.session_state['matchups'] = None
    if 'df_standings' not in st.session_state:
        st.session_state['df_standings'] = None
    if 'last_filter' not in st.session_state:
        st.session_state['last_filter'] = None
    if 'fantasy_league_id' not in st.session_state:
        st.session_state['fantasy_league_id'] = None

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown("### CONFIGURATION")
        league_input = st.text_input("LEAGUE ID", value="987023001")
        
        # URL'den ID ayıklama
        league_id = league_input.split("leagueId=")[1].split("&")[0] if "leagueId=" in league_input else league_input.strip()
        
        st.markdown("---")
        st.markdown("### TIME PERIOD")
        st.caption("⚡ Değiştirdiğiniz anda veri otomatik güncellenir")
        
        time_filter = st.radio(
            "Select Data Range:",
            options=["week", "month", "season"],
            format_func=lambda x: {"week": "📅 Current Week", "month": "📊 Last Month", "season": "🏆 Full Season"}[x],
            key="time_filter_radio"
        )
        
        st.markdown("---")
        load_btn = st.button("INITIALIZE / REFRESH ALL", type="primary", use_container_width=True)

    # --- VERİ YÜKLEME MANTIĞI ---
    # 1. Butona basıldıysa
    # 2. VEYA Filtre değiştiyse (ve halihazırda yüklü veri varsa)
    filter_changed = time_filter != st.session_state['last_filter']
    should_fetch = load_btn or (filter_changed and st.session_state['matchups'] is not None)

    if should_fetch and league_id:
        with st.spinner(f"CONNECTING TO ESPN: {time_filter.upper()} DATA..."):
            try:
                # Standings (Puan Durumu) sadece ilk yüklemede veya butona basınca çekilir
                if st.session_state['df_standings'] is None or load_btn:
                    st.session_state['df_standings'] = scrape_league_standings(int(league_id))
                
                # Matchup verisi her filtre değişiminde çekilir
                new_matchups = scrape_matchups(int(league_id), time_filter)
                
                if new_matchups:
                    st.session_state['matchups'] = new_matchups
                    st.session_state['last_filter'] = time_filter
                    st.session_state['fantasy_league_id'] = league_id
                    st.rerun() # UI'ı yeni veriyle tazelemek için
                else:
                    st.warning("No matchup data found for this period.")
                    
            except Exception as e:
                st.error(f"DATA FETCH ERROR: {str(e)}")

    # --- ANA PANEL GÖRÜNTÜLEME ---
    if st.session_state['matchups'] is not None:
        # Üst Bilgi Barı
        c1, c2 = st.columns([3, 1])
        with c1:
            st.title("FANTASY LEAGUE ANALYTICS")
            current_f = st.session_state.get('last_filter', 'week')
            filter_label = {"week": "CURRENT WEEK", "month": "LAST MONTH", "season": "FULL SEASON"}[current_f]
            st.markdown(f"<div style='color: #94a3b8; margin-top: -15px; margin-bottom: 20px;'>ADVANCED DATA INTELLIGENCE // 9-CAT <span class='time-badge'>{filter_label}</span></div>", unsafe_allow_html=True)

        tab1, tab2, tab3, tab4 = st.tabs(["📊 STANDINGS", "⚔️ MATCHUPS", "🔥 POWER RANK", "📈 ROTO SIM"])

        with tab1:
            if st.session_state['df_standings'] is not None:
                st.dataframe(st.session_state['df_standings'], use_container_width=True, hide_index=True)
            else:
                st.info("Standings data not loaded.")

        with tab2:
            matchups = st.session_state['matchups']
            for match in matchups:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([1, 0.2, 1])
                    with col1:
                        st.markdown(f"<h3 style='text-align:right; margin:0'>{match['away_team']['name']}</h3>", unsafe_allow_html=True)
                        st.markdown(f"<h1 style='text-align:right; color:#3b82f6; margin:0'>{match['away_score']}</h1>", unsafe_allow_html=True)
                    with col2: 
                        st.markdown("<h3 style='text-align:center; color:#64748b; margin-top:15px;'>VS</h3>", unsafe_allow_html=True)
                    with col3:
                        st.markdown(f"<h3 style='text-align:left; margin:0'>{match['home_team']['name']}</h3>", unsafe_allow_html=True)
                        st.markdown(f"<h1 style='text-align:left; color:#ef4444; margin:0'>{match['home_score']}</h1>", unsafe_allow_html=True)

        with tab3:
            st.markdown("### ALL-PLAY-ALL SIMULATION (H2H)")
            sim_data = run_h2h_simulation_detailed(st.session_state['matchups'])
            
            summary_df = pd.DataFrame(sim_data)[['team', 'total_wins', 'total_losses', 'win_pct']]
            summary_df.columns = ["Team", "Cat Wins", "Cat Losses", "Win %"]
            st.dataframe(summary_df.style.background_gradient(subset=['Win %'], cmap="Blues"), use_container_width=True, hide_index=True)
            
            st.divider()
            st.subheader("🕵️ Detailed Matchup Analysis")
            selected_team = st.selectbox("Select a team to analyze:", [t['team'] for t in sim_data])
            
            if selected_team:
                team_stats = next(t for t in sim_data if t['team'] == selected_team)
                icon_win = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="green" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor" style="display:inline; margin-right:5px;"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>"""
                icon_loss = """<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="red" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor" style="display:inline; margin-right:5px;"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>"""
                
                for detail in team_stats['details']:
                    icon = icon_win if detail['result'] == "WIN" else icon_loss
                    st.markdown(f"""
                        <div class="matchup-row" style="border-left: 4px solid {'#22c55e' if detail['result']=='WIN' else '#ef4444'};">
                            <span>{icon} <b>VS</b> {detail['opponent']}</span>
                            <span style="font-family:monospace;">{detail['record']} ({detail['result']})</span>
                        </div>
                    """, unsafe_allow_html=True)

        with tab4:
            raw_df, points_df = calculate_roto_score(st.session_state['matchups'])
            if raw_df is not None:
                st.markdown("#### SCORING TABLE (POINTS 1-10)")
                st.dataframe(rename_display_columns(points_df).style.background_gradient(cmap="Greens"), use_container_width=True, hide_index=True)
    else:
        st.info("Please enter your League ID and click 'Initialize Data Fetch' to start.")

if __name__ == "__main__":
    render_fantasy_league_page()
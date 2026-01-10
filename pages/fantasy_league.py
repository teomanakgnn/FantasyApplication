import streamlit as st
import pandas as pd
from services.selenium_scraper import scrape_league_standings, scrape_matchups

# ---------------- CONFIG & CSS ----------------

def apply_custom_style():
    # Arka plan ve genel stil ayarları
    background_url = "https://wallpaper-house.com/data/out/12/wallpaper2you_489438.jpg" 
    
    st.markdown(f"""
    <style>
        /* --- HEADER GİZLEME VE ALAN AYARLARI --- */
        
        /* Üst Header'ı tamamen gizle */
        header[data-testid="stHeader"] {{
            visibility: hidden;
            display: none;
        }}
        
        /* Sayfa içeriğini biraz yukarı çek (Header gidince boşluk kalmasın) */
        .block-container {{
            padding-top: 2rem !important;
        }}
        
        /* Footer'ı (Made with Streamlit) gizle */
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
        /* Tablo Header */
        thead tr th {{
            background-color: #0f172a !important;
            color: #94a3b8 !important;
            border-bottom: 2px solid #334155;
            text-align: center !important;
        }}
        /* Tablo Hücreleri */
        tbody tr td {{
            color: #f8fafc !important;
            text-align: center !important;
        }}
        /* Selectbox Arka Planı */
        div[data-baseweb="select"] > div {{
            background-color: #1e293b;
            color: white;
            border-color: #475569;
        }}
        /* Sekmeler */
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
    # Toolbar modunu minimal yaparak da gizlemeye yardımcı olabiliriz ama CSS en garantisidir
    st.set_page_config(page_title="Pro Fantasy Analytics", layout="wide", initial_sidebar_state="expanded")
    apply_custom_style()

    # Üst Bar
    c1, c2 = st.columns([3, 1])
    with c1:
        st.title("FANTASY LEAGUE ANALYTICS")
        st.markdown("<div style='color: #94a3b8; margin-top: -15px; margin-bottom: 20px;'>ADVANCED DATA INTELLIGENCE // 9-CAT</div>", unsafe_allow_html=True)

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown("### CONFIGURATION")
        league_input = st.text_input("LEAGUE ID", value="987023001")
        if "leagueId=" in league_input: league_id = league_input.split("leagueId=")[1].split("&")[0]
        else: league_id = league_input.strip()
        st.markdown("---")
        load_data = st.button("INITIALIZE DATA FETCH", type="primary", use_container_width=True)
        
    # --- VERİ YÜKLEME ---
    if load_data and league_id:
        st.session_state.fantasy_league_id = league_id
        with st.spinner("ESTABLISHING CONNECTION TO ESPN SERVERS..."):
            try:
                df_standings = scrape_league_standings(int(league_id))
                matchups = scrape_matchups(int(league_id))
                st.session_state['df_standings'] = df_standings
                st.session_state['matchups'] = matchups
            except Exception as e: st.error(f"DATA FETCH ERROR: {str(e)}")

    # --- GÖRÜNTÜLEME ---
    df_standings = st.session_state.get('df_standings')
    matchups = st.session_state.get('matchups')

    if df_standings is not None or matchups is not None:
        
        tab1, tab2, tab3, tab4 = st.tabs(["LEAGUE STANDINGS", "WEEKLY MATCHUPS", "H2H POWER RANK", "ROTO SIMULATION"])

        # TAB 1: STANDINGS
        with tab1:
            if df_standings is not None and not df_standings.empty:
                st.dataframe(df_standings, use_container_width=True, hide_index=True)
            else: st.info("NO DATA AVAILABLE")

        # TAB 2: MATCHUPS
        with tab2:
            if matchups:
                for match in matchups:
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([1, 0.2, 1])
                        with col1:
                            st.markdown(f"<h3 style='text-align:right; margin:0'>{match['away_team']['name']}</h3>", unsafe_allow_html=True)
                            st.markdown(f"<h1 style='text-align:right; color:#3b82f6; margin:0'>{match['away_score']}</h1>", unsafe_allow_html=True)
                        with col2: st.markdown("<h3 style='text-align:center; color:#64748b'>VS</h3>", unsafe_allow_html=True)
                        with col3:
                            st.markdown(f"<h3 style='text-align:left; margin:0'>{match['home_team']['name']}</h3>", unsafe_allow_html=True)
                            st.markdown(f"<h1 style='text-align:left; color:#ef4444; margin:0'>{match['home_score']}</h1>", unsafe_allow_html=True)

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
                
                # --- DETAYLI ANALİZ (SVG İkonlu) ---
                st.subheader("🕵️ Detailed Matchup Analysis")
                selected_team = st.selectbox("Select a team to analyze:", [t['team'] for t in sim_data])
                
                if selected_team:
                    team_stats = next(t for t in sim_data if t['team'] == selected_team)
                    
                    st.markdown(f"##### Results for {selected_team}")
                    
                    # SVG İkonlar
                    icon_win = """<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>"""
                    icon_loss = """<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>"""
                    icon_tie = """<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14" /></svg>"""
                    
                    for detail in team_stats['details']:
                        if detail['result'] == "WIN":
                            border_color = "#22c55e"; badge_bg = "rgba(34, 197, 94, 0.2)"; badge_text = "#22c55e"; icon = icon_win
                        elif detail['result'] == "LOSS":
                            border_color = "#ef4444"; badge_bg = "rgba(239, 68, 68, 0.2)"; badge_text = "#ef4444"; icon = icon_loss
                        else:
                            border_color = "#94a3b8"; badge_bg = "rgba(148, 163, 184, 0.2)"; badge_text = "#cbd5e1"; icon = icon_tie
                            
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

        # TAB 4: ROTO SIMULATION
        with tab4:
            if matchups:
                st.markdown("### ROTISSERIE (ROTO) ANALYSIS")
                raw_df, points_df = calculate_roto_score(matchups)
                
                if raw_df is not None:
                    st.markdown("#### RAW STATS")
                    format_dict = {}
                    for col in ['FG%', 'FT%']:
                        if col in raw_df.columns: format_dict[col] = "{:.3f}"
                    for col in ['3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO']:
                        if col in raw_df.columns: format_dict[col] = "{:.0f}"

                    raw_df_display = rename_display_columns(raw_df)
                    st.dataframe(raw_df_display.style.format(format_dict), use_container_width=True, hide_index=True)   
                    st.divider()
                    st.markdown("#### SCORING TABLE (POINTS 1-10)")
                    points_df_display = rename_display_columns(points_df)

                    st.dataframe(
                        points_df_display
                        .style
                        .background_gradient(subset=['Total Score'], cmap="Greens")
                        .format("{:.0f}", subset=points_df_display.columns.drop('Team')),
                        use_container_width=True,
                        hide_index=True
                    )

if __name__ == "__main__":
    render_fantasy_league_page()
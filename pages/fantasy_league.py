import streamlit as st
import pandas as pd
from services.selenium_scraper import scrape_league_standings, scrape_matchups, scrape_team_rosters

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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: 1px solid #8b5cf6;
            color: #fff;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.2px;
            margin-left: 12px;
            box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
            text-transform: uppercase;
        }}
        
        .pro-time-section {{
            background: rgba(30, 41, 59, 0.6);  
            border: 1px solid #334155;      
            border-radius: 12px;
            padding: 20px;
            margin: 20px 0;
        }}

        .pro-badge {{
            background: #334155;      /* slate */
            color: #e2e8f0;
            box-shadow: none;
        }}

        
        .pro-badge::before {{
            content: '⚡';
            font-size: 12px;
        }}
        
        .time-option {{
            background: rgba(30, 41, 59, 0.6);
            border: 2px solid #475569;
            border-radius: 8px;
            padding: 12px 16px;
            margin: 8px 0;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        
        .time-option:hover {{
            background: rgba(37, 99, 235, 0.2);
            border-color: #60a5fa;
            transform: translateX(4px);
        }}
        
        .time-option.selected {{
            background: linear-gradient(135deg, rgba(37, 99, 235, 0.3) 0%, rgba(124, 58, 237, 0.3) 100%);
            border-color: #8b5cf6;
            box-shadow: 0 0 20px rgba(139, 92, 246, 0.3);
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

# --- TRADE ANALYZER FONKSİYONLARI ---
def calculate_team_totals(roster):
    """Bir takımın tüm oyuncularının toplam istatistiklerini hesaplar"""
    totals = {'FG%': [], 'FT%': [], '3PM': 0, 'PTS': 0, 'REB': 0, 'AST': 0, 'STL': 0, 'BLK': 0, 'TO': 0}
    
    for player in roster:
        stats = player.get('stats', {})
        for cat in ['3PM', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO']:
            val = clean_stat_value(stats.get(cat, 0))
            totals[cat] += val
        
        # Yüzdelik statler için liste tut (ortalama alınacak)
        for pct in ['FG%', 'FT%']:
            val = clean_stat_value(stats.get(pct, 0))
            if val > 0:
                totals[pct].append(val)
    
    # Yüzdeliklerin ortalamasını al
    totals['FG%'] = sum(totals['FG%']) / len(totals['FG%']) if totals['FG%'] else 0
    totals['FT%'] = sum(totals['FT%']) / len(totals['FT%']) if totals['FT%'] else 0
    
    return totals

def display_trade_impact(old_stats, new_stats):
    """Trade öncesi ve sonrası istatistik değişimlerini gösterir"""
    categories = ['FG%', 'FT%', '3PM', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO']
    
    for cat in categories:
        old_val = old_stats.get(cat, 0)
        new_val = new_stats.get(cat, 0)
        
        if cat in ['FG%', 'FT%']:
            diff = new_val - old_val
            diff_str = f"{diff:+.3f}"
        else:
            diff = new_val - old_val
            diff_str = f"{diff:+.1f}"
        
        # TO için ters mantık (düşük iyi)
        if cat == 'TO':
            if diff < 0:
                color = "#22c55e"
                arrow = "⬇️"
            elif diff > 0:
                color = "#ef4444"
                arrow = "⬆️"
            else:
                color = "#94a3b8"
                arrow = "➡️"
        else:
            if diff > 0:
                color = "#22c55e"
                arrow = "⬆️"
            elif diff < 0:
                color = "#ef4444"
                arrow = "⬇️"
            else:
                color = "#94a3b8"
                arrow = "➡️"
        
        st.markdown(f"""
        <div style='display: flex; justify-content: space-between; padding: 8px; background: rgba(30, 41, 59, 0.4); margin: 4px 0; border-radius: 4px;'>
            <span style='font-weight: 600;'>{cat}</span>
            <span style='color: {color}; font-weight: 700;'>{arrow} {diff_str}</span>
        </div>
        """, unsafe_allow_html=True)

def compare_h2h_winner(team_a_stats, team_b_stats):
    """İki takımı H2H formatında karşılaştırır ve kazananı döner"""
    wins_a, wins_b, ties = 0, 0, 0
    cats = ['FG%', 'FT%', '3PM', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TO']
    
    for cat in cats:
        val_a = team_a_stats.get(cat, 0)
        val_b = team_b_stats.get(cat, 0)
        
        if cat == 'TO':
            if val_a < val_b: wins_a += 1
            elif val_a > val_b: wins_b += 1
            else: ties += 1
        else:
            if val_a > val_b: wins_a += 1
            elif val_a < val_b: wins_b += 1
            else: ties += 1
    
    if wins_a > wins_b:
        return f"Team A Wins ({wins_a}-{wins_b}-{ties})"
    elif wins_b > wins_a:
        return f"Team B Wins ({wins_b}-{wins_a}-{ties})"
    else:
        return f"TIE ({wins_a}-{wins_b}-{ties})"

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

    # Üst Bar
    c1, c2 = st.columns([3, 1])
    with c1:
        st.title("FANTASY LEAGUE ANALYTICS")
        
        # Time filter badge gösterimi
        current_filter = st.session_state.get('time_filter', 'week')
        filter_display = {"week": "CURRENT WEEK", "month": "LAST MONTH", "season": "FULL SEASON"}
        st.markdown(f"<div style='color: #94a3b8; margin-top: -15px; margin-bottom: 20px;'>ADVANCED DATA INTELLIGENCE // 9-CAT <span class='time-badge'>{filter_display[current_filter]}</span></div>", unsafe_allow_html=True)

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown("### CONFIGURATION")
        league_input = st.text_input("LEAGUE ID", value="987023001")
        if "leagueId=" in league_input: league_id = league_input.split("leagueId=")[1].split("&")[0]
        else: league_id = league_input.strip()
        
        st.markdown("---")
        
        # PRO TIME PERIOD SECTION
        st.markdown("""
        <div class='pro-time-section'>
            <div style='display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;'>
                <div style='font-size: 15px; font-weight: 700; color: #e2e8f0; letter-spacing: 0.5px;'>TIME PERIOD</div>
                <div class='pro-badge'>PRO</div>
            </div>
            <div style='color: #94a3b8; font-size: 11px; margin-bottom: 12px;'>⚡ Advanced temporal analysis</div>
        </div>
        """, unsafe_allow_html=True)
        
        time_filter = st.radio(
            "Select Data Range:",
            options=["week", "month", "season"],
            format_func=lambda x: {
                "week": "📅 Current Week",
                "month": "🔒 Last Month (PRO)",
                "season": "🔒 Full Season (PRO)"
            }[x],
            index=0,
            key="time_filter_radio",
            disabled=True,
            label_visibility="collapsed"
        )

        # Manuel olarak sadece week set edelim
        time_filter = "week"
        st.session_state['time_filter'] = "week"
        
        st.markdown("---")
        # TEK BUTON: FULL FETCH
        load_data = st.button("🚀 INITIALIZE FULL DATA FETCH", type="primary", use_container_width=True)
        
    # --- VERİ YÜKLEME (TEK SEFERDE HEPSİ) ---
    if load_data and league_id:
        st.session_state.fantasy_league_id = league_id
        st.session_state.last_time_filter = time_filter
        
        with st.spinner("CONNECTING TO ESPN: FETCHING STANDINGS, MATCHUPS AND ROSTERS..."):
            try:
                # 1. STANDINGS
                df_standings = scrape_league_standings(int(league_id))
                st.session_state['df_standings'] = df_standings
                
                # 2. MATCHUPS
                matchups = scrape_matchups(int(league_id), time_filter)
                st.session_state['matchups'] = matchups
                
                # 3. ROSTERS (Buraya taşındı, artık otomatik)
                rosters = scrape_team_rosters(int(league_id))
                st.session_state['rosters'] = rosters

                if not rosters:
                    st.warning("⚠️ Matchups loaded but Rosters returned empty. Check Selenium scraper.")
                else:
                    st.success(f"✅ All data loaded successfully! ({len(rosters)} teams)")
            
            except Exception as e: st.error(f"DATA FETCH ERROR: {str(e)}")
    
    # --- TIME FILTER DEĞİŞİMİNDE OTOMATİK YENİDEN YÜKLEME ---
    if (st.session_state.get('fantasy_league_id') and 
        st.session_state.get('last_time_filter') and 
        st.session_state.get('last_time_filter') != time_filter):
        
        st.session_state.last_time_filter = time_filter
        
        with st.spinner(f"RELOADING DATA FOR {filter_display[time_filter]}..."):
            try:
                league_id = st.session_state.fantasy_league_id
                matchups = scrape_matchups(int(league_id), time_filter)
                st.session_state['matchups'] = matchups
                st.rerun()
            except Exception as e: 
                st.error(f"DATA RELOAD ERROR: {str(e)}")

    # --- GÖRÜNTÜLEME ---
    df_standings = st.session_state.get('df_standings')
    matchups = st.session_state.get('matchups')
    rosters = st.session_state.get('rosters', {})

    if df_standings is not None or matchups is not None:
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["LEAGUE STANDINGS", "WEEKLY MATCHUPS", "H2H POWER RANK", "ROTO SIMULATION", "TRADE ANALYZER"])

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
                selected_team = st.selectbox("Select a team to analyze:", [t['team'] for t in sim_data], key="team_analyzer_selectbox")
                
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
                    
                    # 3PT, STL, TOV sütunlarını integer'a çevir
                    for col in ['3PT', 'STL', 'TOV']:
                        if col in raw_df_display.columns:
                            raw_df_display[col] = raw_df_display[col].astype(float).astype(int)
                    
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
        
        # TAB 5: TRADE ANALYZER
        with tab5:
            if rosters:
                st.markdown("### 🔄 TRADE IMPACT ANALYZER")
                st.markdown("<div style='color: #94a3b8; margin-bottom: 20px;'>Analyze how trading players would affect both teams' category performance</div>", unsafe_allow_html=True)
                
                team_names = sorted(rosters.keys())
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 🔵 Team A")
                    team_a = st.selectbox("Select Team A", team_names, key="team_a_select")
                    
                    if team_a and team_a in rosters:
                        player_names_a = [p['name'] for p in rosters[team_a]]
                        players_a = st.multiselect(
                            "Players Team A gives away:",
                            player_names_a,
                            key="players_a_select"
                        )
                
                with col2:
                    st.markdown("#### 🔴 Team B")
                    team_b = st.selectbox("Select Team B", [t for t in team_names if t != team_a], key="team_b_select")
                    
                    if team_b and team_b in rosters:
                        player_names_b = [p['name'] for p in rosters[team_b]]
                        players_b = st.multiselect(
                            "Players Team B gives away:",
                            player_names_b,
                            key="players_b_select"
                        )
                
                st.markdown("---")
                
                if st.button("⚡ ANALYZE TRADE", type="primary", use_container_width=True):
                    if not players_a or not players_b:
                        st.warning("⚠️ Please select at least one player from each team")
                    else:
                        # Trade analizi
                        team_a_roster = rosters[team_a]
                        team_b_roster = rosters[team_b]
                        
                        # Oyuncuları bul
                        traded_from_a = [p for p in team_a_roster if p['name'] in players_a]
                        traded_from_b = [p for p in team_b_roster if p['name'] in players_b]
                        
                        # Mevcut durumu hesapla
                        current_a_stats = calculate_team_totals(team_a_roster)
                        current_b_stats = calculate_team_totals(team_b_roster)
                        
                        # Trade sonrası durumu hesapla
                        new_roster_a = [p for p in team_a_roster if p['name'] not in players_a] + traded_from_b
                        new_roster_b = [p for p in team_b_roster if p['name'] not in players_b] + traded_from_a
                        
                        new_a_stats = calculate_team_totals(new_roster_a)
                        new_b_stats = calculate_team_totals(new_roster_b)
                        
                        # Değişimleri göster
                        st.markdown("### 📊 TRADE IMPACT SUMMARY")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown(f"#### {team_a}")
                            display_trade_impact(current_a_stats, new_a_stats)
                        
                        with col2:
                            st.markdown(f"#### {team_b}")
                            display_trade_impact(current_b_stats, new_b_stats)
                        
                        st.markdown("---")
                        
                        # H2H karşılaştırma
                        st.markdown("### ⚔️ HEAD-TO-HEAD COMPARISON")
                        
                        current_winner = compare_h2h_winner(current_a_stats, current_b_stats)
                        new_winner = compare_h2h_winner(new_a_stats, new_b_stats)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Before Trade:**")
                            st.markdown(f"<div style='font-size: 24px; font-weight: bold; color: #60a5fa;'>{current_winner}</div>", unsafe_allow_html=True)
                        
                        with col2:
                            st.markdown("**After Trade:**")
                            st.markdown(f"<div style='font-size: 24px; font-weight: bold; color: #22c55e;'>{new_winner}</div>", unsafe_allow_html=True)
                        
            else:
                st.info("📌 Rosters not loaded. Please click 'INITIALIZE FULL DATA FETCH' first.")

if __name__ == "__main__":
    render_fantasy_league_page()
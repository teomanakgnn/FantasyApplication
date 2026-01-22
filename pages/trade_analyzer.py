import streamlit as st
import pandas as pd
from services.espn_api import get_active_players_stats
from datetime import datetime

# --- GÜNCEL PUANLAMA SİSTEMİ ---
BASE_WEIGHTS = {
    "PTS": 0.75, "REB": 0.5, "AST": 0.8, "STL": 1.7, "BLK": 1.6, "TO": -1.5,
    "FGA": -0.9, "FGM": 1.2, "FTA": -0.55, "FTM": 1.1, "3PM": 0.6, 
    "FG%": 0.0, "FT%": 0.0  # Punt için ekstra
}

# --- TEAM MAP ---
TEAM_MAP = {
    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
    'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
    'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
    'GSW': 'Golden State Warriors', 'GS': 'Golden State Warriors',
    'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
    'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
    'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
    'NOP': 'New Orleans Pelicans', 'NO': 'New Orleans Pelicans',
    'NYK': 'New York Knicks', 'NY': 'New York Knicks',
    'OKC': 'Oklahoma City Thunder', 'ORL': 'Orlando Magic', 
    'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 
    'SAS': 'San Antonio Spurs', 'SA': 'San Antonio Spurs',
    'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'UTAH': 'Utah Jazz', 'WSH': 'Washington Wizards'
}

def calculate_avg_fp(df, punt_cats):
    """Calculate average fantasy points with punt categories"""
    weights = BASE_WEIGHTS.copy()
    
    # Punt kategorilerini 0 yap
    for cat in punt_cats:
        if cat == "FG Punt":
            weights["FGM"] = 0.0
            weights["FGA"] = 0.0
        elif cat == "FT Punt":
            weights["FTM"] = 0.0
            weights["FTA"] = 0.0
        elif cat == "TO Punt":
            weights["TO"] = 0.0
    
    available_cols = [col for col in weights.keys() if col in df.columns]
    if not available_cols: return 0.0
    
    avg_stats = df[available_cols].mean()
    score = 0.0
    for category in available_cols:
        score += avg_stats[category] * weights[category]
    return score

def render_trade_analyzer_page():
    st.set_page_config(layout="wide", page_title="NBA Trade Machine", initial_sidebar_state="expanded")

    st.markdown("""
        <style>
        header {visibility: hidden;}
        .stApp {
            background-image: url('https://wallup.net/wp-content/uploads/2016/03/29/318818-basketball-sport-sports-simple.jpg');
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
        .roster-card:hover { background-color: rgba(255,255,255,0.12); }
        .stat-comparison {
            display: flex; align-items: center; margin: 10px 0; padding: 8px;
            border-radius: 6px; background-color: rgba(255,255,255,0.05);
        }
        .stat-label { width: 90px; font-weight: bold; text-align: center; font-size: 0.9em; }
        .stat-bar-container { flex: 1; display: flex; align-items: center; gap: 10px; }
        .stat-bar {
            height: 25px; border-radius: 4px; display: flex; align-items: center;
            justify-content: center; font-weight: bold; font-size: 0.85em; transition: all 0.3s;
        }
        .team-1-bar { background: linear-gradient(90deg, #3b82f6, #60a5fa); justify-content: flex-end; padding-right: 8px; }
        .team-2-bar { background: linear-gradient(90deg, #f97316, #fb923c); justify-content: flex-start; padding-left: 8px; }
        </style>
    """, unsafe_allow_html=True)

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("Scoring System")
        
        # PUNT STRATEGY
        st.subheader("🎯 Punt Strategy")
        punt_cats = st.multiselect(
            "Select categories to punt (ignore)",
            ["FG Punt", "FT Punt", "TO Punt"],
            help="Punted categories will have 0 weight in calculations"
        )
        
        if punt_cats:
            st.info(f"Punting: {', '.join(punt_cats)}")
        
        st.markdown("---")
        st.markdown("**Active Weights:**")
        
        # Aktif ağırlıkları göster
        display_weights = BASE_WEIGHTS.copy()
        for cat in punt_cats:
            if cat == "FG Punt":
                display_weights["FGM"] = 0.0
                display_weights["FGA"] = 0.0
            elif cat == "FT Punt":
                display_weights["FTM"] = 0.0
                display_weights["FTA"] = 0.0
            elif cat == "TO Punt":
                display_weights["TO"] = 0.0
        
        weights_df = pd.DataFrame(list(display_weights.items()), columns=['Stat', 'Weight'])
        weights_df = weights_df[weights_df['Weight'] != 0]  # 0 olanları gösterme
        weights_df = weights_df.sort_values(by='Weight', ascending=False)
        st.dataframe(weights_df, hide_index=True, use_container_width=True)

    st.title("NBA Trade Analyzer")
    st.markdown("Compare fantasy value of potential trades.")
    
    # Session State Başlatma
    for k in ["team_1_players", "team_2_players", "current_period"]:
        if k not in st.session_state:
            st.session_state[k] = [] if "players" in k else None

    # --- SETTINGS ---
    with st.expander("⚙️ Settings - Choose Your Stats Period", expanded=True):
        st.write("Select time period for analysis:")
        period = st.selectbox(
            "Stats Period",
            ["Season Average", "Last 15 Days", "Last 30 Days"],
            index=0,
            help="Select 'Season Average' for long-term value, or 'Last X Days' for current form.",
            key="period_selector"
        )

    # --- DATA LOADING ---
    days_map = {
        "Last 15 Days": (15, False), 
        "Last 30 Days": (30, False), 
        "Season Average": (None, True)
    }
    
    selected_days, use_season = days_map[period]
    
    # Period değişti mi kontrol et (oyuncuları koruyarak)
    if st.session_state.current_period != period:
        st.session_state.current_period = period
        if 'df_players' in st.session_state:
            del st.session_state['df_players']
    
    # Veriyi çek
    if 'df_players' not in st.session_state:
        with st.spinner(f"Loading statistics for {period}..."):
            st.session_state.df_players = get_active_players_stats(
                days=selected_days, 
                season_stats=use_season
            )

    df_players = st.session_state.df_players
    
    if df_players.empty:
        st.error(f"No data found for {period}. Try selecting 'Season Average' or check your connection.")
        return

    # Gerekli sütunları ekle
    for col in ['FGM', 'FGA', 'FTM', 'FTA', '3PM', 'FG%', 'FT%']:
        if col not in df_players.columns:
            if col == '3PM' and '3Pts' in df_players.columns:
                df_players['3PM'] = df_players['3Pts']
            else:
                df_players[col] = 0.0

    # --- DÜZELTME BURADA: Team Verisi Temizleme ---
    # Yardımcı fonksiyon: Eğer veri dict ise içinden 'team' bilgisini al
    def extract_team_abbr(val):
        if isinstance(val, dict):
            return val.get('team', val.get('abbreviation', 'UNK'))
        return str(val)

    # TEAM sütununu temizle (Dict -> String)
    df_players['TEAM'] = df_players['TEAM'].apply(extract_team_abbr)

    # Takım isimlerini eşleştir
    df_players['TEAM_FULL'] = df_players['TEAM'].map(TEAM_MAP).fillna(df_players['TEAM'])
    
    # --- EKSİK OLAN KISIM BURASIYDI ---
    # all_teams değişkenini tanımlıyoruz
    all_teams = ["All Teams"] + sorted(df_players['TEAM_FULL'].unique().tolist())

    # --- RENDER FUNCTION ---
    def render_trade_side(side_id, title, state_key, other_state_key, color):
        st.markdown(f"### {title}")
        box = st.container(border=True)

        with box:
            col_filter, col_select = st.columns([1, 2])
            
            with col_filter:
                team_filter = st.selectbox("Filter Team", all_teams, key=f"filter_{side_id}_{period}")
            
            # Filtreleme
            filtered = df_players if team_filter == "All Teams" else df_players[df_players['TEAM_FULL'] == team_filter]
            
            # Karşı takımın oyuncularını hariç tut
            other_side_players = st.session_state[other_state_key]
            filtered_players = [p for p in filtered['PLAYER'].tolist() if p not in other_side_players]
            
            # Mevcut seçimleri al
            current_selections = st.session_state[state_key]
            
            # Seçenekleri birleştir: filtered + current (tekrarsız)
            all_options = sorted(list(set(filtered_players + current_selections)))

            with col_select:
                selected = st.multiselect(
                    "Select Players", 
                    options=all_options, 
                    default=current_selections, 
                    key=f"select_{side_id}_{period}"  # Period'u key'e ekle
                )

            # State'i güncelle
            st.session_state[state_key] = selected
            
            # Preview Stats
            if selected:
                # Sadece DataFrame'de olan oyuncuları göster
                valid_selected = [p for p in selected if p in df_players['PLAYER'].values]
                
                if valid_selected:
                    fp_preview = calculate_avg_fp(
                        df_players[df_players['PLAYER'].isin(valid_selected)],
                        punt_cats
                    )
                    st.markdown(f"**Avg FP: {fp_preview:.1f}** ({period})")
                    st.markdown("---")
                    
                    for p in valid_selected:
                        player_data = df_players[df_players['PLAYER'] == p]
                        if not player_data.empty:
                            d = player_data.iloc[0]
                            team = d.get("TEAM", "")
                            pts = d.get("PTS", 0)
                            st.markdown(
                                f"<div class='roster-card' style='border-left:4px solid {color}'>"
                                f"<div><b>{p}</b> <span style='color:#aaa'>({team})</span></div>"
                                f"<div style='color:#aaa; font-size:0.9em;'>{pts:.1f} PTS</div>"
                                f"</div>", unsafe_allow_html=True
                            )
                
                # Eğer seçili oyuncular bu period'ta yoksa uyar
                missing = [p for p in selected if p not in df_players['PLAYER'].values]
                if missing:
                    st.warning(f"⚠️ {len(missing)} player(s) not available in {period}: {', '.join(missing[:3])}{'...' if len(missing) > 3 else ''}")
            else:
                st.info("Select players...")

        return selected

    st.markdown("---")
    c1, c2 = st.columns(2, gap="large")

    with c1:
        side_1 = render_trade_side("side_1", "Team 1 Receives", "team_1_players", "team_2_players", "#3b82f6")
    with c2:
        side_2 = render_trade_side("side_2", "Team 2 Receives", "team_2_players", "team_1_players", "#f97316")

    if not side_1 or not side_2:
        st.info("Add players to both sides to compare.")
        return

    # --- ANALYSIS ENGINE ---
    def analyze(players):
        # Sadece mevcut period'ta olan oyuncuları kullan
        valid_players = [p for p in players if p in df_players['PLAYER'].values]
        
        if not valid_players:
            return pd.DataFrame(), 0.0, pd.Series()
        
        df = df_players[df_players['PLAYER'].isin(valid_players)].copy()
        avg_fp = calculate_avg_fp(df, punt_cats)
        numeric_cols = df.select_dtypes(include='number').columns
        avg_stats = df[numeric_cols].mean()
        return df, avg_fp, avg_stats

    df_1, fp_1, avg_1 = analyze(side_1)
    df_2, fp_2, avg_2 = analyze(side_2)
    
    # Eğer her iki taraf da boşsa uyarı ver
    if df_1.empty or df_2.empty:
        st.warning(f"⚠️ Some selected players are not available in {period}. Analysis may be incomplete.")
        if df_1.empty and df_2.empty:
            st.info("No valid players in current period for both teams.")
            return

    diff = fp_1 - fp_2
    confidence = min(100, abs(diff) * 10)

    st.markdown("---")
    with st.container(border=True):
        st.markdown("## ⚖️ Trade Analysis")
        r1, r2, r3 = st.columns([1, 2, 1])
        
        with r1:
            st.metric("Team 1 Avg FP", f"{fp_1:.1f}", delta=f"{diff:.1f}" if diff != 0 else None)
        
        with r3:
            st.markdown(f"""
                <div style="text-align: right;">
                    <div style="color: rgba(255, 255, 255, 0.6); font-size: 0.875rem;">Team 2 Avg FP</div>
                    <div style="font-size: 2.25rem; font-weight: 600;">{fp_2:.1f}</div>
                    <div style="color: {'#4ade80' if diff > 0 else '#f87171'}; font-size: 0.875rem;">
                        {'↓' if diff > 0 else '↑'} {abs(diff):.1f}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with r2:
            if abs(diff) < 2:
                st.success("FAIR TRADE")
            elif diff > 0:
                st.success(f"TEAM 1 WINS")
                st.caption(f"+{diff:.1f} advantage")
            else:
                st.error(f"TEAM 2 WINS")
                st.caption(f"+{abs(diff):.1f} advantage")
            st.progress(confidence / 100)

    # --- VISUAL COMPARISON ---
    st.markdown("### Stat Breakdown")
    stats_config = [
        ('PTS', 'Points', False), ('REB', 'Rebs', False), ('AST', 'Asts', False),
        ('STL', 'Stls', False), ('BLK', 'Blks', False), ('3PM', '3PM', False), ('TO', 'TO', True)
    ]
    
    for key, label, lower_better in stats_config:
        if key not in avg_1: continue
        v1, v2 = avg_1[key], avg_2[key]
        t1_wins = v1 < v2 if lower_better else v1 > v2
        max_val = max(abs(v1), abs(v2))
        w1 = (abs(v1)/max_val)*50 if max_val else 0
        w2 = (abs(v2)/max_val)*50 if max_val else 0
        
        st.markdown(f"""
            <div class='stat-comparison'>
                <div class='stat-label'>{label}</div>
                <div class='stat-bar-container'>
                    <div style='flex:1; text-align:right;'><div class='stat-bar team-1-bar' style='width:{w1}%; margin-left:auto;'>{v1:.1f}</div></div>
                    <div style='width:40px; text-align:center; font-weight:bold; color:#888;'>{"1" if t1_wins else "2"}</div>
                    <div style='flex:1;'><div class='stat-bar team-2-bar' style='width:{w2}%;'>{v2:.1f}</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # --- DETAILED TABLE (COMBINED SHOOTING STATS) ---
    st.markdown("### Detailed Player Stats")
    
    c_t1, c_t2 = st.columns(2)
    
    for idx, (df_side, col_container, title) in enumerate([
        (df_1, c_t1, "Team 1 Receives"),
        (df_2, c_t2, "Team 2 Receives")
    ]):
        with col_container:
            st.markdown(f"**{title}:**")
            
            # Display kolonları
            display_cols = ['PLAYER', 'PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'TO']
            display_df = df_side[display_cols].copy()
            
            # FG ve FT sütunlarını ekle - DataFrame'den değerleri al
            fg_vals = []
            ft_vals = []
            
            for _, row in df_side.iterrows():
                fgm = row.get('FGM', 0)
                fga = row.get('FGA', 0)
                fg_pct = row.get('FG%', 0)
                
                ftm = row.get('FTM', 0)
                fta = row.get('FTA', 0)
                ft_pct = row.get('FT%', 0)
                
                fg_vals.append(f"{fgm:.1f}/{fga:.1f} ({fg_pct:.1f}%)")
                ft_vals.append(f"{ftm:.1f}/{fta:.1f} ({ft_pct:.1f}%)")
            
            display_df['FG'] = fg_vals
            display_df['FT'] = ft_vals
            
            # Sütun sıralaması
            final_cols = ['PLAYER', 'PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'FG', 'FT', 'TO']
            display_df = display_df[final_cols]
            
            # Sadece sayısal sütunları formatla (FG ve FT hariç)
            numeric_only = ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'TO']
            
            st.dataframe(
                display_df.style.format("{:.1f}", subset=numeric_only),
                use_container_width=True,
                hide_index=True
            )

if __name__ == "__main__":
    render_trade_analyzer_page()
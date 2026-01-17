import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from services.espn_api import get_active_players_stats

def render_trade_analyzer_page():
    st.title("Trade Analyzer")
    
    # Cache için session state kontrolü
    if 'cached_data' not in st.session_state:
        st.session_state.cached_data = {}
    
    # Background Image - Default veya Upload
    with st.expander("⚙️ Settings & Customization"):
        bg_option = st.radio(
            "Background Option",
            ["Default NBA Background", "Upload Custom Image"],
            horizontal=True
        )
        
        if bg_option == "Default NBA Background":
            # Varsayılan NBA background
            st.markdown(
                """
                <style>
                /* Hide Streamlit Header and Menu */
                #MainMenu {visibility: hidden;}
                header {visibility: hidden;}
                footer {visibility: hidden;}
                
                .stApp {
                    background-image: url("https://wallpapercave.com/wp/wp2552650.jpg");
                    background-size: cover;
                    background-position: center;
                    background-repeat: no-repeat;
                    background-attachment: fixed;
                }
                </style>
                """,
                unsafe_allow_html=True
            )
        else:
            uploaded_bg = st.file_uploader(
                "Upload Background Image",
                type=['png', 'jpg', 'jpeg'],
                help="Upload your own background image"
            )
            
            if uploaded_bg is not None:
                import base64
                
                # Convert to base64
                bytes_data = uploaded_bg.getvalue()
                base64_image = base64.b64encode(bytes_data).decode()
                
                # Apply background
                st.markdown(
                    f"""
                    <style>
                    /* Hide Streamlit Header and Menu */
                    #MainMenu {{visibility: hidden;}}
                    header {{visibility: hidden;}}
                    footer {{visibility: hidden;}}
                    
                    .stApp {{
                        background-image: url("data:image/png;base64,{base64_image}");
                        background-size: cover;
                        background-position: center;
                        background-repeat: no-repeat;
                        background-attachment: fixed;
                    }}
                    </style>
                    """,
                    unsafe_allow_html=True
                )
                st.success("Custom background applied!")
    
    st.markdown("---")
    
    # Üst Kısım: Ayarlar
    col_set1, col_set2 = st.columns([1, 1])
    
    with col_set1:
        time_period = st.selectbox(
            "Time Period",
            ["Last 15 Days", "Last 30 Days", "Season Average"],
            index=0
        )
    
    with col_set2:
        analysis_mode = st.selectbox(
            "Analysis Mode",
            ["Simple Comparison", "Advanced Analysis"],
            index=0
        )
    
    # Veri çekme - Cache kullanarak
    days_map = {"Last 15 Days": 15, "Last 30 Days": 30, "Season Average": None}
    days = days_map[time_period]
    
    cache_key = f"data_{days}"
    
    # Cache'de varsa kullan, yoksa çek
    if cache_key in st.session_state.cached_data:
        df_players = st.session_state.cached_data[cache_key]
    else:
        df_players = get_active_players_stats(days=days)
        st.session_state.cached_data[cache_key] = df_players
    
    if df_players.empty:
        st.error("Could not load player data.")
        return

    # Takım isimlerini düzelt
    team_mapping = {
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
    
    if 'TEAM' in df_players.columns:
        df_players['TEAM_FULL'] = df_players['TEAM'].map(team_mapping).fillna(df_players['TEAM'])
        all_teams = sorted(df_players['TEAM_FULL'].dropna().unique().tolist())
        all_teams.insert(0, "All Teams")
    else:
        all_teams = ["All Teams"]

    st.markdown("---")

    # Oyuncu Seçimi
    st.subheader("Team A Receives")
    col1a, col1b = st.columns([1, 2])
    with col1a:
        team_a = st.selectbox("Filter by Team", all_teams, key="team_a", label_visibility="collapsed")
    with col1b:
        if team_a == "All Teams":
            players_a = df_players['PLAYER'].tolist()
        else:
            players_a = df_players[df_players['TEAM_FULL'] == team_a]['PLAYER'].tolist()
        side_a = st.multiselect("Select Players", players_a, key="side_a", label_visibility="collapsed")
    
    st.markdown("###")
    
    st.subheader("Team B Receives")
    col2a, col2b = st.columns([1, 2])
    with col2a:
        team_b = st.selectbox("Filter by Team", all_teams, key="team_b", label_visibility="collapsed")
    with col2b:
        if team_b == "All Teams":
            players_b = df_players['PLAYER'].tolist()
        else:
            players_b = df_players[df_players['TEAM_FULL'] == team_b]['PLAYER'].tolist()
        side_b = st.multiselect("Select Players", players_b, key="side_b", label_visibility="collapsed")

    if not side_a or not side_b:
        st.info("Select players on both sides to compare")
        return

    st.markdown("---")

    # İstatistik Hesaplama
    def get_stats(players):
        subset = df_players[df_players['PLAYER'].isin(players)]
        totals = subset[["PTS", "REB", "AST", "STL", "BLK", "TO", "3Pts"]].sum()
        averages = subset[["FG%", "FT%"]].mean()
        return pd.concat([totals, averages])

    stats_a = get_stats(side_a)
    stats_b = get_stats(side_b)
    
    # Fantasy Points
    weights = st.session_state.get('last_weights', 
                                   {"PTS": 1, "REB": 1.2, "AST": 1.5, "STL": 3, "BLK": 3, "TO": -1, "3Pts": 1})
    
    fp_a = sum(stats_a.get(cat, 0) * val for cat, val in weights.items())
    fp_b = sum(stats_b.get(cat, 0) * val for cat, val in weights.items())

    # Team A Receives Tablosu
    st.markdown("### Team A Receives")
    
    team_a_data = []
    for player in side_a:
        player_row = df_players[df_players['PLAYER'] == player].iloc[0]
        team_a_data.append({
            'R#': player_row.get('R#', ''),
            'PLAYER': player,
            'POS': player_row.get('POS', ''),
            'TEAM': player_row.get('TEAM', ''),
            'GP': player_row.get('GP', 0),
            'MPG': f"{player_row.get('MPG', 0):.1f}",
            'FG%': f"{player_row.get('FG%', 0):.3f}",
            'FT%': f"{player_row.get('FT%', 0):.3f}",
            '3PM': f"{player_row.get('3Pts', 0):.1f}",
            'PTS': f"{player_row.get('PTS', 0):.1f}",
            'TREB': f"{player_row.get('REB', 0):.1f}",
            'AST': f"{player_row.get('AST', 0):.1f}",
            'STL': f"{player_row.get('STL', 0):.1f}",
            'BLK': f"{player_row.get('BLK', 0):.1f}",
            'TO': f"{player_row.get('TO', 0):.1f}",
            'TOTAL': f"{fp_a / len(side_a):.2f}"
        })
    
    # Average row
    team_a_data.append({
        'R#': '', 'PLAYER': 'AVERAGE', 'POS': '', 'TEAM': '', 'GP': '',
        'MPG': f"{stats_a.get('MPG', 0):.1f}" if 'MPG' in stats_a else '',
        'FG%': f"{stats_a.get('FG%', 0):.3f}",
        'FT%': f"{stats_a.get('FT%', 0):.3f}",
        '3PM': f"{stats_a.get('3Pts', 0):.1f}",
        'PTS': f"{stats_a.get('PTS', 0):.1f}",
        'TREB': f"{stats_a.get('REB', 0):.1f}",
        'AST': f"{stats_a.get('AST', 0):.1f}",
        'STL': f"{stats_a.get('STL', 0):.1f}",
        'BLK': f"{stats_a.get('BLK', 0):.1f}",
        'TO': f"{stats_a.get('TO', 0):.1f}",
        'TOTAL': f"{fp_a:.2f}"
    })
    
    # Total row
    team_a_data.append({
        'R#': '', 'PLAYER': 'TOTAL', 'POS': '', 'TEAM': '', 'GP': '',
        'MPG': f"{stats_a.get('MPG', 0):.1f}" if 'MPG' in stats_a else '',
        'FG%': f"{stats_a.get('FG%', 0):.3f}",
        'FT%': f"{stats_a.get('FT%', 0):.3f}",
        '3PM': f"{stats_a.get('3Pts', 0):.1f}",
        'PTS': f"{stats_a.get('PTS', 0):.1f}",
        'TREB': f"{stats_a.get('REB', 0):.1f}",
        'AST': f"{stats_a.get('AST', 0):.1f}",
        'STL': f"{stats_a.get('STL', 0):.1f}",
        'BLK': f"{stats_a.get('BLK', 0):.1f}",
        'TO': f"{stats_a.get('TO', 0):.1f}",
        'TOTAL': f"{fp_a:.2f}"
    })
    
    df_team_a = pd.DataFrame(team_a_data)
    st.dataframe(df_team_a, use_container_width=True, hide_index=True, height=150)
    
    st.markdown("###")
    
    # Team B Receives Tablosu
    st.markdown("### Team B Receives")
    
    team_b_data = []
    for player in side_b:
        player_row = df_players[df_players['PLAYER'] == player].iloc[0]
        team_b_data.append({
            'R#': player_row.get('R#', ''),
            'PLAYER': player,
            'POS': player_row.get('POS', ''),
            'TEAM': player_row.get('TEAM', ''),
            'GP': player_row.get('GP', 0),
            'MPG': f"{player_row.get('MPG', 0):.1f}",
            'FG%': f"{player_row.get('FG%', 0):.3f}",
            'FT%': f"{player_row.get('FT%', 0):.3f}",
            '3PM': f"{player_row.get('3Pts', 0):.1f}",
            'PTS': f"{player_row.get('PTS', 0):.1f}",
            'TREB': f"{player_row.get('REB', 0):.1f}",
            'AST': f"{player_row.get('AST', 0):.1f}",
            'STL': f"{player_row.get('STL', 0):.1f}",
            'BLK': f"{player_row.get('BLK', 0):.1f}",
            'TO': f"{player_row.get('TO', 0):.1f}",
            'TOTAL': f"{fp_b / len(side_b):.2f}"
        })
    
    # Average row
    team_b_data.append({
        'R#': '', 'PLAYER': 'AVERAGE', 'POS': '', 'TEAM': '', 'GP': '',
        'MPG': f"{stats_b.get('MPG', 0):.1f}" if 'MPG' in stats_b else '',
        'FG%': f"{stats_b.get('FG%', 0):.3f}",
        'FT%': f"{stats_b.get('FT%', 0):.3f}",
        '3PM': f"{stats_b.get('3Pts', 0):.1f}",
        'PTS': f"{stats_b.get('PTS', 0):.1f}",
        'TREB': f"{stats_b.get('REB', 0):.1f}",
        'AST': f"{stats_b.get('AST', 0):.1f}",
        'STL': f"{stats_b.get('STL', 0):.1f}",
        'BLK': f"{stats_b.get('BLK', 0):.1f}",
        'TO': f"{stats_b.get('TO', 0):.1f}",
        'TOTAL': f"{fp_b:.2f}"
    })
    
    # Total row
    team_b_data.append({
        'R#': '', 'PLAYER': 'TOTAL', 'POS': '', 'TEAM': '', 'GP': '',
        'MPG': f"{stats_b.get('MPG', 0):.1f}" if 'MPG' in stats_b else '',
        'FG%': f"{stats_b.get('FG%', 0):.3f}",
        'FT%': f"{stats_b.get('FT%', 0):.3f}",
        '3PM': f"{stats_b.get('3Pts', 0):.1f}",
        'PTS': f"{stats_b.get('PTS', 0):.1f}",
        'TREB': f"{stats_b.get('REB', 0):.1f}",
        'AST': f"{stats_b.get('AST', 0):.1f}",
        'STL': f"{stats_b.get('STL', 0):.1f}",
        'BLK': f"{stats_b.get('BLK', 0):.1f}",
        'TO': f"{stats_b.get('TO', 0):.1f}",
        'TOTAL': f"{fp_b:.2f}"
    })
    
    df_team_b = pd.DataFrame(team_b_data)
    st.dataframe(df_team_b, use_container_width=True, hide_index=True, height=150)

    # SONUÇ
    st.markdown("---")
    diff = fp_a - fp_b
    
    if abs(diff) < 1.0:
        st.success(f"Balanced Trade - Difference: {abs(diff):.2f} FP")
    elif diff > 0:
        st.success(f"Team A Wins - Advantage: +{diff:.2f} Fantasy Points")
    else:
        st.error(f"Team B Wins - Advantage: +{abs(diff):.2f} Fantasy Points")

    # ADVANCED ANALYSIS MODU
    if analysis_mode == "Advanced Analysis":
        st.markdown("---")
        st.subheader("Advanced Analysis")
        
        # Tüm kategorilerde karşılaştırma
        categories = ['PTS', 'REB', 'AST', 'STL', 'BLK', '3Pts', 'TO', 'FG%', 'FT%']
        
        comparison_data = []
        for cat in categories:
            val_a = stats_a.get(cat, 0)
            val_b = stats_b.get(cat, 0)
            diff_val = val_a - val_b
            
            if cat == 'TO':
                winner = "Team B" if diff_val > 0 else "Team A" if diff_val < 0 else "Tied"
            else:
                winner = "Team A" if diff_val > 0 else "Team B" if diff_val < 0 else "Tied"
            
            comparison_data.append({
                'Category': cat,
                'Team A': f"{val_a:.1f}",
                'Team B': f"{val_b:.1f}",
                'Difference': f"{diff_val:+.1f}",
                'Advantage': winner
            })
        
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)
        
        # Kategori Bazlı Kazanan Sayısı
        st.markdown("#### Category Winners")
        wins_a = sum(1 for row in comparison_data if row['Advantage'] == 'Team A')
        wins_b = sum(1 for row in comparison_data if row['Advantage'] == 'Team B')
        ties = sum(1 for row in comparison_data if row['Advantage'] == 'Tied')
        
        col_w1, col_w2, col_w3 = st.columns(3)
        with col_w1:
            st.metric("Team A Wins", wins_a)
        with col_w2:
            st.metric("Team B Wins", wins_b)
        with col_w3:
            st.metric("Ties", ties)
        
        # Radar Chart
        st.markdown("#### Visual Comparison")
        radar_cats = ['PTS', 'REB', 'AST', 'STL', 'BLK', '3Pts']
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=[stats_a[c] for c in radar_cats],
            theta=radar_cats,
            fill='toself',
            name='Team A',
            line_color='#3b82f6'
        ))
        
        fig.add_trace(go.Scatterpolar(
            r=[stats_b[c] for c in radar_cats],
            theta=radar_cats,
            fill='toself',
            name='Team B',
            line_color='#ef4444'
        ))
        
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True)),
            showlegend=True,
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__" or "pages" in str(__file__):
    render_trade_analyzer_page()
import streamlit as st
import pandas as pd
from services.espn_api import get_cached_boxscore



def render_boxscore_modal():

    st.write("DEBUG: boxscore modal rendered", st.session_state.get("open_game_id"))

    """Box score'u göster"""
    game_id = st.session_state.get("open_game_id")
    
    if not game_id:
        st.error("No game selected")
        return
    
    st.title("📊 Box Score")
    
    # Close button
    if st.button("⬅️ Back to Games", type="primary", use_container_width=True):
        st.session_state.open_game_id = None
        st.rerun()
    
    st.divider()
    
    try:
        # Load data
        players = get_cached_boxscore(game_id)
        
        if not players:
            st.warning("Box score data not available for this game.")
            return
        
        df = pd.DataFrame(players)
        
        preferred_cols = [
            "PLAYER", "TEAM", "MIN",
            "PTS", "REB", "AST", "STL", "BLK",
            "FGM", "FGA", "3Pts", "FTM", "FTA", "TO"
        ]
        
        # Sadece mevcut kolonları al
        available_cols = [c for c in preferred_cols if c in df.columns]
        df_display = df[available_cols].copy()
        
        # MIN kolonunu sayısal formata çevir (eğer varsa)
        if "MIN" in df_display.columns:
            # MIN formatı genellikle "34:25" gibi olabilir, sadece dakika kısmını al
            def parse_minutes(min_str):
                if pd.isna(min_str) or min_str == "" or min_str == "--":
                    return 0
                try:
                    # Eğer "34:25" formatındaysa ilk kısmı al
                    if isinstance(min_str, str) and ":" in min_str:
                        return float(min_str.split(":")[0])
                    # Eğer direkt sayıysa
                    return float(min_str)
                except:
                    return 0
            
            df_display["MIN_NUMERIC"] = df_display["MIN"].apply(parse_minutes)
            # MIN'e göre azalan sırada sırala
            df_display = df_display.sort_values("MIN_NUMERIC", ascending=False)
            # Geçici kolonu sil
            df_display = df_display.drop(columns=["MIN_NUMERIC"])
        elif "PTS" in df_display.columns:
            # MIN yoksa PTS'ye göre sırala
            df_display = df_display.sort_values("PTS", ascending=False)
        
        # Takıma göre grupla ve göster
        if "TEAM" in df_display.columns:
            teams = df_display["TEAM"].unique()
            
            tabs = st.tabs(list(teams))
            
            for i, team in enumerate(teams):
                with tabs[i]:
                    team_df = df_display[df_display["TEAM"] == team].drop(columns=["TEAM"])
                    st.dataframe(
                        team_df,
                        use_container_width=True,
                        hide_index=True,
                        height=600
                    )
        else:
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                height=600
            )
            
    except Exception as e:
        st.error(f"Error loading box score: {str(e)}")
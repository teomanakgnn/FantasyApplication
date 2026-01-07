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
            "PLAYER", "TEAM",
            "PTS", "REB", "AST", "STL", "BLK",
            "FGM", "FGA", "3Pts", "FTM", "FTA", "TO"
        ]
        
        # Sadece mevcut kolonları al
        available_cols = [c for c in preferred_cols if c in df.columns]
        df_display = df[available_cols].copy()
        
        # PTS'ye göre sırala
        if "PTS" in df_display.columns:
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
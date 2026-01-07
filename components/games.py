import streamlit as st

def render_games(games):
    st.markdown("### Games")

    cols = st.columns(3)
    for i, g in enumerate(games):
        with cols[i % 3]:
            if st.button(
                f"{g['away']} {g['away_score']} — {g['home_score']} {g['home']}",
                key=f"game_{g['game_id']}"
            ):
                st.session_state.open_game_id = g["game_id"]

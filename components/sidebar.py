import streamlit as st
from datetime import datetime, timedelta


def render_sidebar():
    st.sidebar.markdown("### Analysis Parameters")

    date = st.sidebar.date_input(
        "Game Date",
        datetime.now() - timedelta(days=1)
    )

    st.sidebar.markdown("### Build Selection")

    build = st.sidebar.selectbox(
        "Choose your build",
        [
            "Default Build",
            "FT Punt Build",
            "FG Punt Build",
            "TO Punt Build",
            "🔒 Other Punt Builds (Pro)"
        ]
    )

    # --- Default weights (şimdilik hepsi aynı) ---
    base_weights = {
        "PTS": 1.0,
        "REB": 0.4,
        "AST": 0.7,
        "STL": 1.1,
        "BLK": 0.75,
        "TO": -1.0,
        "FGA": -0.7,
        "FGM": 0.5,
        "FTA": -0.4,
        "FTM": 0.6,
        "3Pts": 0.3,
    }

    # --- Build bazlı override (şimdilik aynı bırakıyoruz) ---
    if build == "FT Punt Build":
        weights = base_weights.copy()

    elif build == "FG Punt Build":
        weights = base_weights.copy()

    elif build == "TO Punt Build":
        weights = base_weights.copy()

    elif build == "🔒 Other Punt Builds (Pro)":
        st.sidebar.info(
            "🔓 Unlock all advanced punt builds\n\n"
            "• 9-CAT optimized models\n"
            "• Custom punt combinations\n"
            "• Season-adjusted weights\n\n"
            "**Upgrade to Pro to access**"
        )
        weights = base_weights.copy()

    else:
        weights = base_weights.copy()

    st.sidebar.markdown("### Scoring Model")

    # --- Katsayı inputları ---
    for key, value in weights.items():
        weights[key] = st.sidebar.number_input(
            key,
            value=value
        )

    st.sidebar.markdown("---")

    run = st.sidebar.button("Run Performance Analysis")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Navigation")

    # Player Trends sayfasına git
    if st.sidebar.button("📈 Player Trends", use_container_width=True, type="primary"):
        st.session_state.page = "trends"
        st.rerun()

    # Injury Report sayfasına git
    if st.sidebar.button("🏥 Injury Report", use_container_width=True):
        st.session_state.page = "injury"
        st.rerun()

    if st.sidebar.button("🏆 Fantasy League", use_container_width=True):
        st.session_state.page = "fantasy_league"
        st.rerun()     

    return date, weights, run
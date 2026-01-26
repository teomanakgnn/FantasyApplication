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

    # --- Default weights ---
    base_weights = {
        "PTS": 0.75,      
        "REB": 0.5,      
        "AST": 0.8,      
        "STL": 1.7,      
        "BLK": 1.6,      
        "TO": -1.5,      
        "FGA": -0.9,     
        "FGM": 1.2,      
        "FTA": -0.55,    
        "FTM": 1.1,     
        "3Pts": 0.6, 
    }

    if build == "FT Punt Build":
            # Serbest Atışları (FTM, FTA) sıfırla
            weights = base_weights.copy()
            weights["FTM"] = 0.0
            weights["FTA"] = 0.0

    elif build == "FG Punt Build":
        # Saha İçi İsabetleri (FGM, FGA) sıfırla
        weights = base_weights.copy()
        weights["FGM"] = 0.0
        weights["FGA"] = 0.0

    elif build == "TO Punt Build":
        # Top Kaybını (TO) sıfırla
        weights = base_weights.copy()
        weights["TO"] = 0.0

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

    return date, weights, run
import streamlit as st
from datetime import datetime, timedelta


def render_sidebar():
    # ---------------------------------------------------------
    # 1. STREAMLIT DEFAULT NAVIGASYONU GİZLEME (CSS)
    # ---------------------------------------------------------
    st.markdown("""
        <style>
            /* Streamlit'in otomatik sayfa listesini gizle */
            [data-testid="stSidebarNav"] {
                display: none !important;
            }
            /* Gerekirse üst boşluğu ayarla */
            .st-emotion-cache-16txtl3 {
                padding-top: 1rem !important;
            }
        </style>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("### Navigation")

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

    # ---------------------------------------------------------
    # 2. MEVCUT KODUNUZ
    # ---------------------------------------------------------
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
        "PTS": 0.9,      
        "REB": 0.5,      
        "AST": 0.8,      
        "STL": 1.7,      
        "BLK": 1.6,      
        "TO": -1.3,      
        "FGA": -0.6,     
        "FGM": 0.8,      
        "FTA": -0.35,    
        "FTM": 0.75,     
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
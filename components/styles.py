import streamlit as st

def load_styles():
    st.markdown("""
    <style>

    /* ===============================
       COLOR SYSTEM
       =============================== */
    :root {
        --bg-main: #0E1117;
        --bg-panel: #161A22;
        --bg-card: #1C212B;
        --border-subtle: #2A2F3A;
        --text-main: #E6E6E6;
        --text-muted: #9AA0A6;
        --accent-red: #C8102E;
    }

    /* ===============================
       FULL SITE BACKGROUND
       =============================== */
    html, body, #root, [data-testid="stAppViewContainer"] {
        background:
            linear-gradient(
                180deg,
                rgba(14,17,23,0.65) 0%,
                rgba(14,17,23,0.55) 100%
            ),
            url("https://wallpapercave.com/wp/wp2825278.jpg");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        color: var(--text-main);
        font-family: Inter, Segoe UI, system-ui, sans-serif;
        font-size: 14px;
    }

    /* ===============================
       MAIN CONTENT CONTAINER
       =============================== */
    section.main > div {
        background-color: rgba(22, 26, 34, 0.94);
        border: 1px solid var(--border-subtle);
        padding: 28px 32px;
        margin: 18px 24px;
    }

    /* ===============================
       SIDEBAR
       =============================== */
    section[data-testid="stSidebar"] {
        background-color: rgba(22, 26, 34, 0.98);
        border-right: 1px solid var(--border-subtle);
    }
                
    /* Hide Streamlit top header */
    header[data-testid="stHeader"] {
    display: none;
    }

    /* Extra padding fix (bazı sürümlerde boşluk kalıyor) */
    [data-testid="stAppViewContainer"] {
    padding-top: 0rem;
    }

            

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        font-size: 12px;
        letter-spacing: 0.6px;
        color: var(--text-muted);
        text-transform: uppercase;
    }

    /* ===============================
       INPUTS
       =============================== */
    input, select {
        background-color: var(--bg-card) !important;
        color: var(--text-main) !important;
        border: 1px solid var(--border-subtle) !important;
        border-radius: 2px !important;
        height: 34px;
    }

    /* ===============================
       BUTTONS
       =============================== */
    button[kind="primary"] {
        background-color: var(--accent-red) !important;
        color: #FFFFFF !important;
        border-radius: 2px !important;
        font-weight: 600;
        letter-spacing: 0.3px;
        height: 38px;
        border: none;
    }

    button[kind="primary"]:hover {
        background-color: #a60d24 !important;
    }

    /* ===============================
       HEADERS
       =============================== */
    h1 {
        font-size: 20px;
        font-weight: 600;
        letter-spacing: 0.3px;
        margin-bottom: 6px;
    }

    h2 {
        font-size: 15px;
        font-weight: 600;
        margin-top: 30px;
        padding-bottom: 6px;
        border-bottom: 1px solid var(--border-subtle);
    }

    /* ===============================
       DATAFRAMES
       =============================== */
    [data-testid="stDataFrame"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border-subtle);
    }

    /* ===============================
       EXPANDER
       =============================== */
    details {
        background-color: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 2px;
    }

    summary {
        color: var(--text-muted);
        font-size: 13px;
        letter-spacing: 0.3px;
    }

    /* ===============================
       SCROLLBAR
       =============================== */
    ::-webkit-scrollbar {
        width: 8px;
    }

    ::-webkit-scrollbar-thumb {
        background-color: var(--border-subtle);
    }

    ::-webkit-scrollbar-thumb:hover {
        background-color: var(--accent-red);
    }

    </style>
    """, unsafe_allow_html=True)

    
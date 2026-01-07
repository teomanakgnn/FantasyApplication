import streamlit as st

@st.cache_data(ttl=1800)  # 30 dakika
def get_latest_injuries():
    return [
        {
            "player": "Joel Embiid",
            "status": "OUT",
            "reason": "Knee soreness",
            "date": "Jan 5"
        },
        {
            "player": "Stephen Curry",
            "status": "QUESTIONABLE",
            "reason": "Ankle sprain",
            "date": "Jan 6"
        },
        {
            "player": "LeBron James",
            "status": "PROBABLE",
            "reason": "Illness",
            "date": "Jan 6"
        },
        {
            "player": "Ja Morant",
            "status": "OUT",
            "reason": "Shoulder",
            "date": "Jan 4"
        },
    ]

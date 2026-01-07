import streamlit as st
from services.injuries import get_latest_injuries

st.title("NBA Injury List")

injuries = get_latest_injuries()

if not injuries:
    st.info("No injury data available.")
else:
    for i in injuries:
        st.write(f"**{i['player']}** — {i['reason']} ({i['date']}) — Status: {i['status']}")

# Back to Home button
if st.button("Back to Home"):
    st.session_state['page'] = 'home'
    st.experimental_rerun()

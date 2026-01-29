import streamlit as st

def render_header():
    st.markdown("## NBA Player Stats & Analysis")
    st.markdown(
        "<span style='color:#9AA0A6'>"
        "Box score–based daily performance evaluation"
        "</span>",
        unsafe_allow_html=True
    )

"""
Eski adres: fantasyapplication.streamlit.app

Uygulama Railway'e tasindi (https://app.hooplifenba.com, kod web/ klasorunde).
Streamlit Cloud bu depoyu hala app.py uzerinden calistiriyor; eski yer
imleri ve guncellenmemis mobil uygulama bos sayfaya dusmesin diye burada
yalnizca yeni adrese goturen bir sayfa duruyor. Streamlit Cloud,
requirements.txt'te olmasa da streamlit'i kendisi kurar.
"""
import streamlit as st

NEW_URL = "https://app.hooplifenba.com/"

st.set_page_config(page_title="HoopLife NBA has moved", page_icon="HoopLifeNBA_logo.png",
                   layout="centered")
st.image("HoopLifeNBA_logo.png", width=140)
st.title("HoopLife NBA has moved")
st.write("The app now lives at **app.hooplifenba.com** - faster, with the same "
         "account, watchlist, saved drafts and over/under picks.")
st.link_button("Open the new HoopLife NBA", NEW_URL, type="primary", use_container_width=True)
st.caption("Update your bookmark. On Android, install the latest app version.")

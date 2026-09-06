"""
Card Connections / Court Connect - NBA kart oyunu.

Oyunun tamami components/card_game.html icinde, tek bir bagimsiz
HTML+JS uygulamasi olarak calisir. Bu modul yalnizca oyuncu havuzunu
ve takim renklerini JSON olarak o uygulamaya verir.

Neden boyle: oyun daha once Streamlit widget'lariyla ciziliyordu
(st.columns + st.checkbox + st.markdown). Her dokunus sunucuya gidip
sayfayi bastan cizdigi icin animasyonlar kesiliyor, kartlar Streamlit'in
kendi yerlesim kutularindan tasip ust uste biniyor ve mobilde kolonlar
2+2+1 sarip kartlari farkli genisliklerde birakiyordu. Oyun mantigi
tarayiciya tasininca bu sinifin tamami ortadan kalkti: dokunuslar
aninda tepki veriyor, hicbir yerde kaydirma yok.
"""
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from services.nba_players_data import get_all_players

_HTML_PATH = Path(__file__).resolve().parent.parent / "components" / "card_game.html"

# Oyun ekraninin yuksekligi. Telefonda gorunur alani doldurur,
# masaustunde de telefon formunda ortalanmis durur.
_GAME_HEIGHT = 720


TEAM_COLORS = {
    "Los Angeles Lakers":       ("#552583", "#FDB927"),
    "Boston Celtics":           ("#007A33", "#BA9653"),
    "Golden State Warriors":    ("#1D428A", "#FFC72C"),
    "Milwaukee Bucks":          ("#00471B", "#EEE1C6"),
    "Denver Nuggets":           ("#0E2240", "#FEC524"),
    "Phoenix Suns":             ("#1D1160", "#E56020"),
    "Dallas Mavericks":         ("#00538C", "#B8C4CA"),
    "Philadelphia 76ers":       ("#006BB6", "#ED174C"),
    "Miami Heat":               ("#98002E", "#F9A01B"),
    "Oklahoma City Thunder":    ("#007AC1", "#EF6100"),
    "Minnesota Timberwolves":   ("#0C2340", "#236192"),
    "New York Knicks":          ("#006BB6", "#F58426"),
    "Cleveland Cavaliers":      ("#860038", "#FDBB30"),
    "Sacramento Kings":         ("#5A2D81", "#63727A"),
    "Indiana Pacers":           ("#002D62", "#FDBB30"),
    "Los Angeles Clippers":     ("#C8102E", "#1D428A"),
    "Toronto Raptors":          ("#CE1141", "#000000"),
    "Chicago Bulls":            ("#CE1141", "#000000"),
    "Atlanta Hawks":            ("#E03A3E", "#C1D32F"),
    "Memphis Grizzlies":        ("#5D76A9", "#12173F"),
    "New Orleans Pelicans":     ("#0C2340", "#C8102E"),
    "San Antonio Spurs":        ("#C4CED4", "#000000"),
    "Houston Rockets":          ("#CE1141", "#000000"),
    "Brooklyn Nets":            ("#000000", "#FFFFFF"),
    "Charlotte Hornets":        ("#1D1160", "#00788C"),
    "Portland Trail Blazers":   ("#E03A3E", "#000000"),
    "Utah Jazz":                ("#002B5C", "#F9A01B"),
    "Washington Wizards":       ("#002B5C", "#E31837"),
    "Detroit Pistons":          ("#C8102E", "#1D42BA"),
    "Orlando Magic":            ("#0077C0", "#000000"),
}


@st.cache_data(show_spinner=False)
def _game_payload():
    """Oyuna gonderilen veri paketi (oyuncu havuzu + takim renkleri)."""
    return json.dumps({
        "players": get_all_players(),
        "team_colors": {t: [c[0], c[1]] for t, c in TEAM_COLORS.items()},
    }, ensure_ascii=False)


def _frame_css():
    """Oyun cercevesinin etrafindaki Streamlit bosluklarini kaldirir."""
    st.markdown("""
        <style>
        /* Oyun tek ekrana sigacak sekilde tasarlandi; sayfa dolgusu
           ve ust bosluk oyunu asagi itip kaydirma yaratiyordu. */
        [data-testid="stMainBlockContainer"] {
            padding: 0 !important;
            max-width: 100% !important;
        }
        /* components.html sabit bir yukseklik yaziyor; oyun ekranin
           tamamini doldurmali. CSS ile ezip gorunur alana oturtuyoruz,
           alt/ust sinirlar cok kisa veya cok uzun ekranlarda koruma. */
        [data-testid="stMain"] [data-testid="stIFrame"] {
            display: block; width: 100%; border: 0;
            height: clamp(520px, calc(100dvh - 58px), 900px) !important;
        }
        @supports not (height: 100dvh) {
            [data-testid="stMain"] [data-testid="stIFrame"] {
                height: clamp(520px, calc(100vh - 58px), 900px) !important;
            }
        }
        [data-testid="stMain"] [data-testid="stElementContainer"]:has(iframe) {
            margin: 0 !important;
        }
        header[data-testid="stHeader"] { background: transparent; }
        </style>
    """, unsafe_allow_html=True)


def render_card_game_page():
    """Kart oyununu cizer."""
    _frame_css()
    html = _HTML_PATH.read_text(encoding="utf-8")
    html = html.replace("__GAME_DATA__", _game_payload())
    components.html(html, height=_GAME_HEIGHT, scrolling=False)

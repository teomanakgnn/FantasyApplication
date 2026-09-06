# EN BAŞTA: konsol kodlamasını UTF-8'e sabitle. Windows'un cp1254 kod
# sayfasında log satırlarındaki ✓/❌/📊 karakterleri UnicodeEncodeError
# fırlatıp sayfayı komple düşürüyordu.
from utils.console import configure_console_encoding
configure_console_encoding()

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import textwrap
import extra_streamlit_components as stx
import time
from services.espn_api import (calculate_game_score, get_score_color)
from services.nba_season import (get_current_season_year, get_season_label,
                                 get_season_start_date, is_offseason)
from auth import check_authentication_enhanced, inject_auth_bridge, logout_enhanced
import os
import pickle
import json
from streamlit_javascript import st_javascript
import hashlib
# Import db early so it's available for fingerprint validation
from services.database import db

# ==================== 1. SAYFA AYARLARI (EN BAŞTA OLMALI) ====================
st.set_page_config(
    page_title="HoopLife NBA",
    layout="wide",
    page_icon="🏀",
    # "auto": dar ekranlarda sidebar kapali baslar. "expanded" ile telefonda
    # sidebar ekranin %82'sini kapatiyor ve kullanici her acilista kapatmak
    # zorunda kaliyordu.
    initial_sidebar_state="auto"
)

client_js = """JSON.stringify({
    ua: navigator.userAgent,
    res: window.screen.width + "x" + window.screen.height,
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone
})"""
raw_fp = st_javascript(client_js)

# 2. KRİTİK NOKTA: Fingerprint gelene kadar bekle
if raw_fp is None or raw_fp == 0:
    st.info("Oturum kontrol ediliyor, lütfen bekleyin...")
    st.stop() # Henüz veri yok, aşağıya inme, bir sonraki run'ı bekle.

# 3. Veri geldi, artık işlemleri yapabiliriz
fingerprint_hash = hashlib.sha256(raw_fp.encode()).hexdigest()

# Store fingerprint in session state for use throughout the app
st.session_state.fingerprint_hash = fingerprint_hash

# Bu debug satırını geçici olarak ekle, terminalde görünüyor mu bak:
# print(f"DEBUG: Cihaz İzi Bulundu: {fingerprint_hash}")

# Otomatik giriş denemesi (Sadece login sayfasında değilsek ve authenticated değilsek)
if not st.session_state.get('authenticated'):
    user = db.validate_session_by_fingerprint(fingerprint_hash)
    if user:
        st.session_state.user = user
        st.session_state.authenticated = True
        st.session_state.page = "home"
        st.rerun()


# ==================== 2. SESSION STATE BAŞLATMA ====================
if "auto_loaded" not in st.session_state:
    st.session_state.auto_loaded = True
if "page" not in st.session_state:
    st.session_state.page = "home"
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "show_all_games" not in st.session_state:
    st.session_state.show_all_games = False
if "slider_index" not in st.session_state:
    st.session_state.slider_index = 0

# ==================== 3. AUTH: LocalStorage RESTORE KÖPRÜSÜ ====================
# Kullanıcı giriş yapmamışsa localStorage'ı kontrol et ve URL param ile yenile.
# check_authentication_enhanced() URL param'ı yakalayarak oturumu başlatır.
inject_auth_bridge()

# ==================== 4. KİMLİK DOĞRULAMA ====================
is_authenticated = check_authentication_enhanced()
user = st.session_state.get('user', None)
is_pro = user.get('is_pro', False) if user else False

# ==================== 5. MOBİL UYGULAMA & EMBED KONTROLÜ ====================
def is_embedded():
    return st.query_params.get("embed") == "true"

def is_mobile_app():
    """Capacitor WebView'den gelen istekleri User-Agent ile algıla."""
    try:
        headers = st.context.headers
        ua = headers.get("User-Agent", "") or headers.get("user-agent", "")
        return "HoopLifeNBA" in ua
    except Exception:
        return False

def is_native_app():
    """Capacitor URL'sindeki ?app=true parametresini kontrol et."""
    return st.query_params.get("app") == "true"

embed_mode = is_embedded()
mobile_app_mode = is_mobile_app()
native_app_mode = is_native_app()

extra_styles = ""
if embed_mode or mobile_app_mode or native_app_mode:
    extra_styles = """
        /* --- Streamlit UI Chrome Gizle --- */
        [data-testid="stHeader"] {display: none !important;}
        [data-testid="stToolbar"] {display: none !important;}
        [data-testid="stDecoration"] {display: none !important;}
        [data-testid="stStatusWidget"] {display: none !important; visibility: hidden !important;}
        [data-testid="stBottom"] {display: none !important; height: 0 !important; overflow: hidden !important;}
        [data-testid="stBottom"] > div {display: none !important;}
        [data-testid="stBottom"] a {display: none !important;}
        [data-testid="stFooter"] {display: none !important;}
        [data-testid="stMainMenu"] {display: none !important;}
        [data-testid="stRunningMan"] {display: none !important;}
        [data-testid="stAppRunningIndicator"] {display: none !important;}
        [data-testid="stNotification"] {display: none !important;}
        header {display: none !important;}
        #MainMenu {display: none !important;}
        footer {display: none !important;}
        .stDeployButton {display: none !important;}
        .reportview-container .main footer {display: none !important;}
        [data-testid="manage-app-button"] {display: none !important;}
        .stActionButton {display: none !important;}
        .stApp > header {display: none !important;}
        div[class*="viewerBadge"] {display: none !important;}
        a[class*="viewerBadge"] {display: none !important;}
        span[class*="viewerBadge"] {display: none !important;}
        a[href*="streamlit.io"] {display: none !important;}
        a[href*="github.com/streamlit"] {display: none !important;}
    """

# Mobil uygulama için ek native-hissiyat CSS'i
mobile_native_styles = ""
if mobile_app_mode or native_app_mode:
    mobile_native_styles = """
        /* ========================================
           NATIVE APP — TEMEL DAVRANIŞ & SMOOTH
           ======================================== */
        html, body {
            overscroll-behavior: none !important;
            -webkit-overflow-scrolling: touch !important;
            -webkit-font-smoothing: antialiased !important;
            -moz-osx-font-smoothing: grayscale !important;
            text-rendering: optimizeLegibility !important;
        }

        * {
            -webkit-tap-highlight-color: transparent !important;
        }

        /* Tüm etkileşimli elemanlar smooth geçiş */
        button, a, input, select, details, summary,
        [data-baseweb="tab"],
        .stButton > button {
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }

        ::-webkit-scrollbar {
            width: 0px !important;
            background: transparent !important;
        }

        /* ========================================
           NATIVE APP — KONTEYNER SPACING
           ======================================== */

        .main .block-container {
            padding-top: max(0.5rem, env(safe-area-inset-top)) !important;
            padding-bottom: max(0.5rem, env(safe-area-inset-bottom)) !important;
            padding-left: max(0.5rem, env(safe-area-inset-left)) !important;
            padding-right: max(0.5rem, env(safe-area-inset-right)) !important;
            max-width: 100% !important;
        }

        section.main > div {
            padding: 14px 10px !important;
            margin: 8px 4px !important;
            border-radius: 12px !important;
        }

        [data-testid="stAppViewContainer"] {
            padding-top: 0 !important;
        }

        /* ========================================
           NATIVE APP — BAŞLIKLAR
           ======================================== */

        h1 {
            font-size: 1.3rem !important;
            margin-bottom: 4px !important;
            margin-top: 6px !important;
            letter-spacing: -0.3px !important;
        }

        h2 {
            font-size: 1.1rem !important;
            margin-top: 10px !important;
            margin-bottom: 6px !important;
            letter-spacing: -0.2px !important;
        }

        h3 {
            font-size: 1rem !important;
            margin-top: 8px !important;
            margin-bottom: 4px !important;
        }

        hr {
            margin-top: 8px !important;
            margin-bottom: 8px !important;
            border-color: rgba(255,255,255,0.06) !important;
        }

        /* ========================================
           NATIVE APP — BUTONLAR
           ======================================== */

        .stButton > button {
            min-height: 42px !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            border-radius: 10px !important;
            padding: 8px 14px !important;
            transform: translateZ(0) !important;
        }

        .stButton > button:active {
            transform: scale(0.97) translateZ(0) !important;
            opacity: 0.85 !important;
        }

        button[kind="primary"] {
            min-height: 42px !important;
            border-radius: 10px !important;
        }

        /* ========================================
           NATIVE APP — KARTLAR (border=True)
           ======================================== */

        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px !important;
            transition: box-shadow 0.2s ease !important;
        }

        /* ========================================
           NATIVE APP — TABLOLAR
           ======================================== */

        [data-testid="stDataFrame"] {
            border-radius: 10px !important;
            overflow: hidden !important;
        }

        /* ========================================
           NATIVE APP — TABS
           ======================================== */

        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 0 !important;
        }

        [data-testid="stTabs"] [data-baseweb="tab"] {
            font-size: 13px !important;
            padding: 8px 12px !important;
            border-radius: 6px 6px 0 0 !important;
        }

        /* ========================================
           NATIVE APP — ALERT / EXPANDER
           ======================================== */

        [data-testid="stAlert"] {
            padding: 10px 12px !important;
            font-size: 13px !important;
            border-radius: 10px !important;
        }

        details {
            border-radius: 10px !important;
            transition: all 0.2s ease !important;
        }

        summary {
            font-size: 13px !important;
            padding: 8px 12px !important;
            min-height: 40px !important;
        }

        /* ========================================
           NATIVE APP — SIDEBAR
           ======================================== */

        section[data-testid="stSidebar"] {
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }

        section[data-testid="stSidebar"] > div {
            padding: 10px 12px !important;
        }

        section[data-testid="stSidebar"] .stButton > button {
            min-height: 40px !important;
            font-size: 13px !important;
            border-radius: 10px !important;
        }

        section[data-testid="stSidebar"] hr {
            margin: 8px 0 !important;
        }

        /* ========================================
           NATIVE APP — METRIC
           ======================================== */

        [data-testid="stMetric"] {
            padding: 4px 0 !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 20px !important;
        }

        /* ========================================
           NATIVE APP — DİĞER
           ======================================== */

        [data-testid="stImage"] {
            margin-bottom: 4px !important;
        }

        /* Dialog/modal */
        [data-testid="stModal"] > div {
            padding: 14px !important;
            border-radius: 14px !important;
        }

        /* Form elemanları smooth */
        input, select, [data-baseweb="select"] {
            border-radius: 8px !important;
            transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
        }

        /* Spinner/loading daha smooth */
        .stSpinner > div {
            border-radius: 10px !important;
        }
    """

# ==================== 6. GLOBAL CSS ====================
st.markdown(f"""
    <style>
        /* Streamlit'in pages/ klasöründen otomatik ürettiği gezinme listesini
           gizle - yönlendirme st.session_state.page üzerinden yapılıyor.
           (config.toml'daki ui.hideSidebarNav 1.49 ile kaldırıldı.) */
        [data-testid="stSidebarNav"] {{ display: none !important; }}

        @media (max-width: 768px) {{
            [data-testid="stSidebar"] {{
                position: fixed !important;
                top: 0 !important; left: 0 !important;
                height: 100vh !important;
                width: 85vw !important; max-width: 320px !important;
                z-index: 999999 !important;
                overflow-y: auto !important;
                overflow-x: hidden !important;
                -webkit-overflow-scrolling: touch !important;
            }}
            [data-testid="stSidebar"] > div {{
                height: 100% !important;
                overflow-y: auto !important;
                overflow-x: hidden !important;
                -webkit-overflow-scrolling: touch !important;
            }}
            [data-testid="stSidebar"][aria-expanded="false"] {{
                display: none !important;
                transform: translateX(-100%) !important;
            }}
            [data-testid="stSidebar"][aria-expanded="true"] {{
                display: flex !important;
                transform: translateX(0) !important;
            }}
            [data-testid="stMain"] {{
                margin-left: 0 !important;
                width: 100% !important;
                /* iOS Safari: asil kaydirici bu eleman. Ivmeli kaydirmayi
                   acikca ac ve kaydirmanin ust cerceveye zincirlenmesini
                   engelle - iframe icinde parmakla kaydirma boyle stabil. */
                -webkit-overflow-scrolling: touch !important;
                overscroll-behavior-y: contain !important;
            }}
        }}

        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"] {{ display: none !important; }}

        #hooplife-master-trigger {{
            z-index: 999999999 !important;
            transform: translateZ(0);
            will-change: transform, width;
        }}

        /* .main Streamlit 1.5x'te DOM'dan kalkti; guncel test-id ile yaz. */
        [data-testid="stMainBlockContainer"],
        .main .block-container {{ padding-top: 1.5rem !important; }}

        @media (max-width: 768px) {{
            [data-testid="stMainBlockContainer"],
            .main .block-container {{
                padding-top: 0.5rem !important;
                padding-left: 0.6rem !important;
                padding-right: 0.6rem !important;
            }}
        }}

        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        footer,
        [data-testid="stBottom"] {{ display: none !important; }}

        .spoiler-score {{
            filter: blur(10px);
            transition: filter 0.4s ease;
            cursor: pointer;
            user-select: none;
        }}
        .spoiler-score:hover {{ filter: blur(6px); }}
        .spoiler-score.revealed {{ filter: blur(0px) !important; cursor: default; }}
        .spoiler-container {{
            position: relative;
            display: inline-block;
            padding: 8px 16px;
            background: linear-gradient(135deg, rgba(255,75,75,0.1) 0%, rgba(139,0,0,0.1) 100%);
            border: 2px solid rgba(255,75,75,0.3);
            border-radius: 12px;
            transition: all 0.3s ease;
            cursor: pointer;
        }}
        .spoiler-icon {{
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            font-size: 1.8em;
            pointer-events: none;
            transition: opacity 0.3s ease;
            z-index: 2;
        }}
        .excitement-badge {{ filter: none !important; cursor: default !important; }}

        @media (max-width: 768px) {{
            [data-testid="stSidebar"] .stButton button {{
                font-size: 0.85rem !important;
                padding: 0.4rem 0.6rem !important;
            }}
        }}

        /* =========================================================
           MOBIL UYUM (<=768px)
           Olculen sorunlar: yan yana kolonlar 390px'te okunmuyor,
           dokunma hedefleri 35-38px (Apple/Google onerisi 44px),
           bazi etiketler 11px altinda kaliyordu.
           ========================================================= */
        @media (max-width: 768px) {{
            /* Kolonlar alt alta gecsin - 2-3 kolon telefonda sikisiyordu */
            [data-testid="stHorizontalBlock"] {{
                flex-wrap: wrap !important;
                gap: 0.5rem !important;
            }}
            [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
                min-width: 100% !important;
                flex: 1 1 100% !important;
            }}
            /* 4+ kolonlu gruplar (hizli secim butonlari gibi) tam genislik
               yerine ikili grid olsun - 5 buton alt alta gelince ekranin
               tamamini yiyordu. Kolon sayisina gore esliyoruz; isaretci
               div'e ve kardes seciciye bagli kalmiyor. */
            [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(4))
              > [data-testid="stColumn"] {{
                min-width: 47% !important;
                flex: 1 1 47% !important;
            }}

            /* Dokunma hedefleri en az 44px */
            [data-testid="stButton"] button,
            [data-testid="stFormSubmitButton"] button,
            [data-testid="stDownloadButton"] button {{
                min-height: 44px !important;
                font-size: 0.95rem !important;
            }}
            [data-testid="stTextInput"] input,
            [data-testid="stNumberInput"] input,
            [data-testid="stDateInput"] input,
            [data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
                min-height: 44px !important;
                font-size: 16px !important;  /* iOS'ta 16px alti otomatik zoom yapar */
            }}
            [data-testid="stRadio"] label,
            [data-testid="stCheckbox"] label {{
                min-height: 34px !important;
                display: flex !important;
                align-items: center !important;
            }}

            /* Okunabilirlik tabani */
            [data-testid="stMarkdownContainer"] p,
            [data-testid="stMarkdownContainer"] li,
            [data-testid="stCaptionContainer"] {{ font-size: 0.9rem !important; }}
            [data-testid="stMetricValue"] {{ font-size: 1.35rem !important; }}
            [data-testid="stMetricLabel"] {{ font-size: 0.78rem !important; }}

            /* Sekmeler telefonda tasiyordu - kaydirilabilir olsun */
            [data-testid="stTabs"] [data-baseweb="tab-list"] {{
                overflow-x: auto !important;
                scrollbar-width: none;
            }}
            [data-testid="stTabs"] [data-baseweb="tab-list"]::-webkit-scrollbar {{ display: none; }}
            [data-testid="stTabs"] button[data-baseweb="tab"] {{
                white-space: nowrap !important;
                padding: 0.4rem 0.7rem !important;
            }}

            /* Genis tablolar sayfayi degil kendi kutusunu kaydirsin */
            [data-testid="stDataFrame"] {{ max-width: 100% !important; }}

            /* Baslik boyutlari */
            h1 {{ font-size: 1.3rem !important; }}
            h2 {{ font-size: 1.1rem !important; }}
            h3 {{ font-size: 1rem !important; }}

            /* Icerik kisa oldugunda altta ham parke fotografi kaliyordu.
               Once min-height:100dvh kullaniliyordu; ama iOS iframe'i
               "duzlestirdiginde" ic viewport devlesip dev bir bosluk
               olusturabiliyor. Onun yerine zemini kaplayan arka plan: ayni
               gorunum, yerlesim riski yok. */
            [data-testid="stMain"] {{ background: rgba(22, 26, 34, 0.94) !important; }}
            [data-testid="stMainBlockContainer"] {{
                margin: 0 !important;
                border-radius: 0 !important;
                border-left: none !important;
                border-right: none !important;
                min-height: 0 !important;
            }}

            /* Dikey ritim: 14px'lik bosluklar telefonda sayfayi gereksiz
               uzatiyordu. */
            [data-testid="stVerticalBlock"] {{ gap: 0.6rem !important; }}
            [data-testid="stMarkdownContainer"] hr,
            [data-testid="stMainBlockContainer"] hr {{
                margin: 0.7rem 0 !important;
            }}
            [data-testid="stMainBlockContainer"] h2,
            [data-testid="stMainBlockContainer"] h3 {{
                margin-top: 0.9rem !important;
                margin-bottom: 0.3rem !important;
            }}
            /* Mac kartlari telefonda gereksiz uzundu */
            [data-testid="stVerticalBlockBorderWrapper"] {{ padding: 2px 0 !important; }}
        }}

        /* Cok dar telefonlar */
        @media (max-width: 400px) {{
            [data-testid="stSidebar"] {{ max-width: 300px !important; }}
        }}

        {extra_styles}
        {mobile_native_styles}
    </style>
""", unsafe_allow_html=True)

# Mobil uygulama için native davranış JavaScript'i
if mobile_app_mode or native_app_mode:
    components.html("""
    <script>
        (function() {
            'use strict';
            var parentDoc = window.parent.document;

            // ====== 1. KALICI CSS ENJEKSİYONU (Rerun'larda bile kalır) ======
            var STYLE_ID = 'hooplife-hide-streamlit-chrome';
            if (!parentDoc.getElementById(STYLE_ID)) {
                var style = parentDoc.createElement('style');
                style.id = STYLE_ID;
                style.textContent = [
                    '/* === HoopLife: Streamlit Chrome Gizle (Mobil) === */',
                    '[data-testid="stHeader"],',
                    '[data-testid="stToolbar"],',
                    '[data-testid="stDecoration"],',
                    '[data-testid="stStatusWidget"],',
                    '[data-testid="stBottom"],',
                    '[data-testid="stFooter"],',
                    '[data-testid="stMainMenu"],',
                    '[data-testid="manage-app-button"],',
                    '[data-testid="stRunningMan"],',
                    '[data-testid="stAppRunningIndicator"],',
                    '[data-testid="stNotification"],',
                    'header[data-testid="stHeader"],',
                    '.stApp > header,',
                    '#MainMenu,',
                    'footer,',
                    '.stDeployButton,',
                    '.stActionButton,',
                    '.reportview-container .main footer,',
                    'div[class*="viewerBadge"],',
                    'a[class*="viewerBadge"],',
                    'span[class*="viewerBadge"],',
                    'a[href*="streamlit.io"],',
                    'a[href*="github.com/streamlit"],',
                    '[data-testid="stBottom"] > div,',
                    '[data-testid="stBottom"] a {',
                    '  display: none !important;',
                    '  visibility: hidden !important;',
                    '  height: 0 !important;',
                    '  max-height: 0 !important;',
                    '  overflow: hidden !important;',
                    '  padding: 0 !important;',
                    '  margin: 0 !important;',
                    '  border: none !important;',
                    '  opacity: 0 !important;',
                    '  pointer-events: none !important;',
                    '  position: absolute !important;',
                    '  z-index: -9999 !important;',
                    '}',
                    '',
                    '/* Running/Rerunning durumunu gizle */',
                    '[data-testid="stStatusWidget"] {',
                    '  display: none !important;',
                    '  visibility: hidden !important;',
                    '}',
                    '',
                    '/* Streamlit bottom bar tamamen kaldır */',
                    '[data-testid="stBottom"] {',
                    '  display: none !important;',
                    '  height: 0 !important;',
                    '  overflow: hidden !important;',
                    '}',
                ].join('\\n');
                parentDoc.head.appendChild(style);
            }

            // ====== 2. NATIVE DAVRANIŞLAR ======

            // Long-press context menu engelle
            parentDoc.addEventListener('contextmenu', function(e) {
                e.preventDefault();
                return false;
            });

            // Çift tıklama zoom engelle
            var lastTap = 0;
            parentDoc.addEventListener('touchend', function(e) {
                var now = Date.now();
                if (now - lastTap < 300) {
                    e.preventDefault();
                }
                lastTap = now;
            }, {passive: false});

            // ====== 3. JAVASCRIPT İLE EK GİZLEME (CSS'in yakalayamadıkları için) ======
            function hideStreamlitChrome() {
                var selectors = [
                    '[data-testid="stHeader"]',
                    '[data-testid="stToolbar"]',
                    '[data-testid="stDecoration"]',
                    '[data-testid="stStatusWidget"]',
                    '[data-testid="stBottom"]',
                    '[data-testid="stFooter"]',
                    '[data-testid="stMainMenu"]',
                    '[data-testid="stRunningMan"]',
                    '[data-testid="stAppRunningIndicator"]',
                    '#MainMenu',
                    'footer',
                    '.stDeployButton',
                    '[data-testid="manage-app-button"]',
                    '.stActionButton',
                    '.stApp > header',
                    'div[class*="viewerBadge"]',
                    'a[class*="viewerBadge"]'
                ];
                selectors.forEach(function(sel) {
                    try {
                        var els = parentDoc.querySelectorAll(sel);
                        els.forEach(function(el) {
                            el.style.setProperty('display', 'none', 'important');
                            el.style.setProperty('visibility', 'hidden', 'important');
                            el.style.setProperty('height', '0', 'important');
                            el.style.setProperty('overflow', 'hidden', 'important');
                            el.style.setProperty('opacity', '0', 'important');
                        });
                    } catch(e) {}
                });

                // Metin içeriğine göre "Hosted/Made with Streamlit" vb. yakala
                try {
                    var allFooters = parentDoc.querySelectorAll('footer, div, span, a');
                    allFooters.forEach(function(el) {
                        var txt = el.innerText || '';
                        if (txt && (txt.includes('Hosted by Streamlit') || txt.includes('Made with Streamlit') || txt.includes('Streamlit Community'))) {
                            if (txt.length < 100) {
                                el.style.setProperty('display', 'none', 'important');
                                el.style.setProperty('visibility', 'hidden', 'important');
                            }
                        }
                    });
                } catch(e) {}

                // Kalıcı CSS hâlâ yerinde mi kontrol et (Streamlit bazen DOM'u sıfırlar)
                if (!parentDoc.getElementById('hooplife-hide-streamlit-chrome')) {
                    var s = parentDoc.createElement('style');
                    s.id = 'hooplife-hide-streamlit-chrome';
                    s.textContent = parentDoc._hooplifeChromeCSS || '';
                    parentDoc.head.appendChild(s);
                }
            }

            // CSS içeriğini yedekle (DOM sıfırlanırsa tekrar enjekte etmek için)
            var existingStyle = parentDoc.getElementById(STYLE_ID);
            if (existingStyle) {
                parentDoc._hooplifeChromeCSS = existingStyle.textContent;
            }

            // İlk çalıştırma + periyodik kontrol
            hideStreamlitChrome();
            setInterval(hideStreamlitChrome, 1500);

            // MutationObserver ile yeni eklenen elementleri de yakala
            var observer = new MutationObserver(function(mutations) {
                hideStreamlitChrome();
            });
            observer.observe(parentDoc.body, {childList: true, subtree: true});
        })();
    </script>
    """, height=0, width=0)

# ==================== 7. SIDEBAR DOCK (BASKETBOL BUTONU) ====================
components.html("""
<script>
    (function() {
        'use strict';
        var isTransitioning = false;
        var animationFrame = null;

        function saveSidebarState(isClosed) {
            try { window.parent.localStorage.setItem('hooplife_sidebar_closed', isClosed ? 'true' : 'false'); } catch(e) {}
        }
        function getSavedSidebarState() {
            try { return window.parent.localStorage.getItem('hooplife_sidebar_closed') === 'true'; } catch(e) { return false; }
        }
        function getSidebarState() {
            const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
            if (!sidebar) return null;
            const rect = sidebar.getBoundingClientRect();
            const computed = window.parent.getComputedStyle(sidebar);
            return {
                element: sidebar,
                isClosed: rect.width < 50 || computed.display === 'none'
            };
        }
        function toggleSidebar() {
            if (isTransitioning) return;
            isTransitioning = true;
            const state = getSidebarState();
            if (!state) { isTransitioning = false; return; }
            const isMobile = window.parent.innerWidth <= 768;
            const sidebar = state.element;
            sidebar.style.transition = 'transform 0.3s cubic-bezier(0.4,0,0.2,1), width 0.3s ease';
            if (state.isClosed) {
                sidebar.style.width = isMobile ? '85vw' : '336px';
                sidebar.style.minWidth = isMobile ? '85vw' : '336px';
                sidebar.style.transform = 'translateX(0)';
                sidebar.style.display = 'flex';
                sidebar.setAttribute('aria-expanded', 'true');
                saveSidebarState(false);
            } else {
                sidebar.style.width = '0'; sidebar.style.minWidth = '0';
                sidebar.style.transform = 'translateX(-100%)';
                sidebar.setAttribute('aria-expanded', 'false');
                saveSidebarState(true);
                if (isMobile) setTimeout(() => { sidebar.style.display = 'none'; }, 300);
            }
            setTimeout(() => { isTransitioning = false; updateVisibility(); }, 320);
        }
        function createHoopLifeDock() {
            const old = window.parent.document.getElementById('hooplife-master-trigger');
            if (old) old.remove();
            const trigger = window.parent.document.createElement('div');
            trigger.id = 'hooplife-master-trigger';
            const mob = window.parent.innerWidth <= 768;
            trigger.style.cssText = `position:fixed;${mob ? 'bottom:86px;' : 'top:20%;'}left:0;height:60px;width:45px;
                background:#1a1c24;border:2px solid #ff4b4b;border-left:none;
                border-radius:0 15px 15px 0;z-index:999999999;cursor:pointer;
                display:flex;align-items:center;justify-content:center;
                box-shadow:5px 0 15px rgba(0,0,0,0.4);
                transition:all 0.25s cubic-bezier(0.4,0,0.2,1);`;
            trigger.innerHTML = '<div id="hl-icon" style="font-size:26px;transition:transform 0.4s ease;filter:drop-shadow(0 0 5px rgba(255,75,75,0.3));">🏀</div>';
            trigger.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); toggleSidebar(); });
            trigger.addEventListener('mouseenter', () => {
                if (!isTransitioning && getSidebarState()?.isClosed) {
                    trigger.style.width = '60px'; trigger.style.background = '#ff4b4b';
                    const icon = trigger.querySelector('#hl-icon');
                    if (icon) icon.style.transform = 'rotate(360deg) scale(1.2)';
                }
            });
            trigger.addEventListener('mouseleave', () => {
                if (!isTransitioning && getSidebarState()?.isClosed) {
                    trigger.style.width = '45px'; trigger.style.background = '#1a1c24';
                    const icon = trigger.querySelector('#hl-icon');
                    if (icon) icon.style.transform = 'rotate(0deg) scale(1)';
                }
            });
            window.parent.document.body.appendChild(trigger);
        }
        function updateVisibility() {
            const trigger = window.parent.document.getElementById('hooplife-master-trigger');
            if (!trigger) { createHoopLifeDock(); return; }
            const state = getSidebarState();
            if (!state) return;
            const isMobile = window.parent.innerWidth <= 768;
            if (!state.isClosed) {
                // Sidebar acik: mobilde ust bardaki hamburger X'e donuyor,
                // masaustunde dock'a gerek yok. Her iki durumda da gizle.
                trigger.style.display = 'none';
            } else if (isMobile) {
                // Mobilde gezinme ust bardaki hamburger ile yapiliyor;
                // yuzen top icerigi kapatiyordu, tamamen gizle.
                trigger.style.display = 'none';
            } else {
                Object.assign(trigger.style, {
                    display:'flex', left:'0',
                    top: isMobile ? 'auto' : '20%',
                    bottom: isMobile ? '86px' : 'auto',
                    // Mobilde icerigin uzerinde duruyor; daha kucuk ve
                    // hafif saydam olsun ki altindaki tabloyu kapatmasin.
                    opacity: isMobile ? '0.9' : '1',
                    width: isMobile ? '34px' : '45px',
                    height: isMobile ? '50px' : '60px',
                    background:'#1a1c24', border:'2px solid #ff4b4b', borderLeft:'none',
                    borderRadius:'0 15px 15px 0'
                });
                trigger.innerHTML = '<div id="hl-icon" style="font-size:26px;transition:transform 0.4s ease;">🏀</div>';
                trigger.onmouseenter = () => { trigger.style.width='60px'; trigger.style.background='#ff4b4b'; };
                trigger.onmouseleave = () => { trigger.style.width='45px'; trigger.style.background='#1a1c24'; };
            }
            trigger.onclick = (e) => { e.preventDefault(); e.stopPropagation(); toggleSidebar(); };
        }
        // Mobilde sidebar bir gezinme cekmecesi: icindeki bir butona
        // basildiginda kendiliginden kapanmali, yoksa acilan sayfayi
        // kapatiyor ve kullanici her seferinde elle kapatmak zorunda kaliyor.
        function bindMobileAutoClose() {
            const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
            if (!sidebar || sidebar.dataset.hlAutoClose === '1') return;
            sidebar.dataset.hlAutoClose = '1';
            sidebar.addEventListener('click', (e) => {
                if (window.parent.innerWidth > 768) return;
                const btn = e.target.closest('button');
                if (!btn) return;
                // Form/girdi kontrolleri sayfayi degistirmiyor, onlarda kapatma.
                if (btn.closest('[data-testid="stNumberInput"], [data-testid="stSelectbox"], [data-testid="stDateInput"], [data-testid="stSlider"], [data-testid="stExpander"]')) return;
                // Tiklama Streamlit rerun'u tetikliyor ve bu component
                // iframe'i bastan kuruluyor; bekleyen bir setTimeout yok
                // oluyordu. Bu yuzden niyeti hemen localStorage'a yaz -
                // yeniden yuklenen init() kayitli durumu uygulayip
                // sidebar'i kapali aciyor. Ayrica aninda da kapat.
                saveSidebarState(true);
                const st = getSidebarState();
                if (st && !st.isClosed) {
                    const el = st.element;
                    el.style.transition = 'transform .25s ease, width .25s ease';
                    el.style.width = '0'; el.style.minWidth = '0';
                    el.style.transform = 'translateX(-100%)';
                    el.setAttribute('aria-expanded', 'false');
                    setTimeout(() => { el.style.display = 'none'; }, 260);
                }
            }, true);
        }

        // Gorunmez yardimci elemanlar (components.html(height=0) iframe'leri
        // ve sadece <style> iceren st.markdown bloklari) yuksekligi 0 olsa
        // da stVerticalBlock'un flex 'gap' degeri yuzunden her biri 14px
        // bosluk biraliyordu.
        //
        // DIKKAT: Sadece "yuksekligi 0" bakmak yetmiyor - sidebar mobilde
        // kapaliyken display:none oluyor ve icindeki HER SEY 0 yukseklik
        // olcuyor. Onceki surum bu yuzden sidebar'daki Mock Draft / Card
        // Connections / Login butonlarini kalici olarak gizliyordu; menu
        // aciliyor ama bos geliyordu. Bu yuzden:
        //   1) Sidebar icine asla dokunma
        //   2) Sadece bilinen gorunmez tipleri gizle (bos iframe / style-only
        //      markdown), rastgele 0 yukseklikli her seyi degil
        function isInvisibleHelper(el) {
            const md = el.querySelector('[data-testid="stMarkdown"]');
            const ifr = el.querySelector('[data-testid="stIFrame"]');
            if (ifr) return ifr.getBoundingClientRect().height === 0;
            if (md && md.querySelector('style')) return !(md.innerText || '').trim();
            return false;
        }

        function collapseEmptyContainers() {
            const doc = window.parent.document;
            doc.querySelectorAll('[data-testid="stElementContainer"]').forEach((el) => {
                if (el.closest('[data-testid="stSidebar"]')) return;
                const wasHidden = el.dataset.hlCollapsed === '1';
                if (wasHidden) el.style.display = '';
                if (isInvisibleHelper(el)) {
                    el.style.display = 'none';
                    el.dataset.hlCollapsed = '1';
                } else if (wasHidden) {
                    delete el.dataset.hlCollapsed;
                }
            });
        }

        // ---------------------------------------------------------------
        // MOBIL UST BAR
        // Yuzen basketbol topu icerigin uzerinde duruyor ve metni kapatiyordu
        // (olculdu: ana sayfada "PRO Feature" yazisinin uzerine biniyordu).
        // Mobilde onun yerine standart bir uygulama basligi + hamburger.
        // ---------------------------------------------------------------
        function ensureMobileTopBar() {
            const doc = window.parent.document;
            const isMobile = window.parent.innerWidth <= 768;
            let bar = doc.getElementById('hl-topbar');

            if (!isMobile) {
                if (bar) bar.style.display = 'none';
                doc.documentElement.style.removeProperty('--hl-topbar-h');
                return;
            }

            if (!bar) {
                bar = doc.createElement('div');
                bar.id = 'hl-topbar';
                bar.innerHTML =
                    '<button id="hl-burger" aria-label="Menu" ' +
                    'style="all:unset;display:flex;align-items:center;justify-content:center;' +
                    'width:44px;height:44px;border-radius:10px;cursor:pointer;flex:0 0 auto;">' +
                    '<span id="hl-burger-icon" style="display:block;width:20px;height:14px;position:relative;">' +
                    '<i style="position:absolute;top:0;left:0;width:100%;height:2px;background:#fff;border-radius:2px;transition:.25s;"></i>' +
                    '<i style="position:absolute;top:6px;left:0;width:100%;height:2px;background:#fff;border-radius:2px;transition:.25s;"></i>' +
                    '<i style="position:absolute;top:12px;left:0;width:100%;height:2px;background:#fff;border-radius:2px;transition:.25s;"></i>' +
                    '</span></button>' +
                    '<span style="font-weight:700;font-size:15px;letter-spacing:.2px;color:#fff;' +
                    'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">HoopLife NBA</span>';
                bar.style.cssText =
                    'position:fixed;top:0;left:0;right:0;height:52px;z-index:999999998;' +
                    'display:flex;align-items:center;gap:10px;padding:0 12px;' +
                    'background:rgba(14,17,23,.96);backdrop-filter:saturate(140%) blur(10px);' +
                    '-webkit-backdrop-filter:saturate(140%) blur(10px);' +
                    'border-bottom:1px solid rgba(255,255,255,.09);';
                doc.body.appendChild(bar);
            }
            bar.style.display = 'flex';

            // KRITIK: Ust bar ana dokumanda kaliyor ama her Streamlit
            // rerun'unda bu component iframe'i bastan kuruluyor. Dinleyici
            // eski (yok olmus) iframe'in toggleSidebar'ina bagli kalinca
            // hamburger sessizce calismaz oluyordu. Bu yuzden her turda
            // yeniden ata (onclick atamasi oncekini degistirir).
            const burgerEl = bar.querySelector('#hl-burger');
            if (burgerEl) {
                burgerEl.onclick = function (e) {
                    e.preventDefault(); e.stopPropagation(); toggleSidebar();
                };
            }

            // Icerik barin altinda kalmasin
            let pad = doc.getElementById('hl-topbar-pad');
            if (!pad) {
                pad = doc.createElement('style');
                pad.id = 'hl-topbar-pad';
                pad.textContent =
                    '@media (max-width:768px){' +
                    '[data-testid="stMainBlockContainer"]{padding-top:70px !important;}' +
                    // Sidebar ust barin altindan baslasin, icerigi kaybolmasin
                    '[data-testid="stSidebar"]{top:0 !important;}' +
                    '[data-testid="stSidebar"] [data-testid="stSidebarContent"],' +
                    '[data-testid="stSidebar"] > div{padding-top:56px !important;}' +
                    '}';
                doc.head.appendChild(pad);
            }

            // Sidebar acikken hamburger X'e donsun
            const st = getSidebarState();
            const open = st && !st.isClosed;
            const bars = bar.querySelectorAll('#hl-burger-icon i');
            if (bars.length === 3) {
                bars[0].style.transform = open ? 'translateY(6px) rotate(45deg)' : '';
                bars[1].style.opacity = open ? '0' : '1';
                bars[2].style.transform = open ? 'translateY(-6px) rotate(-45deg)' : '';
            }
        }

        function init() {
            // Kullanici kaydirirken periyodik islerin layout okumasini
            // engelle - yoksa her olcum yerlesimi zorluyor ve telefonda
            // kaydirma takiliyor.
            let scrolling = false, scrollTimer = null;
            function markScrolling() {
                scrolling = true;
                clearTimeout(scrollTimer);
                scrollTimer = setTimeout(() => { scrolling = false; updateVisibility(); }, 180);
            }
            const pdoc = window.parent.document;
            ['touchstart', 'touchmove', 'scroll', 'wheel'].forEach((evt) => {
                pdoc.addEventListener(evt, markScrolling, { passive: true, capture: true });
            });

            createHoopLifeDock();
            ensureMobileTopBar();
            setInterval(() => { if (!scrolling) ensureMobileTopBar(); }, 900);
            bindMobileAutoClose();
            setInterval(bindMobileAutoClose, 1500);
            collapseEmptyContainers();
            // Kaydirma sirasinda calistirma: bu fonksiyon da olcum yapiyor
            // ve gereksiz yerlesim tetikliyor.
            setInterval(() => { if (!scrolling) collapseEmptyContainers(); }, 1500);
            setTimeout(() => {
                if (getSavedSidebarState()) {
                    const s = getSidebarState();
                    if (s && !s.isClosed) {
                        s.element.style.width = '0'; s.element.style.minWidth = '0';
                        s.element.style.transform = 'translateX(-100%)';
                        s.element.setAttribute('aria-expanded','false');
                    }
                }
                updateVisibility();
            }, 800);
            // ONCEDEN: her karede updateVisibility() calisiyordu. Bu fonksiyon
            // once layout okuyor (getBoundingClientRect + getComputedStyle),
            // sonra stil yaziyor - yani her karede zorunlu senkron yerlesim.
            // Gercek telefonda bu, parmakla kaydirmayi boguyordu.
            // Artik: kullanici dokunurken hic calismiyor, aksi halde en fazla
            // 400ms'de bir. Sidebar degisimlerini zaten MutationObserver
            // yakaliyor.
            setInterval(() => {
                if (!isTransitioning && !scrolling) updateVisibility();
            }, 400);
            let resizeTimer;
            window.parent.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => updateVisibility(), 100); });
            const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
            if (sidebar) {
                new MutationObserver(() => { if (!isTransitioning) requestAnimationFrame(updateVisibility); })
                    .observe(sidebar, { attributes: true, attributeFilter: ['style','aria-expanded','class'] });
            }
        }
        if (window.parent.document.readyState === 'loading') {
            window.parent.document.addEventListener('DOMContentLoaded', init);
        } else { init(); }
    })();
</script>
""", height=0, width=0)


# ==================== 8. DİĞER IMPORTLAR ====================
from components.styles import load_styles
from components.header import render_header
from components.sidebar import render_sidebar
from components.tables import render_tables
from components.mvp_lvp import render_mvp_lvp_section
from services.espn_api import (
    get_last_available_game_date,
    get_cached_boxscore,
    get_scoreboard
)

try:
    from services.scoring import calculate_scores
except ImportError:
    pass

load_styles()

# ==================== 9. TRIVIA ====================
@st.dialog("Daily NBA Trivia", width="small")
def show_trivia_modal(question, user_id=None, current_streak=0):
    st.session_state.active_dialog = 'trivia'

    if st.session_state.get('trivia_success_state', False):
        st.balloons()
        st.success("Correct Answer!")
        st.info(f"{question.get('explanation', '')}")
        if user_id:
            new_streak = db.get_user_streak(user_id)
            st.markdown(f"### Current Streak: {new_streak} days!")
        st.caption("See you tomorrow! 👋")
        if st.button("Close", type="primary", key="close_success"):
            st.session_state.pop('trivia_success_state', None)
            st.session_state.pop('trivia_force_open', None)
            st.session_state.active_dialog = None
            st.rerun()
        return

    if st.session_state.get('trivia_error_state', False):
        error_info = st.session_state.get('trivia_error_info', {})
        st.error(f"Wrong. Correct Answer: {error_info.get('correct_option')}) {error_info.get('correct_text')}")
        if error_info.get('explanation'):
            st.info(f"{error_info.get('explanation')}")
        if user_id:
            st.warning("💔 Your streak has been reset.")
        st.caption("Better luck tomorrow! 👋")
        if st.button("Close", type="primary", key="close_error"):
            st.session_state.pop('trivia_error_state', None)
            st.session_state.pop('trivia_error_info', None)
            st.session_state.pop('trivia_force_open', None)
            st.session_state.active_dialog = None
            st.rerun()
        return

    if user_id:
        badge_style = "background-color:rgba(255,75,75,0.15);border:1px solid rgba(255,75,75,0.3);color:#ff4b4b;"
        icon, text = "", f"{current_streak} Day Streak"
    else:
        badge_style = "background-color:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.1);color:#e0e0e0;"
        icon, text = "", "Login to save your daily streak."

    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.1);">
        <div style="font-weight:600;">{datetime.now().strftime('%d %B')}</div>
        <div style="{badge_style} padding:5px 10px;border-radius:12px;font-size:0.85em;">{icon} {text}</div>
    </div>
    <div style="background:linear-gradient(135deg,#FF4B4B 0%,#8B0000 100%);padding:12px;border-radius:10px;margin-bottom:20px;border:1px solid rgba(255,255,255,0.2);">
        <div style="color:white;font-weight:700;">PS5 GIVEAWAY!</div>
        <div style="color:rgba(255,255,255,0.9);font-size:0.82rem;margin-top:5px;">
            Reach a <b>50-day streak</b> to enter the draw for a <b>PlayStation 5</b>!<br>
            <b>Draw Date: April 13th</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"#### {question['question']}")

    with st.form("trivia_form", border=False):
        options = {"A": question['option_a'], "B": question['option_b'], "C": question['option_c'], "D": question['option_d']}
        choice = st.radio("Your answer:", list(options.keys()), format_func=lambda x: f"{x}) {options[x]}", index=None)
        submitted = st.form_submit_button("Answer", width='stretch', type="primary")

    if submitted:
        if not choice:
            st.warning("Please select an option.")
            st.stop()

        is_correct = (choice == question['correct_option'])
        today_str = str(datetime.now().date())

        if is_correct:
            if user_id:
                db.mark_user_trivia_played(user_id)
            else:
                st.session_state[f'trivia_played_{today_str}'] = True
            st.session_state['trivia_success_state'] = True
            st.session_state['trivia_force_open'] = True
            st.rerun()
        else:
            if user_id:
                db.mark_user_trivia_played(user_id)
            else:
                st.session_state[f'trivia_played_{today_str}'] = True
            st.session_state['trivia_error_state'] = True
            st.session_state['trivia_error_info'] = {
                'correct_option': question['correct_option'],
                'correct_text': options[question['correct_option']],
                'explanation': question.get('explanation', '')
            }
            st.session_state['trivia_force_open'] = True
            st.rerun()


def handle_daily_trivia(all_cookies):
    try:
        active = st.session_state.get('active_dialog')
        if active is not None and active != 'trivia':
            return

        trivia = db.get_daily_trivia()
        if not trivia:
            return

        today_str = str(datetime.now().date())
        current_user = st.session_state.get('user')
        force_open = st.session_state.get('trivia_force_open', False)
        should_show = False
        streak = 0
        u_id = None

        session_played_key = f'trivia_played_{today_str}'
        session_played = st.session_state.get(session_played_key, False)

        if current_user:
            u_id = current_user['id']
            has_played = db.check_user_played_trivia_today(u_id)
            if force_open or not has_played:
                should_show = True
                streak = db.get_user_streak(u_id)
        else:
            if session_played:
                should_show = force_open
            else:
                last_played_cookie = all_cookies.get('guest_trivia_date') if all_cookies else None
                if force_open:
                    should_show = True
                elif last_played_cookie == today_str:
                    st.session_state[session_played_key] = True
                else:
                    should_show = True

        if should_show:
            show_trivia_modal(trivia, u_id, streak)

    except Exception as e:
        print(f"Trivia handler error: {e}")





# ==================== 11. SIDEBAR ====================
st.sidebar.image("HoopLifeNBA_logo.png", width='stretch')

with st.sidebar:
    st.markdown("---")

    # Mock Draft - herkese açık
    if st.button("🏀 Mock Draft", width='stretch', type="secondary", key="sidebar_mock_draft_btn"):
        st.session_state.page = "mock_draft"
        st.rerun()

    # Card Game button - accessible to everyone
    if st.button("Card Connections", width='stretch', type="secondary", key="sidebar_card_game_btn"):
        st.session_state.page = "card_game"
        st.rerun()

    st.markdown("---")

    if is_authenticated and user:
        st.markdown(f"""
            <div style='background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                        padding:1rem;border-radius:10px;margin-bottom:1rem;'>
                <div style='color:white;font-weight:600;font-size:1.1rem;'>{user.get('username','User')}</div>
                <div style='color:rgba(255,255,255,0.8);font-size:0.85rem;'>{user.get('email','')}</div>
            </div>
        """, unsafe_allow_html=True)

        if is_pro:
            st.success("PRO Member")
            watchlist_count = len(db.get_watchlist(user['id']))
            if st.button(f"My Watchlist ({watchlist_count})", width='stretch'):
                st.session_state.page = "watchlist"
                st.rerun()
        else:
            st.info("Free Account")
            if st.button("Upgrade to PRO", width='stretch'):
                st.info("Contact admin for PRO upgrade")

        if st.button("Logout", width='stretch'):
            logout_enhanced()
    else:
        st.markdown("""
            <div style='background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%);
                        padding:1rem;border-radius:10px;margin-bottom:1rem;text-align:center;'>
                <div style='color:white;font-weight:600;font-size:1.1rem;margin-bottom:0.5rem;'>Get More Features</div>
                <div style='color:rgba(255,255,255,0.9);font-size:0.85rem;'>Login to unlock PRO features</div>
            </div>
        """, unsafe_allow_html=True)

        if st.button("Login / Register", width='stretch', type="primary"):
            st.session_state.page = "login"
            st.rerun()

        with st.expander("PRO Features"):
            st.markdown("""
                - Player Watchlists
                - Advanced Analytics
                - Player Trends
                - Custom Alerts
                - Save Preferences
                - Export Data
            """)

# ==================== 12. SAYFA YÖNLENDİRMELERİ ====================
if st.session_state.page == "login":
    from auth import render_auth_page_enhanced
    render_auth_page_enhanced()
    st.stop()

if st.session_state.page == "injury":
    from pages.injury_report import render_injury_page
    render_injury_page()
    if st.sidebar.button("Back to Home", width='stretch'):
        st.session_state.page = "home"
        st.rerun()
    st.stop()

if st.session_state.page == "trends":
    if not is_pro:
        st.warning("This is a PRO feature.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Login / Register", width='stretch', type="primary"):
                st.session_state.page = "login"
                st.rerun()
        with col2:
            if st.button("Back to Home", width='stretch'):
                st.session_state.page = "home"
                st.rerun()
        st.stop()
    from pages.player_trends import render_player_trends_page
    render_player_trends_page()
    st.stop()

if st.session_state.page == "fantasy_league":
    from pages.fantasy_league import render_fantasy_league_page
    render_fantasy_league_page()
    st.stop()

if st.session_state.page == "watchlist":
    if not is_pro:
        st.warning("Watchlist is a PRO feature.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Login / Register", width='stretch', type="primary"):
                st.session_state.page = "login"
                st.rerun()
        with col2:
            if st.button("⬅️ Back to Home", width='stretch'):
                st.session_state.page = "home"
                st.rerun()
        st.stop()
    from pages.watchlist import render_watchlist_page
    render_watchlist_page()
    st.stop()

if st.session_state.page == "trade_analyzer":
    from pages.trade_analyzer import render_trade_analyzer_page
    render_trade_analyzer_page()
    st.stop()

if st.session_state.page == "mock_draft":
    from pages.mock_draft import render_mock_draft_page
    render_mock_draft_page()
    if st.sidebar.button("Back to Home", width='stretch', key="md_sidebar_back"):
        st.session_state.page = "home"
        st.rerun()
    st.stop()

if st.session_state.page == "card_game":
    from pages.card_game import render_card_game_page
    render_card_game_page()
    if st.sidebar.button("Back to Home", width='stretch', key="cg_sidebar_back"):
        st.session_state.page = "home"
        st.session_state.pop("card_game", None)
        st.rerun()
    st.stop()

# ==================== 13. BOX SCORE DIALOG ====================
st.markdown("""
    <style>
    .game-header-container {
        display:flex;justify-content:space-between;align-items:center;
        background-color:#f8f9fa;border-radius:12px;padding:20px;
        margin-bottom:20px;border:1px solid #e0e0e0;color:#000;
    }
    .team-info { display:flex;flex-direction:column;align-items:center;width:30%; }
    .team-name { font-weight:700;font-size:1.1rem;margin-top:8px;text-align:center; }
    .score-board { display:flex;flex-direction:column;align-items:center;width:40%; }
    .main-score { font-size:2.5rem;font-weight:800;color:#333; }
    .game-status { background-color:#e3f2fd;color:#1565c0;padding:4px 12px;border-radius:16px;font-size:0.8rem;font-weight:600;margin-top:5px; }
    @media (prefers-color-scheme: dark) {
        .game-header-container { background-color:#262730;border-color:#444;color:#fff; }
        .main-score { color:#fff; }
        .game-status { background-color:#333;color:#90caf9; }
    }
    </style>
""", unsafe_allow_html=True)


@st.dialog("Game Details", width="large")
def show_boxscore_dialog(game_info):
    st.session_state.active_dialog = 'boxscore'
    game_id = game_info['game_id']

    st.markdown(f"""
    <div class="game-header-container">
        <div class="team-info">
            <img src="{game_info.get('away_logo')}" width="60">
            <div class="team-name">{game_info.get('away_team')}</div>
        </div>
        <div class="score-board">
            <div class="main-score">{game_info.get('away_score')} - {game_info.get('home_score')}</div>
            <div class="game-status">{game_info.get('status')}</div>
        </div>
        <div class="team-info">
            <img src="{game_info.get('home_logo')}" width="60">
            <div class="team-name">{game_info.get('home_team')}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Loading stats..."):
        players = get_cached_boxscore(game_id)

    if not players:
        st.warning("Box score details are not available yet.")
        return

    df = pd.DataFrame(players)
    numeric_cols = ["PTS", "REB", "AST", "STL", "BLK", "TO", "FGM", "FGA", "3Pts", "3PTA", "FTM", "FTA"]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df.get(c, 0), errors="coerce").fillna(0)

    df["FG"] = df.apply(lambda x: f"{int(x['FGM'])}-{int(x['FGA'])}", axis=1)
    df["3PT"] = df.apply(lambda x: f"{int(x['3Pts'])}-{int(x['3PTA'])}", axis=1)
    df["FT"] = df.apply(lambda x: f"{int(x['FTM'])}-{int(x['FTA'])}", axis=1)
    if "MIN" not in df.columns:
        df["MIN"] = "--"

    display_cols = ["PLAYER", "MIN", "FG", "3PT", "FT", "PTS", "REB", "AST", "STL", "BLK", "TO"]
    final_cols = [c for c in display_cols if c in df.columns]

    if is_pro and user:
        st.markdown("#### Quick Add to Watchlist")
        watchlist = db.get_watchlist(user['id'])
        watchlist_names = [w['player_name'] for w in watchlist]
        players_to_add = [p for p in df['PLAYER'].unique() if p not in watchlist_names]
        if players_to_add:
            col1, col2 = st.columns([3, 1])
            with col1:
                selected_players = st.multiselect("Select players to add", players_to_add)
            with col2:
                st.write("")
                st.write("")
                if st.button("➕ Add Selected", disabled=not selected_players):
                    added = sum(1 for p in selected_players if db.add_to_watchlist(user['id'], p, f"Added from {game_info.get('away_team')} vs {game_info.get('home_team')}"))
                    if added:
                        st.success(f"Added {added} player(s)!")
                        st.balloons()
        else:
            st.info("All players already in your watchlist!")
        st.markdown("---")
    elif not is_pro:
        st.info("Login with a PRO account to add players to your watchlist!")

    if "TEAM" in df.columns:
        teams = df["TEAM"].unique()
        tab1, tab2 = st.tabs([f"Away: {game_info.get('away_team')}", f"Home: {game_info.get('home_team')}"])

        def render_team_table(container, team_name):
            with container:
                team_df = df[df["TEAM"].astype(str).str.contains(team_name, case=False, na=False)].copy()
                if not team_df.empty:
                    team_df = team_df.sort_values("MIN", ascending=False, key=lambda x: pd.to_numeric(x, errors='coerce').fillna(0))
                    if is_pro and user:
                        wl = db.get_watchlist(user['id'])
                        wl_names = [w['player_name'] for w in wl]
                        team_df['⭐'] = team_df['PLAYER'].apply(lambda x: '⭐' if x in wl_names else '')
                        cols_show = ['⭐'] + final_cols
                    else:
                        cols_show = final_cols
                    st.dataframe(team_df[cols_show], width='stretch', hide_index=True, height=400)
                else:
                    st.info(f"No stats available for {team_name}")

        if len(teams) > 0:
            render_team_table(tab1, teams[0])
            if len(teams) > 1:
                render_team_table(tab2, teams[1])
            else:
                with tab2: st.info("Waiting for data...")
    else:
        st.dataframe(df[final_cols], width='stretch')


# ==================== 14. PLAYOFF BRACKET DIALOG ====================
@st.dialog("🏆 NBA Playoff Bracket Predictions", width="large")
def show_playoff_bracket_dialog():
    st.session_state.active_dialog = 'playoff_bracket'

    # Playoff yılı = sezonun bitiş yılı (2026-27 sezonu -> 2027 playoffları)
    bracket_year = get_current_season_year()

    # Check if there's a shared bracket in URL params
    shared_data = st.query_params.get("bracket", None)

    st.markdown("""
    <style>
    .bracket-title {
        text-align: center;
        font-size: 1.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #ff4b4b, #ff8c00);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }
    .bracket-subtitle {
        text-align: center;
        color: rgba(255,255,255,0.6);
        font-size: 0.85rem;
        margin-bottom: 20px;
    }
    #bracket-root {
        font-family: 'Inter', 'Segoe UI', sans-serif;
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1c2e 100%);
        border-radius: 16px;
        padding: 20px;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .bracket-conference {
        margin-bottom: 28px;
    }
    .conf-label {
        text-align: center;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        padding: 4px 14px;
        border-radius: 20px;
        display: inline-block;
        margin-bottom: 12px;
    }
    .conf-east { background: rgba(30,144,255,0.2); color: #4da6ff; border: 1px solid rgba(30,144,255,0.4); }
    .conf-west { background: rgba(255,75,75,0.2); color: #ff6b6b; border: 1px solid rgba(255,75,75,0.4); }
    .round-row {
        display: grid;
        gap: 6px;
    }
    .matchup {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        overflow: hidden;
        transition: border-color 0.2s ease;
    }
    .matchup:hover { border-color: rgba(255,255,255,0.2); }
    .team-pick {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 9px 12px;
        cursor: pointer;
        border-radius: 0;
        transition: background 0.15s ease;
        font-size: 0.88rem;
        font-weight: 600;
        color: rgba(255,255,255,0.85);
    }
    .team-pick:hover { background: rgba(255,255,255,0.07); }
    .team-pick.winner {
        background: linear-gradient(90deg, rgba(255,165,0,0.18) 0%, rgba(255,165,0,0.05) 100%);
        color: #ffd700;
        border-left: 3px solid #ffd700;
    }
    .team-pick.loser { opacity: 0.4; }
    .seed-badge {
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: rgba(255,255,255,0.1);
        display: flex;
        align-items: center;
        justify-content:center;
        font-size: 0.72rem;
        font-weight: 700;
        flex-shrink: 0;
        color: rgba(255,255,255,0.7);
    }
    .matchup-divider {
        height: 1px;
        background: rgba(255,255,255,0.06);
        margin: 0;
    }
    .btn-row {
        display: flex;
        gap: 10px;
        margin-top: 16px;
        justify-content: center;
        flex-wrap: wrap;
    }
    .action-btn {
        padding: 10px 22px;
        border-radius: 10px;
        border: none;
        cursor: pointer;
        font-size: 0.88rem;
        font-weight: 700;
        transition: all 0.2s ease;
        display: flex;
        align-items: center;
        gap: 7px;
    }
    .btn-download {
        background: linear-gradient(135deg, #ff4b4b, #c0392b);
        color: white;
        box-shadow: 0 4px 15px rgba(255,75,75,0.35);
    }
    .btn-download:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(255,75,75,0.5); }
    .btn-share {
        background: linear-gradient(135deg, #4da6ff, #1a78c2);
        color: white;
        box-shadow: 0 4px 15px rgba(77,166,255,0.35);
    }
    .btn-share:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(77,166,255,0.5); }
    .btn-reset {
        background: rgba(255,255,255,0.08);
        color: rgba(255,255,255,0.7);
        border: 1px solid rgba(255,255,255,0.15);
    }
    .btn-reset:hover { background: rgba(255,255,255,0.13); }
    .share-box {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 10px;
        padding: 10px 14px;
        font-size: 0.8rem;
        color: #4da6ff;
        word-break: break-all;
        margin-top: 12px;
        display: none;
    }
    .copy-hint {
        font-size: 0.72rem;
        color: rgba(255,255,255,0.4);
        margin-top: 5px;
        text-align: center;
        display: none;
    }
    .finalist-display {
        text-align: center;
        padding: 10px;
        font-size: 0.8rem;
        color: rgba(255,255,255,0.5);
        letter-spacing: 1px;
        text-transform: uppercase;
    }
    .finalist-name {
        font-size: 1rem;
        font-weight: 800;
        color: #ffd700;
        display: block;
        margin-top: 3px;
    }
    .champion-box {
        background: linear-gradient(135deg, rgba(255,215,0,0.15), rgba(255,140,0,0.1));
        border: 1px solid rgba(255,215,0,0.3);
        border-radius: 12px;
        padding: 14px;
        text-align: center;
        margin: 12px 0;
    }
    .champion-label {
        font-size: 0.72rem;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: rgba(255,215,0,0.6);
        margin-bottom: 4px;
    }
    .champion-name {
        font-size: 1.25rem;
        font-weight: 900;
        color: #ffd700;
    }
    .round-header {
        font-size: 0.68rem;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: rgba(255,255,255,0.3);
        margin-bottom: 8px;
        margin-top: 14px;
        text-align: left;
        padding-left: 2px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f'<div class="bracket-title">🏆 {bracket_year} NBA Playoff Bracket</div>', unsafe_allow_html=True)
    st.markdown('<div class="bracket-subtitle">Make your predictions — download or share with friends!</div>', unsafe_allow_html=True)

    shared_param = st.query_params.get("bracket", "")

    components.html(f"""
<!DOCTYPE html>
<html>
<head>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: transparent; font-family: 'Segoe UI', system-ui, sans-serif; }}
#bracket-root {{
    background: linear-gradient(135deg, #0f0f1a 0%, #1a1c2e 100%);
    border-radius: 16px;
    padding: 20px 16px;
    border: 1px solid rgba(255,255,255,0.08);
    color: #fff;
}}
.bracket-inner {{
    display: flex;
    flex-direction: column;
    gap: 0;
}}
.conf-label {{
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding: 3px 12px;
    border-radius: 20px;
    display: inline-block;
    margin-bottom: 10px;
}}
.conf-east {{ background: rgba(30,144,255,0.2); color: #4da6ff; border: 1px solid rgba(30,144,255,0.4); }}
.conf-west {{ background: rgba(255,75,75,0.2); color: #ff6b6b; border: 1px solid rgba(255,75,75,0.4); }}
.conf-section {{
    margin-bottom: 18px;
}}
.round-header {{
    font-size: 0.62rem;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: rgba(255,255,255,0.3);
    margin-bottom: 6px;
    margin-top: 10px;
    padding-left: 2px;
}}
.round-grid {{
    display: grid;
    gap: 6px;
}}
.matchup {{
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    overflow: hidden;
}}
.team-pick {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    cursor: pointer;
    font-size: 0.82rem;
    font-weight: 600;
    color: rgba(255,255,255,0.8);
    transition: background 0.15s;
    user-select: none;
}}
.team-pick:hover {{ background: rgba(255,255,255,0.07); }}
.team-pick.winner {{
    background: linear-gradient(90deg, rgba(255,165,0,0.22) 0%, rgba(255,165,0,0.04) 100%);
    color: #ffd700;
    border-left: 3px solid #ffd700;
}}
.team-pick.loser {{ opacity: 0.38; }}
.seed {{ width: 18px; height: 18px; border-radius: 50%; background: rgba(255,255,255,0.1);
    display: flex; align-items: center; justify-content: center;
    font-size: 0.65rem; font-weight: 700; flex-shrink: 0; color: rgba(255,255,255,0.6); }}
.div-line {{ height: 1px; background: rgba(255,255,255,0.06); }}
.champion-box {{
    background: linear-gradient(135deg, rgba(255,215,0,0.15), rgba(255,140,0,0.1));
    border: 1px solid rgba(255,215,0,0.3);
    border-radius: 12px;
    padding: 12px;
    text-align: center;
    margin: 14px 0;
}}
.champion-label {{ font-size: 0.65rem; letter-spacing: 2px; text-transform: uppercase; color: rgba(255,215,0,0.6); margin-bottom: 3px; }}
.champion-name {{ font-size: 1.15rem; font-weight: 900; color: #ffd700; }}
.finalist-row {{ display: flex; gap: 10px; margin: 10px 0; }}
.finalist-box {{
    flex: 1;
    text-align: center;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 10px;
}}
.finalist-conf {{ font-size: 0.62rem; letter-spacing: 1.5px; text-transform: uppercase; color: rgba(255,255,255,0.35); }}
.finalist-name {{ font-size: 0.9rem; font-weight: 800; color: #fff; margin-top: 4px; min-height: 22px; }}
.finals-trophy {{ text-align: center; font-size: 1.8rem; margin: 6px 0; }}
.btn-row {{ display: flex; gap: 8px; margin-top: 16px; justify-content: center; flex-wrap: wrap; }}
.action-btn {{
    padding: 9px 20px;
    border-radius: 10px;
    border: none;
    cursor: pointer;
    font-size: 0.82rem;
    font-weight: 700;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 6px;
}}
.btn-download {{ background: linear-gradient(135deg, #ff4b4b, #c0392b); color: white; box-shadow: 0 3px 12px rgba(255,75,75,0.4); }}
.btn-download:hover {{ transform: translateY(-1px); box-shadow: 0 5px 18px rgba(255,75,75,0.55); }}
.btn-share {{ background: linear-gradient(135deg, #4da6ff, #1a78c2); color: white; box-shadow: 0 3px 12px rgba(77,166,255,0.4); }}
.btn-share:hover {{ transform: translateY(-1px); box-shadow: 0 5px 18px rgba(77,166,255,0.55); }}
.btn-reset {{ background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.65); border: 1px solid rgba(255,255,255,0.15); }}
.btn-reset:hover {{ background: rgba(255,255,255,0.13); }}
.share-url {{
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(77,166,255,0.3);
    border-radius: 10px;
    padding: 9px 12px;
    font-size: 0.75rem;
    color: #4da6ff;
    word-break: break-all;
    margin-top: 10px;
    cursor: pointer;
    display: none;
}}
.copy-hint {{ font-size: 0.68rem; color: rgba(255,255,255,0.35); margin-top: 4px; text-align: center; display: none; }}
.toast {{
    position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
    background: rgba(30,30,50,0.95); color: #fff; padding: 10px 20px;
    border-radius: 30px; font-size: 0.82rem; border: 1px solid rgba(255,255,255,0.15);
    opacity: 0; transition: opacity 0.3s; pointer-events: none; z-index: 9999;
}}
</style>
</head>
<body>
<div id="bracket-root">
  <div class="bracket-inner" id="capture-area">
    <div id="east-section" class="conf-section"></div>
    <div id="finals-section"></div>
    <div id="west-section" class="conf-section"></div>
  </div>
  <div class="btn-row">
    <button class="action-btn btn-download" onclick="downloadBracket()">⬇ Download Image</button>
    <button class="action-btn btn-share" onclick="shareBracket()">🔗 Share Link</button>
    <button class="action-btn btn-reset" onclick="resetBracket()">↺ Reset</button>
  </div>
  <div id="share-url" class="share-url" onclick="copyUrl()"></div>
  <div id="copy-hint" class="copy-hint">Click to copy</div>
  <div id="toast" class="toast"></div>
</div>

<script>
const EAST_TEAMS = [
  {{name:'Cleveland Cavaliers', seed:1}},
  {{name:'Boston Celtics',      seed:2}},
  {{name:'New York Knicks',     seed:3}},
  {{name:'Milwaukee Bucks',     seed:4}},
  {{name:'Indiana Pacers',      seed:5}},
  {{name:'Miami Heat',          seed:6}},
  {{name:'Detroit Pistons',     seed:7}},
  {{name:'Orlando Magic',       seed:8}},
];
const WEST_TEAMS = [
  {{name:'Oklahoma City Thunder', seed:1}},
  {{name:'Houston Rockets',       seed:2}},
  {{name:'LA Lakers',             seed:3}},
  {{name:'Denver Nuggets',        seed:4}},
  {{name:'LA Clippers',           seed:5}},
  {{name:'Golden State Warriors', seed:6}},
  {{name:'Minnesota Timberwolves',seed:7}},
  {{name:'Memphis Grizzlies',     seed:8}},
];

const SHARED = '{shared_param}';

let state = {{
  east: {{ r1: [null,null,null,null], r2: [null,null], cf: null }},
  west: {{ r1: [null,null,null,null], r2: [null,null], cf: null }},
  champion: null
}};

function loadShared() {{
  if (!SHARED) return;
  try {{
    const decoded = atob(SHARED);
    const parsed = JSON.parse(decoded);
    if (parsed && parsed.east && parsed.west) {{
      state = parsed;
      showToast('📋 Shared bracket loaded!');
    }}
  }} catch(e) {{}}
}}

function saveState() {{
  try {{ localStorage.setItem('hl_bracket_{bracket_year}', JSON.stringify(state)); }} catch(e) {{}}
}}
function loadState() {{
  try {{
    const s = localStorage.getItem('hl_bracket_{bracket_year}');
    if (s) state = JSON.parse(s);
  }} catch(e) {{}}
}}

function getMatchupTeams(conf, round, matchupIdx) {{
  if (round === 0) {{
    const teams = conf === 'east' ? EAST_TEAMS : WEST_TEAMS;
    const pairs = [[0,7],[1,6],[2,5],[3,4]];
    return [teams[pairs[matchupIdx][0]], teams[pairs[matchupIdx][1]]];
  }}
  if (round === 1) {{
    const winners = state[conf].r1;
    const pairs = [[0,1],[2,3]];
    const t1 = winners[pairs[matchupIdx][0]];
    const t2 = winners[pairs[matchupIdx][1]];
    return [t1 ? {{name:t1, seed:'?'}} : null, t2 ? {{name:t2, seed:'?'}} : null];
  }}
  if (round === 2) {{
    const w1 = state[conf].r2[0];
    const w2 = state[conf].r2[1];
    return [w1 ? {{name:w1, seed:'?'}} : null, w2 ? {{name:w2, seed:'?'}} : null];
  }}
  return [null, null];
}}

function pickWinner(conf, round, matchupIdx, teamName) {{
  if (round === 0) {{
    state[conf].r1[matchupIdx] = teamName;
    const checkR1 = state[conf].r1[matchupIdx === 0 || matchupIdx === 1 ? (matchupIdx === 0 ? 1 : 0) : (matchupIdx === 2 ? 3 : 2)];
    // invalidate downstream if changed
    const affectedR2 = matchupIdx < 2 ? 0 : 1;
    if (state[conf].r2[affectedR2] && !state[conf].r1.slice(matchupIdx < 2 ? 0 : 2, matchupIdx < 2 ? 2 : 4).includes(state[conf].r2[affectedR2])) {{
      state[conf].r2[affectedR2] = null;
      state[conf].cf = null;
      state.champion = null;
    }}
  }} else if (round === 1) {{
    state[conf].r2[matchupIdx] = teamName;
    if (state[conf].cf && state[conf].cf !== state[conf].r2[0] && state[conf].cf !== state[conf].r2[1]) {{
      state[conf].cf = null;
      state.champion = null;
    }}
  }} else if (round === 2) {{
    state[conf].cf = teamName;
    if (state.champion && state.champion !== teamName && state.champion !== (conf === 'east' ? state.west.cf : state.east.cf)) {{
      state.champion = null;
    }}
  }} else if (round === 3) {{
    state.champion = teamName;
  }}
  saveState();
  render();
}}

function makeMatchup(conf, round, matchupIdx) {{
  const [t1, t2] = getMatchupTeams(conf, round, matchupIdx);
  const winner = round === 0 ? state[conf].r1[matchupIdx]
               : round === 1 ? state[conf].r2[matchupIdx]
               : round === 2 ? state[conf].cf
               : state.champion;

  const row = (t, isTop) => {{
    if (!t) return `<div class="team-pick" style="opacity:0.3;cursor:default;"><div class="seed">?</div><span>TBD</span></div>`;
    const cls = winner === t.name ? 'winner' : (winner && winner !== t.name ? 'loser' : '');
    const onclick = `pickWinner('${{conf}}',${{round}},${{matchupIdx}},'${{t.name.replace(/'/g,"\\'")}}');event.stopPropagation();`;
    return `<div class="team-pick ${{cls}}" onclick="${{onclick}}"><div class="seed">${{t.seed}}</div><span>${{t.name}}</span></div>`;
  }};
  return `<div class="matchup">${{row(t1,true)}}<div class="div-line"></div>${{row(t2,false)}}</div>`;
}}

function renderConf(conf) {{
  const label = conf === 'east' ? 'Eastern Conference' : 'Western Conference';
  const cls   = conf === 'east' ? 'conf-east' : 'conf-west';
  const r1 = [0,1,2,3].map(i => makeMatchup(conf, 0, i)).join('');
  const r2 = [0,1].map(i => makeMatchup(conf, 1, i)).join('');
  const cf = makeMatchup(conf, 2, 0);
  return `
    <div class="conf-label ${{cls}}">${{label}}</div>
    <div class="round-header">First Round</div>
    <div class="round-grid" style="grid-template-columns:1fr 1fr">${{r1}}</div>
    <div class="round-header">Semifinals</div>
    <div class="round-grid" style="grid-template-columns:1fr 1fr">${{r2}}</div>
    <div class="round-header">Conference Finals</div>
    <div class="round-grid">${{cf}}</div>
  `;
}}

function renderFinals() {{
  const ef = state.east.cf;
  const wf = state.west.cf;
  const champ = state.champion;

  const finalistsHtml = `
    <div class="finalist-row">
      <div class="finalist-box">
        <div class="finalist-conf">East Champion</div>
        <div class="finalist-name">${{ef || '—'}}</div>
      </div>
      <div class="finalist-box">
        <div class="finalist-conf">West Champion</div>
        <div class="finalist-name">${{wf || '—'}}</div>
      </div>
    </div>
  `;

  let champSection = '';
  if (ef && wf) {{
    const finalMatchup = `
      <div class="round-header">NBA Finals — Pick Champion</div>
      ${{makeMatchup('finals_pick', 3, 0)}}
    `;
    // Build custom finals matchup
    const w = champ;
    const r1 = (t, isEast) => {{
      if(!t) return '';
      const cls = w === t ? 'winner' : (w && w !== t ? 'loser' : '');
      const conf = isEast ? 'east_finals' : 'west_finals';
      return `<div class="team-pick ${{cls}}" onclick="pickWinner('',3,0,'${{t.replace(/'/g,"\\'")}}');event.stopPropagation();"><div class="seed">🏆</div><span>${{t}}</span></div>`;
    }};
    champSection = `
      <div class="round-header">🏀 NBA Finals</div>
      <div class="matchup">${{r1(ef,true)}}<div class="div-line"></div>${{r1(wf,false)}}</div>
    `;
    if (champ) {{
      champSection += `
        <div class="champion-box" style="margin-top:10px">
          <div class="champion-label">🏆 Your NBA Champion</div>
          <div class="champion-name">${{champ}}</div>
        </div>
      `;
    }}
  }} else {{
    champSection = `<div style="text-align:center;color:rgba(255,255,255,0.3);font-size:0.8rem;padding:16px 0;">Complete conference predictions to unlock Finals</div>`;
  }}

  return `
    <div style="border-top:1px solid rgba(255,255,255,0.07);border-bottom:1px solid rgba(255,255,255,0.07);padding:14px 0;margin:4px 0;">
      ${{finalistsHtml}}
      ${{champSection}}
    </div>
  `;
}}

function render() {{
  document.getElementById('east-section').innerHTML = renderConf('east');
  document.getElementById('west-section').innerHTML = renderConf('west');
  document.getElementById('finals-section').innerHTML = renderFinals();
}}

function resetBracket() {{
  state = {{ east: {{r1:[null,null,null,null],r2:[null,null],cf:null}}, west: {{r1:[null,null,null,null],r2:[null,null],cf:null}}, champion:null }};
  saveState();
  document.getElementById('share-url').style.display = 'none';
  document.getElementById('copy-hint').style.display = 'none';
  render();
  showToast('Bracket reset!');
}}

function downloadBracket() {{
  const el = document.getElementById('capture-area');
  showToast('⏳ Preparing image...');
  html2canvas(el, {{
    scale: 2.5,
    backgroundColor: '#0f0f1a',
    useCORS: true,
    logging: false
  }}).then(canvas => {{
    const link = document.createElement('a');
    link.download = 'my-nba-bracket-{bracket_year}.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
    showToast('✅ Image downloaded!');
  }}).catch(() => showToast('❌ Download failed. Try again.'));
}}

function shareBracket() {{
  const encoded = btoa(JSON.stringify(state));
  const base = window.parent ? window.parent.location.href.split('?')[0] : location.href.split('?')[0];
  const url = base + '?bracket=' + encoded;
  const box = document.getElementById('share-url');
  const hint = document.getElementById('copy-hint');
  box.textContent = url;
  box.style.display = 'block';
  hint.style.display = 'block';
  copyToClipboard(url);
  showToast('🔗 Link copied to clipboard!');
}}

function copyUrl() {{
  const url = document.getElementById('share-url').textContent;
  copyToClipboard(url);
  showToast('✅ Copied to clipboard!');
}}

function copyToClipboard(text) {{
  try {{ navigator.clipboard.writeText(text); }} catch(e) {{
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position='fixed'; ta.style.opacity='0';
    document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta);
  }}
}}

function showToast(msg) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.opacity = '1';
  setTimeout(() => t.style.opacity = '0', 2500);
}}

// Init
loadState();
if (SHARED) loadShared();
render();
</script>
</body>
</html>
""", height=900, scrolling=True)

    if st.button("Close", type="secondary", key="close_bracket_dialog"):
        st.session_state.active_dialog = None
        st.rerun()


# ==================== 15. ANA SAYFA ====================
def home_page():
    if 'active_dialog' not in st.session_state:
        st.session_state.active_dialog = None

    if st.session_state.active_dialog is None or st.session_state.active_dialog == 'trivia':
        handle_daily_trivia(None)

    # Auto-open bracket if shared link is detected
    shared_bracket = st.query_params.get("bracket", "")
    if shared_bracket and st.session_state.active_dialog is None:
        st.session_state.active_dialog = None
        show_playoff_bracket_dialog()

    render_header()

    score_display_mode = 'full'
    if user:
        user_id = user['id']
        prefs = db.get_user_preferences(user_id)
        score_display_mode = db.get_score_display_preference(user_id)
    else:
        prefs = None
        user_id = None



    date, weights, run = render_sidebar()
    st.session_state['last_weights'] = weights

    if st.session_state.auto_loaded:
        run = True

    if not run:
        st.info("Select parameters and click Run.")
        return

    resolved_date, game_ids = get_last_available_game_date(date)
    if not game_ids:
        st.warning("No NBA games found.")
        return

    games = get_scoreboard(resolved_date)
    st.caption(f"Games from {resolved_date.strftime('%B %d, %Y')}")

    # Sezon arasındaysak seçilen günde maç yoktur; en yakın maç gününü
    # gösterdiğimizi ve sezonun ne zaman başladığını belirt.
    if is_offseason():
        season_start = get_season_start_date()
        days_to_tipoff = (season_start.date() - datetime.now().date()).days
        if days_to_tipoff > 0:
            st.info(f"🏀 {get_season_label()} season tips off in {days_to_tipoff} days "
                    f"({season_start.strftime('%B %d, %Y')}). Showing the most recent "
                    f"completed games — meanwhile, try the Mock Draft to prep.")

    # Playoff Bracket Button
    bracket_col1, bracket_col2, bracket_col3 = st.columns([1, 2, 1])
    with bracket_col2:
        components.html("""
<style>
.playoff-btn-wrap { text-align: center; margin: 8px 0 18px 0; }
</style>
<div class="playoff-btn-wrap">
</div>
""", height=0)
        if st.button(
            "🏆  NBA Playoff Bracket Predictions",
            width='stretch',
            type="primary",
            key="open_bracket_btn",
            help=f"Make your {get_current_season_year()} NBA Playoff predictions, download as an image or share the link!"
        ):
            st.session_state.active_dialog = None
            show_playoff_bracket_dialog()

    col_header1, col_header2 = st.columns([3, 1])
    with col_header1:
        st.subheader("Games")
    with col_header2:
        if user:
            new_mode = st.selectbox(
                "",
                options=['full', 'spoiler_protected'],
                index=0 if score_display_mode == 'full' else 1,
                format_func=lambda x: "Full View" if x == 'full' else "Spoiler Protected",
                key="score_display_selector",
                label_visibility="collapsed"
            )
            if new_mode != score_display_mode:
                if db.update_score_display_preference(user_id, new_mode):
                    score_display_mode = new_mode
                    st.rerun()

    games_to_show = 3
    total_games = len(games)
    visible_games = games if st.session_state.show_all_games else games[:games_to_show]
    num_visible = len(visible_games)

    if num_visible == 0:
        st.info("No games to display.")
    else:
        for row_start in range(0, num_visible, 3):
            row_games = visible_games[row_start:row_start + 3]
            cols = st.columns(len(row_games))

            for i, g in enumerate(row_games):
                with cols[i]:
                    with st.container(border=True):
                        game_id = g.get('game_id', f'game_{i}')
                        game_score = calculate_game_score(g.get('home_score'), g.get('away_score'), g.get('status'))

                        if game_score:
                            score_color = get_score_color(game_score)
                            st.markdown(f"""
                                <div style="display:flex;justify-content:flex-end;margin-bottom:2px;">
                                    <span class="excitement-badge" style="background-color:{score_color};color:white;
                                        padding:3px 9px;border-radius:10px;font-weight:bold;font-size:0.9em;">
                                        ★ {game_score}
                                    </span>
                                </div>
                            """, unsafe_allow_html=True)

                        st.markdown(f"<div style='text-align:center;color:grey;font-size:0.9em;margin-bottom:6px;'>{g.get('status')}</div>", unsafe_allow_html=True)

                        c_away, c_score, c_home = st.columns([1, 1.2, 1])
                        with c_away:
                            st.markdown(f"""
                            <div style="display:flex;flex-direction:column;align-items:center;">
                                <img src="{g.get('away_logo')}" style="width:46px;height:46px;object-fit:contain;">
                                <div style="font-size:0.95em;font-weight:bold;margin-top:4px;text-align:center;">{g.get('away_team')}</div>
                            </div>""", unsafe_allow_html=True)

                        with c_score:
                            if score_display_mode == 'spoiler_protected':
                                st.markdown(f"""
                                    <div style="text-align:center;">
                                        <div class="spoiler-container">
                                            <div class="spoiler-score" id="spoiler_{game_id}"
                                                style='font-size:1.25em;font-weight:800;line-height:2;white-space:nowrap;'>
                                                {g.get('away_score')}&nbsp;-&nbsp;{g.get('home_score')}
                                            </div>
                                            <div class="spoiler-icon" id="icon_{game_id}">🔒</div>
                                        </div>
                                    </div>""", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div style='font-size:1.25em;font-weight:800;text-align:center;line-height:3;white-space:nowrap;'>{g.get('away_score')}&nbsp;-&nbsp;{g.get('home_score')}</div>", unsafe_allow_html=True)

                        with c_home:
                            st.markdown(f"""
                            <div style="display:flex;flex-direction:column;align-items:center;">
                                <img src="{g.get('home_logo')}" style="width:46px;height:46px;object-fit:contain;">
                                <div style="font-size:0.95em;font-weight:bold;margin-top:4px;text-align:center;">{g.get('home_team')}</div>
                            </div>""", unsafe_allow_html=True)

                        st.markdown("<hr style='margin:8px 0;'>", unsafe_allow_html=True)

                        if st.button("Box Score", key=f"btn_{game_id}", width='stretch'):
                            st.session_state.active_dialog = None
                            show_boxscore_dialog(g)

    if total_games > games_to_show:
        if st.session_state.show_all_games:
            if st.button("Show Less", width='stretch', type="secondary"):
                st.session_state.show_all_games = False
                st.rerun()
        else:
            remaining = total_games - games_to_show
            if st.button(f"Show All Games (+{remaining} more)", width='stretch', type="primary"):
                st.session_state.show_all_games = True
                st.rerun()

    st.divider()
    st.subheader("Daily Fantasy Stats")

    all_players = []
    for gid in game_ids:
        box = get_cached_boxscore(gid)
        if box:
            all_players.extend(box)

    if all_players:
        df = pd.DataFrame(all_players)
        num_cols = ["PTS", "REB", "AST", "STL", "BLK", "TO", "FGA", "FGM", "FTA", "FTM", "3Pts"]
        for c in num_cols:
            if c not in df.columns:
                df[c] = 0
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        st.session_state["period_df"] = df.copy()

        if is_pro and user:
            with st.expander("Add Players to Watchlist", expanded=False):
                watchlist = db.get_watchlist(user['id'])
                watchlist_names = [w['player_name'] for w in watchlist]
                available_players = [p for p in df['PLAYER'].unique() if p not in watchlist_names]
                if available_players:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        quick_add_players = st.multiselect("Select players", available_players, key="quick_add_main")
                    with col2:
                        st.write("")
                        st.write("")
                        if st.button("➕ Add", disabled=not quick_add_players, key="quick_add_btn"):
                            for player in quick_add_players:
                                db.add_to_watchlist(user['id'], player, f"Added from Daily Stats - {resolved_date.strftime('%Y-%m-%d')}")
                            st.success(f"Added {len(quick_add_players)} player(s)!")
                            st.rerun()
                else:
                    st.info("All players are already in your watchlist!")
        elif not is_pro:
            st.info("**PRO Feature:** Login with a PRO account to add players to your watchlist!")

        render_tables(df, weights=weights)
    else:
        st.info("No stats available for the selected date.")

    current_period = st.session_state.get("stats_period", "Today")
    if current_period != "Today":
        from components.tables import get_date_range
        date_range = get_date_range(current_period)
        render_mvp_lvp_section(date_range, weights, current_period)


home_page()
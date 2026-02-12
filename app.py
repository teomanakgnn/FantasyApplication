import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import textwrap
import extra_streamlit_components as stx
import time
from services.espn_api import (calculate_game_score, get_score_color)
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
    initial_sidebar_state="expanded"
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
        [data-testid="stStatusWidget"] {display: none !important;}
        [data-testid="stBottom"] {display: none !important;}
        header {display: none !important;}
        #MainMenu {display: none !important;}
        footer {display: none !important;}
        .stDeployButton {display: none !important;}
        .reportview-container .main footer {display: none !important;}
        [data-testid="manage-app-button"] {display: none !important;}
        .viewerBadge_container__r5tak {display: none !important;}
        .stActionButton {display: none !important;}
        .viewerBadge_link__1S137 {display: none !important;}
        .viewerBadge_container__1QSob {display: none !important;}
        [data-testid="stFooter"] {display: none !important;}
        a[href*="github.com/streamlit"] {display: none !important;}
        .stApp > header {display: none !important;}
        div[class*="viewerBadge"] {display: none !important;}
    """

# Mobil uygulama için ek native-hissiyat CSS'i
mobile_native_styles = ""
if mobile_app_mode or native_app_mode:
    mobile_native_styles = """
        /* --- Native App Hissiyatı --- */
        html, body {
            overscroll-behavior: none !important;
            -webkit-overflow-scrolling: touch !important;
        }

        /* Safe area (notch'lu telefonlar) */
        .main .block-container {
            padding-top: max(0.5rem, env(safe-area-inset-top)) !important;
            padding-bottom: max(0.5rem, env(safe-area-inset-bottom)) !important;
            padding-left: max(0.6rem, env(safe-area-inset-left)) !important;
            padding-right: max(0.6rem, env(safe-area-inset-right)) !important;
        }

        /* Seçim ve highlight'ı engelle (native hissi) */
        * {
            -webkit-tap-highlight-color: transparent !important;
        }

        /* Scrollbar gizle (native hissi) */
        ::-webkit-scrollbar {
            width: 0px !important;
            background: transparent !important;
        }

        /* Daha küçük üst boşluk */
        .main .block-container {
            padding-top: 0.5rem !important;
        }
    """

# ==================== 6. GLOBAL CSS ====================
st.markdown(f"""
    <style>
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
            }}
        }}

        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"] {{ display: none !important; }}

        #hooplife-master-trigger {{
            z-index: 999999999 !important;
            transform: translateZ(0);
            will-change: transform, width;
        }}

        .main .block-container {{ padding-top: 1.5rem !important; }}

        @media (max-width: 768px) {{
            .main .block-container {{
                padding-top: 0.75rem !important;
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

            // Pull-to-refresh engelle
            var lastTouchY = 0;
            parentDoc.addEventListener('touchstart', function(e) {
                lastTouchY = e.touches[0].clientY;
            }, {passive: true});
            parentDoc.addEventListener('touchmove', function(e) {
                var touchY = e.touches[0].clientY;
                var scrollTop = parentDoc.documentElement.scrollTop || parentDoc.body.scrollTop;
                if (scrollTop <= 0 && touchY > lastTouchY) {
                    e.preventDefault();
                }
            }, {passive: false});

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

            // Streamlit elementlerini sürekli kontrol et ve gizle
            function hideStreamlitChrome() {
                var selectors = [
                    '[data-testid="stHeader"]',
                    '[data-testid="stToolbar"]',
                    '[data-testid="stDecoration"]',
                    '[data-testid="stStatusWidget"]',
                    '[data-testid="stBottom"]',
                    '#MainMenu',
                    'footer',
                    '.stDeployButton',
                    '[data-testid="manage-app-button"]',
                    '.viewerBadge_container__r5tak',
                    '.stActionButton',
                    '.viewerBadge_link__1S137',
                    '.viewerBadge_container__1QSob',
                    '[data-testid="stFooter"]',
                    'a[href*="github.com/streamlit"]',
                    '.stApp > header',
                    'div[class*="viewerBadge"]'
                ];
                selectors.forEach(function(sel) {
                    var els = parentDoc.querySelectorAll(sel);
                    els.forEach(function(el) {
                        el.style.display = 'none';
                        el.style.visibility = 'hidden';
                        el.style.height = '0';
                    });
                });

                // Metin içeriğine göre "Hosted by Streamlit" vb. yakala (Class değişirse diye)
                var allFooters = parentDoc.querySelectorAll('footer, div, span, a');
                allFooters.forEach(function(el) {
                    if (el.innerText && (el.innerText.includes("Hosted by Streamlit") || el.innerText.includes("Made with Streamlit"))) {
                        // Sadece kısa metinleri gizle (kullanıcı içeriği olmasın)
                        if (el.innerText.length < 100) {
                            el.style.display = 'none';
                            el.style.visibility = 'hidden';
                        }
                    }
                });
            }

            // İlk çalıştırma + periyodik kontrol
            hideStreamlitChrome();
            setInterval(hideStreamlitChrome, 2000);

            // MutationObserver ile yeni eklenen elementleri de yakala
            var observer = new MutationObserver(function() {
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
            trigger.style.cssText = `position:fixed;top:20%;left:0;height:60px;width:45px;
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
                if (isMobile) {
                    Object.assign(trigger.style, {
                        top:'15px', left:'calc(85vw - 50px)',
                        background:'rgba(255,75,75,0.95)', width:'40px', height:'40px',
                        borderRadius:'12px', border:'1px solid rgba(255,255,255,0.25)',
                        borderLeft:'1px solid rgba(255,255,255,0.25)'
                    });
                    trigger.innerHTML = '<div style="position:relative;width:18px;height:18px;"><span style="position:absolute;top:50%;left:0;width:100%;height:2px;background:white;transform:rotate(45deg);"></span><span style="position:absolute;top:50%;left:0;width:100%;height:2px;background:white;transform:rotate(-45deg);"></span></div>';
                } else {
                    trigger.style.display = 'none';
                }
            } else {
                Object.assign(trigger.style, {
                    display:'flex', left:'0', top:'20%', width:'45px', height:'60px',
                    background:'#1a1c24', border:'2px solid #ff4b4b', borderLeft:'none',
                    borderRadius:'0 15px 15px 0'
                });
                trigger.innerHTML = '<div id="hl-icon" style="font-size:26px;transition:transform 0.4s ease;">🏀</div>';
                trigger.onmouseenter = () => { trigger.style.width='60px'; trigger.style.background='#ff4b4b'; };
                trigger.onmouseleave = () => { trigger.style.width='45px'; trigger.style.background='#1a1c24'; };
            }
            trigger.onclick = (e) => { e.preventDefault(); e.stopPropagation(); toggleSidebar(); };
        }
        function init() {
            createHoopLifeDock();
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
            function loop() { if (!isTransitioning) updateVisibility(); animationFrame = requestAnimationFrame(loop); }
            loop();
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
@st.dialog("🏀 Daily NBA Trivia Question", width="small")
def show_trivia_modal(question, user_id=None, current_streak=0):
    st.session_state.active_dialog = 'trivia'

    if st.session_state.get('trivia_success_state', False):
        st.balloons()
        st.success("✅ Correct Answer!")
        st.info(f"ℹ️ {question.get('explanation', '')}")
        if user_id:
            new_streak = db.get_user_streak(user_id)
            st.markdown(f"### 🔥 Current Streak: {new_streak} days!")
        st.caption("See you tomorrow! 👋")
        if st.button("Close", type="primary", key="close_success"):
            st.session_state.pop('trivia_success_state', None)
            st.session_state.pop('trivia_force_open', None)
            st.session_state.active_dialog = None
            st.rerun()
        return

    if st.session_state.get('trivia_error_state', False):
        error_info = st.session_state.get('trivia_error_info', {})
        st.error(f"❌ Wrong. Correct Answer: {error_info.get('correct_option')}) {error_info.get('correct_text')}")
        if error_info.get('explanation'):
            st.info(f"ℹ️ {error_info.get('explanation')}")
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
        icon, text = "🔥", f"{current_streak} Day Streak"
    else:
        badge_style = "background-color:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.1);color:#e0e0e0;"
        icon, text = "🔒", "Login to save your daily streak."

    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.1);">
        <div style="font-weight:600;">📅 {datetime.now().strftime('%d %B')}</div>
        <div style="{badge_style} padding:5px 10px;border-radius:12px;font-size:0.85em;">{icon} {text}</div>
    </div>
    <div style="background:linear-gradient(135deg,#FF4B4B 0%,#8B0000 100%);padding:12px;border-radius:10px;margin-bottom:20px;border:1px solid rgba(255,255,255,0.2);">
        <div style="color:white;font-weight:700;">🎮 PS5 GIVEAWAY!</div>
        <div style="color:rgba(255,255,255,0.9);font-size:0.82rem;margin-top:5px;">
            Reach a <b>50-day streak</b> to enter the draw for a <b>PlayStation 5</b>!<br>
            📅 <b>Draw Date: April 13th</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"#### {question['question']}")

    with st.form("trivia_form", border=False):
        options = {"A": question['option_a'], "B": question['option_b'], "C": question['option_c'], "D": question['option_d']}
        choice = st.radio("Your answer:", list(options.keys()), format_func=lambda x: f"{x}) {options[x]}", index=None)
        submitted = st.form_submit_button("Answer", use_container_width=True, type="primary")

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
        print(f"❌ Trivia handler error: {e}")


# ==================== 10. ADSENSE ====================
def render_adsense():
    try:
        with open("adsense.html", 'r', encoding='utf-8') as f:
            source_code = f.read()
        components.html(source_code, height=300, scrolling=False)
    except FileNotFoundError:
        pass


# ==================== 11. SIDEBAR ====================
st.sidebar.image("HoopLifeNBA_logo.png", use_container_width=True)

with st.sidebar:
    st.markdown("---")

    if is_authenticated and user:
        st.markdown(f"""
            <div style='background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                        padding:1rem;border-radius:10px;margin-bottom:1rem;'>
                <div style='color:white;font-weight:600;font-size:1.1rem;'>👤 {user.get('username','User')}</div>
                <div style='color:rgba(255,255,255,0.8);font-size:0.85rem;'>{user.get('email','')}</div>
            </div>
        """, unsafe_allow_html=True)

        if is_pro:
            st.success("⭐ PRO Member")
            watchlist_count = len(db.get_watchlist(user['id']))
            if st.button(f"My Watchlist ({watchlist_count})", use_container_width=True):
                st.session_state.page = "watchlist"
                st.rerun()
        else:
            st.info("Free Account")
            if st.button("⭐ Upgrade to PRO", use_container_width=True):
                st.info("Contact admin for PRO upgrade")

        if st.button("Logout", use_container_width=True):
            logout_enhanced()
    else:
        st.markdown("""
            <div style='background:linear-gradient(135deg,#f59e0b 0%,#d97706 100%);
                        padding:1rem;border-radius:10px;margin-bottom:1rem;text-align:center;'>
                <div style='color:white;font-weight:600;font-size:1.1rem;margin-bottom:0.5rem;'>🎯 Get More Features</div>
                <div style='color:rgba(255,255,255,0.9);font-size:0.85rem;'>Login to unlock PRO features</div>
            </div>
        """, unsafe_allow_html=True)

        if st.button("🔐 Login / Register", use_container_width=True, type="primary"):
            st.session_state.page = "login"
            st.rerun()

        with st.expander("⭐ PRO Features"):
            st.markdown("""
                - 📋 Player Watchlists
                - 📊 Advanced Analytics
                - 📈 Player Trends
                - 🔔 Custom Alerts
                - 💾 Save Preferences
                - 📥 Export Data
            """)

# ==================== 12. SAYFA YÖNLENDİRMELERİ ====================
if st.session_state.page == "login":
    from auth import render_auth_page_enhanced
    render_auth_page_enhanced()
    st.stop()

if st.session_state.page == "injury":
    from pages.injury_report import render_injury_page
    render_injury_page()
    if st.sidebar.button("⬅️ Back to Home", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()
    st.stop()

if st.session_state.page == "trends":
    if not is_pro:
        st.warning("⭐ This is a PRO feature.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔐 Login / Register", use_container_width=True, type="primary"):
                st.session_state.page = "login"
                st.rerun()
        with col2:
            if st.button("⬅️ Back to Home", use_container_width=True):
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
        st.warning("⭐ Watchlist is a PRO feature.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔐 Login / Register", use_container_width=True, type="primary"):
                st.session_state.page = "login"
                st.rerun()
        with col2:
            if st.button("⬅️ Back to Home", use_container_width=True):
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
        st.markdown("#### ⭐ Quick Add to Watchlist")
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
                        st.success(f"✅ Added {added} player(s)!")
                        st.balloons()
        else:
            st.info("All players already in your watchlist!")
        st.markdown("---")
    elif not is_pro:
        st.info("⭐ Login with a PRO account to add players to your watchlist!")

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
                    st.dataframe(team_df[cols_show], use_container_width=True, hide_index=True, height=400)
                else:
                    st.info(f"No stats available for {team_name}")

        if len(teams) > 0:
            render_team_table(tab1, teams[0])
            if len(teams) > 1:
                render_team_table(tab2, teams[1])
            else:
                with tab2: st.info("Waiting for data...")
    else:
        st.dataframe(df[final_cols], use_container_width=True)


# ==================== 14. ANA SAYFA ====================
def home_page():
    if 'active_dialog' not in st.session_state:
        st.session_state.active_dialog = None

    if st.session_state.active_dialog is None or st.session_state.active_dialog == 'trivia':
        handle_daily_trivia(None)

    render_header()

    score_display_mode = 'full'
    if user:
        user_id = user['id']
        prefs = db.get_user_preferences(user_id)
        score_display_mode = db.get_score_display_preference(user_id)
    else:
        prefs = None
        user_id = None

    if not is_pro:
        st.markdown("---")
        render_adsense()
        st.markdown("---")

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
                                        padding:2px 8px;border-radius:10px;font-weight:bold;font-size:0.78em;">
                                        ★ {game_score}
                                    </span>
                                </div>
                            """, unsafe_allow_html=True)

                        st.markdown(f"<div style='text-align:center;color:grey;font-size:0.8em;margin-bottom:6px;'>{g.get('status')}</div>", unsafe_allow_html=True)

                        c_away, c_score, c_home = st.columns([1, 1.2, 1])
                        with c_away:
                            st.markdown(f"""
                            <div style="display:flex;flex-direction:column;align-items:center;">
                                <img src="{g.get('away_logo')}" style="width:46px;height:46px;object-fit:contain;">
                                <div style="font-size:0.78em;font-weight:bold;margin-top:4px;text-align:center;">{g.get('away_team')}</div>
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
                                <div style="font-size:0.78em;font-weight:bold;margin-top:4px;text-align:center;">{g.get('home_team')}</div>
                            </div>""", unsafe_allow_html=True)

                        st.markdown("<hr style='margin:8px 0;'>", unsafe_allow_html=True)

                        if st.button("Box Score", key=f"btn_{game_id}", use_container_width=True):
                            st.session_state.active_dialog = None
                            show_boxscore_dialog(g)

    if total_games > games_to_show:
        if st.session_state.show_all_games:
            if st.button("⬆️ Show Less", use_container_width=True, type="secondary"):
                st.session_state.show_all_games = False
                st.rerun()
        else:
            remaining = total_games - games_to_show
            if st.button(f"Show All Games (+{remaining} more)", use_container_width=True, type="primary"):
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
            with st.expander("⭐ Add Players to Watchlist", expanded=False):
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
                            st.success(f"✅ Added {len(quick_add_players)} player(s)!")
                            st.rerun()
                else:
                    st.info("All players are already in your watchlist!")
        elif not is_pro:
            st.info("⭐ **PRO Feature:** Login with a PRO account to add players to your watchlist!")

        render_tables(df, weights=weights)
    else:
        st.info("No stats available for the selected date.")

    current_period = st.session_state.get("stats_period", "Today")
    if current_period != "Today":
        from components.tables import get_date_range
        date_range = get_date_range(current_period)
        render_mvp_lvp_section(date_range, weights, current_period)


home_page()
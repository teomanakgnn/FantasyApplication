import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import textwrap
import extra_streamlit_components as stx
import time 
from services.espn_api import (calculate_game_score, get_score_color)
from auth import check_authentication


def cleanup_expired_tokens():
    """Süresi dolmuş tüm token dosyalarını temizle"""
    try:
        home_dir = os.path.expanduser("~")
        token_dir = os.path.join(home_dir, ".hooplife")
        
        if not os.path.exists(token_dir):
            return
        
        import glob
        token_files = glob.glob(os.path.join(token_dir, "auth_token_*.pkl"))
        
        for file_path in token_files:
            try:
                with open(file_path, 'rb') as f:
                    token_data = pickle.load(f)
                
                expiry = datetime.fromisoformat(token_data['expiry'])
                if datetime.now() > expiry:
                    os.remove(file_path)
                    print(f"🧹 Expired token removed: {token_data['username']}")
            except:
                # Bozuk dosyayı sil
                os.remove(file_path)
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")

# app.py başlangıcında çağır
cleanup_expired_tokens()

# app.py en başında (cleanup_expired_tokens()'dan sonra)

# LocalStorage'dan token oku
components.html("""
    <script>
        (function() {
            try {
                const authData = localStorage.getItem('hooplife_auth_data');
                if (authData) {
                    const data = JSON.parse(authData);
                    const expiry = new Date(data.expiry);
                    const now = new Date();
                    
                    if (now < expiry) {
                        // Token geçerli, cookie'ye kopyala
                        document.cookie = `hooplife_auth_token=${data.token}; max-age=${60*60*24*30}; path=/; SameSite=Lax`;
                        console.log('✅ Auth token loaded from localStorage');
                    } else {
                        // Token süresi dolmuş
                        localStorage.removeItem('hooplife_auth_data');
                        console.log('🗑️ Expired token removed from localStorage');
                    }
                }
            } catch(e) {
                console.error('❌ LocalStorage read error:', e);
            }
        })();
    </script>
""", height=0)

def load_token_from_storage():
    """localStorage'dan token'ı yükle"""
    if 'token_loaded' not in st.session_state:
        result = components.html("""
            <div id="token-container" style="display:none;"></div>
            <script>
                (function() {
                    const data = localStorage.getItem('hooplife_auth_data');
                    const container = document.getElementById('token-container');
                    
                    if (data && container) {
                        try {
                            const authData = JSON.parse(data);
                            const expiry = new Date(authData.expiry);
                            const now = new Date();
                            
                            if (now > expiry) {
                                localStorage.removeItem('hooplife_auth_data');
                                container.setAttribute('data-token', 'EXPIRED');
                            } else {
                                container.setAttribute('data-token', authData.token);
                                console.log(' Token yüklendi:', authData.token.substring(0, 15) + '...');
                            }
                        } catch(e) {
                            console.error('Token okuma hatası:', e);
                            container.setAttribute('data-token', 'ERROR');
                        }
                    } else {
                        if (container) container.setAttribute('data-token', 'NONE');
                    }
                })();
            </script>
        """, height=0)
        st.session_state.token_loaded = True


load_token_from_storage()

st.set_page_config(
    page_title="HoopLife NBA", 
    layout="wide",
    page_icon="🏀",
    initial_sidebar_state="expanded"
)


components.html("""
    <script>
        window.addEventListener('message', function(event) {
            if (event.data.type === 'HOOPLIFE_AUTH_TOKEN' && event.data.token) {
                // Streamlit'in session state'ine token'ı gönder
                const stateEvent = new CustomEvent('streamlit:setComponentValue', {
                    detail: {
                        value: {
                            token: event.data.token,
                            savedAt: event.data.savedAt
                        }
                    }
                });
                window.dispatchEvent(stateEvent);
            }
        });
    </script>
""", height=0)

# Token'ı session state'e kaydet
if 'stored_auth_token' not in st.session_state:
    st.session_state.stored_auth_token = None

# Sadece şu fonksiyonu kullanın:
def get_cookie_manager():
    # Eğer session state içinde manager zaten varsa onu döndür (Tekrar oluşturma)
    if 'cookie_manager' in st.session_state:
        return st.session_state.cookie_manager
    
    # Yoksa yeni oluştur ve session state'e kaydet
    # key="nba_cookies" ekleyerek benzersiz olmasını sağlıyoruz
    manager = stx.CookieManager(key="nba_cookies")
    st.session_state.cookie_manager = manager
    return manager

cookie_manager = get_cookie_manager()

# 2. Çerezleri uygulama genelinde SADECE BURADA çekiyoruz
all_cookies = cookie_manager.get_all()

# 3. Yükleme kontrolü (Iframe hızı için kritik)
if all_cookies is None:
    st.info("🏀 HoopLife is loading...")
    st.stop()

# 4. Kimlik kontrolü (Manager'ı değil, çektiğimiz all_cookies'i gönderiyoruz)
is_authenticated = check_authentication(all_cookies)

# Iframe'de çerezlerin yüklenmesi 1 saniye sürebilir, 
# veri gelene kadar uygulamayı bekletmek hata almanı önler.
if all_cookies is None:
    st.info("🏀 HoopLife is loading...")
    st.stop()

# 2. Bu manager'ı auth.py'deki fonksiyona gönder
if not st.session_state.get('authenticated'):
    check_authentication(cookie_manager) # Manager'ı parametre olarak geçiyoruz

st.markdown("""
    <script>
        function revealSpoiler(elementId) {
            const element = document.getElementById(elementId);
            if (element) {
                element.classList.add('revealed');
            }
        }
        
        // Tüm spoiler'ları reveal et
        function revealAllSpoilers() {
            document.querySelectorAll('.spoiler-score').forEach(el => {
                el.classList.add('revealed');
            });
        }
    </script>
""", unsafe_allow_html=True)

def is_embedded():
    return st.query_params.get("embed") == "true"

embed_mode = is_embedded()

# Embed modunda ekstra stil ekle
extra_styles = ""
if embed_mode:
    extra_styles = """
        /* EMBED MODE - Her şeyi gizle */
        [data-testid="stHeader"] {display: none !important;}
        [data-testid="stToolbar"] {display: none !important;}
        header {display: none !important;}
        #MainMenu {display: none !important;}
        footer {display: none !important;}
        .stDeployButton {display: none !important;}
        
        /* Üst padding'i kaldır */
        .main .block-container {
            padding-top: 0.5rem !important;
        }
        
        /* Streamlit watermark */
        [data-testid="stStatusWidget"] {display: none !important;}
        
        /* ALTTAKI FOOTER KISMI */
        [data-testid="stBottom"] {display: none !important;}
        .reportview-container .main footer {display: none !important;}
    """

st.markdown(f"""
    <style>
        /* ============================================
           MOBİL SIDEBAR SCROLL DÜZELTMESİ
           ============================================ */
        
        @media (max-width: 768px) {{
            /* Sidebar'ı scroll edilebilir yap */
            [data-testid="stSidebar"] {{
                position: fixed !important;
                top: 0 !important;
                left: 0 !important;
                height: 100vh !important;
                width: 85vw !important;
                max-width: 320px !important;
                z-index: 999999 !important;
                overflow-y: auto !important;  /* ← ÖNEMLİ */
                overflow-x: hidden !important;
                -webkit-overflow-scrolling: touch !important;  /* ← iOS için smooth scroll */
            }}
            
            /* Sidebar içeriği için scroll container */
            [data-testid="stSidebar"] > div {{
                height: 100% !important;
                overflow-y: auto !important;
                overflow-x: hidden !important;
                -webkit-overflow-scrolling: touch !important;
            }}
            
            /* Sidebar inner content */
            [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
                height: auto !important;
                min-height: 100vh !important;
                overflow-y: visible !important;
                padding-bottom: 60px !important;  /* Alt kısım için ekstra padding */
            }}
            
            /* Kapalı durumda gizle */
            [data-testid="stSidebar"][aria-expanded="false"] {{
                display: none !important;
                transform: translateX(-100%) !important;
            }}
            
            /* Açık durumda göster */
            [data-testid="stSidebar"][aria-expanded="true"] {{
                display: flex !important;
                transform: translateX(0) !important;
            }}
            
            /* Main content mobilde full width */
            [data-testid="stMain"] {{
                margin-left: 0 !important;
                width: 100% !important;
            }}
            
            /* Sidebar backdrop (tıklanınca kapat) */
            [data-testid="stSidebar"][aria-expanded="true"]::before {{
                content: '';
                position: fixed;
                top: 0;
                left: 85vw;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.5);
                z-index: -1;
            }}
        }}
        
        /* ============================================
           SIDEBAR GENEL (MOBİL + DESKTOP)
           ============================================ */
        
        /* Streamlit'in default toggle butonunu gizle */
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"] {{
            display: none !important;
        }}
        
        /* Sidebar temel geçişler */
        [data-testid="stSidebar"] {{
            transition: transform 0.3s ease, width 0.3s ease !important;
        }}
        
        /* ============================================
           HOOPLIFE DOCK
           ============================================ */
        
        #hooplife-master-trigger {{
            z-index: 999999999 !important;
            transform: translateZ(0);
            will-change: transform, width;
        }}
            
        
        @media (max-width: 768px) {{
            #hooplife-master-trigger {{
                width: 40px !important;
            }}
            
            #hooplife-master-trigger #hl-text {{
                display: none !important;
            }}
        }}
        
        /* ============================================
           DİĞER SAYFA ELEMENTLERİ
           ============================================ */
        
        .main .block-container {{
            padding-top: 1.5rem !important;
        }}
        
        @media (max-width: 768px) {{
            .main .block-container {{
                padding-top: 0.75rem !important;
                padding-left: 0.6rem !important;
                padding-right: 0.6rem !important;
            }}
        }}
        
        /* Streamlit header/toolbar/footer gizle */
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        footer,
        [data-testid="stBottom"] {{
            display: none !important;
        }}
        
        {extra_styles}
    </style>
""", unsafe_allow_html=True)

# MOBİL SIDEBAR: SCROLL + BACKDROP CLICK DÜZELTMESİ
# Bu JavaScript bloğunu kullanın
components.html("""
<script>
    (function() {
        'use strict';
        
        var isInitialLoad = true;
        var isTransitioning = false;
        var animationFrame = null;
        
        function saveSidebarState(isClosed) {
            try {
                window.parent.localStorage.setItem('hooplife_sidebar_closed', isClosed ? 'true' : 'false');
                window.parent.localStorage.setItem('hooplife_sidebar_user_closed', isClosed ? 'true' : 'false');
            } catch(e) {}
        }
        
        function getSavedSidebarState() {
            try {
                return window.parent.localStorage.getItem('hooplife_sidebar_closed') === 'true';
            } catch(e) {
                return false;
            }
        }
        
        function wasUserClosed() {
            try {
                return window.parent.localStorage.getItem('hooplife_sidebar_user_closed') === 'true';
            } catch(e) {
                return false;
            }
        }
        
        function getSidebarState() {
            const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
            if (!sidebar) return null;
            
            const rect = sidebar.getBoundingClientRect();
            const computed = window.parent.getComputedStyle(sidebar);
            
            return {
                element: sidebar,
                width: rect.width,
                display: computed.display,
                isClosed: rect.width < 50 || computed.display === 'none',
                transform: computed.transform
            };
        }
        
        function forceSidebarClose() {
            const state = getSidebarState();
            if (!state || state.isClosed) return;
            
            const sidebar = state.element;
            const isMobile = window.parent.innerWidth <= 768;
            
            sidebar.style.transition = 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), width 0.3s ease';
            sidebar.style.width = '0';
            sidebar.style.minWidth = '0';
            sidebar.style.transform = 'translateX(-100%)';
            sidebar.setAttribute('aria-expanded', 'false');
            
            if (isMobile) {
                setTimeout(() => {
                    sidebar.style.display = 'none';
                }, 300);
            }
        }
        
        function toggleSidebar() {
            if (isTransitioning) return;
            
            const state = getSidebarState();
            if (!state) return;
            
            isTransitioning = true;
            const isMobile = window.parent.innerWidth <= 768;
            
            // Buton güncelleme - INSTANT
            requestAnimationFrame(() => updateVisibility(true));
            
            const selectors = [
                '[data-testid="stSidebarCollapsedControl"] button',
                '[data-testid="collapsedControl"] button',
                'button[kind="header"]',
                '[data-testid="baseButton-header"]'
            ];
            
            let clicked = false;
            for (let selector of selectors) {
                const btn = window.parent.document.querySelector(selector);
                if (btn && window.parent.getComputedStyle(btn).display !== 'none') {
                    btn.click();
                    clicked = true;
                    break;
                }
            }
            
            if (!clicked) {
                const sidebar = state.element;
                sidebar.style.transition = 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), width 0.3s ease';
                
                if (state.isClosed) {
                    sidebar.style.width = isMobile ? '85vw' : '336px';
                    sidebar.style.minWidth = isMobile ? '85vw' : '336px';
                    sidebar.style.transform = 'translateX(0)';
                    sidebar.style.display = 'flex';
                    sidebar.setAttribute('aria-expanded', 'true');
                    saveSidebarState(false);
                    
                    if (isMobile) {
                        sidebar.style.overflowY = 'auto';
                        sidebar.style.overflowX = 'hidden';
                        sidebar.style.webkitOverflowScrolling = 'touch';
                    }
                } else {
                    forceSidebarClose();
                    saveSidebarState(true);
                }
            }
            
            setTimeout(() => {
                const finalState = getSidebarState();
                if (finalState) {
                    saveSidebarState(finalState.isClosed);
                }
                isTransitioning = false;
                requestAnimationFrame(() => updateVisibility());
            }, 320);
        }

        function createHoopLifeDock() {
            const oldTrigger = window.parent.document.getElementById('hooplife-master-trigger');
            if (oldTrigger) oldTrigger.remove();
            
            const trigger = window.parent.document.createElement('div');
            trigger.id = 'hooplife-master-trigger';
            
            trigger.style.cssText = `
                position: fixed;
                top: 20%;
                left: 0;
                height: 60px;
                width: 45px;
                background: #1a1c24;
                border: 2px solid #ff4b4b;
                border-left: none;
                border-radius: 0 15px 15px 0;
                z-index: 999999999;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 5px 0 15px rgba(0,0,0,0.4);
                transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
                pointer-events: auto;
                transform: translateZ(0);
                will-change: transform, left, top, width, height, background;
            `;
            
            trigger.innerHTML = `<div id="hl-icon" style="font-size: 26px; transition: transform 0.4s ease; filter: drop-shadow(0 0 5px rgba(255, 75, 75, 0.3));">🏀</div>`;
            
            trigger.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                toggleSidebar();
            });
            
            trigger.addEventListener('mouseenter', () => {
                if (!isTransitioning && getSidebarState()?.isClosed) {
                    trigger.style.width = '60px';
                    trigger.style.background = '#ff4b4b';
                    const icon = trigger.querySelector('#hl-icon');
                    if (icon) icon.style.transform = 'rotate(360deg) scale(1.2)';
                }
            });
            
            trigger.addEventListener('mouseleave', () => {
                if (!isTransitioning && getSidebarState()?.isClosed) {
                    trigger.style.width = '45px';
                    trigger.style.background = '#1a1c24';
                    const icon = trigger.querySelector('#hl-icon');
                    if (icon) icon.style.transform = 'rotate(0deg) scale(1)';
                }
            });
            
            window.parent.document.body.appendChild(trigger);
        }

        function updateVisibility(instant = false) {
            if (animationFrame) {
                cancelAnimationFrame(animationFrame);
            }
            
            const trigger = window.parent.document.getElementById('hooplife-master-trigger');
            if (!trigger) {
                createHoopLifeDock();
                return;
            }
            
            const state = getSidebarState();
            if (!state) return;
            
            const isMobile = window.parent.innerWidth <= 768;
            
            // Transition ayarı
            if (instant) {
                trigger.style.transition = 'all 0.15s cubic-bezier(0.4, 0, 0.2, 1)';
            } else {
                trigger.style.transition = 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)';
            }

            if (!state.isClosed) {
                if (isMobile) {
                    // AÇIK DURUM - MOBİL (Çarpı butonu)
                    Object.assign(trigger.style, {
                        position: 'fixed',
                        top: '15px',
                        left: 'calc(85vw - 50px)',
                        background: 'rgba(255, 75, 75, 0.95)',
                        backdropFilter: 'blur(10px)',
                        width: '40px',
                        height: '40px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: '12px',
                        boxShadow: '0 4px 20px rgba(255, 75, 75, 0.4)',
                        border: '1px solid rgba(255, 255, 255, 0.25)',
                        cursor: 'pointer',
                        pointerEvents: 'auto',
                        borderLeft: '1px solid rgba(255, 255, 255, 0.25)'
                    });

                    trigger.innerHTML = `
                        <div style="position: relative; width: 18px; height: 18px;">
                            <span style="position: absolute; top: 50%; left: 0; width: 100%; height: 2px; background: white; transform: rotate(45deg); border-radius: 1px;"></span>
                            <span style="position: absolute; top: 50%; left: 0; width: 100%; height: 2px; background: white; transform: rotate(-45deg); border-radius: 1px;"></span>
                        </div>
                    `;
                } else {
                    trigger.style.display = 'none';
                }
            } else {
                // KAPALI DURUM (Basketbol butonu)
                Object.assign(trigger.style, {
                    display: 'flex',
                    left: '0',
                    top: '20%',
                    width: '45px',
                    height: '60px',
                    background: '#1a1c24',
                    border: '2px solid #ff4b4b',
                    borderLeft: 'none',
                    borderRadius: '0 15px 15px 0',
                    pointerEvents: 'auto',
                    cursor: 'pointer',
                    backdropFilter: 'none'
                });
                
                trigger.innerHTML = `<div id="hl-icon" style="font-size: 26px; transition: transform 0.4s ease; filter: drop-shadow(0 0 8px rgba(255, 75, 75, 0.5));">🏀</div>`;
                
                trigger.onmouseenter = () => {
                    if (!isTransitioning) {
                        trigger.style.width = '60px';
                        trigger.style.background = '#ff4b4b';
                        const icon = trigger.querySelector('#hl-icon');
                        if (icon) icon.style.transform = 'rotate(360deg) scale(1.2)';
                    }
                };
                
                trigger.onmouseleave = () => {
                    if (!isTransitioning) {
                        trigger.style.width = '45px';
                        trigger.style.background = '#1a1c24';
                        const icon = trigger.querySelector('#hl-icon');
                        if (icon) icon.style.transform = 'rotate(0deg) scale(1)';
                    }
                };
            }
            
            trigger.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                toggleSidebar();
            };
        }
        
        function checkAndFixSidebar() {
            if (isTransitioning) return;
            
            const state = getSidebarState();
            
            if (isInitialLoad) {
                isInitialLoad = false;
                if (wasUserClosed() && state && !state.isClosed) {
                    setTimeout(() => {
                        forceSidebarClose();
                        updateVisibility();
                    }, 400);
                    return;
                }
            }
            
            const shouldBeClosed = getSavedSidebarState();
            if (shouldBeClosed && state && !state.isClosed) {
                setTimeout(() => {
                    forceSidebarClose();
                    updateVisibility();
                }, 500);
            } else if (state) {
                saveSidebarState(state.isClosed);
            }
        }
        
        function init() {
            createHoopLifeDock();
            
            setTimeout(() => {
                checkAndFixSidebar();
                updateVisibility();
            }, 800);
            
            // RequestAnimationFrame ile smooth updates
            function smoothUpdate() {
                if (!isTransitioning) {
                    updateVisibility();
                }
                animationFrame = requestAnimationFrame(smoothUpdate);
            }
            smoothUpdate();
            
            // Resize listener
            let resizeTimer;
            window.parent.addEventListener('resize', () => {
                clearTimeout(resizeTimer);
                resizeTimer = setTimeout(() => updateVisibility(true), 100);
            });
            
            // MutationObserver - sidebar değişikliklerini izle
            const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
            if (sidebar) {
                const observer = new MutationObserver(() => {
                    if (!isTransitioning) {
                        requestAnimationFrame(() => updateVisibility());
                    }
                });
                
                observer.observe(sidebar, {
                    attributes: true,
                    attributeFilter: ['style', 'aria-expanded', 'class']
                });
            }
        }
        
        if (window.parent.document.readyState === 'loading') {
            window.parent.document.addEventListener('DOMContentLoaded', init);
        } else {
            init();
        }
    })();
</script>
""", height=0, width=0)


st.markdown("""
    <div style="display: none;">
        HoopLife NBA: Günlük NBA oyuncu istatistikleri, fantasy basketbol analizleri, 
        canlı maç skorları, MVP/LVP sıralamaları ve oyuncu trendleri için en kapsamlı 
        basketbol analiz platformu.
    </div>
""", unsafe_allow_html=True)

st.markdown("""
    <script async src="https://www.googletagmanager.com/gtag/js?id=AW-17915489918"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());

      gtag('config', 'AW-17915489918');
    </script>
""", unsafe_allow_html=True)


st.markdown("""
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-3882980321453628"
     crossorigin="anonymous"></script>
<ins class="adsbygoogle"
     style="display:block"
     data-ad-client="ca-pub-3882980321453628"
     data-ad-slot="REKLAM_ID_BURAYA"
     data-ad-format="auto"
     data-full-width-responsive="true"></ins>
<script>
     (adsbygoogle = window.adsbygoogle || []).push({});
</script>
""", unsafe_allow_html=True)



# --------------------
# TRIVIA LOGIC (GÜNCELLENMİŞ - COOKIE DESTEKLİ)
# --------------------

@st.dialog("🏀 Daily NBA Trivia Question", width="small")
def show_trivia_modal(question, user_id=None, current_streak=0):
    st.session_state.active_dialog = 'trivia'
    
    # --- 1. BAŞARI EKRANI (DOĞRU CEVAP VERİLDİYSE) ---
    if st.session_state.get('trivia_success_state', False):
        st.balloons()
        st.success("✅ Correct Answer!")
        st.info(f"ℹ️ {question.get('explanation', '')}")
        
        # Streak göster
        if user_id:
            new_streak = db.get_user_streak(user_id)
            st.markdown(f"### 🔥 Current Streak: {new_streak} days!")
        
        st.caption("See you tomorrow! 👋")
        
        if st.button("Close", type="primary", key="close_success"):
            del st.session_state['trivia_success_state']
            if 'trivia_force_open' in st.session_state:
                del st.session_state['trivia_force_open']
            st.session_state.active_dialog = None
            st.rerun()
        return
        
    # --- 2. HATA EKRANI (YANLIŞ CEVAP VERİLDİYSE) ---
    if st.session_state.get('trivia_error_state', False):
        error_info = st.session_state.get('trivia_error_info', {})
        st.error(f"❌ Wrong. Correct Answer: {error_info.get('correct_option')}) {error_info.get('correct_text')}")
        if error_info.get('explanation'):
            st.info(f"ℹ️ {error_info.get('explanation')}")
        
        if user_id:
            st.warning("💔 Your streak has been reset.")
        
        st.caption("Better luck tomorrow! 👋")
        
        if st.button("Close", type="primary", key="close_error"):
            del st.session_state['trivia_error_state']
            del st.session_state['trivia_error_info']
            if 'trivia_force_open' in st.session_state:
                del st.session_state['trivia_force_open']
            st.session_state.active_dialog = None
            st.rerun()
        return

    # --- 3. HTML BAŞLIK VE KAMPANYA BANNER ---
    if user_id:
        badge_style = "background-color: rgba(255, 75, 75, 0.15); border: 1px solid rgba(255, 75, 75, 0.3); color: #ff4b4b;"
        icon = "🔥"
        text = f"{current_streak} Day Streak"
    else:
        badge_style = "background-color: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.1); color: #e0e0e0;"
        icon = "🔒"
        text = "Login to save your daily streak."

    # Üst Bilgi Satırı
    header_html = f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.1);">
        <div style="font-weight: 600; font-size: 1rem;">
            📅 {datetime.now().strftime('%d %B')}
        </div>
        <div style="{badge_style} padding: 5px 10px; border-radius: 12px; font-size: 0.85em; display: flex; align-items: center; gap: 5px;">
            <span>{icon}</span> {text}
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    # PS5 Kampanya Banner (Buraya eklendi)
    campaign_html = """
    <div style="background: linear-gradient(135deg, #FF4B4B 0%, #8B0000 100%); 
                padding: 12px; border-radius: 10px; margin-bottom: 20px; 
                border: 1px solid rgba(255,255,255,0.2); box-shadow: 0 4px 15px rgba(255,75,75,0.2);">
        <div style="color: white; font-weight: 700; font-size: 0.95rem; display: flex; align-items: center; gap: 8px;">
            🎮 PS5 GIVEAWAY!
        </div>
        <div style="color: rgba(255,255,255,0.9); font-size: 0.82rem; margin-top: 5px; line-height: 1.4;">
            Reach a <b>50-day streak</b> to enter the draw for a chance to win a <b>PlayStation 5</b>! 
            Register now to start your streak. <br>
            📅 <b>Draw Date: April 13th</b>
        </div>
    </div>
    """
    st.markdown(campaign_html, unsafe_allow_html=True)
    
    # --- 4. SORU VE FORM ---
    st.markdown(f"#### {question['question']}")
    
    with st.form("trivia_form", border=False):
        options = {"A": question['option_a'], "B": question['option_b'], "C": question['option_c'], "D": question['option_d']}
        choice = st.radio("Your answer:", list(options.keys()), format_func=lambda x: f"{x}) {options[x]}", index=None)
        submitted = st.form_submit_button("Answer", use_container_width=True, type="primary")
        
    # ... (form submission logic - geri kalan kod aynı kalabilir)
        
    if submitted:
        if not choice:
            st.warning("Please select an option.")
            st.stop()
        
        is_correct = (choice == question['correct_option'])
        today_str = str(datetime.now().date())
        
        if not user_id:
            cookie_manager = get_cookie_manager()
        
        if is_correct:
            # Doğru cevap
            if user_id:
                db.mark_user_trivia_played(user_id)
            else:
                unique_key = f"set_correct_{int(datetime.now().timestamp())}"
                cookie_manager.set('guest_trivia_date', today_str, key=unique_key)
                st.session_state[f'trivia_played_{today_str}'] = True

            st.session_state['trivia_success_state'] = True
            st.session_state['trivia_force_open'] = True
            st.rerun()
            
        else:
            # Yanlış cevap
            if user_id:
                db.mark_user_trivia_played(user_id)
            else:
                unique_key = f"set_wrong_{int(datetime.now().timestamp())}"
                cookie_manager.set('guest_trivia_date', today_str, key=unique_key)
                st.session_state[f'trivia_played_{today_str}'] = True
            
            correct_text = options[question['correct_option']]
            st.session_state['trivia_error_state'] = True
            st.session_state['trivia_error_info'] = {
                'correct_option': question['correct_option'],
                'correct_text': correct_text,
                'explanation': question.get('explanation', '')
            }
            st.session_state['trivia_force_open'] = True
            st.rerun()

# app.py içindeki fonksiyon tanımı
def handle_daily_trivia(all_cookies): # all_cookies dışarıdan geliyor
    active = st.session_state.get('active_dialog')
    if active is not None and active != 'trivia':
        return
    
    # 1. Soru verisi kontrolü
    trivia = db.get_daily_trivia()
    if not trivia:
        return

    # 2. Temel Değişkenleri Başlat (Hatanın çözümü burası)
    today_str = str(datetime.now().date())
    current_user = st.session_state.get('user')
    force_open = st.session_state.get('trivia_force_open', False)
    should_show = False
    streak = 0
    u_id = None # u_id burada tanımlandı, artık hata vermez
    
    session_played_key = f'trivia_played_{today_str}'
    session_played = st.session_state.get(session_played_key, False)

    # -------------------------------------------------------
    # SENARYO A: GİRİŞ YAPMIŞ KULLANICI
    # -------------------------------------------------------
    if current_user:
        u_id = current_user['id']
        has_played = db.check_user_played_trivia_today(u_id)
        
        if force_open: 
            should_show = True
            streak = db.get_user_streak(u_id)
        elif not has_played: 
            should_show = True
            streak = db.get_user_streak(u_id)
        else: 
            should_show = False

    # -------------------------------------------------------
    # SENARYO B: MİSAFİR KULLANICI (Çerez Kullanımı)
    # -------------------------------------------------------
    else:
        if session_played:
            should_show = force_open
        else:
            # ÖNEMLİ: cookie_manager.get_all() yerine parametre gelen all_cookies kullanılıyor
            last_played_cookie = all_cookies.get('guest_trivia_date') if all_cookies else None

            if force_open:
                should_show = True
            elif last_played_cookie == today_str:
                st.session_state[session_played_key] = True
                should_show = False
            else:
                should_show = True
                streak = 0

    # 3. Karar verildiyse Modalı Aç
    if should_show:
        show_trivia_modal(trivia, u_id, streak)

def render_adsense():
    try:
        with open("adsense.html", 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # Height'i artıralım ki reklam görünsün
        components.html(source_code, height=300, scrolling=False)
        
    except FileNotFoundError:
        st.error("adsense.html dosyası bulunamadı!")


# Authentication kontrolü (opsiyonel)
from auth import check_authentication, logout

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
from services.database import db

try:
    from services.scoring import calculate_scores
except ImportError:
    pass 

def is_embedded():
    return st.query_params.get("embed") == "true"

# --------------------
# INIT & STYLES
# --------------------
embed_mode = is_embedded()

# Embed modunda ekstra stil ekle
extra_styles = ""
if embed_mode:
    extra_styles = """
        /* EMBED MODE - Her şeyi gizle */
        [data-testid="stHeader"] {display: none !important;}
        [data-testid="stToolbar"] {display: none !important;}
        header {display: none !important;}
        #MainMenu {display: none !important;}
        footer {display: none !important;}
        .stDeployButton {display: none !important;}
        
        /* Üst padding'i kaldır */
        .main .block-container {
            padding-top: 0.5rem !important;
        }
        
        /* Streamlit watermark */
        [data-testid="stStatusWidget"] {display: none !important;}
        
        /* ALTTAKI FOOTER KISMI */
        [data-testid="stBottom"] {display: none !important;}
        .reportview-container .main footer {display: none !important;}
    """

# --------------------
# STYLES & CSS
# --------------------
st.markdown(f"""
    <style>
        /* 1. TEMEL SAYFA DÜZENİ */
        .main .block-container {{
            padding-top: 1.5rem !important;
        }}
        
        /* 2. GEREKSİZ ELEMENTLERİ GİZLE */
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {{
            display: none !important;
        }}
        
        /* 3. SIDEBAR TOGGLE - Streamlit default gizleme + custom btn */
        [data-testid="stSidebarCollapsedControl"] {{
            display: none !important;
            pointer-events: none !important;
        }}

        #st-sidebar-toggle-btn {{
            position: fixed !important;
            top: 14px !important;
            left: 10px !important;
            z-index: 9999999 !important;
            width: 38px !important;
            height: 38px !important;
            background: rgba(14, 17, 23, 0.93) !important;
            border: 1px solid rgba(255,255,255,0.35) !important;
            border-radius: 8px !important;
            color: #fff !important;
            font-size: 1.2rem !important;
            line-height: 38px !important;
            text-align: center !important;
            cursor: pointer !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.4) !important;
            transition: background 0.2s, border-color 0.2s !important;
            user-select: none !important;
            -webkit-user-select: none !important;
        }}
        #st-sidebar-toggle-btn:hover {{
            background: #ff4b4b !important;
            border-color: #ff4b4b !important;
        }}

        #sidebar-toggle-btn:hover {{
            background: #ff4b4b;
            border-color: #ff4b4b;
        }}
                
        /* 4. FOOTER VE DİĞER ELEMENTLER */
        [data-testid="stStatusWidget"],
        footer,
        [data-testid="stBottom"] {{
            display: none !important;
        }}
        
 /* ============================================
   SPOILER PROTECTION STYLES - İYİLEŞTİRİLMİŞ
   ============================================ */

        .spoiler-score {{
            filter: blur(10px);
            transition: filter 0.4s ease;
            cursor: pointer;
            user-select: none;
            position: relative;
        }}

        .spoiler-score:hover {{
            filter: blur(6px);
        }}

        .spoiler-score.revealed {{
            filter: blur(0px) !important;
            cursor: default;
        }}

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

        .spoiler-container:hover {{
            background: linear-gradient(135deg, rgba(255,75,75,0.15) 0%, rgba(139,0,0,0.15) 100%);
            border-color: rgba(255,75,75,0.5);
            transform: scale(1.02);
        }}

        .spoiler-icon {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 1.8em;
            opacity: 1;
            pointer-events: none;
            transition: opacity 0.3s ease;
            z-index: 2;
        }}

        .spoiler-icon.hidden {{
            opacity: 0 !important;
            display: none !important;
        }}

        /* Heyecan puanı badge - her zaman görünür */
        .excitement-badge {{
            filter: none !important;
            cursor: default !important;
        }}

        @media (max-width: 768px) {{
            .spoiler-score {{
                filter: blur(8px);
            }}
            .spoiler-container {{
                padding: 6px 12px;
            }}
            .spoiler-icon {{
                font-size: 1.5em;
            }}
        }}
            
        {extra_styles}


        /* ============================================================
           MOBİL RESPONSIVE — @media (max-width: 768px)
           Desktop'ta hiçbir şey değişmez. Sadece dar ekranlarda aktive olur.
           ============================================================ */

        /* --- GENEL SAYFA --- */
        @media (max-width: 768px) {{
            .main .block-container {{
                padding-top: 0.75rem !important;
                padding-left: 0.6rem !important;
                padding-right: 0.6rem !important;
            }}
        }}

        /* --- GAME CARD GRID: 3 sütun → 1 sütun --- */
        @media (max-width: 768px) {{
            /* Streamlit st.columns → flex wrap ile 1 sütun yap */
            .stColumns {{
                flex-wrap: wrap !important;
            }}
            .stColumns > div {{
                flex: 1 1 100% !important;
                max-width: 100% !important;
                min-width: 100% !important;
            }}
        }}

        /* --- GAME CARD İÇİ: away / score / home satırı --- */
        @media (max-width: 768px) {{
            .game-card-row {{
                flex-direction: row !important;   /* yine yatay kalsın */
                align-items: center !important;
                justify-content: space-between !important;
            }}
            .game-card-row > div {{
                flex: 1 !important;
            }}
        }}

        /* --- GAME SCORE BADGE (★ score) --- */
        @media (max-width: 768px) {{
            .game-score-badge {{
                position: relative !important;
                top: auto !important;
                right: auto !important;
                display: inline-block !important;
                margin-bottom: 4px !important;
                float: right !important;
            }}
        }}

        /* --- SCOREBOARD: team logo + name stacking --- */
        @media (max-width: 768px) {{
            .team-block {{
                display: flex !important;
                flex-direction: column !important;
                align-items: center !important;
            }}
            .team-block img {{
                width: 42px !important;
                height: 42px !important;
            }}
            .team-block .team-label {{
                font-size: 0.78em !important;
                margin-top: 3px !important;
                text-align: center !important;
            }}
            .score-block {{
                font-size: 1.25em !important;
                font-weight: 800 !important;
                text-align: center !important;
                white-space: nowrap !important;
            }}
        }}

        /* --- BOX SCORE DIALOG: full-width on mobile --- */
        @media (max-width: 768px) {{
            /* Streamlit dialog overlay */
            [data-testid="stDialog"] {{
                width: 100vw !important;
                max-width: 100vw !important;
                margin: 0 !important;
                border-radius: 12px 12px 0 0 !important;
                max-height: 90vh !important;
                overflow-y: auto !important;
            }}
        }}

        /* --- GAME HEADER İN DIALOG (away logo - score - home logo) --- */
        @media (max-width: 768px) {{
            .game-header-container {{
                padding: 12px 8px !important;
                flex-direction: row !important;
                align-items: center !important;
                justify-content: space-between !important;
            }}
            .game-header-container .team-info {{
                width: 28% !important;
            }}
            .game-header-container .team-info img {{
                width: 44px !important;
            }}
            .game-header-container .team-name {{
                font-size: 0.78rem !important;
                margin-top: 4px !important;
            }}
            .game-header-container .score-board {{
                width: 44% !important;
            }}
            .game-header-container .main-score {{
                font-size: 1.7rem !important;
            }}
            .game-header-container .game-status {{
                font-size: 0.7rem !important;
                padding: 2px 8px !important;
            }}
        }}

        /* --- DATAFRAME (boxscore table): horizontal scroll + küçük font --- */
        @media (max-width: 768px) {{
            .stDataframe,
            [data-testid="stDataframe"] {{
                overflow-x: auto !important;
                -webkit-overflow-scrolling: touch !important;
            }}
            .stDataframe table,
            [data-testid="stDataframe"] table {{
                font-size: 0.75rem !important;
                min-width: 520px !important;
            }}
            .stDataframe th,
            [data-testid="stDataframe"] th {{
                padding: 4px 6px !important;
                font-size: 0.72rem !important;
            }}
            .stDataframe td,
            [data-testid="stDataframe"] td {{
                padding: 4px 6px !important;
            }}
        }}

        /* --- SIDEBAR: mobilde daha kompakt --- */
        @media (max-width: 768px) {{
            [data-testid="stSidebar"] {{
                width: 85vw !important;
                max-width: 320px !important;
            }}
            [data-testid="stSidebar"] .stButton button {{
                font-size: 0.85rem !important;
                padding: 0.4rem 0.6rem !important;
            }}
        }}

        /* --- TRIVIA MODAL: radio label font küçüt --- */
        @media (max-width: 768px) {{
            .trivia-modal .stRadio label {{
                font-size: 0.88rem !important;
            }}
            .trivia-modal .stForm button {{
                font-size: 0.95rem !important;
            }}
        }}

        /* --- "Show All / Show Less" BUTTON: tam genişlik --- */
        @media (max-width: 768px) {{
            .show-all-btn-row {{
                flex-direction: column !important;
            }}
            .show-all-btn-row > div {{
                width: 100% !important;
            }}
        }}

        /* --- ADSENSE CONTAINER: mobilde height azalt --- */
        @media (max-width: 768px) {{
            .adsense-container iframe,
            .adsense-container {{
                max-height: 200px !important;
            }}
        }}

        /* --- SUBHEADER / DIVIDER SPACING --- */
        @media (max-width: 768px) {{
            h2, h3 {{
                margin-top: 0.6rem !important;
                margin-bottom: 0.3rem !important;
            }}
            hr {{
                margin: 0.5rem 0 !important;
            }}
        }}

        /* --- PRO FEATURE EXPANDER: kompakt --- */
        @media (max-width: 768px) {{
            .streamlit-expander {{
                margin: 0.3rem 0 !important;
            }}
            .streamlit-expander .stMarkdown li {{
                font-size: 0.82rem !important;
                margin: 0.15rem 0 !important;
            }}
        }}

        /* --- QUICK ADD COLUMNS: stack on mobile --- */
        @media (max-width: 480px) {{
            .quick-add-row {{
                flex-direction: column !important;
            }}
            .quick-add-row > div {{
                width: 100% !important;
                flex: none !important;
            }}
        }}
    </style>
""", unsafe_allow_html=True)

load_styles()

if "auto_loaded" not in st.session_state:
    st.session_state.auto_loaded = True

if "page" not in st.session_state:
    st.session_state.page = "home"

if "show_all_games" not in st.session_state:
    st.session_state.show_all_games = False

if "slider_index" not in st.session_state:
    st.session_state.slider_index = 0

# Check if user is authenticated (opsiyonel)
is_authenticated = check_authentication(cookie_manager)
user = st.session_state.get('user', None)
is_pro = user.get('is_pro', False) if user else False


st.sidebar.image(
        "HoopLifeNBA_logo.png",             # Resim yolu veya URL'si
        use_container_width=True   # Sidebar genişliğine otomatik sığdırır
    )

# Sidebar - User Section
with st.sidebar:
    st.markdown("---")
    
    if is_authenticated and user:
        # Logged in user
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
                <div style='color: white; font-weight: 600; font-size: 1.1rem;'>
                    👤 {user.get('username', 'User')}
                </div>
                <div style='color: rgba(255,255,255,0.8); font-size: 0.85rem;'>
                    {user.get('email', '')}
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Pro status
        if is_pro:
            st.success("⭐ PRO Member")
            
            # Watchlist quick access
            watchlist_count = len(db.get_watchlist(user['id']))
            if st.button(f" My Watchlist ({watchlist_count})", use_container_width=True):
                st.session_state.page = "watchlist"
                st.rerun()
        else:
            st.info(" Free Account")
            if st.button("⭐ Upgrade to PRO", use_container_width=True):
                st.info("Contact admin for PRO upgrade")
        
        # Logout button
        if st.button(" Logout", use_container_width=True, type="secondary"):
            logout()
    else:
        # Not logged in - show login/register option
        st.markdown("""
            <div style='background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); 
                        padding: 1rem; border-radius: 10px; margin-bottom: 1rem; text-align: center;'>
                <div style='color: white; font-weight: 600; font-size: 1.1rem; margin-bottom: 0.5rem;'>
                    🎯 Get More Features
                </div>
                <div style='color: rgba(255,255,255,0.9); font-size: 0.85rem;'>
                    Login to unlock PRO features
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔐 Login / Register", use_container_width=True, type="primary"):
            st.session_state.page = "login"
            st.rerun()
        
        # Quick feature preview
        with st.expander("⭐ PRO Features"):
            st.markdown("""
                - 📋 Player Watchlists
                - 📊 Advanced Analytics
                - 📈 Player Trends
                - 🔔 Custom Alerts
                - 💾 Save Preferences
                - 📥 Export Data
            """)

# Sayfa yönlendirmesi
if st.session_state.page == "login":
    from auth import render_auth_page
    render_auth_page()
    st.stop()

if st.session_state.page == "injury":
    from pages.injury_report import render_injury_page
    render_injury_page()
    if st.sidebar.button("⬅️ Back to Home", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()
    st.stop()


if st.session_state.page == "trends":
    # PRO kontrolü
    if not is_pro:
        st.warning("⭐ This is a PRO feature. Login and upgrade to access player trends.")
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
    # PRO kontrolü
    if not is_pro:
        st.warning("⭐ Watchlist is a PRO feature. Login and upgrade to access.")
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

# Custom CSS for the Modal/Dialog
st.markdown("""
    <style>
    .game-header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        border: 1px solid #e0e0e0;
        color: #000;
    }
    .team-info {
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 30%;
    }
    .team-name {
        font-weight: 700;
        font-size: 1.1rem;
        margin-top: 8px;
        text-align: center;
    }
    .score-board {
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 40%;
    }
    .main-score {
        font-size: 2.5rem;
        font-weight: 800;
        font-family: 'Arial', sans-serif;
        color: #333;
    }
    .game-status {
        background-color: #e3f2fd;
        color: #1565c0;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-top: 5px;
    }
    .watchlist-btn {
        background-color: #fbbf24;
        color: #000;
        border: none;
        padding: 0.3rem 0.6rem;
        border-radius: 4px;
        font-size: 0.75rem;
        cursor: pointer;
        font-weight: 600;
    }
    .watchlist-btn:hover {
        background-color: #f59e0b;
    }
    .pro-feature-badge {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }
    @media (prefers-color-scheme: dark) {
        .game-header-container { background-color: #262730; border-color: #444; color: #fff; }
        .main-score { color: #fff; }
        .game-status { background-color: #333; color: #90caf9; }
    }
    </style>
""", unsafe_allow_html=True)


# --------------------
# POP-UP (DIALOG) FUNCTION WITH WATCHLIST
# --------------------
@st.dialog("Game Details", width="large")
def show_boxscore_dialog(game_info):
    st.session_state.active_dialog = 'boxscore'
    game_id = game_info['game_id']
    
    # 1. Header
    html_header = f"""
    <div class="game-header-container">
        <div class="team-info">
            <img src="{game_info.get('away_logo')}" width="60">
            <div class="team-name">{game_info.get('away_team')}</div>
        </div>
        <div class="score-board">
            <div class="main-score">
                {game_info.get('away_score')} - {game_info.get('home_score')}
            </div>
            <div class="game-status">{game_info.get('status')}</div>
        </div>
        <div class="team-info">
            <img src="{game_info.get('home_logo')}" width="60">
            <div class="team-name">{game_info.get('home_team')}</div>
        </div>
    </div>
    """
    st.markdown(html_header, unsafe_allow_html=True)

    # 2. Data Loading
    with st.spinner("Loading stats..."):
        players = get_cached_boxscore(game_id)
    
    if not players:
        st.warning("Box score details are not available yet.")
        return

    # 3. Data Processing
    df = pd.DataFrame(players)
    
    numeric_cols = ["PTS", "REB", "AST", "STL", "BLK", "TO", "FGM", "FGA", "3Pts", "3PTA", "FTM", "FTA"]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        else:
            df[c] = 0

    df["FG"] = df.apply(lambda x: f"{int(x['FGM'])}-{int(x['FGA'])}", axis=1)
    df["3PT"] = df.apply(lambda x: f"{int(x['3Pts'])}-{int(x['3PTA'])}", axis=1)
    df["FT"] = df.apply(lambda x: f"{int(x['FTM'])}-{int(x['FTA'])}", axis=1)

    if "MIN" not in df.columns:
        df["MIN"] = "--"

    display_cols = ["PLAYER", "MIN", "FG", "3PT", "FT", "PTS", "REB", "AST", "STL", "BLK", "TO"]
    final_cols = [c for c in display_cols if c in df.columns]

    # 4. PRO FEATURE: Add to Watchlist
    if is_pro and user:
        st.markdown("#### ⭐ Quick Add to Watchlist")
        
        # Get existing watchlist
        watchlist = db.get_watchlist(user['id'])
        watchlist_names = [w['player_name'] for w in watchlist]
        
        # Select players to add
        available_players = df['PLAYER'].unique().tolist()
        players_to_add = [p for p in available_players if p not in watchlist_names]
        
        if players_to_add:
            col1, col2 = st.columns([3, 1])
            with col1:
                selected_players = st.multiselect(
                    "Select players to add",
                    players_to_add,
                    help="Players already in your watchlist are not shown"
                )
            with col2:
                st.write("")
                st.write("")
                if st.button("➕ Add Selected", disabled=not selected_players):
                    added_count = 0
                    for player in selected_players:
                        if db.add_to_watchlist(user['id'], player, f"Added from {game_info.get('away_team')} vs {game_info.get('home_team')}"):
                            added_count += 1
                    
                    if added_count > 0:
                        st.success(f"✅ Added {added_count} player(s) to watchlist!")
                        st.balloons()
        else:
            st.info("All players from this game are already in your watchlist!")
        
        st.markdown("---")
    elif not is_pro:
        # Show PRO teaser
        st.info("⭐ Login with a PRO account to add players to your watchlist directly from here!")

    # 5. Tabs & Tables
    if "TEAM" in df.columns:
        teams = df["TEAM"].unique()
        
        tab1, tab2 = st.tabs([f"Away: {game_info.get('away_team')}", f"Home: {game_info.get('home_team')}"])
        
        def render_team_table(container, team_name):
            with container:
                team_df = df[df["TEAM"].astype(str).str.contains(team_name, case=False, na=False)].copy()
                
                if not team_df.empty:
                    if "MIN" in team_df.columns:
                        team_df = team_df.sort_values(
                            by="MIN", 
                            ascending=False,
                            key=lambda x: pd.to_numeric(x, errors='coerce').fillna(0)
                        )
                    
                    # Add watchlist indicators for PRO users
                    if is_pro and user:
                        watchlist = db.get_watchlist(user['id'])
                        watchlist_names = [w['player_name'] for w in watchlist]
                        team_df['⭐'] = team_df['PLAYER'].apply(lambda x: '⭐' if x in watchlist_names else '')
                        display_cols_with_star = ['⭐'] + final_cols
                    else:
                        display_cols_with_star = final_cols
                    
                    st.dataframe(
                        team_df[display_cols_with_star],
                        use_container_width=True,
                        hide_index=True,
                        height=400,
                        column_config={
                            "⭐": st.column_config.TextColumn("", width="small"),
                            "PTS": st.column_config.NumberColumn("PTS", format="%d"),
                            "MIN": st.column_config.TextColumn("MIN", width="small"),
                            "FG": st.column_config.TextColumn("FG (M-A)", width="small"),
                            "3PT": st.column_config.TextColumn("3PT (M-A)", width="small"),
                            "FT": st.column_config.TextColumn("FT (M-A)", width="small"),
                            "PLAYER": st.column_config.TextColumn("Player", width="medium"),
                        }
                    )
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


# --------------------
# MAIN PAGE
# --------------------

def home_page():
    if 'active_dialog' not in st.session_state:
        st.session_state.active_dialog = None
    
    # Only show trivia if no other dialog is active
    if st.session_state.active_dialog is None or st.session_state.active_dialog == 'trivia':
        handle_daily_trivia(all_cookies)
    render_header()
    
    # Load user preferences if logged in
    score_display_mode = 'full'  # Default
    if user:
        user_id = user['id']
        prefs = db.get_user_preferences(user_id)
        score_display_mode = db.get_score_display_preference(user_id)
    else:
        prefs = None

    if not is_pro:
        st.markdown("---")
        render_adsense()
        st.markdown("---")    
    
    # Sidebar'dan weights'i de alıyoruz
    date, weights, run = render_sidebar()
    st.session_state['last_weights'] = weights
    
    # Override with saved preferences if available
    if prefs and prefs.get('default_weights'):
        import json
        saved_weights = json.loads(prefs['default_weights']) if isinstance(prefs['default_weights'], str) else prefs['default_weights']

    if st.session_state.auto_loaded:
        run = True

    if not run:
        st.info("Select parameters and click Run.")
        return

    # 1. LOAD GAMES
    resolved_date, game_ids = get_last_available_game_date(date)
    if not game_ids:
        st.warning("No NBA games found.")
        return

    games = get_scoreboard(resolved_date)
    st.caption(f"Games from {resolved_date.strftime('%B %d, %Y')}")

    # 2. SCOREBOARD GRID HEADER
    col_header1, col_header2 = st.columns([3, 1])
    with col_header1:
        st.subheader("Games")
    with col_header2:
        if user:
            # Spoiler Protection JavaScript
            st.markdown("""
                <script>
                    function revealSpoiler(elementId) {
                        const element = document.getElementById(elementId);
                        if (element) {
                            element.classList.add('revealed');
                        }
                    }
                </script>
            """, unsafe_allow_html=True)
            
            # Kullanıcı giriş yapmışsa tercih seçeneği göster
            new_mode = st.selectbox(
                "",
                options=['full', 'spoiler_protected'],
                index=0 if score_display_mode == 'full' else 1,
                format_func=lambda x: "Full View" if x == 'full' else "Spoiler Protected",
                key="score_display_selector",
                label_visibility="collapsed"
            )
            
            # Tercih değiştiyse kaydet
            if new_mode != score_display_mode:
                if db.update_score_display_preference(user_id, new_mode):
                    score_display_mode = new_mode
                    st.rerun()
    
    games_to_show = 3
    total_games = len(games)

    if st.session_state.page == "trade_analyzer":
        from pages.trade_analyzer import render_trade_analyzer_page
        render_trade_analyzer_page()
        st.stop()
    
    if st.session_state.show_all_games:
        visible_games = games
    else:
        visible_games = games[:games_to_show]

    num_visible = len(visible_games)
    
    if num_visible == 0:
         st.info("No games to display.")
    else:
        # Mobile column fix script
        st.markdown("""
            <script>
                (function() {
                    function fixColumns() {
                        if (window.innerWidth <= 768) {
                            document.querySelectorAll('.stColumns').forEach(function(row) {
                                row.style.flexWrap = 'wrap';
                                row.querySelectorAll(':scope > div').forEach(function(col) {
                                    col.style.flex = '1 1 100%';
                                    col.style.maxWidth = '100%';
                                    col.style.minWidth = '100%';
                                });
                            });
                        }
                    }
                    fixColumns();
                    window.addEventListener('resize', fixColumns);
                    new MutationObserver(fixColumns).observe(document.body, {childList: true, subtree: true});
                })();
            </script>
        """, unsafe_allow_html=True)

        for row_start in range(0, num_visible, 3):
            row_games = visible_games[row_start:row_start + 3]
            cols = st.columns(len(row_games))
            
            for i, g in enumerate(row_games):
                with cols[i]:
                    with st.container(border=True):
                        game_id = g.get('game_id', f'game_{i}')
                        
                        # --- HEYECAN PUANI - HER ZAMAN GÖRÜNÜR ---
                        game_score = calculate_game_score(g.get('home_score'), g.get('away_score'), g.get('status'))
                        
                        if game_score:
                            score_color = get_score_color(game_score)
                            # excitement-badge class'ı ile blur'dan muaf
                            st.markdown(f"""
                                <div style="
                                    display: flex; 
                                    justify-content: flex-end; 
                                    margin-bottom: 2px;
                                ">
                                    <span class="excitement-badge" style="
                                        background-color: {score_color}; 
                                        color: white; 
                                        padding: 2px 8px; 
                                        border-radius: 10px; 
                                        font-weight: bold; 
                                        font-size: 0.78em; 
                                        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                                        display: inline-block;
                                    ">
                                        ★ {game_score}
                                    </span>
                                </div>
                            """, unsafe_allow_html=True)

                        # Status
                        st.markdown(f"<div style='text-align:center; color:grey; font-size:0.8em; margin-bottom:6px;'>{g.get('status')}</div>", unsafe_allow_html=True)
                        
                        # --- SKORLAR ---
                        c_away, c_score, c_home = st.columns([1, 1.2, 1])
                        
                        with c_away:
                            st.markdown(f"""
                            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center;">
                                <img src="{g.get('away_logo')}" style="width: 46px; height: 46px; object-fit: contain;">
                                <div style="font-size:0.78em; font-weight:bold; margin-top: 4px; text-align:center; line-height:1.2;">{g.get('away_team')}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with c_score:
                            if score_display_mode == 'spoiler_protected':
                                spoiler_id = f"spoiler_{game_id}"
                                icon_id = f"icon_{game_id}"
                                
                                st.markdown(f"""
                                    <div style="text-align:center;">
                                        <div class="spoiler-container" data-game-id="{game_id}">
                                            <div class="spoiler-score" id="{spoiler_id}" style='font-size:1.25em; font-weight:800; line-height: 2; white-space: nowrap;'>
                                                {g.get('away_score')}&nbsp;-&nbsp;{g.get('home_score')}
                                            </div>
                                            <div class="spoiler-icon" id="{icon_id}">🔒</div>
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)
                            else:
                                # FULL VIEW - Normal skor
                                st.markdown(f"<div style='font-size:1.25em; font-weight:800; text-align:center; line-height: 3; white-space: nowrap;'>{g.get('away_score')}&nbsp;-&nbsp;{g.get('home_score')}</div>", unsafe_allow_html=True)
                        
                        # ← BU KISIM EKSİKTİ!
                        with c_home:
                            st.markdown(f"""
                            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center;">
                                <img src="{g.get('home_logo')}" style="width: 46px; height: 46px; object-fit: contain;">
                                <div style="font-size:0.78em; font-weight:bold; margin-top: 4px; text-align:center; line-height:1.2;">{g.get('home_team')}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
                        
                        if st.button(" Box Score", key=f"btn_{game_id}", use_container_width=True):
                            st.session_state.active_dialog = None
                            show_boxscore_dialog(g)     
    


    st.markdown("""
        <script>
            function handleReveal(gameId) {
                const scoreElement = document.getElementById('spoiler_' + gameId);
                const iconElement = document.getElementById('icon_' + gameId);
                
                if (scoreElement) {
                    scoreElement.classList.add('revealed');
                }
                if (iconElement) {
                    iconElement.style.display = 'none';
                }
            }
        </script>
    """, unsafe_allow_html=True)


    # Show All / Show Less
    if total_games > games_to_show:
        if st.session_state.show_all_games:
            if st.button("⬆️ Show Less", use_container_width=True, type="secondary"):
                st.session_state.show_all_games = False
                st.rerun()
        else:
            remaining = total_games - games_to_show
            if st.button(f" Show All Games (+{remaining} more)", use_container_width=True, type="primary"):
                st.session_state.show_all_games = True
                st.rerun()

    st.divider()

    # 3. FANTASY TABLE (All Players) WITH WATCHLIST ACTIONS
    st.subheader("Daily Fantasy Stats")
    
    all_players = []
    for gid in game_ids:
        box = get_cached_boxscore(gid)
        if box: all_players.extend(box)

    if all_players:
        df = pd.DataFrame(all_players)
        
        num_cols = ["PTS", "REB", "AST", "STL", "BLK", "TO", "FGA", "FGM", "FTA", "FTM", "3Pts"]
        for c in num_cols:
            if c not in df.columns: df[c] = 0
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        st.session_state["period_df"] = df.copy()
            

        # PRO FEATURE: Quick add from main table
        if is_pro and user:
            with st.expander("⭐ Add Players to Watchlist", expanded=False):
                watchlist = db.get_watchlist(user['id'])
                watchlist_names = [w['player_name'] for w in watchlist]
                
                available_players = [p for p in df['PLAYER'].unique() if p not in watchlist_names]
                
                if available_players:
                    # Mobilde stack, desktopda yan yana
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        quick_add_players = st.multiselect(
                            "Select players",
                            available_players,
                            key="quick_add_main"
                        )
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
            st.info("⭐ **PRO Feature:** Login with a PRO account to add players to your watchlist and track their performance!")

        render_tables(df, weights=weights) 
    else:
        st.info("No stats available for the selected date.")

    current_period = st.session_state.get("stats_period", "Today")
    
    # Only show MVP/LVP for periods longer than "Today"
    if current_period != "Today":
        from components.tables import get_date_range
        date_range = get_date_range(current_period)
        render_mvp_lvp_section(date_range, weights, current_period)
    

home_page()



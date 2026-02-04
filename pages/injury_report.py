import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime
import streamlit.components.v1 as components

# Üst dizini path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.espn_api import get_injuries


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
        
        var triggerElement = null;
        var backdropElement = null;
        var isInitialLoad = true;  // ← YENİ: İlk yükleme kontrolü
        
        // LocalStorage kullanarak sidebar durumunu sakla
        function saveSidebarState(isClosed) {
            try {
                window.parent.localStorage.setItem('hooplife_sidebar_closed', isClosed ? 'true' : 'false');
                // Sayfa değişikliklerinde kullanmak için ayrı bir flag
                window.parent.localStorage.setItem('hooplife_sidebar_user_closed', isClosed ? 'true' : 'false');
            } catch(e) {
                console.log('LocalStorage kullanılamıyor');
            }
        }
        
        function getSavedSidebarState() {
            try {
                return window.parent.localStorage.getItem('hooplife_sidebar_closed') === 'true';
            } catch(e) {
                return false;
            }
        }
        
        // Kullanıcının manuel olarak kapatıp kapatmadığını kontrol et
        function wasUserClosed() {
            try {
                return window.parent.localStorage.getItem('hooplife_sidebar_user_closed') === 'true';
            } catch(e) {
                return false;
            }
        }
        
        // SIDEBAR DURUMUNU KONTROL ET
        function getSidebarState() {
            const sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
            if (!sidebar) return null;
            
            const rect = sidebar.getBoundingClientRect();
            const computed = window.parent.getComputedStyle(sidebar);
            
            return {
                element: sidebar,
                width: rect.width,
                display: computed.display,
                isClosed: rect.width < 50 || computed.display === 'none'
            };
        }
        
        // SIDEBAR'I ZORLA KAPAT
        function forceSidebarClose() {
            const state = getSidebarState();
            if (!state || state.isClosed) return;
            
            const sidebar = state.element;
            const isMobile = window.parent.innerWidth <= 768;
            
            sidebar.style.width = '0';
            sidebar.style.minWidth = '0';
            sidebar.style.transform = 'translateX(-100%)';
            sidebar.setAttribute('aria-expanded', 'false');
            
            if (isMobile) {
                sidebar.style.display = 'none';
            }
        }
        
        // SIDEBAR'I AÇ/KAPA
        function toggleSidebar() {
            const state = getSidebarState();
            if (!state) return;
            
            const isMobile = window.parent.innerWidth <= 768;
            
            // YÖNTEM 1: Toggle butonunu bul ve tıkla
            const selectors = [
                '[data-testid="stSidebarCollapsedControl"] button',
                '[data-testid="collapsedControl"] button',
                'button[kind="header"]',
                '[data-testid="baseButton-header"]'
            ];
            
            for (let selector of selectors) {
                const btn = window.parent.document.querySelector(selector);
                if (btn && window.parent.getComputedStyle(btn).display !== 'none') {
                    btn.click();
                    
                    if (isMobile) {
                        setTimeout(() => {
                            const newState = getSidebarState();
                            if (newState && newState.isClosed === state.isClosed) {
                                btn.click();
                            }
                        }, 200);
                    }
                    
                    // Toggle gerçekleştikten SONRA durumu kaydet
                    setTimeout(() => {
                        const finalState = getSidebarState();
                        if (finalState) {
                            saveSidebarState(finalState.isClosed);
                        }
                    }, 400);
                    return;
                }
            }
            
            // YÖNTEM 2: Keyboard event
            const keyEvent = new KeyboardEvent('keydown', {
                key: '[',
                code: 'BracketLeft',
                keyCode: 219,
                bubbles: true
            });
            window.parent.document.dispatchEvent(keyEvent);
            
            // YÖNTEM 3: Direct DOM manipulation
            setTimeout(() => {
                const finalState = getSidebarState();
                if (finalState && finalState.isClosed === state.isClosed) {
                    const sidebar = finalState.element;
                    
                    if (state.isClosed) {
                        // Aç
                        sidebar.style.width = isMobile ? '85vw' : '336px';
                        sidebar.style.minWidth = isMobile ? '85vw' : '336px';
                        sidebar.style.transform = 'translateX(0)';
                        sidebar.style.display = 'flex';
                        sidebar.setAttribute('aria-expanded', 'true');
                        saveSidebarState(false);
                        
                        // MOBİL: Scroll'u enable et
                        if (isMobile) {
                            sidebar.style.overflowY = 'auto';
                            sidebar.style.overflowX = 'hidden';
                            sidebar.style.webkitOverflowScrolling = 'touch';
                            
                            const innerContainers = sidebar.querySelectorAll('div');
                            innerContainers.forEach(container => {
                                if (container.getAttribute('data-testid') === 'stSidebarContent') {
                                    container.style.overflowY = 'visible';
                                    container.style.height = 'auto';
                                    container.style.minHeight = '100vh';
                                }
                            });
                        }
                    } else {
                        // Kapat
                        forceSidebarClose();
                        saveSidebarState(true);
                    }
                }
            }, 300);
        }
        
        let hoopLifeTrigger = null;

        function createHoopLifeDock() {
            const oldTrigger = window.parent.document.getElementById('hooplife-master-trigger');
            if (oldTrigger) {
                oldTrigger.remove();
            }
            
            const triggerElement = window.parent.document.createElement('div');
            triggerElement.id = 'hooplife-master-trigger';
            hoopLifeTrigger = triggerElement;
            
            triggerElement.style.cssText = `
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
                transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                pointer-events: auto;
            `;
            
            triggerElement.innerHTML = `
                <div id="hl-icon" style="
                    font-size: 26px; 
                    transition: transform 0.5s ease;
                    filter: drop-shadow(0 0 5px rgba(255, 75, 75, 0.3));
                ">🏀</div>
            `;
            
            triggerElement.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                toggleSidebar(); 
                setTimeout(updateVisibility, 100);
            });
            
            triggerElement.addEventListener('mouseenter', function() {
                triggerElement.style.width = '60px';
                triggerElement.style.background = '#ff4b4b';
                const icon = triggerElement.querySelector('#hl-icon');
                if (icon) icon.style.transform = 'rotate(360deg) scale(1.2)';
            });
            
            triggerElement.addEventListener('mouseleave', function() {
                triggerElement.style.width = '45px';
                triggerElement.style.background = '#1a1c24';
                const icon = triggerElement.querySelector('#hl-icon');
                if (icon) icon.style.transform = 'rotate(0deg) scale(1)';
            });
            
            window.parent.document.body.appendChild(triggerElement);
        }

        function updateVisibility() {
            const trigger = window.parent.document.getElementById('hooplife-master-trigger');
            if (!trigger) {
                createHoopLifeDock();
                return;
            }
            
            const state = getSidebarState(); 
            if (!state) return;
            
            const isMobile = window.parent.innerWidth <= 768;

            if (!state.isClosed) {
                if (isMobile) {
                    Object.assign(trigger.style, {
                        position: 'fixed',
                        top: '15px',
                        left: 'calc(100% - 60px)',
                        background: 'rgba(255, 75, 75, 0.9)',
                        backdropFilter: 'blur(8px)',
                        width: '40px',
                        height: '40px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: '12px',
                        boxShadow: '0 4px 15px rgba(255, 75, 75, 0.3)',
                        border: '1px solid rgba(255, 255, 255, 0.2)',
                        cursor: 'pointer',
                        pointerEvents: 'auto',
                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
                    });

                    trigger.innerHTML = `
                        <div class="close-icon-wrapper" style="position: relative; width: 16px; height: 16px;">
                            <span style="position: absolute; top: 50%; width: 100%; height: 1.5px; background: white; transform: rotate(45deg); transition: 0.3s;"></span>
                            <span style="position: absolute; top: 50%; width: 100%; height: 1.5px; background: white; transform: rotate(-45deg); transition: 0.3s;"></span>
                        </div>
                    `;
                    
                    trigger.onclick = function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        toggleSidebar();
                        setTimeout(updateVisibility, 100);
                    };
                } else {
                    trigger.style.display = 'none';
                }
            } else {
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
                    cursor: 'pointer'
                });
                
                trigger.innerHTML = `
                    <div id="hl-icon" style="font-size: 26px; filter: drop-shadow(0 0 8px rgba(255, 75, 75, 0.5));">🏀</div>
                `;
                
                trigger.onclick = function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    toggleSidebar();
                    setTimeout(updateVisibility, 100);
                };
                
                trigger.onmouseenter = function() {
                    trigger.style.width = '60px';
                    trigger.style.background = '#ff4b4b';
                    const icon = trigger.querySelector('#hl-icon');
                    if (icon) icon.style.transform = 'rotate(360deg) scale(1.2)';
                };
                
                trigger.onmouseleave = function() {
                    trigger.style.width = '45px';
                    trigger.style.background = '#1a1c24';
                    const icon = trigger.querySelector('#hl-icon');
                    if (icon) icon.style.transform = 'rotate(0deg) scale(1)';
                };
            }
        }
        
        // ← YENİ: Sayfa değişikliğinde sidebar durumunu koru
        function checkAndFixSidebar() {
            const state = getSidebarState();
            
            // İLK YÜKLEME: Kullanıcı daha önce kapattıysa kapalı tut
            if (isInitialLoad) {
                isInitialLoad = false;
                
                if (wasUserClosed() && state && !state.isClosed) {
                    setTimeout(() => {
                        forceSidebarClose();
                        updateVisibility();
                    }, 300); // ← Biraz daha gecikme ekle
                    return;
                }
            }
            
            // SONRAKI KONTROLLER: Normal senkronizasyon
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
            
            // İlk kontrolü biraz geciktir - Streamlit'in sidebar'ı render etmesini bekle
            setTimeout(() => {
                checkAndFixSidebar();
                updateVisibility();
            }, 800); // ← 500ms'den 800ms'ye çıkar
            
            // Periyodik kontrol
            setInterval(() => {
                checkAndFixSidebar();
                updateVisibility();
            }, 1000);
            
            window.parent.addEventListener('resize', updateVisibility);
        }
        
        if (window.parent.document.readyState === 'loading') {
            window.parent.document.addEventListener('DOMContentLoaded', init);
        } else {
            init();
        }
        
    })();
</script>
""", height=0, width=0)
# -----------------------------------------------------------------------------
# CSS & STYLING (NBA PROFESSIONAL THEME)
# -----------------------------------------------------------------------------
def load_professional_styles():
    st.markdown("""
    <style>
        /* STREAMLIT HEADER GIZLE */
        header[data-testid="stHeader"] {
            display: none;
        }
        
        /* BACKGROUND IMAGE */
        .stApp {
            background-image: linear-gradient(rgba(0, 0, 0, 0.85), rgba(0, 0, 0, 0.85)), 
                              url('https://cloudfront-us-east-1.images.arcpublishing.com/opb/TRWU3XOQHNHHBLKLDFZIC42W7A.jpg');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            background-repeat: no-repeat;
        }
        
        /* GENEL AYARLAR */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            background-color: transparent;
        }
        
        /* METRIC KARTLARI */
        div[data-testid="stMetric"] {
            background-color: rgba(255, 255, 255, 0.95);
            border: 1px solid rgba(224, 224, 224, 0.5);
            padding: 15px;
            border-radius: 4px;
            border-left: 4px solid #17408B;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            backdrop-filter: blur(10px);
        }
        div[data-testid="stMetric"] label {
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.8rem;
            color: #6c757d;
        }

        /* SIDEBAR TEAM CARD */
        .sidebar-team-card {
            background-color: rgba(248, 249, 250, 0.95);
            border: 1px solid rgba(222, 226, 230, 0.6);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            transition: all 0.2s;
            cursor: pointer;
            backdrop-filter: blur(10px);
        }
        .sidebar-team-card:hover {
            background-color: rgba(233, 236, 239, 0.95);
            border-color: #17408B;
            transform: translateX(3px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
        .sidebar-team-logo {
            width: 35px;
            height: 35px;
            margin-right: 12px;
        }
        .sidebar-team-info {
            flex: 1;
        }
        .sidebar-team-name {
            font-weight: 700;
            font-size: 0.9rem;
            color: #212529;
            margin: 0;
        }
        .sidebar-team-count {
            font-size: 0.75rem;
            color: #6c757d;
            margin-top: 2px;
        }
        .sidebar-injury-badge {
            background-color: #C9082A;
            color: white;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.7rem;
            font-weight: 700;
        }

        /* TEAM HEADER */
        .team-header-container {
            display: flex;
            align-items: center;
            background-color: rgba(29, 29, 29, 0.95);
            color: white;
            padding: 15px 20px;
            margin-top: 30px;
            margin-bottom: 15px;
            border-radius: 2px;
            border-bottom: 3px solid #C9082A;
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        .team-logo-img {
            width: 45px;
            height: 45px;
            margin-right: 15px;
            filter: drop-shadow(0 0 2px rgba(255,255,255,0.2));
        }
        .team-title {
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-size: 1.4rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin: 0;
        }

        /* PLAYER CARD - GÜNCELLENMİŞ SABİT BOYUT */
        .player-card {
            background-color: rgba(255, 255, 255, 0.95);
            border: 1px solid rgba(225, 228, 232, 0.6);
            border-radius: 6px;
            padding: 0;
            margin-bottom: 15px;
            transition: transform 0.2s, box-shadow 0.2s;
            height: 320px;
            display: flex;
            flex-direction: column;
            backdrop-filter: blur(10px);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
            position: relative;
            overflow: hidden;
        }
        
        .player-card:hover {
            border-color: #b0b0b0;
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.25);
            transform: translateY(-2px);
        }
        
        /* CARD DETAILS - SCROLLABLE AREA */
        .card-details {
            padding: 12px 15px;
            background-color: rgba(248, 249, 250, 0.95);
            font-size: 0.85rem;
            color: #495057;
            line-height: 1.4;
            border-top: 1px solid rgba(238, 238, 238, 0.5);
            flex: 1;
            overflow-y: auto;
        }
        
        /* Scrollbar */
        .card-details::-webkit-scrollbar {
            width: 4px;
        }
        .card-details::-webkit-scrollbar-thumb {
            background-color: #ccc;
            border-radius: 4px;
        }
        
        /* Yeni haber ikonu */
        .new-badge {
            position: absolute;
            top: 10px;
            right: 10px;
            background-color: #C9082A;
            color: white;
            font-size: 0.6rem;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 4px;
            z-index: 10;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        .card-top {
            display: flex;
            padding: 15px;
            border-bottom: 1px solid #f0f0f0;
        }
        .p-photo {
            width: 60px;
            height: 60px;
            border-radius: 2px;
            object-fit: cover;
            border: 1px solid #ddd;
            background-color: #f9f9f9;
        }
        .p-info {
            margin-left: 15px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .p-name {
            font-size: 1.05rem;
            font-weight: 700;
            color: #212529;
            line-height: 1.2;
        }
        .p-meta {
            font-size: 0.8rem;
            color: #6c757d;
            margin-top: 4px;
            font-weight: 500;
            text-transform: uppercase;
        }

        /* STATUS BADGES */
        .status-badge {
            display: inline-block;
            padding: 4px 10px;
            font-size: 0.75rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: white;
            margin-top: 10px;
            width: 100%;
            text-align: center;
        }
        .bg-out { background-color: #C9082A; }
        .bg-questionable { background-color: #E0A800; color: black; }
        .bg-doubtful { background-color: #FD7E14; }
        .bg-day-to-day { background-color: #17408B; }
        
        .injury-date {
            font-size: 0.75rem;
            color: #868e96;
            font-style: italic;
            margin-top: 8px;
            display: block;
        }
        
        /* PAGE HEADER */
        .main-header {
            font-family: 'Helvetica Neue', sans-serif;
            font-weight: 900;
            font-size: 2.2rem;
            text-transform: uppercase;
            color: #ffffff;
            padding: 20px;
            border-radius: 2px;
            border-left: 6px solid #17408B;
            margin-bottom: 10px;
            letter-spacing: 1px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.7);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
        }
        .sub-header {
            color: #e9ecef;
            font-size: 0.95rem;
            margin-top: 0px;
            margin-bottom: 30px;
            font-weight: 500;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.7);
            padding-left: 26px;
            letter-spacing: 0.5px;
        }
        
        /* DARK MODE */
        @media (prefers-color-scheme: dark) {
            .player-card { background-color: #262730; border-color: #444; }
            .p-name { color: #fff; }
            .card-details { background-color: #1f2026; color: #bbb; border-top-color: #333; }
            .main-header { color: white; }
            div[data-testid="stMetric"] { background-color: #262730; border-color: #444; }
            .sidebar-team-card { background-color: #262730; border-color: #444; }
            .sidebar-team-card:hover { background-color: #1f2026; }
            .sidebar-team-name { color: #fff; }
        }
    </style>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SIDEBAR
# -----------------------------------------------------------------------------
def render_injury_sidebar(df):
    """Sidebar with team filters and stats"""
    
    total_injuries = len(df)
    st.sidebar.markdown("### 📋 Team Breakdown")
    
    team_stats = df.groupby(['team', 'team_name', 'team_logo']).size().reset_index(name='count')
    team_stats = team_stats.sort_values('team')
    
    if 'selected_injury_team' not in st.session_state:
        st.session_state.selected_injury_team = "ALL TEAMS"
    
    if st.sidebar.button("All Teams", key="all_teams_btn", use_container_width=True, 
                         type="primary" if st.session_state.selected_injury_team == "ALL TEAMS" else "secondary"):
        st.session_state.selected_injury_team = "ALL TEAMS"
        st.rerun()
    
    st.sidebar.markdown("---")
    
    for _, row in team_stats.iterrows():
        team_abbr = row['team']
        team_name = row['team_name']
        team_logo = row['team_logo']
        injury_count = row['count']
        
        st.sidebar.markdown(f"""
        <div class="sidebar-team-card">
            <img src="{team_logo}" class="sidebar-team-logo">
            <div class="sidebar-team-info">
                <div class="sidebar-team-name">{team_abbr}</div>
                <div class="sidebar-team-count">{team_name}</div>
            </div>
            <div class="sidebar-injury-badge">{injury_count}</div>
        </div>
        """, unsafe_allow_html=True)
        
        button_type = "primary" if st.session_state.selected_injury_team == team_abbr else "secondary"
        if st.sidebar.button(f"View {team_abbr}", key=f"team_{team_abbr}", 
                             use_container_width=True, type=button_type):
            st.session_state.selected_injury_team = team_abbr
            st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ℹ️ Status Legend")
    st.sidebar.markdown("""
    - 🔴 **Out**: Will not play
    - 🟡 **Questionable**: Game-time decision
    - 🟠 **Doubtful**: Unlikely to play
    - 🔵 **Day-to-Day**: Status pending
    """)
    
    return st.session_state.selected_injury_team

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def get_status_style(status):
    s = status.lower()
    if "out" in s: return "bg-out"
    if "questionable" in s: return "bg-questionable"
    if "doubtful" in s: return "bg-doubtful"
    if "day" in s: return "bg-day-to-day"
    return "bg-out"

def format_injury_date(date_str):
    """Format injury update date to readable format"""
    if not date_str:
        return "Date unknown"
    
    try:
        injury_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        now = datetime.now(injury_date.tzinfo)
        
        diff = now - injury_date
        
        if diff.days == 0:
            hours = diff.seconds // 3600
            if hours == 0:
                minutes = diff.seconds // 60
                return f"{minutes}m ago" if minutes > 0 else "Just now"
            return f"{hours}h ago"
        elif diff.days == 1:
            return "Yesterday"
        elif diff.days < 7:
            return f"{diff.days}d ago"
        else:
            return injury_date.strftime("%b %d, %Y")
            
    except Exception:
        try:
            injury_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return injury_date.strftime("%b %d, %Y")
        except:
            return "Date unknown"

# -----------------------------------------------------------------------------
# MAIN RENDERER
# -----------------------------------------------------------------------------
def render_injury_page():
    load_professional_styles()
    
    with st.spinner("FETCHING LEAGUE DATA..."):
        injuries = get_injuries()

    if not injuries:
        st.error("SYSTEM MESSAGE: NO INJURY DATA AVAILABLE.")
        return

    df = pd.DataFrame(injuries)
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    
    selected_team = render_injury_sidebar(df)
    
    st.markdown('<div class="main-header">OFFICIAL INJURY REPORT</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">NBA LEAGUE UPDATE • {datetime.now().strftime("%B %d, %Y")}</div>', unsafe_allow_html=True)

    top_col1, top_col2 = st.columns([3, 1])
    
    with top_col2:
        if st.button("🔄 UPDATE DATA", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    with st.container():
        c1, c2, c3 = st.columns(3)
        with c1:
            statuses = ["ALL STATUSES"] + sorted(df["status"].unique().tolist())
            selected_status = st.selectbox("STATUS FILTER", statuses, label_visibility="collapsed", 
                                          index=0, placeholder="Select Status")
        with c2:
            search = st.text_input("PLAYER SEARCH", placeholder="SEARCH PLAYER...", 
                                  label_visibility="collapsed")
        with c3:
            sort_options = ["Newest First", "Oldest First", "Team Name"]
            selected_sort = st.selectbox("SORT BY", sort_options, label_visibility="collapsed", 
                                        index=0)

    filtered_df = df.copy()
    
    if selected_team != "ALL TEAMS":
        filtered_df = filtered_df[filtered_df["team"] == selected_team]
    
    if selected_status != "ALL STATUSES":
        filtered_df = filtered_df[filtered_df["status"] == selected_status]
    
    if search:
        filtered_df = filtered_df[filtered_df["player"].str.contains(search, case=False, na=False)]

    if selected_sort == "Newest First":
        filtered_df = filtered_df.sort_values("date_dt", ascending=False)
    elif selected_sort == "Oldest First":
        filtered_df = filtered_df.sort_values("date_dt", ascending=True)

    st.markdown("---")

    m1, m2, m3 = st.columns(3)
    with m1: 
        st.metric("TOTAL REPORTED", len(filtered_df))
    with m2: 
        st.metric("CONFIRMED OUT", len(filtered_df[filtered_df["status"].str.lower().str.contains("out", na=False)]))
    with m3: 
        st.metric("DAY-TO-DAY", len(filtered_df[filtered_df["status"].str.lower().str.contains("day", na=False)]))

    st.markdown("<br>", unsafe_allow_html=True)

    if filtered_df.empty:
        st.info("NO MATCHING RECORDS FOUND.")
    else:
        if selected_sort == "Team Name":
            teams_list = sorted(filtered_df["team"].unique())
            
            for team in teams_list:
                team_data = filtered_df[filtered_df["team"] == team]
                first_rec = team_data.iloc[0]
                
                st.markdown(f"""
                <div class="team-header-container">
                    <img src="{first_rec['team_logo']}" class="team-logo-img">
                    <div class="team-title">{first_rec['team_name']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                player_cols = st.columns(2) 
                
                for idx, (_, player) in enumerate(team_data.iterrows()):
                    col_idx = idx % 2
                    with player_cols[col_idx]:
                        render_player_card(player, show_team_in_card=False)
        else:
            player_cols = st.columns(2)
            
            for idx, (_, player) in enumerate(filtered_df.iterrows()):
                col_idx = idx % 2
                with player_cols[col_idx]:
                    render_player_card(player, show_team_in_card=True)

def render_player_card(player, show_team_in_card=False):
    status_cls = get_status_style(player['status'])
    photo_url = player['player_photo'] if player['player_photo'] else "https://a.espncdn.com/combiner/i?img=/i/headshots/nophoto.png"
    injury_date_formatted = format_injury_date(player['date'])
    
    # 24 SAAT KONTROLÜ
    is_recent = False
    try:
        dt_obj = player.get('date_dt')
        if pd.isnull(dt_obj):
             dt_obj = pd.to_datetime(player['date'], errors='coerce')
        
        if dt_obj and not pd.isnull(dt_obj):
            if dt_obj.tzinfo:
                dt_obj = dt_obj.replace(tzinfo=None)
            
            now = datetime.now()
            diff = abs((now - dt_obj).total_seconds())
            
            if diff < 86400:
                is_recent = True
    except Exception:
        pass

    # Takım bilgisi
    meta_info = player['position']
    if show_team_in_card:
        team_abbr = str(player['team']).replace("'", "&#39;").replace('"', '&quot;')
        meta_info = f'<span style="color:#17408B; font-weight:800;">{team_abbr}</span> • {player["position"]}'

    # HTML escape fonksiyonu
    def escape_html(text):
        if not isinstance(text, str):
            text = str(text)
        return (text.replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                    .replace("'", '&#39;'))
    
    player_name = escape_html(player['player'])
    injury_type = escape_html(player['injury_type'])
    details = escape_html(player['details'])
    status_text = escape_html(player['status'])

    # HTML oluştur
    if is_recent:
        html = f'''<div class="player-card">
    <div class="new-badge">🔥 NEW</div>
    <div class="card-top">
        <img src="{photo_url}" class="p-photo">
        <div class="p-info">
            <div class="p-name">{player_name}</div>
            <div class="p-meta">{meta_info}</div>
        </div>
    </div>
    <div class="status-badge {status_cls}">{status_text}</div>
    <div class="card-details">
        <strong>INJURY:</strong> {injury_type}<br>
        <span style="opacity:0.8">{details}</span>
        <br><span class="injury-date">📅 Updated: {injury_date_formatted}</span>
    </div>
</div>'''
    else:
        html = f'''<div class="player-card">
    <div class="card-top">
        <img src="{photo_url}" class="p-photo">
        <div class="p-info">
            <div class="p-name">{player_name}</div>
            <div class="p-meta">{meta_info}</div>
        </div>
    </div>
    <div class="status-badge {status_cls}">{status_text}</div>
    <div class="card-details">
        <strong>INJURY:</strong> {injury_type}<br>
        <span style="opacity:0.8">{details}</span>
        <br><span class="injury-date">📅 Updated: {injury_date_formatted}</span>
    </div>
</div>'''
    
    st.markdown(html, unsafe_allow_html=True)

if __name__ == "__main__":
    st.set_page_config(page_title="NBA Injury Report", layout="wide", page_icon="🏀")
    render_injury_page()
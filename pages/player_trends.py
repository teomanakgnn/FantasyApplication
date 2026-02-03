import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import concurrent.futures
import sys
import os
import streamlit.components.v1 as components
import requests
import feedparser
import json
from typing import List, Dict


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
        
        /* ============================================
           TRADE RUMORS - BEYAZ YAZI
           ============================================ */
        
        .trade-rumors-section * {{
            color: white !important;
        }}
        
        .trade-rumors-section h3,
        .trade-rumors-section h4,
        .trade-rumors-section p,
        .trade-rumors-section div,
        .trade-rumors-section span,
        .trade-rumors-section caption,
        .trade-rumors-section blockquote {{
            color: white !important;
        }}
        
        {extra_styles}
    </style>
""", unsafe_allow_html=True)

# MOBİL SIDEBAR: SCROLL + BACKDROP CLICK DÜZELTMESİ
components.html("""
<script>
    (function() {
        'use strict';
        
        var triggerElement = null;
        var backdropElement = null;
        
        // LocalStorage kullanarak sidebar durumunu sakla
        function saveSidebarState(isClosed) {
            try {
                window.parent.localStorage.setItem('hooplife_sidebar_closed', isClosed ? 'true' : 'false');
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
            
            // ÖNEMLİ: Toggle etmeden ÖNCE gerçek durumu kontrol et
            const willBeClosed = !state.isClosed; // Tıkladıktan sonra ne olacak?
            
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
                        saveSidebarState(false); // Açık olarak kaydet
                        
                        // MOBİL: Scroll'u enable et
                        if (isMobile) {
                            sidebar.style.overflowY = 'auto';
                            sidebar.style.overflowX = 'hidden';
                            sidebar.style.webkitOverflowScrolling = 'touch';
                            
                            // İç container'ı da scroll edilebilir yap
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
                        saveSidebarState(true); // Kapalı olarak kaydet
                    }
                }
            }, 300);
        }
        
        // Global bir referans tanımlayalım ki updateVisibility erişebilsin
        let hoopLifeTrigger = null;

        function createHoopLifeDock() {
            // Eski butonu sil (varsa)
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
            
            // Click event'i ekle
            triggerElement.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                toggleSidebar(); 
                setTimeout(updateVisibility, 100);
            });
            
            // Hover Efektleri
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
                // SIDEBAR AÇIKKEN
                if (isMobile) {
                    // MOBİLDE: Premium Görünüm (çarpı butonu)
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
                    // DESKTOP'TA: Butonu gizle
                    trigger.style.display = 'none';
                }
            } else {
                // SIDEBAR KAPALIYKEN (Basketbol Çentiği)
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
        
        // Sidebar durumunu kontrol et ve gerekirse düzelt
        function checkAndFixSidebar() {
            const shouldBeClosed = getSavedSidebarState();
            const state = getSidebarState();
            
            if (shouldBeClosed && state && !state.isClosed) {
                // Kullanıcı daha önce kapattı ama şimdi açık - kapat
                setTimeout(() => {
                    forceSidebarClose();
                    updateVisibility();
                }, 500);
            } else if (state) {
                // Gerçek durumu localStorage'a kaydet (senkronize et)
                saveSidebarState(state.isClosed);
            }
        }
        
        // BAŞLAT
        function init() {
            createHoopLifeDock();
            
            // Sidebar durumunu kontrol et
            checkAndFixSidebar();
            
            setTimeout(updateVisibility, 500);
            setInterval(() => {
                checkAndFixSidebar();
                updateVisibility();
            }, 1000);
            
            window.parent.addEventListener('resize', updateVisibility);
        }
        
        // DOM hazır olunca başlat
        if (window.parent.document.readyState === 'loading') {
            window.parent.document.addEventListener('DOMContentLoaded', init);
        } else {
            init();
        }
        
    })();
</script>
""", height=0, width=0)

# -----------------------------------------------------------------------------
# SABİTLER VE AYARLAR
# -----------------------------------------------------------------------------
SEASON_START_DATE = datetime(2025, 10, 22)

NBA_TEAMS = [
    "Hawks", "Celtics", "Nets", "Hornets", "Bulls", "Cavaliers", "Mavericks", 
    "Nuggets", "Pistons", "Warriors", "Rockets", "Pacers", "Clippers", "Lakers", 
    "Grizzlies", "Heat", "Bucks", "Timberwolves", "Pelicans", "Knicks", "Thunder", 
    "Magic", "76ers", "Suns", "Blazers", "Kings", "Spurs", "Raptors", "Jazz", "Wizards"
]

DEFAULT_WEIGHTS = {
    "PTS": 1.0, "REB": 0.4, "AST": 0.7, "STL": 1.1, "BLK": 0.75, "TO": -1.0,
    "FGA": -0.7, "FGM": 0.5, "FTA": -0.4, "FTM": 0.6, "3Pts": 0.3,
}

# ============================================================================
# TRADE RUMORS - İYİLEŞTİRİLMİŞ VERSİYON
# ============================================================================

@st.cache_data(ttl=1800)  # 30 dakika cache
def fetch_rss_rumors() -> List[Dict]:
    """RSS feed'lerinden trade rumors çeker - İYİLEŞTİRİLMİŞ FİLTRELEME"""
    rumors = []
    
    # Daha güçlü filtreleme için keyword listesi
    TRADE_KEYWORDS = [
        'trade', 'traded', 'trading', 'deal', 'acquire', 'acquired', 
        'sign', 'signed', 'signing', 'rumor', 'rumors', 'interest', 
        'interested', 'pursuing', 'target', 'available', 'shopping',
        'waive', 'waived', 'release', 'released', 'buyout', 'contract',
        'extension', 'negotiations', 'free agent', 'restricted'
    ]
    
    # İlgisiz haberleri filtrele
    EXCLUDE_KEYWORDS = [
        'injury report', 'game preview', 'game recap', 'highlights',
        'fantasy', 'prop bet', 'betting', 'odds', 'prediction',
        'starting lineup', 'score', 'final score', 'player stats',
        'standings', 'playoff picture', 'draft lottery'
    ]
    
    rss_sources = [
        {'url': 'https://www.hoopshype.com/feed/', 'source': 'HoopsHype'},
        {'url': 'https://www.espn.com/espn/rss/nba/news', 'source': 'ESPN'},
        {'url': 'https://bleacherreport.com/articles/feed?tag_id=18', 'source': 'B/R'},
        {'url': 'https://www.cbssports.com/rss/headlines/nba/', 'source': 'CBS Sports'}
    ]
    
    for rss_source in rss_sources:
        try:
            feed = feedparser.parse(rss_source['url'])
            
            for entry in feed.entries[:8]:  # Daha fazla entry kontrol et
                title = entry.get('title', 'No Title')
                content = entry.get('summary', entry.get('description', 'No content'))
                
                combined = (title + " " + content).lower()
                
                # İlgisiz haberleri filtrele
                if any(exclude in combined for exclude in EXCLUDE_KEYWORDS):
                    continue
                
                # Trade/rumor filtresi - daha katı
                if not any(kw in combined for kw in TRADE_KEYWORDS):
                    continue
                
                # Tarih
                try:
                    pub_date = datetime(*entry.published_parsed[:6])
                    date_str = pub_date.strftime('%b %d, %Y')
                    days_ago = (datetime.now() - pub_date).days
                except:
                    date_str = 'Recent'
                    days_ago = 0
                
                # Çok eski haberleri atla (7 günden eski)
                if days_ago > 7:
                    continue
                
                # Takımlar
                teams = [team for team in NBA_TEAMS if team.lower() in combined]
                
                # En az bir takım mention edilmeli
                if not teams:
                    continue
                
                # Likelihood - daha akıllı
                likelihood = "Medium"
                confidence_score = 2
                
                if any(kw in combined for kw in ['official', 'confirmed', 'agreed', 'done deal', 'finalizing', 'completed']):
                    likelihood = "High"
                    confidence_score = 4
                elif any(kw in combined for kw in ['close to', 'nearing', 'likely', 'expected', 'imminent']):
                    likelihood = "Medium-High"
                    confidence_score = 3
                elif any(kw in combined for kw in ['monitoring', 'considering', 'could', 'might', 'potential', 'exploring']):
                    likelihood = "Low"
                    confidence_score = 1
                
                rumors.append({
                    'title': title,
                    'content': content[:350],  # Daha kısa snippet
                    'source': rss_source['source'],
                    'date': date_str,
                    'days_ago': days_ago,
                    'teams': teams,
                    'likelihood': likelihood,
                    'confidence': confidence_score
                })
                
        except Exception as e:
            print(f"RSS Error ({rss_source['source']}): {e}")
            continue
    
    return rumors


@st.cache_data(ttl=3600)
def fetch_espn_headlines() -> List[Dict]:
    """ESPN API'sinden NBA haberleri çeker"""
    rumors = []
    
    TRADE_KEYWORDS = [
        'trade', 'traded', 'deal', 'acquire', 'sign', 'signed',
        'rumor', 'interested', 'pursuing', 'available'
    ]
    
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        articles = data.get('articles', [])
        
        for article in articles[:12]:
            headline = article.get('headline', '')
            description = article.get('description', '')
            
            combined = (headline + " " + description).lower()
            
            # Filtreleme
            if not any(kw in combined for kw in TRADE_KEYWORDS):
                continue
            
            teams = [team for team in NBA_TEAMS if team.lower() in combined]
            
            if not teams:
                continue
            
            # Tarih
            try:
                published = article.get('published', '')
                date_obj = datetime.fromisoformat(published.replace('Z', '+00:00'))
                date_str = date_obj.strftime('%b %d, %Y')
                days_ago = (datetime.now(date_obj.tzinfo) - date_obj).days
            except:
                date_str = 'Recent'
                days_ago = 0
            
            # 7 günden eski haberleri atla
            if days_ago > 7:
                continue
            
            rumors.append({
                'title': headline,
                'content': description[:350],
                'source': 'ESPN API',
                'date': date_str,
                'days_ago': days_ago,
                'teams': teams,
                'likelihood': 'Medium',
                'confidence': 2
            })
            
    except Exception as e:
        print(f"ESPN API Error: {e}")
    
    return rumors


@st.cache_data(ttl=1800)
def fetch_reddit_rumors() -> List[Dict]:
    """Reddit r/nba'dan trade rumors çeker"""
    rumors = []
    
    try:
        url = "https://www.reddit.com/r/nba/search.json"
        params = {
            'q': 'trade OR rumors flair:rumor',
            'sort': 'new',
            'limit': 30,
            't': 'week'
        }
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; NBA-Rumor-Bot/1.0)'}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
        
        data = response.json()
        posts = data.get('data', {}).get('children', [])
        
        for post in posts:
            post_data = post.get('data', {})
            
            title = post_data.get('title', '')
            selftext = post_data.get('selftext', '')
            
            combined = (title + " " + selftext).lower()
            
            # Basic filtering
            if not any(kw in combined for kw in ['trade', 'rumor', 'deal', 'sign', 'interested']):
                continue
            
            teams = [team for team in NBA_TEAMS if team.lower() in combined]
            
            if not teams:
                continue
            
            # Tarih
            created = post_data.get('created_utc', 0)
            pub_date = datetime.fromtimestamp(created)
            date_str = pub_date.strftime('%b %d, %Y')
            days_ago = (datetime.now() - pub_date).days
            
            # Likelihood (upvote bazlı)
            score = post_data.get('score', 0)
            
            if score < 50:  # Düşük upvote'lu postları filtrele
                continue
            
            likelihood = 'High' if score > 1000 else 'Medium-High' if score > 500 else 'Medium' if score > 100 else 'Low'
            confidence = 4 if score > 1000 else 3 if score > 500 else 2 if score > 100 else 1
            
            rumors.append({
                'title': title,
                'content': selftext[:350] if selftext else 'Community discussion',
                'source': f'r/nba (↑{score})',
                'date': date_str,
                'days_ago': days_ago,
                'teams': teams,
                'likelihood': likelihood,
                'confidence': confidence
            })
            
    except Exception as e:
        print(f"Reddit API Error: {e}")
    
    return rumors


def get_trade_rumors() -> List[Dict]:
    """Tüm kaynaklardan rumors çeker ve birleştirir"""
    all_rumors = []
    
    # RSS Feeds
    rss_rumors = fetch_rss_rumors()
    all_rumors.extend(rss_rumors)
    
    # ESPN API
    espn_rumors = fetch_espn_headlines()
    all_rumors.extend(espn_rumors)
    
    # Reddit
    reddit_rumors = fetch_reddit_rumors()
    all_rumors.extend(reddit_rumors)
    
    # Duplicate temizleme (daha akıllı)
    seen_titles = set()
    unique_rumors = []
    
    for rumor in all_rumors:
        # Başlığın ilk 40 karakterini normalize et
        title_key = rumor['title'].lower().strip()[:40]
        
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_rumors.append(rumor)
    
    # Önce confidence'a göre, sonra tarihe göre sırala
    unique_rumors.sort(key=lambda x: (x.get('confidence', 0), -x.get('days_ago', 999)), reverse=True)
    
    # En fazla 15 rumor göster
    return unique_rumors[:15] if unique_rumors else [{
        'title': '⚠️ No trade rumors available',
        'content': 'Could not fetch trade rumors at this time. Please try again later.',
        'source': 'System',
        'date': datetime.now().strftime('%b %d, %Y'),
        'days_ago': 0,
        'teams': [],
        'likelihood': 'N/A',
        'confidence': 0
    }]


# ============================================================================
# MAIN PAGE FUNCTION
# ============================================================================

def render_player_trends_page():
    """Player Trends - Dual Period Comparison"""
    
    # 1. Stil Ayarları
    st.markdown("""
        <style>
            /* Streamlit Header'ı Gizle */
            header[data-testid="stHeader"] {
                display: none !important;
            }
            
            /* Hamburger menüyü gizle */
            #MainMenu {
                visibility: hidden !important;
            }
            
            /* Footer'ı gizle */
            footer {
                visibility: hidden !important;
            }    

            .stApp { background-image: none !important; }
            .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
            div[data-testid="stMetric"] {
                background-color: #f8f9fa; border-radius: 8px; padding: 10px;
                border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }
            @media (prefers-color-scheme: dark) {
                div[data-testid="stMetric"] { background-color: #262730; border-color: #444; }
            }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("Player Form & Trends")
    
    # 2. Import Kontrolü
    try:
        from services.espn_api import get_game_ids, get_cached_boxscore
    except ImportError as e:
        st.error(f"❌ Import Error: {e}")
        return

    # 3. SIDEBAR AYARLARI
    st.sidebar.header("🔍 Trend Settings")
    
    st.sidebar.markdown("### Period Comparison")
    
    period_options = {
        "Last 1 Week": 7,
        "Last 15 Days": 15,
        "Last 30 Days": 30,
        "Last 45 Days": 45,
        "Full Season": 999
    }
    
    period1_label = st.sidebar.selectbox(
        "Period 1:", 
        options=list(period_options.keys()), 
        index=1
    )
    period1_days = period_options[period1_label]
    
    period2_label = st.sidebar.selectbox(
        "Period 2:", 
        options=list(period_options.keys()), 
        index=4
    )
    period2_days = period_options[period2_label]
    
    st.sidebar.markdown("### Filters")
    
    min_games_p1 = st.sidebar.number_input(
        f"Min Games (Period 1)", 
        min_value=1, max_value=20, value=3
    )
    
    min_games_p2 = st.sidebar.number_input(
        f"Min Games (Period 2)", 
        min_value=1, max_value=30, value=5
    )
    
    min_avg_score = st.sidebar.number_input(
        f"Min Avg Score",
        min_value=0, max_value=100, value=20, step=5
    )
    
    max_avg_score = st.sidebar.number_input(
        f"Max Avg Score",
        min_value=0, max_value=150, value=100, step=5
    )
    
    st.sidebar.markdown("---")
    
    # Background URL Input
    st.sidebar.markdown("### 🎨 Background Settings")
    background_url = "https://wallpapercave.com/wp/wp15388438.jpg"
    
    if background_url:
        st.markdown(f"""
            <style>
                .stApp {{
                    background-image: url("{background_url}") !important;
                    background-size: cover !important;
                    background-position: center !important;
                    background-repeat: no-repeat !important;
                    background-attachment: fixed !important;
                }}
                .stApp::before {{
                    content: "";
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.3);
                    z-index: -1;
                }}
            </style>
        """, unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    if st.sidebar.button("⬅️ Back to Home", use_container_width=True):
        st.session_state.page = "home"
        st.rerun()

    st.caption(f"Comparing **{period1_label}** vs **{period2_label}** (Score Range: {min_avg_score}-{max_avg_score})")

    # 4. HELPER FUNCTIONS
    def fetch_games_for_date(date):
        try:
            ids = get_game_ids(date)
            return date, ids
        except:
            return date, []

    def fetch_boxscore_for_game(game_info):
        game_id, game_date = game_info
        try:
            players = get_cached_boxscore(game_id)
            if players:
                for p in players:
                    p['date'] = game_date
                return players
        except:
            pass
        return []

    # 5. VERİ ÇEKME
    if "season_data" not in st.session_state:
        st.session_state.season_data = None

    if st.session_state.season_data is None:
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        today = datetime.now()
        delta = today - SEASON_START_DATE
        total_days = delta.days + 1
        
        dates_to_fetch = [SEASON_START_DATE + timedelta(days=i) for i in range(total_days)]
        
        all_records = []
        all_game_tasks = []

        status_text.text(f"Fetching full season schedule ({total_days} days)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_date = {executor.submit(fetch_games_for_date, d): d for d in dates_to_fetch}
            for i, future in enumerate(concurrent.futures.as_completed(future_to_date)):
                date, ids = future.result()
                if ids:
                    for gid in ids:
                        all_game_tasks.append((gid, date))
                progress_bar.progress(int((i / len(dates_to_fetch)) * 20))

        total_games = len(all_game_tasks)
        status_text.text(f"Fetching stats for {total_games} games (Season)...")
        
        if total_games > 0:
            with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
                future_to_game = {executor.submit(fetch_boxscore_for_game, task): task for task in all_game_tasks}
                for i, future in enumerate(concurrent.futures.as_completed(future_to_game)):
                    result = future.result()
                    if result:
                        all_records.extend(result)
                    
                    current_progress = 20 + int((i / total_games) * 80)
                    progress_bar.progress(min(current_progress, 100))
        
        progress_bar.empty()
        status_text.empty()
        
        if not all_records:
            st.warning("Sezon verisi bulunamadı.")
            return

        st.session_state.season_data = pd.DataFrame(all_records)

    df = st.session_state.season_data.copy()

    # 6. SKOR HESAPLAMA
    numeric_cols = ["PTS", "REB", "AST", "STL", "BLK", "TO", "FGM", "FGA", "FTM", "FTA", "3Pts"]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        else:
            df[c] = 0

    def calc_score(row):
        score = 0
        for stat, weight in DEFAULT_WEIGHTS.items():
            score += row.get(stat, 0) * weight
        return score

    df["fantasy_score"] = df.apply(calc_score, axis=1)
    df["date"] = pd.to_datetime(df["date"])
    
    # 7. PERİYOT ANALİZİ
    today_ts = pd.Timestamp.now()
    
    if period1_days == 999:
        df_p1 = df.copy()
    else:
        p1_start_date = today_ts - pd.Timedelta(days=period1_days)
        df_p1 = df[df["date"] >= p1_start_date].copy()
    
    if period2_days == 999:
        df_p2 = df.copy()
    else:
        p2_start_date = today_ts - pd.Timedelta(days=period2_days)
        df_p2 = df[df["date"] >= p2_start_date].copy()

    if df_p1.empty or df_p2.empty:
        st.info("Seçilen periyotlar için yeterli veri bulunamadı.")
        return

    # 8. GRUPLAMA
    grp_p1 = df_p1.groupby("PLAYER").agg({
        "fantasy_score": "mean",
        "TEAM": "first",
        "date": "count"
    }).rename(columns={"fantasy_score": "avg_p1", "date": "games_p1"})

    grp_p2 = df_p2.groupby("PLAYER").agg({
        "fantasy_score": "mean",
        "TEAM": "first",
        "date": "count"
    }).rename(columns={"fantasy_score": "avg_p2", "date": "games_p2"})

    # 9. BİRLEŞTİRME VE FİLTRELEME
    analysis_df = grp_p1.join(grp_p2[["avg_p2", "games_p2"]], how="inner")
    
    analysis_df = analysis_df[
        (analysis_df["games_p1"] >= min_games_p1) & 
        (analysis_df["games_p2"] >= min_games_p2) &
        (analysis_df["avg_p1"] >= min_avg_score) & 
        (analysis_df["avg_p1"] <= max_avg_score) &
        (analysis_df["avg_p2"] >= min_avg_score) & 
        (analysis_df["avg_p2"] <= max_avg_score)
    ]
    
    analysis_df["diff"] = analysis_df["avg_p1"] - analysis_df["avg_p2"]
    
    risers = analysis_df.sort_values("diff", ascending=False).head(5)
    fallers = analysis_df.sort_values("diff", ascending=True).head(5)

    # 10. GÖRSELLEŞTIRME
    st.subheader(f"🔥 Risers ({period1_label} vs {period2_label})")
    if risers.empty:
        st.info("Kriterlere uyan oyuncu bulunamadı.")
    else:
        cols = st.columns(5)
        for i, (player, row) in enumerate(risers.iterrows()):
            with cols[i]:
                st.metric(
                    label=player,
                    value=f"{row['avg_p1']:.1f}",
                    delta=f"+{row['diff']:.1f}",
                    help=f"{period2_label} Avg: {row['avg_p2']:.1f} | Games: {int(row['games_p1'])}/{int(row['games_p2'])}"
                )

    st.subheader(f"❄️ Fallers ({period1_label} vs {period2_label})")
    if fallers.empty:
        st.info("Kriterlere uyan oyuncu bulunamadı.")
    else:
        cols = st.columns(5)
        for i, (player, row) in enumerate(fallers.iterrows()):
            with cols[i]:
                st.metric(
                    label=player,
                    value=f"{row['avg_p1']:.1f}",
                    delta=f"{row['diff']:.1f}",
                    help=f"{period2_label} Avg: {row['avg_p2']:.1f} | Games: {int(row['games_p1'])}/{int(row['games_p2'])}"
                )
            
    st.divider()

    # 12. COMPARISON TABLE
    st.subheader(f"Comparison Table ({len(analysis_df)} Players)")
    
    display_df = analysis_df.reset_index().sort_values("diff", ascending=False)
    
    st.dataframe(
        display_df[[
            "PLAYER", "TEAM", "games_p1", "games_p2",
            "avg_p1", "avg_p2", "diff"
        ]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "PLAYER": st.column_config.TextColumn("Player", width="medium"),
            "TEAM": st.column_config.TextColumn("Team", width="small"),
            "games_p1": st.column_config.NumberColumn(f"G (P1)", format="%d"),
            "games_p2": st.column_config.NumberColumn(f"G (P2)", format="%d"),
            "avg_p1": st.column_config.NumberColumn(f"{period1_label}", format="%.1f"),
            "avg_p2": st.column_config.NumberColumn(f"{period2_label}", format="%.1f"),
            "diff": st.column_config.NumberColumn("Diff (+/-)", format="%.1f"),
        },
        height=600
    )
    
    st.divider()
    
    # 11. TRADE RUMORS - TABLONUN ALTINDA
    st.markdown('<div class="trade-rumors-section">', unsafe_allow_html=True)
    
    st.subheader("📰 Latest NBA Trade Rumors")
    st.caption("Live updates from ESPN, HoopsHype, Bleacher Report, CBS Sports, and Reddit")

    with st.spinner("Fetching latest trade news from multiple sources..."):
        rumors = get_trade_rumors()

    if rumors and rumors[0]['title'] != '⚠️ No trade rumors available':
        # Likelihood filter
        filter_col1, filter_col2 = st.columns([3, 1])
        
        with filter_col1:
            likelihood_filter = st.multiselect(
                "Filter by likelihood:",
                options=['High', 'Medium-High', 'Medium', 'Low'],
                default=['High', 'Medium-High', 'Medium', 'Low']
            )
        
        with filter_col2:
            show_count = st.number_input("Show top:", min_value=5, max_value=15, value=10, step=1)
        
        # Filtreleme
        filtered_rumors = [r for r in rumors if r['likelihood'] in likelihood_filter][:show_count]
        
        st.markdown(f"**Showing {len(filtered_rumors)} rumors** (sorted by reliability)")
        
        # İlk 3 haberi göster
        initial_display = min(3, len(filtered_rumors))
        
        for idx in range(initial_display):
            rumor = filtered_rumors[idx]
            
            # Likelihood emoji ve badge rengi
            likelihood_config = {
                'High': {'emoji': '🟢', 'badge': 'success'},
                'Medium-High': {'emoji': '🟡', 'badge': 'warning'},
                'Medium': {'emoji': '🟠', 'badge': 'warning'},
                'Low': {'emoji': '🔴', 'badge': 'error'}
            }
            
            config = likelihood_config.get(rumor['likelihood'], {'emoji': '⚪', 'badge': 'info'})
            
            # Days ago formatı
            if rumor['days_ago'] == 0:
                time_badge = "🆕 Today"
            elif rumor['days_ago'] == 1:
                time_badge = "🕐 Yesterday"
            elif rumor['days_ago'] < 7:
                time_badge = f"🕐 {rumor['days_ago']} days ago"
            else:
                time_badge = f"📅 {rumor['date']}"
            
            # Container ile güzel görünüm
            with st.container():
                # Başlık satırı
                title_col, badge_col = st.columns([4, 1])
                
                with title_col:
                    st.markdown(f"### {idx+1}. {rumor['title']}")
                
                with badge_col:
                    st.markdown(f"{config['emoji']} **{rumor['likelihood']}**")
                
                # Meta bilgiler
                info_col1, info_col2 = st.columns(2)
                
                with info_col1:
                    st.caption(f"📡 **{rumor['source']}**")
                
                with info_col2:
                    st.caption(f"{time_badge}")
                
                # İçerik
                st.markdown(f"> {rumor['content']}")
                
                # Takımlar varsa göster
                if rumor['teams']:
                    teams_display = " • ".join([f"**{team}**" for team in rumor['teams'][:5]])
                    st.markdown(f"🏀 {teams_display}")
                
                st.divider()
        
        # Eğer 3'ten fazla haber varsa "Read More" butonu
        if len(filtered_rumors) > 3:
            if 'show_all_rumors' not in st.session_state:
                st.session_state.show_all_rumors = False
            
            if not st.session_state.show_all_rumors:
                if st.button("📖 Read More", use_container_width=True, type="primary"):
                    st.session_state.show_all_rumors = True
                    st.rerun()
            else:
                # Kalan haberleri göster
                for idx in range(initial_display, len(filtered_rumors)):
                    rumor = filtered_rumors[idx]
                    
                    likelihood_config = {
                        'High': {'emoji': '🟢', 'badge': 'success'},
                        'Medium-High': {'emoji': '🟡', 'badge': 'warning'},
                        'Medium': {'emoji': '🟠', 'badge': 'warning'},
                        'Low': {'emoji': '🔴', 'badge': 'error'}
                    }
                    
                    config = likelihood_config.get(rumor['likelihood'], {'emoji': '⚪', 'badge': 'info'})
                    
                    if rumor['days_ago'] == 0:
                        time_badge = "🆕 Today"
                    elif rumor['days_ago'] == 1:
                        time_badge = "🕐 Yesterday"
                    elif rumor['days_ago'] < 7:
                        time_badge = f"🕐 {rumor['days_ago']} days ago"
                    else:
                        time_badge = f"📅 {rumor['date']}"
                    
                    with st.container():
                        title_col, badge_col = st.columns([4, 1])
                        
                        with title_col:
                            st.markdown(f"### {idx+1}. {rumor['title']}")
                        
                        with badge_col:
                            st.markdown(f"{config['emoji']} **{rumor['likelihood']}**")
                        
                        info_col1, info_col2 = st.columns(2)
                        
                        with info_col1:
                            st.caption(f"📡 **{rumor['source']}**")
                        
                        with info_col2:
                            st.caption(f"{time_badge}")
                        
                        st.markdown(f"> {rumor['content']}")
                        
                        if rumor['teams']:
                            teams_display = " • ".join([f"**{team}**" for team in rumor['teams'][:5]])
                            st.markdown(f"🏀 {teams_display}")
                        
                        st.divider()
                
                # Collapse butonu
                if st.button("📕 Show Less", use_container_width=True):
                    st.session_state.show_all_rumors = False
                    st.rerun()
    else:
        st.info("⚠️ No trade rumors available at this time. Please try refreshing the page.")
    
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    render_player_trends_page()
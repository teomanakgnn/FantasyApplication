import streamlit as st
import pandas as pd
from services.espn_api import get_active_players_stats
from datetime import datetime
import streamlit.components.v1 as components

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
                overflow-y: auto !important;
                overflow-x: hidden !important;
                -webkit-overflow-scrolling: touch !important;
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
                padding-bottom: 60px !important;
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

# --- GÜNCEL PUANLAMA SİSTEMİ ---
BASE_WEIGHTS = {
    "PTS": 0.75, "REB": 0.5, "AST": 0.8, "STL": 1.7, "BLK": 1.6, "TO": -1.5,
    "FGA": -0.9, "FGM": 1.2, "FTA": -0.55, "FTM": 1.1, "3PM": 0.6, 
    "FG%": 0.0, "FT%": 0.0
}

# --- TEAM MAP ---
TEAM_MAP = {
    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
    'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
    'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
    'GSW': 'Golden State Warriors', 'GS': 'Golden State Warriors',
    'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
    'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
    'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
    'NOP': 'New Orleans Pelicans', 'NO': 'New Orleans Pelicans',
    'NYK': 'New York Knicks', 'NY': 'New York Knicks',
    'OKC': 'Oklahoma City Thunder', 'ORL': 'Orlando Magic', 
    'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 
    'SAS': 'San Antonio Spurs', 'SA': 'San Antonio Spurs',
    'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'UTAH': 'Utah Jazz', 'WSH': 'Washington Wizards'
}

# ============================================
# THRESHOLD-BASED SMART VALUATION SYSTEM
# ============================================

def calculate_threshold_value(df, punt_cats, min_threshold=12.0, penalty_curve=0.3):
    weights = BASE_WEIGHTS.copy()
    
    # Punt kategorilerini 0 yap
    for cat in punt_cats:
        if cat == "FG Punt":
            weights["FGM"] = 0.0
            weights["FGA"] = 0.0
        elif cat == "FT Punt":
            weights["FTM"] = 0.0
            weights["FTA"] = 0.0
        elif cat == "TO Punt":
            weights["TO"] = 0.0
    
    available_cols = [col for col in weights.keys() if col in df.columns]
    if not available_cols: 
        return 0.0, []
    
    # Her oyuncu için FP hesapla
    player_fps = []
    for idx, row in df.iterrows():
        raw_fp = sum(row.get(col, 0) * weights[col] for col in available_cols)
        player_fps.append({
            'player': row.get('PLAYER', 'Unknown'),
            'raw_fp': raw_fp,
            'adjusted_fp': 0.0,
            'tier': '',
            'multiplier': 1.0
        })
    
    if not player_fps:
        return 0.0, []
    
    # FP'ye göre sırala
    player_fps.sort(key=lambda x: x['raw_fp'], reverse=True)
    
    # Her oyuncu için adjusted value hesapla
    total_adjusted = 0.0
    
    for p in player_fps:
        raw = p['raw_fp']
        
        if raw >= min_threshold:
            # EŞİK ÜSTÜ: TAM DEĞER
            p['adjusted_fp'] = raw
            p['multiplier'] = 1.0
            
            # Tier classification
            if raw >= 30:
                p['tier'] = '⭐ Elite'
            elif raw >= 22:
                p['tier'] = '🔹 Solid Starter'
            elif raw >= 15:
                p['tier'] = '🔸 Starter'
            else:
                p['tier'] = '🟢 Flex'
                
        else:
            # EŞİK ALTI: EKSPONANSIYEL CEZA
            # Formül: adjusted = raw * (raw / threshold) ^ penalty_curve
            ratio = raw / min_threshold
            multiplier = pow(ratio, 1 + penalty_curve)
            
            p['adjusted_fp'] = raw * multiplier
            p['multiplier'] = multiplier
            
            if raw >= 8:
                p['tier'] = '🟡 Bench'
            elif raw >= 4:
                p['tier'] = '🟠 Deep Bench'
            else:
                p['tier'] = '⚪ Streamer'
        
        total_adjusted += p['adjusted_fp']
    
    # Ortalama adjusted value
    avg_adjusted = total_adjusted / len(player_fps) if player_fps else 0.0
    
    return avg_adjusted, player_fps


def calculate_quality_over_quantity(df, punt_cats, top_player_bonus=1.5):
    """
    KALİTE > MİKTAR SİSTEMİ
    
    En iyi oyuncu ekstra bonus alır.
    2-for-1 trade'lerde quality'yi ödüllendirir.
    
    Mantık:
    - En iyi oyuncu: %50 bonus
    - Diğer oyuncular: Normal değer
    """
    weights = BASE_WEIGHTS.copy()
    
    for cat in punt_cats:
        if cat == "FG Punt":
            weights["FGM"] = 0.0
            weights["FGA"] = 0.0
        elif cat == "FT Punt":
            weights["FTM"] = 0.0
            weights["FTA"] = 0.0
        elif cat == "TO Punt":
            weights["TO"] = 0.0
    
    available_cols = [col for col in weights.keys() if col in df.columns]
    if not available_cols: 
        return 0.0
    
    fps = []
    for idx, row in df.iterrows():
        fp = sum(row.get(col, 0) * weights[col] for col in available_cols)
        fps.append(fp)
    
    if not fps:
        return 0.0
    
    fps.sort(reverse=True)
    
    # En iyi oyuncuya bonus
    best_player = fps[0] * top_player_bonus
    others = sum(fps[1:]) if len(fps) > 1 else 0
    
    total = best_player + others
    return total / len(fps)


def calculate_diminishing_returns(df, punt_cats):
    """
    AZALAN VERIM SİSTEMİ
    
    Her ek oyuncu daha az değer katar.
    1 süperstar > 2 iyi oyuncu > 3 orta oyuncu
    
    Katsayılar: 1.0, 0.85, 0.70, 0.55, 0.45...
    """
    weights = BASE_WEIGHTS.copy()
    
    for cat in punt_cats:
        if cat == "FG Punt":
            weights["FGM"] = 0.0
            weights["FGA"] = 0.0
        elif cat == "FT Punt":
            weights["FTM"] = 0.0
            weights["FTA"] = 0.0
        elif cat == "TO Punt":
            weights["TO"] = 0.0
    
    available_cols = [col for col in weights.keys() if col in df.columns]
    if not available_cols: 
        return 0.0
    
    fps = []
    for idx, row in df.iterrows():
        fp = sum(row.get(col, 0) * weights[col] for col in available_cols)
        fps.append(fp)
    
    fps.sort(reverse=True)
    
    # Azalan verim katsayıları
    diminishing_factors = [1.0, 0.85, 0.70, 0.55, 0.45, 0.35, 0.25]
    
    total = 0
    for i, fp in enumerate(fps):
        factor = diminishing_factors[i] if i < len(diminishing_factors) else 0.2
        total += fp * factor
    
    # Normalize et (toplam faktöre böl)
    used_factors = [diminishing_factors[i] if i < len(diminishing_factors) else 0.2 for i in range(len(fps))]
    sum_factors = sum(used_factors)
    
    return total / sum_factors if sum_factors > 0 else 0.0


def render_trade_analyzer_page():
    st.set_page_config(layout="wide", page_title="NBA Trade Machine", initial_sidebar_state="expanded")

    st.markdown("""
        <style>
        header {visibility: hidden;}
        .stApp {
            background-image: url('https://wallup.net/wp-content/uploads/2016/03/29/318818-basketball-sport-sports-simple.jpg');
            background-size: cover;
            background-attachment: fixed;
            background-position: center;
        }
        .roster-card {
            background-color: rgba(255,255,255,0.08);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            transition: all 0.2s;
        }
        .roster-card:hover { background-color: rgba(255,255,255,0.12); }
        .stat-comparison {
            display: flex; align-items: center; margin: 10px 0; padding: 8px;
            border-radius: 6px; background-color: rgba(255,255,255,0.05);
        }
        .stat-label { width: 90px; font-weight: bold; text-align: center; font-size: 0.9em; }
        .stat-bar-container { flex: 1; display: flex; align-items: center; gap: 10px; }
        .stat-bar {
            height: 25px; border-radius: 4px; display: flex; align-items: center;
            justify-content: center; font-weight: bold; font-size: 0.85em; transition: all 0.3s;
        }
        .team-1-bar { background: linear-gradient(90deg, #3b82f6, #60a5fa); justify-content: flex-end; padding-right: 8px; }
        .team-2-bar { background: linear-gradient(90deg, #f97316, #fb923c); justify-content: flex-start; padding-left: 8px; }
        .player-tier {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            margin-left: 8px;
            background: rgba(255,255,255,0.1);
        }
        .multiplier-badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.7em;
            margin-left: 4px;
            background: rgba(255, 200, 0, 0.2);
            color: #ffd700;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Scoring System")
        
        # SCORING METHOD
        st.subheader("Calculation Method")
        scoring_method = st.selectbox(
            "Choose method",
            [
                "Threshold Smart",
                "Quality > Quantity",
                "Diminishing Returns",
                "Simple Average"
            ],
            help="""
            **Threshold Smart**: Oyuncular belli bir eşiğin altındaysa değerleri düşer (ÖNERİLEN)
            **Quality > Quantity**: En iyi oyuncu %50 bonus alır
            **Diminishing Returns**: Her ek oyuncu daha az katkı sağlar
            **Simple Average**: Geleneksel ortalama hesaplama
            """
        )
        
        # THRESHOLD AYARLARI (sadece Threshold Smart için)
        if scoring_method == "Threshold Smart":
            st.markdown("---")
            st.subheader(" Threshold Settings")
            
            min_threshold = st.slider(
                "Minimum FP Threshold",
                min_value=8.0,
                max_value=20.0,
                value=12.0,
                step=1.0,
                help="Players below this threshold will be penalized."
            )
            
            penalty_curve = st.slider(
                "Penalty Strength",
                min_value=0.1,
                max_value=1.0,
                value=0.3,
                step=0.1,
                help="Higher value = harsher penalty (lower value players = less value)"
            )
            
            st.info(f" Threshold: {min_threshold} FP\nPenalty: {penalty_curve:.1f}")
        
        st.markdown("---")
        
        # PUNT STRATEGY
        st.subheader(" Punt Strategy")
        punt_cats = st.multiselect(
            "Punt categories",
            ["FG Punt", "FT Punt", "TO Punt"],
            help="The categories that were punched have a weight of 0."
        )
        
        if punt_cats:
            st.info(f"Punting: {', '.join(punt_cats)}")
        
        st.markdown("---")
        st.markdown("**Active Weights:**")
        
        display_weights = BASE_WEIGHTS.copy()
        for cat in punt_cats:
            if cat == "FG Punt":
                display_weights["FGM"] = 0.0
                display_weights["FGA"] = 0.0
            elif cat == "FT Punt":
                display_weights["FTM"] = 0.0
                display_weights["FTA"] = 0.0
            elif cat == "TO Punt":
                display_weights["TO"] = 0.0
        
        weights_df = pd.DataFrame(list(display_weights.items()), columns=['Stat', 'Weight'])
        weights_df = weights_df[weights_df['Weight'] != 0]
        weights_df = weights_df.sort_values(by='Weight', ascending=False)
        st.dataframe(weights_df, hide_index=True, use_container_width=True)

    st.title(" NBA Trade Analyzer")
    st.markdown(f"Using **{scoring_method}** method")
    
    # Session State
    for k in ["team_1_players", "team_2_players", "current_period"]:
        if k not in st.session_state:
            st.session_state[k] = [] if "players" in k else None

    # --- SETTINGS ---
    with st.expander("⚙️ Stats Period", expanded=True):
        period = st.selectbox(
            "Time period",
            ["Season Average", "Last 15 Days", "Last 30 Days"],
            index=0,
            key="period_selector"
        )

    # --- DATA LOADING ---
    days_map = {
        "Last 15 Days": (15, False), 
        "Last 30 Days": (30, False), 
        "Season Average": (None, True)
    }
    
    selected_days, use_season = days_map[period]
    
    if st.session_state.current_period != period:
        st.session_state.current_period = period
        if 'df_players' in st.session_state:
            del st.session_state['df_players']
    
    if 'df_players' not in st.session_state:
        with st.spinner(f"Loading {period}..."):
            st.session_state.df_players = get_active_players_stats(
                days=selected_days, 
                season_stats=use_season
            )

    df_players = st.session_state.df_players
    
    if df_players.empty:
        st.error(f"No data for {period}")
        return

    for col in ['FGM', 'FGA', 'FTM', 'FTA', '3PM', 'FG%', 'FT%']:
        if col not in df_players.columns:
            if col == '3PM' and '3Pts' in df_players.columns:
                df_players['3PM'] = df_players['3Pts']
            else:
                df_players[col] = 0.0

    def extract_team_abbr(val):
        if isinstance(val, dict):
            return val.get('team', val.get('abbreviation', 'UNK'))
        return str(val)

    df_players['TEAM'] = df_players['TEAM'].apply(extract_team_abbr)
    df_players['TEAM_FULL'] = df_players['TEAM'].map(TEAM_MAP).fillna(df_players['TEAM'])
    all_teams = ["All Teams"] + sorted(df_players['TEAM_FULL'].unique().tolist())

    # --- RENDER FUNCTION ---
    def render_trade_side(side_id, title, state_key, other_state_key, color):
        st.markdown(f"### {title}")
        box = st.container(border=True)

        with box:
            col_filter, col_select = st.columns([1, 2])
            
            with col_filter:
                team_filter = st.selectbox("Team", all_teams, key=f"filter_{side_id}_{period}")
            
            filtered = df_players if team_filter == "All Teams" else df_players[df_players['TEAM_FULL'] == team_filter]
            other_side_players = st.session_state[other_state_key]
            filtered_players = [p for p in filtered['PLAYER'].tolist() if p not in other_side_players]
            current_selections = st.session_state[state_key]
            all_options = sorted(list(set(filtered_players + current_selections)))

            with col_select:
                selected = st.multiselect(
                    "Players", 
                    options=all_options, 
                    default=current_selections, 
                    key=f"select_{side_id}_{period}"
                )

            st.session_state[state_key] = selected
            
            if selected:
                valid_selected = [p for p in selected if p in df_players['PLAYER'].values]
                
                if valid_selected:
                    df_subset = df_players[df_players['PLAYER'].isin(valid_selected)]
                    
                    # Metoda göre hesapla
                    if scoring_method == "Threshold Smart":
                        fp_preview, player_details = calculate_threshold_value(
                            df_subset, punt_cats, min_threshold, penalty_curve
                        )
                    elif scoring_method == "Quality > Quantity":
                        fp_preview = calculate_quality_over_quantity(df_subset, punt_cats)
                        player_details = []
                    elif scoring_method == "Diminishing Returns":
                        fp_preview = calculate_diminishing_returns(df_subset, punt_cats)
                        player_details = []
                    else:  # Simple Average
                        weights = BASE_WEIGHTS.copy()
                        for cat in punt_cats:
                            if cat == "FG Punt":
                                weights["FGM"] = 0.0
                                weights["FGA"] = 0.0
                            elif cat == "FT Punt":
                                weights["FTM"] = 0.0
                                weights["FTA"] = 0.0
                            elif cat == "TO Punt":
                                weights["TO"] = 0.0
                        
                        available_cols = [col for col in weights.keys() if col in df_players.columns]
                        avg_stats = df_subset[available_cols].mean()
                        fp_preview = sum(avg_stats[col] * weights[col] for col in available_cols)
                        player_details = []
                    
                    st.markdown(f"**Total Value: {fp_preview:.1f} FP**")
                    st.markdown("---")
                    
                    # Oyuncuları göster
                    if scoring_method == "Threshold Smart" and player_details:
                        for p_info in player_details:
                            p = p_info['player']
                            player_data = df_players[df_players['PLAYER'] == p]
                            if not player_data.empty:
                                d = player_data.iloc[0]
                                team = d.get("TEAM", "")
                                pts = d.get("PTS", 0)
                                tier = p_info.get('tier', '')
                                raw = p_info['raw_fp']
                                adj = p_info['adjusted_fp']
                                mult = p_info['multiplier']
                                
                                multiplier_html = ""
                                if mult < 1.0:
                                    multiplier_html = f"<span class='multiplier-badge'>×{mult:.2f}</span>"
                                
                                st.markdown(
                                    f"<div class='roster-card' style='border-left:4px solid {color}'>"
                                    f"<div><b>{p}</b> <span style='color:#aaa'>({team})</span>"
                                    f"<span class='player-tier'>{tier}</span>{multiplier_html}</div>"
                                    f"<div style='color:#aaa; font-size:0.9em;'>"
                                    f"{pts:.1f} PTS | Raw: {raw:.1f} → Adj: {adj:.1f} FP"
                                    f"</div>"
                                    f"</div>", unsafe_allow_html=True
                                )
                    else:
                        for p in valid_selected:
                            player_data = df_players[df_players['PLAYER'] == p]
                            if not player_data.empty:
                                d = player_data.iloc[0]
                                team = d.get("TEAM", "")
                                pts = d.get("PTS", 0)
                                st.markdown(
                                    f"<div class='roster-card' style='border-left:4px solid {color}'>"
                                    f"<div><b>{p}</b> <span style='color:#aaa'>({team})</span></div>"
                                    f"<div style='color:#aaa; font-size:0.9em;'>{pts:.1f} PTS</div>"
                                    f"</div>", unsafe_allow_html=True
                                )
                
                missing = [p for p in selected if p not in df_players['PLAYER'].values]
                if missing:
                    st.warning(f"⚠️ {len(missing)} player(s) unavailable")
            else:
                st.info("Select players...")

        return selected

    st.markdown("---")
    c1, c2 = st.columns(2, gap="large")

    with c1:
        side_1 = render_trade_side("side_1", "Team 1 Receives", "team_1_players", "team_2_players", "#3b82f6")
    with c2:
        side_2 = render_trade_side("side_2", "Team 2 Receives", "team_2_players", "team_1_players", "#f97316")

    if not side_1 or not side_2:
        st.info("Add players to both sides")
        return

    # --- ANALYSIS ---
    def analyze(players):
        valid_players = [p for p in players if p in df_players['PLAYER'].values]
        
        if not valid_players:
            return pd.DataFrame(), 0.0, pd.Series(), []
        
        df = df_players[df_players['PLAYER'].isin(valid_players)].copy()
        
        if scoring_method == "Threshold Smart":
            fp, player_details = calculate_threshold_value(df, punt_cats, min_threshold, penalty_curve)
        elif scoring_method == "Quality > Quantity":
            fp = calculate_quality_over_quantity(df, punt_cats)
            player_details = []
        elif scoring_method == "Diminishing Returns":
            fp = calculate_diminishing_returns(df, punt_cats)
            player_details = []
        else:
            weights = BASE_WEIGHTS.copy()
            for cat in punt_cats:
                if cat == "FG Punt":
                    weights["FGM"] = 0.0
                    weights["FGA"] = 0.0
                elif cat == "FT Punt":
                    weights["FTM"] = 0.0
                    weights["FTA"] = 0.0
                elif cat == "TO Punt":
                    weights["TO"] = 0.0
            
            available_cols = [col for col in weights.keys() if col in df.columns]
            avg_stats = df[available_cols].mean()
            fp = sum(avg_stats[col] * weights[col] for col in available_cols)
            player_details = []
        
        numeric_cols = df.select_dtypes(include='number').columns
        avg_stats = df[numeric_cols].mean()
        return df, fp, avg_stats, player_details

    df_1, fp_1, avg_1, details_1 = analyze(side_1)
    df_2, fp_2, avg_2, details_2 = analyze(side_2)
    
    if df_1.empty or df_2.empty:
        st.warning("⚠️ Some players unavailable")
        if df_1.empty and df_2.empty:
            return

    diff = fp_1 - fp_2
    confidence = min(100, abs(diff) * 10)

    st.markdown("---")
    with st.container(border=True):
        st.markdown("## Trade Result")
        r1, r2, r3 = st.columns([1, 2, 1])
        
        with r1:
            st.metric("Team 1", f"{fp_1:.1f}", delta=f"{diff:.1f}" if diff != 0 else None)
        
        with r3:
            st.markdown(f"""
                <div style="text-align: right;">
                    <div style="color: rgba(255, 255, 255, 0.6); font-size: 0.875rem;">Team 2</div>
                    <div style="font-size: 2.25rem; font-weight: 600;">{fp_2:.1f}</div>
                    <div style="color: {'#4ade80' if diff > 0 else '#f87171'}; font-size: 0.875rem;">
                        {'↓' if diff > 0 else '↑'} {abs(diff):.1f}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with r2:
            if abs(diff) < 2:
                st.success(" FAIR TRADE")
            elif diff > 0:
                st.success(f" TEAM 1 WINS")
                st.caption(f"+{diff:.1f} advantage")
            else:
                st.error(f" TEAM 2 WINS")
                st.caption(f"+{abs(diff):.1f} advantage")
            st.progress(confidence / 100)

    # --- STAT BREAKDOWN ---
    st.markdown("### Stat Breakdown")
    stats_config = [
        ('PTS', 'Points', False), ('REB', 'Rebs', False), ('AST', 'Asts', False),
        ('STL', 'Stls', False), ('BLK', 'Blks', False), ('3PM', '3PM', False), ('TO', 'TO', True)
    ]
    
    for key, label, lower_better in stats_config:
        if key not in avg_1: continue
        v1, v2 = avg_1[key], avg_2[key]
        t1_wins = v1 < v2 if lower_better else v1 > v2
        max_val = max(abs(v1), abs(v2))
        w1 = (abs(v1)/max_val)*50 if max_val else 0
        w2 = (abs(v2)/max_val)*50 if max_val else 0
        
        st.markdown(f"""
            <div class='stat-comparison'>
                <div class='stat-label'>{label}</div>
                <div class='stat-bar-container'>
                    <div style='flex:1; text-align:right;'><div class='stat-bar team-1-bar' style='width:{w1}%; margin-left:auto;'>{v1:.1f}</div></div>
                    <div style='width:40px; text-align:center; font-weight:bold; color:#888;'>{"1" if t1_wins else "2"}</div>
                    <div style='flex:1;'><div class='stat-bar team-2-bar' style='width:{w2}%;'>{v2:.1f}</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # --- DETAILED STATS ---
    st.markdown("### Detailed Stats")
    
    c_t1, c_t2 = st.columns(2)
    
    for idx, (df_side, col_container, title) in enumerate([
        (df_1, c_t1, "Team 1"),
        (df_2, c_t2, "Team 2")
    ]):
        with col_container:
            st.markdown(f"**{title}:**")
            
            display_cols = ['PLAYER', 'PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'TO']
            display_df = df_side[display_cols].copy()
            
            fg_vals = []
            ft_vals = []
            
            for _, row in df_side.iterrows():
                fgm = row.get('FGM', 0)
                fga = row.get('FGA', 0)
                fg_pct = row.get('FG%', 0)
                
                ftm = row.get('FTM', 0)
                fta = row.get('FTA', 0)
                ft_pct = row.get('FT%', 0)
                
                fg_vals.append(f"{fgm:.1f}/{fga:.1f} ({fg_pct:.1f}%)")
                ft_vals.append(f"{ftm:.1f}/{fta:.1f} ({ft_pct:.1f}%)")
            
            display_df['FG'] = fg_vals
            display_df['FT'] = ft_vals
            
            final_cols = ['PLAYER', 'PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'FG', 'FT', 'TO']
            display_df = display_df[final_cols]
            
            numeric_only = ['PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'TO']
            
            st.dataframe(
                display_df.style.format("{:.1f}", subset=numeric_only),
                use_container_width=True,
                hide_index=True
            )

if __name__ == "__main__":
    render_trade_analyzer_page()
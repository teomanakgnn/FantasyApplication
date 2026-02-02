import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import concurrent.futures
import sys
import os
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
                        sidebar.style.width = '0';
                        sidebar.style.minWidth = '0';
                        sidebar.style.transform = 'translateX(-100%)';
                        sidebar.setAttribute('aria-expanded', 'false');
                        
                        if (isMobile) {
                            sidebar.style.display = 'none';
                        }
                    }
                }
            }, 300);
        }
        
        // BACKDROP OLUŞTUR (MOBİLDE SIDEBAR DIŞINA TIKLANINCA KAPANSIN)
        function createBackdrop() {
            const isMobile = window.parent.innerWidth <= 768;
            if (!isMobile) return;
            
            // Backdrop zaten varsa sil
            if (backdropElement) {
                backdropElement.remove();
                backdropElement = null;
            }
            
            const state = getSidebarState();
            if (!state || state.isClosed) return;
            
            backdropElement = window.parent.document.createElement('div');
            backdropElement.id = 'sidebar-backdrop';
            backdropElement.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                z-index: 999998;
                cursor: pointer;
            `;
            
            // Backdrop'a tıklayınca sidebar'ı kapat
            backdropElement.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                toggleSidebar();
            });
            
            window.parent.document.body.appendChild(backdropElement);
        }
        
        // BACKDROP'U KALDIR
        function removeBackdrop() {
            if (backdropElement) {
                backdropElement.remove();
                backdropElement = null;
            }
        }
        
        // Global bir referans tanımlayalım ki updateVisibility erişebilsin
        let hoopLifeTrigger = null;

        function createHoopLifeDock() {
            // Eğer zaten varsa tekrar oluşturma
            hoopLifeTrigger = window.parent.document.getElementById('hooplife-master-trigger');
            if (hoopLifeTrigger) return;
            
            const triggerElement = window.parent.document.createElement('div');
            triggerElement.id = 'hooplife-master-trigger';
            hoopLifeTrigger = triggerElement; // Global referansa ata
            
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
                // Sidebar açılacağı için görünürlüğü hemen güncelle
                updateVisibility();
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
            if (!trigger) return;
            
            const state = getSidebarState(); 
            const isMobile = window.parent.innerWidth <= 768;
            const sidebarWidth = 350; // Sidebar genişliğinize göre burayı güncelleyin

            if (state) {
                if (!state.isClosed) {
                    // SIDEBAR AÇIKKEN (Premium Görünüm)
                    Object.assign(trigger.style, {
                        position: 'fixed',             // Ekranın üstüne sabitlemek için
                        top: '15px',
                        left: isMobile ? 'calc(100% - 60px)' : `${sidebarWidth - 20}px`,
                        background: 'rgba(255, 75, 75, 0.9)', // Hafif şeffaf canlı kırmızı
                        backdropFilter: 'blur(8px)',          // Cam efekti
                        width: '40px',
                        height: '40px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: '12px',                 // Daha modern yumuşak köşeler
                        boxShadow: '0 4px 15px rgba(255, 75, 75, 0.3)', // Derinlik için gölge
                        border: '1px solid rgba(255, 255, 255, 0.2)',
                        cursor: 'pointer',
                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
                    });

                    // Daha zarif, ince hatlı X ikonu
                    trigger.innerHTML = `
                        <div class="close-icon-wrapper" style="position: relative; width: 16px; height: 16px;">
                            <span style="position: absolute; top: 50%; width: 100%; height: 1.5px; background: white; transform: rotate(45deg); transition: 0.3s;"></span>
                            <span style="position: absolute; top: 50%; width: 100%; height: 1.5px; background: white; transform: rotate(-45deg); transition: 0.3s;"></span>
                        </div>
                    `;
                } else {
                    // SIDEBAR KAPALIYKEN (Şık Basketbol Çentiği)
                    trigger.style.left = '0';
                    trigger.style.width = '45px';
                    trigger.style.background = '#1a1c24';
                    trigger.style.borderRadius = '0 15px 15px 0';
                    trigger.innerHTML = `
                        <div id="hl-icon" style="font-size: 26px; filter: drop-shadow(0 0 8px rgba(255, 75, 75, 0.5));">🏀</div>
                    `;
                }
            }
        }
        
        // BAŞLAT
        function init() {
            createHoopLifeDock();
            setTimeout(updateVisibility, 500);
            setInterval(updateVisibility, 100);
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
# 2025-26 Sezonu Başlangıç Tarihi (Tahmini/Varsayılan)
SEASON_START_DATE = datetime(2025, 10, 22)

DEFAULT_WEIGHTS = {
    "PTS": 1.0, "REB": 0.4, "AST": 0.7, "STL": 1.1, "BLK": 0.75, "TO": -1.0,
    "FGA": -0.7, "FGM": 0.5, "FTA": -0.4, "FTM": 0.6, "3Pts": 0.3,
}

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
    
    # İki farklı periyot seçimi
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
        index=1  # "Last 15 Days" varsayılan
    )
    period1_days = period_options[period1_label]
    
    period2_label = st.sidebar.selectbox(
        "Period 2:", 
        options=list(period_options.keys()), 
        index=4  # "Full Season" varsayılan
    )
    period2_days = period_options[period2_label]
    
    st.sidebar.markdown("### Filters")
    
    # Maç Sayısı Filtresi (Her iki periyot için)
    min_games_p1 = st.sidebar.number_input(
        f"Min Games (Period 1)", 
        min_value=1, max_value=20, value=3
    )
    
    min_games_p2 = st.sidebar.number_input(
        f"Min Games (Period 2)", 
        min_value=1, max_value=30, value=5
    )
    
    # Min ve Max Avg Score Filtreleri
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
    background_url = "https://wallpapers.com/images/featured/stock-market-pd5zksxr07t7a4xu.jpg"
    
    # Apply background if URL provided
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
                /* Optional: Add overlay for better text readability */
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

    # 4. PARALEL VERİ ÇEKME FONKSİYONLARI (Helper)
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

    # 5. VERİ ÇEKME & İŞLEME (SEZONLUK DATA)
    if "season_data" not in st.session_state:
        st.session_state.season_data = None

    # Eğer veri yoksa yükle (Tüm sezonu çeker)
    if st.session_state.season_data is None:
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        today = datetime.now()
        # Sezon başından bugüne kadar olan gün sayısı
        delta = today - SEASON_START_DATE
        total_days = delta.days + 1
        
        # Tarih listesi (Sezon başından bugüne)
        dates_to_fetch = [SEASON_START_DATE + timedelta(days=i) for i in range(total_days)]
        
        all_records = []
        all_game_tasks = []

        # A. Schedule Çekme
        status_text.text(f"Fetching full season schedule ({total_days} days)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_date = {executor.submit(fetch_games_for_date, d): d for d in dates_to_fetch}
            for i, future in enumerate(concurrent.futures.as_completed(future_to_date)):
                date, ids = future.result()
                if ids:
                    for gid in ids:
                        all_game_tasks.append((gid, date))
                progress_bar.progress(int((i / len(dates_to_fetch)) * 20)) # %20'si schedule

        # B. Box Scores Çekme
        total_games = len(all_game_tasks)
        status_text.text(f"Fetching stats for {total_games} games (Season)...")
        
        if total_games > 0:
            with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
                future_to_game = {executor.submit(fetch_boxscore_for_game, task): task for task in all_game_tasks}
                for i, future in enumerate(concurrent.futures.as_completed(future_to_game)):
                    result = future.result()
                    if result:
                        all_records.extend(result)
                    
                    # Progress Bar (%20 -> %100 arası)
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
    
    # 7. İKİ PERİYOT ANALİZİ
    today_ts = pd.Timestamp.now()
    
    # Period 1
    if period1_days == 999:  # Full Season
        df_p1 = df.copy()
    else:
        p1_start_date = today_ts - pd.Timedelta(days=period1_days)
        df_p1 = df[df["date"] >= p1_start_date].copy()
    
    # Period 2
    if period2_days == 999:  # Full Season
        df_p2 = df.copy()
    else:
        p2_start_date = today_ts - pd.Timedelta(days=period2_days)
        df_p2 = df[df["date"] >= p2_start_date].copy()

    # Eğer periyotlarda veri yoksa uyar
    if df_p1.empty or df_p2.empty:
        st.info("Seçilen periyotlar için yeterli veri bulunamadı.")
        return

    # 8. ORTALAMALAR VE GRUPLAMA
    # Period 1 Ortalamaları
    grp_p1 = df_p1.groupby("PLAYER").agg({
        "fantasy_score": "mean",
        "TEAM": "first",
        "date": "count"
    }).rename(columns={"fantasy_score": "avg_p1", "date": "games_p1"})

    # Period 2 Ortalamaları
    grp_p2 = df_p2.groupby("PLAYER").agg({
        "fantasy_score": "mean",
        "TEAM": "first",
        "date": "count"
    }).rename(columns={"fantasy_score": "avg_p2", "date": "games_p2"})

    # 9. BİRLEŞTİRME
    # Inner Join: Her iki periyotta da verisi olanlar
    analysis_df = grp_p1.join(grp_p2[["avg_p2", "games_p2"]], how="inner")
    
    # FİLTRELEME
    # 1. Maç Sayısı Filtreleri
    analysis_df = analysis_df[
        (analysis_df["games_p1"] >= min_games_p1) & 
        (analysis_df["games_p2"] >= min_games_p2)
    ]
    
    # 2. Ortalama Puan Filtreleri (Her iki periyot için)
    analysis_df = analysis_df[
        (analysis_df["avg_p1"] >= min_avg_score) & 
        (analysis_df["avg_p1"] <= max_avg_score) &
        (analysis_df["avg_p2"] >= min_avg_score) & 
        (analysis_df["avg_p2"] <= max_avg_score)
    ]
    
    # Fark Hesapla (Period 1 - Period 2)
    analysis_df["diff"] = analysis_df["avg_p1"] - analysis_df["avg_p2"]
    
    # Sıralama
    risers = analysis_df.sort_values("diff", ascending=False).head(5)
    fallers = analysis_df.sort_values("diff", ascending=True).head(5)

    # 10. GÖRSELLEŞTİRME (RISERS & FALLERS)
    
    # RISERS
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

    # FALLERS
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

    # 11. DETAYLI TABLO (Sadece Comparison Table)
    st.subheader(f"Comparison Table ({len(analysis_df)} Players)")
    
    # Tabloyu hazırlama
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

if __name__ == "__main__":
    render_player_trends_page()
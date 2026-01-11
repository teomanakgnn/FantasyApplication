import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import concurrent.futures
import sys
import os

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
    
    st.title("📈 Player Form & Trends")
    
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
    st.subheader(f"📊 Comparison Table ({len(analysis_df)} Players)")
    
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
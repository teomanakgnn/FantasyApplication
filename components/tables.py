import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from utils.helpers import parse_minutes
# Gerekli tüm fonksiyonları import ediyoruz
from services.espn_api import get_historical_boxscores, get_injuries 

# =================================================================
# 1. YARDIMCI HESAPLAMA FONKSİYONLARI
# =================================================================

def calculate_fantasy_score(stats_dict, weights):
    """
    Verilen istatistiklere ve ağırlıklara göre fantezi puanını hesaplar.
    """
    score = 0.0
    for stat, weight in weights.items():
        val = stats_dict.get(stat, 0)
        try:
            score += float(val) * float(weight)
        except (ValueError, TypeError):
            pass
    return score

def get_date_range(period):
    """
    Seçilen periyoda göre tarih aralığını döndürür.
    """
    today = datetime.now()
    if period == "Today":
        return today.date(), today.date()
    elif period == "This Week":
        start = today - timedelta(days=today.weekday())
        return start.date(), today.date()
    elif period == "This Month":
        start = today.replace(day=1)
        return start.date(), today.date()
    elif period == "Season":
        if today.month >= 10:
            season_start = today.replace(month=10, day=22)
        else:
            season_start = today.replace(year=today.year - 1, month=10, day=22)
        return season_start.date(), today.date()
    return today.date(), today.date()

def aggregate_player_stats(all_game_data, weights):
    """
    Geçmiş maç verilerini toplar, ortalamasını alır ve puanı hesaplar.
    """
    player_totals = {}
    
    for game_day in all_game_data:
        players = game_day.get('players', [])
        game_date = game_day.get('date')  # Tarihi al
        
        for player in players:
            key = f"{player.get('PLAYER')}_{player.get('TEAM')}"
            
            if key not in player_totals:
                player_totals[key] = {
                    'PLAYER': player.get('PLAYER'),
                    'TEAM': player.get('TEAM'),
                    'GAMES': 0,
                    'MIN_TOTAL': 0,
                    'PTS': 0, 'REB': 0, 'AST': 0, 'STL': 0, 'BLK': 0, 'TO': 0,
                    'FGM': 0, 'FGA': 0, '3Pts': 0, '3PTA': 0, 'FTM': 0, 'FTA': 0,
                    '+/-': 0,
                    'game_logs': []  # Her oyun için detaylı log
                }
            
            stats = player_totals[key]
            stats['GAMES'] += 1
            stats['MIN_TOTAL'] += parse_minutes(player.get('MIN', '0'))
            
            numeric_stats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 
                           'FGM', 'FGA', '3Pts', '3PTA', 'FTM', 'FTA', '+/-']
            
            for stat in numeric_stats:
                val = player.get(stat, 0)
                try: stats[stat] += float(val)
                except: pass
            
            # Her oyun için log kaydet (MVP/LVP analizi için)
            game_log = {
                'DATE': game_date,
                'MIN': parse_minutes(player.get('MIN', '0'))
            }
            for stat in numeric_stats:
                game_log[stat] = player.get(stat, 0)
            stats['game_logs'].append(game_log)
    
    result = []
    for stats in player_totals.values():
        games = stats['GAMES']
        if games > 0:
            avg_stats = stats.copy()
            
            # Ortalamaları al
            avg_stats['MIN'] = f"{int(stats['MIN_TOTAL'] / games)}"
            avg_stats['MIN_INT'] = stats['MIN_TOTAL'] / games
            
            stats_to_average = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 
                              'FGM', 'FGA', '3Pts', '3PTA', 'FTM', 'FTA', '+/-']
            
            for k in stats_to_average:
                avg_stats[k] = stats[k] / games

            # Skoru hesapla
            avg_stats['USER_SCORE'] = calculate_fantasy_score(avg_stats, weights)
            
            # Formatlama (Görsel için)
            avg_stats['FG'] = f"{avg_stats['FGM']:.1f}/{avg_stats['FGA']:.1f}"
            avg_stats['3PT'] = f"{avg_stats['3Pts']:.1f}/{avg_stats['3PTA']:.1f}"
            avg_stats['FT'] = f"{avg_stats['FTM']:.1f}/{avg_stats['FTA']:.1f}"
            
            result.append(avg_stats)
    
    return pd.DataFrame(result)

# =================================================================
# 2. OYUNCU ANALİZ MODALI (YENİLENMİŞ PRO UI & ANALİZ)
# =================================================================
@st.dialog("Player Insights", width="large")
def show_player_analysis(player_row, weights):

    # ======================================================
    # A. VERİ HAZIRLIĞI
    # ======================================================
    name = player_row["PLAYER"]
    team = player_row["TEAM"]
    score = float(player_row["USER_SCORE"])
    mins = float(player_row.get("MIN_INT", 0))

    pts = float(player_row.get("PTS", 0))
    reb = float(player_row.get("REB", 0))
    ast = float(player_row.get("AST", 0))
    stl = float(player_row.get("STL", 0))
    blk = float(player_row.get("BLK", 0))
    to = float(player_row.get("TO", 0))

    fga = float(player_row.get("FGA", 0))
    fgm = float(player_row.get("FGM", 0))
    fta = float(player_row.get("FTA", 0))
    ftm = float(player_row.get("FTM", 0))

    stocks = stl + blk
    fp_min = score / mins if mins > 0 else 0
    fg_pct = (fgm / fga * 100) if fga > 0 else 0
    ft_pct = (ftm / fta * 100) if fta > 0 else 0

    # Yeni metrikler
    usage_proxy = fga + 0.44 * fta + ast
    impact_score = pts + reb*1.2 + ast*1.5 + stocks*3 - to*2

    # ======================================================
    # B. ANALİZ MOTORU
    # ======================================================
    analysis_tags = []

    if fga >= 20:
        analysis_tags.append(("🔥 High Volume", "Hücumda ana opsiyon olarak oynadı.", "high"))
    elif fga <= 5 and mins > 20:
        analysis_tags.append(("👻 Passive", "Dakika aldı ama hücumda silikti.", "low"))

    if fp_min >= 1.4:
        analysis_tags.append(("💎 Elite Efficiency", "Dakika başına elit fantasy verim.", "high"))
    elif fp_min < 0.8 and mins > 15:
        analysis_tags.append(("❄️ Cold", "Verim fantasy için yetersiz.", "low"))

    if stocks >= 4:
        analysis_tags.append(("🔒 Lockdown", "Savunma katkısı üst seviye.", "high"))

    if ast >= 10:
        analysis_tags.append(("🧠 Playmaker", "Hücumu yönlendiren ana isim.", "high"))

    if fga > 18 and fp_min < 0.9:
        analysis_tags.append(("🟡 Empty Volume", "Şut hacmi var, fantasy karşılığı zayıf.", "mid"))

    if mins < 22 and fp_min > 1.3:
        analysis_tags.append(("⚠️ Volatile", "Yüksek verim – düşük dakika riski.", "mid"))

    # ======================================================
    # C. SAKATLIK BAĞLAMI
    # ======================================================
    all_injuries = get_injuries()
    team_injuries = [
        inj for inj in all_injuries
        if inj["team"].upper() == team.upper() and "Out" in inj.get("status", "")
    ]
    missing = [i["player"] for i in team_injuries]

    context_msg = ""
    if missing:
        if fga >= 15:
            context_msg = f"**{', '.join(missing[:2])}** yokluğunda hücum yükünü üstlendi."
        else:
            context_msg = f"Takımda **{len(missing)}** eksik olmasına rağmen hücumda öne çıkamadı."

    # ======================================================
    # D. SCOUT REPORT (OTOMATİK YORUM)
    # ======================================================
    scout_report = f"""
**{name}**, bu maçta **{int(mins)} dakika** sahada kaldı ve  
**{score:.1f} fantasy puan** üretti.

Hücumda **{int(fga)} şut** kullanarak belirgin bir rol üstlendi.  
Dakika başına üretimi **{fp_min:.2f} FP/Min** seviyesinde.
"""

    if fp_min >= 1.3:
        scout_report += "\nBu seviye **elit fantasy verim** bandına giriyor."
    elif fp_min < 0.8:
        scout_report += "\nBu performans fantasy açısından **zayıf** kaldı."

    # ======================================================
    # E. UI STİL
    # ======================================================
    st.markdown("""
    <style>
    .kpi-box { text-align:center; padding:12px; border-radius:10px; background:#f1f3f5; }
    .kpi-label { font-size:0.7rem; color:#666; }
    .kpi-value { font-size:1.4rem; font-weight:800; }
    .main-score { font-size:3rem; font-weight:900; }
    </style>
    """, unsafe_allow_html=True)

    # ======================================================
    # F. HEADER
    # ======================================================
    h1, h2 = st.columns([3,1])
    with h1:
        st.markdown(f"### {name}")
        st.caption(team)

        for tag, desc, level in analysis_tags:
            color = "#d4edda" if level=="high" else "#fff3cd" if level=="mid" else "#f8d7da"
            st.markdown(
                f"<span style='background:{color};padding:4px 10px;border-radius:12px;font-size:0.8rem;margin-right:6px'>{tag}</span>",
                unsafe_allow_html=True
            )

    with h2:
        st.markdown(f"<div class='main-score'>{int(score)}</div>", unsafe_allow_html=True)
        st.caption("Fantasy PTS")

    st.divider()

    # ======================================================
    # G. KPI STRIP
    # ======================================================
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(f"<div class='kpi-box'><div class='kpi-label'>FP / MIN</div><div class='kpi-value'>{fp_min:.2f}</div></div>", unsafe_allow_html=True)
    k2.markdown(f"<div class='kpi-box'><div class='kpi-label'>USAGE</div><div class='kpi-value'>{usage_proxy:.1f}</div></div>", unsafe_allow_html=True)
    k3.markdown(f"<div class='kpi-box'><div class='kpi-label'>IMPACT</div><div class='kpi-value'>{impact_score:.1f}</div></div>", unsafe_allow_html=True)
    k4.markdown(f"<div class='kpi-box'><div class='kpi-label'>STOCKS</div><div class='kpi-value'>{int(stocks)}</div></div>", unsafe_allow_html=True)

    st.divider()

    # ======================================================
    # H. ANALYSIS SECTIONS
    # ======================================================
    left, right = st.columns([1.4,1])

    with left:
        st.subheader("📋 Scout Report")
        st.markdown(scout_report)

        if context_msg:
            st.info(context_msg, icon="🩺")

        st.subheader("🔮 Fantasy Outlook")
        if fp_min >= 1.2 and mins >= 28:
            st.success("🔒 Güvenli starter – yüksek taban")
        elif fp_min >= 1.2 and mins < 25:
            st.warning("⚠️ Boom/Bust – dakika artarsa patlar")
        elif fp_min < 0.8:
            st.error("❄️ Fade – fantasy katkı zayıf")
        else:
            st.info("🟡 Ortalama fantasy katkı")

    with right:
        st.subheader("🎯 Shooting")
        st.markdown(f"**FG:** {int(fgm)}/{int(fga)} ({fg_pct:.0f}%)")
        st.progress(min(fg_pct/100, 1.0))
        if fta > 0:
            st.markdown(f"**FT:** {int(ftm)}/{int(fta)} ({ft_pct:.0f}%)")
            st.progress(min(ft_pct/100, 1.0))


# =================================================================
# 3. ANA TABLO FONKSİYONU (MVP/LVP İÇİN VERİ KAYDETME EKLENDİ)
# =================================================================
def render_tables(today_df, weights, default_period="Today"):
    
    if "stats_period" not in st.session_state:
        st.session_state.stats_period = default_period
        
    st.markdown("### 📅 Time Period")
    cols = st.columns(4)
    periods = ["Today", "This Week", "This Month", "Season"]
    
    for i, p in enumerate(periods):
        style = "primary" if st.session_state.stats_period == p else "secondary"
        if cols[i].button(p, key=f"btn_{p}", type=style, use_container_width=True):
            st.session_state.stats_period = p
            st.rerun()
            
    current_period = st.session_state.stats_period
    active_df = pd.DataFrame()
    raw_period_data = []  # MVP/LVP için ham veri
    
    # --- VERİ HAZIRLIĞI ---
    if current_period == "Today":
        active_df = today_df.copy()
        if not active_df.empty:
            active_df["USER_SCORE"] = active_df.apply(lambda x: calculate_fantasy_score(x, weights), axis=1)
            if "MIN_INT" not in active_df.columns:
                active_df["MIN_INT"] = active_df["MIN"].apply(parse_minutes)
            
            # Today için period_df olarak kaydet
            st.session_state["period_df"] = active_df.copy()
    else:
        start_date, end_date = get_date_range(current_period)
        with st.spinner(f"Fetching stats for {current_period}..."):
            historical_data = get_historical_boxscores(start_date, end_date)
            if historical_data:
                # Önce aggregate edilmiş veriyi oluştur (tablo için)
                active_df = aggregate_player_stats(historical_data, weights)
                
                # MVP/LVP için her günün RAW verisini kaydet
                all_daily_records = []
                for game_day in historical_data:
                    players = game_day.get('players', [])
                    game_date = game_day.get('date')
                    
                    for player in players:
                        record = {
                            'DATE': pd.to_datetime(game_date) if game_date else pd.Timestamp.now(),
                            'PLAYER': player.get('PLAYER'),
                            'TEAM': player.get('TEAM'),
                            'MIN': parse_minutes(player.get('MIN', '0'))
                        }
                        
                        # Tüm stat'ları ekle
                        numeric_stats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 
                                       'FGM', 'FGA', '3Pts', '3PTA', 'FTM', 'FTA', '+/-']
                        for stat in numeric_stats:
                            val = player.get(stat, 0)
                            try:
                                record[stat] = float(val)
                            except:
                                record[stat] = 0
                        
                        all_daily_records.append(record)
                
                # DataFrame'e çevir ve session state'e kaydet
                if all_daily_records:
                    period_df = pd.DataFrame(all_daily_records)
                    st.session_state["period_df"] = period_df

    if active_df.empty:
        st.warning(f"No data available for {current_period}")
        return

    # --- VERİ TİPİ VE YUVARLAMA ---
    if "USER_SCORE" in active_df.columns:
        active_df["USER_SCORE"] = active_df["USER_SCORE"].astype(float).round(2)
        
    if "+/-" in active_df.columns:
         active_df["+/-"] = pd.to_numeric(active_df["+/-"], errors='coerce').fillna(0)

    is_today = (current_period == "Today")
    stat_cols = ["PTS", "REB", "AST", "STL", "BLK", "TO", "+/-"]
    
    for col in stat_cols:
        if col in active_df.columns:
            if is_today:
                active_df[col] = active_df[col].fillna(0).astype(int)
            else:
                active_df[col] = active_df[col].astype(float).round(1)

    # --- TABLO YAPISI ---
    column_order = ["PLAYER", "TEAM", "USER_SCORE", "MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "STL", "BLK", "TO", "+/-"]
    if not is_today:
        column_order.insert(2, "GAMES")
        
    available_cols = [c for c in column_order if c in active_df.columns]
    stat_fmt = "%d" if is_today else "%.1f"

    col_config = {
        "PLAYER": st.column_config.TextColumn("Player", width="medium"),
        "TEAM": st.column_config.TextColumn("Team", width="small"),
        "GAMES": st.column_config.NumberColumn("GP", format="%d", width="small"),
        "USER_SCORE": st.column_config.NumberColumn("Score", format="%.2f", width="small"),
        "MIN": st.column_config.TextColumn("Min", width="small"),
        "PTS": st.column_config.NumberColumn("PTS", format=stat_fmt, width="small"),
        "REB": st.column_config.NumberColumn("REB", format=stat_fmt, width="small"),
        "AST": st.column_config.NumberColumn("AST", format=stat_fmt, width="small"),
        "STL": st.column_config.NumberColumn("STL", format=stat_fmt, width="small"),
        "BLK": st.column_config.NumberColumn("BLK", format=stat_fmt, width="small"),
        "TO": st.column_config.NumberColumn("TO", format=stat_fmt, width="small"),
        "+/-": st.column_config.NumberColumn("+/-", format=stat_fmt, width="small"),
    }

    st.markdown("---")
    st.caption("💡 **Tip:** Click on a player row to see **Context & Injury Analysis**.")

    # --- TOP 10 ---
    st.markdown(f"## 🔥 Top 10 Performances ({current_period})")
    top_df = active_df.sort_values("USER_SCORE", ascending=False).head(10)
    
    event_top = st.dataframe(
        top_df[available_cols],
        use_container_width=True,
        hide_index=True,
        column_config=col_config,
        height=380,
        on_select="rerun",
        selection_mode="single-row"
    )
    
    if len(event_top.selection.rows) > 0:
        selected_index = event_top.selection.rows[0]
        selected_row = top_df.iloc[selected_index]
        show_player_analysis(selected_row, weights)

    # --- WORST 10 ---
    st.markdown(f"## 📉 Lowest 10 Performances ({current_period})")
    min_minutes = 17 
    filtered_low = active_df[active_df["MIN_INT"] >= min_minutes]
    if len(filtered_low) < 5: filtered_low = active_df[active_df["MIN_INT"] >= 5]
    
    low_df = filtered_low.sort_values("USER_SCORE", ascending=True).head(10)
    
    event_low = st.dataframe(
        low_df[available_cols],
        use_container_width=True,
        hide_index=True,
        column_config=col_config,
        height=380,
        on_select="rerun",
        selection_mode="single-row"
    )

    if len(event_low.selection.rows) > 0:
        selected_index = event_low.selection.rows[0]
        selected_row = low_df.iloc[selected_index]
        show_player_analysis(selected_row, weights)

    # --- FULL LIST ---
    with st.expander(f"📋 Full Player List ({len(active_df)} players)"):
        st.dataframe(active_df.sort_values("USER_SCORE", ascending=False)[available_cols], use_container_width=True, hide_index=True, column_config=col_config)
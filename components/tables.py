import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from utils.helpers import parse_minutes
from services.espn_api import get_historical_boxscores, get_injuries, get_current_team_rosters, get_nba_season_stats_official 
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

def normalize_player_name(name):
    """İsimleri karşılaştırma için normalize eder"""
    if not name:
        return ""
    return name.replace(".", "").replace("'", "").replace("-", " ").lower().strip()

def aggregate_player_stats(all_game_data, weights):
    """
    Geçmiş maç verilerini toplar, ortalamasını alır ve puanı hesaplar.
    **ÖNEMLİ:** Oyuncuları sadece isme göre takip eder, güncel takım bilgisini kullanır.
    """
    # Güncel roster bilgisini al
    try:
        current_rosters = get_current_team_rosters()
        print(f"✓ Roster bilgisi alındı: {len(current_rosters)} oyuncu")
    except Exception as e:
        print(f"❌ Roster alınamadı: {e}")
        current_rosters = {}
    
    # Normalize edilmiş roster dictionary oluştur
    normalized_rosters = {}
    for player_name, team in current_rosters.items():
        norm_name = normalize_player_name(player_name)
        normalized_rosters[norm_name] = {
            'team': team,
            'original_name': player_name
        }
    
    print(f"✓ Normalize edilmiş roster: {len(normalized_rosters)} oyuncu")
    
    player_totals = {}
    matched_count = 0
    unmatched_count = 0
    
    for game_day in all_game_data:
        players = game_day.get('players', [])
        game_date = game_day.get('date')
        
        for player in players:
            raw_name = player.get('PLAYER')
            if not raw_name:
                continue
            
            # İsmi normalize et
            norm_name = normalize_player_name(raw_name)
            
            # Güncel roster'dan oyuncuyu bul
            roster_info = normalized_rosters.get(norm_name)
            
            if roster_info:
                # Roster'da bulundu - resmi ismi ve güncel takımı kullan
                display_name = roster_info['original_name']
                current_team = roster_info['team']
                matched_count += 1
            else:
                # Roster'da yok - ham ismi kullan
                display_name = raw_name
                current_team = player.get('TEAM', 'UNK')
                unmatched_count += 1
                
                # Debug için (tarih tipini kontrol et)
                if game_date:
                    try:
                        date_diff = (datetime.now() - pd.to_datetime(game_date)).days
                        if date_diff < 7 and unmatched_count <= 10:  # İlk 10 uyumsuzluğu göster
                            print(f"⚠️ Roster'da bulunamadı: {raw_name} (Normalized: {norm_name})")
                    except:
                        pass
            
            # KEY: SADECE OYUNCU İSMİ (takım yok!)
            key = display_name
            
            if key not in player_totals:
                player_totals[key] = {
                    'PLAYER': display_name,
                    'TEAM': current_team,  # Güncel takım
                    'GAMES': 0,
                    'MIN_TOTAL': 0,
                    'PTS': 0, 'REB': 0, 'AST': 0, 'STL': 0, 'BLK': 0, 'TO': 0,
                    'FGM': 0, 'FGA': 0, '3Pts': 0, '3PTA': 0, 'FTM': 0, 'FTA': 0,
                    '+/-': 0,
                    'game_logs': [],
                    'teams_played_for': set()  # Hangi takımlarda oynadığını takip et
                }
            
            stats = player_totals[key]
            
            # Takım bilgisini güncelle (her zaman en güncel)
            stats['TEAM'] = current_team
            
            # Bu oyuncunun oynadığı takımları kaydet
            game_team = player.get('TEAM', '')
            if game_team:
                stats['teams_played_for'].add(game_team)
            
            # Maç sayısını artır
            stats['GAMES'] += 1
            
            # Dakika parse et
            min_val = parse_minutes(player.get('MIN', '0'))
            stats['MIN_TOTAL'] += min_val
            
            # Numerik statları topla
            numeric_stats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 
                           'FGM', 'FGA', '3Pts', '3PTA', 'FTM', 'FTA', '+/-']
            
            for stat in numeric_stats:
                val = player.get(stat, 0)
                try: 
                    stats[stat] += float(val)
                except: 
                    pass
            
            # Her oyun için log kaydet (MVP/LVP analizi için)
            game_log = {
                'DATE': game_date,
                'MIN': min_val,
                'TEAM': game_team  # O maçta hangi takımda oynadı
            }
            for stat in numeric_stats:
                try:
                    game_log[stat] = float(player.get(stat, 0))
                except:
                    game_log[stat] = 0
            stats['game_logs'].append(game_log)
    
    # Ortalamaları hesapla
    result = []
    for stats in player_totals.values():
        games = stats['GAMES']
        if games == 0:
            continue
            
        avg_stats = stats.copy()
        
        # Ortalama dakika
        avg_min = stats['MIN_TOTAL'] / games
        avg_stats['MIN'] = f"{int(avg_min)}"
        avg_stats['MIN_INT'] = avg_min
        
        # Diğer ortalamaları
        stats_to_average = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 
                          'FGM', 'FGA', '3Pts', '3PTA', 'FTM', 'FTA', '+/-']
        
        for k in stats_to_average:
            avg_stats[k] = stats[k] / games

        # Fantasy skorunu hesapla
        avg_stats['USER_SCORE'] = calculate_fantasy_score(avg_stats, weights)
        
        # Shooting formatlama
        avg_stats['FG'] = f"{avg_stats['FGM']:.1f}/{avg_stats['FGA']:.1f}"
        avg_stats['3PT'] = f"{avg_stats['3Pts']:.1f}/{avg_stats['3PTA']:.1f}"
        avg_stats['FT'] = f"{avg_stats['FTM']:.1f}/{avg_stats['FTA']:.1f}"
        
        # Transfer bilgisi ekle (birden fazla takımda oynadıysa)
        if len(stats['teams_played_for']) > 1:
            teams_list = sorted(list(stats['teams_played_for']))
            avg_stats['TRADED'] = f"({' → '.join(teams_list)})"
        else:
            avg_stats['TRADED'] = ""
        
        result.append(avg_stats)
    
    df = pd.DataFrame(result)
    
    # Debug özeti
    print(f"\n{'='*60}")
    print(f"📊 AGGREGATE ÖZET")
    print(f"{'='*60}")
    print(f"✓ Toplam {len(df)} oyuncu bulundu")
    print(f"✓ Roster eşleşmesi: {matched_count} oyuncu")
    print(f"⚠️ Eşleşmedi: {unmatched_count} oyuncu")
    
    # Transfer edilen oyuncuları işaretle
    if not df.empty and 'TRADED' in df.columns:
        traded = df[df['TRADED'] != '']
        if not traded.empty:
            print(f"🔄 {len(traded)} oyuncu transfer oldu:")
            for _, p in traded.iterrows():
                print(f"   • {p['PLAYER']}: {p['TRADED']}")
    print(f"{'='*60}\n")
    
    return df

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

    # Transfer bilgisi
    traded_info = player_row.get("TRADED", "")

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
**{name}**, bu periyotta **{int(mins)} dakika** sahada kaldı ve  
**{score:.1f} fantasy puan** üretti.

Hücumda **{int(fga)} şut** kullanarak belirgin bir rol üstlendi.  
Dakika başına üretimi **{fp_min:.2f} FP/Min** seviyesinde.
"""

    if traded_info:
        scout_report += f"\n\n🔄 **Transfer:** {traded_info}"

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
        st.caption(f"{team} {traded_info if traded_info else ''}")

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
# 3. ANA TABLO FONKSİYONU
# =================================================================


# Bu importların dosyanızın başında olduğundan emin olun.
# show_player_analysis fonksiyonu da bu dosyanın yukarısında tanımlı olmalıdır.

def render_tables(today_df, weights, default_period="Today"):
    """
    Ana tabloyu render eder.
    Period seçimine göre (Today, Season, Week) farklı veri kaynaklarını kullanır.
    """
    
    # Session State Başlatma
    if "stats_period" not in st.session_state:
        st.session_state.stats_period = default_period
        
    # --- PERİYOT SEÇİM BUTONLARI ---
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
    
    # =================================================================
    # VERİ HAZIRLIĞI (DATA FETCHING STRATEGY)
    # =================================================================
    
    # --- DURUM 1: SEZON (Official API - Tek İstek) ---
    if current_period == "Season":
        with st.spinner("Fetching official NBA Season Leaders..."):
            # 2026 Sezonu (2025-26)
            active_df = get_nba_season_stats_official(season_year=2026)
            
            if not active_df.empty:
                # Fantasy Puanı Hesapla
                active_df["USER_SCORE"] = active_df.apply(lambda x: calculate_fantasy_score(x, weights), axis=1)
                
                # MIN değerini sakla ve formatla
                active_df["MIN_INT"] = active_df["MIN"] # Sayısal kopya
                # Görsel için string format (örn: 34.5)
                active_df["MIN"] = active_df["MIN"].apply(lambda x: f"{x:.1f}")
                
                # Şut yüzdelerini string formatına çevir
                active_df["FG"] = active_df.apply(lambda x: f"{x['FGM']:.1f}/{x['FGA']:.1f}", axis=1)
                active_df["3PT"] = active_df.apply(lambda x: f"{x['3Pts']:.1f}/{x['3PTA']:.1f}", axis=1)
                active_df["FT"] = active_df.apply(lambda x: f"{x['FTM']:.1f}/{x['FTA']:.1f}", axis=1)
                
                # Sezon modunda "Günlük Veri" yoktur. period_df'e özet tabloyu atıyoruz.
                # NOT: Bu modda MVP/LVP widget'ı 'DATE' bulamazsa çalışmayabilir.
                st.session_state["period_df"] = active_df.copy()

    # --- DURUM 2: BUGÜN (Canlı Veri) ---
    elif current_period == "Today":
        active_df = today_df.copy()
        if not active_df.empty:
            active_df["USER_SCORE"] = active_df.apply(lambda x: calculate_fantasy_score(x, weights), axis=1)
            
            # DATE sütunu ekle (Bugünün tarihi)
            active_df["DATE"] = datetime.now().date()
            
            if "MIN_INT" not in active_df.columns:
                active_df["MIN_INT"] = active_df["MIN"].apply(parse_minutes)
            
            # Bugün verisini session'a at
            st.session_state["period_df"] = active_df.copy()

    # --- DURUM 3: HAFTALIK / AYLIK (Geçmiş Maç Toplama) ---
    else:
        start_date, end_date = get_date_range(current_period)
        with st.spinner(f"Fetching stats for {current_period}..."):
            historical_data = get_historical_boxscores(start_date, end_date)
            
            if historical_data:
                # 1. Tablo İçin Özet Veri (Aggregate)
                active_df = aggregate_player_stats(historical_data, weights)
                
                # 2. Grafikler İçin Günlük Veri (Detail Logs)
                # aggregate fonksiyonu veriyi eziyor, grafikler için ham veriye ihtiyacımız var
                all_daily_records = []
                for game_day in historical_data:
                    game_date = game_day.get('date')
                    players = game_day.get('players', [])
                    for player in players:
                        try:
                            # Ham veriyi kopyala
                            rec = player.copy()
                            rec['DATE'] = pd.to_datetime(game_date) if game_date else pd.Timestamp.now()
                            
                            # Numerik dönüşümler
                            numeric_stats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TO', 'FGM', 'FGA', '3Pts', 'FTM', 'FTA']
                            for stat in numeric_stats:
                                rec[stat] = float(player.get(stat, 0))
                            
                            rec['MIN'] = parse_minutes(player.get('MIN', 0))
                            # Takım ve İsim
                            if not rec.get('PLAYER'): continue
                                
                            all_daily_records.append(rec)
                        except Exception:
                            continue
                
                # Günlük verileri session'a kaydet (Grafikler/MVP widget'ı için)
                if all_daily_records:
                    daily_df = pd.DataFrame(all_daily_records)
                    daily_df["USER_SCORE"] = daily_df.apply(lambda x: calculate_fantasy_score(x, weights), axis=1)
                    st.session_state["period_df"] = daily_df
                else:
                    st.session_state["period_df"] = pd.DataFrame()

    # --- VERİ KONTROLÜ ---
    if active_df.empty:
        st.warning(f"No data available for {current_period}")
        return

    # --- TABLO FORMATLAMA AYARLARI ---
    
    # Veri tiplerini düzelt
    if "USER_SCORE" in active_df.columns:
        active_df["USER_SCORE"] = active_df["USER_SCORE"].astype(float).round(2)
    
    if "+/-" in active_df.columns:
         active_df["+/-"] = pd.to_numeric(active_df["+/-"], errors='coerce').fillna(0)

    # Bugün modu mu? (Integer vs Float gösterimi için)
    is_today = (current_period == "Today")
    stat_fmt = "%d" if is_today else "%.1f"
    
    # İstatistik sütunlarını yuvarla (Today ise int yap)
    stat_cols = ["PTS", "REB", "AST", "STL", "BLK", "TO", "+/-"]
    for col in stat_cols:
        if col in active_df.columns:
            if is_today:
                active_df[col] = active_df[col].fillna(0).astype(int)
            else:
                active_df[col] = active_df[col].astype(float).round(1)

    # Tablo Sütun Sırası
    column_order = ["PLAYER", "TEAM", "USER_SCORE", "MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "STL", "BLK", "TO", "+/-"]
    
    # Today hariç diğerlerinde "GAMES" (GP) gösterelim
    if not is_today:
        column_order.insert(2, "GAMES")
        if "GP" in active_df.columns: # Season verisinde GP gelir, aggregate'de GAMES
            active_df = active_df.rename(columns={"GP": "GAMES"})
        
    available_cols = [c for c in column_order if c in active_df.columns]

    # Streamlit Column Config
    col_config = {
        "PLAYER": st.column_config.TextColumn("Player", width="medium"),
        "TEAM": st.column_config.TextColumn("Team", width="small"),
        "GAMES": st.column_config.NumberColumn("GP", format="%d", width="small"),
        "USER_SCORE": st.column_config.NumberColumn("Score", format="%.2f", width="small"),
        "MIN": st.column_config.TextColumn("Min", width="small"), # String olduğu için TextColumn
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

    # =================================================================
    # TABLOLARIN ÇİZİLMESİ
    # =================================================================

    # --- 1. TOP 10 PERFORMANCES ---
    st.markdown(f"## 🔥 Top 10 Performances ({current_period})")
    
    # Score'a göre sırala
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
    
    # Seçim yapılırsa Modal aç
    if len(event_top.selection.rows) > 0:
        selected_index = event_top.selection.rows[0]
        selected_row = top_df.iloc[selected_index]
        show_player_analysis(selected_row, weights)

    # --- 2. LOWEST 10 PERFORMANCES ---
    st.markdown(f"## 📉 Lowest 10 Performances ({current_period})")
    
    # Filtre: Çok az oynayanları "En Kötü" listesine sokma
    # Season/Month için ortalama 15 dk, Today için 10 dk altı filtrelenir
    min_minutes = 15 if not is_today else 10
    
    if "MIN_INT" in active_df.columns:
        filtered_low = active_df[active_df["MIN_INT"] >= min_minutes]
        # Eğer filtre sonrası liste çok boşsa limiti düşür
        if len(filtered_low) < 5: 
            filtered_low = active_df[active_df["MIN_INT"] >= 5]
    else:
        filtered_low = active_df

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

    # --- 3. FULL LIST (EXPANDER) ---
    with st.expander(f"📋 Full Player List ({len(active_df)} players)"):
        full_sorted_df = active_df.sort_values("USER_SCORE", ascending=False).reset_index(drop=True)
        # Sıra numarası ekle
        full_sorted_df.insert(0, '#', full_sorted_df.index + 1)
        
        cols_with_rank = ['#'] + available_cols

        full_col_config = col_config.copy()
        full_col_config['#'] = st.column_config.NumberColumn("#", format="%d", width="40px")

        st.dataframe(
            full_sorted_df[cols_with_rank], 
            use_container_width=True, 
            hide_index=True, 
            column_config=full_col_config
        )
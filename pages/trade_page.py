import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Services klasörünü path'e ekle
current_dir = Path(__file__).parent.resolve()
project_root = current_dir.parent
services_dir = project_root / "services"

sys.path.insert(0, str(services_dir))
sys.path.insert(0, str(project_root))

# Selenium scraper ve trade analyzer'ı import et
from services.selenium_scraper import scrape_all_rosters
from services.trade_analyzer import TradeAnalyzer

st.set_page_config(page_title="Trade Analyzer", layout="wide")

st.title("🏀 NBA Fantasy Trade Analyzer")

# League ID
if 'league_id' not in st.session_state:
    st.session_state.league_id = None

# Sidebar: League ID Input
with st.sidebar:
    st.header("⚙️ Settings")
    
    league_id_input = st.text_input(
        "ESPN League ID",
        value=st.session_state.league_id or "",
        help="ESPN Fantasy Basketball League ID'nizi girin"
    )
    
    if st.button("Load League Data", type="primary"):
        if league_id_input:
            st.session_state.league_id = int(league_id_input)
            # Cache'i temizle
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Lütfen League ID girin!")
    
    st.divider()
    
    if st.session_state.league_id:
        st.success(f"✅ League ID: {st.session_state.league_id}")
        
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

# Ana sayfa
if not st.session_state.league_id:
    st.info("👈 Lütfen sol menüden League ID'nizi girin ve 'Load League Data' butonuna tıklayın.")
    
    st.markdown("""
    ### 📋 Nasıl Kullanılır?
    
    1. **ESPN Fantasy Basketball** ligine gidin
    2. URL'den **League ID**'yi kopyalayın
       - Örnek URL: `https://fantasy.espn.com/basketball/league?leagueId=1427083046`
       - League ID: `1427083046`
    3. Sol menüdeki alana yapıştırın
    4. "Load League Data" butonuna tıklayın
    
    ### ⚠️ Önemli Notlar
    - Lig **public (herkese açık)** olmalı
    - İlk yükleme 30-60 saniye sürebilir (Selenium ile scraping yapılıyor)
    - Veriler cache'lenir, sonraki yüklemeler hızlı olur
    """)
    
    st.stop()

# Veri yükleme
@st.cache_data(ttl=3600, show_spinner=False)
def load_roster_data(league_id):
    """Selenium ile tüm kadroları scrape et"""
    return scrape_all_rosters(league_id)

try:
    with st.spinner('🔄 Lig kadroları çekiliyor... (Bu 30-60 saniye sürebilir)'):
        roster_df = load_roster_data(st.session_state.league_id)
    
    if roster_df.empty:
        st.error("""
        ❌ Veri çekilemedi!
        
        **Olası Nedenler:**
        - League ID yanlış olabilir
        - Lig private (özel) olabilir - Public yapın
        - ESPN sayfası yapısı değişmiş olabilir
        """)
        st.stop()
    
    # Veri yüklendi mesajı
    st.success(f"✅ {len(roster_df)} oyuncu, {roster_df['team_name'].nunique()} takımdan yüklendi!")
    
    # Trade Analyzer oluştur
    analyzer = TradeAnalyzer(roster_df)
    
    # Takım listesi
    teams = roster_df[['team_id', 'team_name']].drop_duplicates().sort_values('team_name')
    team_map = dict(zip(teams['team_name'], teams['team_id']))
    
    st.divider()
    
    # İki sütun: Takımlar
    col1, col2 = st.columns(2)
    
    # SOL TARAF - SİZİN TAKIMINIZ
    with col1:
        st.subheader("🏠 Your Team")
        team_a_name = st.selectbox(
            "Select Your Team", 
            list(team_map.keys()), 
            key="team_a"
        )
        team_a_id = team_map[team_a_name]
        
        # Takım oyuncuları
        players_a = roster_df[roster_df['team_id'] == team_a_id].copy()
        
        # Oyuncu tablosu
        display_cols = ['player_name', 'PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'FG%', 'FT%']
        
        st.dataframe(
            players_a[display_cols].set_index('player_name').style.format({
                'PTS': '{:.1f}',
                'REB': '{:.1f}',
                'AST': '{:.1f}',
                'STL': '{:.1f}',
                'BLK': '{:.1f}',
                '3PM': '{:.1f}',
                'FG%': '{:.1f}',
                'FT%': '{:.1f}'
            }),
            height=300,
            use_container_width=True
        )
        
        # Takas edilecek oyuncular
        trade_out = st.multiselect(
            "Select Players to GIVE",
            players_a['player_name'].tolist(),
            key="players_out"
        )
        
        # ID'leri al (trade_analyzer için player_name kullanacağız)
    
    # SAĞ TARAF - KARŞI TAKIM
    with col2:
        st.subheader("🤝 Partner Team")
        
        # Kendi takımını hariç tut
        other_teams = [t for t in team_map.keys() if t != team_a_name]
        
        team_b_name = st.selectbox(
            "Select Partner Team",
            other_teams,
            key="team_b"
        )
        team_b_id = team_map[team_b_name]
        
        # Takım oyuncuları
        players_b = roster_df[roster_df['team_id'] == team_b_id].copy()
        
        st.dataframe(
            players_b[display_cols].set_index('player_name').style.format({
                'PTS': '{:.1f}',
                'REB': '{:.1f}',
                'AST': '{:.1f}',
                'STL': '{:.1f}',
                'BLK': '{:.1f}',
                '3PM': '{:.1f}',
                'FG%': '{:.1f}',
                'FT%': '{:.1f}'
            }),
            height=300,
            use_container_width=True
        )
        
        # Alınacak oyuncular
        trade_in = st.multiselect(
            "Select Players to RECEIVE",
            players_b['player_name'].tolist(),
            key="players_in"
        )
    
    st.divider()
    
    # ANALİZ BUTONU
    if st.button("🔍 Analyze Trade Impact", type="primary", use_container_width=True):
        if not trade_out and not trade_in:
            st.warning("⚠️ Lütfen en az bir taraftan oyuncu seçin!")
        else:
            with st.spinner("📊 Takas analiz ediliyor..."):
                # Player name'lerden ID'leri bul
                ids_out = players_a[players_a['player_name'].isin(trade_out)].index.tolist()
                ids_in = players_b[players_b['player_name'].isin(trade_in)].index.tolist()
                
                # Analiz yap
                result = analyzer.analyze_trade(team_a_id, ids_out, team_b_id, ids_in)
            
            st.success(f"### 📊 Trade Impact for **{team_a_name}**")
            
            # Kategori sonuçları
            categories = ['FG%', 'FT%', '3PM', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS']
            cols = st.columns(len(categories))
            
            for i, cat in enumerate(categories):
                data = result[cat]
                diff = data['diff']
                
                # TO için ters renklendirme
                if cat == 'TO':
                    if diff < 0:
                        color = "normal"  # Azalma = İyi
                    elif diff > 0:
                        color = "inverse"  # Artma = Kötü
                    else:
                        color = "off"
                else:
                    if data['impact'] == 'positive':
                        color = "normal"
                    elif data['impact'] == 'negative':
                        color = "inverse"
                    else:
                        color = "off"
                
                with cols[i]:
                    st.metric(
                        label=cat,
                        value=f"{data['new']:.2f}",
                        delta=f"{diff:+.2f}",
                        delta_color=color
                    )
            
            # Detaylı Özet
            st.divider()
            
            col_detail1, col_detail2 = st.columns(2)
            
            with col_detail1:
                st.markdown("#### 🔄 Players Going Out")
                if trade_out:
                    for player in trade_out:
                        p_stats = players_a[players_a['player_name'] == player].iloc[0]
                        st.write(f"**{player}**")
                        st.caption(f"📊 {p_stats['PTS']:.1f} PTS • {p_stats['REB']:.1f} REB • {p_stats['AST']:.1f} AST • {p_stats['STL']:.1f} STL • {p_stats['BLK']:.1f} BLK")
                else:
                    st.info("_No players selected_")
            
            with col_detail2:
                st.markdown("#### 📥 Players Coming In")
                if trade_in:
                    for player in trade_in:
                        p_stats = players_b[players_b['player_name'] == player].iloc[0]
                        st.write(f"**{player}**")
                        st.caption(f"📊 {p_stats['PTS']:.1f} PTS • {p_stats['REB']:.1f} REB • {p_stats['AST']:.1f} AST • {p_stats['STL']:.1f} STL • {p_stats['BLK']:.1f} BLK")
                else:
                    st.info("_No players selected_")
            
            # Net Impact Summary
            st.divider()
            st.markdown("### 📈 Overall Impact Summary")
            
            positive_count = sum(1 for v in result.values() if v['impact'] == 'positive')
            negative_count = sum(1 for v in result.values() if v['impact'] == 'negative')
            neutral_count = len(result) - positive_count - negative_count
            
            summary_cols = st.columns(3)
            
            with summary_cols[0]:
                st.metric("✅ Categories Improved", positive_count)
            
            with summary_cols[1]:
                st.metric("⚠️ Categories Worsened", negative_count)
            
            with summary_cols[2]:
                st.metric("➖ No Change", neutral_count)
            
            # Recommendation
            if positive_count > negative_count:
                st.success("💡 **Recommendation:** This trade looks favorable overall!")
            elif positive_count < negative_count:
                st.warning("💡 **Recommendation:** This trade may hurt your team. Consider alternatives.")
            else:
                st.info("💡 **Recommendation:** This is a balanced trade. Consider your team needs.")

except ImportError as e:
    st.error(f"❌ Import Hatası: {e}")
    st.info("""
    **Kontrol Edin:**
    - `services/selenium_scraper.py` dosyası var mı?
    - `services/trade_analyzer.py` dosyası var mı?
    - Gerekli kütüphaneler kurulu mu? (`selenium`, `beautifulsoup4`, `webdriver-manager`)
    """)
    
except Exception as e:
    st.error(f"❌ Beklenmeyen Hata: {e}")
    
    with st.expander("🔍 Detaylı Hata Mesajı"):
        import traceback
        st.code(traceback.format_exc())
import streamlit as st
import sys
import pandas as pd
from pathlib import Path

# --- SETUP ---
current_dir = Path(__file__).parent.resolve()
project_root = current_dir.parent
services_dir = project_root / "services"

if str(services_dir) not in sys.path:
    sys.path.insert(0, str(services_dir))

# Importlar
try:
    from services.selenium_scraper import scrape_all_rosters
    from services.trade_analyzer import TradeAnalyzer
except ImportError as e:
    st.error(f"Modül Hatası: {e}")
    st.stop()

# --- PAGE CONFIG ---
st.set_page_config(page_title="NBA Trade Analyzer", page_icon="🏀", layout="wide")

# --- SESSION STATE ---
if 'league_id' not in st.session_state:
    st.session_state.league_id = None
if 'roster_data' not in st.session_state:
    st.session_state.roster_data = None

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Ayarlar")
    league_id_input = st.text_input("ESPN League ID", value=str(st.session_state.league_id) if st.session_state.league_id else "")
    
    if st.button("Verileri Çek", type="primary"):
        if league_id_input:
            st.session_state.league_id = int(league_id_input)
            st.cache_data.clear()
            st.session_state.roster_data = None
            st.rerun()
        else:
            st.error("League ID girin!")

    st.info("Liginiz 'Public' (Herkese Açık) olmalıdır. Private liglerde çalışmaz.")

# --- FUNCTIONS ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_data(league_id):
    return scrape_all_rosters(league_id)

# --- MAIN ---
st.title("🏀 NBA Fantasy Trade Analyzer")

if not st.session_state.league_id:
    st.info("👈 Sol menüden League ID girerek başlayın.")
    st.stop()

if st.session_state.roster_data is None:
    with st.spinner('🔄 Veriler ESPN üzerinden çekiliyor... (30-45 sn)'):
        try:
            df = get_data(st.session_state.league_id)
            if not df.empty:
                st.session_state.roster_data = df
                st.rerun()
            else:
                st.error("❌ Veri çekilemedi! Lütfen Lig ID'yi kontrol edin ve Ligin Public olduğundan emin olun.")
                st.stop()
        except Exception as e:
            st.error(f"Hata: {e}")
            st.stop()

df = st.session_state.roster_data
expected_cols = [
    'team_id', 'team_name',
    'player_name', 'player_id',
    'FG%', 'FT%', '3PM', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS'
]

# Eğer kolon kaymışsa
if df['player_name'].dtype != object:
    df = df.copy()

    # player_name yanlışsa, index resetleyip tekrar eşle
    df.reset_index(drop=True, inplace=True)

    # Doğru kolonları zorla ata (AMA SIRAYI KORUYARAK)
    df = pd.DataFrame(df.values, columns=df.columns)

    # En kritik düzeltme
    df['player_name'] = df['player_name'].astype(str)

# SON KONTROL
assert 'player_name' in df.columns

# Analyzer'ı Başlat
analyzer = TradeAnalyzer(df)
st.success(f"✅ Hazır! {len(df)} oyuncu yüklendi.")

# --- UI ---
col1, col2 = st.columns(2)
team_names = sorted(df['team_name'].unique())
team_map = df[['team_name', 'team_id']].drop_duplicates().set_index('team_name')['team_id'].to_dict()

# LEFT: TEAM A
with col1:
    st.subheader("🏠 Takım A (Siz)")
    team_a = st.selectbox("Takım Seçin", team_names, key="t1")
    team_a_id = team_map[team_a]
    
    players_a = df[df['team_name'] == team_a]
    st.dataframe(players_a[['player_name', 'PTS', 'REB', 'AST']].set_index('player_name'), use_container_width=True)
    
    trade_out = st.multiselect("Verilecekler", players_a['player_name'].tolist())

# RIGHT: TEAM B
with col2:
    st.subheader("🤝 Takım B (Partner)")
    other_teams = [t for t in team_names if t != team_a]
    team_b = st.selectbox("Partner Seçin", other_teams, key="t2")
    team_b_id = team_map[team_b]
    
    players_b = df[df['team_name'] == team_b]
    st.dataframe(players_b[['player_name', 'PTS', 'REB', 'AST']].set_index('player_name'), use_container_width=True)
    
    trade_in = st.multiselect("Alınacaklar", players_b['player_name'].tolist())

st.divider()

if st.button("🔍 Analiz Et", type="primary", use_container_width=True):
    if not trade_out and not trade_in:
        st.warning("Oyuncu seçimi yapın.")
    else:
        # İSİM YERİNE PLAYER_ID KULLANIYORUZ (DÜZELTİLDİ)
        ids_out = df[(df['team_name'] == team_a) & (df['player_name'].isin(trade_out))]['player_id'].tolist()
        ids_in = df[(df['team_name'] == team_b) & (df['player_name'].isin(trade_in))]['player_id'].tolist()
        
        try:
            result = analyzer.analyze_trade(team_a_id, ids_out, team_b_id, ids_in)
            
            # Sonuçları Yazdır
            cols = st.columns(9)
            cats = ['FG%', 'FT%', '3PM', 'REB', 'AST', 'STL', 'BLK', 'TO', 'PTS']
            
            for i, cat in enumerate(cats):
                if cat in result:
                    val = result[cat]
                    delta_color = "inverse" if cat == 'TO' else "normal"
                    with cols[i]:
                        st.metric(cat, f"{val['new']:.1f}", f"{val['diff']:+.2f}", delta_color=delta_color)
                        
        except Exception as e:
            st.error(f"Analiz Hatası: {e}")
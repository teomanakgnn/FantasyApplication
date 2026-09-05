"""
Fantasy NBA draft verisi.

ESPN'in fantasy oyuncu havuzundan draft sıralaması (ADP benzeri),
auction değeri, pozisyon uygunluğu ve sahiplenme oranını çeker;
geçen sezonun gerçek istatistikleriyle birleştirir.
"""

import json
import os
import tempfile
import time

import pandas as pd
import streamlit as st

from services.espn_api import get_nba_season_stats_official
from services.nba_season import (
    get_current_season_year,
    get_season_label,
    get_session,
)

FANTASY_BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons"

# ESPN fantasy pozisyon kodları
POSITION_NAMES = {1: "PG", 2: "SG", 3: "SF", 4: "PF", 5: "C"}

# Kadro slotları -> pozisyon (eligibleSlots eşlemesi)
SLOT_TO_POSITION = {0: "PG", 1: "SG", 2: "SF", 3: "PF", 4: "C"}

# Bir draft edilen oyuncunun doldurabileceği kadro yerleri
ROSTER_SLOTS = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL", "UTIL", "BENCH", "BENCH", "BENCH", "BENCH"]

# Fantasy puanı: standart 9-kategori yaklaşımına yakın ağırlıklar
DEFAULT_FANTASY_WEIGHTS = {
    "PTS": 1.0, "REB": 1.2, "AST": 1.5, "STL": 3.0, "BLK": 3.0,
    "3Pts": 1.0, "TO": -1.5, "FGM": 1.0, "FGA": -0.5, "FTM": 1.0, "FTA": -0.5,
}


@st.cache_data(ttl=86400, show_spinner=False)
def get_pro_team_map(season_year=None):
    """ESPN fantasy proTeamId -> takım kısaltması haritası."""
    season = season_year or get_current_season_year()
    url = f"{FANTASY_BASE}/{season}?view=proTeamSchedules_wl"
    try:
        resp = get_session().get(url, headers={"Accept": "application/json"}, timeout=25)
        resp.raise_for_status()
        teams = (resp.json().get("settings") or {}).get("proTeams") or []
        return {int(t["id"]): t.get("abbrev", "FA") for t in teams if t.get("id") is not None}
    except Exception as exc:
        print(f"⚠️ proTeam haritası alınamadı: {exc}")
        return {0: "FA"}


def _eligible_positions(player):
    """eligibleSlots'tan oyuncunun oynayabileceği gerçek pozisyonları çıkarır."""
    slots = player.get("eligibleSlots") or []
    positions = [SLOT_TO_POSITION[s] for s in slots if s in SLOT_TO_POSITION]
    if not positions:
        primary = POSITION_NAMES.get(player.get("defaultPositionId"))
        positions = [primary] if primary else ["UTIL"]
    # Sabit sırada tut (PG, SG, SF, PF, C)
    order = ["PG", "SG", "SF", "PF", "C"]
    return sorted(set(positions), key=lambda p: order.index(p) if p in order else 99)


RANK_COLUMNS = ["PLAYER", "ESPN_ID", "TEAM", "POS", "POSITIONS",
                "RANK", "AUCTION", "OWNED", "INJURY"]

# Draft siralamasi gunde bir kez bile degismiyor ama ESPN'in bu ucu
# yogun zamanlarda baglantiyi resetliyor (olculdu: soguk istekte
# ConnectionError, ardindan calisiyor). Basarili bir cekimi diske yazip
# ESPN ulasilamadiginda oradan servis ediyoruz - boylece sayfa hic
# bos kalmiyor.
_RANK_CACHE_DIR = os.path.join(tempfile.gettempdir(), "hooplife_draft_cache")
_RANK_CACHE_MAX_AGE = 7 * 24 * 3600  # bayat da olsa hicbir seyden iyidir


def _rank_cache_path(season):
    return os.path.join(_RANK_CACHE_DIR, f"draft_ranks_{season}.json")


def _save_rank_cache(season, rows):
    try:
        os.makedirs(_RANK_CACHE_DIR, exist_ok=True)
        with open(_rank_cache_path(season), "w", encoding="utf-8") as fh:
            json.dump({"saved_at": time.time(), "rows": rows}, fh)
    except Exception as exc:
        print(f"⚠️ Draft sıralaması diske yazılamadı: {exc}")


def _load_rank_cache(season):
    try:
        path = _rank_cache_path(season)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as fh:
            blob = json.load(fh)
        age = time.time() - float(blob.get("saved_at") or 0)
        if age > _RANK_CACHE_MAX_AGE:
            return None
        print(f"↩️ Draft sıralaması disk önbelleğinden okundu ({age/3600:.1f} saat önce).")
        return blob.get("rows") or None
    except Exception:
        return None


def _fetch_rank_payload(season, attempts=3):
    """
    Draft siralamasini ceker.

    Once leaguedefaults ucu denenir: filtredeki 'limit' degerine uyuyor,
    3179 yerine 500 oyuncu donduruyor (24MB -> 16MB). Olmazsa genel
    players ucuna dusulur. Baglanti hatalarinda VE sirali oyuncu
    icermeyen kisik yanitlarda artan bekleme ile tekrar denenir.

    Returns:
        list[dict] - islenmis satirlar, basarisizsa None.
    """
    fantasy_filter = {
        "players": {
            "limit": 500,
            "sortDraftRanks": {"sortPriority": 100, "sortAsc": True, "value": "STANDARD"},
        }
    }
    headers = {"Accept": "application/json",
               "x-fantasy-filter": json.dumps(fantasy_filter)}

    urls = [
        f"{FANTASY_BASE}/{season}/segments/0/leaguedefaults/3?view=kona_player_info",
        f"{FANTASY_BASE}/{season}/players?scoringPeriodId=0&view=kona_player_info",
    ]

    team_map = get_pro_team_map(season)
    last_problem = None

    for attempt in range(attempts):
        for url in urls:
            try:
                resp = get_session().get(url, headers=headers, timeout=45)
                resp.raise_for_status()
                payload = resp.json()
                players = payload.get("players") if isinstance(payload, dict) else payload
                rows = _rows_from_players(players, team_map)
                # Sadece "yanit geldi" yetmiyor: ESPN bazen sirali oyuncu
                # icermeyen kisik bir yanit donuyor. Dogrulamayi burada
                # yapip boyle bir yaniti da yeniden deneme sebebi sayiyoruz.
                if len(rows) >= 50:
                    return rows
                last_problem = f"sıralı oyuncu yok/eksik ({len(rows)})"
            except Exception as exc:
                last_problem = f"{exc.__class__.__name__}"
        if attempt < attempts - 1:
            wait = 1.5 * (attempt + 1)
            print(f"⚠️ Draft sıralaması alınamadı ({last_problem}), "
                  f"{wait:.1f}s sonra tekrar denenecek")
            time.sleep(wait)

    print(f"❌ Draft sıralaması çekilemedi: {last_problem}")
    return None


def _rows_from_players(players, team_map):
    rows = []
    for player in players or []:
        ranks = (player.get("draftRanksByRankType") or {}).get("STANDARD")
        if not ranks or ranks.get("rank") is None:
            continue
        positions = _eligible_positions(player)
        rows.append({
            "PLAYER": player.get("fullName") or "Unknown",
            "ESPN_ID": player.get("id"),
            "TEAM": team_map.get(player.get("proTeamId"), "FA"),
            "POS": positions[0],
            "POSITIONS": positions,
            "RANK": int(ranks["rank"]),
            "AUCTION": int(ranks.get("auctionValue") or 0),
            "OWNED": round(float((player.get("ownership") or {}).get("percentOwned") or 0), 1),
            "INJURY": player.get("injuryStatus") or "ACTIVE",
        })
    return rows


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_draft_rankings(season_year=None):
    """
    ESPN fantasy havuzundan draft sıralamalı oyuncuları çeker.

    ESPN ulaşılamazsa diskteki son başarılı çekime düşer; o da yoksa
    boş DataFrame döner (çağıran taraf "tekrar dene" gösterir).
    """
    season = season_year or get_current_season_year()

    rows = _fetch_rank_payload(season)
    if rows:
        _save_rank_cache(season, rows)
    else:
        rows = _load_rank_cache(season)

    if not rows:
        return pd.DataFrame(columns=RANK_COLUMNS)

    df = pd.DataFrame(rows).sort_values(["RANK", "AUCTION"], ascending=[True, False])
    # ESPN aynı rank'i birden çok oyuncuya verebiliyor; sıralamayı benzersizleştir.
    df = df.reset_index(drop=True)
    df["ADP"] = df.index + 1

    print(f"✓ {get_season_label(season)} draft havuzu: {len(df)} sıralı oyuncu")
    return df


def calculate_fantasy_points(row, weights=None):
    """Bir oyuncunun maç başına fantasy puanını hesaplar."""
    w = weights or DEFAULT_FANTASY_WEIGHTS
    total = 0.0
    for stat, weight in w.items():
        try:
            total += float(row.get(stat, 0) or 0) * weight
        except (TypeError, ValueError):
            continue
    return round(total, 1)


def _normalize(name):
    if not name:
        return ""
    return name.replace(".", "").replace("'", "").replace("-", " ").lower().strip()


@st.cache_data(ttl=21600, show_spinner=False)
def get_draft_board(weights=None):
    """
    Draft sıralamasını geçen sezonun gerçek istatistikleriyle birleştirir.

    Returns:
        DataFrame - draft sırasına göre, istatistik sütunları eklenmiş.
        İstatistiği olmayan oyuncular (çaylaklar) da listede kalır.
    """
    board = fetch_draft_rankings()
    if board.empty:
        return board

    stats = get_nba_season_stats_official()
    stat_columns = ["GP", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TO",
                    "FGM", "FGA", "FTM", "FTA", "3Pts", "3PTA", "FG%", "FT%", "3P%"]

    if stats.empty:
        for col in stat_columns + ["FPTS"]:
            board[col] = 0.0
        board["ROOKIE"] = True
        return board

    stats = stats.copy()
    stats["_key"] = stats["PLAYER"].map(_normalize)
    # Aynı isim birden çok kez gelirse en çok maç oynayanı tut.
    stats = stats.sort_values("GP", ascending=False).drop_duplicates("_key", keep="first")

    lookup = stats.set_index("_key")[[c for c in stat_columns if c in stats.columns]]

    board = board.copy()
    board["_key"] = board["PLAYER"].map(_normalize)
    merged = board.merge(lookup, how="left", left_on="_key", right_index=True)

    # İstatistiği olmayanlar çaylak veya geçen sezon oynamamış oyuncular.
    merged["ROOKIE"] = merged["GP"].isna() if "GP" in merged.columns else True
    for col in stat_columns:
        if col not in merged.columns:
            merged[col] = 0.0
    merged[stat_columns] = merged[stat_columns].fillna(0.0)

    merged["FPTS"] = merged.apply(lambda r: calculate_fantasy_points(r, weights), axis=1)

    return merged.drop(columns=["_key"]).reset_index(drop=True)


def get_headshot_url(espn_id):
    """ESPN oyuncu fotoğrafı; ID yoksa yer tutucu."""
    if not espn_id:
        return "https://a.espncdn.com/combiner/i?img=/i/headshots/nophoto.png&w=200&h=145"
    return (f"https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/"
            f"{espn_id}.png&w=200&h=145")

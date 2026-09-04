"""
Fantasy NBA draft verisi.

ESPN'in fantasy oyuncu havuzundan draft sıralaması (ADP benzeri),
auction değeri, pozisyon uygunluğu ve sahiplenme oranını çeker;
geçen sezonun gerçek istatistikleriyle birleştirir.
"""

import json

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


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_draft_rankings(season_year=None):
    """
    ESPN fantasy havuzundan draft sıralamalı oyuncuları çeker.

    Returns:
        DataFrame - PLAYER, ESPN_ID, TEAM, POS, POSITIONS, RANK,
                    AUCTION, OWNED, INJURY
        Sıralama draft rank'e göre artan.
    """
    season = season_year or get_current_season_year()

    # Filtre başlığı ESPN tarafında yok sayılıyor ama sıralamayı etkiliyor;
    # yanıtın tamamı alınıp rank'i olan oyuncular yerel olarak süzülür.
    fantasy_filter = {
        "players": {
            "limit": 1500,
            "sortDraftRanks": {"sortPriority": 100, "sortAsc": True, "value": "STANDARD"},
        }
    }
    headers = {"Accept": "application/json", "x-fantasy-filter": json.dumps(fantasy_filter)}
    url = f"{FANTASY_BASE}/{season}/players?scoringPeriodId=0&view=kona_player_info"

    try:
        resp = get_session().get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        print(f"⚠️ Draft sıralaması alınamadı ({season}): {exc}")
        return pd.DataFrame(columns=[
            "PLAYER", "ESPN_ID", "TEAM", "POS", "POSITIONS",
            "RANK", "AUCTION", "OWNED", "INJURY",
        ])

    players = payload.get("players") if isinstance(payload, dict) else payload
    team_map = get_pro_team_map(season)

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

    if not rows:
        print(f"⚠️ {season} sezonunda draft sıralaması bulunamadı.")
        return pd.DataFrame(columns=[
            "PLAYER", "ESPN_ID", "TEAM", "POS", "POSITIONS",
            "RANK", "AUCTION", "OWNED", "INJURY",
        ])

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

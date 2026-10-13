"""
Tier List ve Stat Match icin oyuncu verisi.

Ikisi de draft siralamasindan besleniyor: ESPN kimligi (fotograf), takim,
mevki ve gecen sezonun mac basi ortalamalari ayni tabloda.

Stat Match: iki oyuncu, iki istatistik satiri; hangi satirin kime ait
oldugu bulunur. Ciftler bilerek zor seciliyor: ayni mevki grubu ve
birbirine yakin sayi ortalamasi. Gunluk tur herkes icin ayni (Londra
gunune gore tohumlu); pratik turu her seferinde yeni.
"""
import random
from datetime import date

from services.cache import cache_data
from services.daily_player import today

STAT_KEYS = [("PTS", "PTS", 1), ("REB", "REB", 1), ("AST", "AST", 1), ("STL", "STL", 1),
             ("BLK", "BLK", 1), ("3Pts", "3PM", 1), ("FG%", "FG%", 1), ("FT%", "FT%", 1)]
ROUNDS = 10
LAUNCH = date(2026, 10, 13)


def _group(positions):
    pos = set(positions or [])
    if "C" in pos:
        return "C"
    if pos & {"PG", "SG"} and not pos & {"PF"}:
        return "G"
    return "F"


@cache_data(ttl=6 * 3600, show_spinner=False, copy_result=False)
def board_players(limit=220):
    """Draft siralamasindaki oyuncular (ADP sirasiyla), gecen sezon ortalamalariyla."""
    from services.draft_data import get_draft_board
    board = get_draft_board()
    if board is None or board.empty:
        return []
    out = []
    for _, r in board.sort_values("ADP").head(limit).iterrows():
        try:
            pid = str(int(r["ESPN_ID"]))
        except (TypeError, ValueError):
            continue
        positions = list(r["POSITIONS"]) if isinstance(r["POSITIONS"], (list, tuple)) else [r["POS"]]
        stats = {}
        for key, label, digits in STAT_KEYS:
            try:
                stats[label] = round(float(r.get(key) or 0), digits)
            except (TypeError, ValueError):
                stats[label] = 0.0
        out.append({"id": pid, "name": r["PLAYER"], "team": r["TEAM"], "pos": "/".join(positions),
                    "group": _group(positions), "gp": int(r.get("GP") or 0),
                    "adp": round(float(r["ADP"]), 1) if r["ADP"] < 999 else None, "stats": stats})
    return out


def tier_players(limit=200):
    return [{k: p[k] for k in ("id", "name", "team", "pos", "adp")} for p in board_players(limit)]


def stat_match_number(day=None):
    return ((day or today()) - LAUNCH).days + 1


def stat_match_rounds(seed, rounds=ROUNDS):
    """
    Zor ciftler: ayni mevki grubu, sayi ortalamasi en fazla 5 farkli,
    gecen sezon en az 25 mac. Her oyuncu bir turda bir kez.
    """
    pool = [p for p in board_players(180) if p["gp"] >= 25]
    rng = random.Random(seed)
    rng.shuffle(pool)
    used, out = set(), []
    for a in pool:
        if len(out) >= rounds:
            break
        if a["id"] in used:
            continue
        mates = [b for b in pool if b["id"] not in used and b["id"] != a["id"]
                 and b["group"] == a["group"] and abs(b["stats"]["PTS"] - a["stats"]["PTS"]) <= 5]
        if not mates:
            continue
        b = rng.choice(mates)
        used.update({a["id"], b["id"]})
        left, right = (a, b) if rng.random() < .5 else (b, a)
        # Satirlarin sirasi da rastgele: ust satir sol oyuncunun mu?
        top_is_left = rng.random() < .5
        out.append({
            "players": [_card(left), _card(right)],
            "lines": [left["stats"], right["stats"]] if top_is_left else [right["stats"], left["stats"]],
            "answer": 0 if top_is_left else 1,      # ust satir hangi oyuncunun (0 = sol)
        })
    return out


def _card(p):
    return {"id": p["id"], "name": p["name"], "team": p["team"], "pos": p["pos"]}

"""
Pyramid: gunluk oyun. Bir kategori (gecen sezonun toplam top calmasi gibi) ve
10 oyuncu; oyuncu piramidi en coktan en aza dizer (tepe 1, sonra 2, 3, 4
hucre; en alt satirin en sagi en az). Herkes ayni gun ayni bulmacayi gorur;
cevap sunucuda, kontrol /api/pyramid/check ile.

Oyuncular taninan isimlerden (gecen sezon en cok dakika x mac oynayanlar),
degerleri birbirine cok yakin olmayacak sekilde secilir (esitlik yok).
"""
import random
from datetime import date

from services.cache import cache_data
from services.daily_player import today

LAUNCH = date(2026, 10, 24)
SEASON_LABEL = "2025-26"
N = 10

# anahtar, baslik, deger(satir), birim, en kucuk fark
CATEGORIES = [
    ("pts", "Total points", lambda r: r["PTS"] * r["GP"], "points", 30),
    ("reb", "Total rebounds", lambda r: r["REB"] * r["GP"], "rebounds", 15),
    ("ast", "Total assists", lambda r: r["AST"] * r["GP"], "assists", 12),
    ("stl", "Total steals", lambda r: r["STL"] * r["GP"], "steals", 4),
    ("blk", "Total blocks", lambda r: r["BLK"] * r["GP"], "blocks", 4),
    ("tpm", "3-pointers made", lambda r: r["3Pts"] * r["GP"], "threes", 6),
    ("ppg", "Points per game", lambda r: r["PTS"], "ppg", 0.6),
    ("rpg", "Rebounds per game", lambda r: r["REB"], "rpg", 0.3),
    ("apg", "Assists per game", lambda r: r["AST"], "apg", 0.3),
    ("mpg", "Minutes per game", lambda r: r["MIN"], "mpg", 0.5),
    ("tov", "Total turnovers", lambda r: r["TO"] * r["GP"], "turnovers", 8),
    ("gp", "Games played", lambda r: r["GP"], "games", 1),
]


def puzzle_number(day=None):
    return ((day or today()) - LAUNCH).days + 1


@cache_data(ttl=6 * 3600, show_spinner=False, copy_result=False)
def _pool():
    """Taninan oyuncular: gecen sezon toplam dakikasi en yuksek 140 oyuncu."""
    from services.espn_api import get_nba_season_stats_official
    from services.nba_season import get_current_season_year
    df = get_nba_season_stats_official(get_current_season_year() - 1)
    if df is None or df.empty:
        return []
    rows = []
    for _, r in df.iterrows():
        try:
            rec = {k: float(r[k] or 0) for k in ("GP", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TO", "3Pts")}
        except (TypeError, ValueError):
            continue
        if rec["GP"] < 25 or not r.get("PLAYER_ID"):
            continue
        rec.update({"id": str(r["PLAYER_ID"]), "name": r["PLAYER"], "team": r["TEAM"]})
        rows.append(rec)
    rows.sort(key=lambda r: -(r["MIN"] * r["GP"]))
    return rows[:140]


def build(seed):
    """Bulmaca: kategori ve 10 oyuncu (karisik), cevap sirasi (en coktan en aza)."""
    pool = _pool()
    if len(pool) < N:
        return None
    rng = random.Random(seed)
    cats = list(CATEGORIES)
    rng.shuffle(cats)
    for key, label, fn, unit, gap in cats:
        for _ in range(300):
            pick = rng.sample(pool, N)
            vals = sorted((fn(p) for p in pick), reverse=True)
            if all(a - b >= gap for a, b in zip(vals, vals[1:])):
                ranked = sorted(pick, key=lambda p: -fn(p))
                players = [{"id": p["id"], "name": p["name"], "team": p["team"]} for p in pick]
                rng.shuffle(players)
                answer = [{"id": p["id"], "name": p["name"], "team": p["team"], "value": _fmt(fn(p), key)} for p in ranked]
                return {"category": key, "label": label, "unit": unit, "season": SEASON_LABEL,
                        "players": players, "answer": answer}
    return None


def _fmt(v, key):
    return round(v, 1) if key in ("ppg", "rpg", "apg", "mpg") else int(round(v))


def daily(day=None):
    day = day or today()
    return build(f"pyramid-{day.isoformat()}")


def public(puzzle):
    """Tarayiciya giden kisim: cevap yok."""
    return {k: puzzle[k] for k in ("category", "label", "unit", "season", "players")}


def check(puzzle, order):
    """order: oyuncu kimlikleri, tepeden asagi. Her hucre: dogru / bir sira yakin / uzak."""
    truth = [a["id"] for a in puzzle["answer"]]
    marks = []
    for i, pid in enumerate(order[:N]):
        true_rank = truth.index(pid) if pid in truth else 99
        marks.append("hit" if true_rank == i else "near" if abs(true_rank - i) == 1 else "miss")
    return {"marks": marks, "score": marks.count("hit"), "answer": puzzle["answer"]}

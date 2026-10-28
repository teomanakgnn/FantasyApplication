"""
3x3 Grid: solda 3, ustte 3 kategori (takim, odul, istatistik). Her hucreye iki
kategoriyi birden saglayan bir oyuncu yazilir. Veri: services/grid.json
(scripts/build_grid.py; 1985-86'dan bu yana NBA'de oynamis herkes).

Modlar: gunluk grid (herkese ayni, 9 tahmin hakki), bota karsi XOX ve
arkadasa karsi canli XOX (web/routes/grid.py). Cevaplar hep sunucuda kontrol edilir.
"""
import json
import os
import random
import re
from datetime import date
from functools import lru_cache

from services.daily_player import today

LAUNCH = date(2026, 10, 28)
GUESSES = 9
MIN_ANSWERS = 3            # her hucrede en az bu kadar dogru cevap olmali
DATA_FILE = os.path.join(os.path.dirname(__file__), "grid.json")


@lru_cache(maxsize=1)
def data():
    with open(DATA_FILE, encoding="utf-8") as fh:
        d = json.load(fh)
    for pid, p in d["players"].items():
        p["id"] = pid
        p["t"] = set(p["t"])
        # Taninirlik: bot ve "en bilinen cevaplar" icin
        p["fame"] = 4 * p["as"] + 2 * p["ring"] + p["c"].get("gp", 0) / 120 + p["yrs"] / 3 + 3 * sum(p["aw"].values())
    return d


def _c(p, k):
    return p["c"].get(k, 0)


def _career(k, v):
    return lambda p: _c(p, "gp") >= 200 and _c(p, k) >= v


# anahtar, etiket, kosul
OTHER = [
    ("champ", "NBA Champion", lambda p: p["ring"] >= 1),
    ("as1", "All-Star", lambda p: p["as"] >= 1),
    ("as2", "2+ time All-Star", lambda p: p["as"] >= 2),
    ("as5", "5+ time All-Star", lambda p: p["as"] >= 5),
    ("mvp", "MVP", lambda p: p["aw"].get("mvp", 0) >= 1),
    ("fmvp", "Finals MVP", lambda p: p["aw"].get("fmvp", 0) >= 1),
    ("dpoy", "Defensive Player of the Year", lambda p: p["aw"].get("dpoy", 0) >= 1),
    ("roy", "Rookie of the Year", lambda p: p["aw"].get("roy", 0) >= 1),
    ("smoy", "Sixth Man of the Year", lambda p: p["aw"].get("smoy", 0) >= 1),
    ("mip", "Most Improved Player", lambda p: p["aw"].get("mip", 0) >= 1),
    ("allnba", "All-NBA Team", lambda p: p["aw"].get("allnba", 0) >= 1),
    ("alldef", "All-Defensive Team", lambda p: p["aw"].get("alldef", 0) >= 1),
    ("c20", "20+ PPG career", _career("pts", 20)),
    ("c25", "25+ PPG career", _career("pts", 25)),
    ("c8r", "8+ RPG career", _career("reb", 8)),
    ("c6a", "6+ APG career", _career("ast", 6)),
    ("s25", "25+ PPG season", lambda p: p["best"]["pts"] >= 25),
    ("s12r", "12+ RPG season", lambda p: p["best"]["reb"] >= 12),
    ("s10a", "10+ APG season", lambda p: p["best"]["ast"] >= 10),
    ("s2b", "2.5+ BPG season", lambda p: p["best"]["blk"] >= 2.5),
    ("s2s", "2+ SPG season", lambda p: p["best"]["stl"] >= 2),
    ("y15", "15+ NBA seasons", lambda p: p["yrs"] >= 15),
    ("g1000", "1,000+ games", lambda p: _c(p, "gp") >= 1000),
]
# Ayni grid'de birlikte anlamsiz olanlar (biri digerini kapsar)
OVERLAP = [{"as1", "as2", "as5"}, {"c20", "c25", "s25"}, {"mvp", "allnba"}, {"y15", "g1000"}, {"fmvp", "champ"}]


@lru_cache(maxsize=1)
def categories():
    d = data()
    out = {}
    for tid, t in d["teams"].items():
        out["t" + tid] = {"key": "t" + tid, "label": t["name"], "short": t["abbr"], "kind": "team", "logo": t["abbr"].lower(),
                          "test": (lambda tid: lambda p: tid in p["t"])(tid)}
    for key, label, fn in OTHER:
        out[key] = {"key": key, "label": label, "short": label, "kind": "stat", "test": fn}
    return out


def answers(a, b):
    """a ve b kategorilerini birlikte saglayan oyuncular (taninirliga gore)."""
    cats = categories()
    fa, fb = cats[a]["test"], cats[b]["test"]
    return sorted((p for p in data()["players"].values() if fa(p) and fb(p)), key=lambda p: -p["fame"])


def _clash(a, b):
    return a == b or any(a in g and b in g for g in OVERLAP)


def build(seed, min_answers=MIN_ANSWERS):
    """Satir ve sutun kategorileri; her hucrede en az min_answers cevap. Tohumla ayni grid."""
    rng = random.Random(str(seed))
    cats = categories()
    team_keys = [k for k, c in cats.items() if c["kind"] == "team"]
    other_keys = [k for k, c in cats.items() if c["kind"] == "stat"]
    for _ in range(4000):
        # Takim ve odul/istatistik karisik: 2-4 odul/istatistik, her eksende en az bir takim
        n_other = rng.choice([2, 3, 3, 4])
        keys = rng.sample(team_keys, 6 - n_other) + rng.sample(other_keys, n_other)
        rng.shuffle(keys)
        rows, cols = keys[:3], keys[3:]
        if all(cats[k]["kind"] == "stat" for k in rows) or all(cats[k]["kind"] == "stat" for k in cols):
            continue
        if any(_clash(a, b) for a in keys for b in keys if a != b):
            continue
        counts = [[len(answers(r, c)) for c in cols] for r in rows]
        if min(min(x) for x in counts) < min_answers:
            continue
        return {"seed": str(seed), "rows": rows, "cols": cols, "counts": counts}
    return None


def label(key):
    c = categories()[key]
    return {"key": key, "label": c["label"], "short": c["short"], "kind": c["kind"], "logo": c.get("logo")}


def public(g):
    return {"seed": g["seed"], "rows": [label(k) for k in g["rows"]], "cols": [label(k) for k in g["cols"]],
            "counts": g["counts"]}


def puzzle_number(day=None):
    return ((day or today()) - LAUNCH).days + 1


@lru_cache(maxsize=8)
def daily(day=None):
    day = day or today()
    return build(f"grid-{day.isoformat()}", min_answers=4)


def by_seed(seed):
    if seed == "daily":
        return daily()
    if re.fullmatch(r"[a-z0-9-]{4,40}", str(seed or "")):
        return _cached(seed)
    return None


@lru_cache(maxsize=512)
def _cached(seed):
    return build(seed)


def player_card(p):
    return {"id": p["id"], "name": p["n"], "years": f"{p['y0'] - 1}-{str(p['y1'])[-2:]}"}


def check(g, cell, pid):
    """cell = 0..8 (satir*3 + sutun). Dogru mu ve oyuncu karti."""
    if not g or not isinstance(cell, int) or not 0 <= cell <= 8:
        return {"error": "Unknown cell."}
    p = data()["players"].get(str(pid))
    if not p:
        return {"error": "Unknown player."}
    r, c = g["rows"][cell // 3], g["cols"][cell % 3]
    cats = categories()
    ok = cats[r]["test"](p) and cats[c]["test"](p)
    return {"ok": bool(ok), "player": player_card(p), "cell": cell}


def reveal(g, n=5):
    """Her hucrenin en bilinen cevaplari ve toplam cevap sayisi."""
    out = []
    for r in g["rows"]:
        for c in g["cols"]:
            a = answers(r, c)
            out.append({"count": len(a), "top": [player_card(p) for p in a[:n]]})
    return out


@lru_cache(maxsize=1)
def player_list():
    """Otomatik tamamlama listesi: herkes, taninirliga gore."""
    ps = sorted(data()["players"].values(), key=lambda p: -p["fame"])
    return [player_card(p) for p in ps]


# ==================== XOX ====================

LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
MAX_TURNS = 24             # kimse kazanamazsa: daha cok hucre alan kazanir
BOT_LEVELS = {"easy": 0.55, "medium": 0.72, "hard": 0.88}


def winner(board):
    """board: 9 elemanli liste ("X", "O" ya da None). Kazanan, "draw" ya da None."""
    for a, b, c in LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    if all(board):
        return "draw"
    return None


def final_result(board, turns):
    w = winner(board)
    if w:
        return w
    if turns >= MAX_TURNS:
        x, o = board.count("X"), board.count("O")
        return "X" if x > o else "O" if o > x else "draw"
    return None


def _bot_cell(board, me, rng, level):
    """Kazanabilecegi hucre, rakibi durduracak hucre, merkez, koseler; kolayda biraz rastgele."""
    them = "X" if me == "O" else "O"
    free = [i for i in range(9) if not board[i]]
    if not free:
        return None
    if rng.random() < {"easy": 0.45, "medium": 0.2, "hard": 0.05}[level]:
        return rng.choice(free)
    for who in (me, them):
        for line in LINES:
            vals = [board[i] for i in line]
            if vals.count(who) == 2 and vals.count(None) == 1:
                return line[vals.index(None)]
    if 4 in free:
        return 4
    corners = [i for i in (0, 2, 6, 8) if i in free]
    return rng.choice(corners or free)


def bot_move(g, board, used, me="O", level="medium", seed=None):
    """Botun hamlesi: hucre ve oyuncu. Kacirirsa (seviyeye gore) yanlis oyuncu soyler."""
    level = level if level in BOT_LEVELS else "medium"
    rng = random.Random(seed)
    cell = _bot_cell(board, me, rng, level)
    if cell is None:
        return None
    used = {str(x) for x in used or []}
    r, c = g["rows"][cell // 3], g["cols"][cell % 3]
    pool = [p for p in answers(r, c) if p["id"] not in used]
    # Bilinen oyuncular daha olasi; zor bot nadir cevaplari da bilir
    depth = {"easy": 6, "medium": 15, "hard": 60}[level]
    if pool and rng.random() < BOT_LEVELS[level]:
        p = rng.choice(pool[:depth])
        return {"cell": cell, "ok": True, "player": player_card(p)}
    # Yanlis tahmin: satirdaki ya da sutundaki kategoriden biri tutan ama digeri tutmayan bilinen oyuncu
    cats = categories()
    near = [p for p in data()["players"].values()
            if (cats[r]["test"](p) != cats[c]["test"](p)) and p["id"] not in used and p["fame"] > 20]
    p = rng.choice(near) if near else None
    return {"cell": cell, "ok": False, "player": player_card(p) if p else None}

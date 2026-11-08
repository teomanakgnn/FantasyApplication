"""
NBA Auction: iki oyuncu, 20'ser dolar, bes kisilik kadro. Havuzdan oyuncular sirayla
gelir; taraflar sirayla artirir ya da salar, en yuksek teklifi veren alir.

Kurallar (tum dogrulama sunucuda, burada):
  - Her oyuncuda acilisi siradaki taraf yapar; acilis sirasi her oyuncuda degisir.
  - Acan taraf normalde salamaz: en az 1 dolar vermek zorunda. Sonra taraflar sirayla
    artirir ya da pas der; pas diyenin karsisindaki son teklifiyle oyuncuyu alir.
  - Rakibin parasi bittiyse (yalnizca bos yerlerinin 1'er dolari kaldiysa) acan taraf
    oyuncuyu ona paslayabilir: rakip 1 dolara almak zorunda kalir.
  - Her bos kadro yeri icin 1 dolar ayrilmali: en yuksek teklif = para - (bos yer - 1).
  - Kadrosu dolan cikar. Kalan taraf siradaki oyunculari 1'er dolara otomatik alir.
  - Sonraki oyuncu kimseye gosterilmez.

Draft turu:
  - Normal: oyuncunun adi ve kariyer sayilari gorunur.
  - Kor (blind): yalnizca kategori gorunur ("Career 8+ assists", "Spurs, 1990-2000");
    oyuncu satilinca aciklanir.

Puanlama:
  - judge: 100 uzerinden (score_team): yetenek, sut, oyun kurma, savunma, ribaund ve gercekte
    takim arkadasligi. Mevki ve rol dengesi bilerek yok. services/auction_judge.py bunu temel
    alarak yapay zekaya degerlendirtir; yapay zeka yoksa sonuc bu puandir.
  - h2h3 / h2h5: bes oyuncunun kariyer ortalamalari toplanir, kategorilerin cogunu alan kazanir
    (PTS-REB-AST; h2h5'te STL-BLK de). h2h5'te elle girilen eski efsaneler havuzda yok: top
    calma ve blok verileri bilinmiyor. Esitlikte 100 uzerinden puan bakilir.

Oyuncu puanlari (ovr ve alt degerler) oyun bitene kadar istemciye gitmez.
Veri: services/auction.json (scripts/build_auction.py).
"""
import itertools
import json
import random
import re
from pathlib import Path

from services.eighty_two import NAMES

START_MONEY = 20
ROSTER = 5
LOTS = 60
SLOTS = ("PG", "SG", "SF", "PF", "C")
FILLER_OVR = 40
SCORINGS = ("judge", "h2h3", "h2h5")
H2H = {"h2h3": (("pts", "PTS"), ("reb", "REB"), ("ast", "AST")),
       "h2h5": (("pts", "PTS"), ("reb", "REB"), ("ast", "AST"), ("stl", "STL"), ("blk", "BLK"))}
# (OVR alt siniri, adet): her oyunda yildiz sayisi benzer olsun
TIERS = ((95, 10), (90, 16), (82, 20), (0, 14))
CATEGORIES = (("quality", "Talent", 55), ("spacing", "Shooting", 13), ("playmaking", "Playmaking", 13),
              ("defense", "Defense", 15), ("rebounding", "Rebounding", 4))
WEIGHTS = (0.30, 0.25, 0.20, 0.15, 0.10)

# Kor draft kategorileri
STAT_CATEGORIES = (
    ("Career 25+ points per game", lambda p: p["pts"] >= 25),
    ("Career 20 to 25 points per game", lambda p: 20 <= p["pts"] < 25),
    ("Career 8+ assists per game", lambda p: p["ast"] >= 8),
    ("Career 5 to 8 assists per game", lambda p: 5 <= p["ast"] < 8),
    ("Career 10+ rebounds per game", lambda p: p["reb"] >= 10),
    ("Career 7 to 10 rebounds per game", lambda p: 7 <= p["reb"] < 10),
    ("MVP winner", lambda p: p["mvp"] >= 1),
    ("3+ time NBA champion", lambda p: p["ring"] >= 3),
    ("1 or 2 time NBA champion", lambda p: p["ring"] in (1, 2)),
    ("10+ time All-Star", lambda p: p["as"] >= 10),
    ("5 to 9 time All-Star", lambda p: 5 <= p["as"] < 10),
    ("Never an All-Star", lambda p: p["as"] == 0),
    ("All-Star who never won a title", lambda p: p["as"] >= 1 and p["ring"] == 0),
    ("Elite three-point shooter", lambda p: p["sht"] >= 70),
    ("Elite defender", lambda p: p["dfn"] >= 90),
    ("Elite rim protector", lambda p: p["rim"] >= 75),
    ("Career began before 1990", lambda p: p["y0"] < 1990),
    ("Retired before 2000", lambda p: p["y1"] < 2000),
    ("Debuted in the 2000s", lambda p: 2000 <= p["y0"] < 2010),
    ("Debuted in the 2010s", lambda p: 2010 <= p["y0"] < 2020),
    ("Debuted since 2020", lambda p: p["y0"] >= 2020),
    ("Active player", lambda p: p["cur"]),
    ("Point guard with 7+ career assists", lambda p: p["pos"] == "PG" and p["ast"] >= 7),
    ("Center with 15+ career points", lambda p: p["pos"] == "C" and p["pts"] >= 15),
    ("Forward with 20+ career points", lambda p: p["pos"] in ("SF", "PF") and p["pts"] >= 20),
)
ERAS = ((1986, 1990, "1985-90"), (1991, 2000, "1990-2000"), (2001, 2010, "2000-10"), (2011, 2020, "2010-20"),
        (2021, 2099, "2020-now"))
MIN_IN_CATEGORY = 5
TEAM_CATEGORY_SHARE = 0.4

_POOL = None
_BY_ID = None
_WORTH = {}
_CATS = {}


def _load():
    global _POOL, _BY_ID
    if _POOL is None:
        _POOL = json.loads(Path(__file__).with_name("auction.json").read_text(encoding="utf-8"))["players"]
        _BY_ID = {p["id"]: p for p in _POOL}
    return _POOL


def pool_for(scoring):
    pool = _load()
    return [p for p in pool if not p.get("legend")] if scoring == "h2h5" else pool


def player(pid):
    _load()
    return _BY_ID[pid]


def card(pid):
    """Istemciye giden hali: puan yok."""
    p = player(pid)
    return {"id": p["id"], "name": p["name"], "pos": p["pos"], "y0": p["y0"], "y1": p["y1"], "cur": p["cur"],
            "pts": p["pts"], "reb": p["reb"], "ast": p["ast"], "stl": p.get("stl", 0), "blk": p.get("blk", 0),
            "as": p["as"], "ring": p["ring"], "mvp": p["mvp"], "photo": p["photo"]}


def worth(pid, scoring="judge"):
    """Bot icin deger olcegi (OVR benzeri). H2H'de yetenek degil kariyer sayilari onemli."""
    if scoring == "judge":
        return player(pid)["ovr"]
    if scoring not in _WORTH:
        def raw(p):
            base = p["pts"] / 25 + p["reb"] / 10 + p["ast"] / 7
            return base + p.get("stl", 0) / 1.6 + p.get("blk", 0) / 1.4 if scoring == "h2h5" else base
        ranked = sorted(pool_for(scoring), key=raw)
        _WORTH[scoring] = {p["id"]: 66 + 33 * (i / max(1, len(ranked) - 1)) ** 1.3 for i, p in enumerate(ranked)}
    return _WORTH[scoring].get(pid, 66)


def categories(scoring="judge"):
    """Kor draft: [{"label", "ids", "team"}]. Yeterince oyuncusu olmayanlar elenir."""
    if scoring in _CATS:
        return _CATS[scoring]
    pool = pool_for(scoring)
    out = [{"label": label, "ids": [p["id"] for p in pool if fn(p)], "team": False} for label, fn in STAT_CATEGORIES]
    teams = {}
    for p in pool:
        for code in p.get("ts") or ():
            m = re.fullmatch(r"([A-Z]+)(\d{4})", code)
            if m:
                for lo, hi, era in ERAS:
                    if lo <= int(m.group(2)) <= hi:
                        teams.setdefault((m.group(1), era), set()).add(p["id"])
    for (team, era), ids in sorted(teams.items()):
        out.append({"label": f"{NAMES.get(team, team)}, {era}", "ids": sorted(ids), "team": True})
    _CATS[scoring] = [c for c in out if len(c["ids"]) >= MIN_IN_CATEGORY]
    return _CATS[scoring]


def build_lots(rng, scoring="judge"):
    pool = pool_for(scoring)
    lots, floor_prev = [], 101
    for floor, count in TIERS:
        tier = [p["id"] for p in pool if floor <= p["ovr"] < floor_prev]
        lots += rng.sample(tier, min(count, len(tier)))
        floor_prev = floor
    rng.shuffle(lots)
    return lots[:LOTS]


def build_blind_lots(rng, scoring="judge"):
    """Kategori + o kategoriden gizli oyuncu. Ayni kategori ve oyuncu bir oyunda tekrar etmez."""
    cats = categories(scoring)
    stat = [c for c in cats if not c["team"]]
    team = [c for c in cats if c["team"]]
    rng.shuffle(stat)
    rng.shuffle(team)
    lots, labels, means, used = [], [], [], set()
    while len(lots) < ROSTER * 2 + 2 and (stat or team):
        src = team if team and (not stat or rng.random() < TEAM_CATEGORY_SHARE) else stat
        c = src.pop()
        free = [i for i in c["ids"] if i not in used]
        if not free:
            continue
        pid = rng.choice(free)
        used.add(pid)
        lots.append(pid)
        labels.append(c["label"])
        means.append(sum(worth(i, scoring) for i in c["ids"]) / len(c["ids"]))
    return lots, labels, means


# ==================== OYUN DURUMU ====================

def new_game(seed=None, opener=0, blind=False, scoring="judge"):
    rng = random.Random(seed)
    scoring = scoring if scoring in SCORINGS else "judge"
    if blind:
        lots, labels, means = build_blind_lots(rng, scoring)
    else:
        lots, labels, means = build_lots(rng, scoring), None, None
    g = {"lots": lots, "labels": labels, "means": means, "blind": bool(blind), "scoring": scoring, "i": 0, "bid": 0,
         "bidder": None, "opener": opener, "turn": opener,
         "seats": [{"money": START_MONEY, "roster": []}, {"money": START_MONEY, "roster": []}],
         "over": False, "events": []}
    _settle_turn(g)
    return g


def open_slots(g, seat):
    return ROSTER - len(g["seats"][seat]["roster"])


def max_bid(g, seat):
    n = open_slots(g, seat)
    return 0 if n <= 0 else g["seats"][seat]["money"] - (n - 1)


def lone(g, seat):
    """Rakibin kadrosu doldu: bu taraf tek basina."""
    return open_slots(g, 1 - seat) <= 0 and open_slots(g, seat) > 0


def can_give(g, seat):
    """Acan taraf oyuncuyu paslayabilir mi: teklif yok ve rakibin yalnizca 1'er dolari kaldi."""
    return g["turn"] == seat and g["bidder"] is None and max_bid(g, 1 - seat) == 1


def current(g):
    return g["lots"][g["i"]] if not g["over"] and g["i"] < len(g["lots"]) else None


def current_label(g):
    return g["labels"][g["i"]] if g["blind"] and current(g) else None


def _event(g, kind, **kw):
    g["events"].append({"kind": kind, **kw})
    g["events"] = g["events"][-40:]


def _award(g, seat, price, given=False):
    pid = current(g)
    s = g["seats"][seat]
    s["money"] -= price
    s["roster"].append({"id": pid, "price": price})
    name = g["lot_names"][g["i"]] if g.get("lot_names") else player(pid)["name"]
    _event(g, "sold", seat=seat, price=price, name=name, id=pid, given=given)
    _next_lot(g)


def _finish(g):
    g["over"] = True
    g["turn"] = None


def _next_lot(g):
    g["i"] += 1
    g["bid"], g["bidder"] = 0, None
    if all(open_slots(g, i) <= 0 for i in (0, 1)) or g["i"] >= len(g["lots"]):
        return _finish(g)
    g["opener"] = 1 - g["opener"]
    g["turn"] = g["opener"]
    _settle_turn(g)


def _settle_turn(g):
    """Kadrosu dolu taraf hic oynamaz; tek kalan taraf oyuncuyu 1 dolara otomatik alir."""
    if open_slots(g, g["turn"]) <= 0:
        g["turn"] = 1 - g["turn"]
    if lone(g, g["turn"]):
        _award(g, g["turn"], 1)


def bid(g, seat, amount):
    """(tamam mi, hata). Rakip gecemiyorsa oyuncu hemen satilir."""
    if g["over"] or g["turn"] != seat:
        return False, "Not your turn."
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return False, "Bad bid."
    if amount <= g["bid"]:
        return False, f"Bid more than ${g['bid']}."
    limit = max_bid(g, seat)
    if amount > limit:
        return False, f"You can bid up to ${limit}: keep $1 for each open spot."
    g["bid"], g["bidder"] = amount, seat
    _event(g, "bid", seat=seat, price=amount)
    if max_bid(g, 1 - seat) <= amount:
        _award(g, seat, amount)
    else:
        g["turn"] = 1 - seat
    return True, None


def pass_turn(g, seat, timeout=False):
    """Teklif varken oyuncu son teklifi verene gider; teklif yokken yalnizca parasi biten rakibe paslanir."""
    if g["over"] or g["turn"] != seat:
        return False, "Not your turn."
    if g["bidder"] is None:
        if not can_give(g, seat):
            return False, "You open this player: bid at least $1."
        _event(g, "pass", seat=seat, timeout=timeout)
        _award(g, 1 - seat, 1, given=True)
        return True, None
    _event(g, "pass", seat=seat, timeout=timeout)
    _award(g, g["bidder"], g["bid"])
    return True, None


def timeout_move(g):
    """Sure doldu: acan taraf 1 dolar vermis sayilir, teklif varsa pas."""
    seat = g["turn"]
    return bid(g, seat, 1) if g["bidder"] is None else pass_turn(g, seat, timeout=True)


# ==================== PUANLAMA ====================

def _mates(players):
    pairs = []
    for a, b in itertools.combinations(players, 2):
        if set(a.get("ts") or ()) & set(b.get("ts") or ()):
            pairs.append([a["name"], b["name"]])
    return pairs


def score_team(roster):
    """roster: [{"id", "price"}]. Kategoriler, kadro ve toplam (0-100)."""
    ps = sorted((player(x["id"]) for x in roster), key=lambda p: SLOTS.index(p["pos"]))
    price = {x["id"]: x["price"] for x in roster}
    ovrs = sorted((p["ovr"] for p in ps), reverse=True)
    ovrs += [FILLER_OVR] * (ROSTER - len(ovrs))
    rating = sum(w * o for w, o in zip(WEIGHTS, ovrs))

    def top(key, n=1):
        return sorted((p[key] for p in ps), reverse=True)[:n] or [0]

    ply = top("ply", 2)
    values = {"quality": 55 * max(0.0, min(1.0, (rating - 60) / 37)),
              "spacing": 13 * min(1.0, (sum(p["sht"] for p in ps) / ROSTER) / 52),
              "playmaking": 13 * min(1.0, (ply[0] + 0.5 * (ply[1] if len(ply) > 1 else 0)) / 125),
              "defense": 15 * min(1.0, 0.65 * (sum(p["dfn"] for p in ps) / ROSTER) / 72 + 0.35 * top("rim")[0] / 85),
              "rebounding": 4 * min(1.0, sum(p["rbd"] for p in ps) / 300)}
    mates = _mates(ps)
    chemistry = min(3, len(mates))
    cats = [{"k": k, "label": label, "max": mx, "v": round(values[k], 1)} for k, label, mx in CATEGORIES]
    lineup = [_row(p, price) for p in ps]
    lineup += [{"slot": "-", "name": "Replacement player", "filler": True, "ovr": FILLER_OVR}] * (ROSTER - len(ps))
    return {"cats": cats, "chemistry": chemistry, "mates": mates, "rating": round(rating, 1), "lineup": lineup,
            "total": round(min(100.0, sum(values.values()) + chemistry), 1)}


def _row(p, price):
    return {"slot": p["pos"], "id": p["id"], "name": p["name"], "pos": p["pos"], "ovr": p["ovr"], "price": price[p["id"]],
            "photo": p["photo"], "y0": p["y0"], "y1": p["y1"], "pts": p["pts"], "reb": p["reb"], "ast": p["ast"],
            "stl": p.get("stl", 0), "blk": p.get("blk", 0)}


_NOTES = {"quality": "talent", "spacing": "shooting", "playmaking": "playmaking", "defense": "defense",
          "rebounding": "rebounding"}


def engine_verdict(a, b):
    """Yapay zeka yoksa kisa yorum. 'Team A' / 'Team B' adlari sonra degistirilir."""
    if a["total"] == b["total"]:
        return "Dead even on paper: these two rosters cancel each other out."
    win, lose, wn, ln = (a, b, "Team A", "Team B") if a["total"] > b["total"] else (b, a, "Team B", "Team A")
    diff = sorted((w["v"] - l["v"], w["k"]) for w, l in zip(win["cats"], lose["cats"]))
    edge, weak = _NOTES[diff[-1][1]], diff[0]
    text = f"{wn} wins it on {edge}"
    if weak[0] < 0:
        text += f", even though {ln} had the better {_NOTES[weak[1]]}"
    text += f". Final score {win['total']:.1f} to {lose['total']:.1f}."
    if win["mates"]:
        text += f" Real chemistry helped: {win['mates'][0][0]} and {win['mates'][0][1]} have shared a locker room."
    return text


def head_to_head(g):
    """Bes oyuncunun kariyer ortalamalari toplanir; kategoriyi yuksek olan alir."""
    rows, wins = [], [0, 0]
    for key, label in H2H[g["scoring"]]:
        a, b = (round(sum(player(x["id"]).get(key, 0) for x in s["roster"]), 1) for s in g["seats"])
        w = None if a == b else (0 if a > b else 1)
        if w is not None:
            wins[w] += 1
        rows.append({"k": key, "label": label, "a": a, "b": b, "w": w})
    return {"cats": rows, "wins": wins}


def _h2h_verdict(h):
    def names(seat):
        return [c["label"] for c in h["cats"] if c["w"] == seat]

    def joined(items):
        return ", ".join(items[:-1]) + " and " + items[-1] if len(items) > 1 else (items[0] if items else "nothing")

    a, b = h["wins"]
    text = f"Team A takes {joined(names(0))}; Team B takes {joined(names(1))}."
    if a == b:
        return text + " Categories split evenly, so the overall score decides it."
    lead = "Team A" if a > b else "Team B"
    return text + f" {lead} wins the matchup {max(a, b)}-{min(a, b)}."


def result(g):
    """Motorun sonucu; auction_judge bunu ustune yazabilir (yalnizca judge puanlamasinda)."""
    teams = []
    for s in g["seats"]:
        t = score_team(s["roster"])
        t["money_left"] = s["money"]
        teams.append(t)
    if g["scoring"] in H2H:
        h = head_to_head(g)
        return decide({"teams": teams, "h2h": h, "verdict": _h2h_verdict(h), "by": "h2h"})
    return decide({"teams": teams, "verdict": engine_verdict(teams[0], teams[1]), "by": "engine"})


def decide(res):
    """Kazanan: H2H'de kategori sayisi; sonra yuksek toplam, artan para, o da esitse beraberlik."""
    a, b = res["teams"]
    wins = (res.get("h2h") or {}).get("wins") or [0, 0]
    ka, kb = (wins[0], a["total"], a["money_left"]), (wins[1], b["total"], b["money_left"])
    res["winner"] = None if ka == kb else (0 if ka > kb else 1)
    return res


# ==================== BOT ====================

VALUE_CURVE = [(60, 1), (75, 1.5), (82, 3), (88, 5), (92, 7), (95, 9.5), (97, 11.5), (99, 14)]


def _value(ovr):
    for (x0, y0), (x1, y1) in zip(VALUE_CURVE, VALUE_CURVE[1:]):
        if ovr <= x1:
            return y0 + (y1 - y0) * max(0, ovr - x0) / (x1 - x0)
    return VALUE_CURVE[-1][1]


def bot_value(g, seat, rng):
    """Su anki oyuncu bot icin kac dolar eder. Kor draftta oyuncuyu bilmez, kategorinin ortalamasina bakar."""
    s = g["seats"][seat]
    n = open_slots(g, seat)
    w = g["means"][g["i"]] if g["blind"] else g["lot_scores"][g["i"]] if g.get("lot_scores") else worth(current(g), g["scoring"])
    v = _value(w) * max(0.6, min(1.5, (s["money"] / max(n, 1)) / 4)) + rng.uniform(-1.2, 1.2)
    if not g["blind"] and g["scoring"] == "judge" and ROSTER - n >= 2 and player(current(g))["sht"] >= 60 \
            and not any(player(x["id"])["sht"] >= 60 for x in s["roster"]):
        v *= 1.2
    return v


def bot_move(g, seat, rng=None):
    """('bid', tutar) ya da ('pass', None). Rakibin gecemeyecegi tutardan fazla vermez."""
    rng = rng or random
    v = bot_value(g, seat, rng)
    limit = max_bid(g, seat)
    opp_max = max_bid(g, 1 - seat)
    if g["bid"] == 0:
        if can_give(g, seat):
            return ("pass", None) if v < 2.5 else ("bid", 1)
        # Degerli oyuncuyu yuksek acip rakibi zorlar; digerlerini 1 dolara acar
        amount = min(limit, max(1, int(v * rng.uniform(0.3, 0.6)))) if v >= 4 else 1
        return "bid", min(amount, max(1, opp_max))
    next_bid = g["bid"] + 1
    if next_bid > limit or v < next_bid:
        return "pass", None
    # Rakibi tartmak icin ara sira buyuk adim
    step = 2 if v - next_bid >= 4 and rng.random() < 0.35 else 1
    return "bid", min(limit, int(v), next_bid + step - 1, max(next_bid, opp_max))

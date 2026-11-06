"""
NBA Auction: iki oyuncu, 20'ser dolar, bes kisilik kadro. Havuzdan oyuncular sirayla
gelir; taraflar sirayla artirir ya da salar, en yuksek teklifi veren alir.

Kurallar (tum dogrulama sunucuda, burada):
  - Her oyuncuda acilisi siradaki taraf yapar; acilis sirasi her oyuncuda degisir.
  - Acan taraf salamaz: en az 1 dolar vermek zorunda. Sonra taraflar sirayla artirir ya
    da pas der; pas diyenin karsisindaki son teklifiyle oyuncuyu alir. Her oyuncu satilir.
  - Her bos kadro yeri icin 1 dolar ayrilmali: en yuksek teklif = para - (bos yer - 1).
    Boylece kimse parasiz kalip kadrosunu dolduramama durumuna dusmez.
  - Kadrosu dolan cikar. Kalan taraf siradaki oyunculari 1'er dolara otomatik alir.
  - Sonraki oyuncu kimseye gosterilmez.

Puanlama (score_team): yetenek, mevki uyumu, sut, oyun kurma, savunma, ribaund, rol
dengesi ve gercekte takim arkadasligi. services/auction_judge.py bunu temel alarak
yapay zekaya degerlendirtir; yapay zeka yoksa sonuc bu puandir.

Oyuncu puanlari (ovr ve alt degerler) oyun bitene kadar istemciye gitmez.
Veri: services/auction.json (scripts/build_auction.py).
"""
import itertools
import json
import random
from pathlib import Path

START_MONEY = 20
ROSTER = 5
LOTS = 60
SLOTS = ("PG", "SG", "SF", "PF", "C")
FILLER_OVR = 40
# (OVR alt siniri, adet): her oyunda yildiz sayisi benzer olsun
TIERS = ((95, 10), (90, 16), (82, 20), (0, 14))
CATEGORIES = (("quality", "Talent", 45), ("fit", "Positional fit", 15), ("spacing", "Shooting", 10),
              ("playmaking", "Playmaking", 10), ("defense", "Defense", 12), ("rebounding", "Rebounding", 4),
              ("balance", "Role balance", 4))
WEIGHTS = (0.30, 0.25, 0.20, 0.15, 0.10)

_POOL = None
_BY_ID = None


def _load():
    global _POOL, _BY_ID
    if _POOL is None:
        _POOL = json.loads(Path(__file__).with_name("auction.json").read_text(encoding="utf-8"))["players"]
        _BY_ID = {p["id"]: p for p in _POOL}
    return _POOL


def player(pid):
    _load()
    return _BY_ID[pid]


def card(pid):
    """Istemciye giden hali: puan yok."""
    p = player(pid)
    return {"id": p["id"], "name": p["name"], "pos": p["pos"], "y0": p["y0"], "y1": p["y1"], "cur": p["cur"],
            "pts": p["pts"], "reb": p["reb"], "ast": p["ast"], "as": p["as"], "ring": p["ring"], "mvp": p["mvp"],
            "photo": p["photo"]}


def build_lots(rng):
    pool = _load()
    lots, floor_prev = [], 101
    for floor, count in TIERS:
        tier = [p["id"] for p in pool if floor <= p["ovr"] < floor_prev]
        lots += rng.sample(tier, min(count, len(tier)))
        floor_prev = floor
    rng.shuffle(lots)
    return lots[:LOTS]


# ==================== OYUN DURUMU ====================

def new_game(seed=None, opener=0):
    rng = random.Random(seed)
    g = {"lots": build_lots(rng), "i": 0, "bid": 0, "bidder": None, "opener": opener, "turn": opener,
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


def current(g):
    return g["lots"][g["i"]] if not g["over"] and g["i"] < len(g["lots"]) else None


def _event(g, kind, **kw):
    g["events"].append({"kind": kind, **kw})
    g["events"] = g["events"][-40:]


def _award(g, seat, price):
    pid = current(g)
    s = g["seats"][seat]
    s["money"] -= price
    s["roster"].append({"id": pid, "price": price})
    _event(g, "sold", seat=seat, price=price, name=player(pid)["name"], id=pid)
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
    """Yalnizca teklif varken: oyuncu son teklifi verene gider. Acan taraf salamaz."""
    if g["over"] or g["turn"] != seat:
        return False, "Not your turn."
    if g["bidder"] is None:
        return False, "You open this player: bid at least $1."
    _event(g, "pass", seat=seat, timeout=timeout)
    _award(g, g["bidder"], g["bid"])
    return True, None


def timeout_move(g):
    """Sure doldu: acan taraf 1 dolar vermis sayilir, teklif varsa pas."""
    seat = g["turn"]
    return bid(g, seat, 1) if g["bidder"] is None else pass_turn(g, seat, timeout=True)


# ==================== PUANLAMA ====================

def _assign(players):
    """Bes mevkiye en az uyumsuzlukla yerlesim. Komsu mevki hafif, uzak mevki agir."""
    order = {s: i for i, s in enumerate(SLOTS)}
    best, best_cost = None, 10 ** 9
    filled = players + [None] * (ROSTER - len(players))
    for perm in set(itertools.permutations(range(ROSTER))):
        cost = 0
        for slot_i, pi in enumerate(perm):
            p = filled[pi]
            if p:
                cost += (0, 1, 3, 5, 5)[abs(order[p["pos"]] - slot_i)]
        if cost < best_cost:
            best, best_cost = perm, cost
    return [(SLOTS[i], filled[pi]) for i, pi in enumerate(best)], best_cost


def _mates(players):
    pairs = []
    for a, b in itertools.combinations(players, 2):
        if set(a.get("ts") or ()) & set(b.get("ts") or ()):
            pairs.append([a["name"], b["name"]])
    return pairs


def score_team(roster):
    """roster: [{"id", "price"}]. Kategoriler, dizilis ve toplam (0-100)."""
    ps = [player(x["id"]) for x in roster]
    price = {x["id"]: x["price"] for x in roster}
    ovrs = sorted((p["ovr"] for p in ps), reverse=True)
    ovrs += [FILLER_OVR] * (ROSTER - len(ovrs))
    rating = sum(w * o for w, o in zip(WEIGHTS, ovrs))
    quality = 45 * max(0.0, min(1.0, (rating - 60) / 37))
    lineup, cost = _assign(ps)
    fit = max(0.0, 15 - 2.0 * cost) * len(ps) / ROSTER

    def top(key, n=1):
        return sorted((p[key] for p in ps), reverse=True)[:n] or [0]

    spacing = 10 * min(1.0, (sum(p["sht"] for p in ps) / ROSTER) / 52)
    ply = top("ply", 2)
    playmaking = 10 * min(1.0, (ply[0] + 0.5 * (ply[1] if len(ply) > 1 else 0)) / 125)
    defense = 12 * min(1.0, 0.65 * (sum(p["dfn"] for p in ps) / ROSTER) / 72 + 0.35 * top("rim")[0] / 85)
    rebounding = 4 * min(1.0, sum(p["rbd"] for p in ps) / 300)
    scorers = sum(1 for p in ps if p["sco"] >= 75)
    handlers = sum(1 for p in ps if p["ply"] >= 75)
    balance = 4.0
    if scorers >= 4:
        balance -= 1.5 * (scorers - 3)
    if handlers >= 3:
        balance -= 1.5 * (handlers - 2)
    if scorers == 0:
        balance -= 2
    balance = max(0.0, balance) * len(ps) / ROSTER
    mates = _mates(ps)
    chemistry = min(3, len(mates))
    values = {"quality": quality, "fit": fit, "spacing": spacing, "playmaking": playmaking, "defense": defense,
              "rebounding": rebounding, "balance": balance}
    cats = [{"k": k, "label": label, "max": mx, "v": round(values[k], 1)} for k, label, mx in CATEGORIES]
    return {"cats": cats, "chemistry": chemistry, "mates": mates, "rating": round(rating, 1),
            "lineup": [_slot_row(slot, p, price) for slot, p in lineup],
            "total": round(min(100.0, sum(values.values()) + chemistry), 1)}


def _slot_row(slot, p, price):
    if not p:
        return {"slot": slot, "name": "Replacement player", "filler": True, "ovr": FILLER_OVR}
    return {"slot": slot, "id": p["id"], "name": p["name"], "pos": p["pos"], "ovr": p["ovr"], "price": price[p["id"]],
            "off": p["pos"] != slot, "photo": p["photo"], "y0": p["y0"], "y1": p["y1"]}


_NOTES = {"quality": "talent", "fit": "positional fit", "spacing": "shooting", "playmaking": "playmaking",
          "defense": "defense", "rebounding": "rebounding", "balance": "role balance"}


def engine_verdict(a, b):
    """Yapay zeka yoksa kisa yorum. 'Team A' / 'Team B' adlari sonra degistirilir."""
    if a["total"] == b["total"]:
        return "Dead even on paper: these two rosters cancel each other out."
    win, lose, wn, ln = (a, b, "Team A", "Team B") if a["total"] > b["total"] else (b, a, "Team B", "Team A")
    diff = sorted(((w["v"] - l["v"]) / w["max"], w["k"]) for w, l in zip(win["cats"], lose["cats"]))
    edge, weak = _NOTES[diff[-1][1]], diff[0]
    text = f"{wn} wins it on {edge}"
    if weak[0] < 0:
        text += f", even though {ln} had the better {_NOTES[weak[1]]}"
    text += f". Final score {win['total']:.1f} to {lose['total']:.1f}."
    if win["mates"]:
        text += f" Real chemistry helped: {win['mates'][0][0]} and {win['mates'][0][1]} have shared a locker room."
    return text


def result(g):
    """Motorun sonucu; auction_judge bunu ustune yazabilir."""
    teams = []
    for s in g["seats"]:
        t = score_team(s["roster"])
        t["money_left"] = s["money"]
        teams.append(t)
    return decide({"teams": teams, "verdict": engine_verdict(teams[0], teams[1]), "by": "engine"})


def decide(res):
    """Kazanan: yuksek toplam, esitse artan para, o da esitse beraberlik."""
    a, b = res["teams"]
    key = lambda t: (t["total"], t["money_left"])  # noqa: E731
    res["winner"] = None if key(a) == key(b) else (0 if key(a) > key(b) else 1)
    return res


# ==================== BOT ====================

VALUE_CURVE = [(60, 1), (75, 1.5), (82, 3), (88, 5), (92, 7), (95, 9.5), (97, 11.5), (99, 14)]


def _value(ovr):
    for (x0, y0), (x1, y1) in zip(VALUE_CURVE, VALUE_CURVE[1:]):
        if ovr <= x1:
            return y0 + (y1 - y0) * max(0, ovr - x0) / (x1 - x0)
    return VALUE_CURVE[-1][1]


def bot_value(g, seat, pid, rng):
    """Bu oyuncu bot icin kac dolar eder: yetenek, kalan butce ve kadro ihtiyaci."""
    s, p = g["seats"][seat], player(pid)
    n = open_slots(g, seat)
    v = _value(p["ovr"]) * max(0.6, min(1.5, (s["money"] / max(n, 1)) / 4)) + rng.uniform(-1.2, 1.2)
    have = [player(x["id"])["pos"] for x in s["roster"]]
    if p["pos"] in have:
        v *= 0.6 if n > 1 else 0.3
    elif n == 1 and len(set(have)) >= 4:
        v *= 1.3                                  # son eksik mevki
    if n > 0 and ROSTER - n >= 2 and not any(player(x["id"])["sht"] >= 60 for x in s["roster"]) and p["sht"] >= 60:
        v *= 1.2
    left = LOTS - g["i"]
    if left <= n * 3:                             # havuz bitiyor, secici olma
        v += 2
    return v


def bot_move(g, seat, rng=None):
    """('bid', tutar) ya da ('pass', None). Acarken pas yok."""
    rng = rng or random
    v = bot_value(g, seat, current(g), rng)
    limit = max_bid(g, seat)
    if g["bid"] == 0:
        # Degerli oyuncuyu yuksek acip rakibi zorlar; digerlerini 1 dolara acar
        return "bid", min(limit, max(1, int(v * rng.uniform(0.3, 0.6)))) if v >= 4 else 1
    next_bid = g["bid"] + 1
    if next_bid > limit or v < next_bid:
        return "pass", None
    # Rakibi tartmak icin ara sira buyuk adim
    step = 2 if v - next_bid >= 4 and rng.random() < 0.35 else 1
    return "bid", min(limit, int(v), next_bid + step - 1)

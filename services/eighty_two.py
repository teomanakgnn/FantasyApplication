"""
82-0: rastgele bir takim ve donem cikar, kadrosundan bir oyuncu sec, bes
mevkiyi doldur. Kadronun gucu 82 maclik sezona cevrilir; hedef 82-0.

Donem: tek sezon, 5 ya da 10 sezonluk dilim. Dilimde o takimda oynamis
her oyuncu, o yillardaki en iyi sezonuyla listelenir.

Yeniden cevirme: oyun basina bir "takim" (ayni yillar, baska takim) ve bir
"yil" (ayni takim, baska donem) hakki. Her cevirmenin alternatifleri
sunucuda onceden hazirlanir; gunluk oyunda herkes ayni secenekleri gorur.

Puanlama: oyuncu OVR'leri (55-99, oyun sirasinda gizli) buyukten kucuge
siralanip agirliklandirilir - yildiz takimi tasir, ama tek basina degil.
Agirlikli puan, elle ayarlanmis bir egriyle galibiyete cevrilir (asagida).

Veri: services/eighty_two.json (scripts/build_eighty_two.py), 1986-2026.
"""
import json
import random
from datetime import date
from pathlib import Path

from services.daily_player import today

LAUNCH = date(2026, 10, 13)
SPINS = 5
SPANS = (1, 5, 10)
OFF_POSITION = 6          # mevki disi oyuncunun OVR cezasi
ROSTER_LIMIT = 15

# En iyiden en zayifa agirliklar: yildiz daha cok sayilir.
WEIGHTS = [0.30, 0.25, 0.20, 0.15, 0.10]
# (agirlikli OVR, galibiyet) noktalari; aradaki degerler dogrusal.
# Ornekler: iki 95 + uc 60 -> ~79 -> 32 galibiyet; her takimin en iyisini
# secen tipik kadro ~90 -> 55; agirlikli 96 ve ustu -> 82-0 (eskiden 98.8
# gerekiyordu, kimse ulasamiyordu).
CURVE = [(55, 2), (60, 6), (70, 15), (79, 32), (85, 45), (90, 55), (92, 63), (94, 72), (95, 77), (96, 82)]

SLOTS = ["PG", "SG", "SF", "PF", "C"]
FITS = {"PG": {"PG", "G"}, "SG": {"SG", "G", "GF"}, "SF": {"SF", "F", "GF"}, "PF": {"PF", "F"}, "C": {"C"}}

NAMES = {
    "ATL": "Atlanta Hawks", "BKN": "Brooklyn Nets", "BOS": "Boston Celtics", "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers", "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GS": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers", "LAC": "LA Clippers",
    "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies", "MIA": "Miami Heat", "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves", "NJ": "New Jersey Nets", "NY": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns", "POR": "Portland Trail Blazers",
    "SA": "San Antonio Spurs", "SAC": "Sacramento Kings", "SEA": "Seattle SuperSonics", "TOR": "Toronto Raptors",
    "UTAH": "Utah Jazz", "VAN": "Vancouver Grizzlies", "WSH": "Washington Wizards", "CHA": "Charlotte Hornets",
    "NO": "New Orleans Pelicans",
}

_DATA = None
_INDEX = None


def _data():
    global _DATA, _INDEX
    if _DATA is None:
        raw = json.loads(Path(__file__).with_name("eighty_two.json").read_text(encoding="utf-8"))
        _DATA = raw["teams"]
        _INDEX = {}
        for t in _DATA:
            _INDEX.setdefault(t["team"], {})[t["season"]] = t
    return _DATA


def _index():
    _data()
    return _INDEX


def team_name(abbr, season):
    if abbr == "WSH":
        return "Washington Bullets" if season <= 1997 else "Washington Wizards"
    if abbr == "NO":
        return "New Orleans Hornets" if season <= 2013 else "New Orleans Pelicans"
    if abbr == "CHA":
        return "Charlotte Bobcats" if 2005 <= season <= 2014 else "Charlotte Hornets"
    return NAMES.get(abbr, abbr)


def puzzle_number(day=None):
    return ((day or today()) - LAUNCH).days + 1


def _label(start, span):
    if span == 1:
        return f"{start - 1}-{str(start)[2:]}"
    return f"{start - 1}-{start + span - 1}"      # ornek: 2014-2018 (5 sezon)


def _window_ok(abbr, start, span):
    seasons = _index().get(abbr, {})
    have = sum(1 for y in range(start, start + span) if y in seasons)
    return have >= max(1, (span * 3 + 4) // 5)        # dilimin en az %60'i


def _view(abbr, start, span):
    seasons = _index()[abbr]
    best = {}
    for y in range(start, start + span):
        t = seasons.get(y)
        if not t:
            continue
        for p in t["players"]:
            weight = p["gp"] * p["min"]
            cur = best.get(p["id"])
            if cur is None:
                best[p["id"]] = dict(p, season=y, _load=weight)
            else:
                cur["_load"] += weight
                if p["ovr"] > cur["ovr"]:
                    load = cur["_load"]
                    best[p["id"]] = dict(p, season=y, _load=load)
    # Sira OVR'yi ele vermesin: takimda harcanan dakikaya gore.
    players = sorted(best.values(), key=lambda p: -p["_load"])[:ROSTER_LIMIT]
    mid = start + span // 2
    return {
        "key": f"{abbr}-{start}-{span}", "abbr": abbr, "start": start, "span": span,
        "label": _label(start, span), "name": team_name(abbr, mid),
        "logo": None if abbr in ("NJ", "SEA", "VAN") else f"https://a.espncdn.com/i/teamlogos/nba/500/{abbr.lower()}.png",
        "players": [{"id": p["id"], "name": p["name"], "pos": p["pos"], "season": p["season"], "gp": p["gp"],
                     "pts": p["pts"], "reb": p["reb"], "ast": p["ast"], "stl": p["stl"], "blk": p["blk"],
                     "ovr": p["ovr"]} for p in players],
    }


def _starts(span):
    years = sorted({t["season"] for t in _data()})
    return [y for y in years if y + span - 1 <= years[-1]]


def _pick(rng, span, used, abbr=None, start=None):
    """Kullanilmamis gecerli bir (takim, baslangic) secer."""
    abbrs = sorted(_index())
    starts = _starts(span)
    for _ in range(400):
        a = abbr or rng.choice(abbrs)
        s = start if start is not None else rng.choice(starts)
        if (a, s) not in used and _window_ok(a, s, span):
            used.add((a, s))
            return a, s
    # Sabit tutulan alanla bulunamazsa serbest birak
    return _pick(rng, span, used) if (abbr or start is not None) else (abbrs[0], starts[0])


def game(seed, span=1):
    """
    Bes cevirme; her birinin yaninda 'takim' ve 'yil' alternatifi hazir.
    Ayni takim-donem bir oyunda iki kez cikmaz.
    """
    span = span if span in SPANS else 1
    rng = random.Random(f"{seed}-{span}")
    used, out = set(), []
    for _ in range(SPINS):
        a, s = _pick(rng, span, used)
        ta, ts = _pick(rng, span, used, start=s)          # t: ayni yillar, baska takim
        ya, ys = _pick(rng, span, used, abbr=a)           # y: ayni takim, baska donem
        # Iki hak ayni cevirmede art arda kullanilirsa ikincisi o an
        # ekrandaki takima gore: ty = t'nin baska donemi, yt = y'nin yillarinda baska takim
        tya, tys = _pick(rng, span, used, abbr=ta)
        yta, yts = _pick(rng, span, used, start=ys)
        out.append({"main": _view(a, s, span), "t": _view(ta, ts, span), "y": _view(ya, ys, span),
                    "ty": _view(tya, tys, span), "yt": _view(yta, yts, span)})
    return out


def wins_for(rating):
    if rating <= CURVE[0][0]:
        return CURVE[0][1]
    for (x0, y0), (x1, y1) in zip(CURVE, CURVE[1:]):
        if rating <= x1:
            return int(round(y0 + (y1 - y0) * (rating - x0) / (x1 - x0)))
    return 82


def rating(ovrs):
    ovrs = sorted(ovrs, reverse=True)
    return sum(w * o for w, o in zip(WEIGHTS, ovrs))


def config():
    return {"slots": SLOTS, "fits": {k: sorted(v) for k, v in FITS.items()}, "penalty": OFF_POSITION,
            "weights": WEIGHTS, "curve": CURVE, "spins": SPINS, "spans": list(SPANS),
            # Cark seridindeki sahte duraklar icin
            "franchises": [{"abbr": a, "name": NAMES.get(a, a),
                            "logo": f"https://a.espncdn.com/i/teamlogos/nba/500/{a.lower()}.png"}
                           for a in NAMES if a not in ("NJ", "SEA", "VAN")]}

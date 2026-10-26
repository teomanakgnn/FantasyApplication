"""
Arama motoru sayfalari: 2026-27 fantasy siralamasi ve oyuncu basina
"fantasy outlook" sayfasi. Siralama 2026-27 sezonunun gercek mac basi
istatistiklerinden (services/trade_values.py, "season"); bu sezon yeterli maci
olmayan oyuncular projeksiyonlariyla listenin sonuna eklenir (sayfalari kalir).

Insanlarin Google'da aradigi sey tam olarak bu: "jokic fantasy outlook",
"fantasy basketball rankings 2026-27", "punt ft% targets".
"""
import math
import re
import unicodedata

from services.cache import cache_data
from services.trade_values import CATS, players

PUNTS = ["FT%", "FG%", "AST", "3PM", "PTS", "TO"]


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def _min_games(rows):
    """Siralamaya girmek icin gereken mac: takimlarin oynadigi macin ~%40'i (en az 1)."""
    most = max((p["gp"] for p in rows), default=0)
    return max(1, round(0.4 * most))


def _prep(rows, basis):
    out = []
    for p in rows:
        q = dict(p)
        q["slug"] = slugify(p["name"])
        q["total"] = round(sum(p["z"].values()), 2)
        q["basis"] = basis
        out.append(q)
    return sorted(out, key=lambda p: -p["total"])


@cache_data(ttl=1800, show_spinner=False, copy_result=False)
def table():
    """
    2026-27 sezon istatistiklerine gore 9-cat sirasi. Yeterli maci olanlar
    once (mac basi z-skoru), digerleri (sakat, az mac) projeksiyonla sonra.
    """
    season = players("season")
    need = _min_games(season)
    ranked = _prep([p for p in season if p["gp"] >= need], "season")
    seen = {p["slug"] for p in ranked}
    rest = [p for p in _prep(players("proj"), "proj") if p["slug"] not in seen]
    # Bu sezon az oynamis ama sezon satiri olanlar: istatistikleri gercek olsun
    by_season = {slugify(p["name"]): p for p in season}
    for p in rest:
        s = by_season.get(p["slug"])
        if s:
            p["season_gp"] = s["gp"]
    out = ranked + rest
    for i, p in enumerate(out, 1):
        p["rank"] = i
    # Her punt yapisinda sira (iki grup kendi icinde, ayni duzen)
    for c in PUNTS:
        order = (sorted(ranked, key=lambda p: -(p["total"] - p["z"][c]))
                 + sorted(rest, key=lambda p: -(p["total"] - p["z"][c])))
        for i, p in enumerate(order, 1):
            p.setdefault("punt_rank", {})[c] = i
    by_slug = {p["slug"]: p for p in out}
    return out, by_slug


def ranked_count():
    rows, _ = table()
    return sum(1 for p in rows if p["basis"] == "season")


def adp_of(name):
    from services.trade_values import _board_info, _norm
    return (_board_info()[1].get(_norm(name)) or {}).get("adp")


def tier(rank):
    return ("Elite" if rank <= 12 else "Early-round star" if rank <= 36 else "Solid starter" if rank <= 72
            else "Mid-round value" if rank <= 120 else "Late-round flier" if rank <= 170 else "Deep-league option")


def similar(p, pool, n=5):
    def dist(q):
        return math.sqrt(sum((p["z"][c] - q["z"][c]) ** 2 for c in CATS))
    return sorted((q for q in pool if q["slug"] != p["slug"] and abs(q["rank"] - p["rank"]) <= 60), key=dist)[:n]


def outlook(p):
    """Kurallarla yazilmis kisa fantasy yorumu (paragraf listesi)."""
    z = p["z"]
    strong = sorted(CATS, key=lambda c: -z[c])
    weak = sorted(CATS, key=lambda c: z[c])
    name = p["name"].split(" ")[-1] if len(p["name"].split(" ")) > 1 else p["name"]
    paras = []
    line = (f"{p['s']['pts']:.1f} points, {p['s']['reb']:.1f} rebounds, {p['s']['ast']:.1f} assists, "
            f"{p['s']['stl']:.1f} steals, {p['s']['blk']:.1f} blocks and {p['s']['tpm']:.1f} threes per game")
    if p.get("basis") == "season":
        paras.append(f"{p['name']} ranks No. {p['rank']} in 9-category leagues on his 2026-27 numbers "
                     f"({tier(p['rank']).lower()}): {line} over {p['gp']} game{'s' if p['gp'] != 1 else ''}.")
    else:
        paras.append(f"{p['name']} has not played enough 2026-27 games to be ranked on this season's stats yet, "
                     f"so he sits at No. {p['rank']} on his projection: {line}.")
    good = [c for c in strong if z[c] >= 0.75][:3]
    bad = [c for c in weak if z[c] <= -0.5][:2]
    if good:
        paras.append(f"His fantasy value comes from {', '.join(good)}"
                     + (f"; the drag is {' and '.join(bad)}." if bad else ", with no real weak spot."))
    best_punt = min(PUNTS, key=lambda c: p["punt_rank"][c])
    if p["punt_rank"][best_punt] + 5 < p["rank"]:
        paras.append(f"He fits a punt {best_punt} build best: there he ranks No. {p['punt_rank'][best_punt]}, "
                     f"{p['rank'] - p['punt_rank'][best_punt]} spots higher than in a balanced team.")
    else:
        paras.append(f"He is a balanced contributor - no punt build lifts him much, which makes {name} easy to fit "
                     f"into any team.")
    adp = adp_of(p["name"])
    if adp:
        diff = adp - p["rank"]
        if diff >= 12:
            paras.append(f"Draft value: his ADP is {adp:.0f}, so he usually goes about {diff:.0f} picks after our "
                         f"ranking - a bargain if you need his categories.")
        elif diff <= -12:
            paras.append(f"Draft value: his ADP is {adp:.0f}, roughly {-diff:.0f} picks earlier than we rank him. "
                         f"Name value is doing some of the work here.")
        else:
            paras.append(f"Draft value: his ADP ({adp:.0f}) is in line with where we rank him.")
    if p.get("basis") != "season" and p["avail"] < 0.8:
        paras.append(f"Health: he is projected for about {round(p['avail'] * 82)} games, so build depth behind him.")
    if p.get("injury") and p["injury"] != "ACTIVE":
        paras.append(f"Current status: {p['injury'].replace('_', ' ').lower()}.")
    return paras

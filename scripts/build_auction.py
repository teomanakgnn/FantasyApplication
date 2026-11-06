"""
NBA Auction oyuncu havuzu (services/auction.json).

Kimler girer:
  - Guncel oyuncular: son sezonu 2025-26 ya da sonrasi ve rotasyon seviyesi
  - 2000 sonrasi bilinenler: All-Star, buyuk odul ya da yuksek zirve
  - Daha eskiler: yalnizca cok bilinenler (LEGENDS, elle; veri seti 1986'da basliyor)

Kaynak: services/eighty_two.json (sezonluk OVR ve istatistik), services/grid.json
(kariyer, oduller), ESPN kariyer istatistikleri (uclukler - ikisinde de yok).

Calistirma: python scripts/build_auction.py  (birkac dakika; ESPN'e 6 paralel istek)
"""
import concurrent.futures as cf
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from scripts.build_grid import get, num  # noqa: E402

OUT = os.path.join(ROOT, "services", "auction.json")
CURRENT_FROM = 2026
MAJOR = ("mvp", "fmvp", "dpoy", "roy", "smoy", "allnba")

# Ad, mevki, ilk/son yil, kariyer sayi/ribaund/asist, All-Star, yuzuk, MVP, OVR, savunma, sut, pota koruma, oyun kurma
LEGENDS = [
    ("Wilt Chamberlain", "C", 1960, 1973, 30.1, 22.9, 4.4, 13, 2, 4, 98, 88, 5, 95, 45),
    ("Bill Russell", "C", 1957, 1969, 15.1, 22.5, 4.3, 12, 11, 5, 97, 99, 5, 99, 42),
    ("Oscar Robertson", "PG", 1961, 1974, 25.7, 6.2, 9.5, 12, 1, 1, 96, 65, 55, 8, 98),
    ("Jerry West", "SG", 1961, 1974, 27.0, 5.8, 6.7, 14, 1, 0, 96, 82, 75, 10, 70),
    ("Elgin Baylor", "SF", 1959, 1972, 27.4, 13.5, 4.3, 11, 0, 0, 93, 50, 25, 15, 42),
    ("Kareem Abdul-Jabbar", "C", 1970, 1989, 24.6, 11.2, 3.6, 19, 6, 6, 99, 85, 8, 92, 38),
    ("Julius Erving", "SF", 1977, 1987, 22.0, 6.7, 3.9, 11, 1, 1, 95, 72, 18, 45, 40),
    ("Larry Bird", "SF", 1980, 1992, 24.3, 10.0, 6.3, 12, 3, 3, 98, 72, 82, 20, 68),
    ("Magic Johnson", "PG", 1980, 1996, 19.5, 7.2, 11.2, 12, 5, 3, 98, 60, 30, 12, 100),
    ("Moses Malone", "C", 1975, 1995, 20.3, 12.2, 1.3, 12, 1, 3, 94, 58, 3, 50, 12),
    ("Pete Maravich", "SG", 1971, 1980, 24.2, 4.2, 5.4, 5, 0, 0, 88, 35, 60, 5, 58),
    ("John Havlicek", "SF", 1963, 1978, 20.8, 6.3, 4.8, 13, 8, 0, 91, 78, 45, 10, 50),
    ("Walt Frazier", "PG", 1968, 1980, 18.9, 5.9, 6.1, 7, 2, 0, 90, 90, 40, 10, 65),
    ("Bill Walton", "C", 1975, 1987, 13.3, 10.5, 3.4, 2, 2, 1, 86, 85, 5, 88, 38),
    ("Elvin Hayes", "PF", 1969, 1984, 21.0, 12.5, 1.8, 12, 1, 0, 90, 72, 3, 75, 18),
    ("Bob Cousy", "PG", 1951, 1963, 18.4, 5.2, 7.5, 13, 6, 1, 90, 45, 35, 5, 85),
    ("George Gervin", "SG", 1977, 1986, 26.2, 4.6, 2.8, 9, 0, 0, 90, 35, 45, 20, 30),
    ("Rick Barry", "SF", 1966, 1980, 23.2, 6.5, 4.9, 8, 1, 1, 90, 60, 62, 8, 52),
    ("Willis Reed", "C", 1965, 1974, 18.7, 12.9, 1.8, 7, 2, 1, 89, 70, 5, 55, 20),
    ("Kevin McHale", "PF", 1981, 1993, 17.9, 7.3, 1.7, 7, 3, 0, 90, 72, 3, 72, 18),
    ("Robert Parish", "C", 1977, 1997, 14.5, 9.1, 1.4, 9, 4, 0, 86, 62, 2, 62, 15),
    ("Isiah Thomas", "PG", 1982, 1994, 19.2, 3.6, 9.3, 12, 2, 0, 93, 68, 35, 5, 92),
    ("James Worthy", "SF", 1983, 1994, 17.6, 5.1, 3.0, 7, 3, 0, 87, 50, 12, 20, 30),
]
LEGEND_NAMES = {x[0] for x in LEGENDS}
OLD_MIN_ALL_STAR = 7
MIN_PEAK = 70
# Veri setinde G/F gelen ya da yanlis mevkide gorunen yildizlar
POS_FIX = {"Michael Jordan": "SG", "Kobe Bryant": "SG", "LeBron James": "SF", "Tim Duncan": "PF", "Dirk Nowitzki": "PF",
           "Kevin Garnett": "PF", "Charles Barkley": "PF", "Karl Malone": "PF", "Giannis Antetokounmpo": "PF",
           "Kevin Durant": "SF", "Dwyane Wade": "SG", "James Harden": "SG", "Reggie Miller": "SG", "Ray Allen": "SG",
           "Vince Carter": "SG", "Tracy McGrady": "SF", "Scottie Pippen": "SF", "Clyde Drexler": "SG",
           "Dominique Wilkins": "SF", "Allen Iverson": "PG", "Carmelo Anthony": "SF", "Paul Pierce": "SF",
           "Kawhi Leonard": "SF", "Anthony Davis": "PF", "Shaquille O'Neal": "C", "Hakeem Olajuwon": "C",
           "David Robinson": "C", "Patrick Ewing": "C", "Stephen Curry": "PG", "Steve Nash": "PG", "Jason Kidd": "PG"}
# Siralama yuzdesi -> OVR: havuzda herkes 99 olmasin, en iyiler gercekten seyrek olsun
OVR_CURVE = [(0, 66), (25, 75), (50, 81), (75, 88), (90, 93), (97, 97), (100, 99)]


def ovr_from_rank(pct):
    for (x0, y0), (x1, y1) in zip(OVR_CURVE, OVR_CURVE[1:]):
        if pct <= x1:
            return round(y0 + (y1 - y0) * (pct - x0) / (x1 - x0))
    return 99


def resume(g, rows):
    """Zirve + kariyer: en iyi bes sezon ve oduller. Kisa bir patlama ile uzun bir kariyer ayni olmasin."""
    aw = g.get("aw") or {}
    top = sorted((r["ovr"] for r in rows), reverse=True)[:5]
    return (sum(top) / len(top) + 2.0 * min(4, aw.get("mvp", 0)) + 0.6 * aw.get("fmvp", 0) + 0.35 * min(14, g["as"])
            + 0.35 * min(12, aw.get("allnba", 0)) + 0.5 * min(6, g.get("ring", 0)) + 0.5 * aw.get("dpoy", 0))


def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, int(round(x))))


def three_point(pid):
    """ESPN kariyerinden en iyi sezon 3PM ve kariyer 3P%."""
    d = get(f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{pid}/stats")
    cats = {c.get("name"): c for c in (d or {}).get("categories") or []}
    avg = cats.get("averages")
    if not avg:
        return pid, None
    labels = avg["labels"]
    if "3PT" not in labels:
        return pid, None
    i = labels.index("3PT")
    pct_i = labels.index("3P%") if "3P%" in labels else None
    best = 0.0
    for st in avg.get("statistics") or []:
        s = st.get("stats") or []
        gp = num(s[0]) if s else 0
        made = re.split(r"[-/]", str(s[i]))[0] if i < len(s) else "0"
        if gp >= 25:
            best = max(best, num(made))
    tot = avg.get("totals") or []
    pct = num(tot[pct_i]) if pct_i is not None and pct_i < len(tot) else 0.0
    return pid, {"best": best, "pct": pct}


def position(rows):
    """En cok oynanan ayrintili mevki; eski veride G/F icin istatistikten."""
    counts = {}
    for r in rows:
        counts[r["pos"]] = counts.get(r["pos"], 0) + 1
    exact = {k: v for k, v in counts.items() if k in ("PG", "SG", "SF", "PF", "C")}
    if exact:
        return max(exact, key=exact.get)
    top = max(counts, key=counts.get)
    peak = max(rows, key=lambda r: r["ovr"])
    if top == "C":
        return "C"
    if top in ("G", "GF"):
        return "PG" if peak["ast"] >= 5.5 else "SG"
    return "PF" if peak["reb"] >= 7 else "SF"


def main():
    e82 = json.load(open(os.path.join(ROOT, "services", "eighty_two.json"), encoding="utf-8"))["teams"]
    grid = json.load(open(os.path.join(ROOT, "services", "grid.json"), encoding="utf-8"))["players"]
    seasons = {}
    for t in e82:
        for p in t["players"]:
            seasons.setdefault(p["id"], []).append(dict(p, season=t["season"], team=t["team"]))

    chosen = {}
    for pid, g in grid.items():
        rows = seasons.get(pid)
        if not rows or g["n"] in LEGEND_NAMES:
            continue
        top = sorted((r["ovr"] for r in rows), reverse=True)[:3]
        peak = sum(top) / len(top)
        aw = g.get("aw") or {}
        major = any(aw.get(k) for k in MAJOR)
        if top[0] < MIN_PEAK:                # "Gary Payton II" babasinin All-Star sayisiyla gelmesin
            continue
        if g["y1"] >= CURRENT_FROM:
            keep = peak >= 74 or g["as"] >= 1
        elif g["y1"] >= 2000:
            keep = g["as"] >= 1 or major or top[0] >= 88
        else:
            keep = g["as"] >= OLD_MIN_ALL_STAR or aw.get("mvp")
        if keep:
            chosen[pid] = (g, rows, peak)

    print("secilen", len(chosen), "ucluk verisi cekiliyor")
    threes = {}
    with cf.ThreadPoolExecutor(6) as ex:
        for pid, r in ex.map(three_point, list(chosen)):
            threes[pid] = r

    name_to_id = {g["n"]: pid for pid, g in grid.items()}
    raw = sorted(resume(g, rows) for g, rows, _ in chosen.values())
    players = []
    for pid, (g, rows, peak) in chosen.items():
        aw = g.get("aw") or {}
        c = g["c"]
        b = g["best"]
        three = threes.get(pid) or {"best": 0.0, "pct": 0.0}
        peak_row = max(rows, key=lambda r: r["ovr"])
        ovr = ovr_from_rank(100 * sum(1 for x in raw if x <= resume(g, rows)) / len(raw))
        pos = POS_FIX.get(g["n"]) or position(rows)
        big = pos in ("PF", "C")
        d = b.get("stl", 0) * 22 + b.get("blk", 0) * (20 if big else 12) + aw.get("alldef", 0) * 3 + aw.get("dpoy", 0) * 8
        sh = three["best"] * 15 + max(0, three["pct"] - 33) * 4
        if three["pct"] < 30:
            sh *= 0.5
        players.append({
            "id": pid, "name": g["n"], "pos": pos, "y0": g["y0"], "y1": g["y1"], "cur": g["y1"] >= CURRENT_FROM,
            "pts": c.get("pts", 0), "reb": c.get("reb", 0), "ast": c.get("ast", 0),
            "as": g["as"], "ring": g.get("ring", 0), "mvp": aw.get("mvp", 0), "photo": True,
            "ovr": clamp(ovr, 55, 99), "peak_season": peak_row["season"],
            "sco": clamp(b.get("pts", 0) * 3.0), "ply": clamp(b.get("ast", 0) * 10), "rbd": clamp(b.get("reb", 0) * 7.5),
            "dfn": clamp(d), "sht": clamp(sh), "rim": clamp(b.get("blk", 0) * 30),
            "ts": sorted(f"{r['team']}{r['season']}" for r in rows),
        })
    for row in LEGENDS:
        name, pos, y0, y1, pts, reb, ast, stars, ring, mvp, ovr, dfn, sht, rim, ply = row
        pid = name_to_id.get(name)
        rows = seasons.get(pid) or []
        players.append({
            "id": pid or "L-" + re.sub(r"[^a-z]", "", name.lower()), "name": name, "pos": pos, "y0": y0, "y1": y1, "cur": False,
            "pts": pts, "reb": reb, "ast": ast, "as": stars, "ring": ring, "mvp": mvp, "photo": bool(pid),
            "ovr": ovr, "peak_season": None, "sco": clamp(pts * 3.2), "ply": ply, "rbd": clamp(reb * 6),
            "dfn": dfn, "sht": sht, "rim": rim, "ts": sorted(f"{r['team']}{r['season']}" for r in rows),
        })
    players.sort(key=lambda p: (-p["ovr"], p["name"]))
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"players": players}, fh, ensure_ascii=False, separators=(",", ":"))
    print("havuz", len(players), "ucluk verisi olmayan", sum(1 for pid in chosen if not threes.get(pid)))


if __name__ == "__main__":
    main()

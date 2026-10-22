"""
82-0 oyununun veri seti: her sezonun her takiminin kadrosu, oyuncularin
o sezonki mac basi ortalamalari ve 60-99 arasi bir OVR puani.
Kaynak ESPN sezon istatistikleri; sonuc services/eighty_two.json.
"""
import concurrent.futures as cf
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("SKIP_WARMUP", "1")
from services.espn_api import get_nba_season_stats_official  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "services", "eighty_two.json")


def num(v):
    try:
        f = float(v)
        return 0.0 if f != f else f
    except (TypeError, ValueError):
        return 0.0


def season(year):
    try:
        df = get_nba_season_stats_official(year)
    except Exception as exc:
        print(year, "failed", exc)
        return year, []
    rows = []
    for _, r in df.iterrows():
        gp, mins = num(r.get("GP")), num(r.get("MIN"))
        if gp < 20 or mins < 12 or not r.get("PLAYER_ID"):
            continue
        p = {"id": str(r["PLAYER_ID"]), "name": r["PLAYER"], "team": r["TEAM"], "pos": r.get("POS") or "",
             "gp": int(gp), "min": round(mins, 1)}
        for k, key in (("pts", "PTS"), ("reb", "REB"), ("ast", "AST"), ("stl", "STL"), ("blk", "BLK"), ("fg", "FG%")):
            p[k] = round(num(r.get(key)), 1)
        rows.append(p)
    return year, rows


def _base_fg(pos):
    """Mevkiye gore beklenen FG% (uzunlar pota dibinden atar)."""
    pos = pos or ""
    if "C" in pos or pos == "PF":
        return 51
    return 44 if ("G" in pos and "F" not in pos) else 47


def value(p):
    # Kaba bir "mac basi etki": skor, ribaund, asist ve savunma. Verim iki
    # yonlu: mevkisine gore isabetli atan kazanir, cok atip az sokan kaybeder
    # (eski formul hacmi ve ribaundu odullendiriyordu: Drummond = MVP Curry).
    # Az mac oynayan biraz geriye duser.
    base = p["pts"] + 0.85 * p["reb"] + 1.5 * p["ast"] + 2.0 * p["stl"] + 1.6 * p["blk"]
    base += (p["fg"] - _base_fg(p.get("pos"))) * 0.25 * p["pts"] / 10
    return base * (0.8 + 0.2 * min(p["gp"], 70) / 70)


EXPONENT = 4.5   # buyudukce ust dilim seyreklesir (90+ ve 95+ daha az)


def rescore():
    """Mevcut veri dosyasindaki istatistiklerden OVR'leri yeniden hesapla (ESPN'e gitmeden)."""
    import bisect
    with open(OUT, encoding="utf-8") as fh:
        data = json.load(fh)
    allp = [p for t in data["teams"] for p in t["players"]]
    vals = sorted(value(p) for p in allp)
    for p in allp:
        p["ovr"] = int(round(55 + 44 * (bisect.bisect_left(vals, value(p)) / len(vals)) ** EXPONENT))
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print("rescored", len(allp), "player-seasons")


def main():
    years = range(1980, 2027)
    with cf.ThreadPoolExecutor(6) as ex:
        seasons = dict(ex.map(season, years))
    allp = [p for rows in seasons.values() for p in rows]
    vals = sorted(value(p) for p in allp)
    n = len(vals)

    def ovr(v):
        # yuzdelik -> 55..99; ust dilim seyrek: %90 = 84, %99 = 97, 99 yalniz en tepe
        import bisect
        q = bisect.bisect_left(vals, v) / n
        return int(round(55 + 44 * q ** EXPONENT))

    teams = []
    for year, rows in sorted(seasons.items()):
        if not rows:
            continue
        by_team = {}
        for p in rows:
            p["ovr"] = ovr(value(p))
            by_team.setdefault(p["team"], []).append(p)
        for abbr, players in by_team.items():
            players.sort(key=lambda p: -p["min"])
            if len(players) < 7:
                continue
            teams.append({"season": year, "team": abbr, "players": players[:12]})
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"teams": teams}, fh, ensure_ascii=False, separators=(",", ":"))
    yrs = sorted({t["season"] for t in teams})
    print("seasons", yrs[0], "-", yrs[-1], len(yrs), "teams", len(teams), "bytes", os.path.getsize(OUT))


if __name__ == "__main__":
    rescore() if "--rescore" in sys.argv else main()

"""
Starting Five oyununun veri seti: 2002-2026 NBA Finalleri ve konferans
finallerinin ilk beşleri (ESPN). Bir kez calistirilip sonuc depoya
yazilir: services/starting_five.json. Yeni sezon icin tekrar calistir.
"""
import concurrent.futures as cf
import json
import os
import re
from datetime import date, timedelta

import requests

SB = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
SUM = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
OUT = os.path.join(os.path.dirname(__file__), "..", "services", "starting_five.json")
KEEP = re.compile(r"final", re.I)


def day_events(d):
    try:
        data = requests.get(SB, params={"dates": d.strftime("%Y%m%d"), "seasontype": 3}, timeout=20).json()
    except Exception:
        return []
    out = []
    for e in data.get("events", []):
        notes = [n.get("headline", "") for n in e.get("competitions", [{}])[0].get("notes", [])]
        title = notes[0] if notes else ""
        if KEEP.search(title):
            out.append((e["id"], title, d.isoformat(), e.get("season", {}).get("year")))
    return out


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def game(ev):
    gid, title, day, year = ev
    try:
        s = requests.get(SUM, params={"event": gid}, timeout=20).json()
        comp = s["header"]["competitions"][0]
        scores = {c["team"]["abbreviation"]: num(c.get("score")) for c in comp["competitors"]}
        home = next(c["team"]["abbreviation"] for c in comp["competitors"] if c.get("homeAway") == "home")
        teams, bench = [], []
        for t in s["boxscore"]["players"]:
            st = t["statistics"][0]
            keys = st.get("keys") or []
            ix = {k: i for i, k in enumerate(keys)}
            starters = []
            for a in st["athletes"]:
                ath = a["athlete"]
                stats = a.get("stats") or []
                line = {k: num(stats[ix[k]]) if k in ix and ix[k] < len(stats) else 0
                        for k in ("minutes", "points", "rebounds", "assists")}
                p = {"id": str(ath.get("id")), "name": ath.get("displayName"),
                     "pos": (ath.get("position") or {}).get("abbreviation") or "",
                     "jersey": ath.get("jersey"), "min": line["minutes"], "pts": line["points"],
                     "reb": line["rebounds"], "ast": line["assists"]}
                (starters if a.get("starter") else bench).append(p)
            if len(starters) != 5:
                return None
            team = t["team"]
            teams.append({"abbr": team["abbreviation"], "name": team.get("displayName"),
                          "logo": team.get("logo"), "color": "#" + (team.get("color") or "333333"),
                          "score": scores.get(team["abbreviation"], 0), "home": team["abbreviation"] == home,
                          "starters": starters})
        if len(teams) != 2:
            return None
        return {"id": gid, "title": title, "date": day, "season": year, "teams": teams,
                "bench": [b["name"] for b in bench]}
    except Exception as exc:
        print("skip", gid, exc)
        return None


def main():
    days = []
    for year in range(2002, 2027):
        d = date(year, 5, 12)
        while d <= date(year, 6, 25):
            days.append(d)
            d += timedelta(days=1)
    with cf.ThreadPoolExecutor(16) as ex:
        events = [e for evs in ex.map(day_events, days) for e in evs]
    events = list({e[0]: e for e in events}.values())
    print("events", len(events))
    with cf.ThreadPoolExecutor(16) as ex:
        games = [g for g in ex.map(game, events) if g]
    games.sort(key=lambda g: g["date"])
    names = sorted({p["name"] for g in games for t in g["teams"] for p in t["starters"]}
                   | {n for g in games for n in g.pop("bench")})
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"games": games, "names": names}, fh, ensure_ascii=False, separators=(",", ":"))
    print("games", len(games), "names", len(names), "bytes", os.path.getsize(OUT))


if __name__ == "__main__":
    main()

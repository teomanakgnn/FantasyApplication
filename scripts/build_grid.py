"""
3x3 Grid oyununun veri seti (services/grid.json).

Oyuncu havuzu: 1985-86'dan bu yana kadrolarda yer almis herkes (82-0 veri seti).
Her oyuncu icin:
  - ESPN kariyer istatistikleri: sezon sezon takimlar (franchise kimligiyle: Sonics = Thunder),
    sezon ortalamalari, kariyer ortalamalari
  - ESPN sezonluk oduller: MVP, DPOY, ROY, 6MOY, MIP, Finals MVP, All-NBA, All-Defensive;
    sampiyon = o yilin Finals MVP'sinin takimi, o sezon o takimda oynayan herkes
  - All-Star secim sayisi: Wikipedia "List of NBA All-Stars" (MediaWiki API)

Calistirma: python scripts/build_grid.py  (birkac dakika; ESPN'e nazik, 6 paralel istek)
"""
import concurrent.futures as cf
import html as htmllib
import json
import os
import re
import sys
import time
import unicodedata

import requests

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "services", "grid.json")
UA = {"User-Agent": "HoopLifeNBA-grid-builder/1.0 (+https://app.hooplifenba.com)"}
CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba"
AWARDS = {33: "mvp", 39: "dpoy", 35: "roy", 40: "smoy", 36: "mip", 43: "fmvp",
          44: "allnba", 45: "allnba", 46: "allnba", 49: "alldef", 50: "alldef"}
FIRST_SEASON, LAST_SEASON = 1980, 2026


def norm(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", s)
    return re.sub(r"[^a-z]", "", s)


def get(url, params=None, tries=3):
    for k in range(tries):
        try:
            # Wikipedia tanitici bir User-Agent ister; ESPN'e projenin her yerindeki gibi varsayilan istek
            r = requests.get(url, params=params, headers=UA if "wikipedia.org" in url else None, timeout=25)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            if k == tries - 1:
                print("  failed", url, exc)
                return None
            time.sleep(1.5 * (k + 1))


def num(v):
    try:
        f = float(str(v).replace(",", ""))
        return 0.0 if f != f else f
    except (TypeError, ValueError):
        return 0.0


# ---------------- oyuncu havuzu ----------------
def universe():
    data = json.load(open(os.path.join(ROOT, "services", "eighty_two.json"), encoding="utf-8"))
    out = {}
    for t in data["teams"]:
        for p in t["players"]:
            out.setdefault(p["id"], p["name"])
    return out


# ---------------- takimlar ----------------
def teams():
    d = get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams")
    out = {}
    for x in d["sports"][0]["leagues"][0]["teams"]:
        t = x["team"]
        out[str(t["id"])] = {"abbr": t["abbreviation"], "name": t["displayName"], "short": t.get("shortDisplayName") or t["name"]}
    return out


# ---------------- oyuncu kariyeri ----------------
def career(pid):
    d = get(f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{pid}/stats")
    if not d:
        return pid, None
    cats = {c.get("name"): c for c in d.get("categories") or []}
    avg = cats.get("averages")
    if not avg:
        return pid, None
    labels = avg["labels"]
    ix = {k: labels.index(k) for k in ("GP", "MIN", "PTS", "REB", "AST", "STL", "BLK") if k in labels}
    seasons = []
    for st in avg.get("statistics") or []:
        yr = (st.get("season") or {}).get("year")
        tid = str(st.get("teamId") or "")
        s = st.get("stats") or []
        if not yr or not tid:
            continue
        seasons.append({"y": int(yr), "t": tid, **{k.lower(): num(s[i]) for k, i in ix.items() if i < len(s)}})
    tot = avg.get("totals") or []
    car = {k.lower(): num(tot[i]) for k, i in ix.items() if i < len(tot)}
    return pid, {"seasons": seasons, "career": car}


# ---------------- oduller ----------------
def season_awards(year):
    d = get(f"{CORE}/seasons/{year}/awards", {"limit": 100})
    out = []
    for it in (d or {}).get("items") or []:
        m = re.search(r"/awards/(\d+)", it["$ref"])
        aid = int(m.group(1)) if m else None
        if aid not in AWARDS:
            continue
        a = get(it["$ref"])
        for w in (a or {}).get("winners") or []:
            ath = re.search(r"/athletes/(\d+)", (w.get("athlete") or {}).get("$ref", ""))
            team = re.search(r"/teams/(\d+)", (w.get("team") or {}).get("$ref", ""))
            out.append({"award": AWARDS[aid], "pid": ath.group(1) if ath else None, "team": team.group(1) if team else None})
    return year, out


# ---------------- All-Star (Wikipedia) ----------------
def all_stars():
    j = get("https://en.wikipedia.org/w/api.php", {"action": "parse", "page": "List of NBA All-Stars", "prop": "text",
                                                    "format": "json", "formatversion": 2})
    html = j["parse"]["text"]
    out = {}
    clean = lambda c: htmllib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip()
    for tb in re.findall(r'<table class="wikitable.*?</table>', html, re.S):
        rows = re.findall(r"<tr.*?</tr>", tb, re.S)
        head = [clean(c) for c in re.findall(r"<t[hd].*?</t[hd]>", rows[0], re.S)] if rows else []
        if "Player" not in head:
            continue
        pi, ni = head.index("Player"), head.index("#")
        for r in rows[1:]:
            cells = [clean(c) for c in re.findall(r"<t[hd].*?</t[hd]>", r, re.S)]
            if len(cells) <= max(pi, ni):
                continue
            name = re.sub(r"\[.*?\]|[\^*†‡§]", "", cells[pi]).strip()
            n = int(num(cells[ni]))
            if name and n:
                out[norm(name)] = max(out.get(norm(name), 0), n)
    return out


def main():
    t0 = time.time()
    uni = universe()
    print("players", len(uni))
    tm = teams()
    print("teams", len(tm))

    careers = {}
    with cf.ThreadPoolExecutor(6) as ex:
        for i, (pid, c) in enumerate(ex.map(career, list(uni))):
            if c:
                careers[pid] = c
            if i % 300 == 0:
                print(f"  careers {i}/{len(uni)}  {time.time() - t0:.0f}s")
    print("careers", len(careers))

    awards, champs = {}, {}
    with cf.ThreadPoolExecutor(6) as ex:
        for year, rows in ex.map(season_awards, range(FIRST_SEASON, LAST_SEASON + 1)):
            for r in rows:
                if r["award"] == "fmvp" and r["team"]:
                    champs[year] = r["team"]
                if r["pid"]:
                    awards.setdefault(r["pid"], {}).setdefault(r["award"], []).append(year)
    print("champions", len(champs), sorted(champs.items())[-3:])

    stars = all_stars()
    print("all-star names", len(stars))

    players, unmatched = {}, 0
    for pid, name in uni.items():
        c = careers.get(pid)
        if not c or not c["seasons"]:
            continue
        seasons = c["seasons"]
        team_ids = sorted({s["t"] for s in seasons if s["t"] in tm})
        ring = sorted({s["y"] for s in seasons if champs.get(s["y"]) == s["t"] and s.get("gp", 0) >= 1})
        aw = {k: len(set(v)) for k, v in (awards.get(pid) or {}).items()}
        n_as = stars.get(norm(name), 0)
        q = lambda k: max((s.get(k, 0) for s in seasons if s.get("gp", 0) >= 40), default=0.0)
        players[pid] = {
            "n": name, "t": team_ids, "y0": min(s["y"] for s in seasons), "y1": max(s["y"] for s in seasons),
            "yrs": len({s["y"] for s in seasons}), "ring": len(ring), "as": n_as, "aw": aw,
            "c": {k: round(v, 1) for k, v in c["career"].items()},
            "best": {k: round(q(k), 1) for k in ("pts", "reb", "ast", "stl", "blk")},
        }
    # Wikipedia'daki All-Star adlarindan havuzda eslesmeyen (cogu 1986 oncesi emekliler)
    names = {norm(p["n"]) for p in players.values()}
    unmatched = [k for k in stars if k not in names]
    print("players out", len(players), "all-star names not in pool:", len(unmatched))
    json.dump({"built": time.strftime("%Y-%m-%d"), "teams": tm, "champions": {str(k): v for k, v in champs.items()},
               "players": players}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {OUT} in {time.time() - t0:.0f}s, {os.path.getsize(OUT) // 1024} KB")


if __name__ == "__main__":
    main()

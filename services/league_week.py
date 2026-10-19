"""
My League haftasi: bu haftanin eslesmeleri, beklenen skor ve kategori
kategori beklenen sonuc, skor tahmini penceresi.

Beklenen haftalik toplamlar: her takimin IR disindaki oyunculari; her gun o
gun maci olan oyunculardan en iyi N'i (N = ligin ilk bes + UTIL sayisi)
sayilir. Oyuncu mac basi degeri ESPN'in sezon projeksiyonu, sezon icinde
son 15 gun ile yarim yarima. Kategori kazanma ihtimali: iki takimin
beklenen farki / haftalik sapma (normal yaklasim).

Hafta / son tarih: ESPN haftalari Pazartesi-Pazar (1. hafta sezonun ilk
gunu basliyor). Tahmin, haftanin Pazartesi'si 23:59 Londra saatinde kapanir
(1. hafta icin sezon baslamadan onceki Pazartesi).
"""
import math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import requests

from services.cache import cache_data
from services.espn_league import BASE, _cookies, _team_name

LONDON = ZoneInfo("Europe/London")
SEASON_URL = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/seasons/{season}"
STAT = {"PTS": "0", "BLK": "1", "STL": "2", "AST": "3", "REB": "6", "TO": "11", "3PM": "17",
        "FGM": "13", "FGA": "14", "FTM": "15", "FTA": "16"}
CAT_BY_ID = {0: "PTS", 1: "BLK", 2: "STL", 3: "AST", 6: "REB", 11: "TO", 17: "3PM", 19: "FG%", 20: "FT%"}
ORDER = ["FG%", "FT%", "3PM", "PTS", "REB", "AST", "STL", "BLK", "TO"]
# Mac basi degisim katsayisi (sapma / ortalama): STL/BLK cok oynak
CV = {"PTS": 0.42, "REB": 0.45, "AST": 0.5, "STL": 0.95, "BLK": 0.95, "TO": 0.6, "3PM": 0.75}
SLOT_BENCH, SLOT_IR = 12, 13


def _get(url, views, timeout=20):
    r = requests.get(url, params=[("view", v) for v in views], cookies=_cookies(), timeout=timeout)
    r.raise_for_status()
    return r.json()


@cache_data(ttl=6 * 3600, show_spinner=False, copy_result=False)
def pro_schedule(season):
    """{proTeamId: set(scoringPeriodId)} ve {scoringPeriodId: ilk mac tarihi (UTC)}."""
    data = _get(SEASON_URL.format(season=season), ("proTeamSchedules_wl",))
    games, first = {}, {}
    for t in data["settings"]["proTeams"]:
        for sp, gl in (t.get("proGamesByScoringPeriod") or {}).items():
            sp = int(sp)
            if gl:
                games.setdefault(t["id"], set()).add(sp)
                ts = min(g["date"] for g in gl) / 1000
                first[sp] = min(first.get(sp, ts), ts)
    return games, first


@cache_data(ttl=300, show_spinner=False, copy_result=False)
def league_raw(league_id, season):
    url = BASE.format(season=season, league_id=int(league_id))
    return _get(url, ("mTeam", "mRoster", "mSettings", "mStatus", "mMatchupScore"))


def _sp_date(sp, first, start_day):
    """ESPN gun numarasinin ABD tarihi."""
    return start_day + timedelta(days=sp - 1)


def weeks(season, first):
    """Hafta -> (baslangic, bitis) ABD tarihleri; ESPN haftalari Pazartesi-Pazar."""
    start_day = datetime.utcfromtimestamp(first[1]).date() if first.get(1) else date(season - 1, 10, 20)
    # Ilk mac ABD'de aksam, UTC'de ertesi gun olabilir: 07:00 UTC oncesi bir gun geri
    if first.get(1) and datetime.utcfromtimestamp(first[1]).hour < 9:
        start_day -= timedelta(days=1)
    out, s = {}, start_day
    for w in range(1, 30):
        e = s + timedelta(days=6 - s.weekday())        # o haftanin Pazar'i
        out[w] = (s, e)
        s = e + timedelta(days=1)
    return out, start_day


def deadline(week_start):
    monday = week_start - timedelta(days=week_start.weekday())
    return datetime.combine(monday, time(23, 59), LONDON)


def _proj(pl, season):
    """Mac basi beklenen istatistik: ESPN projeksiyonu (+ sezon icinde son 15 gun)."""
    proj, l15, l15_gp = None, None, 0
    for s in pl.get("stats") or []:
        sid = str(s.get("id") or "")
        if s.get("statSourceId") == 1 and s.get("statSplitTypeId") == 0 and sid.endswith(str(season)):
            proj = s.get("averageStats") or {}
        if s.get("statSourceId") == 0 and s.get("statSplitTypeId") == 2 and sid.endswith(str(season)):
            l15 = s.get("averageStats") or {}
            l15_gp = int(float(l15.get("42") or 0))
    base = proj or l15 or {}
    out = {}
    for k, code in STAT.items():
        v = float(base.get(code) or 0)
        if proj and l15 and l15_gp >= 3:
            v = 0.5 * v + 0.5 * float(l15.get(code) or 0)
        out[k] = v
    return out


def _value(s):
    return s["PTS"] + 1.2 * s["REB"] + 1.5 * s["AST"] + 3 * s["STL"] + 3 * s["BLK"] - s["TO"] + 0.5 * s["3PM"]


def _phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def team_week(team, sps, games, starters, season):
    """Takimin hafta boyunca beklenen kategori toplamlari ve varyanslari."""
    players = []
    for e in (team.get("roster") or {}).get("entries") or []:
        if e.get("lineupSlotId") == SLOT_IR:
            continue
        pl = (e.get("playerPoolEntry") or {}).get("player") or {}
        if pl.get("injuryStatus") in ("OUT", "INJURY_RESERVE", "SUSPENSION"):
            continue
        st = _proj(pl, season)
        players.append({"pro": pl.get("proTeamId"), "s": st, "v": _value(st)})
    tot = {k: 0.0 for k in STAT}
    var = {k: 0.0 for k in CV}
    gp = 0
    for sp in sps:
        today = sorted((p for p in players if sp in games.get(p["pro"], ())), key=lambda p: -p["v"])[:starters]
        gp += len(today)
        for p in today:
            for k in STAT:
                tot[k] += p["s"][k]
            for k, cv in CV.items():
                var[k] += (cv * p["s"][k]) ** 2
    return tot, var, gp


def compare(a, b, cats):
    (ta, va, ga), (tb, vb, gb) = a, b
    rows, ea = [], 0.0
    for c in cats:
        if c in ("FG%", "FT%"):
            m, at = ("FGM", "FGA") if c == "FG%" else ("FTM", "FTA")
            pa = ta[m] / ta[at] if ta[at] else 0.0
            pb = tb[m] / tb[at] if tb[at] else 0.0
            sd = math.sqrt(1.6 * (pa * (1 - pa) / max(ta[at], 1) + pb * (1 - pb) / max(tb[at], 1))) or 0.01
            p = _phi((pa - pb) / sd)
            rows.append({"cat": c, "a": round(100 * pa, 1), "b": round(100 * pb, 1), "pa": round(p, 3), "pct": True})
        else:
            sd = math.sqrt(va[c] + vb[c]) or 1.0
            diff = ta[c] - tb[c]
            p = _phi((-diff if c == "TO" else diff) / sd)
            rows.append({"cat": c, "a": round(ta[c], 1), "b": round(tb[c], 1), "pa": round(p, 3), "pct": False})
        ea += rows[-1]["pa"]
    n = len(rows)
    return rows, round(ea, 1), round(n - ea, 1), ga, gb


def week(league_id, season, my_team=None):
    data = league_raw(int(league_id), int(season))
    settings = data.get("settings") or {}
    cats = [CAT_BY_ID[i["statId"]] for i in (settings.get("scoringSettings") or {}).get("scoringItems") or []
            if i.get("statId") in CAT_BY_ID]
    cats = [c for c in ORDER if c in cats] or ORDER
    slots = (settings.get("rosterSettings") or {}).get("lineupSlotCounts") or {}
    starters = sum(int(n) for k, n in slots.items() if int(k) not in (SLOT_BENCH, SLOT_IR)) or 10
    games, first = pro_schedule(int(season))
    wk, start_day = weeks(int(season), first)
    teams = {t["id"]: t for t in data.get("teams") or []}
    names = {tid: _team_name(t) for tid, t in teams.items()}

    now = datetime.now(LONDON)
    current = (data.get("status") or {}).get("currentMatchupPeriod") or 1
    # Tahmine acik hafta: son tarihi gecmemis ilk hafta
    open_week = next((w for w in range(1, 25) if deadline(wk[w][0]) > now), None)
    show = open_week or current

    def sps_of(w):
        s, e = wk[w]
        return [sp for sp in range((s - start_day).days + 1, (e - start_day).days + 2)]

    matchups = []
    for m in data.get("schedule") or []:
        if m.get("matchupPeriodId") != show:
            continue
        h, a = (m.get("home") or {}), (m.get("away") or {})
        if "teamId" not in a:
            continue
        sps = sps_of(show)
        rows, eh, ea, gh, ga = compare(team_week(teams[h["teamId"]], sps, games, starters, season),
                                       team_week(teams[a["teamId"]], sps, games, starters, season), cats)
        cs_h, cs_a = h.get("cumulativeScore") or {}, a.get("cumulativeScore") or {}
        matchups.append({
            "id": m["id"], "home": h["teamId"], "away": a["teamId"],
            "home_name": names.get(h["teamId"]), "away_name": names.get(a["teamId"]),
            "home_logo": teams[h["teamId"]].get("logo"), "away_logo": teams[a["teamId"]].get("logo"),
            "exp_home": eh, "exp_away": ea, "games_home": gh, "games_away": ga, "cats": rows,
            "actual": [cs_h.get("wins", 0), cs_a.get("wins", 0), cs_h.get("ties", 0)],
            "final": m.get("winner") not in (None, "UNDECIDED"),
            "mine": my_team is not None and str(my_team) in (str(h["teamId"]), str(a["teamId"])),
        })
    matchups.sort(key=lambda m: not m["mine"])
    s, e = wk[show]
    return {"week": show, "start": s, "end": e, "deadline": deadline(s), "open": open_week == show,
            "cats": cats, "n_cats": len(cats), "matchups": matchups, "teams": names}


def results(league_id, season, period):
    """Biten haftanin gercek sonuclari: {matchup_id: (home, away)} (yalnizca kesinlesenler)."""
    data = league_raw(int(league_id), int(season))
    out = {}
    for m in data.get("schedule") or []:
        if m.get("matchupPeriodId") == period and m.get("winner") not in (None, "UNDECIDED"):
            out[m["id"]] = ((m["home"].get("cumulativeScore") or {}).get("wins", 0),
                            (m["away"].get("cumulativeScore") or {}).get("wins", 0))
    return out

"""
My League analizleri (ESPN): oyuncu formu, lig nabzi, takim form tablosu,
serbest oyuncu firsatlari, kullanicinin takimi icin uyarilar ve yorumlar.

Kaynak tek bir ESPN cagrisi (mRoster + mTeam + mSettings): her oyuncunun
sezon, son 7 / 15 / 30 gun ortalamalari, sakatlik durumu ve kadrodaki
yeri (ilk bes / yedek / IR) ayni yanitta geliyor. Serbest oyuncular icin
ikinci bir cagri (kona_player_info).

Form olcusu: oyuncunun tek sayilik fantasy degeri (sayi + ribaund + asist
+ top calma + blok - top kaybi, yuzde katkisi dahil) son 15 gunde sezon
ortalamasina gore. Az oynayan oyuncu (son donemde 2 mactan az) form
hesabina girmez.

Yeni sezon ligi henuz yenilenmemisse (ESPN 404) bir onceki sezona duser
ve bunu ekranda soyler.
"""
import json

import requests

from services.cache import cache_data
from services.espn_league import BASE, LeagueError, _cookies, _team_name
from services.nba_season import get_current_season_year

# ESPN istatistik kimlikleri
PTS, BLK, STL, AST, REB, TO = "0", "1", "2", "3", "6", "11"
FGM, FGA, FTM, FTA, TPM, MIN, GP = "13", "14", "15", "16", "17", "40", "42"
SPLITS = {0: "season", 1: "last7", 2: "last15", 3: "last30"}
SLOT_BENCH, SLOT_IR = 12, 13
INJURY_WORDS = {"OUT": "out", "DAY_TO_DAY": "day-to-day", "SUSPENSION": "suspended", "INJURY_RESERVE": "on IR"}
PRO_TEAMS = {1: "ATL", 2: "BOS", 3: "NO", 4: "CHI", 5: "CLE", 6: "DAL", 7: "DEN", 8: "DET", 9: "GS", 10: "HOU",
             11: "IND", 12: "LAC", 13: "LAL", 14: "MIA", 15: "MIL", 16: "MIN", 17: "BKN", 18: "NY", 19: "ORL",
             20: "PHI", 21: "PHX", 22: "POR", 23: "SAC", 24: "SA", 25: "OKC", 26: "UTAH", 27: "WSH", 28: "TOR",
             29: "MEM", 30: "CHA", 0: "FA"}
HOT, COLD = 1.25, 0.75


def _get(league_id, season, views, headers=None):
    url = BASE.format(season=int(season), league_id=int(league_id))
    try:
        r = requests.get(url, params=[("view", v) for v in views], cookies=_cookies(),
                         headers=headers or {}, timeout=20)
    except requests.RequestException as exc:
        raise LeagueError("Could not reach ESPN. Try again in a moment.") from exc
    if r.status_code == 401:
        raise LeagueError("This league is private, so ESPN will not share it.")
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise LeagueError(f"ESPN returned {r.status_code}. Try again in a moment.")
    return r.json()


@cache_data(ttl=600, show_spinner=False, copy_result=False)
def league_data(league_id, season=None):
    """(veri, sezon, onceki_sezon_mu). Yeni sezon yoksa bir oncekine duser."""
    season = int(season or get_current_season_year())
    for s in (season, season - 1):
        data = _get(league_id, s, ("mTeam", "mRoster", "mSettings", "mStatus"))
        if data:
            return data, s, s != season
    raise LeagueError(f"No league {league_id} on ESPN. Check the ID.")


@cache_data(ttl=900, show_spinner=False, copy_result=False)
def free_agents(league_id, season, limit=60):
    flt = {"players": {"filterStatus": {"value": ["FREEAGENT", "WAIVERS"]}, "limit": limit,
                       "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}
    data = _get(league_id, season, ("kona_player_info",), {"x-fantasy-filter": json.dumps(flt)}) or {}
    return [_player(p.get("player") or {}, slot=None, season=season) for p in data.get("players", [])]


# ==================== OYUNCU ====================

def _value(avg):
    """Tek sayilik fantasy degeri (mac basi)."""
    if not avg:
        return 0.0
    g = lambda k: float(avg.get(k) or 0)
    fg = (g(FGM) - 0.47 * g(FGA)) * 1.2       # isabet katkisi, lig ortalamasina gore
    ft = (g(FTM) - 0.78 * g(FTA)) * 1.0
    return g(PTS) + 1.2 * g(REB) + 1.5 * g(AST) + 3 * g(STL) + 3 * g(BLK) - 1.5 * g(TO) + g(TPM) * 0.5 + fg + ft


def _player(pl, slot, season):
    splits = {}
    for s in pl.get("stats") or []:
        if s.get("statSourceId") != 0 or s.get("statSplitTypeId") not in SPLITS:
            continue
        sid = str(s.get("id") or "")
        # Sezon toplami icin yalnizca istenen sezonun satiri
        if s.get("statSplitTypeId") == 0 and not sid.endswith(str(season)):
            continue
        splits[SPLITS[s["statSplitTypeId"]]] = s.get("averageStats") or {}
    season_avg = splits.get("season") or {}
    gp = lambda k: int(float((splits.get(k) or {}).get(GP) or 0))
    out = {
        "id": str(pl.get("id")), "name": pl.get("fullName") or "", "team": PRO_TEAMS.get(pl.get("proTeamId"), ""),
        "injury": pl.get("injuryStatus") or "ACTIVE", "slot": slot,
        "owned": round(float((pl.get("ownership") or {}).get("percentOwned") or 0), 1),
        "gp": gp("season"), "min": round(float(season_avg.get(MIN) or 0), 1),
        "value": round(_value(season_avg), 1),
        "line": {k: round(float(season_avg.get(code) or 0), 1)
                 for k, code in (("pts", PTS), ("reb", REB), ("ast", AST), ("stl", STL), ("blk", BLK), ("3pm", TPM))},
    }
    for k in ("last7", "last15", "last30"):
        avg = splits.get(k) or {}
        out[k] = round(_value(avg), 1) if gp(k) >= 2 else None
        out[k + "_gp"] = gp(k)
    recent = out["last15"] if out["last15"] is not None else out["last7"]
    out["form"] = round(recent / out["value"], 2) if recent is not None and out["value"] > 3 else None
    out["trend"] = ("hot" if out["form"] and out["form"] >= HOT else "cold" if out["form"] and out["form"] <= COLD else "")
    return out


# ==================== LIG ====================

def build(league_id, my_team_id=None, season=None):
    data, season, fallback = league_data(league_id, season)
    settings = data.get("settings") or {}
    teams = []
    for t in data.get("teams") or []:
        roster = []
        for e in (t.get("roster") or {}).get("entries") or []:
            pl = (e.get("playerPoolEntry") or {}).get("player") or {}
            roster.append(_player(pl, e.get("lineupSlotId"), season))
        active = [p for p in roster if p["slot"] not in (SLOT_IR,)]
        # Form tablosu: en iyi 10 aktif oyuncunun son 15 gun degeri vs sezon degeri
        top = sorted(active, key=lambda p: -p["value"])[:10]
        season_strength = sum(p["value"] for p in top)
        recent_strength = sum((p["last15"] if p["last15"] is not None else p["value"]) for p in top)
        rec = (t.get("record") or {}).get("overall") or {}
        teams.append({"id": t.get("id"), "name": _team_name(t), "abbrev": t.get("abbrev"), "logo": t.get("logo"),
                      "wins": rec.get("wins", 0), "losses": rec.get("losses", 0), "ties": rec.get("ties", 0),
                      "rank": t.get("playoffSeed") or t.get("rankCalculatedFinal") or 0,
                      "roster": sorted(roster, key=lambda p: (p["slot"] in (SLOT_BENCH, SLOT_IR), -p["value"])),
                      "strength": round(season_strength, 1), "recent": round(recent_strength, 1)})
    for key, field in (("strength_rank", "strength"), ("recent_rank", "recent")):
        for i, t in enumerate(sorted(teams, key=lambda t: -t[field]), 1):
            t[key] = i
    me = next((t for t in teams if str(t["id"]) == str(my_team_id)), None) if my_team_id else None

    rostered = [dict(p, owner=t["name"], owner_id=t["id"]) for t in teams for p in t["roster"] if p["form"] is not None]
    # Siralama orana degil mutlak farka gore: 3'ten 10'a cikan yedek, 30'dan
    # 40'a cikan yildizin onune gecmesin.
    gain = lambda p: (p["last15"] if p["last15"] is not None else p["last7"]) - p["value"]
    hot = sorted([p for p in rostered if p["trend"] == "hot" and p["value"] >= 8], key=lambda p: -gain(p))[:8]
    cold = sorted([p for p in rostered if p["trend"] == "cold" and p["value"] >= 15], key=gain)[:8]

    try:
        fas = free_agents(league_id, season)
    except LeagueError:
        fas = []
    waiver = sorted([p for p in fas if p["injury"] == "ACTIVE" and (p["last15"] or p["last7"] or 0) > 0],
                    key=lambda p: -((p["last15"] if p["last15"] is not None else p["last7"]) or 0))[:8]

    out = {"name": settings.get("name") or f"League {league_id}", "season": season, "fallback": fallback,
           "teams": sorted(teams, key=lambda t: (t["rank"] or 99, -t["wins"])), "me": me,
           "hot": hot, "cold": cold, "waiver": waiver,
           "period": (data.get("status") or {}).get("currentMatchupPeriod")}
    out["form_table"] = sorted(teams, key=lambda t: t["recent_rank"])
    if me:
        out["alerts"] = alerts(me, waiver)
        out["notes"] = notes(me, teams, waiver)
    return out


# ==================== UYARILAR / YORUMLAR ====================

def alerts(me, waiver):
    """Kullanicinin takimi icin yapilacaklar. Her uyari kalici bir anahtar tasir (e-posta tekrari icin)."""
    out = []
    starters = [p for p in me["roster"] if p["slot"] not in (SLOT_BENCH, SLOT_IR)]
    bench = [p for p in me["roster"] if p["slot"] == SLOT_BENCH]
    for p in starters:
        if p["injury"] in ("OUT", "INJURY_RESERVE", "SUSPENSION"):
            out.append({"level": "bad", "key": f"out-{p['id']}-{p['injury']}",
                        "text": f"{p['name']} is {INJURY_WORDS.get(p['injury'], 'out')} but still in your starting lineup."})
        elif p["injury"] == "DAY_TO_DAY":
            out.append({"level": "warn", "key": f"dtd-{p['id']}",
                        "text": f"{p['name']} is day-to-day - check before lock."})
    for p in bench:
        worst = min(starters, key=lambda s: (s["last15"] if s["last15"] is not None else s["value"]), default=None)
        if worst and p["trend"] == "hot" and (p["last15"] or 0) > (worst["last15"] if worst["last15"] is not None else worst["value"]):
            out.append({"level": "good", "key": f"bench-{p['id']}",
                        "text": f"{p['name']} is hot on your bench ({p['last15']:.0f} value, last 15) - more than {worst['name']} is giving you."})
    for p in starters:
        if p["trend"] == "cold" and p["value"] >= 15:
            out.append({"level": "warn", "key": f"cold-{p['id']}",
                        "text": f"{p['name']} has gone cold: {p['last15'] or p['last7']:.0f} value over the last stretch against {p['value']:.0f} for the season."})
    if waiver:
        mine = sorted(me["roster"], key=lambda p: (p["last15"] if p["last15"] is not None else p["value"]))
        weakest = mine[0] if mine else None
        best = waiver[0]
        best_v = best["last15"] if best["last15"] is not None else best["last7"]
        weak_v = (weakest["last15"] if weakest and weakest["last15"] is not None else weakest["value"]) if weakest else 0
        if weakest and best_v and best_v > weak_v + 3:
            out.append({"level": "good", "key": f"fa-{best['id']}",
                        "text": f"{best['name']} ({best['team']}) is a free agent playing better ({best_v:.0f}) than {weakest['name']} ({weak_v:.0f}). Worth a look."})
    order = {"bad": 0, "warn": 1, "good": 2}
    return sorted(out, key=lambda a: order[a["level"]])


def notes(me, teams, waiver):
    """Kisa yorumlar: takimin yeri, formu, tasiyicisi."""
    n = len(teams)
    out = []
    sr, rr = me["strength_rank"], me["recent_rank"]
    out.append(f"On paper your roster ranks {_ord(sr)} of {n}; on recent form it is {_ord(rr)}.")
    if rr <= sr - 2:
        out.append("Your team is trending up - the last two weeks are better than your season numbers.")
    elif rr >= sr + 2:
        out.append("Your team is underperforming its talent lately. Check the cold players below before you panic-trade.")
    stars = sorted(me["roster"], key=lambda p: -p["value"])[:2]
    if stars:
        out.append(f"{' and '.join(p['name'] for p in stars)} carry your team.")
    hot = [p for p in me["roster"] if p["trend"] == "hot" and p["injury"] == "ACTIVE"]
    if hot:
        out.append(f"Hot right now: {', '.join(p['name'] for p in hot[:3])}.")
    leader = min(teams, key=lambda t: t["recent_rank"])
    if leader["id"] != me["id"]:
        out.append(f"The team to watch is {leader['name']} - best form in the league over the last 15 days.")
    return out


def _ord(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def team_choices(league_id, season=None):
    data, season, fallback = league_data(league_id, season)
    return [{"id": t.get("id"), "name": _team_name(t)} for t in data.get("teams") or []], \
        (data.get("settings") or {}).get("name") or f"League {league_id}", season

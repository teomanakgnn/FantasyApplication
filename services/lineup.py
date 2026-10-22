"""
Gunun kadrosu (My League, ESPN): bugun maci olan oyuncular, rakip ve saat,
mevki uygunluguna gore en iyi ilk bes/on ve gereken degisiklikler.

Oneri: baslangic yerleri x oyuncular atama problemi (scipy
linear_sum_assignment). Agirlik = oyuncunun mac basi degeri (ESPN
projeksiyonu + son 15 gun), bugun maci yoksa / OUT ise 0 (yedege). Maci
baslamis oyuncu kilitli: ESPN degistirmeye izin vermez, yerinde kalir.
Mevcut yerine kucuk bir bonus: esit secenekte gereksiz hareket olmaz.

Yonetici icin: oneriyi ESPN'e uygula (resmi olmayan yazma ucu, sahibin
espn_s2 / SWID cerezleriyle).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import requests
from scipy.optimize import linear_sum_assignment

from services import league_week as lw
from services.cache import cache_data

EASTERN = ZoneInfo("America/New_York")
SLOT_NAMES = {0: "PG", 1: "SG", 2: "SF", 3: "PF", 4: "C", 5: "G", 6: "F", 7: "SG/SF", 8: "G/F", 9: "PF/C",
              10: "F/C", 11: "UTIL", 12: "BE", 13: "IR"}
WRITE_URL = ("https://lm-api-writes.fantasy.espn.com/apis/v3/games/fba/seasons/{season}"
             "/segments/0/leagues/{league_id}/transactions/")
SKIP = ("OUT", "INJURY_RESERVE", "SUSPENSION")


@cache_data(ttl=6 * 3600, show_spinner=False, copy_result=False)
def _pro_games(season):
    """{scoringPeriodId: {proTeamId: {opp, home, ts}}} - her takimin o gunku maci."""
    data = lw._get(lw.SEASON_URL.format(season=season), ("proTeamSchedules_wl",))
    out = {}
    for t in data["settings"]["proTeams"]:
        for sp, gl in (t.get("proGamesByScoringPeriod") or {}).items():
            for g in gl or []:
                home = g.get("homeProTeamId") == t["id"]
                out.setdefault(int(sp), {})[t["id"]] = {
                    "opp": g.get("awayProTeamId") if home else g.get("homeProTeamId"),
                    "home": home, "ts": (g.get("date") or 0) / 1000}
    return out


def today_sp(season):
    """ESPN gun numarasi (1 = sezonun ilk gunu), ABD Dogu tarihine gore."""
    _, first = lw.pro_schedule(season)
    _, start_day = lw.weeks(season, first)
    return (datetime.now(EASTERN).date() - start_day).days + 1


def plan(league_id, season, team_id, sp=None):
    from services.draft_data import get_pro_team_map
    data = lw.league_raw(int(league_id), season)
    team = next((t for t in data.get("teams") or [] if t["id"] == int(team_id)), None)
    if not team:
        return None
    sp = sp or today_sp(season)
    games = _pro_games(season).get(sp, {})
    abbr = get_pro_team_map(season)
    now = datetime.now().timestamp()

    counts = ((data.get("settings") or {}).get("rosterSettings") or {}).get("lineupSlotCounts") or {}
    slots = [int(s) for s, n in sorted(counts.items(), key=lambda kv: int(kv[0]))
             for _ in range(int(n)) if int(s) not in (lw.SLOT_BENCH, lw.SLOT_IR)]

    players = []
    for e in (team.get("roster") or {}).get("entries") or []:
        pl = (e.get("playerPoolEntry") or {}).get("player") or {}
        g = games.get(pl.get("proTeamId"))
        injury = pl.get("injuryStatus") or "ACTIVE"
        st = lw._proj(pl, season)
        players.append({
            "id": pl.get("id"), "name": pl.get("fullName"), "team": abbr.get(pl.get("proTeamId"), ""),
            "slot": e.get("lineupSlotId"), "eligible": set(pl.get("eligibleSlots") or []), "injury": injury,
            "value": round(lw._value(st), 1), "game": g, "plays": bool(g) and injury not in SKIP,
            "locked": bool(g) and g["ts"] and now >= g["ts"],
            "opp": (("vs " if g["home"] else "@ ") + abbr.get(g["opp"], "")) if g else "",
            "tip": datetime.utcfromtimestamp(g["ts"]).isoformat() + "Z" if g and g["ts"] else None})

    # Kilitli (maci baslamis) ve IR'dakiler yerinde kalir; onlarin baslangic yerleri dolu sayilir
    free_slots = list(slots)
    target = {}
    for p in players:
        if p["slot"] == lw.SLOT_IR or p["locked"]:
            target[p["id"]] = p["slot"]
            if p["slot"] in free_slots:
                free_slots.remove(p["slot"])
    pool = [p for p in players if p["id"] not in target]
    if pool and free_slots:
        w = np.full((len(pool), len(free_slots)), -1e6)
        for i, p in enumerate(pool):
            for j, s in enumerate(free_slots):
                if s in p["eligible"]:
                    w[i, j] = (p["value"] if p["plays"] else 0.0) + (0.05 if p["slot"] == s else 0.0)
        rows, cols = linear_sum_assignment(w, maximize=True)
        for i, j in zip(rows, cols):
            p = pool[i]
            if w[i, j] > 0:   # oynayan ya da zaten orada duran (hareket gerekmez)
                target[p["id"]] = free_slots[j]
    for p in pool:
        target.setdefault(p["id"], lw.SLOT_BENCH)

    moves, warnings = [], []
    for p in players:
        p["target"] = target[p["id"]]
        p["target_name"] = SLOT_NAMES.get(p["target"], str(p["target"]))
        p["slot_name"] = SLOT_NAMES.get(p["slot"], str(p["slot"]))
        p["eligible"] = sorted(p["eligible"])
        if p["target"] != p["slot"]:
            moves.append({"playerId": p["id"], "type": "LINEUP", "fromLineupSlotId": p["slot"],
                          "toLineupSlotId": p["target"]})
    starting = lambda key: [p for p in players if p[key] not in (lw.SLOT_BENCH, lw.SLOT_IR)]
    now_active = sum(1 for p in starting("slot") if p["plays"])
    best_active = sum(1 for p in starting("target") if p["plays"])
    # Uyarilar: yapilacak bir sey varsa o, yoksa tek satir ozet
    benched = [p for p in players if p["slot"] == lw.SLOT_BENCH and p["target"] not in (lw.SLOT_BENCH, lw.SLOT_IR)]
    sitting = [p for p in players if p["slot"] not in (lw.SLOT_BENCH, lw.SLOT_IR) and p["target"] == lw.SLOT_BENCH]
    for p in benched:
        warnings.append(f"Start {p['name']} ({p['opp']}).")
    for p in sitting:
        why = ("no game today" if not p["game"] else p["injury"].replace("_", " ").lower() if p["injury"] in SKIP
               else "your other players with games project more")
        warnings.append(f"Bench {p['name']} ({why}).")
    idle = [p for p in starting("target") if not p["plays"]]
    if idle and not benched:
        warnings.append(f"{len(idle)} starting spot{'s' if len(idle) != 1 else ''} without a game today - "
                        "no one on your bench plays either." if len(idle) > 1 else
                        f"{idle[0]['name']} has no game today and no bench player can replace him.")
    for p in starting("target"):
        if p["game"] and p["injury"] in ("DAY_TO_DAY", "QUESTIONABLE", "DOUBTFUL"):
            warnings.append(f"{p['name']} is {p['injury'].replace('_', ' ').lower()} - check before tip-off.")
    players.sort(key=lambda p: (p["target"] in (lw.SLOT_BENCH, lw.SLOT_IR), p["target"] == lw.SLOT_IR,
                                slots.index(p["target"]) if p["target"] in slots else 99, -p["value"]))
    day = datetime.now(EASTERN).date()
    return {"sp": sp, "date": f"{day:%A, %B} {day.day}", "players": players, "moves": moves, "warnings": warnings,
            "active_now": now_active, "active_best": best_active, "playing": sum(1 for p in players if p["plays"]),
            "starters": len(slots), "team_name": lw._team_name(team)}


def apply(league_id, season, team_id, espn_s2, swid):
    """Oneriyi ESPN'e uygular. (ok, mesaj, uygulanan hareket sayisi)"""
    p = plan(league_id, season, team_id)
    if not p:
        return False, "Team not found.", 0
    if not p["moves"]:
        return True, "Your lineup is already optimal.", 0
    swid = swid if swid.startswith("{") else "{" + swid + "}"
    body = {"isLeagueManager": False, "teamId": int(team_id), "type": "ROSTER", "memberId": swid,
            "scoringPeriodId": p["sp"], "executionType": "EXECUTE", "items": p["moves"]}
    r = requests.post(WRITE_URL.format(season=season, league_id=int(league_id)), json=body, timeout=20,
                      cookies={"espn_s2": espn_s2, "SWID": swid}, headers={"Accept": "application/json"})
    if r.status_code in (200, 201):
        return True, f"Lineup set on ESPN: {len(p['moves'])} move{'s' if len(p['moves']) != 1 else ''}.", len(p["moves"])
    try:
        detail = (r.json().get("messages") or [r.json().get("details")])[0]
    except Exception:
        detail = r.text[:200]
    if r.status_code in (401, 403):
        return False, "ESPN rejected the login cookies - refresh espn_s2 / SWID.", 0
    return False, f"ESPN said no ({r.status_code}): {detail}", 0

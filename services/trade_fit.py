"""
Trade Fit (yonetici): bir takasin KENDI takimima etkisi, kendi ligimde.

Takim gucu: onumuzdeki 3 haftanin NBA takvimi, IR disi kadro, her gun en
iyi N oyuncu (N = ligin baslangic yeri), ESPN projeksiyonu + son 15 gun
(services/league_week.team_week). Her takim ligdeki herkese karsi
eslestirilir; "haftalik beklenen kategori galibiyeti" = rakiplere karsi
ortalama. Takas once/sonra hem benim hem karsi takim icin hesaplanir.
"""
from datetime import datetime

from services import league_week as lw
from services.espn_league import _team_name
from services.league_insights import league_data


def _season(league_id):
    _, season, _ = league_data(int(league_id))
    return season


def rosters(league_id):
    season = _season(league_id)
    data = lw.league_raw(int(league_id), season)
    out = []
    for t in data.get("teams") or []:
        players = []
        for e in (t.get("roster") or {}).get("entries") or []:
            pl = (e.get("playerPoolEntry") or {}).get("player") or {}
            s = lw._proj(pl, season)
            players.append({"id": pl.get("id"), "name": pl.get("fullName"), "slot": e.get("lineupSlotId"),
                            "injury": pl.get("injuryStatus") or "ACTIVE", "value": round(lw._value(s), 1),
                            "pts": round(s["PTS"], 1), "reb": round(s["REB"], 1), "ast": round(s["AST"], 1)})
        players.sort(key=lambda p: -p["value"])
        out.append({"id": t["id"], "name": _team_name(t), "players": players})
    return {"season": season, "teams": out}


def _sps(season, n_weeks=3):
    games, first = lw.pro_schedule(int(season))
    wk, start_day = lw.weeks(int(season), first)
    today = datetime.now(lw.LONDON).date()
    weeks_ahead = [w for w in sorted(wk) if wk[w][1] >= today][:n_weeks]
    sps = []
    for w in weeks_ahead:
        s, e = wk[w]
        s = max(s, today)
        sps += list(range((s - start_day).days + 1, (e - start_day).days + 2))
    return games, sps


def evaluate(league_id, my_team, partner, send, get):
    season = _season(league_id)
    data = lw.league_raw(int(league_id), season)
    settings = data.get("settings") or {}
    cats = [lw.CAT_BY_ID[i["statId"]] for i in (settings.get("scoringSettings") or {}).get("scoringItems") or []
            if i.get("statId") in lw.CAT_BY_ID]
    cats = [c for c in lw.ORDER if c in cats] or lw.ORDER
    slots = (settings.get("rosterSettings") or {}).get("lineupSlotCounts") or {}
    starters = sum(int(n) for k, n in slots.items() if int(k) not in (lw.SLOT_BENCH, lw.SLOT_IR)) or 10
    games, sps = _sps(season)
    teams = {t["id"]: t for t in data.get("teams") or []}
    my_team, partner = int(my_team), int(partner) if partner else None
    send, get = {int(x) for x in send}, {int(x) for x in get}

    def entries(t):
        return (t.get("roster") or {}).get("entries") or []

    def pid(e):
        return ((e.get("playerPoolEntry") or {}).get("player") or {}).get("id")

    after = {tid: dict(t) for tid, t in teams.items()}
    mine = [e for e in entries(teams[my_team]) if pid(e) not in send]
    moved_in = [dict(e, lineupSlotId=lw.SLOT_BENCH) for e in entries(teams[partner])] if partner else []
    mine += [e for e in moved_in if pid(e) in get]
    after[my_team] = dict(teams[my_team], roster={"entries": mine})
    if partner:
        theirs = [e for e in entries(teams[partner]) if pid(e) not in get]
        theirs += [dict(e, lineupSlotId=lw.SLOT_BENCH) for e in entries(teams[my_team]) if pid(e) in send]
        after[partner] = dict(teams[partner], roster={"entries": theirs})

    def strength(state):
        weeks = {tid: lw.team_week(t, sps, games, starters, season) for tid, t in state.items()}
        return weeks

    def expected_vs_league(weeks, tid):
        tot, per_cat = 0.0, {c: 0.0 for c in cats}
        opps = [o for o in weeks if o != tid]
        for o in opps:
            rows, e, _, _, _ = lw.compare(weeks[tid], weeks[o], cats)
            tot += e
            for r in rows:
                per_cat[r["cat"]] += r["pa"]
        n = max(1, len(opps))
        return tot / n, {c: v / n for c, v in per_cat.items()}

    def ranks(weeks, tid):
        out = {}
        for c in cats:
            def val(w):
                t = w[0]
                if c in ("FG%", "FT%"):
                    m, a = ("FGM", "FGA") if c == "FG%" else ("FTM", "FTA")
                    return t[m] / t[a] if t[a] else 0
                return -t[c] if c == "TO" else t[c]
            order = sorted(weeks, key=lambda x: -val(weeks[x]))
            out[c] = order.index(tid) + 1
        return out

    before_w, after_w = strength(teams), strength(after)
    res = {"cats": cats, "teams": len(teams), "weeks_counted": len(sps)}
    for key, tid in (("me", my_team), ("partner", partner)):
        if tid is None:
            continue
        b, bc = expected_vs_league(before_w, tid)
        a, ac = expected_vs_league(after_w, tid)
        rb, ra = ranks(before_w, tid), ranks(after_w, tid)
        res[key] = {"name": _team_name(teams[tid]), "before": round(b, 2), "after": round(a, 2), "delta": round(a - b, 2),
                    "cats": [{"cat": c, "before": round(100 * bc[c]), "after": round(100 * ac[c]),
                              "rank_before": rb[c], "rank_after": ra[c]} for c in cats]}
    me = res["me"]
    d = me["delta"]
    res["verdict"] = ("Clearly helps your team" if d >= 0.35 else "Helps a little" if d >= 0.1 else
                      "Basically neutral" if d > -0.1 else "Hurts a little" if d > -0.35 else "Hurts your team")
    up = [c["cat"] for c in me["cats"] if c["after"] - c["before"] >= 5]
    down = [c["cat"] for c in me["cats"] if c["before"] - c["after"] >= 5]
    notes = [f"Against the rest of the league you win {me['before']:.1f} categories a week now and "
             f"{me['after']:.1f} after the trade ({'+' if d >= 0 else ''}{d:.2f})."]
    if up:
        notes.append("Better in: " + ", ".join(up) + ".")
    if down:
        notes.append("Worse in: " + ", ".join(down) + ".")
    if "partner" in res:
        pdlt = res["partner"]["delta"]
        notes.append(f"{res['partner']['name']} goes {'+' if pdlt >= 0 else ''}{pdlt:.2f} a week - "
                     + ("neither team changes much." if abs(pdlt) < 0.1 and abs(d) < 0.1 else
                        "they gain more than you; expect them to say yes." if pdlt > d + 0.15 else
                        "you gain more than they do; they may push back." if d > pdlt + 0.15 else
                        "both sides gain about the same - a sellable deal."))
    extra = len(get) - len(send)
    if extra > 0:
        notes.append(f"You take on {extra} more player{'s' if extra > 1 else ''} than you send - you will have to drop "
                     "someone. The numbers assume your worst players sit on the bench.")
    elif extra < 0:
        notes.append(f"You open {-extra} roster spot{'s' if extra < -1 else ''} - add a free agent and the trade gets better than shown.")
    res["notes"] = notes
    return res

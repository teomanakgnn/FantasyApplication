"""
Canli draft asistani (yonetici): ESPN ligindeki draft surerken her an
siradaki secim icin oneri verir.

ESPN mDraftDetail: tum secim sirasi (takim, tur) ve yapilan secimler
(playerId > 0). Oneri: draft siralamasindaki 9 kategori degeri (kadroya
gore duzeltilmis) + mevki ihtiyaci + en zayif kategorilere katki; ayrica
oyuncunun bir sonraki secimime kadar kalma ihtimali (ADP dagilimi).
"""
import requests

from services.cache import cache_data
from services.espn_league import BASE, _cookies
from services.nba_season import get_current_season_year
from services.strategy_engine import (NINE_CAT, category_scores, draftable_depth, survival,
                                      total_value)

CAT_LABEL = {"FG%": "FG%", "FT%": "FT%", "3Pts": "3PM", "PTS": "PTS", "REB": "REB", "AST": "AST",
             "STL": "STL", "BLK": "BLK", "TO": "TO"}


def _draft(league_id):
    url = BASE.format(season=get_current_season_year(), league_id=int(league_id))
    r = requests.get(url, params=[("view", "mDraftDetail"), ("view", "mTeam"), ("view", "mSettings")],
                     cookies=_cookies(), timeout=15)
    r.raise_for_status()
    return r.json()


@cache_data(ttl=1800, show_spinner=False, copy_result=False)
def _scores(teams, rounds):
    from services.draft_data import get_draft_board
    board = get_draft_board()
    sc = category_scores(board, draftable_depth(teams, rounds))
    # Sakatlik riski fiyatlanmis deger (Draft Strategy ile ayni): cok mac
    # kacirmasi beklenen oyuncu geriye duser.
    from services.strategy_engine import availability_weighted, replacement_level
    sc = availability_weighted(sc, replacement_level(sc, teams, rounds))
    sc = sc.assign(VALUE=total_value(sc), ESPN_ID=board.set_index("PLAYER").reindex(sc["PLAYER"])["ESPN_ID"].values)
    return sc


def _group(positions):
    pos = set(positions or [])
    out = set()
    if pos & {"PG", "SG", "G"}:
        out.add("G")
    if pos & {"SF", "PF", "F"}:
        out.add("F")
    if "C" in pos:
        out.add("C")
    return out


@cache_data(ttl=600, show_spinner=False, copy_result=False)
def _draft_cached(league_id):
    return _draft(league_id)


def pool(league_id):
    """Elle giris icin oyuncu listesi (otomatik tamamlama)."""
    d = _draft_cached(league_id)
    teams = len(d.get("teams") or []) or 12
    rounds = max(1, len(d["draftDetail"]["picks"]) // teams)
    sc = _scores(teams, rounds)
    out = []
    for _, r in sc.sort_values("ADP").iterrows():
        if r["ESPN_ID"] == r["ESPN_ID"]:
            out.append({"id": str(int(r["ESPN_ID"])), "name": r["PLAYER"], "team": r["TEAM"], "pos": "/".join(r["POSITIONS"])})
    return out


def state(league_id, my_team, manual=None):
    """
    manual: elle girilen secimler (oyuncu kimlikleri, secim sirasiyla).
    ESPN canli draft sirasinda secimleri API'de yayinlamiyor; o zaman
    sira ESPN'in secim tablosundan, oyuncular kullanicidan gelir.
    """
    d = _draft_cached(league_id) if manual is not None else _draft(league_id)
    if manual is not None:
        order = sorted(d["draftDetail"]["picks"], key=lambda p: p["overallPickNumber"])
        for i, p in enumerate(order):
            p["playerId"] = int(manual[i]) if i < len(manual) else -1
        d = dict(d, draftDetail=dict(d["draftDetail"], picks=order))
    teams = {t["id"]: (t.get("name") or t.get("abbrev") or f"Team {t['id']}") for t in d.get("teams", [])}
    picks = sorted(d["draftDetail"]["picks"], key=lambda p: p["overallPickNumber"])
    total, nteams = len(picks), len(teams) or 12
    rounds = max(1, total // nteams)
    sc = _scores(nteams, rounds)
    by_id = {str(int(x)): i for i, x in sc["ESPN_ID"].items() if x == x}

    made = [p for p in picks if p.get("playerId", -1) > 0]
    taken = {str(p["playerId"]) for p in made}
    nxt = next((p for p in picks if p.get("playerId", -1) <= 0), None)
    my_open = [p["overallPickNumber"] for p in picks if p.get("playerId", -1) <= 0 and str(p["teamId"]) == str(my_team)]

    def row(pid):
        i = by_id.get(str(pid))
        return sc.loc[i] if i is not None else None

    mine = [p for p in made if str(p["teamId"]) == str(my_team)]
    my_rows = [row(p["playerId"]) for p in mine]
    my_rows = [r for r in my_rows if r is not None]
    # Kategori profili ve mevki sayilari
    profile = {c: float(sum(r[c] for r in my_rows)) for c in NINE_CAT}
    weak = sorted(NINE_CAT, key=lambda c: profile[c])[:3] if my_rows else []
    counts = {"G": 0, "F": 0, "C": 0}
    for r in my_rows:
        for g in _group(r["POSITIONS"]):
            counts[g] += 1

    avail = sc[~sc["ESPN_ID"].astype("Int64").astype(str).isin(taken)].copy()
    first, second = (my_open + [None, None])[:2]
    on_me = first is not None and nxt is not None and nxt["overallPickNumber"] == first
    after = second
    avail["NEXT_ODDS"] = survival(avail["ADP"].values, after) if after else 0.0
    need = {g for g, n in counts.items() if n < {"G": 4, "F": 4, "C": 2}[g] - (0 if len(my_rows) > 5 else 2)}
    def fit(r):
        bonus = 0.6 if _group(r["POSITIONS"]) & need else 0.0
        bonus += 0.25 * sum(max(0.0, r[c]) for c in weak)
        return r["VALUE"] + bonus
    avail["FIT"] = avail.apply(fit, axis=1)
    # Bir sonraki secimime kalacak oyuncu simdi alinmaz: kalma ihtimali yuksekse hafif ceza
    avail["SCORE"] = avail["FIT"] - 0.8 * avail["NEXT_ODDS"]
    # Sira bende degilse: benim secimime kadar kalma ihtimali dusuk olanlar asagi
    if first and not on_me:
        avail["NOW_ODDS"] = survival(avail["ADP"].values, first)
        avail["SCORE"] = avail["SCORE"] - 20.0 * (avail["NOW_ODDS"] < 0.3)
    else:
        avail["NOW_ODDS"] = 1.0
    top = avail.sort_values("SCORE", ascending=False).head(12)

    def reason(r):
        strong = sorted(NINE_CAT, key=lambda c: -r[c])[:3]
        bits = ["+" + "/".join(CAT_LABEL[c] for c in strong)]
        helps = [CAT_LABEL[c] for c in weak if r[c] > 0.4]
        if helps:
            bits.append("fixes " + ", ".join(helps))
        if _group(r["POSITIONS"]) & need:
            bits.append("fills " + "/".join(sorted(_group(r["POSITIONS"]) & need)))
        if after:
            odds = float(r["NEXT_ODDS"])
            bits.append("likely gone" if odds < .3 else f"{int(odds * 100)}% to last to #{after}")
        return " · ".join(bits)

    recs = [{"id": str(int(r["ESPN_ID"])) if r["ESPN_ID"] == r["ESPN_ID"] else "", "name": r["PLAYER"],
             "team": r["TEAM"], "pos": "/".join(r["POSITIONS"]), "adp": round(float(r["ADP"]), 1) if r["ADP"] < 999 else None,
             "value": round(float(r["VALUE"]), 2), "injury": r["INJURY"], "next_odds": round(float(r["NEXT_ODDS"]), 2),
             "now_odds": round(float(r["NOW_ODDS"]), 2), "reason": reason(r)} for _, r in top.iterrows()]

    def named(p):
        r = row(p["playerId"])
        return {"pick": p["overallPickNumber"], "round": p["roundId"], "team": teams.get(p["teamId"], p["teamId"]),
                "player": r["PLAYER"] if r is not None else f"#{p['playerId']}", "mine": str(p["teamId"]) == str(my_team)}

    return {
        "league": (d.get("settings") or {}).get("name"), "my_team": teams.get(int(my_team)) if str(my_team).isdigit() else my_team,
        "in_progress": d["draftDetail"].get("inProgress"), "done": d["draftDetail"].get("drafted"),
        "pick": nxt["overallPickNumber"] if nxt else None, "total": total,
        "on_clock": teams.get(nxt["teamId"]) if nxt else None, "on_me": on_me,
        "my_next": first, "my_after": after, "until_me": (first - nxt["overallPickNumber"]) if (first and nxt) else None,
        "recent": [named(p) for p in made[-10:]][::-1],
        "mine": [named(p) for p in mine],
        "weak": [CAT_LABEL[c] for c in weak], "counts": counts,
        "recs": recs,
    }

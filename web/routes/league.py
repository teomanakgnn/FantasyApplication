"""
My League: ESPN veya Yahoo liginin puan durumu, eslesmeler, herkes-herkese
(H2H) guc siralamasi ve roto simulasyonu.

Yahoo oturumu tarayici basina sunucu belleginde tutulur. Eski surum
Yahoo anahtarini herkesin paylastigi tek bir dosyaya (yahoo_token.json)
yaziyordu; bir kullanicinin Yahoo hesabi digerlerine acik kalabiliyordu.
"""
import secrets
import time

import pandas as pd
from fastapi import APIRouter, Form, Request

import config
from web.core import redirect, render

router = APIRouter()

CATS = ["FG%", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK", "TO"]
LABELS = {"3PTM": "3PM", "ST": "STL", "TO": "TOV"}
YAHOO_COOKIE = "hl_yahoo"
_YAHOO = {}   # cerez -> {"service", "touched", "leagues"}


def _num(value):
    try:
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace("%", "")
        return 0.0 if text in ("", "--") else float(text)
    except (TypeError, ValueError):
        return 0.0


def _compare(a, b):
    w = l = t = 0
    for cat in CATS:
        x, y = _num(a.get(cat, 0)), _num(b.get(cat, 0))
        if cat == "TO":
            x, y = -x, -y
        if x > y:
            w += 1
        elif x < y:
            l += 1
        else:
            t += 1
    return w, l, t


def power_rank(matchups):
    pool = []
    for m in matchups:
        for side in ("home_team", "away_team"):
            pool.append({"name": m[side]["name"], "stats": m[side].get("stats", {})})
    results = []
    for a in pool:
        wins = losses = ties = 0
        details = []
        for b in pool:
            if a["name"] == b["name"]:
                continue
            w, l, t = _compare(a["stats"], b["stats"])
            wins, losses, ties = wins + w, losses + l, ties + t
            details.append({"opponent": b["name"], "record": f"{w}-{l}-{t}",
                            "result": "WIN" if w > l else "LOSS" if l > w else "TIE"})
        total = wins + losses + ties
        results.append({"team": a["name"], "wins": wins, "losses": losses,
                        "pct": wins / total if total else 0, "details": details,
                        "beaten": sum(d["result"] == "WIN" for d in details)})
    results.sort(key=lambda r: (-r["wins"], -r["pct"]))
    return results


def roto(matchups):
    rows = []
    for m in matchups:
        for side in ("home_team", "away_team"):
            stats = m[side].get("stats", {})
            rows.append({"Team": m[side]["name"], **{c: _num(stats.get(c, 0)) for c in CATS}})
    if not rows:
        return [], []
    df = pd.DataFrame(rows)
    points = df[["Team"]].copy()
    for cat in CATS:
        points[cat] = df[cat].rank(ascending=(cat != "TO"), method="min")
    points["Total"] = points[CATS].sum(axis=1)
    points = points.sort_values("Total", ascending=False)
    raw = df.set_index("Team").loc[points["Team"]].reset_index()
    return raw.to_dict("records"), points.to_dict("records")


# ==================== YAHOO ====================

def _yahoo_entry(request, create=False):
    key = request.cookies.get(YAHOO_COOKIE)
    entry = _YAHOO.get(key) if key else None
    if entry:
        entry["touched"] = time.time()
        return key, entry
    if not create:
        return None, None
    from services.yahoo_api import YahooFantasyService
    key = secrets.token_urlsafe(18)
    entry = {"service": YahooFantasyService(config.YAHOO_CLIENT_ID, config.YAHOO_CLIENT_SECRET),
             "touched": time.time(), "authed": False, "leagues": []}
    stale = [k for k, v in _YAHOO.items() if time.time() - v["touched"] > 12 * 3600]
    for k in stale:
        _YAHOO.pop(k, None)
    _YAHOO[key] = entry
    return key, entry


def _yahoo_ready():
    return bool(config.YAHOO_CLIENT_ID and config.YAHOO_CLIENT_SECRET)


@router.get("/league/yahoo/connect")
def yahoo_connect(request: Request):
    if not _yahoo_ready():
        return redirect("/league?platform=yahoo", "Yahoo is not configured on this server.", "error")
    key, entry = _yahoo_entry(request, create=True)
    url = entry["service"].get_authorization_url()
    response = redirect(url)
    response.set_cookie(YAHOO_COOKIE, key, max_age=12 * 3600, httponly=True,
                        secure=config.PRODUCTION, samesite="lax", path="/")
    return response


@router.post("/league/yahoo/code")
def yahoo_code(request: Request, code: str = Form("")):
    key, entry = _yahoo_entry(request)
    if not entry:
        return redirect("/league?platform=yahoo", "Start the Yahoo connection again.", "error")
    try:
        entry["service"].fetch_token(code.strip())
        entry["authed"] = True
        entry["leagues"] = entry["service"].get_user_leagues("nba")
    except Exception as exc:
        print(f"yahoo auth failed: {exc}")
        return redirect("/league?platform=yahoo", "Yahoo did not accept that code. Try again.", "error")
    return redirect("/league?platform=yahoo", "Connected to Yahoo.")


@router.post("/league/yahoo/disconnect")
def yahoo_disconnect(request: Request):
    key = request.cookies.get(YAHOO_COOKIE)
    _YAHOO.pop(key, None)
    response = redirect("/league?platform=yahoo", "Yahoo disconnected.")
    response.delete_cookie(YAHOO_COOKIE, path="/")
    return response


@router.post("/league/yahoo/rosters")
def yahoo_rosters(request: Request, league_key: str = Form("")):
    _, entry = _yahoo_entry(request)
    if not entry or not entry.get("authed"):
        return redirect("/league?platform=yahoo", "Connect Yahoo first.", "error")
    try:
        entry.setdefault("rosters", {})[league_key] = entry["service"].get_league_rosters(league_key)
    except Exception as exc:
        print(f"yahoo rosters failed: {exc}")
        return redirect(f"/league?platform=yahoo&league_key={league_key}#trade",
                        "Yahoo could not load the rosters. Try again.", "error")
    return redirect(f"/league?platform=yahoo&league_key={league_key}#trade", "Rosters loaded.")


def yahoo_trade(entry, league_key, q):
    """Yahoo liginde iki takim arasi takasin kategori etkisi (eski sayfadaki hesap)."""
    rosters = (entry.get("rosters") or {}).get(league_key)
    if not rosters:
        return None
    names = list(rosters)
    team_a = q.get("team_a") if q.get("team_a") in rosters else names[0]
    others = [n for n in names if n != team_a]
    team_b = q.get("team_b") if q.get("team_b") in others else (others[0] if others else team_a)
    give = [k for k in q.getlist("give") if any(p["player_key"] == k for p in rosters[team_a]["players"])]
    get = [k for k in q.getlist("get") if any(p["player_key"] == k for p in rosters[team_b]["players"])]
    result = {"teams": names, "team_a": team_a, "team_b": team_b,
              "players_a": rosters[team_a]["players"], "players_b": rosters[team_b]["players"],
              "give": give, "get": get, "impact": None, "error": None}
    if give or get:
        try:
            stats = entry["service"].get_players_stats(league_key, give + get)
        except Exception as exc:
            print(f"yahoo player stats failed: {exc}")
            stats = []
        if not stats:
            result["error"] = "Yahoo did not return stats for those players."
            return result
        key_of = {p["name"]: p["player_key"] for p in rosters[team_a]["players"] + rosters[team_b]["players"]}
        out_side = [p for p in stats if key_of.get(p["name"]) in give]
        in_side = [p for p in stats if key_of.get(p["name"]) in get]

        def total(side, cat):
            values = [_num(p["stats"].get(cat, 0)) for p in side]
            if not values:
                return 0.0
            return sum(values) / len(values) if "%" in cat else sum(values)
        result["impact"] = [{"cat": c, "label": LABELS.get(c, c),
                             "delta": total(in_side, c) - total(out_side, c)} for c in CATS]
        result["out_side"], result["in_side"] = out_side, in_side
    return result


# ==================== SAYFA ====================

def _parse_league_id(value):
    value = (value or "").strip()
    if "leagueId=" in value:
        value = value.split("leagueId=")[1].split("&")[0]
    return value if value.isdigit() else None


@router.get("/league")
def league(request: Request):
    q = request.query_params
    platform = q.get("platform")
    context = {"platform": platform, "error": None, "standings": None, "matchups": None,
               "cats": CATS, "labels": LABELS, "yahoo_ready": _yahoo_ready()}
    try:
        week = int(q.get("week") or 0)
    except ValueError:
        week = 0
    context["week"] = week

    if platform == "espn":
        raw_id = q.get("league_id", "")
        context["league_input"] = raw_id
        league_id = _parse_league_id(raw_id)
        if raw_id and not league_id:
            context["error"] = "Enter the numeric league ID (or paste the league URL)."
        elif league_id:
            from services.espn_league import (LeagueError, get_league_matchups,
                                              get_league_standings)
            try:
                standings = get_league_standings(int(league_id))
                matchups = get_league_matchups(int(league_id), matchup_period=week or None)
                context.update(standings=standings.to_dict("records") if not standings.empty else [],
                               matchups=matchups)
                # Herkese acik ESPN ligi: link ligdeki herkes icin calisiyor
                context["share_url"] = (f"{config.SITE_URL.rstrip('/')}/league?platform=espn"
                                        f"&league_id={league_id}&ref=league-share")
            except LeagueError as exc:
                context["error"] = str(exc)
            except Exception as exc:
                print(f"espn league failed: {exc}")
                context["error"] = "That league could not be read. Check the ID and try again."

    elif platform == "yahoo":
        _, entry = _yahoo_entry(request)
        context["yahoo"] = entry
        league_key = q.get("league_key", "")
        context["league_key"] = league_key
        if entry and entry.get("authed") and league_key:
            try:
                standings = entry["service"].get_league_standings(league_key)
                matchups = entry["service"].get_league_matchups(league_key, week or None)
                context.update(standings=standings.to_dict("records") if standings is not None and not standings.empty else [],
                               matchups=matchups)
            except Exception as exc:
                print(f"yahoo league failed: {exc}")
                context["error"] = "Yahoo could not load that league. Reconnect and try again."
            context["trade"] = yahoo_trade(entry, league_key, q)

    if context["matchups"]:
        context["power"] = power_rank(context["matchups"])
        context["roto_raw"], context["roto_points"] = roto(context["matchups"])
    return render(request, "league.html", active="league", **context)

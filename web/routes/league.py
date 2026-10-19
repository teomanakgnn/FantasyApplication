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
from services.database import db
from web.core import current_user, login_required, redirect, render

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


# ==================== CANLI DRAFT ASISTANI (yonetici) ====================

def _is_admin(request):
    u = current_user(request)
    return bool(u and u.get("username") in config.ADMIN_USERNAMES)


@router.get("/admin/draft")
def draft_assist_page(request: Request, league: str = "", team: str = ""):
    gate = login_required(request)
    if gate:
        return gate
    if not _is_admin(request):
        return redirect("/", "Not available.", "error")
    leagues = [r for r in db.list_leagues(current_user(request)["id"]) if r["platform"] == "espn"]
    return render(request, "draft_assist.html", active="league", leagues=leagues, league=league, team=team,
                  feed_url=f"{config.SITE_URL.rstrip('/')}/api/draft-feed/{_feed_token()}")


# ESPN draft odasindaki yer iminden gelen canli secimler: {league: {"ids": [...], "ts": ...}}
_FEED = {}


def _feed_token():
    import hashlib
    import hmac
    return hmac.new(config.SECRET_KEY.encode(), b"draft-feed", hashlib.sha256).hexdigest()[:24]


@router.post("/api/draft-feed/{token}")
async def draft_feed(request: Request, token: str):
    """
    ESPN canli draft secimlerini API'de yayinlamiyor; kullanicinin draft
    odasi sekmesindeki yer imi her birkac saniyede secimleri buraya yollar.
    Cerez yok (baska site), gizli anahtarla korunur.
    """
    from fastapi.responses import JSONResponse
    cors = {"Access-Control-Allow-Origin": "*"}
    if token != _feed_token():
        return JSONResponse({"error": "bad token"}, 403, headers=cors)
    import json as _json
    try:
        body = _json.loads((await request.body()).decode("utf-8") or "{}")
    except ValueError:
        return JSONResponse({"error": "bad body"}, 400, headers=cors)
    league = str(body.get("league") or "")
    ids = [str(x) for x in body.get("ids") or [] if str(x).isdigit()]
    names = body.get("names")
    if not ids and body.get("names"):
        from services.draft_assist import pool
        from services.daily_player import norm as _n
        by_name = {_n(p["name"]): p["id"] for p in pool(int(league))}
        # Listede bulunamayan isim atlanmaz: yerini tutar, yoksa sonraki tum
        # secimler bir sira kayar ve takimlar yanlis hesaplanir.
        ids = [by_name.get(_n(n)) or ("?" + n[:60]) for n in body["names"]]
        missing = [i[1:] for i in ids if i.startswith("?")]
        if missing:
            print("draft feed unmatched:", missing[:10])
    prev = _FEED.get(league, {}).get("ids", [])
    if body.get("names") is not None:
        n = body.get("names") or []
        print(f"draft feed names: {len(n)} first={n[:4]} last={n[-4:]}")
    _FEED[league] = {"ids": ids if len(ids) >= len(prev) or body.get("ids") else prev, "ts": time.time(),
                     "source": "api" if body.get("ids") else "page", "seen": len(body.get("names") or ids)}
    return JSONResponse({"ok": True, "picks": len(_FEED[league]["ids"])}, headers=cors)


@router.post("/api/admin/draft")
async def draft_assist_manual(request: Request):
    """Elle girilen secimlerle oneri (ESPN canli secimleri yayinlamiyor)."""
    from fastapi.responses import JSONResponse
    if not _is_admin(request):
        return JSONResponse({"error": "Not available."}, 403)
    body = await request.json()
    try:
        from services.draft_assist import pool, state
        feed = _FEED.get(str(body.get("league")))
        live = feed and time.time() - feed["ts"] < 30
        taken = feed["ids"] if live else [str(x) for x in body.get("taken") or []]
        out = state(int(body.get("league")), str(body.get("team")), manual=taken)
        out["feed"] = {"live": bool(live), "picks": len(taken), "source": feed and feed.get("source"),
                       "age": round(time.time() - feed["ts"]) if feed else None}
        out["taken"] = taken
        if body.get("with_pool"):
            out["pool"] = pool(int(body.get("league")))
        return out
    except Exception as exc:
        print(f"draft assist failed: {exc}")
        return JSONResponse({"error": f"Could not build advice: {exc}"[:200]}, 502)


@router.get("/api/admin/draft")
def draft_assist_api(request: Request, league: str = "", team: str = ""):
    from fastapi.responses import JSONResponse
    if not _is_admin(request):
        return JSONResponse({"error": "Not available."}, 403)
    try:
        from services.draft_assist import state
        return state(int(league), team)
    except Exception as exc:
        print(f"draft assist failed: {exc}")
        return JSONResponse({"error": f"Could not read the draft: {exc}"[:200]}, 502)


# ==================== TRADE FIT (yonetici) ====================

@router.get("/admin/trade-fit")
def trade_fit_page(request: Request):
    gate = login_required(request)
    if gate:
        return gate
    if not _is_admin(request):
        return redirect("/", "Not available.", "error")
    leagues = [r for r in db.list_leagues(current_user(request)["id"]) if r["platform"] == "espn" and r["team_id"]]
    return render(request, "trade_fit.html", active="league", leagues=leagues)


@router.get("/api/admin/trade-fit/rosters")
def trade_fit_rosters(request: Request, league: str = ""):
    from fastapi.responses import JSONResponse
    if not _is_admin(request):
        return JSONResponse({"error": "Not available."}, 403)
    try:
        from services.trade_fit import rosters
        return rosters(int(league))
    except Exception as exc:
        return JSONResponse({"error": f"Could not read the league: {exc}"[:200]}, 502)


@router.post("/api/admin/trade-fit")
async def trade_fit_eval(request: Request):
    from fastapi.responses import JSONResponse
    if not _is_admin(request):
        return JSONResponse({"error": "Not available."}, 403)
    b = await request.json()
    try:
        from services.trade_fit import evaluate
        return evaluate(int(b["league"]), int(b["team"]), b.get("partner"), b.get("send") or [], b.get("get") or [])
    except Exception as exc:
        print(f"trade fit failed: {exc}")
        return JSONResponse({"error": f"Could not evaluate: {exc}"[:200]}, 502)


# ==================== HAFTALIK TAHMIN ====================

def _week_context(user, league_id, season, team):
    from services import league_week as lw
    wk = lw.week(int(league_id), int(season), team or None)
    mine = db.my_predictions(user["id"], league_id, season, wk["week"]) if user and db.available else {}
    for m in wk["matchups"]:
        m["pred"] = mine.get(m["id"])
    return {"wk": wk, "leaderboard": _leaderboard(league_id, season, wk["week"]) if db.available else []}


def _leaderboard(league_id, season, current):
    """Biten haftalarin puanlari: tam skor 3, dogru kazanan (ya da beraberlik) 1."""
    from services import league_week as lw
    rows = db.league_predictions(league_id, season)
    if not rows:
        return []
    board, results = {}, {}
    for r in rows:
        b = board.setdefault(r["user_id"], {"name": r["username"], "points": 0, "exact": 0, "picks": 0, "scored": 0})
        b["picks"] += 1
        if r["period"] not in results:
            try:
                results[r["period"]] = lw.results(int(league_id), int(season), r["period"])
            except Exception:
                results[r["period"]] = {}
        res = results[r["period"]].get(r["matchup_id"])
        if not res:
            continue
        b["scored"] += 1
        if (r["home"], r["away"]) == tuple(res):
            b["points"] += 3
            b["exact"] += 1
        elif (r["home"] > r["away"]) == (res[0] > res[1]) and (r["home"] == r["away"]) == (res[0] == res[1]):
            b["points"] += 1
    return sorted(board.values(), key=lambda b: (-b["points"], -b["exact"], b["name"].lower()))


@router.post("/api/league/predict")
async def predict(request: Request):
    from datetime import datetime
    from fastapi.responses import JSONResponse
    from services import league_week as lw
    user = current_user(request)
    if not user:
        return JSONResponse({"error": "Sign in to make predictions."}, 401)
    body = await request.json()
    try:
        league, season, matchup = str(int(body["league"])), int(body["season"]), int(body["matchup"])
        home, away = int(body["home"]), int(body["away"])
    except (KeyError, TypeError, ValueError):
        return JSONResponse({"error": "Bad prediction."}, 400)
    wk = lw.week(int(league), season)
    if not wk["open"] or datetime.now(lw.LONDON) >= wk["deadline"]:
        return JSONResponse({"error": "Predictions for this week are closed."}, 403)
    if matchup not in {m["id"] for m in wk["matchups"]}:
        return JSONResponse({"error": "That matchup is not this week."}, 400)
    n = wk["n_cats"]
    if not (0 <= home <= n and 0 <= away <= n and home + away <= n):
        return JSONResponse({"error": f"Scores must add up to at most {n} categories."}, 400)
    db.save_prediction(user["id"], league, season, wk["week"], matchup, home, away)
    return {"ok": True}


# ==================== KAYITLI LIGLER ====================

def _summary(row):
    """Pano karti: ESPN liginde takim sirasi, rekor, uyari sayisi, ilk yorum."""
    out = dict(row)
    if row["platform"] != "espn":
        return out
    try:
        from services import league_insights as li
        r = li.build(int(row["league_ref"]), row.get("team_id"))
        me = r.get("me")
        out.update(league_name=r["name"], fallback=r["fallback"], teams=len(r["teams"]),
                   alerts=r.get("alerts") or [], note=(r.get("notes") or [None])[0])
        if me:
            out.update(team_name=me["name"], record=f"{me['wins']}-{me['losses']}", rank=me["rank"],
                       form_rank=me["recent_rank"])
    except Exception as exc:
        out["error"] = str(exc)[:160]
    return out


def _dashboard(request, user):
    import concurrent.futures as cf
    rows = db.list_leagues(user["id"])
    with cf.ThreadPoolExecutor(4) as ex:
        cards = list(ex.map(_summary, rows))
    return render(request, "league_home.html", active="league", cards=cards, yahoo_ready=_yahoo_ready())


@router.get("/league/my/{league_id}")
def my_league(request: Request, league_id: int):
    gate = login_required(request)
    if gate:
        return gate
    row = db.get_league(current_user(request)["id"], league_id)
    if not row:
        return redirect("/league", "That league is not in your list.", "error")
    if row["platform"] == "espn":
        return redirect(f"/league?platform=espn&league_id={row['league_ref']}&team={row['team_id'] or ''}#insights")
    return redirect(f"/league?platform=yahoo&league_key={row['league_ref']}")


@router.post("/league/save")
def save_league(request: Request, platform: str = Form("espn"), league_ref: str = Form(""),
                team_id: str = Form(""), name: str = Form("")):
    user = current_user(request)
    if not user:
        return redirect("/login?next=/league", "Sign in to save your leagues.", "info")
    platform = "yahoo" if platform == "yahoo" else "espn"
    if platform == "espn":
        league_ref = _parse_league_id(league_ref) or ""
    if not league_ref:
        return redirect("/league", "That league ID does not look right.", "error")
    if len(db.list_leagues(user["id"])) >= 12:
        return redirect("/league", "You can keep up to 12 leagues.", "error")
    saved = db.save_league(user["id"], platform, league_ref, team_id or None, name)
    if not saved:
        return redirect("/league", "Could not save the league. Try again.", "error")
    if platform == "espn":
        return redirect(f"/league?platform=espn&league_id={league_ref}&team={team_id}#insights",
                        "League saved. It is now on your My League page.")
    return redirect("/league", "League saved.")


@router.post("/league/{league_id}/delete")
def delete_league(request: Request, league_id: int):
    user = current_user(request)
    if user:
        db.delete_league(user["id"], league_id)
    return redirect("/league", "League removed.")


@router.post("/league/{league_id}/alerts")
def league_alerts(request: Request, league_id: int, on: str = Form("0")):
    user = current_user(request)
    if user:
        db.update_league(user["id"], league_id, email_alerts=on == "1")
    return redirect("/league", "Email alerts " + ("on." if on == "1" else "off."))


@router.get("/league")
def league(request: Request):
    q = request.query_params
    platform = q.get("platform")
    user = current_user(request)
    if not platform and user and db.available and db.list_leagues(user["id"]):
        return _dashboard(request, user)
    context = {"platform": platform, "error": None, "standings": None, "matchups": None,
               "insights": None, "wk": None, "leaderboard": [], "team": "", "saved": None, "league_id": None, "signed_in": bool(user),
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
            from services import league_insights as li
            from services.espn_league import (LeagueError, get_league_matchups,
                                              get_league_standings)
            saved = None
            if user and db.available:
                saved = next((r for r in db.list_leagues(user["id"])
                              if r["platform"] == "espn" and r["league_ref"] == str(league_id)), None)
            team = q.get("team") or (saved or {}).get("team_id") or ""
            context.update(team=str(team), saved=saved, league_id=league_id)
            season = None
            # Once analiz: yeni sezon ligi yenilenmemisse bir onceki sezona duser,
            # puan durumu da ayni sezondan okunur.
            try:
                insights = li.build(int(league_id), team or None)
                context["insights"] = insights
                season = insights["season"]
            except LeagueError as exc:
                context["error"] = str(exc)
            except Exception as exc:
                print(f"league insights failed: {exc}")
            # Bu hafta: beklenen skorlar ve tahminler
            if season:
                try:
                    context.update(_week_context(user, league_id, season, team))
                except Exception as exc:
                    print(f"league week failed: {exc}")
            if not context["error"]:
                try:
                    standings = get_league_standings(int(league_id), season)
                    matchups = get_league_matchups(int(league_id), season, matchup_period=week or None)
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

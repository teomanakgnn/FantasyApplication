"""
Oyunlar: gunluk gizemli oyuncu (Wordle tipi) ve playoff tahmin agaci.

Gizemli oyuncu: cevap tarayiciya gitmez, her tahmini sunucu
karsilastirir (services/daily_player.py). Eski Card Connections oyunu
kaldirildi; eski adresler yeni oyuna yonleniyor.

Playoff agaci eskiden paylasim linkindeki ?bracket= degerini hic
temizlemeden JavaScript koduna yaziyordu: hazirlanmis bir link, acan
kisinin tarayicisinda istenen kodu calistirabiliyordu. Artik sunucu
linke hic dokunmuyor; tarayici degeri JSON olarak okuyup yalnizca
bilinen takim adlarini kabul ediyor ve ekrana metin olarak basiyor.
"""
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from services import daily_player as daily
from services import minigames
from services import eighty_two as e82
from services import starting_five as sf
from services.nba_season import get_current_season_year, get_season_label
from services.win_totals import get_team_identity
from services.database import db
from web.core import current_user, render
from web.routes.over_under import load_lines

router = APIRouter()


# ==================== GIZEMLI OYUNCU ====================

@router.get("/daily")
def daily_page(request: Request):
    players = daily.search_list()
    user = current_user(request)
    payload = json.dumps({
        "puzzle": daily.puzzle_number(),
        "max": daily.MAX_GUESSES,
        "next_in": daily.seconds_to_next(),
        "players": players,
        "signed_in": bool(user),
        "server_stats": db.get_daily_stats(user["id"]) if user and db.available else None,
    }, ensure_ascii=False).replace("</", "<\\/")
    return render(request, "daily.html", active="daily", payload=payload,
                  ready=bool(players), puzzle=daily.puzzle_number())


def _bad(message, status=400):
    return JSONResponse({"error": message}, status_code=status)


def _check_puzzle(body):
    if int(body.get("puzzle") or 0) != daily.puzzle_number():
        return _bad("A new player is up. Reload the page to play today's puzzle.", 409)
    return None


@router.post("/api/daily/guess")
async def daily_guess(request: Request):
    body = await request.json()
    stale = _check_puzzle(body)
    if stale:
        return stale
    answer = daily.answer_for()
    if not answer:
        return _bad("Today's player is not ready yet. Try again in a minute.", 503)
    guess = daily.player_pool().get(str(body.get("player_id") or ""))
    if not guess:
        return _bad("Pick a player from the list.")
    correct = guess["id"] == answer["id"]
    out = {"player": {"id": guess["id"], "name": guess["name"]},
           "cells": daily.compare(guess, answer), "correct": correct}
    if correct:
        out["answer"] = daily.public_answer(answer)
    return out


@router.post("/api/daily/reveal")
async def daily_reveal(request: Request):
    """Haklar bitince cevabi gosterir: 8 farkli, yanlis tahmin gonderilmeli."""
    body = await request.json()
    stale = _check_puzzle(body)
    if stale:
        return stale
    answer = daily.answer_for()
    if not answer:
        return _bad("Today's player is not ready yet.", 503)
    guesses = {str(g) for g in (body.get("guesses") or [])}
    pool = daily.player_pool()
    if len(guesses) < daily.MAX_GUESSES or answer["id"] in guesses or \
            any(g not in pool for g in guesses):
        return _bad("Use all your guesses first.", 403)
    return {"answer": daily.public_answer(answer)}


_STAT_KEYS = ("played", "wins", "streak", "best", "last", "lastWin")


@router.post("/api/daily/stats")
async def daily_stats(request: Request):
    """Giris yapan kullanicinin serisi: her cihazda ayni istatistik."""
    user = current_user(request)
    if not user:
        return _bad("Sign in to keep your streak on every device.", 401)
    body = await request.json()
    try:
        stats = {k: max(0, min(int(body.get(k) or 0), 100000)) for k in _STAT_KEYS}
        dist = [max(0, min(int(x or 0), 100000)) for x in (body.get("dist") or [])][:daily.MAX_GUESSES]
    except (TypeError, ValueError):
        return _bad("Bad stats.")
    stats["dist"] = dist + [0] * (daily.MAX_GUESSES - len(dist))
    db.save_daily_stats(user["id"], stats)
    return {"ok": True}


# ==================== STAT MATCH / TIER LIST ====================

def _json(data):
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


@router.get("/stat-match")
def stat_match(request: Request):
    day = daily.today()
    rounds = minigames.stat_match_rounds(f"statmatch-{day.isoformat()}")
    payload = {"puzzle": minigames.stat_match_number(day), "rounds": rounds,
               "next_in": daily.seconds_to_next(), "signed_in": bool(current_user(request))}
    return render(request, "stat_match.html", active="statmatch", payload=_json(payload),
                  ready=len(rounds) >= 5, puzzle=payload["puzzle"])


@router.get("/api/stat-match/practice")
def stat_match_practice():
    import secrets
    return {"rounds": minigames.stat_match_rounds(secrets.token_hex(8))}


# ==================== PYRAMID ====================

@router.get("/pyramid")
def pyramid_page(request: Request):
    from services import pyramid
    day = daily.today()
    puzzle = pyramid.daily(day)
    payload = {"puzzle": pyramid.puzzle_number(day), "seed": "daily", "next_in": daily.seconds_to_next(),
               "signed_in": bool(current_user(request)), **(pyramid.public(puzzle) if puzzle else {})}
    return render(request, "pyramid.html", active="pyramid", payload=_json(payload), ready=bool(puzzle),
                  puzzle=payload["puzzle"], label=(puzzle or {}).get("label", ""))


@router.get("/api/pyramid/practice")
def pyramid_practice():
    import secrets
    from services import pyramid
    seed = "p-" + secrets.token_hex(8)
    puzzle = pyramid.build(seed)
    if not puzzle:
        return _bad("Could not build a practice pyramid. Try again.")
    return {"seed": seed, **pyramid.public(puzzle)}


@router.post("/api/pyramid/check")
async def pyramid_check(request: Request):
    from services import pyramid
    body = await request.json()
    seed = str(body.get("seed") or "daily")
    puzzle = pyramid.daily() if seed == "daily" else pyramid.build(seed) if seed.startswith("p-") else None
    if not puzzle:
        return _bad("Unknown puzzle.")
    order = [str(x) for x in (body.get("order") or [])]
    if len(order) != pyramid.N or set(order) != {p["id"] for p in puzzle["players"]}:
        return _bad("Place all ten players first.")
    return pyramid.check(puzzle, order)


@router.get("/tier-list")
def tier_list(request: Request):
    players = minigames.tier_players(200)
    return render(request, "tier_list.html", active="tiers", payload=_json({"players": players}),
                  ready=bool(players))


# ==================== 82-0 ====================

@router.get("/82-0")
def eighty_two(request: Request):
    payload = {"puzzle": e82.puzzle_number(), "config": e82.config(),
               "signed_in": bool(current_user(request))}
    return render(request, "eighty_two.html", active="eightytwo", payload=_json(payload),
                  puzzle=payload["puzzle"], ready=True)


@router.get("/api/82-0/game")
def eighty_two_game(span: int = 1, daily_game: int = 1):
    """Gunluk oyun: tarih + donem uzunlugu tohumlu; pratik: rastgele."""
    import secrets
    seed = f"82-0-{daily.today().isoformat()}" if daily_game else secrets.token_hex(8)
    return {"spins": e82.game(seed, span), "span": span if span in e82.SPANS else 1}


# ==================== STARTING FIVE ====================

@router.get("/starting-five")
def starting_five(request: Request):
    game = sf.view(sf.daily_game_id())
    payload = {"puzzle": sf.puzzle_number(), "game": game, "names": sf.names(),
               "next_in": daily.seconds_to_next(), "signed_in": bool(current_user(request))}
    return render(request, "starting_five.html", active="starting5", payload=_json(payload),
                  puzzle=payload["puzzle"], ready=bool(game))


@router.get("/api/starting-five/random")
def starting_five_random():
    return {"game": sf.view(sf.random_game_id())}


@router.post("/api/starting-five/guess")
async def starting_five_guess(request: Request):
    body = await request.json()
    hits = sf.guess(str(body.get("game") or ""), str(body.get("name") or "")[:80])
    if hits is None:
        return _bad("That game is not available.", 404)
    return {"hits": hits}


@router.post("/api/starting-five/reveal")
async def starting_five_reveal(request: Request):
    body = await request.json()
    teams = sf.reveal(str(body.get("game") or ""))
    if teams is None:
        return _bad("That game is not available.", 404)
    return {"teams": teams}


@router.post("/api/streak")
async def streak_api(request: Request):
    """Gunluk oyun bitti: giris yapan kullanicinin serisini sunucuda isle."""
    user = current_user(request)
    if not user:
        return _bad("Sign in to keep streaks on every device.", 401)
    body = await request.json()
    from web.core import _puzzles
    game = str(body.get("game") or "")
    today = _puzzles().get(game)
    if body.get("sync") and today:
        last, streak = int(body.get("last") or 0), int(body.get("streak") or 0)
        if last in (today, today - 1) and 0 < streak <= last:
            db.sync_streak(user["id"], game, last, streak)
        return {"ok": True}
    if not today or int(body.get("puzzle") or 0) != today:
        return _bad("Unknown game or day.")
    return {"streak": db.bump_streak(user["id"], game, today, int(body.get("seed") or 0))}


@router.get("/card-game")
@router.get("/card-game/play")
def old_card_game():
    return RedirectResponse("/daily", status_code=301)


@router.get("/bracket")
def bracket(request: Request):
    """
    Playoff tahmin agaci. Tohumlar sabit gecmis sezon listesi degil:
    iki konferansin Vegas galibiyet baremine gore ilk sekizi.
    """
    season = get_current_season_year()
    identity = get_team_identity()
    rows = load_lines(season)
    east, west = [], []
    for r in sorted(rows, key=lambda r: -r["line"]):
        team = {"name": r["team_name"], "short": identity.get(r["team"], {}).get("short") or r["team_name"],
                "abbr": r["team"]}
        conf = (r.get("conf") or "")
        if conf.startswith("East") and len(east) < 8:
            east.append(team)
        elif conf.startswith("West") and len(west) < 8:
            west.append(team)
    for group in (east, west):
        for seed, team in enumerate(group, start=1):
            team["seed"] = seed
    return render(request, "bracket.html", active="bracket", east=east, west=west,
                  year=season, season=get_season_label(season))

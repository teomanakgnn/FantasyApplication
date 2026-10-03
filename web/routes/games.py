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
from services.nba_season import get_current_season_year, get_season_label
from services.win_totals import get_team_identity
from web.core import render
from web.routes.over_under import load_lines

router = APIRouter()


# ==================== GIZEMLI OYUNCU ====================

@router.get("/daily")
def daily_page(request: Request):
    players = daily.search_list()
    payload = json.dumps({
        "puzzle": daily.puzzle_number(),
        "max": daily.MAX_GUESSES,
        "next_in": daily.seconds_to_next(),
        "players": players,
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

"""
Oyunlar: Card Connections (kart oyunu) ve playoff tahmin agaci.

Kart oyunu kendi basina calisan bir HTML+JS uygulamasi
(components/card_game.html); burada yalnizca oyuncu havuzu icine
yerlestirilip sunuluyor.

Playoff agaci eskiden paylasim linkindeki ?bracket= degerini hic
temizlemeden JavaScript koduna yaziyordu: hazirlanmis bir link, acan
kisinin tarayicisinda istenen kodu calistirabiliyordu. Artik sunucu
linke hic dokunmuyor; tarayici degeri JSON olarak okuyup yalnizca
bilinen takim adlarini kabul ediyor ve ekrana metin olarak basiyor.
"""
import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from services.cache import cache_data
from services.nba_players_data import get_all_players
from services.nba_season import get_current_season_year, get_season_label
from services.win_totals import get_team_identity
from web.core import render
from web.routes.over_under import load_lines

router = APIRouter()

_GAME_HTML = Path(__file__).resolve().parents[1] / "games" / "card_game.html"

TEAM_COLORS = {
    "Los Angeles Lakers": ("#552583", "#FDB927"), "Boston Celtics": ("#007A33", "#BA9653"),
    "Golden State Warriors": ("#1D428A", "#FFC72C"), "Milwaukee Bucks": ("#00471B", "#EEE1C6"),
    "Denver Nuggets": ("#0E2240", "#FEC524"), "Phoenix Suns": ("#1D1160", "#E56020"),
    "Dallas Mavericks": ("#00538C", "#B8C4CA"), "Philadelphia 76ers": ("#006BB6", "#ED174C"),
    "Miami Heat": ("#98002E", "#F9A01B"), "Oklahoma City Thunder": ("#007AC1", "#EF6100"),
    "Minnesota Timberwolves": ("#0C2340", "#236192"), "New York Knicks": ("#006BB6", "#F58426"),
    "Cleveland Cavaliers": ("#860038", "#FDBB30"), "Sacramento Kings": ("#5A2D81", "#63727A"),
    "Indiana Pacers": ("#002D62", "#FDBB30"), "Los Angeles Clippers": ("#C8102E", "#1D428A"),
    "Toronto Raptors": ("#CE1141", "#000000"), "Chicago Bulls": ("#CE1141", "#000000"),
    "Atlanta Hawks": ("#E03A3E", "#C1D32F"), "Memphis Grizzlies": ("#5D76A9", "#12173F"),
    "New Orleans Pelicans": ("#0C2340", "#C8102E"), "San Antonio Spurs": ("#C4CED4", "#000000"),
    "Houston Rockets": ("#CE1141", "#000000"), "Brooklyn Nets": ("#000000", "#FFFFFF"),
    "Charlotte Hornets": ("#1D1160", "#00788C"), "Portland Trail Blazers": ("#E03A3E", "#000000"),
    "Utah Jazz": ("#002B5C", "#F9A01B"), "Washington Wizards": ("#002B5C", "#E31837"),
    "Detroit Pistons": ("#C8102E", "#1D42BA"), "Orlando Magic": ("#0077C0", "#000000"),
}


@cache_data(ttl=3600, show_spinner=False, copy_result=False)
def _game_document():
    payload = json.dumps({
        "players": get_all_players(),
        "team_colors": {t: [c[0], c[1]] for t, c in TEAM_COLORS.items()},
    }, ensure_ascii=False).replace("</", "<\\/")
    return _GAME_HTML.read_text(encoding="utf-8").replace("__GAME_DATA__", payload)


@router.get("/card-game")
def card_game(request: Request):
    return render(request, "card_game.html", active="cards")


@router.get("/card-game/play", response_class=HTMLResponse)
def card_game_frame():
    return HTMLResponse(_game_document())


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

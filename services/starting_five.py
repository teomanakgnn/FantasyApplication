"""
Starting Five: gecmis bir playoff macinin iki ilk besi. Her takimdan iki
oyuncu acik, uc oyuncu gizli; gizlilerin mevkisi, formasi ve o macta
urettigi sayilar ipucu. Gizli oyuncular isimle tahmin ediliyor.

Veri: services/starting_five.json (scripts/build_starting_five.py).
Hangi oyuncularin gizli oldugu yalnizca mac kimligine bagli; boylece
sunucu durum tutmadan her tahmini kontrol edebiliyor ve isimler
tarayiciya gonderilmiyor.
"""
import json
import random
import re
import unicodedata
from datetime import date
from pathlib import Path

from services.daily_player import today

_DATA = None
LAUNCH = date(2026, 10, 13)
SHOWN = 2          # takim basina acik oyuncu
MAX_MISSES = 5


def _data():
    global _DATA
    if _DATA is None:
        path = Path(__file__).with_name("starting_five.json")
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["by_id"] = {g["id"]: g for g in raw["games"]}
        _DATA = raw
    return _DATA


def norm(name):
    name = unicodedata.normalize("NFD", name or "")
    name = "".join(c for c in name if unicodedata.category(c) != "Mn").lower()
    name = re.sub(r"[.'’\-]", " ", name)
    name = re.sub(r"\b(jr|sr|ii|iii|iv)\b", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def puzzle_number(day=None):
    return ((day or today()) - LAUNCH).days + 1


def names():
    return _data()["names"]


def _big_game(g):
    t = g["title"].upper()
    return "FINALS" in t and "SEMI" not in t


def daily_game_id(day=None):
    """Gunun maci: Finaller ve konferans finalleri arasindan, tekrar etmeden."""
    games = sorted((g for g in _data()["games"] if _big_game(g)), key=lambda g: g["id"])
    order = list(range(len(games)))
    random.Random("starting-five-v1").shuffle(order)
    n = puzzle_number(day) - 1
    return games[order[n % len(order)]]["id"]


def random_game_id():
    return random.choice(_data()["games"])["id"]


def _shown(game):
    """Takim basina acik oyuncularin sirasi (mac kimliginden tohumlu)."""
    rng = random.Random(f"sf-{game['id']}")
    return [set(rng.sample(range(5), SHOWN)) for _ in game["teams"]]


def _title(game):
    t = game["title"].strip()
    t = re.sub(r"\s+", " ", t)
    return t.title().replace("Nba", "NBA")


def view(game_id):
    game = _data()["by_id"].get(str(game_id))
    if not game:
        return None
    shown = _shown(game)
    teams = []
    for ti, team in enumerate(game["teams"]):
        slots = []
        for si, p in enumerate(team["starters"]):
            slot = {"pos": p["pos"], "jersey": p["jersey"], "min": p["min"], "pts": p["pts"],
                    "reb": p["reb"], "ast": p["ast"]}
            if si in shown[ti]:
                slot.update(name=p["name"], id=p["id"], given=True)
            slots.append(slot)
        teams.append({"abbr": team["abbr"], "name": team["name"], "logo": team["logo"],
                      "color": team["color"], "score": team["score"], "slots": slots})
    season = game["season"]
    return {"id": game["id"], "title": _title(game), "date": game["date"],
            "season": f"{season - 1}-{str(season)[2:]}" if season else "", "teams": teams,
            "hidden": sum(5 - len(s) for s in shown), "max_misses": MAX_MISSES}


def guess(game_id, name):
    """Gizli bir ilk-bes oyuncusuysa [(takim, slot, oyuncu)] doner."""
    game = _data()["by_id"].get(str(game_id))
    if not game:
        return None
    shown = _shown(game)
    key = norm(name)
    hits = []
    for ti, team in enumerate(game["teams"]):
        for si, p in enumerate(team["starters"]):
            if si not in shown[ti] and norm(p["name"]) == key:
                hits.append({"team": ti, "slot": si, "name": p["name"], "id": p["id"]})
    return hits


def reveal(game_id):
    game = _data()["by_id"].get(str(game_id))
    if not game:
        return None
    return [[{"name": p["name"], "id": p["id"]} for p in t["starters"]] for t in game["teams"]]

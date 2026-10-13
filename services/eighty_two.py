"""
82-0: rastgele bir takim-sezon cikar, kadrosundan bir oyuncu sec, bes
mevkiyi doldur. Takimin ortalama OVR'si (mevki disi oyuncu cezali) 82
maclik sezona cevrilir; hedef 82-0.

Veri: services/eighty_two.json (scripts/build_eighty_two.py), 1986-2026.
Gunluk oyunda herkes ayni sirayla ayni takimlari gorur.
"""
import json
import math
import random
from datetime import date
from pathlib import Path

from services.daily_player import today

LAUNCH = date(2026, 10, 13)
SPINS = 5
REROLLS = 1
OFF_POSITION = 6          # mevki disi oyuncunun OVR cezasi
MU, K = 87.5, 2.0         # en iyiyi secen ortalama oyuncu ~52 galibiyet; 82-0 icin ~97.7 ortalama

SLOTS = ["PG", "SG", "SF", "PF", "C"]
FITS = {"PG": {"PG", "G"}, "SG": {"SG", "G", "GF"}, "SF": {"SF", "F", "GF"}, "PF": {"PF", "F"}, "C": {"C"}}

NAMES = {
    "ATL": "Atlanta Hawks", "BKN": "Brooklyn Nets", "BOS": "Boston Celtics", "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers", "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GS": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers", "LAC": "LA Clippers",
    "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies", "MIA": "Miami Heat", "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves", "NJ": "New Jersey Nets", "NY": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns", "POR": "Portland Trail Blazers",
    "SA": "San Antonio Spurs", "SAC": "Sacramento Kings", "SEA": "Seattle SuperSonics", "TOR": "Toronto Raptors",
    "UTAH": "Utah Jazz", "VAN": "Vancouver Grizzlies",
}

_DATA = None


def _data():
    global _DATA
    if _DATA is None:
        raw = json.loads(Path(__file__).with_name("eighty_two.json").read_text(encoding="utf-8"))
        _DATA = raw["teams"]
    return _DATA


def team_name(abbr, season):
    if abbr == "WSH":
        return "Washington Bullets" if season <= 1997 else "Washington Wizards"
    if abbr == "NO":
        return "New Orleans Hornets" if season <= 2013 else "New Orleans Pelicans"
    if abbr == "CHA":
        return "Charlotte Bobcats" if 2005 <= season <= 2014 else "Charlotte Hornets"
    return NAMES.get(abbr, abbr)


def puzzle_number(day=None):
    return ((day or today()) - LAUNCH).days + 1


def _spin_view(t):
    season = t["season"]
    return {"season": season, "label": f"{season - 1}-{str(season)[2:]}", "abbr": t["team"],
            "name": team_name(t["team"], season),
            "logo": None if t["team"] in ("NJ", "SEA", "VAN") else
            f"https://a.espncdn.com/i/teamlogos/nba/500/{t['team'].lower()}.png",
            "players": [{k: p[k] for k in ("id", "name", "pos", "gp", "min", "pts", "reb", "ast", "stl", "blk", "ovr")}
                        for p in t["players"]]}


def spins(seed, count=SPINS + REROLLS):
    """Bir oyunun takim sirasi: ayni takim iki kez cikmaz."""
    rng = random.Random(seed)
    picks = rng.sample(range(len(_data())), count)
    return [_spin_view(_data()[i]) for i in picks]


def record(avg_ovr):
    p = 1 / (1 + math.exp(-(avg_ovr - MU) / K))
    wins = int(round(82 * p))
    return wins, 82 - wins


def config():
    return {"slots": SLOTS, "fits": {k: sorted(v) for k, v in FITS.items()}, "penalty": OFF_POSITION,
            "mu": MU, "k": K, "spins": SPINS, "rerolls": REROLLS,
            # Cark seridindeki sahte duraklar icin
            "franchises": [{"abbr": a, "name": NAMES.get(a, a),
                            "logo": f"https://a.espncdn.com/i/teamlogos/nba/500/{a.lower()}.png"}
                           for a in NAMES if a not in ("NJ", "SEA", "VAN")]}

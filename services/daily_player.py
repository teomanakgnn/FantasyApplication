"""
Gunluk gizemli oyuncu (Wordle tipi).

Herkes ayni gun ayni oyuncuyu tahmin eder; 8 hak var. Her tahminde
oyuncunun takimi, konferansi, divizyonu, pozisyonu, boyu, yasi ve forma
numarasi gizli oyuncuyla karsilastirilir: tutan yesil, 2 birim yakin
olan sari, sayilarda ok cevabin yonunu gosterir.

Cevap tarayiciya hic gonderilmiyor; karsilastirmayi sunucu yapiyor.
Gunun oyuncusu ilk istekte secilip veritabanina yaziliyor (oyuncunun o
anki bilgileriyle birlikte): gun icinde takas olsa bile herkes ayni
ipuclariyla oynar. Gun degisimi Londra saatiyle gece yarisi (yaz/kis
saati otomatik).
"""
import random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from services.cache import cache_data
from services.database import db
from services.espn_api import get_current_team_rosters

LAUNCH = date(2026, 10, 3)
MAX_GUESSES = 8
# Cevaplar taninan oyunculardan secilir (draft siralamasinin ilk 120'si);
# tahmin olarak ligdeki herkes yazilabilir.
ANSWER_POOL_SIZE = 120
NO_REPEAT_DAYS = 120

TEAMS = {
    "ATL": ("East", "Southeast", "Hawks"), "BOS": ("East", "Atlantic", "Celtics"),
    "BKN": ("East", "Atlantic", "Nets"), "CHA": ("East", "Southeast", "Hornets"),
    "CHI": ("East", "Central", "Bulls"), "CLE": ("East", "Central", "Cavaliers"),
    "DAL": ("West", "Southwest", "Mavericks"), "DEN": ("West", "Northwest", "Nuggets"),
    "DET": ("East", "Central", "Pistons"), "GS": ("West", "Pacific", "Warriors"),
    "HOU": ("West", "Southwest", "Rockets"), "IND": ("East", "Central", "Pacers"),
    "LAC": ("West", "Pacific", "Clippers"), "LAL": ("West", "Pacific", "Lakers"),
    "MEM": ("West", "Southwest", "Grizzlies"), "MIA": ("East", "Southeast", "Heat"),
    "MIL": ("East", "Central", "Bucks"), "MIN": ("West", "Northwest", "Timberwolves"),
    "NO": ("West", "Southwest", "Pelicans"), "NY": ("East", "Atlantic", "Knicks"),
    "OKC": ("West", "Northwest", "Thunder"), "ORL": ("East", "Southeast", "Magic"),
    "PHI": ("East", "Atlantic", "76ers"), "PHX": ("West", "Pacific", "Suns"),
    "POR": ("West", "Northwest", "Trail Blazers"), "SA": ("West", "Southwest", "Spurs"),
    "SAC": ("West", "Pacific", "Kings"), "TOR": ("East", "Atlantic", "Raptors"),
    "UTAH": ("West", "Northwest", "Jazz"), "WSH": ("East", "Southeast", "Wizards"),
}
DIV_SHORT = {"Atlantic": "ATL", "Central": "CEN", "Southeast": "SE",
             "Northwest": "NW", "Pacific": "PAC", "Southwest": "SW"}


DAY_ZONE = ZoneInfo("Europe/London")


def today():
    return datetime.now(DAY_ZONE).date()


def puzzle_number(day=None):
    return ((day or today()) - LAUNCH).days + 1


def seconds_to_next():
    now = datetime.now(DAY_ZONE)
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), DAY_ZONE)
    return max(1, int((midnight - now).total_seconds()))


def _int(value):
    """ESPN boyu 77.0, formayi "23" olarak veriyor."""
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def player_pool():
    """{espn id: oyuncu} - ligdeki tum aktif kadro oyunculari."""
    pool = _build_pool()
    if not pool:
        _build_pool.clear()     # ESPN'e ulasilamadiysa bos sonucu 6 saat tutma
    return pool


@cache_data(ttl=6 * 3600, show_spinner=False, copy_result=False)
def _build_pool():
    pool = {}
    for name, info in (get_current_team_rosters() or {}).items():
        if not isinstance(info, dict) or not info.get("id") or info.get("team") not in TEAMS:
            continue
        height, age = _int(info.get("height")), _int(info.get("age"))
        if not height or age is None:
            continue
        pid = str(info["id"])
        pool[pid] = {"id": pid, "name": name, "team": info["team"],
                     "pos": info.get("pos") or "", "height": height, "age": age,
                     "jersey": _int(info.get("jersey"))}
    return pool


def search_list():
    """Otomatik tamamlama icin hafif liste."""
    return sorted(({"id": p["id"], "name": p["name"], "team": p["team"]}
                   for p in player_pool().values()), key=lambda p: p["name"])


def _candidates(pool):
    try:
        from services.draft_data import get_draft_board
        board = get_draft_board().sort_values("ADP")
        ids = [str(int(i)) for i in board["ESPN_ID"].dropna()]
        picks = [i for i in ids if i in pool][:ANSWER_POOL_SIZE]
        if len(picks) >= 30:
            return picks
    except Exception as exc:
        print(f"daily player: draft board unavailable ({exc})")
    return sorted(pool)[:ANSWER_POOL_SIZE]


_answers = {}


def answer_for(day=None):
    """Gunun oyuncusu (o gunku bilgileriyle). Kadro yoksa None."""
    day = day or today()
    if day in _answers:
        return _answers[day]
    stored = db.get_daily_player(day)
    if stored and stored.get("data"):
        _answers[day] = stored["data"]
        return stored["data"]
    pool = player_pool()
    if not pool:
        return None
    candidates = _candidates(pool)
    recent = db.recent_daily_player_ids(day, NO_REPEAT_DAYS) if db.available else set()
    fresh = [c for c in candidates if c not in recent] or candidates
    rng = random.Random(f"hooplife-daily-{day.isoformat()}")
    pid = rng.choice(sorted(fresh))
    data = pool[pid]
    if db.available:
        saved = db.set_daily_player(day, pid, data)
        if saved and saved.get("data"):
            data = saved["data"]
        _answers[day] = data
    return data


def _height_label(inches):
    return f"{inches // 12}'{inches % 12}\""


def _num_cell(key, guess, answer, label):
    if guess is None or answer is None:
        return {"key": key, "value": label if guess is not None else "-", "status": "miss", "dir": None}
    if guess == answer:
        return {"key": key, "value": label, "status": "hit", "dir": None}
    return {"key": key, "value": label, "status": "near" if abs(guess - answer) <= 2 else "miss",
            "dir": "up" if answer > guess else "down"}


def compare(guess, answer):
    """Tahmin satiri: her ipucu icin deger, durum (hit/near/miss) ve yon."""
    g_conf, g_div, _ = TEAMS[guess["team"]]
    a_conf, a_div, _ = TEAMS[answer["team"]]

    def eq(key, gv, av, label=None):
        return {"key": key, "value": label or gv, "status": "hit" if gv == av else "miss", "dir": None}

    return [
        eq("team", guess["team"], answer["team"]),
        eq("conf", g_conf, a_conf),
        eq("div", g_div, a_div, DIV_SHORT[g_div]),
        eq("pos", guess["pos"], answer["pos"]),
        _num_cell("height", guess["height"], answer["height"], _height_label(guess["height"])),
        _num_cell("age", guess["age"], answer["age"], str(guess["age"])),
        _num_cell("jersey", guess["jersey"], answer["jersey"],
                  f"#{guess['jersey']}" if guess["jersey"] is not None else "-"),
    ]


def public_answer(answer):
    return {"id": answer["id"], "name": answer["name"], "team": answer["team"],
            "team_name": TEAMS.get(answer["team"], ("", "", answer["team"]))[2],
            "headshot": f"https://a.espncdn.com/i/headshots/nba/players/full/{answer['id']}.png"}

"""
Gunluk kazi kazan (giris yapan kullanici, gunde bir kart). Kart olusturulurken
sunucu bugunun oyunlarindan 1, 2 ya da 3'unu secer; kartta yalnizca ipucu SAYISI
yazar. Kullanici oyunlari tek tek dener: ipucu olan oyunun sayfasinda ipucu cikar,
digerlerinde "burada yok" notu. Hangi oyunlarin secildigi tarayiciya hic gitmez.

Ipuclari bugunun gunluk bulmacalarindan uretilir (cevap sunucuda):
  grid       gunluk grid'in en zor karesine uyan bir oyuncu
  eightytwo  bugunku ilk cevirmenin en iyi oyuncusu (secili donem modunda)
  pyramid    piramidin tepesindeki oyuncu
  daily      gizemli oyuncunun mevkisi ve konferansi
  starting5  gizli ilk bes oyuncularindan birinin adi
  statmatch  bir turun dogru cevabi
"""
import json
import random

from services.daily_player import today

GAMES = {"daily": ("Mystery Player", "/daily"), "statmatch": ("Stat Match", "/stat-match"),
         "starting5": ("Starting Five", "/starting-five"), "eightytwo": ("82-0 Challenge", "/82-0"),
         "pyramid": ("Pyramid", "/pyramid"), "grid": ("3x3 Grid", "/grid")}
# Kac ipucu: cogunlukla 1-2, nadiren 3
COUNT_WEIGHTS = [(1, 0.5), (2, 0.35), (3, 0.15)]


def _rng_count(rng):
    r, acc = rng.random(), 0.0
    for n, w in COUNT_WEIGHTS:
        acc += w
        if r <= acc:
            return n
    return 1


def card(db, user_id, day=None):
    """Bugunun karti (yoksa olusturur): {n, scratched, found}. Oyunlar disari verilmez."""
    day = day or today()
    row = db.scratch_get(user_id, day)
    if not row:
        rng = random.Random()
        n = _rng_count(rng)
        games = rng.sample(sorted(GAMES), n)
        db.scratch_create(user_id, day, json.dumps(games))
        row = db.scratch_get(user_id, day)
    games = json.loads(row["games"] or "[]")
    found = json.loads(row["found"] or "[]")
    return {"n": len(games), "scratched": bool(row["scratched"]), "found": len(found), "day": day.isoformat()}


def scratch(db, user_id):
    c = card(db, user_id)
    db.scratch_mark(user_id, today())
    return dict(c, scratched=True)


def lookup(db, user_id, game, params=None):
    """Bu oyunda ipucu var mi? Varsa ipucu ve bulunanlara ekler."""
    if game not in GAMES:
        return {"state": "unknown"}
    row = db.scratch_get(user_id, today())
    if not row or not row["scratched"]:
        return {"state": "no_card" if not row else "not_scratched"}
    games = json.loads(row["games"] or "[]")
    found = json.loads(row["found"] or "[]")
    if game not in games:
        return {"state": "none", "n": len(games), "found": len(found)}
    hint = build_hint(game, params or {})
    if game not in found:
        found.append(game)
        db.scratch_found(user_id, today(), json.dumps(found))
    return {"state": "hint", "n": len(games), "found": len(found), "game": GAMES[game][0], "hint": hint}


# ==================== IPUCLARI ====================

def build_hint(game, params):
    try:
        return HINTS[game](params)
    except Exception as exc:                       # bulmaca hazir degilse ipucu yine de bos donmesin
        print(f"scratch hint {game} failed: {exc}")
        return {"title": "Hint", "text": "Today's puzzle is still loading - come back in a minute for your hint."}


def _grid(params):
    from services import grid
    g = grid.daily()
    best = None
    for ri, r in enumerate(g["rows"]):
        for ci, c in enumerate(g["cols"]):
            a = grid.answers(r, c)
            if a and (best is None or len(a) < best[0]):
                best = (len(a), ri, ci, a[0])
    _, ri, ci, p = best
    rl, cl = grid.label(g["rows"][ri])["label"], grid.label(g["cols"][ci])["label"]
    return {"title": "A square is open", "text": f"{rl} + {cl}: {p['n']} fits this square - the hardest one on today's grid.",
            "player": {"id": p["id"], "name": p["n"]}}


def _eightytwo(params):
    from services import eighty_two as e82
    try:
        span = int(params.get("span") or 1)
    except ValueError:
        span = 1
    span = span if span in e82.SPANS else 1
    spins = e82.game(f"82-0-{today().isoformat()}", span)
    first = spins[0]["main"]
    best = max(first["players"], key=lambda p: p["ovr"])
    mode = "1-season" if span == 1 else f"{span}-season"
    return {"title": "Scout's pick", "text": f"Spin 1 today ({mode} mode): {first['name']} {first['label']} - "
                                            f"{best['name']} is the best player on that roster.",
            "player": {"id": best["id"], "name": best["name"]}}


def _pyramid(params):
    from services import pyramid
    pz = pyramid.daily()
    top = pz["answer"][0]
    return {"title": "Top of the pyramid", "text": f"{top['name']} belongs at the very top of today's pyramid ({pz['label'].lower()}).",
            "player": {"id": top["id"], "name": top["name"]}}


def _daily(params):
    from services import daily_player as dp
    a = dp.answer_for()
    conf = dp.TEAMS.get(a["team"], ("", "", ""))[0]
    pos = {"G": "guard", "F": "forward", "C": "center"}.get(a.get("pos"), a.get("pos") or "player")
    return {"title": "Scouting report", "text": f"Today's mystery player is a {pos} in the {conf}ern Conference."}


def _starting5(params):
    from services import starting_five as sf
    gid = sf.daily_game_id()
    game = sf._data()["by_id"].get(str(gid))
    shown = sf._shown(game)
    hidden = [(t["abbr"], p) for ti, t in enumerate(game["teams"]) for si, p in enumerate(t["starters"]) if si not in shown[ti]]
    abbr, p = random.Random(f"s5-hint-{today().isoformat()}").choice(hidden)
    return {"title": "One starter revealed", "text": f"{p['name']} started for {abbr} in today's game.",
            "player": {"id": p.get("id"), "name": p["name"]}}


def _statmatch(params):
    from services import minigames
    day = today()
    rounds = minigames.stat_match_rounds(f"statmatch-{day.isoformat()}")
    i = random.Random(f"sm-hint-{day.isoformat()}").randrange(len(rounds))
    r = rounds[i]
    players = r.get("players") or []
    left = players[0]["name"] if players else "the left player"
    right = players[1]["name"] if len(players) > 1 else "the right player"
    top_is = left if r["answer"] == 0 else right
    return {"title": "Round answer", "text": f"Round {i + 1}: the top stat line belongs to {top_is}."}


HINTS = {"grid": _grid, "eightytwo": _eightytwo, "pyramid": _pyramid, "daily": _daily, "starting5": _starting5,
         "statmatch": _statmatch}

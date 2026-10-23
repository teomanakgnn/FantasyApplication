"""
Mac simulasyonu: bir maci 5.000 kez oynatir (Monte Carlo, oyuncu bazli).

Her oyuncu icin dakika basi oranlar (2'lik / 3'luk / serbest atis denemesi,
ribaund, asist, top calma, blok, top kaybi) ve isabet yuzdeleri: gecen sezon
(2025-26) ile bu sezonun harmani; az mac oynanmissa gecen sezon agir basar.
Yuzdeler lig ortalamasina dogru buzulur (az atisla %60 uclukcu olmaz).

Her senaryoda:
  - kim oynar: OUT oynamaz; day-to-day / questionable / doubtful oyuncu
    ihtimaliyle oynar (0.6 / 0.6 / 0.2),
  - dakikalar: beklenen dakika + gurultu, takim 240 dakikaya olceklenir,
  - tempo: iki takim ayni sayida topa sahip olur; mac temposu rastgele,
  - takimin o geceki isabet formu (iyi / kotu gece) ve ev sahibi avantaji,
  - denemeler Poisson, isabetler Binom; diger istatistikler Poisson,
  - beraberlikte uzatma.
"En tipik mac": skor farki ve toplam sayisi medyana en yakin, kazanani en
olasi taraf olan senaryolar arasinda oyuncu sayilari medyana en yakin olan.
"""
import json
import random
import unicodedata
import zlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

N_SIMS = 5000
MODEL = "v1"
EASTERN = ZoneInfo("America/New_York")
LONDON = ZoneInfo("Europe/London")
LG = {"p2": 0.54, "p3": 0.36, "pft": 0.78}
PLAY_PROB = {"out": 0.0, "doubtful": 0.2, "questionable": 0.6, "day-to-day": 0.6, "probable": 0.9}
WEIGHTS = {"pts": 0.75, "reb": 0.5, "ast": 0.8, "stl": 1.7, "blk": 1.6, "to": -1.5, "fga": -0.9, "fgm": 1.2,
           "fta": -0.55, "ftm": 1.1, "tpm": 0.6}


def _norm(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return "".join(ch for ch in s if ch.isalnum())


def _f(v):
    try:
        f = float(v)
        return 0.0 if f != f else f
    except (TypeError, ValueError):
        return 0.0


# ==================== OYUNCU PROFILLERI ====================

def _profiles(team_abbr, season):
    """Takimin oyunculari: dakika basi oranlar, yuzdeler, beklenen dakika, oynama ihtimali."""
    from services.espn_api import get_current_team_rosters, get_injuries, get_nba_season_stats_official
    rosters = get_current_team_rosters() or {}
    last = get_nba_season_stats_official(season - 1)
    cur = get_nba_season_stats_official(season)
    by_id = lambda df: {str(r["PLAYER_ID"]): r for _, r in df.iterrows()} if df is not None and not df.empty else {}
    L, C = by_id(last), by_id(cur)
    status = {}
    for i in get_injuries() or []:
        status[_norm(i.get("player"))] = (i.get("status") or "").lower()

    out = []
    for name, info in rosters.items():
        if not isinstance(info, dict) or (info.get("team") or "").upper() != team_abbr.upper():
            continue
        pid = str(info.get("id") or "")
        l, c = L.get(pid), C.get(pid)
        if l is None and c is None:
            continue                      # hic NBA dakikasi yok: rotasyon disi say
        def per_min(r):
            m = _f(r["MIN"]) or 1.0
            fga, tpa, fta = _f(r["FGA"]), _f(r["3PTA"]), _f(r["FTA"])
            return {"fga2": max(fga - tpa, 0) / m, "fga3": tpa / m, "fta": fta / m, "reb": _f(r["REB"]) / m,
                    "ast": _f(r["AST"]) / m, "stl": _f(r["STL"]) / m, "blk": _f(r["BLK"]) / m, "to": _f(r["TO"]) / m}
        def totals(r):
            gp = _f(r["GP"])
            fgm, fga, tpm, tpa = _f(r["FGM"]) * gp, _f(r["FGA"]) * gp, _f(r["3Pts"]) * gp, _f(r["3PTA"]) * gp
            return {"2m": fgm - tpm, "2a": fga - tpa, "3m": tpm, "3a": tpa, "fm": _f(r["FTM"]) * gp, "fa": _f(r["FTA"]) * gp}
        w = 0.0 if c is None else _f(c["GP"]) / (_f(c["GP"]) + 8.0)
        if l is None:
            w = 1.0
        rates, mins = {}, 0.0
        for src, wt in ((l, 1 - w), (c, w)):
            if src is None or wt == 0:
                continue
            pm = per_min(src)
            for k, v in pm.items():
                rates[k] = rates.get(k, 0.0) + wt * v
            mins += wt * _f(src["MIN"])
        tot = {k: 0.0 for k in ("2m", "2a", "3m", "3a", "fm", "fa")}
        for src in (l, c):
            if src is not None:
                for k, v in totals(src).items():
                    tot[k] += v
        pct = {"p2": (tot["2m"] + 60 * LG["p2"]) / (tot["2a"] + 60),
               "p3": (tot["3m"] + 70 * LG["p3"]) / (tot["3a"] + 70),
               "pft": (tot["fm"] + 30 * LG["pft"]) / (tot["fa"] + 30)}
        st = status.get(_norm(name), "")
        play = next((p for k, p in PLAY_PROB.items() if k in st), 1.0)
        out.append({"id": pid, "name": name, "pos": info.get("pos") or "", "min": mins, "rates": rates,
                    "pct": pct, "play": play, "status": st})
    out.sort(key=lambda p: -p["min"])
    return out[:15]


# ==================== SIMULASYON ====================

def _minutes(rng, players, n):
    """
    Rotasyon: oynayanlar beklenen dakikasi kadar (gurultulu), en cok oynayandan
    baslayarak dagitilir; takim 240'a ulasinca kalan yedekler oynamaz. Sakat
    yildizin dakikalari boylece rotasyonun devamina gecer. Toplam 240'in
    altinda kalirsa (cok sakat) herkes orantili artar.
    """
    base = np.array([p["min"] for p in players])                 # zaten dakikaya gore sirali
    plays = rng.random((n, len(players))) < np.array([p["play"] for p in players])
    want = np.where(plays, np.clip(base + rng.normal(0, 2.5, (n, len(players))), 0, 42), 0.0)
    before = np.cumsum(want, axis=1) - want
    m = np.clip(np.minimum(want, 240.0 - before), 0, None)
    # Toplam 240'in altindaysa oynayanlara orantili ekle; 44 sinirina takilanin
    # artani digerlerine gecsin (birkac tur)
    for _ in range(4):
        gap = 240.0 - m.sum(axis=1, keepdims=True)
        room = np.where((m > 0) & (m < 44.0), m, 0.0)
        share = room / np.maximum(room.sum(axis=1, keepdims=True), 1e-9)
        m = np.minimum(m + np.clip(gap, 0, None) * share, 44.0)
    return m


def _count(rng, mean):
    """Deneme sayisi: Poisson'dan az oynak (takim toplami topa sahip olmayla sinirli)."""
    return np.clip(np.round(rng.normal(mean, np.sqrt(mean) * 0.45)), 0, None).astype(int)


def _team(rng, players, mins, poss_scale, form, home):
    R = lambda k: np.array([p["rates"].get(k, 0.0) for p in players])
    P = lambda k: np.array([p["pct"][k] for p in players])
    scale = mins * poss_scale[:, None]
    boost = 0.012 if home else 0.0
    fga2 = _count(rng, R("fga2") * scale)
    fga3 = _count(rng, R("fga3") * scale)
    fta = _count(rng, R("fta") * scale * (1.04 if home else 1.0))
    p2 = np.clip(P("p2") + form[:, None] + boost, 0.2, 0.8)
    p3 = np.clip(P("p3") + form[:, None] + boost * 0.6, 0.1, 0.6)
    fgm2 = rng.binomial(fga2, p2)
    fgm3 = rng.binomial(fga3, p3)
    ftm = rng.binomial(fta, np.clip(P("pft"), 0.3, 0.95))
    box = {"min": mins, "fgm": fgm2 + fgm3, "fga": fga2 + fga3, "tpm": fgm3, "tpa": fga3, "ftm": ftm, "fta": fta,
           "pts": 2 * fgm2 + 3 * fgm3 + ftm}
    for k in ("reb", "ast", "stl", "blk", "to"):
        box[k] = rng.poisson(R(k) * scale)
    return box


def _poss_per_min(players):
    """Takimin dakika basi 'topa sahip olma' tahmini (FGA + 0.44 FTA + TO), rotasyon dakikalariyla."""
    base = np.array([p["min"] * p["play"] for p in players])
    base = np.clip(np.minimum(base, 240.0 - (np.cumsum(base) - base)), 0, None)
    base = base * 240.0 / max(base.sum(), 1e-9)
    r = np.array([p["rates"].get("fga2", 0) + p["rates"].get("fga3", 0) + 0.44 * p["rates"].get("fta", 0)
                  + p["rates"].get("to", 0) for p in players])
    return float((r * base).sum())


def _league_poss(season):
    """Gecen sezon takim basina mac basi topa sahip olma (FGA + 0.44 FTA + TO), oyuncu toplamlarindan."""
    from services.espn_api import get_nba_season_stats_official
    df = get_nba_season_stats_official(season - 1)
    if df is None or df.empty:
        return 100.0
    tot = ((df["FGA"] + 0.44 * df["FTA"] + df["TO"]) * df["GP"]).sum()
    return float(tot / (30 * 82))


def simulate(game_id, away, home, season, n=N_SIMS, seed=None):
    rng = np.random.default_rng(seed if seed is not None else zlib.crc32(f"{game_id}-{MODEL}".encode()))
    teams = {"away": _profiles(away, season), "home": _profiles(home, season)}
    if len(teams["away"]) < 7 or len(teams["home"]) < 7:
        return None
    # Iki takim ayni sayida topa sahip olur: lig ortalamasi x mac temposu. Her takimin
    # oyuncularinin oranlari bu paya olceklenir (rotasyonun toplam kullanimi %100'u gecmesin).
    poss = {k: _poss_per_min(v) for k, v in teams.items()}
    game_poss = _league_poss(season) * 0.975 * rng.normal(1.0, 0.03, n)   # 0.975: cop zamani eklemesi ve ev avantaji sonrasi lig ortalamasina kalibrasyon
    box, score = {}, {}
    for side in ("away", "home"):
        mins = _minutes(rng, teams[side], n)
        form = rng.normal(0, 0.012, n)
        box[side] = _team(rng, teams[side], mins, game_poss / poss[side], form, side == "home")
        score[side] = box[side]["pts"].sum(axis=1).astype(float)
    # Mac gidisati: buyuk farkta yildizlar dinlenir, geride kalan takim cop zamaninda
    # farki kapatir. 8 sayiyi asan farkin %35'i geride kalana doner (gercek NBA'de skor
    # farkinin sapmasi ~13.5; saf isabet rastgeleligi ~17 veriyordu).
    m = score["home"] - score["away"]
    give = np.round(np.clip(np.abs(m) - 8, 0, None) * 0.35)
    score["home"] += np.where(m < 0, give, 0)
    score["away"] += np.where(m > 0, give, 0)
    # Uzatma: beraberlikte 5 dakikalik ek bolum (takim ortalamasinin 5/48'i)
    ot = np.zeros(n, dtype=int)
    tied = score["away"] == score["home"]
    for _ in range(4):
        if not tied.any():
            break
        for side in ("away", "home"):
            score[side][tied] += np.round(rng.normal(score[side].mean() * 5 / 48, 3.2, tied.sum()))
        ot[tied] += 1
        tied = score["away"] == score["home"]
    score["home"][tied] += 1          # cok nadir: dort uzatmadan sonra hala esitse ev sahibi

    margin = score["home"] - score["away"]
    home_win = margin > 0
    p_home = float(home_win.mean())
    fav_home = p_home >= 0.5
    med_margin, med_total = float(np.median(margin)), float(np.median(score["home"] + score["away"]))

    def player_rows(side):
        rows = []
        b = box[side]
        for i, p in enumerate(teams[side]):
            played = b["min"][:, i] > 0
            if played.mean() < 0.05:
                continue
            pts = b["pts"][:, i][played]
            fp = sum(WEIGHTS[k] * b[k][:, i] for k in WEIGHTS)[played]
            dd = ((b["pts"][:, i] >= 10).astype(int) + (b["reb"][:, i] >= 10) + (b["ast"][:, i] >= 10)
                  + (b["stl"][:, i] >= 10) + (b["blk"][:, i] >= 10))[played]
            med = lambda k: float(np.median(b[k][:, i][played]))
            rows.append({"id": p["id"], "name": p["name"], "pos": p["pos"], "status": p["status"],
                         "play": round(float(played.mean()), 2), "min": round(med("min"), 1),
                         "pts": med("pts"), "reb": med("reb"), "ast": med("ast"), "stl": med("stl"), "blk": med("blk"),
                         "to": med("to"), "tpm": med("tpm"),
                         "pts_lo": float(np.percentile(pts, 10)), "pts_hi": float(np.percentile(pts, 90)),
                         "p20": round(float((pts >= 20).mean()), 3), "p30": round(float((pts >= 30).mean()), 3),
                         "p_dd": round(float((dd >= 2).mean()), 3), "p_td": round(float((dd >= 3).mean()), 3),
                         "fp": round(float(np.mean(fp)), 1)})
        rows.sort(key=lambda r: -r["min"])
        return rows

    players = {s: player_rows(s) for s in ("away", "home")}

    # En tipik mac
    close = (np.abs(margin - med_margin) <= 3) & (np.abs(score["home"] + score["away"] - med_total) <= 6) & (home_win == fav_home)
    idx = np.where(close)[0]
    if not len(idx):
        idx = np.argsort(np.abs(margin - med_margin))[:200]
    dev = np.zeros(len(idx))
    for side in ("away", "home"):
        pts = box[side]["pts"]
        med = np.median(pts, axis=0)
        sd = pts.std(axis=0) + 1.0
        dev += (np.abs(pts[idx] - med) / sd).sum(axis=1)
    t = int(idx[np.argmin(dev)])

    def typical(side):
        b, rows = box[side], []
        for i, p in enumerate(teams[side]):
            if b["min"][t, i] < 1:
                continue
            rows.append({"id": p["id"], "name": p["name"], "min": int(round(b["min"][t, i])),
                         **{k: int(b[k][t, i]) for k in ("pts", "reb", "ast", "stl", "blk", "to", "fgm", "fga", "tpm", "tpa", "ftm", "fta")}})
        rows.sort(key=lambda r: -r["min"])
        return rows

    # Sayi lideri: her senaryoda en cok sayi atan (iki takim birlikte)
    allpts = np.concatenate([box["away"]["pts"], box["home"]["pts"]], axis=1)
    names = [p["name"] for p in teams["away"]] + [p["name"] for p in teams["home"]]
    lead = np.bincount(allpts.argmax(axis=1), minlength=len(names)) / n
    leaders = [{"name": names[i], "p": round(float(lead[i]), 3)} for i in np.argsort(-lead)[:3]]

    bins = list(range(-30, 31, 5))
    hist = np.histogram(np.clip(margin, -32, 32), bins=[-100] + bins[1:-1] + [100])[0] / n
    return {
        "game_id": str(game_id), "away": away, "home": home, "n": n, "model": MODEL,
        "created": datetime.now(LONDON).isoformat(timespec="minutes"),
        "p_home": round(p_home, 3), "p_away": round(1 - p_home, 3),
        "score": {s: {"median": float(np.median(score[s])), "lo": float(np.percentile(score[s], 10)),
                      "hi": float(np.percentile(score[s], 90))} for s in ("away", "home")},
        "margin_median": med_margin, "total_median": med_total,
        "total_lo": float(np.percentile(score["home"] + score["away"], 10)),
        "total_hi": float(np.percentile(score["home"] + score["away"], 90)),
        "p_ot": round(float((ot > 0).mean()), 3), "p_close": round(float((np.abs(margin) <= 5).mean()), 3),
        "hist": [{"from": bins[i], "to": bins[i + 1], "p": round(float(hist[i]), 3)} for i in range(len(hist))],
        "players": players, "leaders": leaders,
        "typical": {"away": typical("away"), "home": typical("home"),
                    "score": {"away": int(score["away"][t]), "home": int(score["home"][t])}, "ot": int(ot[t])},
        "out": {s: [p["name"] for p in teams[s] if p["play"] == 0] for s in ("away", "home")},
    }


# ==================== GUNLUK SECIM VE KAYIT ====================

def pick_games(day, games, k=2):
    """Gunun rastgele k maci (tarih tohumlu: ayni gun hep ayni maclar). Baslamamis maclar."""
    pool = [g for g in games if str(g.get("status", "")).lower() in ("scheduled", "pre-game", "")]
    rng = random.Random(f"sim-{day.isoformat()}")
    return rng.sample(pool, min(k, len(pool)))


def daily_run(force=False):
    """Sabah (Londra 09:00 sonrasi), gunun iki maci yoksa simule edip kaydeder. Yeni sayfa yollarini dondurur."""
    from services.database import db
    from services.nba_pages import game_path, games_on
    from services.nba_season import get_current_season_year
    now = datetime.now(LONDON)
    day = datetime.now(EASTERN).date()
    if not force and now.hour < 9:
        return []
    if not db.available:
        return []
    done = db.sims_for_day(day)
    if len(done) >= 2 and not force:
        return []
    games = games_on(day)
    picked = [g for g in pick_games(day, games) if g["game_id"] not in done]
    season = get_current_season_year()
    fresh = []
    for g in picked:
        try:
            res = simulate(g["game_id"], g["away_team"], g["home_team"], season)
        except Exception as exc:
            print(f"sim failed for {g['game_id']}: {exc}")
            continue
        if res:
            db.save_sim(g["game_id"], day, json.dumps(res))
            fresh.append(game_path(g))
            print(f"simulated {g['away_team']} @ {g['home_team']}: home {res['p_home']:.0%}")
    return fresh

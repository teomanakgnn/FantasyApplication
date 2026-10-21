"""
Fantasy waiver wire: ESPN liglerinin cogunda bosta duran (sahiplenilme
< %50) ama son gunlerde 9 kategoride deger ureten oyuncular.

Veri tek ESPN cagrisi: en cok sahiplenilen 650 oyuncu, sahiplenilme orani
ve haftalik degisimi, bu sezonun / son 7 / son 15 gunun / gecen sezonun
mac basi ortalamalari. z-skorlari Trade Analyzer ile ayni yontem (draft
edilen havuza gore, yuzdeler hacim agirlikli, TO ters).
"""
import json
from datetime import datetime

import pandas as pd

from services.cache import cache_data
from services.draft_data import FANTASY_BASE, get_pro_team_map
from services.nba_season import get_current_season_year, get_session
from services.trade_values import CATS, _zscores

WINDOWS = {"7": ("Last 7 days", 1), "15": ("Last 15 days", 2), "season": ("Season", 0)}
POS = {1: "PG", 2: "SG", 3: "SF", 4: "PF", 5: "C"}
# ESPN istatistik kimlikleri -> bizim alanlar
STAT = {"pts": "0", "blk": "1", "stl": "2", "ast": "3", "reb": "6", "to": "11", "fgm": "13", "fga": "14",
        "ftm": "15", "fta": "16", "tpm": "17", "min": "40", "gp": "42"}


@cache_data(ttl=2 * 3600, show_spinner=False, copy_result=False)
def _pool():
    season = get_current_season_year()
    flt = {"players": {"limit": 650, "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
                       "filterStatsForSourceIds": {"value": [0]}, "filterStatsForSplitTypeIds": {"value": [0, 1, 2]}}}
    r = get_session().get(f"{FANTASY_BASE}/{season}/segments/0/leaguedefaults/3?view=kona_player_info",
                          headers={"Accept": "application/json", "x-fantasy-filter": json.dumps(flt)}, timeout=45)
    r.raise_for_status()
    teams = get_pro_team_map(season)
    out = []
    for e in r.json().get("players") or []:
        p = e.get("player") or e
        own = p.get("ownership") or {}
        splits = {}
        for s in p.get("stats") or []:
            avg = s.get("averageStats") or {}
            if s.get("statSourceId") != 0 or not avg:
                continue
            key = ("last" if s.get("seasonId") == season - 1 and s.get("statSplitTypeId") == 0 else
                   {0: "season", 1: "7", 2: "15"}.get(s.get("statSplitTypeId")) if s.get("seasonId") == season else None)
            if key:
                splits[key] = {k: float(avg.get(v) or 0) for k, v in STAT.items()}
        out.append({"id": p.get("id"), "name": p.get("fullName"), "team": teams.get(p.get("proTeamId"), "FA"),
                    "pos": POS.get(p.get("defaultPositionId"), ""), "injury": p.get("injuryStatus") or "ACTIVE",
                    "owned": round(float(own.get("percentOwned") or 0), 1),
                    "change": round(float(own.get("percentChange") or 0), 1), "splits": splits})
    return out


def week_number():
    """ESPN fantezi haftasi (Pazartesi-Pazar), 1'den baslar."""
    try:
        from services import league_week as lw
        season = get_current_season_year()
        _, first = lw.pro_schedule(season)
        wk, _ = lw.weeks(season, first)
        today = datetime.now(lw.LONDON).date()
        for w, (s, e) in wk.items():
            if s <= today <= e:
                return w
    except Exception:
        pass
    return None


def _reasons(p, cats_sorted):
    out = []
    s, last = p["s"], p.get("last")
    if last and last["min"] and s["min"] - last["min"] >= 5:
        out.append(f"Minutes up: {s['min']:.0f} a game, {last['min']:.0f} last season.")
    good = [c for c in cats_sorted if p["z"][c] >= 0.8][:3]
    if good:
        out.append("Helps in " + ", ".join("low turnovers" if c == "TO" else c for c in good) + ".")
    if p["change"] >= 1.5:
        out.append(f"Being added fast: +{p['change']:.1f}% of ESPN leagues this week.")
    bad = [c for c in ("FG%", "FT%", "TO") if p["z"][c] <= -1.0]
    if bad:
        out.append("Hurts " + " and ".join("turnovers" if c == "TO" else c for c in bad) + ".")
    if p["injury"] not in ("ACTIVE", "NORMAL"):
        out.append(f"Listed {p['injury'].replace('_', ' ').lower()} - check before adding.")
    if p["gp"] <= 2:
        out.append(f"Small sample ({p['gp']} game{'s' if p['gp'] != 1 else ''}).")
    return out


@cache_data(ttl=1800, show_spinner=False, copy_result=False)
def board(window="15"):
    """Penceredeki z-skorlarina gore tum havuz; sayfa sahiplenilmeye gore suzer."""
    window = window if window in WINDOWS else "15"
    rows = []
    for p in _pool():
        st = p["splits"].get(window) or p["splits"].get("season")
        if not st or st["gp"] < 1 or st["min"] < 10:
            continue
        rows.append({**p, "s": st, "last": p["splits"].get("last")})
    if not rows:
        return []
    df = pd.DataFrame([r["s"] for r in rows])
    z = _zscores(df)
    for i, r in enumerate(rows):
        r["z"] = {c: round(float(z.at[i, c]), 2) for c in CATS}
        r["total"] = round(sum(r["z"].values()), 2)
        r["gp"] = int(r["s"]["gp"])
        # Kucuk ornek cezasi: tek macta patlayan oyuncu listeyi ele gecirmesin
        r["score"] = r["total"] * min(1.0, 0.55 + 0.15 * r["gp"]) + 0.08 * max(r["change"], 0)
        order = sorted(CATS, key=lambda c: -r["z"][c])
        r["reasons"] = _reasons(r, order)
        r["best"] = [c for c in order if r["z"][c] >= 0.5][:3]
    rows.sort(key=lambda r: -r["score"])
    return rows


def pickups(window="15", max_owned=50, cat=None, limit=40):
    rows = [r for r in board(window) if r["owned"] < max_owned]
    if cat in CATS:
        rows = sorted(rows, key=lambda r: -(r["z"][cat] + 0.15 * r["total"]))
    return rows[:limit]


def risers(limit=8):
    """Bu hafta en hizli eklenenler (sahiplenilme degisimi)."""
    rows = [r for r in board("15") if r["owned"] < 80 and r["change"] > 0]
    return sorted(rows, key=lambda r: -r["change"])[:limit]

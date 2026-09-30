"""
Trade analyzer: iki taraf, dort degerleme yontemi, punt secenekleri.

Sunucu yalnizca secilen donemin oyuncu ortalamalarini verir; secim ve
hesap tarayicida, yani oyuncu eklemek/cikarmak aninda sonuc degistirir.
"""
from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Request

from services.cache import cache_data
from services.espn_api import get_nba_season_stats_official
from web import stats
from web.core import render

router = APIRouter()

PERIODS = {"season": "Season average", "30": "Last 30 days", "15": "Last 15 days"}


def _rows(df):
    out = []
    for _, r in df.iterrows():
        def n(key):
            try:
                return round(float(r.get(key, 0) or 0), 2)
            except (TypeError, ValueError):
                return 0.0
        out.append({"name": r["PLAYER"], "team": str(r.get("TEAM") or ""), "gp": int(n("GAMES") or n("GP")),
                    "pts": n("PTS"), "reb": n("REB"), "ast": n("AST"), "stl": n("STL"),
                    "blk": n("BLK"), "to": n("TO"), "tpm": n("3Pts"), "fgm": n("FGM"),
                    "fga": n("FGA"), "ftm": n("FTM"), "fta": n("FTA")})
    return out


@cache_data(ttl=1800, show_spinner=False, copy_result=False)
def players_for(period):
    if period == "season":
        df = stats.season_table(stats.BASE_WEIGHTS)
        if df.empty:
            return []
        df = df[pd.to_numeric(df.get("MIN_INT", 0), errors="coerce").fillna(0) >= 10]
        return sorted(_rows(df), key=lambda p: p["name"])
    days = int(period)
    end = date.today()
    rows = stats._period_games(end - timedelta(days=days), end)
    if not rows:
        return []
    daily = pd.DataFrame(rows)
    daily = stats._numeric(daily, stats.STAT_KEYS)
    daily["MIN_INT"] = daily["MIN"].apply(stats.parse_minutes) if "MIN" in daily.columns else 0
    daily = daily[daily["MIN_INT"] > 0]
    if daily.empty:
        return []
    agg = daily.groupby("PLAYER").agg(TEAM=("TEAM", "last"), GAMES=("PLAYER", "size"),
                                      MIN=("MIN_INT", "mean"),
                                      **{k: (k, "mean") for k in stats.STAT_KEYS}).reset_index()
    agg = agg[agg["MIN"] >= 10]
    return sorted(_rows(agg), key=lambda p: p["name"])


@router.get("/trade-analyzer")
def trade(request: Request, period: str = "season"):
    if period not in PERIODS:
        period = "season"
    players = players_for(period)
    # Sezon oncesi son 15/30 gunde mac yok: bos sayfa yerine neden bos oldugunu soyle.
    return render(request, "trade.html", active="trade", period=period, periods=PERIODS,
                  players=players, teams=sorted({p["team"] for p in players if p["team"]}),
                  team_names=stats.TEAM_NAMES)

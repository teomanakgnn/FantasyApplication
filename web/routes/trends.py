"""Player Trends (Pro): iki donemin fantasy ortalamasi karsilastirmasi + soylentiler."""
from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Request

from services.nba_season import get_season_start_date
from services.rumors import trade_rumors
from utils.images import headshot
from web import stats
from web.core import current_user, is_pro, render
from web.plans import UPGRADE_NOTE

router = APIRouter()

PERIODS = {"7": "Last 7 days", "15": "Last 15 days", "30": "Last 30 days",
           "45": "Last 45 days", "season": "Full season"}
TREND_WEIGHTS = {"PTS": 1.0, "REB": 0.4, "AST": 0.7, "STL": 1.1, "BLK": 0.75, "TO": -1.0,
                 "FGA": -0.7, "FGM": 0.5, "FTA": -0.4, "FTM": 0.6, "3Pts": 0.3}


def _start(period):
    if period == "season":
        start = get_season_start_date()
        if start.date() > date.today():
            start = get_season_start_date(start.year)
        return start.date()
    return date.today() - timedelta(days=int(period))


def _int(value, default, low, high):
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


@router.get("/trends")
def trends(request: Request):
    user = current_user(request)
    if not is_pro(user):
        return render(request, "locked.html", active="trends", feature="Player trends",
                      body="Compare any two periods to find who is heating up and who is fading, "
                           "plus a feed of trade rumours from around the league.",
                      note=UPGRADE_NOTE)
    q = request.query_params
    p1 = q.get("p1", "15") if q.get("p1") in PERIODS else "15"
    p2 = q.get("p2", "30") if q.get("p2") in PERIODS else "30"
    min_g1 = _int(q.get("g1"), 3, 1, 30)
    min_g2 = _int(q.get("g2"), 5, 1, 60)
    lo = _int(q.get("lo"), 20, 0, 150)
    hi = _int(q.get("hi"), 100, 0, 150)

    earliest = min(_start(p1), _start(p2))
    rows = stats._period_games(earliest, date.today())
    table, risers, fallers = [], [], []
    if rows:
        df = pd.DataFrame(rows)
        df = stats._numeric(df, list(TREND_WEIGHTS))
        df["FS"] = sum(df[k] * w for k, w in TREND_WEIGHTS.items())
        df["DATE"] = pd.to_datetime(df["DATE"])

        def agg(period):
            part = df[df["DATE"] >= pd.Timestamp(_start(period))]
            return part.groupby("PLAYER").agg(avg=("FS", "mean"), games=("FS", "size"), team=("TEAM", "last"))
        a, b = agg(p1), agg(p2)
        merged = a.join(b, how="inner", lsuffix="1", rsuffix="2")
        merged = merged[(merged["games1"] >= min_g1) & (merged["games2"] >= min_g2) &
                        merged["avg1"].between(lo, hi) & merged["avg2"].between(lo, hi)]
        merged["diff"] = merged["avg1"] - merged["avg2"]
        index = stats._roster_index()
        for name, r in merged.sort_values("diff", ascending=False).iterrows():
            table.append({"player": name, "team": r["team1"], "g1": int(r["games1"]), "g2": int(r["games2"]),
                          "a1": r["avg1"], "a2": r["avg2"], "diff": r["diff"],
                          "photo": headshot((index.get(stats._norm(name)) or {}).get("id"))})
        risers = table[:5]
        fallers = sorted(table, key=lambda r: r["diff"])[:5]
    return render(request, "trends.html", active="trends", periods=PERIODS, p1=p1, p2=p2,
                  g1=min_g1, g2=min_g2, lo=lo, hi=hi, table=table, risers=risers,
                  fallers=fallers, has_games=bool(rows), rumors=trade_rumors())

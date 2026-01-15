from services.espn_api import get_historical_boxscores
from utils.helpers import parse_minutes

# ---------------- CONFIG ----------------
PLAYER_NAME = "Julian Champagnie"
START_DATE = "2026-01-06"
END_DATE = "2026-01-12"

# Fantasy weights (app ile birebir aynı olmalı)
weights = {
    "PTS": 1.0,
    "REB": 0.4,
    "AST": 0.7,
    "STL": 1.1,
    "BLK": 0.75,
    "TO": -1.0
}

# ---------------------------------------

def calculate_fantasy_score(player, weights):
    score = 0.0
    for stat, weight in weights.items():
        try:
            score += float(player.get(stat, 0)) * float(weight)
        except (TypeError, ValueError):
            pass
    return score


historical_data = get_historical_boxscores(START_DATE, END_DATE)

print(f"\n🔍 Checking appearances for: {PLAYER_NAME}\n")

for game_day in historical_data:
    date = game_day.get("date", "UNKNOWN DATE")
    players = game_day.get("players", [])

    day_stats = []

    for p in players:
        name = p.get("PLAYER")
        mins = parse_minutes(p.get("MIN", "0"))

        if not name or mins < 5:
            continue

        score = calculate_fantasy_score(p, weights)

        day_stats.append({
            "player": name,
            "score": score,
            "mins": mins
        })

    if not day_stats:
        continue

    # ---------- TOP 10 ----------
    mvp_pool = [x for x in day_stats if x["mins"] >= 20]
    mvp_pool.sort(key=lambda x: x["score"], reverse=True)
    top10 = [x["player"] for x in mvp_pool[:10]]

    # ---------- WORST 10 ----------
    lvp_pool = [x for x in day_stats if x["mins"] >= 15]
    lvp_pool.sort(key=lambda x: x["score"])
    worst10 = [x["player"] for x in lvp_pool[:10]]

    if PLAYER_NAME in top10 or PLAYER_NAME in worst10:
        print(f"📅 {date}")
        if PLAYER_NAME in top10:
            rank = top10.index(PLAYER_NAME) + 1
            print(f"   🏆 TOP 10 → Rank #{rank}")
        if PLAYER_NAME in worst10:
            rank = worst10.index(PLAYER_NAME) + 1
            print(f"   💔 WORST 10 → Rank #{rank}")

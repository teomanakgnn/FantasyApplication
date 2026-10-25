"""
My League 'Last night': ligdeki her takimin o gece (son mac gunu) oynayan
oyunculari, kutu skor satiri ve fantezi puaniyla. Kendi takimin en ustte.
"""
from datetime import timedelta

from services import league_week as lw
from services.nba_pages import games_on, today_et


def _last_game_day():
    """Biten maci olan en yakin gun (dun, yoksa geriye dogru 5 gun)."""
    day = today_et()
    for back in range(0, 6):
        d = day - timedelta(days=back)
        games = [g for g in games_on(d) if g["final"]]
        if games and (back > 0 or all(g["final"] for g in games_on(d))):
            return d, games
    return None, []


def night(league_id, season, my_team=None):
    from web import stats
    day, games = _last_game_day()
    if not day:
        return None
    box, where = {}, {}
    for g in games:
        for r in stats.boxscore(g["game_id"], final=True) or []:
            if r.get("ID"):
                box[str(r["ID"])] = r
                opp = g["home_team"] if r.get("TEAM") == g["away_team"] else g["away_team"]
                where[str(r["ID"])] = {"game_id": g["game_id"], "opp": opp, "home": r.get("TEAM") == g["home_team"],
                                       "score": f"{g['away_team']} {g['away_score']}-{g['home_score']} {g['home_team']}"}
    data = lw.league_raw(int(league_id), season)
    teams = []
    for t in data.get("teams") or []:
        played = []
        for e in (t.get("roster") or {}).get("entries") or []:
            pl = (e.get("playerPoolEntry") or {}).get("player") or {}
            pid = str(pl.get("id") or "")
            r = box.get(pid)
            if not r:
                continue
            fp = round(stats.fantasy_score(r, stats.BASE_WEIGHTS), 1)
            played.append({"id": pid, "name": pl.get("fullName") or r.get("PLAYER"), "team": r.get("TEAM"), "fp": fp,
                           "slot": e.get("lineupSlotId"), **where[pid],
                           **{k: r.get(k) for k in ("MIN", "PTS", "REB", "AST", "STL", "BLK", "TO", "PF", "FGM", "FGA",
                                                    "3Pts", "3PTA", "FTM", "FTA")}})
        played.sort(key=lambda p: -p["fp"])
        teams.append({"id": t["id"], "name": lw._team_name(t), "players": played, "mine": str(t["id"]) == str(my_team),
                      "fp": round(sum(p["fp"] for p in played), 1),
                      "pts": sum(int(p["PTS"] or 0) for p in played if str(p["PTS"]).isdigit())})
    teams.sort(key=lambda t: (not t["mine"], -t["fp"]))
    return {"day": day, "teams": teams, "games": len(games)}

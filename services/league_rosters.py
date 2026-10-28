"""
Kullanicinin kayitli ESPN liglerindeki tum fantezi takimlarinin kadrolari
(Tier List filtresi icin). Oyuncu kimligi ESPN kimligi: Tier List ve draft
siralamasi da ayni kimligi kullanir.
"""
from services import league_week as lw
from services.espn_league import _team_name
from services.league_insights import PRO_TEAMS, league_data

POS = {1: "PG", 2: "SG", 3: "SF", 4: "PF", 5: "C"}


def league_rosters(leagues):
    """leagues: db.list_leagues satirlari. ESPN disindakiler atlanir; okunamayan lig hata notuyla doner."""
    out = []
    for lg in leagues:
        if lg.get("platform") != "espn":
            continue
        try:
            _, season, _ = league_data(int(lg["league_ref"]))
            data = lw.league_raw(int(lg["league_ref"]), season)
        except Exception as exc:
            print(f"tier rosters: league {lg.get('league_ref')} failed: {exc}")
            out.append({"name": lg.get("name") or "League", "error": True, "teams": []})
            continue
        teams = []
        for t in data.get("teams") or []:
            players = []
            for e in (t.get("roster") or {}).get("entries") or []:
                pl = (e.get("playerPoolEntry") or {}).get("player") or {}
                if not pl.get("id"):
                    continue
                players.append({"id": str(pl["id"]), "name": pl.get("fullName") or "",
                                "team": PRO_TEAMS.get(pl.get("proTeamId"), ""), "pos": POS.get(pl.get("defaultPositionId"), "")})
            teams.append({"id": t["id"], "name": _team_name(t), "mine": str(t["id"]) == str(lg.get("team_id") or ""),
                          "players": players})
        teams.sort(key=lambda t: (not t["mine"], t["name"].lower()))
        out.append({"name": lg.get("name") or (data.get("settings") or {}).get("name") or "League", "teams": teams})
    return out

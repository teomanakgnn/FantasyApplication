"""
NBA Auction yapay zeka hakemi: iki kadroyu Claude'a degerlendirtir.

ANTHROPIC_API_KEY yoksa, gunluk sinir doluysa ya da cagri hata/zaman asimi verirse None
doner ve oyun services/auction.py'nin puanini kullanir: oyun asla hakem yuzunden takilmaz.
Istemde kullanici metni yok: yalnizca kendi havuzumuzdaki oyuncu verisi. Takimlar "Team A"
ve "Team B"; oyuncu adlari yorumda sonradan yerlestirilir.
"""
import asyncio
import json
from datetime import date

import anthropic

import config
from services import auction

TIMEOUT = 30
SYSTEM = """You judge a fantasy basketball auction game. Two players each bought a five-man roster from a pool of NBA players of all eras. Decide which team is better if each player performed at his prime and they played a seven-game series.

Score both teams in these categories, using each category's full range:
- quality (0-45): overall talent, with stars counting most
- fit (0-15): can these five actually share a floor, positions and roles
- spacing (0-10): shooting and floor spacing
- playmaking (0-10): shot creation and passing
- defense (0-12): perimeter and rim defense
- rebounding (0-4)
- balance (0-4): enough touches to go round, no glaring role gaps

The analytics baseline in the request comes from a formula that knows nothing about how players actually fit together. Start from it and move scores where your basketball judgment disagrees, for example a non-shooter who still thrives inside a lineup, or two ball-dominant stars who overlap. Keep the scoring fair and consistent across both teams.

Each team's note is one sentence on its defining strength or flaw. The verdict is two or three sentences explaining who wins and why, naming specific players. Refer to the teams only as "Team A" and "Team B". Write in plain English for a basketball fan, with no markdown."""

_TEAM = {"type": "object", "additionalProperties": False,
         "required": ["quality", "fit", "spacing", "playmaking", "defense", "rebounding", "balance", "note"],
         "properties": {**{k: {"type": "number"} for k, _, _ in auction.CATEGORIES}, "note": {"type": "string"}}}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["team_a", "team_b", "verdict"],
          "properties": {"team_a": _TEAM, "team_b": _TEAM, "verdict": {"type": "string"}}}

_client = None
_used = {"day": None, "n": 0}


def enabled():
    return bool(config.ANTHROPIC_API_KEY)


def _take_budget():
    """Gunluk sinir: acik uclu bir oyun API faturasini buyutmesin."""
    today = date.today().isoformat()
    if _used["day"] != today:
        _used.update(day=today, n=0)
    if _used["n"] >= config.AUCTION_AI_DAILY:
        return False
    _used["n"] += 1
    return True


def _team_brief(label, seat, team):
    players = []
    for row in team["lineup"]:
        if row.get("filler"):
            players.append({"slot": row["slot"], "name": "Replacement-level player"})
            continue
        p = auction.player(row["id"])
        players.append({"slot": row["slot"], "name": p["name"], "natural_position": p["pos"], "career_years": f"{p['y0']}-{p['y1']}",
                        "career_ppg": p["pts"], "career_rpg": p["reb"], "career_apg": p["ast"], "all_star": p["as"],
                        "rings": p["ring"], "mvp": p["mvp"], "rating_of_99": p["ovr"], "shooting_of_100": p["sht"],
                        "defense_of_100": p["dfn"], "paid": row["price"]})
    return {"team": label, "players": players, "baseline": {c["k"]: c["v"] for c in team["cats"]},
            "real_life_teammates": team["mates"], "money_left": seat["money"]}


def _apply(res, data):
    """Yanit gecerliyse sonucu gunceller; sayilar kategori sinirlarina kirpilir."""
    out = {"teams": [], "by": "ai", "verdict": str(data["verdict"]).strip()}
    for team, key in zip(res["teams"], ("team_a", "team_b")):
        got = data[key]
        cats = [{"k": c["k"], "label": c["label"], "max": c["max"], "v": round(max(0.0, min(float(c["max"]), float(got[c["k"]]))), 1)}
                for c in team["cats"]]
        t = dict(team, cats=cats, note=str(got["note"]).strip())
        t["total"] = round(min(100.0, sum(c["v"] for c in cats) + team["chemistry"]), 1)
        out["teams"].append(t)
    return auction.decide(out)


async def judge(game, res):
    """AI sonucu ya da None (motor sonucu kalir)."""
    global _client
    if not enabled() or not _take_budget():
        return None
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY, timeout=TIMEOUT, max_retries=1)
    brief = [_team_brief(n, s, t) for n, s, t in zip(("Team A", "Team B"), game["seats"], res["teams"])]
    # Reddedilen istek yedek modelde yeniden calisir; Haiku'da bu yedek yok
    fallback = {} if "haiku" in config.AUCTION_AI_MODEL else {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    try:
        msg = await asyncio.wait_for(_client.beta.messages.create(
            model=config.AUCTION_AI_MODEL, max_tokens=8000, **fallback,
            system=SYSTEM, output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": json.dumps(brief, ensure_ascii=False)}]), TIMEOUT + 5)
        if msg.stop_reason != "end_turn":
            print(f"auction judge stopped: {msg.stop_reason}")
            return None
        text = next(b.text for b in msg.content if b.type == "text")
        return _apply(res, json.loads(text))
    except asyncio.TimeoutError:
        print("auction judge timed out")
    except anthropic.APIStatusError as exc:
        print(f"auction judge API error {exc.status_code}: {exc.message}")
    except anthropic.APIConnectionError as exc:
        print(f"auction judge connection error: {exc}")
    except (ValueError, KeyError, StopIteration, TypeError) as exc:
        print(f"auction judge bad response: {exc}")
    return None

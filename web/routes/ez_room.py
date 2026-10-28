"""
82-0 arkadas odasi: odadaki herkes ayni bes cevirmeyle (ayni tohum) ayni anda
kadrosunu kurar; bitiren kadrosunu gonderir, sunucu dogrulayip puanlar. Herkes
bitirince en iyi kadro (takim puani) kazanir. Sohbet ve canli ilerleme WebSocket'le.

  POST /api/82-0/room            oda kur (donem, kolay mod)
  GET  /82-0/room/{code}         oyun sayfasi (oda modunda)
  GET  /api/82-0/room/{code}     bu turun cevirmeleri
  WS   /ws/82-0/{code}           katil, ilerleme, gonder, sohbet, yeni tur

Odalar bellekte (tek makine); hesap gerekmez: ad + tarayicidaki rastgele kimlik.
"""
import json
import re
import secrets
import time

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

import config
from services import eighty_two as e82
from web.core import current_user, render

router = APIRouter()
ROOM_TTL = 6 * 3600
MAX_PLAYERS = 8
CODE_RE = re.compile(r"^[A-Za-z0-9]{6,12}$")
_rooms = {}


def _bad(message, status=400):
    return JSONResponse({"error": message}, status_code=status)


def _new_round(room):
    room["round"] = room.get("round", 0) + 1
    room["seed"] = "room-" + secrets.token_hex(6)
    room["results"] = {}
    room["progress"] = {}


def _cleanup():
    now = time.time()
    for code, r in list(_rooms.items()):
        if not r["conns"] and now - r["touched"] > ROOM_TTL:
            _rooms.pop(code, None)


def score(spins, lineup, choice, easy):
    """
    Gonderilen kadroyu dogrula ve puanla. lineup: {slot: {"spin": i, "id": oyuncu}},
    choice: {i: "t"|"y"|"ty"|"yt"} (o cevirmede kullanilan yeniden cevirme haklari).
    Her cevirmeden tam bir oyuncu; oyuncu o cevirmenin ekrandaki takiminda olmali.
    """
    if set(lineup or {}) != set(e82.SLOTS):
        return None, "Fill all five spots."
    choice = {str(k): str(v) for k, v in (choice or {}).items()}
    if any(v not in ("t", "y", "ty", "yt") for v in choice.values()):
        return None, "Bad re-roll."
    joined = "".join(choice.values())
    if joined.count("t") > 1 or joined.count("y") > 1:
        return None, "Only one re-roll of each kind."
    spins_used = sorted(int((lineup[s] or {}).get("spin", -1)) for s in e82.SLOTS)
    if spins_used != list(range(e82.SPINS)):
        return None, "One player from each spin."
    rows, ids = [], set()
    for slot in e82.SLOTS:
        x = lineup[slot]
        i = int(x["spin"])
        view = spins[i][choice.get(str(i)) or "main"]
        p = next((p for p in view["players"] if p["id"] == str(x.get("id"))), None)
        if not p or p["id"] in ids:
            return None, "That player was not on the team you spun."
        ids.add(p["id"])
        eff = p["ovr"] - (0 if p["pos"] in e82.FITS[slot] else e82.OFF_POSITION)
        rows.append({"slot": slot, "id": p["id"], "name": p["name"], "pos": p["pos"], "team": view["abbr"],
                     "season": p["season"], "ovr": eff})
    r = e82.rating([x["ovr"] for x in rows])
    return {"rating": round(r, 2), "wins": e82.wins_for(r), "lineup": rows}, None


# ==================== SAYFALAR / API ====================

@router.post("/api/82-0/room")
async def room_create(request: Request):
    b = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    _cleanup()
    span = int(b.get("span") or 1) if str(b.get("span") or "1").isdigit() else 1
    code = secrets.token_hex(4)
    room = {"span": span if span in e82.SPANS else 1, "easy": bool(b.get("easy")), "seats": {}, "conns": {},
            "chat": [], "created": time.time(), "touched": time.time()}
    _new_round(room)
    _rooms[code] = room
    return {"code": code, "url": f"/82-0/room/{code}"}


@router.get("/82-0/room/{code}")
def room_page(request: Request, code: str):
    room = _rooms.get(code) if CODE_RE.match(code) else None
    payload = {"puzzle": e82.puzzle_number(), "config": e82.config(), "signed_in": bool(current_user(request)),
               "room": {"code": code, "exists": bool(room), "span": room["span"] if room else 1,
                        "easy": room["easy"] if room else False,
                        "me": (current_user(request) or {}).get("username") or ""}}
    # Davet linkiyle gelen misafir "gunde bir oyun" kapisina takilmasin: ayri etkin sayfa adi
    return render(request, "eighty_two.html", active="eightytwo-room", payload=json.dumps(payload).replace("</", "<\\/"),
                  puzzle=None, room=code)


@router.get("/api/82-0/room/{code}")
def room_spins(code: str):
    room = _rooms.get(code)
    if not room:
        return _bad("This room has ended.", 404)
    return {"round": room["round"], "span": room["span"], "easy": room["easy"],
            "spins": e82.game(room["seed"], room["span"])}


# ==================== CANLI ====================

async def _send(ws, obj):
    try:
        await ws.send_text(json.dumps(obj))
    except Exception:
        pass


def _public(room, viewer=None):
    """
    Kisiye ozel gorunum. Baskasinin kadrosu ve puani yalnizca izleyen kendi kadrosunu
    gonderdiyse ya da herkes bitirdiyse gorunur (yoksa ortak cevirmelerdeki gizli
    OVR'ler oyun bitmeden ogrenilirdi).
    """
    online = {c["cid"] for c in room["conns"].values()}
    seats = room["seats"]
    playing = [cid for cid in seats if cid in online or cid in room["results"]]
    everyone_done = bool(playing) and all(cid in room["results"] for cid in playing) and len(room["results"]) >= 1
    players = []
    can_see = everyone_done or viewer in room["results"]
    for cid, s in seats.items():
        res = room["results"].get(cid)
        if res and cid != viewer and not can_see:
            res = {"wins": None, "rating": None, "lineup": None, "hidden": True}
        players.append({"cid": cid, "name": s["name"], "online": cid in online, "done": cid in room["results"],
                        "you": cid == viewer,
                        "progress": room["progress"].get(cid, 0),
                        "wins": res["wins"] if res else None, "rating": res["rating"] if res else None,
                        "lineup": res["lineup"] if res else None})
    players.sort(key=lambda p: (-(p["rating"] if p["rating"] is not None else -1), p["name"].lower()))
    best = max((p["rating"] for p in players if p["rating"] is not None), default=None)
    winners = [p["name"] for p in players if p["rating"] is not None and p["rating"] == best] if everyone_done else []
    return {"t": "state", "round": room["round"], "span": room["span"], "easy": room["easy"], "players": players,
            "all_done": everyone_done, "winners": winners}


async def _broadcast(room, obj):
    for c in list(room["conns"].values()):
        await _send(c["ws"], obj)


async def _broadcast_state(room):
    for c in list(room["conns"].values()):
        await _send(c["ws"], _public(room, c["cid"]))


def _clean_name(raw):
    name = re.sub(r"[^\w .\-]", "", str(raw or ""), flags=re.UNICODE).strip()[:20]
    return name if len(name) >= 2 else None


@router.websocket("/ws/82-0/{code}")
async def room_ws(ws: WebSocket, code: str):
    origin = ws.headers.get("origin") or ""
    if config.PRODUCTION and origin and origin.rstrip("/") != config.SITE_URL.rstrip("/"):
        await ws.close(code=4403)
        return
    room = _rooms.get(code)
    await ws.accept()
    if not room:
        await _send(ws, {"t": "gone"})
        await ws.close()
        return
    conn_id = secrets.token_hex(6)
    conn = None
    try:
        while True:
            raw = await ws.receive_text()
            if len(raw) > 8000:
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            t = msg.get("t")
            room["touched"] = time.time()
            if t == "hello":
                cid = str(msg.get("cid") or "")[:40]
                name = _clean_name(msg.get("name"))
                if len(cid) < 8 or not name:
                    await _send(ws, {"t": "error", "text": "Pick a name (2+ letters)."})
                    continue
                if cid not in room["seats"] and len(room["seats"]) >= MAX_PLAYERS:
                    await _send(ws, {"t": "error", "text": f"This room is full ({MAX_PLAYERS} players)."})
                    continue
                conn = {"ws": ws, "cid": cid, "name": name}
                room["conns"][conn_id] = conn
                room["seats"][cid] = {"name": name}
                await _send(ws, {"t": "chatlog", "items": room["chat"][-50:]})
                await _broadcast_state(room)
            elif not conn:
                continue
            elif t == "progress":
                try:
                    room["progress"][conn["cid"]] = max(0, min(5, int(msg.get("n") or 0)))
                except (TypeError, ValueError):
                    continue
                await _broadcast_state(room)
            elif t == "submit":
                if int(msg.get("round") or 0) != room["round"]:
                    await _send(ws, {"t": "error", "text": "A new round started - your lineup was for the last one."})
                    continue
                if conn["cid"] in room["results"]:
                    continue
                res, err = score(e82.game(room["seed"], room["span"]), msg.get("lineup"), msg.get("choice"), room["easy"])
                if err:
                    await _send(ws, {"t": "error", "text": err})
                    continue
                room["results"][conn["cid"]] = res
                room["progress"][conn["cid"]] = 5
                await _broadcast_state(room)
            elif t == "next":
                st = _public(room, conn["cid"])
                if not st["all_done"]:
                    await _send(ws, {"t": "error", "text": "Wait until everyone has finished."})
                    continue
                _new_round(room)
                await _broadcast(room, {"t": "round", "round": room["round"], "by": conn["name"]})
                await _broadcast_state(room)
            elif t == "chat":
                text = re.sub(r"\s+", " ", str(msg.get("text") or "")).strip()[:300]
                now = time.time()
                if not text or now - conn.get("last_chat", 0) < 0.7:
                    continue
                conn["last_chat"] = now
                item = {"name": conn["name"], "text": text, "ts": int(now)}
                room["chat"] = (room["chat"] + [item])[-80:]
                await _broadcast(room, {"t": "chat", **item})
            elif t == "ping":
                await _send(ws, {"t": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"82-0 room ws error: {exc}")
    finally:
        room["conns"].pop(conn_id, None)
        if room["conns"]:
            await _broadcast_state(room)

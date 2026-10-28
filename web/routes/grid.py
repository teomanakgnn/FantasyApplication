"""
3x3 Grid sayfalari ve API'si (oyun mantigi services/grid.py).

  /grid                 gunluk grid, bota karsi XOX, arkadas daveti
  /grid/room/{code}     arkadasla canli XOX + sohbet (WebSocket /ws/grid/{code})

Canli odalar bellekte (tek makine). Hesap gerekmez: kisi bir ad secer, tarayicida
rastgele bir kimlik (cid) tutulur; baglanti koparsa ayni koltuga doner.
"""
import asyncio
import json
import re
import secrets
import time

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

import config
from services import daily_player as daily
from services import grid
from web.core import current_user, render

router = APIRouter()
TURN_SECS = 40
ROOM_TTL = 6 * 3600
CODE_RE = re.compile(r"^[A-Za-z0-9_-]{6,14}$")


def _bad(message, status=400):
    return JSONResponse({"error": message}, status_code=status)


def _json(obj):
    return json.dumps(obj).replace("</", "<\\/")


def _practice_seed():
    return "p-" + secrets.token_hex(5)


# ==================== SAYFALAR ====================

@router.get("/grid")
def grid_page(request: Request):
    g = grid.daily()
    payload = {"mode": "home", "puzzle": grid.puzzle_number(), "daily": grid.public(g) if g else None,
               "guesses": grid.GUESSES, "next_in": daily.seconds_to_next(), "signed_in": bool(current_user(request)),
               "max_turns": grid.MAX_TURNS, "turn_secs": TURN_SECS}
    return render(request, "grid.html", active="grid", payload=_json(payload), ready=bool(g), puzzle=payload["puzzle"],
                  room=None)


@router.get("/grid/room/{code}")
def grid_room_page(request: Request, code: str):
    if not CODE_RE.match(code):
        return render(request, "grid.html", active="grid", payload=_json({"mode": "gone"}), ready=True, puzzle=None, room=None)
    room = _rooms.get(code)
    payload = {"mode": "room", "room": code, "exists": bool(room), "max_turns": grid.MAX_TURNS, "turn_secs": TURN_SECS,
               "me": (current_user(request) or {}).get("username") or ""}
    # Davet linkiyle gelen misafir "gunde bir oyun" kapisina takilmasin: ayri etkin sayfa adi
    return render(request, "grid.html", active="grid-room", payload=_json(payload), ready=True, puzzle=None, room=code)


# ==================== API ====================

@router.get("/api/grid/players")
def grid_players():
    return JSONResponse({"players": grid.player_list()}, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/api/grid/new")
def grid_new():
    for _ in range(5):
        seed = _practice_seed()
        g = grid.by_seed(seed)
        if g:
            return grid.public(g)
    return _bad("Could not build a grid. Try again.")


@router.post("/api/grid/check")
async def grid_check(request: Request):
    b = await request.json()
    g = grid.by_seed(str(b.get("seed") or ""))
    if not g:
        return _bad("Unknown grid.")
    try:
        cell = int(b.get("cell"))
    except (TypeError, ValueError):
        return _bad("Unknown cell.")
    res = grid.check(g, cell, str(b.get("pid") or ""))
    return _bad(res["error"]) if "error" in res else res


@router.get("/api/grid/reveal")
def grid_reveal(seed: str):
    g = grid.by_seed(seed)
    return {"cells": grid.reveal(g)} if g else _bad("Unknown grid.")


@router.post("/api/grid/bot")
async def grid_bot(request: Request):
    b = await request.json()
    g = grid.by_seed(str(b.get("seed") or ""))
    board = b.get("board") or []
    if not g or len(board) != 9:
        return _bad("Unknown game.")
    board = [x if x in ("X", "O") else None for x in board]
    move = grid.bot_move(g, board, b.get("used") or [], me="O", level=str(b.get("level") or "medium"),
                         seed=f"{g['seed']}-{b.get('turn', 0)}-{secrets.randbits(16)}")
    return move or _bad("No move left.")


@router.post("/api/grid/room")
def grid_room_create():
    _cleanup()
    code = secrets.token_urlsafe(6).replace("_", "x").replace("-", "y")[:8]
    g = None
    for _ in range(5):
        g = grid.by_seed(_practice_seed())
        if g:
            break
    if not g:
        return _bad("Could not build a grid. Try again.")
    _rooms[code] = _new_room(g)
    return {"code": code, "url": f"/grid/room/{code}"}


# ==================== CANLI ODA ====================

_rooms = {}
_ticker = None


def _new_room(g, first="X"):
    return {"grid": g, "seats": {"X": None, "O": None}, "board": [None] * 9, "cards": [None] * 9, "turn": first,
            "turns": 0, "used": set(), "result": None, "deadline": None, "chat": [], "conns": {},
            "created": time.time(), "touched": time.time(), "rematch": set(), "first": first, "log": []}


def _cleanup():
    now = time.time()
    for code, r in list(_rooms.items()):
        if not r["conns"] and now - r["touched"] > ROOM_TTL:
            _rooms.pop(code, None)


def _view(room, conn):
    side = next((s for s, seat in room["seats"].items() if seat and seat["cid"] == conn["cid"]), None)
    left = max(0, int(room["deadline"] - time.time())) if room["deadline"] and not room["result"] else None
    return {"t": "state", "grid": grid.public(room["grid"]), "board": room["board"], "cards": room["cards"],
            "turn": room["turn"], "turns": room["turns"], "result": room["result"], "left": left,
            "seats": {s: (seat["name"] if seat else None) for s, seat in room["seats"].items()},
            "online": {s: bool(seat and any(c["cid"] == seat["cid"] for c in room["conns"].values()))
                       for s, seat in room["seats"].items()},
            "you": side, "watchers": sum(1 for c in room["conns"].values()
                                        if not any(seat and seat["cid"] == c["cid"] for seat in room["seats"].values())),
            "rematch": sorted(room["rematch"]), "log": room["log"][-6:]}


async def _send(ws, obj):
    try:
        await ws.send_text(json.dumps(obj))
    except Exception:
        pass


async def _broadcast_state(room):
    for c in list(room["conns"].values()):
        await _send(c["ws"], _view(room, c))


async def _broadcast(room, obj):
    for c in list(room["conns"].values()):
        await _send(c["ws"], obj)


def _started(room):
    return bool(room["seats"]["X"] and room["seats"]["O"])


def _next_turn(room):
    room["turns"] += 1
    room["turn"] = "O" if room["turn"] == "X" else "X"
    room["result"] = grid.final_result(room["board"], room["turns"])
    room["deadline"] = None if room["result"] else time.time() + TURN_SECS


async def _tick():
    """Sure dolan hamle: sira karsi tarafa gecer."""
    while True:
        await asyncio.sleep(1)
        now = time.time()
        for room in list(_rooms.values()):
            if room["deadline"] and not room["result"] and now > room["deadline"]:
                who = room["turn"]
                room["log"].append({"side": who, "text": "ran out of time"})
                _next_turn(room)
                await _broadcast_state(room)


def _clean_name(raw):
    name = re.sub(r"[^\w .\-]", "", str(raw or ""), flags=re.UNICODE).strip()[:20]
    return name if len(name) >= 2 else None


@router.websocket("/ws/grid/{code}")
async def grid_ws(ws: WebSocket, code: str):
    global _ticker
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
    if _ticker is None or _ticker.done():
        _ticker = asyncio.create_task(_tick())
    conn_id = secrets.token_hex(6)
    conn = None
    try:
        while True:
            raw = await ws.receive_text()
            if len(raw) > 4000:
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
                conn = {"ws": ws, "cid": cid, "name": name}
                room["conns"][conn_id] = conn
                seat = next((s for s, x in room["seats"].items() if x and x["cid"] == cid), None)
                if seat:
                    room["seats"][seat]["name"] = name
                else:
                    free = next((s for s in ("X", "O") if not room["seats"][s]), None)
                    if free:
                        room["seats"][free] = {"cid": cid, "name": name}
                        if _started(room) and room["deadline"] is None and not room["result"]:
                            room["deadline"] = time.time() + TURN_SECS
                await _send(ws, {"t": "chatlog", "items": room["chat"][-50:]})
                await _broadcast_state(room)
            elif not conn:
                continue
            elif t == "guess":
                side = next((s for s, x in room["seats"].items() if x and x["cid"] == conn["cid"]), None)
                if not side or room["result"] or not _started(room):
                    continue
                if side != room["turn"]:
                    await _send(ws, {"t": "error", "text": "Not your turn."})
                    continue
                try:
                    cell = int(msg.get("cell"))
                except (TypeError, ValueError):
                    continue
                pid = str(msg.get("pid") or "")
                if not 0 <= cell <= 8 or room["board"][cell]:
                    await _send(ws, {"t": "error", "text": "That square is taken."})
                    continue
                if pid in room["used"]:
                    await _send(ws, {"t": "error", "text": "That player was already used."})
                    continue
                res = grid.check(room["grid"], cell, pid)
                if "error" in res:
                    await _send(ws, {"t": "error", "text": res["error"]})
                    continue
                if res["ok"]:
                    room["board"][cell], room["cards"][cell] = side, res["player"]
                    room["used"].add(pid)
                room["log"].append({"side": side, "cell": cell, "ok": res["ok"], "player": res["player"]["name"]})
                _next_turn(room)
                await _broadcast(room, {"t": "move", "side": side, "cell": cell, "ok": res["ok"], "player": res["player"]})
                await _broadcast_state(room)
            elif t == "chat":
                text = re.sub(r"\s+", " ", str(msg.get("text") or "")).strip()[:300]
                if not text:
                    continue
                now = time.time()
                if now - conn.get("last_chat", 0) < 0.7:
                    continue
                conn["last_chat"] = now
                side = next((s for s, x in room["seats"].items() if x and x["cid"] == conn["cid"]), None)
                item = {"name": conn["name"], "side": side, "text": text, "ts": int(now)}
                room["chat"] = (room["chat"] + [item])[-80:]
                await _broadcast(room, {"t": "chat", **item})
            elif t == "rematch":
                side = next((s for s, x in room["seats"].items() if x and x["cid"] == conn["cid"]), None)
                if not side or not room["result"]:
                    continue
                room["rematch"].add(side)
                if room["rematch"] >= {"X", "O"}:
                    g = None
                    for _ in range(5):
                        g = grid.by_seed(_practice_seed())
                        if g:
                            break
                    if g:
                        first = "O" if room["first"] == "X" else "X"
                        fresh = _new_room(g, first)
                        fresh.update({"seats": room["seats"], "chat": room["chat"], "conns": room["conns"],
                                      "deadline": time.time() + TURN_SECS})
                        room.clear()
                        room.update(fresh)
                        await _broadcast(room, {"t": "info", "text": f"New grid - {first} starts."})
                await _broadcast_state(room)
            elif t == "ping":
                await _send(ws, {"t": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"grid ws error: {exc}")
    finally:
        room["conns"].pop(conn_id, None)
        if room["conns"]:
            await _broadcast_state(room)

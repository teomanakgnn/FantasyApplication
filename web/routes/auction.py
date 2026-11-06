"""
NBA Auction: arkadasla canli oda ya da bota karsi. Her iki mod ayni sunucu motorunu
kullanir (services/auction.py); solo odada ikinci koltukta bot oturur.

  GET  /auction                 giris sayfasi
  POST /api/auction/room        oda kur ({"solo": true} bota karsi)
  GET  /auction/room/{code}     oyun sayfasi
  WS   /ws/auction/{code}       katil, teklif, sal, sohbet, rovans

Odalar bellekte (tek makine); hesap gerekmez: ad + tarayicidaki rastgele kimlik.
"""
import asyncio
import json
import random
import re
import secrets
import time

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

import config
from services import auction, auction_judge
from web.core import current_user, render

router = APIRouter()
ROOM_TTL = 2 * 3600
MAX_ROOMS = 3000
TURN_SECS = 20
BOT_NAME = "HoopBot"
CODE_RE = re.compile(r"^[A-Za-z0-9]{6,12}$")
_rooms = {}
_ticker = None


def _bad(message, status=400):
    return JSONResponse({"error": message}, status_code=status)


def _cleanup():
    now = time.time()
    for code, r in list(_rooms.items()):
        if not r["conns"] and now - r["touched"] > ROOM_TTL:
            _rooms.pop(code, None)


def _new_game(room):
    room["round"] = room.get("round", 0) + 1
    room["game"] = auction.new_game(secrets.token_hex(6), opener=room["round"] % 2, blind=room["blind"], scoring=room["scoring"])
    room.update({"phase": "waiting", "deadline": None, "bot_at": None, "result": None})


def _begin(room):
    room["phase"] = "live"
    _arm_turn(room)


def _arm_turn(room):
    """Her hamleden sonra: saat yeniden, sira botta ise dusunme suresi."""
    now = time.time()
    g = room["game"]
    room["deadline"] = now + TURN_SECS
    room["bot_at"] = now + random.uniform(1.0, 2.6) if room.get("bot_seat") == g["turn"] else None


@router.get("/auction")
def auction_page(request: Request):
    payload = {"room": None, "me": (current_user(request) or {}).get("username") or "", "secs": TURN_SECS,
               "money": auction.START_MONEY, "roster": auction.ROSTER, "signed_in": bool(current_user(request))}
    return render(request, "auction.html", active="auction", payload=json.dumps(payload).replace("</", "<\\/"), room=None)


@router.post("/api/auction/room")
async def room_create(request: Request):
    b = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    _cleanup()
    if len(_rooms) >= MAX_ROOMS:
        return _bad("Too many games running right now. Try again shortly.", 503)
    code = secrets.token_hex(4)
    b = b if isinstance(b, dict) else {}
    solo = bool(b.get("solo"))
    scoring = b.get("scoring") if b.get("scoring") in auction.SCORINGS else "judge"
    room = {"solo": solo, "blind": bool(b.get("blind")), "scoring": scoring, "bot_seat": 1 if solo else None, "seats": {}, "names": [None, BOT_NAME if solo else None],
            "conns": {}, "chat": [], "touched": time.time()}
    _new_game(room)
    _rooms[code] = room
    return {"code": code, "url": f"/auction/room/{code}"}


@router.get("/auction/room/{code}")
def room_page(request: Request, code: str):
    room = _rooms.get(code) if CODE_RE.match(code) else None
    payload = {"room": {"code": code, "exists": bool(room), "solo": bool(room and room["solo"])},
               "me": (current_user(request) or {}).get("username") or "", "secs": TURN_SECS,
               "money": auction.START_MONEY, "roster": auction.ROSTER, "signed_in": bool(current_user(request))}
    return render(request, "auction.html", active="auction", payload=json.dumps(payload).replace("</", "<\\/"), room=code)


# ==================== CANLI ====================

async def _send(ws, obj):
    try:
        await ws.send_text(json.dumps(obj))
    except Exception:
        pass


def _team_public(room, seat):
    s = room["game"]["seats"][seat]
    roster = [{**auction.card(x["id"]), "price": x["price"]} for x in s["roster"]]
    return {"seat": seat, "name": room["names"][seat], "money": s["money"], "roster": roster,
            "online": seat == room.get("bot_seat") or any(c["seat"] == seat for c in room["conns"].values())}


def _public(room, viewer_seat):
    g = room["game"]
    now = time.time()
    pid = auction.current(g)
    live = room["phase"] == "live"
    me = viewer_seat
    my_turn = live and me is not None and g["turn"] == me
    limit = auction.max_bid(g, me) if my_turn else 0
    # Kor draftta oyuncu satilana kadar sunucudan cikmaz: yalnizca kategori
    lot = None
    if pid and live:
        lot = {"blind": True, "category": auction.current_label(g)} if g["blind"] else auction.card(pid)
    events = [dict(e, seat_name=room["names"][e["seat"]] if e.get("seat") is not None else None) for e in g["events"][-14:]]
    return {"t": "state", "round": room["round"], "phase": room["phase"], "solo": room["solo"], "you": me,
            "teams": [_team_public(room, 0), _team_public(room, 1)], "turn": g["turn"] if live else None,
            "lot": lot, "blind": room["blind"], "scoring": room["scoring"], "can_give": bool(my_turn and auction.can_give(g, me)),
            "lot_no": g["i"] + 1, "lots": len(g["lots"]), "bid": g["bid"], "bidder": g["bidder"], "limit": limit,
            "left": round(room["deadline"] - now, 2) if live and room["deadline"] else None, "secs": TURN_SECS,
            "events": events, "result": room["result"], "ai_on": auction_judge.enabled()}


async def _broadcast(room, obj, skip=None):
    for k, c in list(room["conns"].items()):
        if k != skip:
            await _send(c["ws"], obj)


async def _broadcast_state(room):
    for c in list(room["conns"].values()):
        await _send(c["ws"], _public(room, c["seat"]))


def _named_verdict(res, room):
    a, b = room["names"][0] or "Team A", room["names"][1] or "Team B"
    res["verdict"] = res["verdict"].replace("Team A", a).replace("Team B", b)
    return res


async def _judge(room, round_no):
    """Motor sonucu hazir; hakem varsa uzerine yazar. Oda bu arada yeni tura gectiyse atilir."""
    base = auction.result(room["game"])
    verdict = None
    if room["scoring"] == "judge":
        try:
            verdict = await auction_judge.judge(room["game"], base)
        except Exception as exc:
            print(f"auction judge failed: {exc}")
    if room["round"] != round_no:
        return
    room["result"] = _named_verdict(verdict or base, room)
    room["phase"] = "done"
    await _broadcast_state(room)


async def _after_move(room):
    if room["game"]["over"]:
        room["phase"] = "judging"
        room["deadline"] = None
        asyncio.create_task(_judge(room, room["round"]))
    else:
        _arm_turn(room)
    await _broadcast_state(room)


async def _tick():
    while True:
        await asyncio.sleep(0.4)
        now = time.time()
        for room in list(_rooms.values()):
            if room["phase"] != "live" or not room["conns"]:
                continue
            g = room["game"]
            if room.get("bot_at") and now >= room["bot_at"] and g["turn"] == room["bot_seat"]:
                kind, amount = auction.bot_move(g, room["bot_seat"])
                if kind == "bid":
                    auction.bid(g, room["bot_seat"], amount)
                else:
                    auction.pass_turn(g, room["bot_seat"])
                await _after_move(room)
            elif room["deadline"] and now > room["deadline"] + 0.8:
                auction.timeout_move(g)
                await _after_move(room)


def _clean_name(raw):
    name = re.sub(r"[^\w .\-]", "", str(raw or ""), flags=re.UNICODE).strip()[:20]
    return name if len(name) >= 2 else None


def _seat_for(room, cid):
    if cid in room["seats"]:
        return room["seats"][cid]
    taken = set(room["seats"].values())
    if room.get("bot_seat") is not None:
        taken.add(room["bot_seat"])
    free = [i for i in (0, 1) if i not in taken]
    return free[0] if free else None


@router.websocket("/ws/auction/{code}")
async def room_ws(ws: WebSocket, code: str):
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
            if len(raw) > 2000:
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(msg, dict):
                continue
            t = msg.get("t")
            room["touched"] = time.time()
            if t == "hello":
                cid = str(msg.get("cid") or "")[:40]
                name = _clean_name(msg.get("name"))
                if len(cid) < 8 or not name:
                    await _send(ws, {"t": "error", "text": "Pick a name (2+ letters)."})
                    continue
                seat = _seat_for(room, cid)
                if seat is None:
                    await _send(ws, {"t": "error", "text": "This game already has two players."})
                    continue
                if name == room["names"][1 - seat]:
                    name = f"{name} 2"[:20]
                conn = {"ws": ws, "cid": cid, "seat": seat, "name": name}
                room["conns"][conn_id] = conn
                room["seats"][cid] = seat
                room["names"][seat] = name
                await _send(ws, {"t": "chatlog", "items": room["chat"][-50:]})
                await _broadcast(room, {"t": "joined", "name": name}, skip=conn_id)
                if room["phase"] == "waiting" and all(room["names"]):
                    _begin(room)
                await _broadcast_state(room)
            elif not conn:
                continue
            elif t in ("bid", "pass"):
                if room["phase"] != "live":
                    continue
                if int(msg.get("round") or 0) != room["round"] or int(msg.get("lot") or 0) != room["game"]["i"] + 1:
                    continue                            # gecikmeli tiklama: baska bir oyuncuya gitmesin
                g = room["game"]
                ok, err = auction.bid(g, conn["seat"], msg.get("amount")) if t == "bid" else auction.pass_turn(g, conn["seat"])
                if not ok:
                    await _send(ws, {"t": "error", "text": err})
                    continue
                await _after_move(room)
            elif t == "next":
                if room["phase"] != "done":
                    continue
                _new_game(room)
                if all(room["names"]):
                    _begin(room)
                await _broadcast(room, {"t": "round", "by": conn["name"]})
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
        print(f"auction ws error: {exc}")
    finally:
        room["conns"].pop(conn_id, None)
        if room["conns"]:
            await _broadcast_state(room)

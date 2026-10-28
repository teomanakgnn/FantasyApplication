"""
82-0 arkadas odasi: odadaki herkes ayni bes cevirmeyle (ayni tohum) ayni anda
kadrosunu kurar. Tur herkes icin ayni anda baslar (3 sn geri sayim) ve tum secimler
icin toplam ROUND_SECS saniye vardir; sure dolunca kadrolar oldugu gibi kilitlenir
(bos mevki = FILLER_OVR'lik yedek). Her secim aninda sunucuya gider ve dogrulanir;
rakipler secimleri canli gorur (OVR'ler tur bitene kadar gizli). En iyi kadro kazanir.

  POST /api/82-0/room            oda kur (donem, kolay mod)
  GET  /82-0/room/{code}         oyun sayfasi (oda modunda)
  GET  /api/82-0/room/{code}     bu turun cevirmeleri
  WS   /ws/82-0/{code}           katil, kadro, baslat, sohbet, yeni tur

Odalar bellekte (tek makine); hesap gerekmez: ad + tarayicidaki rastgele kimlik.
"""
import asyncio
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
ROUND_SECS = 90
COUNTDOWN = 3
GRACE = 2                 # ag gecikmesi icin son saniyelerde gelen secimler
FILLER_OVR = 45           # sure dolunca bos kalan mevki
CODE_RE = re.compile(r"^[A-Za-z0-9]{6,12}$")
_rooms = {}
_ticker = None


def _bad(message, status=400):
    return JSONResponse({"error": message}, status_code=status)


def _new_round(room):
    room["round"] = room.get("round", 0) + 1
    room["seed"] = "room-" + secrets.token_hex(6)
    room["spins"] = e82.game(room["seed"], room["span"])
    room.update({"results": {}, "partial": {}, "phase": "waiting", "start_at": None, "deadline": None,
                 "players_in": set()})


def _cleanup():
    now = time.time()
    for code, r in list(_rooms.items()):
        if not r["conns"] and now - r["touched"] > ROOM_TTL:
            _rooms.pop(code, None)


def score(spins, lineup, choice, partial=False):
    """
    Kadroyu dogrula ve puanla. lineup: {slot: {"spin": i, "id": oyuncu}},
    choice: {i: "t"|"y"|"ty"|"yt"} (o cevirmede kullanilan yeniden cevirme haklari).
    Her cevirmeden en fazla bir oyuncu; oyuncu o cevirmenin ekrandaki takiminda olmali.
    partial: eksik mevki olabilir (puanda FILLER_OVR).
    """
    lineup = lineup or {}
    if not set(lineup) <= set(e82.SLOTS):
        return None, "Unknown spot."
    if not partial and set(lineup) != set(e82.SLOTS):
        return None, "Fill all five spots."
    choice = {str(k): str(v) for k, v in (choice or {}).items()}
    if any(v not in ("t", "y", "ty", "yt") for v in choice.values()):
        return None, "Bad re-roll."
    joined = "".join(choice.values())
    if joined.count("t") > 1 or joined.count("y") > 1:
        return None, "Only one re-roll of each kind."
    try:
        spins_used = [int((lineup[s] or {}).get("spin", -1)) for s in lineup]
    except (TypeError, ValueError):
        return None, "Bad spin."
    if len(set(spins_used)) != len(spins_used) or any(not 0 <= i < e82.SPINS for i in spins_used):
        return None, "One player from each spin."
    rows, ids = [], set()
    for slot in e82.SLOTS:
        x = lineup.get(slot)
        if not x:
            rows.append({"slot": slot, "id": None, "name": "Replacement player", "pos": "", "team": "", "season": None,
                         "ovr": FILLER_OVR, "filler": True})
            continue
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
    return {"rating": round(r, 2), "wins": e82.wins_for(r), "lineup": rows,
            "filled": sum(1 for x in rows if not x.get("filler"))}, None


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
                        "easy": room["easy"] if room else False, "secs": ROUND_SECS, "filler": FILLER_OVR,
                        "me": (current_user(request) or {}).get("username") or ""}}
    # Davet linkiyle gelen misafir "gunde bir oyun" kapisina takilmasin: ayri etkin sayfa adi
    return render(request, "eighty_two.html", active="eightytwo-room", payload=json.dumps(payload).replace("</", "<\\/"),
                  puzzle=None, room=code)


@router.get("/api/82-0/room/{code}")
def room_spins(code: str):
    room = _rooms.get(code)
    if not room:
        return _bad("This room has ended.", 404)
    return {"round": room["round"], "span": room["span"], "easy": room["easy"], "spins": room["spins"]}


# ==================== CANLI ====================

async def _send(ws, obj):
    try:
        await ws.send_text(json.dumps(obj))
    except Exception:
        pass


def _online(room):
    return {c["cid"] for c in room["conns"].values()}


def _public(room, viewer=None):
    """
    Kisiye ozel gorunum. Rakiplerin secimleri (ad, takim, sezon) hep gorunur; OVR,
    puan ve galibiyet ise yalnizca tur bitince (ya da izleyen kendi kadrosunu
    kilitlediyse) - yoksa ortak cevirmelerdeki gizli OVR'ler oyun bitmeden ogrenilirdi.
    """
    online = _online(room)
    done = room["phase"] == "done"
    can_see = done or viewer in room["results"]
    players = []
    for cid, s in room["seats"].items():
        if cid not in online and cid not in room["players_in"] and cid not in room["results"]:
            continue
        res = room["results"].get(cid)
        part = room["partial"].get(cid) or {}
        picks = {x["slot"]: {"id": x["id"], "name": x["name"], "team": x["team"], "season": x["season"],
                             **({"ovr": x["ovr"]} if (can_see and res) or cid == viewer else {})}
                 for x in (res or part.get("res") or {}).get("lineup", []) if not x.get("filler")}
        show = res and (cid == viewer or can_see)
        players.append({"cid": cid, "name": s["name"], "online": cid in online, "done": cid in room["results"],
                        "you": cid == viewer, "picks": picks, "count": len(picks),
                        "wins": res["wins"] if show else None, "rating": res["rating"] if show else None,
                        "lineup": res["lineup"] if show else None})
    players.sort(key=lambda p: (not p["you"], p["name"].lower()) if not done else
                 (-(p["rating"] if p["rating"] is not None else -1), p["name"].lower()))
    best = max((p["rating"] for p in players if p["rating"] is not None), default=None)
    winners = [p["name"] for p in players if done and p["rating"] is not None and p["rating"] == best]
    now = time.time()
    return {"t": "state", "round": room["round"], "span": room["span"], "easy": room["easy"], "phase": room["phase"],
            "starts_in": round(room["start_at"] - now, 2) if room["start_at"] and room["phase"] == "live" else None,
            "left": round(room["deadline"] - now, 2) if room["deadline"] and room["phase"] == "live" else None,
            "players": players, "all_done": done, "winners": winners, "secs": ROUND_SECS}


async def _broadcast(room, obj, skip=None):
    for c in list(room["conns"].values()):
        if c["cid"] != skip:
            await _send(c["ws"], obj)


async def _broadcast_state(room):
    for c in list(room["conns"].values()):
        await _send(c["ws"], _public(room, c["cid"]))


def _maybe_start(room, force=False):
    """Iki (ya da daha fazla) kisi odadaysa ya da biri 'simdi basla' derse tur baslar."""
    if room["phase"] != "waiting":
        return False
    online = _online(room)
    if len(online) >= 2 or (force and online):
        now = time.time()
        room.update({"phase": "live", "start_at": now + COUNTDOWN, "deadline": now + COUNTDOWN + ROUND_SECS,
                     "players_in": set(online)})
        return True
    return False


def _finish_round(room):
    """Sure doldu ya da herkes kilitledi: kilitlemeyenlerin o anki kadrosu puanlanir."""
    for cid in room["players_in"] | set(room["partial"]):
        if cid in room["results"]:
            continue
        part = room["partial"].get(cid) or {}
        res, _ = score(room["spins"], part.get("lineup") or {}, part.get("choice") or {}, partial=True)
        room["results"][cid] = dict(res, timeout=True)
    room["phase"] = "done"


async def _tick():
    while True:
        await asyncio.sleep(0.5)
        now = time.time()
        for room in list(_rooms.values()):
            if room["phase"] == "live" and now > room["deadline"] + GRACE:
                _finish_round(room)
                await _broadcast(room, {"t": "timeup"})
                await _broadcast_state(room)


def _clean_name(raw):
    name = re.sub(r"[^\w .\-]", "", str(raw or ""), flags=re.UNICODE).strip()[:20]
    return name if len(name) >= 2 else None


@router.websocket("/ws/82-0/{code}")
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
                if room["phase"] == "live":
                    room["players_in"].add(cid)          # gec gelen kalan sureyle oynar
                _maybe_start(room)
                await _send(ws, {"t": "chatlog", "items": room["chat"][-50:]})
                await _broadcast(room, {"t": "joined", "name": name}, skip=cid)
                await _broadcast_state(room)
            elif not conn:
                continue
            elif t == "start":
                if _maybe_start(room, force=True):
                    await _broadcast_state(room)
            elif t == "lineup":
                cid = conn["cid"]
                if int(msg.get("round") or 0) != room["round"]:
                    await _send(ws, {"t": "error", "text": "A new round started - that lineup was for the last one."})
                    continue
                now = time.time()
                if room["phase"] != "live" or cid in room["results"] or now < room["start_at"] - 1 \
                        or now > room["deadline"] + GRACE:
                    continue
                final = bool(msg.get("final"))
                res, err = score(room["spins"], msg.get("lineup"), msg.get("choice"), partial=not final)
                if err:
                    await _send(ws, {"t": "error", "text": err})
                    continue
                old = room["partial"].get(cid) or {}
                before = (old.get("res") or {}).get("filled", 0)
                prev = {x["slot"]: x["id"] for x in (old.get("res") or {}).get("lineup", []) if not x.get("filler")}
                room["partial"][cid] = {"lineup": msg.get("lineup"), "choice": msg.get("choice"), "res": res}
                room["players_in"].add(cid)
                if final:
                    room["results"][cid] = res
                    await _broadcast(room, {"t": "locked", "name": conn["name"], "left": round(room["deadline"] - now)}, skip=cid)
                elif res["filled"] > before:
                    new = next((x for x in res["lineup"] if not x.get("filler") and prev.get(x["slot"]) != x["id"]), None)
                    await _broadcast(room, {"t": "pick", "name": conn["name"], "n": res["filled"],
                                            "player": new["name"] if new else "", "slot": new["slot"] if new else ""},
                                     skip=cid)
                if room["players_in"] and all(c in room["results"] for c in room["players_in"]):
                    _finish_round(room)
                await _broadcast_state(room)
            elif t == "next":
                if room["phase"] != "done":
                    await _send(ws, {"t": "error", "text": "Wait until the round is over."})
                    continue
                _new_round(room)
                _maybe_start(room)
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

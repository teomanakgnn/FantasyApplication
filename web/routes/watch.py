"""
Watch party: mac odasi. Canli skor, oyunlar, fantezi liderleri, sohbet,
tepkiler; ayrica sesli sohbet ve ekran paylasimi (WebRTC, kisiden kisiye -
ses ve goruntu sunucudan gecmez, sunucu yalnizca baglanti sinyallerini
tasir). Lobi yalnizca yonetici; odaya yonetici veya davet linki olan
giris yapmis kullanici girer.
"""
import hashlib
import hmac
import json
import os
import time
from datetime import timedelta
from itertools import count

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse

import config
from services import watch_party as wp
from services.database import db
from web import stats
from web.core import current_user, login_required, redirect, render

router = APIRouter()

REACTIONS = ["🔥", "😂", "😱", "👏", "💀", "🧊", "😤", "🐐"]
CALL_LIMIT = 8  # kisiden kisiye agda herkes herkese bagli; kalabalik oda kaldirmaz
_last_post = {}


def _is_admin(u):
    return bool(u and u.get("username") in config.ADMIN_USERNAMES)


def room_key(game_id):
    return hmac.new(config.SECRET_KEY.encode(), f"watch:{game_id}".encode(), hashlib.sha256).hexdigest()[:16]


def _member(u, game_id, k):
    """Odaya girebilir mi: yonetici ya da gecerli davet anahtari olan uye."""
    if not u:
        return False
    return _is_admin(u) or (bool(k) and hmac.compare_digest(str(k), room_key(game_id)))


GUEST_COOKIE, NAME_COOKIE = "hl_wpg", "hl_wpn"


def _key_ok(game_id, k):
    return bool(k) and hmac.compare_digest(str(k), room_key(game_id))


def _guest_name(raw):
    """Misafir adi: 2-20 karakter, harf/rakam/bosluk/._- ; yoksa None."""
    import re
    from urllib.parse import unquote
    name = re.sub(r"[^\w .\-]", "", unquote(raw or ""), flags=re.UNICODE).strip()[:20]
    return name if len(name) >= 2 else None


def _who(conn, game_id, k):
    """
    Odadaki kisi: uye (davet linkiyle ya da yonetici) veya davet linkiyle gelen
    misafir. Misafirin kimligi tarayicidaki rastgele anahtar, adi kendi yazdigi
    ('(guest)' etiketiyle: uyelerin adini taklit edemez). Ad yoksa None.
    """
    u = current_user(conn)
    if u and _member(u, game_id, k):
        return {"id": u["id"], "name": u["username"], "guest": False}
    if not _key_ok(game_id, k):
        return None
    token = conn.cookies.get(GUEST_COOKIE) or ""
    name = _guest_name(conn.cookies.get(NAME_COOKIE))
    if len(token) < 16 or not name:
        return None
    return {"id": "g:" + token[:16], "name": f"{name} (guest)", "guest": True}


def _ice_servers():
    """STUN her zaman; TURN (zor aglar icin aktarma) ortam degiskeniyle eklenir."""
    servers = [{"urls": ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302",
                         "stun:stun.cloudflare.com:3478"]}]
    turn = os.environ.get("TURN_URLS")
    if turn:
        servers.append({"urls": [u.strip() for u in turn.split(",") if u.strip()],
                        "username": os.environ.get("TURN_USERNAME", ""),
                        "credential": os.environ.get("TURN_CREDENTIAL", "")})
    return servers


@router.get("/admin/watch")
def lobby(request: Request):
    gate = login_required(request)
    if gate:
        return gate
    if not _is_admin(current_user(request)):
        return redirect("/", "Not available.", "error")
    day = wp.today_et()
    days = []
    for d in (day, day - timedelta(days=1)):
        try:
            games = stats.scoreboard(d)
        except Exception:
            games = []
        if games:
            days.append((d, games))
    return render(request, "watch_lobby.html", active="home", days=days, room_key=room_key)


@router.get("/admin/watch/{game_id}")
def old_room(game_id: str):
    return RedirectResponse(f"/watch/{game_id}?k={room_key(game_id)}", 303)


@router.get("/watch/{game_id}")
def room(request: Request, game_id: str, k: str = ""):
    u = current_user(request)
    # Yonetici anahtarsiz girdiyse adres cubugu da paylasilabilir olsun: anahtarli adrese git
    if _is_admin(u) and not _key_ok(game_id, k):
        return RedirectResponse(f"/watch/{game_id}?k={room_key(game_id)}", 302)
    guest = not (u and _member(u, game_id, k))
    if guest and not _key_ok(game_id, k):
        if not u:
            return login_required(request, next_url=f"/watch/{game_id}")
        return redirect("/", "That watch party link is incomplete or out of date - ask for a fresh invite link.", "error")
    try:
        g = wp.game_state(game_id)
    except Exception:
        return redirect("/", "Game not found.", "error")
    key = room_key(game_id)
    invite = f"{config.SITE_URL.rstrip('/')}/watch/{game_id}?k={key}"
    response = render(request, "watch_room.html", active="home", game_id=game_id, g=g, reactions=REACTIONS,
                      room_k=key, invite=invite, is_admin=_is_admin(u), guest=guest,
                      ice=json.dumps(_ice_servers()), call_limit=CALL_LIMIT)
    if guest and len(request.cookies.get(GUEST_COOKIE) or "") < 16:
        import secrets
        response.set_cookie(GUEST_COOKIE, secrets.token_urlsafe(18), max_age=365 * 86400, httponly=True,
                            secure=config.PRODUCTION, samesite="lax", path="/")
    return response


def _msg(r):
    return {"id": r["id"], "user": r["username"], "kind": r["kind"], "body": r["body"],
            "at": r["created_at"].isoformat() + "Z" if r.get("created_at") else ""}


@router.get("/api/watch/{game_id}/feed")
def feed(request: Request, game_id: str, after: int = 0, board: int = 0, k: str = ""):
    if not (_member(current_user(request), game_id, k) or _key_ok(game_id, k)):
        return JSONResponse({"error": "Not available."}, 403)
    out = {"messages": [_msg(r) for r in db.watch_messages(game_id, after)],
           "in_call": [p["name"] for p in _rooms.get(game_id, {}).values()]}
    try:
        g = wp.game_state(game_id)
        out["game"] = g
        if board:
            out["leaders"] = wp.fantasy_leaders(game_id, final=g["final"])
    except Exception as exc:
        out["game_error"] = str(exc)[:120]
    return out


@router.post("/api/watch/{game_id}/post")
async def post(request: Request, game_id: str, k: str = ""):
    who = _who(request, game_id, k)
    if not who:
        return JSONResponse({"error": "Pick a name to chat." if _key_ok(game_id, k) else "Not available."}, 403)
    b = await request.json()
    kind = "react" if b.get("kind") == "react" else "msg"
    body = str(b.get("body") or "").strip()[:280]
    if kind == "react" and body not in REACTIONS:
        return JSONResponse({"error": "Unknown reaction."}, 400)
    if not body:
        return JSONResponse({"error": "Empty message."}, 400)
    now = time.time()
    if now - _last_post.get(who["id"], 0) < (0.25 if kind == "react" else 0.8):
        return JSONResponse({"error": "Slow down a little."}, 429)
    _last_post[who["id"]] = now
    mid = db.add_watch_message(game_id, 0 if who["guest"] else who["id"], who["name"], kind, body)
    return {"id": mid}


# ==================== SESLI SOHBET / EKRAN PAYLASIMI: SINYAL ====================
# Oda -> {peer_id: {"ws", "name", "uid", "mic", "sharing"}}. Tek sunucu, tek
# islem (fly.toml: tek makine, --ha=false), bellekte tutmak yeterli.

_rooms = {}
_ids = count(1)


def _public(pid, p):
    return {"id": pid, "name": p["name"], "mic": p["mic"], "sharing": p["sharing"]}


async def _send(ws, msg):
    try:
        await ws.send_text(json.dumps(msg))
    except Exception:
        pass


async def _broadcast(game_id, msg, skip=None):
    for pid, p in list(_rooms.get(game_id, {}).items()):
        if pid != skip:
            await _send(p["ws"], msg)


@router.websocket("/ws/watch/{game_id}")
async def signal(ws: WebSocket, game_id: str, k: str = ""):
    who = _who(ws, game_id, k)
    if not who:
        await ws.close(code=4403)
        return
    origin = ws.headers.get("origin") or ""
    if config.PRODUCTION and origin and origin.rstrip("/") != config.SITE_URL.rstrip("/"):
        await ws.close(code=4403)
        return
    room = _rooms.setdefault(game_id, {})
    await ws.accept()
    if len(room) >= CALL_LIMIT:
        await _send(ws, {"type": "full", "limit": CALL_LIMIT})
        await ws.close()
        return
    # Ayni kullanici ikinci sekmeden gelirse eskisini dusur
    for pid, p in list(room.items()):
        if p["uid"] == who["id"]:
            room.pop(pid, None)
            await _broadcast(game_id, {"type": "leave", "id": pid})
            try:
                await p["ws"].close(code=4409)
            except Exception:
                pass
    me = str(next(_ids))
    room[me] = {"ws": ws, "name": who["name"], "uid": who["id"], "mic": False, "sharing": False}
    await _send(ws, {"type": "welcome", "id": me,
                     "peers": [_public(pid, p) for pid, p in room.items() if pid != me]})
    await _broadcast(game_id, {"type": "join", **_public(me, room[me])}, skip=me)
    try:
        while True:
            raw = await ws.receive_text()
            if len(raw) > 64000:
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            t = msg.get("type")
            if t == "signal":
                target = room.get(str(msg.get("to")))
                if target:
                    await _send(target["ws"], {"type": "signal", "from": me, "data": msg.get("data")})
            elif t == "state":
                p = room.get(me)
                if p:
                    p["mic"], p["sharing"] = bool(msg.get("mic")), bool(msg.get("sharing"))
                    await _broadcast(game_id, {"type": "state", **_public(me, p)}, skip=me)
            elif t == "ping":
                await _send(ws, {"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"watch ws error: {exc}")
    finally:
        if room.get(me, {}).get("ws") is ws:
            room.pop(me, None)
            await _broadcast(game_id, {"type": "leave", "id": me})
        if not room:
            _rooms.pop(game_id, None)

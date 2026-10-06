"""
Ziyaretci sayaci: hangi ulkeden, hangi sayfaya, nereden gelindi.

Uygulama Cloudflare'in onunden gecmiyor (DNS-only), bu yuzden Cloudflare
ulke gosteremiyor; GA da cerez izni vermeyenleri saymiyor. Burada her
sayfa gorunumu sunucuda kaydediliyor:

  * IP saklanmiyor: ulkesi bulunup atiliyor. Ziyaretciyi gun icinde ayirt
    etmek icin IP + tarayici + gun + gizli anahtarin ozeti tutuluyor; ertesi
    gun ayni kisi farkli ozet aliyor (kalici takip yok).
  * Botlar (Google, tarayicilar, tarama araclari) ve yonetici sayilmiyor.
  * Kayit istegi bekletmez: kuyruga atilir, arka planda toplu yazilir.

Ulke verisi: DB-IP Lite (CC BY 4.0) - scripts/fetch_geoip.py.
"""
import hashlib
import os
import queue
import re
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import config

BOT_RE = re.compile(r"bot|crawl|spider|slurp|preview|headless|python|curl|wget|httpx|go-http|java/|"
                    r"facebookexternalhit|lighthouse|pingdom|uptime|monitor|scan|axios|node-fetch|okhttp",
                    re.I)
MOBILE_RE = re.compile(r"mobile|iphone|android|ipad", re.I)
_GEOIP_PATH = os.environ.get("GEOIP_DB") or os.path.join(
    os.path.dirname(__file__), "..", "data", "dbip-country.mmdb")

_reader = None
_reader_failed = False
_queue = queue.Queue(maxsize=5000)
_started = False
_lock = threading.Lock()


def _geo():
    global _reader, _reader_failed
    if _reader is None and not _reader_failed:
        try:
            import maxminddb
            # Dosya Python'da aciliyor: kutuphanenin C kismi Windows'ta
            # ASCII olmayan yollari (Masaustu) acamiyor.
            with open(_GEOIP_PATH, "rb") as fh:
                _reader = maxminddb.open_database(fh, mode=maxminddb.MODE_FD)
        except Exception as exc:
            print(f"geoip unavailable: {exc}")
            _reader_failed = True
    return _reader


def country(ip):
    """(ISO kodu, Ingilizce ad) - bulunamazsa ("", "Unknown")."""
    reader = _geo()
    if not reader or not ip:
        return "", "Unknown"
    try:
        rec = reader.get(ip) or {}
        c = rec.get("country") or {}
        return c.get("iso_code") or "", (c.get("names") or {}).get("en") or "Unknown"
    except Exception:
        return "", "Unknown"


def is_bot(user_agent):
    return not user_agent or bool(BOT_RE.search(user_agent))


def _visitor(ip, user_agent):
    day = datetime.now(timezone.utc).date().isoformat()
    raw = f"{config.SECRET_KEY}|{day}|{ip}|{user_agent}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def _source(request):
    """Bu gorunumun kaynagi: utm/ref parametresi, yoksa disaridan gelen site."""
    q = request.query_params
    src = q.get("utm_source") or q.get("ref")
    if src:
        medium = q.get("utm_medium")
        return re.sub(r"[^\w./:-]", "", f"{src}/{medium}" if medium else src)[:80].lower()
    ref = request.headers.get("referer") or ""
    host = urlparse(ref).netloc.lower().removeprefix("www.")
    if host and "hooplifenba.com" not in host:
        return "ref:" + host[:70]
    return ""


def record(request, ip):
    """Middleware cagirir; asla hata firlatmaz, istegi bekletmez."""
    try:
        ua = request.headers.get("user-agent", "")
        if is_bot(ua):
            return
        iso, name = country(ip)
        item = (_visitor(ip, ua), iso, name, request.url.path[:120], _source(request),
                "mobile" if MOBILE_RE.search(ua) else "desktop")
        _ensure_worker()
        _queue.put_nowait(item)
    except Exception:
        pass


def _ensure_worker():
    global _started
    if _started:
        return
    with _lock:
        if not _started:
            threading.Thread(target=_worker, daemon=True).start()
            _started = True


def _worker():
    from services.database import db
    while True:
        batch = [_queue.get()]
        time.sleep(2)
        while not _queue.empty() and len(batch) < 500:
            batch.append(_queue.get_nowait())
        try:
            db.record_page_views(batch)
        except Exception as exc:
            print(f"page view write failed: {exc}")

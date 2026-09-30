"""
Web katmaninin ortak parcalari: sablonlar, oturum, flash mesajlari.

Oturum
------
Giris yapinca rastgele bir anahtar uretilir, veritabaninda yalnizca
ozeti tutulur (services/database.py) ve tarayiciya HttpOnly bir cerez
olarak verilir. JavaScript cereze ulasamaz; URL'de hic gorunmez.

Eski surumde oturum iki yoldan geri yukleniyordu ve ikisi de sorunluydu:
  * localStorage'daki anahtar URL'e yazilip sayfa yenileniyordu - tarayici
    bu yonlendirmeyi engelledigi icin "beni hatirla" hic calismiyordu.
  * "Cihaz izi" (tarayici + ekran + saat dilimi) ile otomatik giris -
    ayni telefonu kullanan iki kisi birbirinin hesabina girebiliyordu.
Ikisi de kaldirildi; cerez bu isi tek basina ve guvenli yapiyor.
"""
import json
import secrets
import time
from pathlib import Path
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

import config
from services.database import db

WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))

SESSION_COOKIE = "hl_session"
FLASH_COOKIE = "hl_flash"
SESSION_MAX_AGE = 30 * 24 * 3600

# Statik dosyalarin onbellek kirici surumu: her acilista degisir.
ASSET_VERSION = str(int(time.time()))

NAV = [
    ("home", "/", "Home"),
    ("mock", "/mock-draft", "Mock Draft"),
    ("strategy", "/draft-strategy", "Draft Strategy"),
    ("ou", "/over-under", "Over / Under"),
    ("cards", "/card-game", "Card Connections"),
    ("bracket", "/bracket", "Playoff Bracket"),
    None,
    ("injuries", "/injuries", "Injury Report"),
    ("trade", "/trade-analyzer", "Trade Analyzer"),
    ("league", "/league", "My League"),
    ("trends", "/trends", "Player Trends"),
]

# ==================== OTURUM ====================

# Ayni oturum anahtari icin her istekte veritabanina gitmemek icin kisa
# sureli bellek: kullanici bilgisi 60 saniye saklanir. Cikis ve plan
# degisikligi bunu hemen temizler.
_user_cache = {}
_USER_TTL = 60


def _cached_user(token):
    hit = _user_cache.get(token)
    if hit and time.time() - hit[0] < _USER_TTL:
        return hit[1]
    user = db.validate_session_by_token(token) if token else None
    if user:
        _user_cache[token] = (time.time(), user)
    else:
        _user_cache.pop(token, None)
    if len(_user_cache) > 5000:
        _user_cache.clear()
    return user


def forget_user_cache(token=None):
    if token:
        _user_cache.pop(token, None)
    else:
        _user_cache.clear()


def current_user(request: Request):
    """Istegin kullanicisi (veya None). Istek basina bir kez hesaplanir."""
    if hasattr(request.state, "user"):
        return request.state.user
    token = request.cookies.get(SESSION_COOKIE)
    user = _cached_user(token) if token else None
    request.state.user = user
    request.state.session_token = token if user else None
    return user


def is_pro(user):
    return bool(user and user.get("is_pro"))


def set_session_cookie(response, token, remember=True):
    response.set_cookie(
        SESSION_COOKIE, token,
        max_age=SESSION_MAX_AGE if remember else None,
        httponly=True, secure=config.PRODUCTION, samesite="lax", path="/")


def clear_session_cookie(response):
    response.delete_cookie(SESSION_COOKIE, path="/")


def from_proxy(request: Request):
    """Istek Cloudflare koprusunden mi geliyor (paylasilan anahtar eslesiyor mu)?"""
    secret = config.PROXY_SECRET
    return bool(secret) and secrets.compare_digest(
        request.headers.get("x-hl-proxy-secret", ""), secret)


def public_host(request: Request):
    """Tarayicinin gordugu alan adi (kopru arkasinda Railway adresi degil)."""
    if from_proxy(request):
        return request.headers.get("x-hl-host") or request.headers.get("host")
    return request.headers.get("host")


def client_ip(request: Request):
    if from_proxy(request) and request.headers.get("x-hl-client-ip"):
        return request.headers["x-hl-client-ip"]
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ==================== FLASH ====================

def flash(response, message, kind="ok"):
    """
    Bir sonraki sayfada bir kez gosterilecek mesaj.

    Eski surumde "Kaydedildi" gibi mesajlar yazilip hemen sayfa yeniden
    cizildigi icin kullanici hicbirini goremiyordu.
    """
    response.set_cookie(FLASH_COOKIE, quote(json.dumps({"m": message, "k": kind})),
                        max_age=60, httponly=True, secure=config.PRODUCTION,
                        samesite="lax", path="/")
    return response


def pop_flash(request: Request):
    raw = request.cookies.get(FLASH_COOKIE)
    if not raw:
        return None
    try:
        from urllib.parse import unquote
        data = json.loads(unquote(raw))
        request.state.clear_flash = True
        return {"message": str(data.get("m", ""))[:300], "kind": data.get("k", "ok")}
    except Exception:
        request.state.clear_flash = True
        return None


def redirect(url, message=None, kind="ok"):
    response = RedirectResponse(url, status_code=303)
    if message:
        flash(response, message, kind)
    return response


# ==================== SABLON ====================

def render(request: Request, template, active=None, status_code=200, **context):
    user = current_user(request)
    context.update({
        "request": request,
        "user": user,
        "pro": is_pro(user),
        "nav": NAV,
        "active": active,
        "flash": pop_flash(request),
        "asset_version": ASSET_VERSION,
        "ga_id": config.GOOGLE_ANALYTICS_ID,
    })
    response = templates.TemplateResponse(request, template, context, status_code=status_code)
    if getattr(request.state, "clear_flash", False):
        response.delete_cookie(FLASH_COOKIE, path="/")
    return response


def login_required(request: Request, next_url=None):
    """Giris yoksa giris sayfasina yonlendirme cevabi, varsa None."""
    if current_user(request):
        return None
    target = next_url or request.url.path
    return redirect(f"/login?next={quote(target)}", "Sign in to continue.", "info")


# ==================== FORMAT ====================

def _num(value, decimals=1):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if decimals == 0:
        return f"{number:.0f}"
    return f"{number:.{decimals}f}"


templates.env.filters["num"] = _num
templates.env.globals["min"] = min
templates.env.globals["max"] = max

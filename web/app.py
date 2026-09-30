"""
HoopLife NBA - web uygulamasi (FastAPI).

Calistirma:  uvicorn web.app:app --host 0.0.0.0 --port 8000

Streamlit'ten neden cikildi: her tiklama butun sayfayi sunucuda bastan
calistiriyor, ilk acilis 11-15 saniye suruyor, uygulama ABD'de calisip
Londra'daki veritabanina her sorguda okyanus asiyordu; mobil menu, geri
tusu ve adres cubugu gibi temel web davranislari da elle taklit
ediliyordu. Burada her sayfa normal bir web sayfasi: dogrudan adresi
var, geri tusu calisiyor, etkilesim tarayicida.
"""
import threading
import time
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

import config
from utils.console import configure_console_encoding
from web.core import WEB_DIR, public_host, render

configure_console_encoding()

app = FastAPI(title="HoopLife NBA", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@app.middleware("http")
async def security(request: Request, call_next):
    """
    Durum degistiren isteklerde koken kontrolu (CSRF).

    Oturum cerezi SameSite=Lax; ek olarak Origin/Referer bu sitenin degilse
    POST reddedilir. Baska bir sitedeki form kullanicinin adina islem
    yapamaz.
    """
    if request.method not in SAFE_METHODS:
        origin = request.headers.get("origin") or request.headers.get("referer")
        if origin:
            host = urlparse(origin).netloc
            if host and host != public_host(request):
                return PlainTextResponse("Cross-site request blocked.", status_code=403)

    started = time.time()
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elapsed = time.time() - started
    if elapsed > 2:
        print(f"slow request {request.method} {request.url.path} {elapsed:.1f}s")
    return response


# ==================== SAYFALAR ====================

from web.routes import (account, auth, draft, games, home, injuries, league,  # noqa: E402
                        mock, over_under, trade, trends, watchlist)

for module in (home, auth, account, watchlist, over_under, draft, mock, games,
               injuries, trade, league, trends):
    app.include_router(module.router)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}


@app.get("/robots.txt", include_in_schema=False)
def robots():
    return PlainTextResponse("User-agent: *\nAllow: /\n")


# ==================== HATALAR ====================

@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
    title = "Page not found" if exc.status_code == 404 else "Something went wrong"
    return render(request, "error.html", status_code=exc.status_code,
                  title=title, detail=exc.detail if exc.status_code != 404 else None)


@app.exception_handler(Exception)
async def server_error(request: Request, exc: Exception):
    import traceback
    detail = traceback.format_exc()
    print(detail)
    # Yoneticiye e-posta (Resend tanimliysa; ayni hata 15 dk'da bir)
    from services import mailer
    mailer.alert(f"{exc.__class__.__name__} on {request.method} {request.url.path}",
                 f"{request.method} {request.url}" + "\n\n" + detail)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "Server error. Try again."}, status_code=500)
    return render(request, "error.html", status_code=500, title="Something went wrong",
                  detail="The page hit an error. Try again in a moment.")


# ==================== ISITMA ====================

def _warm():
    """
    Pahali verileri acilista arka planda hazirla.

    Ilk ziyaretci ESPN'den 16 MB'lik draft havuzunu ve sezon
    istatistiklerini beklemek zorunda kalmasin. Streamlit'te "uygulama
    uyaniyor" ekraninin bir sebebi buydu.
    """
    from datetime import date

    steps = []
    try:
        from services.database import db
        steps.append(("db", lambda: db.available))
        from web import stats
        steps.append(("games", lambda: stats.resolve_game_day(date.today())))
        from services.espn_api import get_current_team_rosters, get_injuries
        steps.append(("rosters", get_current_team_rosters))
        steps.append(("injuries", get_injuries))
        from services.draft_data import get_draft_board
        steps.append(("draft board", get_draft_board))
        from services.win_totals import get_team_identity
        steps.append(("teams", get_team_identity))
    except Exception as exc:
        print(f"warm-up import failed: {exc}")
    for name, step in steps:
        started = time.time()
        try:
            step()
            print(f"warm-up {name}: {time.time() - started:.1f}s")
        except Exception as exc:
            print(f"warm-up {name} failed: {exc}")


@app.on_event("startup")
def start_warmup():
    if config.flag("SKIP_WARMUP"):
        return
    threading.Thread(target=_warm, daemon=True).start()

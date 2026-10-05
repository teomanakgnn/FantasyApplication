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
from web.core import WEB_DIR, public_host, remember_source, render

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
    path = request.url.path
    if path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif request.method == "GET" and not path.startswith(("/api/", "/healthz")):
        remember_source(request, response)
    elapsed = time.time() - started
    if elapsed > 2:
        print(f"slow request {request.method} {request.url.path} {elapsed:.1f}s")
    return response


# ==================== SAYFALAR ====================

from web.routes import (account, auth, draft, games, home, injuries, league,  # noqa: E402
                        mock, outreach, over_under, trade, trends, watchlist)

for module in (home, auth, account, watchlist, over_under, draft, mock, games,
               injuries, trade, league, trends, outreach):
    app.include_router(module.router)


@app.get("/healthz", include_in_schema=False)
def healthz():
    """
    Railway yeni surume trafigi ancak burasi 200 donunce verir. Isinma
    bitene kadar (en fazla 100 sn) 503: boylece her yayindan sonraki ilk
    ziyaretci ESPN verisinin cekilmesini beklemek zorunda kalmiyor.
    """
    if _WARM_DONE.is_set() or config.flag("SKIP_WARMUP") or time.time() - _STARTED > 100:
        return {"ok": True}
    return JSONResponse({"ok": False, "warming": True}, status_code=503)


PUBLIC_PAGES = ["/", "/over-under", "/mock-draft", "/draft-strategy", "/bracket",
                "/injuries", "/trade-analyzer", "/league", "/daily", "/register", "/privacy", "/terms"]


@app.get("/privacy", include_in_schema=False)
def privacy(request: Request):
    return render(request, "legal.html", page="privacy")


@app.get("/terms", include_in_schema=False)
def terms(request: Request):
    return render(request, "legal.html", page="terms")


@app.get("/robots.txt", include_in_schema=False)
def robots():
    base = config.SITE_URL.rstrip("/")
    return PlainTextResponse(
        "User-agent: *\nAllow: /\n"
        "Disallow: /api/\nDisallow: /account\nDisallow: /watchlist\n"
        "Disallow: /reset-password\nDisallow: /admin/\nDisallow: /unsubscribe\n"
        f"\nSitemap: {base}/sitemap.xml\n")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    """Google'in tarayacagi herkese acik sayfalar."""
    from datetime import date
    from fastapi.responses import Response
    base = config.SITE_URL.rstrip("/")
    urls = "".join(f"<url><loc>{base}{path}</loc><lastmod>{date.today()}</lastmod></url>"
                   for path in PUBLIC_PAGES)
    body = ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')
    return Response(body, media_type="application/xml")


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

_STARTED = time.time()
_WARM_DONE = threading.Event()


def _warm():
    """
    Pahali verileri acilista arka planda hazirla: sayfalarin gercekten
    istedigi veriler (ana sayfa varsayilan olarak DUNUN maclarini acar;
    eski isinma bugunu hazirliyordu ve ilk ziyaretci 8 sn bekliyordu).
    """
    from datetime import date, timedelta

    def step(name, fn):
        started = time.time()
        try:
            fn()
            print(f"warm-up {name}: {time.time() - started:.1f}s")
        except Exception as exc:
            print(f"warm-up {name} failed: {exc}")

    try:
        from services.database import db
        from services.draft_data import get_draft_board
        from services.espn_api import get_current_team_rosters, get_injuries
        from services.nba_season import get_current_season_year
        from services.win_totals import get_team_identity
        from utils.images import name_to_id_map
        from web import stats
        from web.routes.over_under import load_lines

        step("db", lambda: db.available)
        step("rosters", get_current_team_rosters)

        def home():
            day, _ = stats.resolve_game_day(date.today() - timedelta(days=1))
            games = stats.scoreboard(day) if day else []
            stats.today_table(games, stats.BASE_WEIGHTS)
        step("home", home)
        step("injuries", get_injuries)
        step("teams", get_team_identity)
        step("over/under lines", lambda: load_lines(get_current_season_year()))
        step("draft board", get_draft_board)
        step("season stats", lambda: stats.season_table(stats.BASE_WEIGHTS))
        step("player photos", name_to_id_map)
        from services import daily_player
        step("mystery player", daily_player.answer_for)
    finally:
        _WARM_DONE.set()


@app.on_event("startup")
def start_warmup():
    if config.flag("SKIP_WARMUP"):
        _WARM_DONE.set()
        return
    threading.Thread(target=_warm, daemon=True).start()

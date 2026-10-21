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
from fastapi.responses import RedirectResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

import config
from utils.console import configure_console_encoding
from services import visits
from web.core import (SESSION_COOKIE, WEB_DIR, _cached_user, client_ip, public_host,
                      remember_source, render)

ME_COOKIE = "hl_me"     # yonetici tarayicisi: ziyaretci sayimina girmez

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
    if request.method not in SAFE_METHODS and not request.url.path.startswith("/api/draft-feed/"):
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
        _count_visit(request, response)
    elapsed = time.time() - started
    if elapsed > 2:
        print(f"slow request {request.method} {request.url.path} {elapsed:.1f}s")
    return response


def _count_visit(request, response):
    """
    Ziyaretci paneli icin sayfa gorunumu (services/visits.py). Yonetici
    sayilmaz: giris yapmis yonetici tarayicisina kalici bir isaret cerezi
    alir; cikis yapsa da o tarayici sayim disi kalir.
    """
    if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
        return
    if request.url.path.startswith(("/admin/", "/account", "/unsubscribe")):
        return
    if request.cookies.get(ME_COOKIE):
        return
    token = request.cookies.get(SESSION_COOKIE)
    user = _cached_user(token) if token else None
    if user and user.get("username") in config.ADMIN_USERNAMES:
        response.set_cookie(ME_COOKIE, "1", max_age=5 * 365 * 86400, httponly=True,
                            secure=config.PRODUCTION, samesite="lax", path="/")
        return
    visits.record(request, client_ip(request))


# ==================== SAYFALAR ====================

from web.routes import (account, auth, games, home, injuries, league,  # noqa: E402
                        nba, outreach, over_under, players, trade, trends, watch, watchlist)

for module in (home, nba, auth, account, watchlist, over_under, games,
               injuries, trade, league, trends, outreach, players, watch):
    app.include_router(module.router)


# Kaldirilan draft sayfalari (sezon basladi): eski linkler ve Google kayitlari
# siralamaya gitsin, 404 olmasin.
@app.get("/mock-draft", include_in_schema=False)
@app.get("/draft-strategy", include_in_schema=False)
def _retired_draft_pages():
    return RedirectResponse("/rankings", 301)


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


PUBLIC_PAGES = ["/", "/nba/scores", "/nba/standings", "/waiver-wire", "/over-under", "/bracket",
                "/injuries", "/trade-analyzer", "/league", "/daily", "/stat-match", "/starting-five", "/82-0", "/tier-list", "/rankings", "/register", "/privacy", "/terms"]


@app.get("/privacy", include_in_schema=False)
def privacy(request: Request):
    return render(request, "legal.html", page="privacy")


@app.get("/terms", include_in_schema=False)
def terms(request: Request):
    return render(request, "legal.html", page="terms")


@app.get("/robots.txt", include_in_schema=False)
def robots():
    base = config.SITE_URL.rstrip("/")
    # Yapay zeka asistanlari ve arama botlari acikca davetli (ChatGPT, Claude,
    # Perplexity, Gemini, Copilot/Bing). Kisitlamalar herkes icin ayni.
    ai = "".join(f"User-agent: {b}\nAllow: /\n\n" for b in (
        "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User",
        "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended", "Bingbot"))
    return PlainTextResponse(
        ai + "User-agent: *\nAllow: /\n"
        "Disallow: /api/\nDisallow: /account\nDisallow: /watchlist\n"
        "Disallow: /reset-password\nDisallow: /admin/\nDisallow: /unsubscribe\n"
        f"\nSitemap: {base}/sitemap.xml\n")


def _extra_pages():
    """Oyuncu sayfalari ve sezonun biten maclari (Google'in bulmasi icin). Punt
    siralamalari ayni sayfanin sorgulu hali (canonical /rankings), haritaya konmuyor."""
    from services.nba_pages import indexed_games
    return players.sitemap_paths() + [path for path, _ in indexed_games()]


@app.get("/llms.txt", include_in_schema=False)
def llms():
    """Yapay zeka asistanlari icin site ozeti (llmstxt.org)."""
    base = config.SITE_URL.rstrip("/")
    return PlainTextResponse(f"""# HoopLife NBA

> NBA scores, box scores with team and player shot charts, standings, player stats and game logs for the
> 2026-27 season, plus fantasy basketball tools (9-cat rankings, trade analyzer, ESPN/Yahoo league tools),
> an NBA injury report and daily NBA games. Free to use; a free account saves leagues, picks and streaks.

## NBA scores and stats (2026-27 season)
- [NBA scores today]({base}/nba/scores): every game of the day with live and final scores; any date via ?date=YYYY-MM-DD.
- [Game pages]({base}/nba/scores): one page per game - box score, quarter scores, top performers, team and player shot charts, recap.
- [NBA standings]({base}/nba/standings): Eastern and Western Conference tables with games behind, home/road, last 10, streak.
- [Player stats and game logs]({base}/players/victor-wembanyama): 2026-27 season averages, every game this season, fantasy outlook.
- [NBA injury report]({base}/injuries): every injured player by team, updated through the day.
- [Box scores and fantasy scoring]({base}/): yesterday's games with every player scored the way your fantasy league scores; tap a player for his shot chart.

## Fantasy basketball
- [Fantasy basketball waiver wire]({base}/waiver-wire): best pickups this week - players owned in under 50% of ESPN leagues ranked by 9-cat value over the last 7 / 15 days or season, with the hottest adds and per-category filters (STL, BLK, 3PM...).
- [Fantasy basketball rankings 2026-27]({base}/rankings): top 300 for 9-cat leagues; re-rank for punt FT%, FG%, AST, 3PM, PTS, TO.
- [Trade analyzer]({base}/trade-analyzer): who wins a trade, category by category, for 9-cat, 8-cat and points leagues, including 2-for-1 roster-spot math.
- [My League]({base}/league): ESPN and Yahoo league standings, power rankings, weekly expected scores, category projections and matchup predictions.
- [Player trends]({base}/trends): who is rising and falling over the last weeks.

## Daily NBA games
- [Mystery Player]({base}/daily): guess the NBA player in 8 tries (Wordle-style).
- [Stat Match]({base}/stat-match): match two stat lines to two players.
- [Starting Five]({base}/starting-five): name the missing starters of a real playoff game.
- [82-0 Challenge]({base}/82-0): build a five from random teams and eras and try to go 82-0.
- [NBA over/under win totals]({base}/over-under): preseason Las Vegas win totals for all 30 teams and how each team is tracking.
""")


def _indexnow_key():
    import hashlib
    return hashlib.sha256((config.SECRET_KEY + "indexnow").encode()).hexdigest()[:32]


@app.get("/{key}.txt", include_in_schema=False)
def indexnow_key(key: str):
    if key != _indexnow_key():
        raise HTTPException(404)
    return PlainTextResponse(key)


def _ping_indexnow(paths=None):
    """Bing/Yandex'e (ChatGPT arama ve Copilot Bing dizinini kullanir) sayfalari bildir."""
    import requests
    base = config.SITE_URL.rstrip("/")
    urls = [base + p for p in (paths if paths is not None else PUBLIC_PAGES + _extra_pages())]
    if not urls:
        return
    try:
        r = requests.post("https://api.indexnow.org/indexnow", timeout=20, json={
            "host": base.split("//", 1)[1], "key": _indexnow_key(), "keyLocation": f"{base}/{_indexnow_key()}.txt",
            "urlList": urls[:10000]})
        print(f"indexnow: {r.status_code} for {len(urls)} urls")
    except Exception as exc:
        print(f"indexnow failed: {exc}")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    """Google'in tarayacagi herkese acik sayfalar."""
    from datetime import date
    from fastapi.responses import Response
    base = config.SITE_URL.rstrip("/")
    urls = "".join(f"<url><loc>{base}{path}</loc><lastmod>{date.today()}</lastmod></url>"
                   for path in PUBLIC_PAGES + _extra_pages())
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
        from services.trade_values import players as trade_players
        step("trade values", lambda: trade_players("proj"))
        from services.player_pages import table as player_table
        step("player pages", player_table)
        from services import nba_pages, waiver
        step("game index", nba_pages.refresh_index)
        step("waiver wire", lambda: waiver.board("15"))

        def games_loop():
            """
            Sezon boyunca: biten maclarin sayfalari site haritasina girer ve
            Bing'e (IndexNow) bildirilir; skor ve puan durumu sayfalari da.
            Ilk bildirim yeni surum trafige acildiktan sonra (anahtar dosyasi).
            """
            time.sleep(240)
            if config.PRODUCTION:
                _ping_indexnow()
            while True:
                time.sleep(1800)
                try:
                    fresh = nba_pages.refresh_index()
                    if fresh and config.PRODUCTION:
                        _ping_indexnow(fresh + ["/nba/scores", "/nba/standings", "/waiver-wire", "/"])
                except Exception as exc:
                    print(f"game index failed: {exc}")
        threading.Thread(target=games_loop, daemon=True).start()
    finally:
        _WARM_DONE.set()


@app.on_event("startup")
def start_warmup():
    if config.flag("SKIP_WARMUP"):
        _WARM_DONE.set()
        return
    threading.Thread(target=_warm, daemon=True).start()
    # Lig uyarilari: gunde bir e-posta (services/league_digest.py)
    from services import league_digest
    league_digest.start()

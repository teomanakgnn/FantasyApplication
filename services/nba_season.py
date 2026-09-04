"""
Merkezi NBA sezon takvimi ve HTTP yardımcıları.

Uygulamanın her yerinde sabit yıl (2024/2025/2026...) yazmak yerine buradaki
fonksiyonlar kullanılır. Sezon bilgisi ESPN'in kendi takviminden canlı çekilir,
API ulaşılamazsa takvime dayalı bir tahmine düşer.

ESPN sezon numaralandırması bitiş yılını kullanır:
    2026-27 sezonu -> season_year = 2027
"""

from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils.console import configure_console_encoding

# Veri modüllerinin hepsi bu modülü import ediyor; hangi giriş noktasından
# çalışılırsa çalışılsın konsol kodlaması güvenli olsun diye burada da
# çağrılıyor (idempotent).
configure_console_encoding()

# ESPN'in "site.api" hostu Mozilla/* benzeri tarayıcı User-Agent'larını
# Akamai üzerinden 403 ile reddediyor; requests'in kendi UA'sı geçiyor.
# Bu yüzden bu hosta ASLA tarayıcı UA'sı gönderme.
SITE_API_HOST = "site.api.espn.com"

# ESPN sezon tipleri
SEASON_TYPE_PRESEASON = 1
SEASON_TYPE_REGULAR = 2
SEASON_TYPE_POSTSEASON = 3

_SESSION = None


def get_session() -> requests.Session:
    """Retry + connection pooling yapan paylaşımlı requests session'ı."""
    global _SESSION
    if _SESSION is None:
        s = requests.Session()
        retry = Retry(
            total=2,
            backoff_factor=0.4,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=32, pool_maxsize=32)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _SESSION = s
    return _SESSION


def espn_get(url, params=None, timeout=12, headers=None):
    """
    ESPN için güvenli GET. site.api.espn.com'a tarayıcı UA'sı göndermez
    (o host tarayıcı UA'larını 403 ile reddediyor).
    """
    hdrs = dict(headers or {})
    if SITE_API_HOST in url:
        hdrs.pop("User-Agent", None)
        hdrs.pop("user-agent", None)
    return get_session().get(url, params=params, timeout=timeout, headers=hdrs or None)


# ---------------------------------------------------------------- sezon takvimi

_SEASON_CACHE = {"fetched_at": None, "data": None}
_SEASON_CACHE_TTL = timedelta(hours=6)


def _season_dict(season, source):
    year = season.get("year")
    if not year:
        raise ValueError("yanıtta sezon yılı yok")
    stype = season.get("type") or {}
    return {
        "season_year": int(year),
        "season_type": int(stype.get("type") or SEASON_TYPE_REGULAR),
        "season_type_name": stype.get("name") or "Regular Season",
        "start_date": _parse_iso(season.get("startDate")),
        "end_date": _parse_iso(season.get("endDate")),
        # Preseason'da bu alan düzenli sezonun ne zaman başlayacağını verir.
        "phase_end_date": _parse_iso(stype.get("endDate")),
        "source": source,
    }


def _fetch_espn_calendar():
    """
    Canlı sezon takvimini çeker.

    Öncelik istatistik API'sinde: onun 'currentSeason.type' alanı sezonun
    o anki gerçek evresini (Preseason/Regular/Postseason) verir. Scoreboard
    ise hedef sezon tipini döndürdüğü için Eylül'de bile "Regular Season"
    diyebiliyor; o yüzden sadece yedek olarak kullanılır.
    """
    try:
        resp = get_session().get(
            "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete",
            params={"region": "us", "lang": "en", "limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        current = resp.json().get("currentSeason")
        if current:
            return _season_dict(current, "espn:statistics")
    except Exception as exc:
        print(f"⚠️ İstatistik takvimi alınamadı ({exc}); scoreboard deneniyor.")

    url = f"https://{SITE_API_HOST}/apis/site/v2/sports/basketball/nba/scoreboard"
    resp = espn_get(url, timeout=10)
    resp.raise_for_status()
    leagues = resp.json().get("leagues") or []
    if not leagues:
        raise ValueError("scoreboard yanıtında 'leagues' yok")
    return _season_dict(leagues[0].get("season") or {}, "espn:scoreboard")


def _parse_iso(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def _fallback_calendar(today=None):
    """API'ye ulaşılamazsa takvime dayalı tahmin."""
    today = today or datetime.now()
    # NBA sezonu Ekim'de başlar ve takip eden yılın Haziran'ında biter.
    # Ekim veya sonrasıysak sezon gelecek yılın numarasını taşır.
    season_year = today.year + 1 if today.month >= 10 else today.year

    if today.month in (7, 8, 9):
        stype, sname = SEASON_TYPE_PRESEASON, "Offseason"
    elif today.month in (5, 6):
        stype, sname = SEASON_TYPE_POSTSEASON, "Postseason"
    else:
        stype, sname = SEASON_TYPE_REGULAR, "Regular Season"

    return {
        "season_year": season_year,
        "season_type": stype,
        "season_type_name": sname,
        "start_date": datetime(season_year - 1, 10, 21),
        "end_date": datetime(season_year, 6, 30),
        "source": "fallback",
    }


def get_season_info(force_refresh=False):
    """
    Güncel NBA sezon bilgisini döndürür (6 saat bellek içi cache).

    Returns dict: season_year, season_type, season_type_name,
                  start_date, end_date, source
    """
    now = datetime.now()
    cached = _SEASON_CACHE["data"]
    fetched = _SEASON_CACHE["fetched_at"]

    if not force_refresh and cached and fetched and now - fetched < _SEASON_CACHE_TTL:
        return cached

    try:
        info = _fetch_espn_calendar()
    except Exception as exc:  # ağ/parse hatası -> takvime düş
        print(f"⚠️ Sezon takvimi ESPN'den alınamadı ({exc}); tahmine düşülüyor.")
        info = _fallback_calendar(now)

    _SEASON_CACHE["data"] = info
    _SEASON_CACHE["fetched_at"] = now
    return info


def get_current_season_year() -> int:
    """Güncel ESPN sezon yılı (2026-27 sezonu için 2027)."""
    return get_season_info()["season_year"]


def get_stats_season_year() -> int:
    """
    İstatistik göstermek için tercih edilen sezon.

    Sezon henüz başlamadıysa (preseason/offseason) güncel sezonda maç
    olmayacağı için bir önceki sezona düşer. Yine de veri çeken tarafların
    boş sonuçta bir önceki sezona düşmesi beklenir (bkz. season_candidates).
    """
    info = get_season_info()
    if info["season_type"] == SEASON_TYPE_PRESEASON:
        return info["season_year"] - 1
    return info["season_year"]


def season_candidates():
    """
    Veri çekerken sırayla denenecek sezon yılları.

    Sezon başı/sonu geçişlerinde güncel sezonda henüz istatistik olmayabilir;
    bu liste her zaman geçerli bir yedeğe düşmeyi garantiler.
    """
    info = get_season_info()
    current = info["season_year"]
    if info["season_type"] == SEASON_TYPE_PRESEASON:
        # Hazırlık döneminde önce geçen sezon (veri orada), sonra yenisi.
        return [current - 1, current]
    return [current, current - 1]


def get_season_label(season_year=None) -> str:
    """2027 -> '2026-27'"""
    year = season_year or get_current_season_year()
    return f"{year - 1}-{str(year)[2:]}"


def get_season_start_date(season_year=None) -> datetime:
    """
    Verilen sezonun düzenli sezon başlangıç tarihi.
    Bilinmiyorsa Ekim'in 21'i kabul edilir.
    """
    info = get_season_info()
    year = season_year or info["season_year"]

    if year == info["season_year"]:
        # Hazırlık dönemindeysek preseason'ın bitişi = düzenli sezonun başı.
        if info["season_type"] == SEASON_TYPE_PRESEASON and info.get("phase_end_date"):
            return info["phase_end_date"]
        if info.get("start_date"):
            # ESPN'in startDate'i preseason'ı da kapsıyor; düzenli sezon
            # istatistikleri için en erken 15 Ekim'i taban al.
            return max(info["start_date"], datetime(year - 1, 10, 15))

    return datetime(year - 1, 10, 21)


def is_season_active() -> bool:
    """Düzenli sezon veya playoff devam ediyor mu?"""
    return get_season_info()["season_type"] in (SEASON_TYPE_REGULAR, SEASON_TYPE_POSTSEASON)


def is_offseason() -> bool:
    """Sezon dışı / hazırlık dönemi mi?"""
    return not is_season_active()

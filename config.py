"""
Uygulama ayarlari.

Sunucuda (Railway) ayarlar ortam degiskenlerinden gelir. Yerel
gelistirmede ortam degiskeni tanimli degilse eski Streamlit dosyasi
(.streamlit/secrets.toml) okunur; boylece makinedeki mevcut sirlar
tasinmadan calisir. Bu dosya depoya girmez (.gitignore).
"""
import os
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None

ROOT = Path(__file__).resolve().parent
_SECRETS_FILE = ROOT / ".streamlit" / "secrets.toml"


def _load_file():
    if tomllib is None or not _SECRETS_FILE.exists():
        return {}
    try:
        with open(_SECRETS_FILE, "rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return {}


_FILE = _load_file()


def get(name, default=None):
    """Ortam degiskeni, yoksa yerel sir dosyasi, yoksa varsayilan."""
    value = os.environ.get(name)
    # Panelden yapistirilan degerlerde gorunmez satir sonu () kalabiliyor;
    # veritabani adresi bu yuzden cozulemiyordu. Her deger kirpiliyor.
    if value is not None:
        value = value.strip()
    if value not in (None, ""):
        return value
    for key in (name, name.lower()):
        if key in _FILE and _FILE[key] not in (None, ""):
            return _FILE[key]
    return default


def flag(name, default=False):
    value = get(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


# Canli ortam mi? Cerezlerin Secure bayragi buna bagli.
PRODUCTION = flag("PRODUCTION", default=bool(os.environ.get("RAILWAY_ENVIRONMENT")))

SITE_URL = get("SITE_URL", "https://app.hooplifenba.com")
GOOGLE_ANALYTICS_ID = get("GOOGLE_ANALYTICS_ID")

YAHOO_CLIENT_ID = get("YAHOO_CLIENT_ID")
YAHOO_CLIENT_SECRET = get("YAHOO_CLIENT_SECRET")

ESPN_S2 = get("ESPN_S2") or get("espn_s2")
ESPN_SWID = get("ESPN_SWID") or get("swid")

# Cloudflare koprusu (app.hooplifenba.com -> Railway) her istege bu anahtari
# ekler. Anahtar eslesirse koprunun ilettigi gercek alan adi ve ziyaretci IP'si
# kullanilir; eslesmezse bu basliklar yok sayilir (sahte baslikla gelen
# istek hicbir sey kazanmaz).
PROXY_SECRET = get("PROXY_SECRET")

# Hesap panelinde "Grant Pro" formunu gorebilen kullanici adlari.
ADMIN_USERNAMES = {u.strip() for u in (get("ADMIN_USERNAMES", "admin") or "").split(",")
                   if u.strip()}

# Yayına alma (Railway)

Uygulama FastAPI ile yazılmış tek bir web sunucusu (`web/`). Railway depodaki
`Dockerfile` ve `railway.json` ile kendiliğinden kurulur, her push'ta yeniden
yayına alınır.

## Nasıl kurulu

- **Railway**: proje `hooplife-nba`, servis `web`, bölge EU West. `main`
  dalına her push otomatik yayına alınır. Railway adresi:
  `https://web-production-3cd60.up.railway.app`
- **app.hooplifenba.com**: Cloudflare DNS'te `CNAME app -> c33ci7og.up.railway.app`
  (DNS only / gri bulut). Sertifikayı Railway (Let's Encrypt) veriyor.
- **hooplifenba.com**: açılış sayfası Worker'ı `lively-voice-08bf`
  (`cloudflare/landing/`). `/app` yeni uygulamaya yönlendirir.
  Güncellemek: `cd cloudflare/landing && npx wrangler deploy`
- **Streamlit Cloud** (`fantasyapplication.streamlit.app`): yalnızca "taşındı"
  sayfası (`app.py`). İstenirse Streamlit panelinden tamamen silinebilir.

## Değişkenleri değiştirmek

`railway variables --service web --set "AD=değer"` ya da Railway paneli →
servis → Variables. Değer yapıştırırken sonda boşluk/satır sonu kalırsa
uygulama kırpar.

## Ortam değişkenleri

| Ad | Açıklama |
| --- | --- |
| `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT` | Neon Postgres |
| `GOOGLE_ANALYTICS_ID` | Opsiyonel |
| `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET` | My League → Yahoo bağlantısı |
| `ESPN_S2`, `ESPN_SWID` | Opsiyonel: özel ESPN ligleri |
| `ADMIN_USERNAMES` | Hesap sayfasında "Grant Pro" formunu görenler (virgülle) |
| `PRODUCTION=1` | Çerezleri yalnızca HTTPS'te gönderir |
| `RESEND_API_KEY` | E-posta (Resend) |
| `ALERT_EMAIL` | Sunucu hatalarının bildirileceği adres |
| `PASSWORD_RESET_EMAIL=1` | Alan adı Resend'de doğrulanınca açılır |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` | Kayıt formunda bot koruması |

## Yerelde çalıştırma

```
pip install -r requirements.txt
uvicorn web.app:app --reload --port 8000
```

Yerelde ortam değişkeni yoksa `.streamlit/secrets.toml` okunur.

## Mobil uygulama

`mobile/capacitor.config.json` artık `https://app.hooplifenba.com/` adresini
açıyor. Değişikliğin telefona gitmesi için APK'nın yeniden derlenmesi gerekir:
`cd mobile && npx cap sync android`, ardından Android Studio'dan build.

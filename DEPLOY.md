# Yayına alma (Railway)

Uygulama FastAPI ile yazılmış tek bir web sunucusu (`web/`). Railway depodaki
`Dockerfile` ve `railway.json` ile kendiliğinden kurulur, her push'ta yeniden
yayına alınır.

## İlk kurulum

1. https://railway.com → GitHub ile giriş → **Hobby** plan.
2. **New Project → Deploy from GitHub repo** → `FantasyApplication` deposu.
3. Servis → **Settings**:
   - **Source → Branch**: `main` (geçiş sırasında `railway`)
   - **Region**: `EU West (Amsterdam)` (veritabanı Londra'da; ~8 ms).
4. Servis → **Variables → Raw Editor**: yereldeki `railway.env` dosyasının
   içeriğini yapıştır → **Update Variables**. (Bu dosya depoya girmez.)
5. Servis → **Settings → Networking → Custom Domain**: `app.hooplifenba.com`.
   Railway bir CNAME hedefi verir.
6. Cloudflare → `hooplifenba.com` → **DNS** → CNAME kaydı ekle:
   ad `app`, hedef Railway'in verdiği adres, **Proxy: DNS only (gri bulut)**.
7. Site `https://app.hooplifenba.com` adresinde açılınca Cloudflare Worker'ın
   kodunu `cloudflare-worker.js` ile güncelle (açılış sayfasındaki "Open the app"
   artık yeni adrese gidiyor).

## Ortam değişkenleri

| Ad | Açıklama |
| --- | --- |
| `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT` | Neon Postgres |
| `GOOGLE_ANALYTICS_ID` | Opsiyonel |
| `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET` | My League → Yahoo bağlantısı |
| `ESPN_S2`, `ESPN_SWID` | Opsiyonel: özel ESPN ligleri |
| `ADMIN_USERNAMES` | Hesap sayfasında "Grant Pro" formunu görenler (virgülle) |
| `PRODUCTION=1` | Çerezleri yalnızca HTTPS'te gönderir |

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

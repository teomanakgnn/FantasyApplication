# HoopLife NBA - Mobile APK

Streamlit uygulamasını WebView ile saran Android uygulaması.

## Gereksinimler

- [Android Studio](https://developer.android.com/studio) (APK build için)
- Node.js 18+ (zaten kurulu)

## Kurulum & Build

```bash
# 1. Bağımlılıkları yükle (zaten yapıldı)
cd mobile
npm install

# 2. Android projesini sync et
npx cap sync android

# 3. Android Studio'da aç
npx cap open android
```

## APK Build

Android Studio açıldıktan sonra:

1. **Build** → **Build Bundle(s) / APK(s)** → **Build APK(s)**
2. APK dosyası: `android/app/build/outputs/apk/debug/app-debug.apk`

### Signed APK (Play Store için)

1. **Build** → **Generate Signed Bundle / APK**
2. **APK** seç → keystore oluştur/seç
3. **release** build type seç → **Finish**

## Yapılandırma

| Ayar | Dosya | Açıklama |
|---|---|---|
| App URL | `capacitor.config.json` → `server.url` | Streamlit app adresi |
| App Name | `capacitor.config.json` → `appName` | Uygulama ismi |
| App ID | `capacitor.config.json` → `appId` | Package name |
| Tema | `android/.../styles.xml` | Dark theme renkleri |

## App Icon Değiştirme

1. [Android Asset Studio](https://romannurik.github.io/AndroidAssetStudio/icons-launcher.html) ile ikon oluştur
2. İndirilen dosyaları `android/app/src/main/res/mipmap-*` klasörlerine kopyala

## Proje Yapısı

```
mobile/
├── capacitor.config.json   # Capacitor ayarları
├── package.json            # Node bağımlılıkları
├── resources/
│   └── icon.png           # App ikonu kaynağı
├── www/
│   ├── index.html         # Fallback loading sayfası
│   └── css/style.css      # Loading animasyonu
└── android/               # Android projesi (otomatik oluşturuldu)
    └── app/
        └── src/main/
            ├── AndroidManifest.xml
            └── res/values/styles.xml
```

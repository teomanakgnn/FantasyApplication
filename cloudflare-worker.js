addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  const streamlitBase = 'https://fantasyapplication.streamlit.app'

  // hooplifenba.com/X  ->  streamlit.app/X   (derin linkler korunur)
  const path = url.pathname

  const params = new URLSearchParams(url.search)
  // Uygulama Streamlit Cloud'da private oldugu surece embed=true gerekli:
  // bu parametre olmadan ziyaretciler login ekranina dusuyor.
  params.set('embed', 'true')
  params.delete('embedded')

  const targetUrl = `${streamlitBase}${path}?${params.toString()}`

  const html = `
<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>HoopLife NBA — Fantasy Stats, Mock Draft & Analiz</title>
  <meta name="description" content="NBA fantasy istatistikleri, mock draft simülatörü, sakatlık takibi ve takas analizi.">
  <meta name="theme-color" content="#0B0E14">
  <link rel="icon" href="https://raw.githubusercontent.com/teomanakgnn/FantasyApplication/main/HoopLifeNBA_logo.png">
  <link rel="apple-touch-icon" href="https://raw.githubusercontent.com/teomanakgnn/FantasyApplication/main/HoopLifeNBA_logo.png">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="HoopLife">

  <meta property="og:type" content="website">
  <meta property="og:title" content="HoopLife NBA — Fantasy Stats & Mock Draft">
  <meta property="og:description" content="NBA fantasy istatistikleri, mock draft simülatörü ve takas analizi.">
  <meta property="og:url" content="https://hooplifenba.com/">
  <meta property="og:image" content="https://raw.githubusercontent.com/teomanakgnn/FantasyApplication/main/HoopLifeNBA_logo.png">
  <meta name="twitter:card" content="summary_large_image">

  <style>
    :root { color-scheme: dark; }

    /* ONCEKI SURUMDEKI HATA:
         html, body { overflow: hidden !important; height: 100% }
         iframe     { position: fixed; height: calc(100vh + 50px) }
       iOS'ta (Safari ve Chrome - ikisi de WebKit) iframe'ler
       "duzlestirilir": CSS yuksekligi yok sayilir, iframe icerik boyuna
       kadar uzar ve ic kaydirma verilmez. Dis sayfa da overflow:hidden
       oldugu icin tasan icerik TAMAMEN erisilemez kaliyordu.
       ("Draftı Başlat butonunun alti gozukmuyor ve kaydiramiyorum") */

    html, body {
      margin: 0;
      padding: 0;
      height: 100%;
      background: #0B0E14;
      /* overflow:hidden YOK - kaydirmayi engellemiyoruz */
    }

    /* Streamlit Community Cloud embed modunda uygulamanin etrafina kendi
       kabugunu koyuyor. Olculdu:
         - altta 36px, position:fixed, bottom:0, rgb(240,242,246) acik gri
           "Built with Streamlit / Fullscreen" cubugu
         - uygulamayi her yandan 2px iceri alan acik renkli cerceve
       embed_options ile kaldirilamiyor (hide_footer / dark_theme denendi,
       ucu de degistirmedi). Bu yuzden kirpiliyor:
         #clip  -> gorunur alani sabitler ve tasani gizler
         #app-scroll -> her yandan 2px, alttan 44px disari tasar,
                        boylece cerceve ve rozet gorunur alanin disinda kalir
       Kaydirma korunuyor: #app-scroll hala overflow-y:auto. */
    #clip {
      position: fixed;
      inset: 0;
      overflow: hidden;
      background: #0B0E14;
    }

    #app-scroll {
      position: absolute;
      top: -2px;
      left: -2px;
      right: -2px;
      bottom: -44px;
      overflow-y: auto;
      overflow-x: hidden;
      -webkit-overflow-scrolling: touch;
      overscroll-behavior-y: contain;
      background: #0B0E14;
    }

    #app {
      display: block;
      width: 100%;
      height: 100%;
      min-height: 100%;
      border: 0;
      background: #0B0E14;
    }

    /* Uygulama uyanirken bos beyaz ekran kalmasin */
    #splash {
      position: fixed; inset: 0; z-index: 5;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center; gap: 16px;
      background: #0B0E14; color: #E8EAED; text-align: center; padding: 24px;
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
      transition: opacity .45s ease;
    }
    #splash.hidden { opacity: 0; pointer-events: none; }
    #splash img { width: 128px; max-width: 44vw; }
    #splash .t { font-size: 15px; font-weight: 600; }
    #splash .s { font-size: 13px; color: #9BA3B0; max-width: 300px; line-height: 1.5; }
    .spin {
      width: 26px; height: 26px; border-radius: 50%;
      border: 3px solid rgba(255,255,255,.15); border-top-color: #C8102E;
      animation: sp .9s linear infinite;
    }
    @keyframes sp { to { transform: rotate(360deg); } }
    @media (prefers-reduced-motion: reduce) { .spin { animation: none; } }
  </style>
</head>
<body>
  <div id="splash">
    <img src="https://raw.githubusercontent.com/teomanakgnn/FantasyApplication/main/HoopLifeNBA_logo.png" alt="HoopLife NBA">
    <div class="spin"></div>
    <div class="t">Yükleniyor…</div>
    <div class="s">Uygulama uzun süredir kullanılmadıysa uyanması yarım dakikayı bulabilir.</div>
  </div>

  <div id="clip">
   <div id="app-scroll">
    <iframe id="app"
            src="${targetUrl}"
            title="HoopLife NBA"
            scrolling="yes"
            allow="clipboard-read; clipboard-write; fullscreen"></iframe>
   </div>
  </div>

  <script>
    (function () {
      var s = document.getElementById('splash');
      var a = document.getElementById('app');
      var done = false;
      function hide() {
        if (done) return;
        done = true;
        // iframe'in 'load' olayi Streamlit Cloud kabugu gelince tetikleniyor;
        // uygulamanin kendisi biraz daha gec boyaniyor ve o arada Cloud'un
        // ACIK RENKLI kabugu goruluyor. Bekleme ekranini biraz daha tut.
        setTimeout(function () {
          s.classList.add('hidden');
          setTimeout(function () { s.style.display = 'none'; }, 500);
        }, 2600);
      }
      a.addEventListener('load', hide);
      setTimeout(hide, 20000);
    })();
  </script>
</body>
</html>

`

  return new Response(html, {
    headers: {
      'Content-Type': 'text/html;charset=UTF-8',
      'X-Frame-Options': 'ALLOWALL'
    }
  })
}

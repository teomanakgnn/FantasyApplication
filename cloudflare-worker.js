/**
 * hooplifenba.com - Cloudflare Worker
 *
 * Onceki surum her yolu bir iframe icinde Streamlit uygulamasina
 * sariyordu. Reklam trafigi icin bu yapi calismiyordu:
 *
 *   - Acilis sayfasinda olcum yoktu. Reklamdan gelen ziyaretci once
 *     sarmalayiciya, oradan baska bir kaynaga (streamlit.app) giriyordu;
 *     hangi reklamin ise yaradigi hicbir yerde gorunmuyordu.
 *   - Gizlilik politikasi, kullanim sartlari, robots.txt ve sitemap.xml
 *     yoktu; her yol ayni sarmalayici sayfasini donuyordu. Google Ads
 *     kisisel veri toplayan siteler icin gizlilik politikasi sart
 *     kosuyor, bu site eposta ve parola topluyor.
 *   - Cerez onayi yoktu. Birlesik Krallik/AB trafigi icin analitik
 *     cerezleri once onay ister.
 *   - Ziyaretci, Streamlit uygulamasi uyanana kadar bos ekrana bakiyordu.
 *
 * Bu surum alan adinda gercek bir acilis sayfasi sunuyor: Cloudflare
 * kenarindan aninda aciliyor, olcum ve onay iceriyor, uygulamaya
 * reklam parametrelerini (gclid, utm_*) tasiyarak gonderiyor.
 */

const APP = 'https://fantasyapplication.streamlit.app'
const SITE = 'https://hooplifenba.com'
const LOGO = 'https://raw.githubusercontent.com/teomanakgnn/FantasyApplication/main/HoopLifeNBA_logo.png'
const GA_ID = 'G-L36E2X2BQK'

// Sezon acilisi: sayfadaki geri sayim buna gore hesaplaniyor.
const TIPOFF = '2026-10-20T23:00:00Z'

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  const path = url.pathname.replace(/\/+$/, '') || '/'

  if (path === '/robots.txt') return text(ROBOTS)
  if (path === '/sitemap.xml') return xml(SITEMAP)
  if (path === '/privacy') return html(page('privacy'))
  if (path === '/terms') return html(page('terms'))

  // Uygulama: yonlendirme, iframe degil. Reklam parametreleri korunur ki
  // hangi tiklamanin uygulamaya ulastigi olculebilsin.
  if (path === '/app' || path.startsWith('/app/')) {
    const target = new URL(APP + path.replace(/^\/app/, ''))
    url.searchParams.forEach((v, k) => target.searchParams.set(k, v))
    return Response.redirect(target.toString(), 302)
  }

  if (path === '/') return html(page('home'))
  return html(page('notfound'), 404)
}

const text = body => new Response(body, {
  headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'public, max-age=3600' }
})
const xml = body => new Response(body, {
  headers: { 'content-type': 'application/xml; charset=utf-8', 'cache-control': 'public, max-age=3600' }
})
const html = (body, status = 200) => new Response(body, {
  status,
  headers: {
    'content-type': 'text/html; charset=utf-8',
    'cache-control': 'public, max-age=300',
    'x-content-type-options': 'nosniff',
    'referrer-policy': 'strict-origin-when-cross-origin'
  }
})

const ROBOTS = `User-agent: *
Allow: /
Disallow: /app

Sitemap: ${SITE}/sitemap.xml
`

const SITEMAP = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>${SITE}/</loc><priority>1.0</priority></url>
  <url><loc>${SITE}/privacy</loc><priority>0.3</priority></url>
  <url><loc>${SITE}/terms</loc><priority>0.3</priority></url>
</urlset>
`

// ==================== SAYFA ====================

function page(kind) {
  const titles = {
    home: 'HoopLife NBA - Fantasy Basketball Tools',
    privacy: 'Privacy Policy - HoopLife NBA',
    terms: 'Terms of Use - HoopLife NBA',
    notfound: 'Page not found - HoopLife NBA'
  }
  const descs = {
    home: 'Free fantasy basketball tools: mock draft simulator on live ESPN rankings, draft strategy with punt builds, daily box-score scoring and a trade analyzer.',
    privacy: 'How HoopLife NBA handles your data.',
    terms: 'Terms of use for HoopLife NBA.',
    notfound: 'That page does not exist.'
  }
  const bodies = { home: HOME, privacy: PRIVACY, terms: TERMS, notfound: NOTFOUND }

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>${titles[kind]}</title>
<meta name="description" content="${descs[kind]}">
<link rel="canonical" href="${SITE}${kind === 'home' ? '/' : '/' + kind}">
<link rel="icon" href="${LOGO}">
<link rel="apple-touch-icon" href="${LOGO}">
<meta name="theme-color" content="#0B0E14">
<meta property="og:type" content="website">
<meta property="og:title" content="${titles[kind]}">
<meta property="og:description" content="${descs[kind]}">
<meta property="og:image" content="${LOGO}">
<meta property="og:url" content="${SITE}/">
<meta name="twitter:card" content="summary_large_image">
${STYLE}
</head>
<body>
${bodies[kind]}
${FOOTER}
${CONSENT_UI}
${SCRIPT}
</body>
</html>`
}

const STYLE = `<style>
  *,*::before,*::after{box-sizing:border-box}
  :root{
    --bg:#0B0E14; --panel:#12161F; --card:#171C27; --line:rgba(255,255,255,.09);
    --ink:#E8ECF4; --ink2:#A9B4C6; --ink3:#77839A; --accent:#C8102E; --good:#34D399;
  }
  html,body{margin:0;padding:0;background:var(--bg);color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased;line-height:1.55}
  .wrap{max-width:860px;margin:0 auto;padding:0 20px}
  a{color:inherit}
  .brand{text-decoration:none}
  header{padding:22px 0 0}
  .brand{display:flex;align-items:center;gap:11px}
  .brand img{width:38px;height:38px;border-radius:9px}
  .brand b{font-size:1.02rem;letter-spacing:-.2px}
  .hero{padding:34px 0 8px}
  .kicker{display:inline-block;font-size:.72rem;font-weight:800;letter-spacing:1.3px;
    text-transform:uppercase;color:#FDBA74;background:rgba(249,115,22,.14);
    padding:5px 10px;border-radius:999px;margin-bottom:16px}
  h1{font-size:clamp(1.9rem,6.5vw,2.9rem);line-height:1.1;letter-spacing:-1px;
    font-weight:800;margin:0 0 14px;text-wrap:balance}
  .sub{font-size:1.04rem;color:var(--ink2);margin:0 0 24px;max-width:56ch}
  .cta{display:flex;flex-wrap:wrap;gap:11px;align-items:center}
  .btn{display:inline-flex;align-items:center;justify-content:center;
    min-height:52px;padding:0 26px;border-radius:13px;font-size:1rem;font-weight:700;
    text-decoration:none;border:1px solid transparent;transition:filter .15s ease}
  .btn-main{background:var(--accent);color:#fff}
  .btn-main:active{filter:brightness(.9)}
  .btn-ghost{border-color:var(--line);color:var(--ink2)}
  .note{font-size:.82rem;color:var(--ink3);margin-top:12px}
  section{padding:34px 0;border-top:1px solid var(--line);margin-top:34px}
  h2{font-size:1.3rem;letter-spacing:-.4px;margin:0 0 18px}
  .grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(236px,1fr))}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 17px}
  .card h3{font-size:.98rem;margin:0 0 6px;letter-spacing:-.2px}
  .card p{font-size:.87rem;color:var(--ink2);margin:0}
  .facts{display:flex;flex-wrap:wrap;gap:22px;margin-top:6px}
  .fact b{display:block;font-size:1.5rem;letter-spacing:-.6px}
  .fact span{font-size:.74rem;color:var(--ink3);text-transform:uppercase;letter-spacing:.9px}
  .prose p{color:var(--ink2);font-size:.92rem;max-width:66ch}
  .prose h3{font-size:1rem;margin:22px 0 6px}
  .prose ul{color:var(--ink2);font-size:.92rem;max-width:66ch;padding-left:20px}
  footer{border-top:1px solid var(--line);margin-top:40px;padding:22px 0 34px;
    font-size:.82rem;color:var(--ink3)}
  footer a{color:var(--ink2);text-decoration:none;margin-right:16px}
  #consent{position:fixed;left:12px;right:12px;bottom:12px;z-index:50;
    background:var(--panel);border:1px solid var(--line);border-radius:14px;
    padding:15px 16px;box-shadow:0 14px 40px rgba(0,0,0,.5);display:none}
  #consent p{margin:0 0 12px;font-size:.84rem;color:var(--ink2)}
  #consent .row{display:flex;gap:9px;flex-wrap:wrap}
  #consent button{flex:1;min-width:120px;min-height:44px;border-radius:11px;
    font-size:.88rem;font-weight:700;cursor:pointer;border:1px solid var(--line);
    background:transparent;color:var(--ink2);font-family:inherit}
  #consent button.yes{background:var(--accent);border-color:var(--accent);color:#fff}
  @media (max-width:520px){ .btn{width:100%} .cta{flex-direction:column;align-items:stretch} }
</style>`

const HEADER = `<header><div class="wrap"><a class="brand" href="/">
  <img src="${LOGO}" alt=""><b>HoopLife NBA</b></a></div></header>`

const HOME = `${HEADER}
<main class="wrap">
  <div class="hero">
    <span class="kicker" id="kicker">Season tips off 20 October</span>
    <h1>Win your fantasy basketball draft.</h1>
    <p class="sub">Practise your draft on live ESPN rankings, see which punt build
      actually suits your pick, and score every box score with your own league
      settings. Free, no sign-up needed to start.</p>
    <div class="cta">
      <a class="btn btn-main" href="/app" data-cta="hero">Open the app</a>
      <a class="btn btn-ghost" href="#what">What is inside</a>
    </div>
    <p class="note">Works in the browser on phone and desktop. Nothing to install.</p>
  </div>

  <section id="what">
    <h2>What is inside</h2>
    <div class="grid">
      <div class="card"><h3>Mock draft simulator</h3>
        <p>Snake or auction, 4 to 20 teams, on the current ESPN ranking board.
           Run it as many times as you like before the real thing.</p></div>
      <div class="card"><h3>Draft strategy</h3>
        <p>Tell it your league size and pick slot; it shows who is likely there at
           each of your picks and what roster each punt build gets you.</p></div>
      <div class="card"><h3>Daily box scores</h3>
        <p>Every game scored with your own category weights, so the numbers match
           the league you actually play in.</p></div>
      <div class="card"><h3>Trade analyzer</h3>
        <p>Compare both sides on the categories that matter, including punt
           builds.</p></div>
      <div class="card"><h3>Injury report</h3>
        <p>Who is out, who is a game-time decision, and which team it thins out.</p></div>
      <div class="card"><h3>Watchlist</h3>
        <p>Track players across nights and keep your own notes on each one.</p></div>
    </div>
  </section>

  <section>
    <h2>Built on real numbers</h2>
    <div class="facts">
      <div class="fact"><b>400+</b><span>ranked players</span></div>
      <div class="fact"><b>9</b><span>scoring categories</span></div>
      <div class="fact"><b>30</b><span>team rosters, live</span></div>
    </div>
    <p class="note" style="margin-top:18px">Rankings, ADP and rosters come from
      ESPN and refresh through the season.</p>
  </section>

  <section>
    <h2>Start with the draft</h2>
    <p class="sub">Drafts are won before the season starts. Run a mock, try a punt
      build, see what your slot actually gets you.</p>
    <div class="cta"><a class="btn btn-main" href="/app" data-cta="footer">Open the app</a></div>
  </section>
</main>`

const PRIVACY = `${HEADER}
<main class="wrap prose">
  <section style="border-top:0;margin-top:8px">
    <h1 style="font-size:1.8rem">Privacy Policy</h1>
    <p>Last updated 24 September 2026. HoopLife NBA is run by an individual, not a
      company. This page explains what the site stores and why.</p>

    <h3>What we collect</h3>
    <ul>
      <li><b>Account details.</b> If you create an account we store your username,
        email address and a hashed password. The password itself is never stored.</li>
      <li><b>Things you save.</b> Your watchlist, notes, saved mock drafts and
        display preferences.</li>
      <li><b>Sessions.</b> A random sign-in token so you stay logged in. It is
        stored as a hash on our side and in your browser's local storage.</li>
      <li><b>Analytics.</b> If you accept analytics cookies, Google Analytics
        records anonymous usage: pages visited, device type, and which advert or
        link brought you here. If you decline, no analytics cookies are set.</li>
    </ul>

    <h3>What we do not do</h3>
    <ul>
      <li>We do not sell your data.</li>
      <li>We do not send marketing email.</li>
      <li>We do not take payments, so no card details exist.</li>
    </ul>

    <h3>Third parties</h3>
    <p>Player statistics come from ESPN's public endpoints. The app is hosted on
      Streamlit Community Cloud, the database on Neon, and this page on Cloudflare.
      Analytics, when accepted, is Google Analytics 4.</p>

    <h3>Your choices</h3>
    <p>You can change or delete your account at any time from Account &rarr;
      Settings inside the app; deleting removes your account, watchlist, saved
      drafts and sessions. You can withdraw analytics consent by clearing this
      site's data in your browser.</p>

    <h3>Contact</h3>
    <p>Questions about your data: <a href="mailto:teomanakgn84@gmail.com">teomanakgn84@gmail.com</a>.</p>
  </section>
</main>`

const TERMS = `${HEADER}
<main class="wrap prose">
  <section style="border-top:0;margin-top:8px">
    <h1 style="font-size:1.8rem">Terms of Use</h1>
    <p>Last updated 24 September 2026.</p>

    <h3>What this is</h3>
    <p>HoopLife NBA is a free hobby project that shows publicly available NBA
      statistics and fantasy tools. It is not affiliated with, endorsed by or
      connected to the NBA, ESPN, Yahoo or any team.</p>

    <h3>No guarantees</h3>
    <p>Statistics, rankings and projections come from third-party sources and may
      be wrong, late or missing. Nothing here is betting advice or a prediction of
      any outcome. Use it to prepare for your fantasy league, not to make
      financial decisions.</p>

    <h3>Your account</h3>
    <p>Keep your password to yourself. You are responsible for what happens under
      your account. We may remove accounts that abuse the service.</p>

    <h3>Availability</h3>
    <p>The site is provided as-is and may be offline, slow or changed at any time.</p>

    <h3>Contact</h3>
    <p><a href="mailto:teomanakgn84@gmail.com">teomanakgn84@gmail.com</a></p>
  </section>
</main>`

const NOTFOUND = `${HEADER}
<main class="wrap">
  <section style="border-top:0;margin-top:20px">
    <h1 style="font-size:1.7rem">That page does not exist</h1>
    <p class="sub">The link may be old or mistyped.</p>
    <div class="cta"><a class="btn btn-main" href="/">Go to the home page</a></div>
  </section>
</main>`

const FOOTER = `<footer><div class="wrap">
  <a href="/">Home</a><a href="/privacy">Privacy</a><a href="/terms">Terms</a>
  <div style="margin-top:10px">&copy; 2026 HoopLife NBA. Not affiliated with the NBA or ESPN.</div>
</div></footer>`

const CONSENT_UI = `<div id="consent" role="dialog" aria-label="Cookie choice">
  <p>We use analytics cookies to see which pages and adverts work. Nothing is set
     unless you accept. <a href="/privacy" style="color:#A9B4C6">How we use data</a>.</p>
  <div class="row">
    <button class="yes" id="c-yes">Accept</button>
    <button id="c-no">Decline</button>
  </div>
</div>`

// Consent Mode v2: olcum varsayilan olarak KAPALI baslar, kullanici
// kabul edene kadar hicbir analitik cerezi yazilmaz.
const SCRIPT = `<script>
(function(){
  var KEY='hl_consent';
  window.dataLayer=window.dataLayer||[];
  function gtag(){dataLayer.push(arguments);}
  window.gtag=gtag;
  gtag('consent','default',{
    ad_storage:'denied', ad_user_data:'denied', ad_personalization:'denied',
    analytics_storage:'denied', wait_for_update:500
  });

  function loadGA(){
    if(window.__gaLoaded) return; window.__gaLoaded=true;
    var s=document.createElement('script'); s.async=true;
    s.src='https://www.googletagmanager.com/gtag/js?id=${GA_ID}';
    document.head.appendChild(s);
    gtag('js',new Date());
    // Uygulama baska bir kaynakta calisiyor; ayni ziyaret olarak
    // sayilmasi icin alan adlari birbirine baglaniyor.
    gtag('config','${GA_ID}',{
      linker:{domains:['hooplifenba.com','fantasyapplication.streamlit.app']}
    });
  }

  var saved=null;
  try{ saved=localStorage.getItem(KEY); }catch(e){}
  if(saved==='yes'){
    gtag('consent','update',{ad_storage:'granted',ad_user_data:'granted',
      ad_personalization:'granted',analytics_storage:'granted'});
    loadGA();
  } else if(saved!=='no'){
    var box=document.getElementById('consent');
    if(box) box.style.display='block';
  }

  function decide(ok){
    try{ localStorage.setItem(KEY, ok?'yes':'no'); }catch(e){}
    var box=document.getElementById('consent'); if(box) box.style.display='none';
    if(ok){
      gtag('consent','update',{ad_storage:'granted',ad_user_data:'granted',
        ad_personalization:'granted',analytics_storage:'granted'});
      loadGA();
    }
  }
  var y=document.getElementById('c-yes'), n=document.getElementById('c-no');
  if(y) y.onclick=function(){decide(true);};
  if(n) n.onclick=function(){decide(false);};

  // Uygulamaya gecis: olculebilir tek donusum bu. Reklam parametreleri
  // (gclid, utm_*) uygulamaya tasiniyor ki kaynak kaybolmasin.
  document.querySelectorAll('a[href="/app"]').forEach(function(a){
    a.addEventListener('click',function(){
      try{ gtag('event','open_app',{placement:a.dataset.cta||'unknown'}); }catch(e){}
      var q=location.search;
      if(q && q.length>1) a.href='/app'+q;
    });
  });

  // Sezon geri sayimi
  var k=document.getElementById('kicker');
  if(k){
    var days=Math.ceil((new Date('${TIPOFF}')-new Date())/86400000);
    if(days>1) k.textContent='Season tips off in '+days+' days';
    else if(days===1) k.textContent='Season tips off tomorrow';
    else k.textContent='Season is live';
  }
})();
</script>`

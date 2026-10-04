/**
 * hooplifenba.com - Cloudflare Worker
 *
 * Alan adina gelen her istek uygulamaya (app.hooplifenba.com) kalici
 * olarak yonlendiriliyor. Eskiden burada ayri bir tanitim sayfasi vardi;
 * ziyaretci once tanitimi, sonra "Open the app" ile uygulamayi goruyordu.
 * Reklam ve paylasim trafigi artik dogrudan uygulamaya iniyor; gizlilik
 * ve kullanim sartlari da uygulamanin icinde (/privacy, /terms).
 *
 * Yol ve sorgu korunuyor: hooplifenba.com/mock-draft?utm_source=x ->
 * app.hooplifenba.com/mock-draft?utm_source=x. Eski "/app" linkleri
 * uygulamanin ana sayfasina gidiyor. Parametresiz gelislerde yonlendiren
 * site uygulamada gorunmez (yonlendirmede kaybolur); bu yuzden ?ref=
 * olarak tasiniyor ki kayit kaynagi olcumu bozulmasin.
 */

const APP = 'https://app.hooplifenba.com'

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  let path = url.pathname
  if (path === '/app' || path.startsWith('/app/')) path = path.slice(4) || '/'

  const target = new URL(APP + path)
  url.searchParams.forEach((v, k) => target.searchParams.set(k, v))

  if (![...target.searchParams.keys()].some(k => k === 'ref' || k.startsWith('utm_') || k === 'gclid')) {
    const referer = request.headers.get('referer')
    let host = ''
    try { host = new URL(referer).hostname.replace(/^www\./, '') } catch (e) {}
    if (host && !host.endsWith('hooplifenba.com')) target.searchParams.set('ref', host)
  }
  return Response.redirect(target.toString(), 301)
}

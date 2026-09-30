/**
 * app.hooplifenba.com -> Railway koprusu.
 *
 * Alan adi Cloudflare'de; uygulama Railway'de calisiyor. Bu Worker
 * "custom domain" olarak app.hooplifenba.com'a bagli (Cloudflare DNS
 * kaydini kendisi olusturuyor) ve her istegi Railway'e iletiyor.
 *
 * Uygulama gercek alan adini ve ziyaretci IP'sini X-Forwarded-Host /
 * X-Client-IP basliklarindan okur, ama yalnizca X-Proxy-Secret
 * eslesirse (ayni anahtar Railway'de PROXY_SECRET). Boylece Railway
 * adresine dogrudan gelen sahte basliklar ise yaramaz.
 *
 * Statik dosyalar (/static/) Cloudflare kenarinda onbellege alinir; her
 * surum kendi ?v= adresiyle geldigi icin eski dosya kalmaz.
 */
const ORIGIN = 'https://web-production-3cd60.up.railway.app'

export default {
  async fetch(request, env) {
    const url = new URL(request.url)
    const target = new URL(url.pathname + url.search, ORIGIN)

    const headers = new Headers(request.headers)
    headers.set('X-Forwarded-Host', url.host)
    headers.set('X-Forwarded-Proto', 'https')
    headers.set('X-Client-IP', request.headers.get('CF-Connecting-IP') || '')
    headers.set('X-Proxy-Secret', env.PROXY_SECRET || '')

    const init = {
      method: request.method,
      headers,
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
      redirect: 'manual',
    }
    if (url.pathname.startsWith('/static/') && request.method === 'GET') {
      init.cf = { cacheEverything: true, cacheTtl: 604800 }
    }

    let response
    try {
      response = await fetch(target.toString(), init)
    } catch (err) {
      return new Response('HoopLife NBA is restarting. Try again in a few seconds.', {
        status: 503, headers: { 'content-type': 'text/plain; charset=utf-8', 'retry-after': '5' },
      })
    }

    // Uygulama tam adresli bir yonlendirme yaparsa Railway adresini gizle
    const location = response.headers.get('location')
    if (location && location.startsWith(ORIGIN)) {
      response = new Response(response.body, response)
      response.headers.set('location', location.replace(ORIGIN, `https://${url.host}`))
    }
    return response
  },
}

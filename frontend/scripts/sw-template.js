const ASSETS = __PRECACHE__
const CACHE = 'pashuraksha-shell-' + '__VERSION__'
const ASSET_PATHS = new Set(ASSETS)
self.addEventListener('install', event => {
  // Installation fails intact if any essential asset is unavailable.
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting()))
})
self.addEventListener('activate', event => event.waitUntil((async () => {
  for (const key of await caches.keys()) if (key.startsWith('pashuraksha-shell-') && key !== CACHE) await caches.delete(key)
  await self.clients.claim()
})()))
self.addEventListener('fetch', event => {
  const {request}=event, url=new URL(request.url)
  // Only this build's public files and navigation are eligible. Private API
  // responses, external services and map tiles never enter the shell cache.
  if(request.method!=='GET' || url.origin!==self.location.origin || url.pathname.startsWith('/api/'))return
  if(request.mode==='navigate') {
    event.respondWith(fetch(request).catch(()=>caches.match('/index.html').then(value=>value || Response.error())))
  } else if(ASSET_PATHS.has(url.pathname)) {
    event.respondWith(caches.match(url.pathname).then(value=>value || fetch(request)))
  }
})

const CACHE_NAME = 'rory-app-cache';

const STATIC_ASSETS = [
  '/',
  'index.html',
  'archive.html',
  'admin.html',
  'status.html',
  'style-console.css',
  'apple-touch-icon.png',
  'manifest.json'
];

// Pre-cache core shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Take immediate control
self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Bypass non-GET and all Cloudflare Worker API endpoints
  if (req.method !== 'GET' || url.hostname.includes('workers.dev')) {
    return;
  }

  // 1. HTML Pages (Navigation): Network-first with offline cache fallback
  if (req.mode === 'navigate' || req.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(req)
        .then((networkRes) => {
          if (networkRes.ok) {
            const copy = networkRes.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          }
          return networkRes;
        })
        .catch(() => caches.match(req)) // Serves cached page when offline
    );
    return;
  }

  // 2. Story JSON Data: Stale-While-Revalidate (instant load + background refresh)
  if (url.pathname.endsWith('stories.json') || url.pathname.endsWith('story.json')) {
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cached = await cache.match(req);
        const networkFetch = fetch(req).then((networkRes) => {
          if (networkRes.ok) {
            cache.put(req, networkRes.clone());
          }
          return networkRes;
        }).catch(() => cached);

        return cached || networkFetch;
      })
    );
    return;
  }

  // 3. Static Assets (Icons, Fonts, Images): Cache-first
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
        }
        return res;
      });
    })
  );
});

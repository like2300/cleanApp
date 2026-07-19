// Service Worker minimal pour CLEAN (PWA / mode hors-ligne)
// Met en cache les assets statiques et la page d'accueil pour un fonctionnement
// de base sans réseau. Les données dynamiques (API Django) ne sont pas cachées.

const CACHE_NAME = "clean-cache-v1";
const ASSETS = [
  "/",
  "/static/manifest.webmanifest",
  "/static/favicon.png",
  "/static/css/inter.css",
  "/static/css/fontawesome.min.css",
  "/static/js/tailwind.min.js",
  "/static/js/iconify-icon.min.js",
  "/static/js/iconify-bundle.js",
  "/static/js/chart.min.js",
  "/static/js/qrcode.min.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  // Stratégie "cache d'abord" pour les assets statiques, "réseau d'abord"
  // pour le reste (pages dynamiques).
  if (request.method !== "GET") return;
  if (request.url.includes("/static/")) {
    event.respondWith(
      caches.match(request).then(
        (cached) => cached || fetch(request)
      )
    );
    return;
  }
  event.respondWith(
    fetch(request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        return response;
      })
      .catch(() => caches.match(request))
  );
});

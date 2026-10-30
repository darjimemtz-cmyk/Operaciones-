self.addEventListener('install', (e) => {
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (e) => {
    // Pasa directo al servidor Flask en tiempo real sin congelar la caché
    e.respondWith(fetch(e.request));
});
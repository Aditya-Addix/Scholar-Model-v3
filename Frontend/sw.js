const CACHE_VERSION = "addix-pwa-v1";
const CORE_ASSETS = [
  "./",
  "./index.html",
  "./style.css",
  "./app.js",
  "./manifest.json",
  "./logo.png"
];

const EXTERNAL_ASSETS = [
  "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.11/katex.min.css",
  "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.11/katex.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.11/contrib/auto-render.min.js"
];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_VERSION);
    await cache.addAll(CORE_ASSETS);

    for (const url of EXTERNAL_ASSETS) {
      try {
        const response = await fetch(url, { mode: "no-cors" });
        await cache.put(url, response);
      } catch (error) {
        // External warmup should not block install.
      }
    }

    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys
        .filter((key) => key !== CACHE_VERSION)
        .map((key) => caches.delete(key))
    );
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  event.respondWith((async () => {
    const cached = await caches.match(event.request);
    if (cached) {
      return cached;
    }

    try {
      const networkResponse = await fetch(event.request);
      const url = new URL(event.request.url);
      const isStaticAsset =
        url.origin === self.location.origin ||
        EXTERNAL_ASSETS.includes(event.request.url);

      if (isStaticAsset && networkResponse && networkResponse.status === 200) {
        const cache = await caches.open(CACHE_VERSION);
        await cache.put(event.request, networkResponse.clone());
      }

      return networkResponse;
    } catch (error) {
      const fallback = await caches.match("./index.html");
      if (fallback) {
        return fallback;
      }
      throw error;
    }
  })());
});

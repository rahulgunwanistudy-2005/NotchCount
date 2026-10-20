/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />
/**
 * Offline shell: precache the build so the capture screen opens with no signal. API calls are
 * never cached; photos live in IndexedDB, not here.
 */
import { build, files, version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;
const CACHE = `nc-shell-${version}`;
// The map is for admins at a desk; keep it out of the offline bundle walkers download.
const ASSETS = [...build.filter((f) => !f.includes('maplibre')), ...files, '/200.html'];

sw.addEventListener('install', (event) => {
	event.waitUntil(
		caches
			.open(CACHE)
			.then((cache) => cache.addAll(ASSETS))
			.then(() => sw.skipWaiting())
	);
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
			.then(() => sw.clients.claim())
	);
});

sw.addEventListener('fetch', (event) => {
	const req = event.request;
	const url = new URL(req.url);
	if (req.method !== 'GET' || url.origin !== sw.location.origin || url.pathname.startsWith('/api/')) return;

	if (req.mode === 'navigate') {
		// Shell first: every route renders from the same 200.html, and a sleeping host or no signal
		// must never stand between a walker and the shutter. A new deploy installs a new cache.
		event.respondWith(
			caches.match('/200.html').then((hit) => hit ?? fetch(req).catch(() => Response.error()))
		);
		return;
	}
	if (ASSETS.includes(url.pathname)) {
		event.respondWith(caches.match(url.pathname).then((hit) => hit ?? fetch(req)));
	}
});

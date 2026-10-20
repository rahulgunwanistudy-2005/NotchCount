/**
 * MapLibre helpers. Tiles: OpenFreeMap (free, no key; attribution required and shown by
 * MapLibre). The basemap is recoloured to Limewash and Fog so the route and dots carry colour.
 */
import type { Map as MlMap, StyleSpecification } from 'maplibre-gl';

export const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron';

export async function loadMapLibre() {
	const [mod, worker] = await Promise.all([
		import('maplibre-gl'),
		import('maplibre-gl/dist/maplibre-gl-worker.mjs?url'),
		import('maplibre-gl/dist/maplibre-gl.css')
	]);
	mod.setWorkerUrl(worker.default);
	return mod;
}

export async function quietStyle(): Promise<StyleSpecification | string> {
	try {
		const res = await fetch(STYLE_URL);
		const style = (await res.json()) as StyleSpecification;
		for (const layer of style.layers) {
			const paint = (layer as { paint?: Record<string, unknown> }).paint ?? {};
			if (layer.type === 'background') paint['background-color'] = '#eef2ef';
			else if (layer.type === 'fill') {
				paint['fill-color'] = layer.id.includes('water') ? '#d9e1dd' : '#e6ebe8';
				paint['fill-outline-color'] = '#e6ebe8';
			} else if (layer.type === 'line') {
				paint['line-color'] = layer.id.includes('water') ? '#d9e1dd' : '#ffffff';
			} else if (layer.type === 'symbol') {
				paint['text-color'] = '#5f6b73';
				paint['text-halo-color'] = '#eef2ef';
			}
			(layer as { paint?: Record<string, unknown> }).paint = paint;
		}
		return style;
	} catch {
		return STYLE_URL;
	}
}

export function fitTo(map: MlMap, coords: [number, number][], padding = 40): void {
	if (coords.length === 0) return;
	let [minX, minY] = coords[0];
	let [maxX, maxY] = coords[0];
	for (const [x, y] of coords) {
		minX = Math.min(minX, x);
		minY = Math.min(minY, y);
		maxX = Math.max(maxX, x);
		maxY = Math.max(maxY, y);
	}
	map.fitBounds(
		[
			[minX, minY],
			[maxX, maxY]
		],
		{ padding, maxZoom: 18, duration: 0 }
	);
}

/** Great-circle length of a polyline in metres. */
export function lengthMetres(coords: [number, number][]): number {
	const R = 6371008.8;
	let total = 0;
	for (let i = 1; i < coords.length; i++) {
		const [lon1, lat1] = coords[i - 1].map((v) => (v * Math.PI) / 180);
		const [lon2, lat2] = coords[i].map((v) => (v * Math.PI) / 180);
		const a = Math.sin((lat2 - lat1) / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2;
		total += 2 * R * Math.asin(Math.sqrt(a));
	}
	return total;
}

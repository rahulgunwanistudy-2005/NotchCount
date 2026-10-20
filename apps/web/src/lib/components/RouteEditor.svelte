<script lang="ts">
	import { onMount } from 'svelte';
	import type { GeoJSONSource, Map as MlMap } from 'maplibre-gl';
	import { fitTo, lengthMetres, loadMapLibre, quietStyle } from '$lib/map';

	let {
		points = $bindable<[number, number][]>([]),
		readonly = false,
		center = [77.209, 28.6139] as [number, number]
	}: { points?: [number, number][]; readonly?: boolean; center?: [number, number] } = $props();

	let container = $state<HTMLDivElement | null>(null);
	let map: MlMap | null = null;
	let failed = $state(false);

	const length = $derived(lengthMetres(points));

	function render() {
		const src = map?.getSource('route') as GeoJSONSource | undefined;
		src?.setData({
			type: 'FeatureCollection',
			features: [
				...(points.length > 1
					? [{ type: 'Feature' as const, properties: {}, geometry: { type: 'LineString' as const, coordinates: points } }]
					: []),
				...points.map((c, i) => ({
					type: 'Feature' as const,
					properties: { start: i === 0 },
					geometry: { type: 'Point' as const, coordinates: c }
				}))
			]
		});
	}

	$effect(() => {
		void points.length;
		render();
	});

	onMount(() => {
		let destroyed = false;
		void (async () => {
			try {
				const maplibre = await loadMapLibre();
				if (destroyed || !container) return;
				const m = new maplibre.Map({
					container,
					style: await quietStyle(),
					center: points[0] ?? center,
					zoom: 16,
					attributionControl: { compact: true }
				});
				map = m;
				m.addControl(new maplibre.NavigationControl({ showCompass: false }), 'top-right');
				m.on('load', () => {
					m.addSource('route', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
					m.addLayer({
						id: 'route-line',
						type: 'line',
						source: 'route',
						filter: ['==', '$type', 'LineString'],
						paint: { 'line-color': '#2f5d9e', 'line-width': 5 }
					});
					m.addLayer({
						id: 'route-points',
						type: 'circle',
						source: 'route',
						filter: ['==', '$type', 'Point'],
						paint: {
							'circle-radius': ['case', ['get', 'start'], 8, 5],
							'circle-color': ['case', ['get', 'start'], '#1f2b38', '#ffffff'],
							'circle-stroke-color': '#1f2b38',
							'circle-stroke-width': 2
						}
					});
					render();
					if (points.length > 1) fitTo(m, points);
				});
				if (!readonly) {
					m.on('click', (e) => {
						points = [...points, [Number(e.lngLat.lng.toFixed(6)), Number(e.lngLat.lat.toFixed(6))]];
					});
				}
			} catch {
				failed = true;
			}
		})();
		return () => {
			destroyed = true;
			map?.remove();
		};
	});

	export function locate() {
		navigator.geolocation?.getCurrentPosition((p) =>
			map?.flyTo({ center: [p.coords.longitude, p.coords.latitude], zoom: 17 })
		);
	}
</script>

<div class="editor">
	<div class="map" bind:this={container} role="application" aria-label="Route map"></div>
	{#if failed}<p class="error">The map did not load. Check the connection and reload.</p>{/if}
	{#if !readonly}
		<div class="tools">
			<span class="num">{points.length} points, {(length / 1000).toFixed(2)} km</span>
			<button class="btn quiet" type="button" onclick={locate}>Go to my location</button>
			<button class="btn quiet" type="button" disabled={points.length === 0} onclick={() => (points = points.slice(0, -1))}
				>Remove last point</button
			>
			<button class="btn quiet" type="button" disabled={points.length === 0} onclick={() => (points = [])}>Clear</button>
		</div>
		<p class="hint">Tap the map along the lanes, from the start point in walking order. The dark dot is the start.</p>
	{/if}
</div>

<style>
	.map {
		height: 420px;
		border: 2px solid var(--rule);
		border-radius: var(--radius-control);
		overflow: hidden;
	}
	.tools {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
		align-items: center;
		margin-top: var(--space-3);
	}
	.hint {
		color: var(--fog-text);
		margin-top: var(--space-2);
	}
</style>

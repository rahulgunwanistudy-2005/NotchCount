<script lang="ts">
	/**
	 * The sterilised share on a half dial: the range as a band, the middle value as a filled arc and a number, and
	 * the 70% line rabies control aims for. The numbers are printed under it, so the dial is never
	 * the only way to read them.
	 */
	let {
		share,
		low,
		high,
		target = 0.7,
		label
	}: { share: number; low: number; high: number; target?: number; label: string } = $props();

	const R = 110;
	const CX = 140;
	const CY = 136;
	const point = (v: number, r = R) => {
		const a = Math.PI * (1 - Math.min(1, Math.max(0, v)));
		return { x: CX + r * Math.cos(a), y: CY - r * Math.sin(a) };
	};
	const arc = (from: number, to: number, r = R) => {
		const a = point(from, r);
		const b = point(to, r);
		// A half dial never sweeps more than 180 degrees, so the small arc is always the right one.
		return `M ${a.x} ${a.y} A ${r} ${r} 0 0 1 ${b.x} ${b.y}`;
	};
	const t1 = $derived(point(target, R + 16));
	const t2 = $derived(point(target, R - 16));
	const tl = $derived(point(target, R + 30));
	const pct = (v: number) => `${Math.round(v * 100)}%`;
</script>

<figure class="gauge">
	<svg viewBox="0 0 280 160" role="img" aria-label={label}>
		<path d={arc(0, 1)} class="track" />
		<path d={arc(low, high)} class="band" />
		<path d={arc(0, share)} class="fill" />
		<line x1={t1.x} y1={t1.y} x2={t2.x} y2={t2.y} class="target" />
		<text x={tl.x} y={tl.y} class="tlabel" text-anchor="middle">{pct(target)} target</text>
		<text x={CX} y={CY - 8} class="value" text-anchor="middle">{pct(share)}</text>
		<text x={CX} y={CY + 14} class="sub" text-anchor="middle">sterilised</text>
	</svg>
	<figcaption>
		<span class="num">{pct(low)} to {pct(high)}</span> sterilised.
		{#if high < target}Short of the {pct(target)} target even at the top of the range.
		{:else if low >= target}Above the {pct(target)} target across the whole range.
		{:else}The range crosses the {pct(target)} target.{/if}
	</figcaption>
</figure>

<style>
	.gauge {
		margin: 0;
		max-width: 22rem;
	}
	svg {
		width: 100%;
		height: auto;
		display: block;
		overflow: visible;
	}
	.track {
		fill: none;
		stroke: var(--canvas);
		stroke-width: 26;
		stroke-linecap: round;
	}
	.band {
		fill: none;
		stroke: var(--notched-wash);
		stroke-width: 26;
	}
	.fill {
		fill: none;
		stroke: var(--notched);
		stroke-width: 8;
		stroke-linecap: round;
	}
	.target {
		stroke: var(--plain);
		stroke-width: 4;
		stroke-linecap: round;
	}
	.tlabel {
		font: 600 11px var(--font-body);
		fill: #7a4317;
	}
	.value {
		font: 800 46px var(--font-display);
		fill: var(--slate);
	}
	.sub {
		font: 500 13px var(--font-body);
		fill: var(--fog-text);
	}
	figcaption {
		color: var(--ink-soft);
		font-size: 0.94rem;
		margin-top: var(--space-2);
	}
</style>

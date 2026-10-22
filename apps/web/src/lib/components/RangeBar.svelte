<script lang="ts">
	/**
	 * One estimate with its range: a soft bar from low to high, a slate tick at the middle value and,
	 * when given, a thin mark at what was actually seen. The numbers are always printed beside it.
	 */
	let {
		low,
		mid,
		high,
		seen = null,
		max,
		format = (v: number) => String(Math.round(v)),
		tone = 'sage',
		label
	}: {
		low: number;
		mid: number;
		high: number;
		seen?: number | null;
		max: number;
		format?: (v: number) => string;
		tone?: 'sage' | 'notched';
		label: string;
	} = $props();

	const W = 300;
	const x = (v: number) => 6 + (Math.min(Math.max(v, 0), max) / max) * (W - 12);
</script>

<svg viewBox="0 0 {W} 46" class="range {tone}" role="img" aria-label={label}>
	<line class="axis" x1="6" x2={W - 6} y1="20" y2="20" />
	<rect class="bar" x={x(low)} y="11" width={Math.max(4, x(high) - x(low))} height="18" rx="9" />
	{#if seen !== null}
		<line class="seen" x1={x(seen)} x2={x(seen)} y1="8" y2="32" />
	{/if}
	<line class="mid" x1={x(mid)} x2={x(mid)} y1="6" y2="34" />
	<text x={x(low)} y="44" text-anchor="middle">{format(low)}</text>
	<text x={x(high)} y="44" text-anchor="middle">{format(high)}</text>
</svg>

<style>
	.range {
		width: 100%;
		max-width: 26rem;
		display: block;
		overflow: visible;
	}
	.axis {
		stroke: var(--rule);
		stroke-width: 2;
	}
	.bar {
		fill: var(--sage);
	}
	.notched .bar {
		fill: var(--notched-wash);
	}
	.mid {
		stroke: var(--slate);
		stroke-width: 3;
		stroke-linecap: round;
	}
	.notched .mid {
		stroke: var(--notched);
	}
	.seen {
		stroke: var(--fog-text);
		stroke-width: 1.5;
		stroke-dasharray: 3 3;
	}
	text {
		font: 500 11px var(--font-body);
		fill: var(--fog-text);
		font-variant-numeric: tabular-nums;
	}
</style>

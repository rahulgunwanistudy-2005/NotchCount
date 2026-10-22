<script lang="ts" module>
	export interface StripDog {
		passes: number[];
		status: 'notched' | 'not_notched' | 'not_visible';
		route_m?: number | null;
	}
</script>

<script lang="ts">
	/**
	 * The orchestrated moment (DESIGN_BRIEF): pass 1 dots drop onto a straightened route, pass 2
	 * dots drop below, matched dogs join with short arcs, then the range bar resolves. Once, about
	 * 2.5 s; reduced motion shows the final state.
	 *
	 * Public use passes `positions = null`: dots are evenly spaced in a shuffled order and carry no
	 * location. The team view passes metres along the route.
	 */
	let {
		dogs,
		routeLength = null,
		population = null,
		seen = 0,
		label
	}: {
		dogs: StripDog[];
		routeLength?: number | null;
		population?: { median: number; low: number; high: number } | null;
		seen?: number;
		label: string;
	} = $props();

	const W = 640;
	const PAD = 18;
	const Y_ROUTE = 26;
	const Y1 = 70;
	const Y2 = 150;

	const usePositions = $derived(routeLength !== null && dogs.every((d) => d.route_m !== null && d.route_m !== undefined));

	function spread(n: number, i: number) {
		return n <= 1 ? W / 2 : PAD + (i * (W - 2 * PAD)) / (n - 1);
	}

	const layout = $derived.by(() => {
		const p1 = dogs.filter((d) => d.passes.includes(1));
		const p2 = dogs.filter((d) => d.passes.includes(2));
		const x = (d: StripDog, list: StripDog[]) =>
			usePositions && routeLength
				? PAD + ((d.route_m ?? 0) / routeLength) * (W - 2 * PAD)
				: spread(list.length, list.indexOf(d));
		// Without positions, walk 2 gets its own fixed scramble so the arcs show matching, not a grid.
		const scramble = (d: StripDog) => (dogs.indexOf(d) * 2654435761) % 97;
		const p2order = usePositions ? p2 : [...p2].sort((a, b) => scramble(a) - scramble(b));
		return {
			one: p1.map((d, i) => ({ d, x: x(d, p1), i })),
			two: p2order.map((d, i) => ({ d, x: x(d, p2order), i })),
			p1,
			p2order
		};
	});

	const arcs = $derived(
		layout.one
			.map((a) => {
				const b = layout.two.find((t) => t.d === a.d);
				return b ? { x1: a.x, x2: b.x, k: a.i } : null;
			})
			.filter((v): v is { x1: number; x2: number; k: number } => v !== null)
	);

	const scaleMax = $derived(population ? Math.max(population.high * 1.15, seen + 1) : 1);
	const sx = (v: number) => PAD + (v / scaleMax) * (W - 2 * PAD);
	const delay = (start: number, i: number, n: number, span: number) => start + (n > 1 ? (i / (n - 1)) * span : 0);
</script>

<figure class="strip" aria-label={label}>
	<svg viewBox="0 0 {W} {population ? 240 : 190}" role="img" aria-labelledby="strip-desc">
		<desc id="strip-desc">{label}</desc>
		<defs>
			<pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
				<rect width="5" height="5" fill="#ffffff" />
				<line x1="0" y1="0" x2="0" y2="5" stroke="#8a969e" stroke-width="2" />
			</pattern>
		</defs>
		<line class="route" x1={PAD} x2={W - PAD} y1={Y_ROUTE} y2={Y_ROUTE} />
		<text class="lbl" x={PAD} y={Y1 - 16}>Walk 1</text>
		<text class="lbl" x={PAD} y={Y2 + 30}>Walk 2</text>

		{#each arcs as a (a.k)}
			<path
				class="arc"
				style="animation-delay: {1.6 + (a.k % 12) * 0.03}s"
				d="M {a.x1} {Y1 + 6} C {a.x1} {(Y1 + Y2) / 2}, {a.x2} {(Y1 + Y2) / 2}, {a.x2} {Y2 - 6}"
				pathLength="1"
			/>
		{/each}

		{#each layout.one as p (p.i)}
			<circle
				class="dot {p.d.status}"
				cx={p.x}
				cy={Y1}
				r="6"
				style="animation-delay: {delay(0.1, p.i, layout.one.length, 0.7)}s; --from: {Y_ROUTE - Y1}px"
			/>
		{/each}
		{#each layout.two as p (p.i)}
			<circle
				class="dot {p.d.status}"
				cx={p.x}
				cy={Y2}
				r="6"
				style="animation-delay: {delay(0.9, p.i, layout.two.length, 0.7)}s; --from: {Y_ROUTE - Y2}px"
			/>
		{/each}

		{#if population}
			<g class="range">
				<line class="axis" x1={PAD} x2={W - PAD} y1="205" y2="205" />
				<rect class="bar" x={sx(population.low)} y="197" width={Math.max(2, sx(population.high) - sx(population.low))} height="16" rx="3" />
				<line class="median" x1={sx(population.median)} x2={sx(population.median)} y1="191" y2="219" />
				<line class="seen" x1={sx(seen)} x2={sx(seen)} y1="195" y2="215" />
				<text class="lbl" x={sx(seen)} y="234" text-anchor="middle">{seen} seen</text>
				<text class="lbl strong" x={sx(population.median)} y="186" text-anchor="middle"
					>about {Math.round(population.median)}</text
				>
			</g>
		{/if}
	</svg>
	<figcaption>
		<span class="key"><svg width="12" height="12"><circle cx="6" cy="6" r="5" class="dot notched static" /></svg>
			Ear-notched</span>
		<span class="key"><svg width="12" height="12"><circle cx="6" cy="6" r="5" class="dot not_notched static" /></svg>
			No notch</span>
		<span class="key"><svg width="12" height="12"><circle cx="6" cy="6" r="5" class="dot not_visible static" /></svg>
			Ear not visible</span>
		<span class="key"><svg width="18" height="12"><path d="M2 2 C2 8, 16 4, 16 10" class="arc static" /></svg> Same dog on both walks</span>
		{#if !usePositions}<span class="note">Dots are not placed where the dogs were seen.</span>{/if}
	</figcaption>
</figure>

<style>
	.strip {
		margin: 0;
	}
	svg {
		width: 100%;
		height: auto;
		overflow: visible;
	}
	.route {
		stroke: var(--moss);
		stroke-width: 4;
		stroke-linecap: round;
	}
	.lbl {
		font: 600 12px var(--font-body);
		fill: var(--fog-text);
	}
	.lbl.strong {
		fill: var(--ink);
		font-size: 14px;
	}
	.dot {
		stroke: var(--ink);
		stroke-width: 1.5;
		animation: drop 420ms cubic-bezier(0.3, 1.4, 0.5, 1) both;
	}
	.dot.notched {
		fill: var(--notch-teal);
	}
	.dot.not_notched {
		fill: var(--plain);
	}
	.dot.not_visible {
		fill: url(#hatch);
		stroke: var(--fog);
	}
	.arc {
		fill: none;
		stroke: var(--ink-soft);
		stroke-width: 1.4;
		stroke-dasharray: 1;
		stroke-dashoffset: 1;
		animation: draw 500ms ease-out forwards;
	}
	.range {
		animation: fade 400ms ease-out 2.1s both;
	}
	.axis {
		stroke: var(--rule);
		stroke-width: 2;
	}
	.bar {
		fill: var(--sage);
		stroke: var(--moss);
		stroke-width: 1.5;
	}
	.median {
		stroke: var(--slate);
		stroke-width: 3;
	}
	.seen {
		stroke: var(--fog-text);
		stroke-width: 2;
		stroke-dasharray: 3 2;
	}
	.static {
		animation: none;
		stroke-dashoffset: 0;
	}
	figcaption {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2) var(--space-4);
		color: var(--ink-soft);
		font-size: 0.94rem;
		margin-top: var(--space-2);
	}
	.key {
		white-space: nowrap;
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}
	.note {
		color: var(--fog-text);
		flex-basis: 100%;
	}
	/* The SVG scales down on phones; keep labels and dots readable at about 12 px and 4 px. */
	@media (max-width: 600px) {
		.lbl {
			font-size: 22px;
		}
		.lbl.strong {
			font-size: 24px;
		}
		.dot:not(.static) {
			r: 9px;
		}
	}
	@keyframes drop {
		from {
			transform: translateY(var(--from));
			opacity: 0;
		}
		to {
			transform: none;
			opacity: 1;
		}
	}
	@keyframes draw {
		to {
			stroke-dashoffset: 0;
		}
	}
	@keyframes fade {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.dot,
		.range {
			animation: none;
		}
		.arc {
			animation: none;
			stroke-dashoffset: 0;
		}
	}
</style>

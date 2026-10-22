<script lang="ts">
	/**
	 * "Count a street": walk a made-up lane twice, watch dogs get photographed, and see the same
	 * estimate the engine makes (lib/sim.ts) form, then reveal the whole street and compare.
	 */
	import { onMount } from 'svelte';
	import RangeBar from './RangeBar.svelte';
	import { chapman, makeStreet, mulberry32, wilson, type Coat, type SimDog } from '$lib/sim';

	type Stage = 'ready' | 'walk1' | 'night' | 'walk2' | 'done' | 'revealed';

	const LAYOUTS = {
		wide: {
			w: 1000,
			h: 440,
			path: 'M 40 300 C 190 120, 330 380, 500 250 S 760 70, 960 190',
			r: 13
		},
		compact: {
			w: 600,
			h: 700,
			path: 'M 70 120 C 340 50, 600 180, 450 260 S 70 350, 130 460 S 520 530, 530 630',
			r: 15
		}
	} as const;

	const VISIBILITY = [
		{ label: 'Hard', p: 0.42 },
		{ label: 'Normal', p: 0.62 },
		{ label: 'Easy', p: 0.82 }
	];

	let container: HTMLDivElement;
	let pathEl = $state<SVGPathElement | null>(null);
	let compact = $state(false);
	const L = $derived(compact ? LAYOUTS.compact : LAYOUTS.wide);

	let seed = $state(20261023);
	let visIndex = $state(1);
	let dogs = $state<SimDog[]>(makeStreet(20261023, VISIBILITY[1].p));
	let stage = $state<Stage>('ready');
	let progress = $state(0);
	/** 0 = not photographed, 1 = walk 1, 2 = walk 2, 3 = both. */
	let marks = $state<number[]>([]);
	let flashes = $state<{ id: number; key: number }[]>([]);
	let samples = $state<{ x: number; y: number }[]>([]);
	let decor = $state<{ kind: 'tree' | 'house'; x: number; y: number; s: number; tone: number }[]>([]);
	let reduced = false;

	onMount(() => {
		reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		const ro = new ResizeObserver(([e]) => (compact = e.contentRect.width < 620));
		ro.observe(container);
		return () => ro.disconnect();
	});

	// Sample the lane once per layout so dogs and the walker can sit on it.
	$effect(() => {
		const el = pathEl;
		void L;
		if (!el) return;
		const len = el.getTotalLength();
		const pts = Array.from({ length: 401 }, (_, i) => {
			const p = el.getPointAtLength((i / 400) * len);
			return { x: p.x, y: p.y };
		});
		samples = pts;
		decor = scatterDecor(pts, L.w, L.h, seed);
	});

	function scatterDecor(pts: { x: number; y: number }[], w: number, h: number, s: number) {
		const rnd = mulberry32(s ^ 0x5eed);
		const out: { kind: 'tree' | 'house'; x: number; y: number; s: number; tone: number }[] = [];
		for (let tries = 0; tries < 400 && out.length < (compact ? 14 : 22); tries++) {
			const x = 30 + rnd() * (w - 60);
			const y = 30 + rnd() * (h - 60);
			const near = Math.min(...pts.filter((_, i) => i % 4 === 0).map((p) => Math.hypot(p.x - x, p.y - y)));
			const clash = out.some((d) => Math.hypot(d.x - x, d.y - y) < 46);
			if (near > 92 && !clash) {
				out.push({ kind: rnd() < 0.55 ? 'tree' : 'house', x, y, s: 0.8 + rnd() * 0.5, tone: Math.floor(rnd() * 3) });
			}
		}
		return out;
	}

	function at(t: number, side: number) {
		if (samples.length < 2) return { x: 0, y: 0 };
		const f = Math.min(0.9999, Math.max(0, t)) * (samples.length - 1);
		const i = Math.floor(f);
		const a = samples[i];
		const b = samples[Math.min(i + 1, samples.length - 1)];
		const k = f - i;
		const dx = b.x - a.x;
		const dy = b.y - a.y;
		const n = Math.hypot(dx, dy) || 1;
		return { x: a.x + dx * k + (-dy / n) * side, y: a.y + dy * k + (dx / n) * side };
	}

	const walk = $derived(stage === 'walk2' || stage === 'done' || stage === 'revealed' ? 1 : 0);
	const walker = $derived(at(progress, 0));

	function newStreet(nextSeed = seed + 1) {
		seed = nextSeed;
		dogs = makeStreet(seed, VISIBILITY[visIndex].p);
		marks = dogs.map(() => 0);
		stage = 'ready';
		progress = 0;
		decor = samples.length ? scatterDecor(samples, L.w, L.h, seed) : decor;
	}

	function setVisibility(i: number) {
		visIndex = i;
		newStreet(seed);
	}

	function runWalk(w: 0 | 1) {
		stage = w === 0 ? 'walk1' : 'walk2';
		if (marks.length !== dogs.length) marks = dogs.map(() => 0);
		const duration = reduced ? 0 : 4200;
		const start = performance.now();
		let key = 0;
		const step = (now: number) => {
			progress = duration ? Math.min(1, (now - start) / duration) : 1;
			dogs.forEach((d, i) => {
				const bit = w === 0 ? 1 : 2;
				if (d.seen[w] && d.t[w] <= progress && !(marks[i] & bit)) {
					marks[i] |= bit;
					if (!reduced) {
						const f = { id: i, key: key++ };
						flashes = [...flashes, f];
						setTimeout(() => (flashes = flashes.filter((x) => x !== f)), 700);
					}
				}
			});
			if (progress < 1) requestAnimationFrame(step);
			else stage = w === 0 ? 'night' : 'done';
		};
		requestAnimationFrame(step);
	}

	function next() {
		if (stage === 'ready') runWalk(0);
		else if (stage === 'night') {
			progress = 0;
			runWalk(1);
		} else if (stage === 'done') stage = 'revealed';
		else if (stage === 'revealed') newStreet();
	}

	const n1 = $derived(marks.filter((m) => m & 1).length);
	const n2 = $derived(marks.filter((m) => m & 2).length);
	const m2 = $derived(marks.filter((m) => m === 3).length);
	const est = $derived(stage === 'done' || stage === 'revealed' ? chapman(n1, n2, m2) : null);
	const seenNotched = $derived(dogs.filter((d, i) => marks[i] && d.notched).length);
	const seenDistinct = $derived(marks.filter((m) => m).length);
	const share = $derived(stage === 'done' || stage === 'revealed' ? wilson(seenNotched, seenDistinct) : null);
	const trueShare = $derived(dogs.filter((d) => d.notched).length / dogs.length);
	const caught = $derived(est ? dogs.length >= Math.floor(est.low) && dogs.length <= Math.ceil(est.high) : false);

	const visible = (i: number) => stage === 'revealed' || marks[i] > 0;
	const dogPos = (d: SimDog, i: number) => {
		// Before the second walk dogs stand where walk 1 found them; after it, where they wandered to.
		const w = stage === 'walk2' || stage === 'done' || stage === 'revealed' ? 1 : 0;
		void i;
		return at(d.t[w], d.side[w]);
	};

	const COAT: Record<Coat, string> = {
		tan: '#c48a4f',
		ginger: '#d27434',
		cream: '#eedfc2',
		black: '#2f2b28',
		patch: '#e9dcc6'
	};

	const buttonLabel = $derived(
		{
			ready: 'Start walk 1',
			walk1: 'Walking…',
			night: 'Walk again next morning',
			walk2: 'Walking…',
			done: 'Reveal the whole street',
			revealed: 'Try a new street'
		}[stage]
	);

	const narration = $derived(
		{
			ready: 'A made-up lane at dawn. You cannot see the dogs yet: you only learn about the ones you photograph.',
			walk1: `Walk 1: ${n1} dogs photographed so far.`,
			night: `Walk 1 found ${n1} dogs. Overnight they move about a little. Walk the same lane again.`,
			walk2: `Walk 2: ${n2} dogs photographed, ${m2} of them already seen on walk 1.`,
			done: est
				? `${m2} of the ${n2} dogs on walk 2 were already known. That ratio gives the total.`
				: 'No dog was seen on both walks, so there is no estimate. Real surveys walk again.',
			revealed: est
				? caught
					? `There are really ${dogs.length} dogs. The range caught the truth: the ${dogs.length - seenDistinct} dogs never photographed were counted from the ratio.`
					: `There are really ${dogs.length} dogs, outside the range this time. With perfect matching that happens about 1 street in 20.`
				: `There are really ${dogs.length} dogs.`
		}[stage]
	);
</script>

<div class="sim" bind:this={container}>
	<div class="stage">
		<svg viewBox="0 0 {L.w} {L.h}" role="img" aria-label="A simulated lane with dogs along it, seen from above">
			<defs>
				<radialGradient id="sim-sun" cx="0.85" cy="0.05" r="0.6">
					<stop offset="0" stop-color="#fbe5cf" />
					<stop offset="1" stop-color="#fbe5cf" stop-opacity="0" />
				</radialGradient>
			</defs>
			<rect width={L.w} height={L.h} fill="var(--sage)" />
			<rect width={L.w} height={L.h} fill="url(#sim-sun)" />

			{#each decor as d, i (i)}
				{#if d.kind === 'tree'}
					<g transform="translate({d.x} {d.y}) scale({d.s})">
						<circle r="17" fill={['#b4c48a', '#a3b57a', '#c3cf9c'][d.tone]} />
						<circle r="9" cx="-6" cy="-5" fill="#ffffff" opacity="0.18" />
					</g>
				{:else}
					<g transform="translate({d.x} {d.y}) scale({d.s})">
						<rect x="-18" y="-14" width="36" height="28" rx="5" fill={['#f7f6ec', '#fbe5cf', '#eef0e1'][d.tone]} />
						<path d="M -21 -12 L 0 -27 L 21 -12 Z" fill={['#d27434', '#75906a', '#3c5958'][d.tone]} opacity="0.85" />
						<rect x="-5" y="2" width="10" height="12" rx="2" fill="#3c5958" opacity="0.5" />
					</g>
				{/if}
			{/each}

			<path d={L.path} class="kerb" />
			<path d={L.path} class="road" bind:this={pathEl} />
			<path d={L.path} class="centre" />

			{#if samples.length}
				{#if stage !== 'ready'}
					<path
						d={L.path}
						class="trail"
						pathLength="1"
						stroke-dasharray="1"
						stroke-dashoffset={1 - progress}
						class:second={walk === 1}
					/>
				{/if}

				{#each dogs as d, i (d.id)}
					{@const p = dogPos(d, i)}
					<g
						class="dog"
						class:shown={visible(i)}
						class:ghost={stage === 'revealed' && !marks[i]}
						class:faded={(stage === 'walk2' || stage === 'done') && marks[i] === 1}
						style="transform: translate({p.x}px, {p.y}px)"
					>
						{#if marks[i] === 3}<circle r={L.r + 7} class="ring both" />{/if}
						{#if marks[i] === 1 || marks[i] === 3}<circle r={L.r + 3.5} class="ring one" />{/if}
						{#if marks[i] === 2}<circle r={L.r + 3.5} class="ring two" />{/if}
						<circle r={L.r} fill={COAT[d.coat]} class="body" />
						{#if d.coat === 'patch'}<circle r={L.r * 0.45} cx={L.r * 0.3} cy={L.r * 0.25} fill="#7a4a24" />{/if}
						{#if d.notched}
							<path
								d="M {-L.r * 1.05} {-L.r * 0.35} L {-L.r * 0.35} {-L.r * 0.35} L {-L.r * 0.7} {-L.r * 1.05} Z"
								transform="rotate(10)"
								fill="var(--sage)"
								class="notch"
							/>
						{/if}
					</g>
				{/each}

				{#each flashes as f (f.key)}
					{@const p = dogPos(dogs[f.id], f.id)}
					<circle cx={p.x} cy={p.y} r={L.r} class="flash" />
				{/each}

				{#if stage === 'walk1' || stage === 'walk2'}
					<g style="transform: translate({walker.x}px, {walker.y}px)">
						<circle r={compact ? 70 : 80} class="view" />
						<circle r={L.r + 5} class="walker" />
						<path
							d="M -6 -2 h 3 l 1.5 -2.5 h 3 l 1.5 2.5 h 3 v 8 h -12 z"
							transform="scale({compact ? 1.25 : 1.1})"
							fill="#fff"
						/>
					</g>
				{/if}
			{/if}
		</svg>
		<p class="label">Simulation: a made-up street with made-up dogs. The maths is the engine's.</p>
	</div>

	<div class="panel-side">
		<div class="counters" aria-live="polite">
			<div class="c"><span class="k">Walk 1</span><span class="v num">{n1}</span></div>
			<div class="c"><span class="k">Walk 2</span><span class="v num">{stage === 'ready' || stage === 'walk1' || stage === 'night' ? '–' : n2}</span></div>
			<div class="c"><span class="k">Seen on both</span><span class="v num">{stage === 'ready' || stage === 'walk1' || stage === 'night' ? '–' : m2}</span></div>
		</div>

		<p class="narration" aria-live="polite">{narration}</p>

		{#if est}
			<div class="result">
				<p class="big">
					About <span class="num">{Math.round(est.nHat)}</span> dogs live on this street
					<span class="soft">(<span class="num">{Math.round(est.low)} to {Math.round(est.high)}</span>)</span>
				</p>
				<RangeBar
					low={est.low}
					mid={est.nHat}
					high={est.high}
					seen={est.distinct}
					truth={stage === 'revealed' ? dogs.length : null}
					max={Math.max(est.high, dogs.length) * 1.2}
					label="Estimated {Math.round(est.nHat)} dogs, range {Math.round(est.low)} to {Math.round(est.high)}"
				/>
				{#if share}
					<p class="mid">
						<span class="num">{Math.round(share.p * 100)}%</span> are sterilised
						<span class="soft">(<span class="num">{Math.round(share.low * 100)}% to {Math.round(share.high * 100)}%</span>)</span>
					</p>
					<RangeBar
						tone="notched"
						low={share.low}
						mid={share.p}
						high={share.high}
						truth={stage === 'revealed' ? trueShare : null}
						max={1}
						format={(v) => `${Math.round(v * 100)}%`}
						label="Sterilised share {Math.round(share.p * 100)} percent"
					/>
				{/if}
				{#if stage === 'revealed'}
					<p class="truth-line">
						<span class="diamond" aria-hidden="true"></span>The truth: {dogs.length} dogs, {Math.round(trueShare * 100)}% sterilised.
						{seenDistinct} were ever photographed.
					</p>
				{/if}
			</div>
		{/if}

		<div class="controls">
			<button class="btn peach go" onclick={next} disabled={stage === 'walk1' || stage === 'walk2'}>{buttonLabel}</button>
			<fieldset class="vis" disabled={stage !== 'ready'}>
				<legend>How easy the dogs are to spot</legend>
				{#each VISIBILITY as v, i (v.label)}
					<label class:on={visIndex === i}>
						<input type="radio" name="vis" checked={visIndex === i} onchange={() => setVisibility(i)} />{v.label}
					</label>
				{/each}
			</fieldset>
		</div>

		<ul class="legend">
			<li><span class="sw notch-sw" aria-hidden="true"></span>Notch in the ear: sterilised</li>
			<li><span class="sw ring1" aria-hidden="true"></span>Photographed on walk 1</li>
			<li><span class="sw ring2" aria-hidden="true"></span>Seen again on walk 2</li>
		</ul>
	</div>
</div>

<style>
	.sim {
		display: grid;
		gap: var(--space-5);
		background: var(--surface);
		border-radius: var(--radius-shell);
		padding: var(--space-4);
		box-shadow: 0 30px 60px -40px rgba(35, 52, 51, 0.45);
	}
	@media (min-width: 1000px) {
		.sim {
			grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
			padding: var(--space-5);
			align-items: start;
		}
	}
	.stage {
		min-width: 0;
	}
	svg {
		display: block;
		width: 100%;
		height: auto;
		border-radius: var(--radius-panel);
	}
	.label {
		margin: var(--space-2) 0 0;
		font-size: 0.86rem;
		color: var(--fog-text);
	}
	.kerb {
		fill: none;
		stroke: #c9d3ad;
		stroke-width: 58;
		stroke-linecap: round;
	}
	.road {
		fill: none;
		stroke: var(--surface-soft);
		stroke-width: 46;
		stroke-linecap: round;
	}
	.centre {
		fill: none;
		stroke: #e3dfcb;
		stroke-width: 2;
		stroke-dasharray: 10 12;
	}
	.trail {
		fill: none;
		stroke: var(--peach);
		stroke-width: 5;
		stroke-linecap: round;
		opacity: 0.85;
	}
	.trail.second {
		stroke: var(--slate);
		opacity: 0.5;
	}
	.dog {
		opacity: 0;
		transition:
			transform 900ms cubic-bezier(0.4, 0, 0.2, 1),
			opacity 300ms;
	}
	.dog.shown {
		opacity: 1;
	}
	.dog.ghost {
		opacity: 0.55;
	}
	.dog.ghost .body {
		stroke: var(--plain);
		stroke-width: 2;
		stroke-dasharray: 3 3;
	}
	.dog.faded {
		opacity: 0.45;
	}
	.body {
		stroke: rgba(35, 52, 51, 0.35);
		stroke-width: 1;
	}
	.ring {
		fill: none;
		stroke-width: 2.5;
	}
	.ring.one {
		stroke: var(--slate);
	}
	.ring.two {
		stroke: var(--peach);
	}
	.ring.both {
		stroke: var(--peach);
		stroke-width: 3;
	}
	.view {
		fill: #ffffff;
		opacity: 0.22;
	}
	.walker {
		fill: var(--plain);
		stroke: #fff;
		stroke-width: 2.5;
	}
	.flash {
		fill: none;
		stroke: #fff;
		stroke-width: 3;
		animation: flash 650ms ease-out forwards;
		transform-box: fill-box;
		transform-origin: center;
	}
	@keyframes flash {
		from {
			opacity: 1;
			transform: scale(1);
		}
		to {
			opacity: 0;
			transform: scale(3.2);
		}
	}

	.panel-side {
		min-width: 0;
		display: grid;
		gap: var(--space-4);
		align-content: start;
	}
	.counters {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: var(--space-2);
	}
	.c {
		background: var(--surface-soft);
		border-radius: var(--radius-tile);
		padding: var(--space-3);
		display: grid;
	}
	.k {
		font-size: 0.82rem;
		color: var(--fog-text);
	}
	.v {
		font-family: var(--font-display);
		font-weight: 700;
		font-size: var(--step-3);
		color: var(--slate);
		line-height: 1.1;
	}
	.narration {
		margin: 0;
		color: var(--ink-soft);
		min-height: 3.2em;
	}
	.result {
		display: grid;
		gap: var(--space-2);
	}
	.big {
		font-family: var(--font-display);
		font-weight: 700;
		font-size: var(--step-2);
		line-height: 1.2;
		color: var(--slate);
		margin: 0;
	}
	.mid {
		font-family: var(--font-display);
		font-weight: 700;
		color: var(--slate);
		margin: var(--space-3) 0 0;
	}
	.soft {
		font-weight: 400;
		color: var(--ink-soft);
	}
	.truth-line {
		margin: var(--space-2) 0 0;
		background: var(--peach-wash);
		border-radius: var(--radius-tile);
		padding: var(--space-3) var(--space-4);
		font-weight: 500;
	}
	.diamond {
		display: inline-block;
		width: 10px;
		height: 10px;
		background: var(--plain);
		transform: rotate(45deg);
		margin-right: var(--space-2);
	}
	.controls {
		display: grid;
		gap: var(--space-3);
	}
	.go {
		min-height: 52px;
		font-size: var(--step-1);
	}
	.vis {
		border: 0;
		padding: 0;
		margin: 0;
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
		align-items: center;
	}
	.vis legend {
		float: left;
		margin-right: var(--space-2);
		color: var(--fog-text);
		font-size: 0.9rem;
	}
	.vis label {
		display: inline-flex;
		align-items: center;
		min-height: 36px;
		padding: 0 var(--space-4);
		border-radius: var(--radius-control);
		border: 1.5px solid var(--rule);
		cursor: pointer;
		font-size: 0.92rem;
	}
	.vis label.on {
		background: var(--slate);
		border-color: var(--slate);
		color: #fff;
	}
	.vis input {
		position: absolute;
		opacity: 0;
		pointer-events: none;
	}
	.vis label:has(input:focus-visible) {
		outline: 3px solid var(--focus);
		outline-offset: 2px;
	}
	.vis:disabled label {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.legend {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-4);
		font-size: 0.86rem;
		color: var(--ink-soft);
	}
	.legend li {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}
	.sw {
		width: 14px;
		height: 14px;
		border-radius: 50%;
		display: inline-block;
	}
	.notch-sw {
		background: conic-gradient(var(--surface) 0 40deg, #c48a4f 40deg 360deg);
		transform: rotate(-60deg);
	}
	.ring1 {
		border: 2.5px solid var(--slate);
	}
	.ring2 {
		border: 2.5px solid var(--peach);
	}
	@media (prefers-reduced-motion: reduce) {
		.dog {
			transition: none;
		}
	}
</style>

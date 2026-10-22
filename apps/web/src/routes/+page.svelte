<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import Doodle from '$lib/components/Doodle.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import RouteStrip from '$lib/components/RouteStrip.svelte';
	import SiteFooter from '$lib/components/SiteFooter.svelte';
	import SiteHeader from '$lib/components/SiteHeader.svelte';
	import StreetSim from '$lib/components/StreetSim.svelte';
	import { countUp, inview } from '$lib/inview';
	import assets from '$lib/landing-assets.json';
	import { REPO_URL, SAMPLE_REPORT_NOTE, SAMPLE_REPORT_SLUG } from '$lib/site';
	import type { PublicReport } from '$lib/types';

	const sampleHref = `/r/${SAMPLE_REPORT_SLUG}`;
	let sample = $state<PublicReport | null>(null);

	onMount(async () => {
		try {
			sample = await api.get<PublicReport>(`/reports/${SAMPLE_REPORT_SLUG}`);
		} catch {
			/* the section falls back to a link */
		}
	});

	// Problem numbers: each from a public source, listed beside it (docs/BIBLE.md section 1).
	const facts = [
		{
			value: 3717336,
			format: (v: number) => Math.round(v).toLocaleString('en-IN'),
			label: 'dog-bite cases reported in India in 2024',
			source: 'Lok Sabha reply, via IANS',
			href: 'https://ianslive.in/centre-steps-up-stray-dog-control-measures-over-37-lakh-dog-bite-cases-in-2024--20250722185614'
		},
		{
			value: 70,
			format: (v: number) => `${Math.round(v)}%`,
			label: 'of dogs sterilised and vaccinated: the share rabies control aims for',
			source: 'Dhaka mark-resight study, PMC4433337',
			href: 'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4433337/'
		},
		{
			value: 60.6,
			format: (v: number) => `${v.toFixed(1)}%`,
			label: 'the coverage a mark-resight survey actually measured across Dhaka',
			source: 'Same study',
			href: 'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4433337/'
		},
		{
			value: 20000,
			format: (v: number) => Math.round(v).toLocaleString('en-IN'),
			label: 'dogs Chandigarh says it sterilised, against 12,920 strays counted. Residents call the drive "only on paper".',
			source: 'The Tribune',
			href: 'https://www.tribuneindia.com/news/chandigarh/dogged-by-strays-chandigarh-residents-say-sterilisation-drive-only-on-paper-375979'
		}
	];
	let shown = $state(facts.map(() => 0));
	const startCount = () => facts.forEach((f, i) => countUp(f.value, (v) => (shown[i] = v), 1600 + i * 200));

	let pipelineOn = $state(false);
	const hero = assets.hero['hero-dog'];
	const sitting = assets.hero['sitting-dog'];
	const street = assets.street;
	const crops = assets.crops;

	const steps = [
		{
			title: 'Walk the route at dawn',
			body: 'Photograph every dog you pass: the whole dog from the side, then its head with both ears. The app works with no signal and uploads later.'
		},
		{
			title: 'Walk it again next morning',
			body: 'Same route, same time, same pace. Some dogs turn up on both walks, and that overlap is what the count is built from.'
		},
		{
			title: 'Check the matches',
			body: 'The app pairs photos that look like the same dog and looks for the ear notch. People confirm every match and ear it is unsure about.'
		},
		{
			title: 'Send the report',
			body: 'How many dogs use the route and what share are sterilised, each with its range, on one page for the ward officer. Nothing is sent until a team member presses Approve.'
		}
	];
</script>

<svelte:head>
	<title>NotchCount: count the street dogs on your route</title>
	<meta
		name="description"
		content="Walk one route on two mornings, photograph every street dog, and measure what share are really sterilised, with an honest range."
	/>
</svelte:head>

<div class="page">
	<SiteHeader sample={sampleHref} />

	<main>
		<!-- Hero: the claim, and a real photo with the real detector's box on it. -->
		<section class="hero">
			<div class="copy">
				<p class="kicker"><span class="dot" aria-hidden="true"></span>A street-dog census anyone can run</p>
				<h1>Count the dogs on your street. Find out if sterilisation is really happening.</h1>
				<p class="lead">
					A vet cuts a small V from the ear of every dog it sterilises. Walk your lane on two mornings, photograph
					every dog, and NotchCount tells you how many dogs live there and how many carry that notch, with an honest
					range.
				</p>
				<div class="cta">
					<a class="btn peach big" href="#try"><Icon name="survey" size={20} />Try it on a street</a>
					<a class="btn quiet big" href={sampleHref}>Read a sample report</a>
				</div>
				<ul class="proof">
					<li><strong class="num">0.988</strong><span>AUC telling same dog from different dogs, 191 real dogs</span></li>
					<li><strong class="num">2.5 s</strong><span>to blur, crop and embed a photo</span></li>
					<li><strong>Offline</strong><span>capture, for lanes with no signal at 6 am</span></li>
				</ul>
			</div>

			<div class="art">
				<svg class="ring" viewBox="0 0 300 300" aria-hidden="true">
					<defs><path id="ring-path" d="M 150 150 m -128 0 a 128 128 0 1 1 256 0 a 128 128 0 1 1 -256 0" /></defs>
					<text><textPath href="#ring-path">count every dog ~ walk it twice ~ check the ears ~ send the number ~ </textPath></text>
				</svg>
				<Doodle shape="dashes" class="dash-fan" />
				<div class="photo main-photo">
					<figure>
						<img src="/img/hero-dog.webp" alt="A ginger street dog standing on a paved courtyard" width={hero.w} height={hero.h} />
					</figure>
					<svg class="boxes" viewBox="0 0 {hero.w} {hero.h}" aria-hidden="true">
						<rect
							class="det"
							x={hero.box[0]}
							y={hero.box[1]}
							width={hero.box[2] - hero.box[0]}
							height={hero.box[3] - hero.box[1]}
							rx="14"
						/>
					</svg>
					<span class="tag" style="left: {(hero.box[0] / hero.w) * 100}%; top: {(hero.box[1] / hero.h) * 100}%"
						>dog, {Math.round(hero.conf * 100)}%</span
					>
				</div>
				<div class="match-card">
					<div class="thumbs">
						<img src="/img/hero-dog.webp" alt="" width="64" height="80" />
						<img src="/img/sitting-dog.webp" alt="" width="64" height="80" />
					</div>
					<div>
						<p class="mc-title">Same dog?</p>
						<p class="mc-body">Similarity <strong class="num">{assets.hero_similarity.toFixed(2)}</strong>: different dogs</p>
					</div>
				</div>
				<Doodle shape="loops" class="loops" />
			</div>
			<Doodle shape="bean" class="bean" />
			<p class="hero-note">
				Box and similarity are the real output of NotchCount's detector and matcher on these photos.
			</p>
		</section>

		<!-- The problem, in sourced numbers. -->
		<section class="problem" use:inview={startCount} aria-labelledby="problem-h">
			<div class="problem-inner">
				<div class="problem-head">
					<h2 id="problem-h">Cities say they sterilise street dogs. Nobody outside checks.</h2>
					<p>
						India's answer to street dogs is catch, sterilise, vaccinate, ear-notch and return. It only works if enough
						dogs on a street are done. That share is almost never measured by anyone except the operator being paid to
						do it.
					</p>
				</div>
				<div class="facts">
					{#each facts as f, i (f.label)}
						<article class="fact">
							<p class="fact-n num">{f.format(shown[i])}</p>
							<p class="fact-l">{f.label}</p>
							<a class="fact-s" href={f.href} rel="noopener">{f.source}</a>
						</article>
					{/each}
				</div>
			</div>
		</section>

		<!-- The method, as something to play with. -->
		<section class="try" id="try" aria-labelledby="try-h">
			<svg class="wave" viewBox="0 0 1200 120" preserveAspectRatio="none" aria-hidden="true">
				<path d="M0 120 V 60 C 260 110, 560 0, 860 40 S 1140 70, 1200 30 V 120 Z" />
			</svg>
			<div class="try-inner">
				<div class="try-head">
					<h2 id="try-h">Count a street in 30 seconds</h2>
					<p>
						You will never photograph every dog. The trick is to walk twice. If most dogs on the second walk were already
						seen on the first, you missed few; if only some were, you missed many. Walk this lane twice, then reveal the
						dogs you never saw.
					</p>
				</div>
				<StreetSim />
			</div>
		</section>

		<!-- What the pipeline does to a photo, from its real output. -->
		<section class="camera" use:inview={() => (pipelineOn = true)} aria-labelledby="cam-h">
			<h2 id="cam-h">What happens to each photo</h2>
			<p class="intro">Three steps run on every upload, before a person sees anything. These are real results.</p>
			<div class="cam-grid" class:on={pipelineOn}>
				<article class="cam">
					<div class="cam-pic">
						<img src="/img/pipeline/street-blurred.webp" alt="A street scene with every person and a bus blurred" width={street.w} height={street.h} loading="lazy" />
						<svg viewBox="0 0 {street.w} {street.h}" aria-hidden="true">
							{#each street.boxes as b, i (i)}
								<rect
									class="pbox {b.kind}"
									style="transition-delay: {i * 160}ms"
									x={b.box[0]}
									y={b.box[1]}
									width={b.box[2] - b.box[0]}
									height={b.box[3] - b.box[1]}
									rx="10"
								/>
							{/each}
						</svg>
					</div>
					<p class="step-n">1</p>
					<h3>Blur people first</h3>
					<p>
						{street.persons} people and {street.vehicles} bus found and blurred before the photo is stored. The detector then
						checks the blurred photo again; if anyone is still visible, nothing is kept.
					</p>
				</article>
				<article class="cam">
					<div class="cam-pic">
						<img src="/img/sitting-dog.webp" alt="A tan street dog sitting by a wall" width={sitting.w} height={sitting.h} loading="lazy" />
						<svg viewBox="0 0 {sitting.w} {sitting.h}" aria-hidden="true">
							<rect
								class="pbox dog"
								x={sitting.box[0]}
								y={sitting.box[1]}
								width={sitting.box[2] - sitting.box[0]}
								height={sitting.box[3] - sitting.box[1]}
								rx="14"
							/>
						</svg>
						<span class="tag small" style="left: {(sitting.box[0] / sitting.w) * 100}%; top: {(sitting.box[1] / sitting.h) * 100}%"
							>dog, {Math.round(sitting.conf * 100)}%</span
						>
					</div>
					<p class="step-n">2</p>
					<h3>Find every dog</h3>
					<p>
						A YOLO11 detector finds each dog and cuts it out. Sleeping dogs, puppies and dogs half behind a gate all count.
						Cows and cats are never counted as dogs.
					</p>
				</article>
				<article class="cam">
					<div class="cam-pic pair-pic">
						<img src="/img/hero-dog.webp" alt="Crop of the ginger dog" width="320" height="400" loading="lazy" />
						<img src="/img/sitting-dog.webp" alt="Crop of the tan dog" width="320" height="400" loading="lazy" />
						<div class="meter">
							<span class="meter-fill" style="width: {pipelineOn ? assets.hero_similarity * 100 : 0}%"></span>
						</div>
						<p class="meter-l">Similarity {assets.hero_similarity.toFixed(2)}: different dogs</p>
					</div>
					<p class="step-n">3</p>
					<h3>Match across walks</h3>
					<p>
						A DINOv2 model turns each dog into a fingerprint. On photos of 191 real dogs it told the same dog from a
						different one with an AUC of 0.988. When it is unsure, a person decides.
					</p>
					<a class="more" href="{REPO_URL}/blob/main/docs/REID_BENCHMARK.md" rel="noopener">How we measured that</a>
				</article>
			</div>
		</section>

		<!-- Every dog gets its own photo: the crops the pipeline cut from the sample photos. -->
		<section class="gallery" aria-labelledby="gal-h">
			<div class="gal-head">
				<h2 id="gal-h">Every dog gets its own record</h2>
				<p class="hint">Crops cut by NotchCount from 16 street-dog photos (Slyronit, CC BY-SA 4.0). One dog, lying upside down, was missed.</p>
			</div>
			<div class="marquee" aria-hidden="true">
				<div class="track">
					{#each [...crops, ...crops] as c, i (i)}
						<img src={c.src} alt="" width="200" height="200" loading="lazy" class="crop c{i % 4}" />
					{/each}
				</div>
			</div>
		</section>

		<section class="how" id="how">
			<svg class="wave" viewBox="0 0 1200 120" preserveAspectRatio="none" aria-hidden="true">
				<path d="M0 120 V 70 C 300 120, 620 10, 900 30 S 1150 60, 1200 40 V 120 Z" />
			</svg>
			<div class="how-body">
				<figure class="blob-photo">
					<img src="/img/crops/dog-12.webp" alt="A white and brown street dog lying on a pavement" width="320" height="320" loading="lazy" />
				</figure>
				<div class="how-copy">
					<h2>How a team runs it</h2>
					<ol class="steps">
						{#each steps as s, i (s.title)}
							<li>
								<span class="n" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>
								<h3>{s.title}</h3>
								<p>{s.body}</p>
							</li>
						{/each}
					</ol>
				</div>
			</div>
		</section>

		<section class="sample">
			<div class="sample-head">
				<h2>What a report looks like</h2>
				<p class="hint">{SAMPLE_REPORT_NOTE}</p>
			</div>
			<div class="sample-panel">
				{#if sample}
					<div class="sample-numbers">
						{#if sample.headline.population}<p class="big">{sample.headline.population}</p>{/if}
						{#if sample.headline.share}<p class="big">{sample.headline.share}</p>{/if}
						<p>{sample.method_lines[2] ?? ''}</p>
						<a class="btn" href={sampleHref}>Open the sample report</a>
					</div>
					<div class="sample-strip">
						<RouteStrip
							dogs={sample.strip}
							population={sample.results.population ?? null}
							seen={sample.results.counts?.distinct ?? 0}
							label="Each dot is one dog. Top row: first walk. Bottom row: second walk. Lines join the same dog seen on both walks."
						/>
					</div>
				{:else}
					<div class="sample-numbers">
						<p class="big">The count, the sterilised share, each with its range, and how they were made.</p>
						<a class="btn" href={sampleHref}>Open the sample report</a>
					</div>
				{/if}
			</div>
		</section>

		<section class="roles">
			<h2>Who does what</h2>
			<p class="intro">A team is a few neighbours. Each person gets a sign-in link from the team admin.</p>
			<div class="role-row">
				<article class="role walker">
					<span class="role-icon"><Icon name="camera" size={26} /></span>
					<h3>Walkers</h3>
					<p>Walk the route on both mornings with the phone. Two photos per dog, side then head.</p>
					<ul>
						<li>Works offline</li>
						<li>Faces and plates are blurred</li>
						<li>Undo the last photo</li>
					</ul>
				</article>
				<article class="role reviewer">
					<span class="role-icon"><Icon name="pairs" size={26} /></span>
					<h3>Reviewers</h3>
					<p>Sit at a laptop after the walks and answer two questions, one photo at a time.</p>
					<ul>
						<li>Same dog or different?</li>
						<li>Is the ear notched?</li>
						<li>Keyboard: S, D and N</li>
					</ul>
				</article>
				<article class="role admin">
					<span class="role-icon"><Icon name="case" size={26} /></span>
					<h3>Team admin</h3>
					<p>Draws the route, invites the team, runs the estimate and approves the email to the officer.</p>
					<ul>
						<li>Draw the route on a map</li>
						<li>Publish the report</li>
						<li>Approve before anything is sent</li>
					</ul>
				</article>
			</div>
		</section>

		<section class="safety">
			<div class="safety-blob">
				<div class="safety-title">
					<Icon name="warning" size={40} />
					<h2>Before you walk</h2>
				</div>
				<ol>
					<li>An adult goes with every walker under 18.</li>
					<li>Stay at least 3 metres from every dog. Zoom instead of walking closer.</li>
					<li>Do not feed, call, chase or wake the dogs.</li>
					<li>
						If anyone is bitten or scratched, wash the wound with soap and running water for 15 minutes and go for
						anti-rabies treatment the same day.
					</li>
				</ol>
				<a class="btn" href="/app/protocol">Read the full field card</a>
			</div>
		</section>
	</main>

	<SiteFooter />
</div>

<style>
	.page {
		background: var(--surface);
		overflow-x: clip;
		min-height: 100vh;
	}
	main {
		position: relative;
	}
	section h2 {
		font-size: clamp(1.7rem, 1.2rem + 1.8vw, 2.6rem);
	}

	/* ---------- Hero ---------- */
	.hero {
		position: relative;
		display: grid;
		gap: var(--space-7);
		max-width: 78rem;
		margin: 0 auto;
		padding: var(--space-6) var(--space-5) var(--space-8);
		align-items: center;
	}
	@media (min-width: 960px) {
		.hero {
			grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
			padding-left: var(--space-8);
			padding-top: var(--space-7);
		}
	}
	.kicker {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		background: var(--sage);
		color: var(--slate);
		border-radius: var(--radius-control);
		padding: var(--space-1) var(--space-4);
		font-weight: 500;
		font-size: 0.94rem;
	}
	.kicker .dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--plain);
		box-shadow: 0 0 0 4px rgba(207, 122, 48, 0.25);
		animation: pulse 2.4s ease-in-out infinite;
	}
	@keyframes pulse {
		50% {
			box-shadow: 0 0 0 8px rgba(207, 122, 48, 0);
		}
	}
	h1 {
		font-size: clamp(2.3rem, 1.2rem + 4vw, 4.1rem);
		line-height: 1.06;
		letter-spacing: -0.02em;
		max-width: 15ch;
		margin: var(--space-4) 0 var(--space-5);
		animation: rise 900ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
	}
	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(18px);
		}
	}
	.lead {
		font-size: var(--step-1);
		line-height: 1.5;
		color: var(--ink-soft);
		max-width: 34rem;
	}
	.cta {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-3);
		margin-top: var(--space-5);
	}
	.btn.big {
		min-height: 54px;
		padding: 0 var(--space-6);
		font-size: 1.05rem;
	}
	.proof {
		list-style: none;
		padding: 0;
		margin: var(--space-6) 0 0;
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: var(--space-4);
		max-width: 36rem;
	}
	.proof li {
		display: grid;
		align-content: start;
		border-left: 2px solid var(--sage);
		padding-left: var(--space-3);
	}
	.proof strong {
		font-family: var(--font-display);
		font-size: var(--step-2);
		color: var(--slate);
	}
	.proof span {
		font-size: 0.88rem;
		color: var(--fog-text);
		line-height: 1.35;
	}
	.art {
		position: relative;
		justify-self: center;
		width: min(100%, 440px);
		padding: var(--space-5) 0;
	}
	.ring {
		position: absolute;
		width: 132%;
		left: -16%;
		top: -12%;
		animation: spin 60s linear infinite;
		pointer-events: none;
	}
	.ring text {
		font-family: var(--font-display);
		font-size: 14.2px;
		letter-spacing: 0.18em;
		fill: var(--moss);
		opacity: 0.75;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	.photo {
		position: relative;
		z-index: 1;
	}
	.main-photo figure {
		margin: 0;
		aspect-ratio: 4 / 5;
		border-radius: 50% 50% 34px 34px / 34% 34% 34px 34px;
		overflow: hidden;
		box-shadow: 0 40px 70px -40px rgba(35, 52, 51, 0.55);
		animation: rise 1100ms 150ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
	}
	.main-photo img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.boxes {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		overflow: visible;
	}
	.det {
		fill: none;
		stroke: #fff;
		stroke-width: 5;
		stroke-dasharray: 2600;
		stroke-dashoffset: 2600;
		animation: draw 1400ms 900ms ease-out forwards;
		filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.35));
	}
	@keyframes draw {
		to {
			stroke-dashoffset: 0;
		}
	}
	.tag {
		position: absolute;
		transform: translate(-2px, -110%);
		background: #fff;
		color: var(--ink);
		font-weight: 600;
		font-size: 0.9rem;
		border-radius: 10px;
		padding: 2px 10px;
		box-shadow: 0 6px 18px -8px rgba(0, 0, 0, 0.45);
		animation: fade-in 500ms 2100ms both;
		white-space: nowrap;
	}
	.tag.small {
		font-size: 0.8rem;
	}
	@keyframes fade-in {
		from {
			opacity: 0;
			transform: translate(-2px, -80%);
		}
	}
	.match-card {
		position: absolute;
		z-index: 2;
		left: -12%;
		bottom: 4%;
		display: flex;
		align-items: center;
		gap: var(--space-3);
		background: var(--surface);
		border-radius: 20px;
		padding: var(--space-3) var(--space-4) var(--space-3) var(--space-3);
		box-shadow: 0 24px 40px -24px rgba(35, 52, 51, 0.6);
		animation: float 7s ease-in-out infinite, fade-in 600ms 2500ms both;
	}
	@keyframes float {
		50% {
			transform: translateY(-8px);
		}
	}
	.thumbs {
		display: flex;
	}
	.thumbs img {
		width: 44px;
		height: 54px;
		object-fit: cover;
		border-radius: 12px;
		border: 3px solid var(--surface);
	}
	.thumbs img + img {
		margin-left: -14px;
	}
	.mc-title {
		margin: 0;
		font-family: var(--font-display);
		font-weight: 700;
		color: var(--slate);
	}
	.mc-body {
		margin: 0;
		font-size: 0.86rem;
		color: var(--ink-soft);
	}
	.art :global(.dash-fan) {
		width: 70%;
		left: -30%;
		top: -6%;
	}
	.art :global(.loops) {
		width: 42%;
		right: -16%;
		bottom: -14%;
		z-index: 2;
	}
	.hero :global(.bean) {
		width: 56px;
		right: 46%;
		top: 6%;
	}
	.hero-note {
		grid-column: 1 / -1;
		justify-self: end;
		margin: 0;
		font-size: 0.82rem;
		color: var(--fog-text);
	}
	@media (max-width: 959px) {
		.hero :global(.bean) {
			display: none;
		}
	}
	@media (max-width: 640px) {
		.match-card {
			left: 0;
			bottom: -6%;
		}
		.ring {
			width: 118%;
			left: -9%;
		}
	}

	/* ---------- Problem: a dark band ---------- */
	.problem {
		background: var(--slate);
		color: #eef0e1;
		position: relative;
		overflow: hidden;
	}
	.problem::before {
		content: '';
		position: absolute;
		width: 520px;
		height: 520px;
		right: -160px;
		top: -200px;
		border-radius: 46% 54% 42% 58%;
		background: #456766;
	}
	.problem-inner {
		position: relative;
		max-width: 78rem;
		margin: 0 auto;
		padding: var(--space-8) var(--space-5);
		display: grid;
		gap: var(--space-7);
	}
	.problem h2 {
		color: #fff;
		max-width: 20ch;
	}
	.problem-head p {
		color: #d6ddcc;
		max-width: 42rem;
		font-size: var(--step-1);
		line-height: 1.5;
	}
	.facts {
		display: grid;
		gap: var(--space-5);
	}
	@media (min-width: 760px) {
		.facts {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	@media (min-width: 1100px) {
		.facts {
			grid-template-columns: repeat(4, minmax(0, 1fr));
		}
	}
	.fact {
		border-top: 1.5px solid rgba(238, 240, 225, 0.25);
		padding-top: var(--space-4);
	}
	.fact-n {
		font-family: var(--font-display);
		font-weight: 800;
		font-size: clamp(2.2rem, 1.4rem + 2.4vw, 3.3rem);
		line-height: 1;
		color: var(--peach);
		margin: 0 0 var(--space-3);
	}
	.fact-l {
		color: #eef0e1;
		margin: 0 0 var(--space-2);
	}
	.fact-s {
		color: #c9d3ad;
		font-size: 0.86rem;
	}

	/* ---------- Try it ---------- */
	.try {
		position: relative;
		background: var(--sage);
		margin-top: var(--space-8);
	}
	.wave {
		position: absolute;
		left: 0;
		right: 0;
		top: -119px;
		width: 100%;
		height: 120px;
	}
	.wave path {
		fill: var(--sage);
	}
	.try-inner {
		max-width: 80rem;
		margin: 0 auto;
		padding: var(--space-4) var(--space-4) var(--space-8);
	}
	.try-head {
		max-width: 46rem;
		margin: 0 auto var(--space-6);
		text-align: center;
	}
	.try-head p {
		margin: 0 auto;
		font-size: var(--step-1);
		line-height: 1.5;
		color: var(--ink-soft);
	}

	/* ---------- Camera ---------- */
	.camera {
		max-width: 78rem;
		margin: 0 auto;
		padding: var(--space-8) var(--space-5) 0;
	}
	.camera h2,
	.camera .intro {
		text-align: center;
	}
	.intro {
		margin: 0 auto var(--space-6);
		color: var(--ink-soft);
	}
	.cam-grid {
		display: grid;
		gap: var(--space-6);
	}
	@media (min-width: 900px) {
		.cam-grid {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
	}
	.cam {
		position: relative;
	}
	.cam-pic {
		position: relative;
		aspect-ratio: 4 / 5;
		border-radius: var(--radius-panel);
		overflow: hidden;
		background: var(--ink);
	}
	.cam-pic img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.cam-pic svg {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
	}
	.pbox {
		fill: none;
		stroke-width: 5;
		opacity: 0;
		transition: opacity 500ms;
	}
	.pbox.person {
		stroke: #fff;
		stroke-dasharray: 14 10;
	}
	.pbox.vehicle {
		stroke: var(--peach);
		stroke-dasharray: 14 10;
	}
	.pbox.dog {
		stroke: #fff;
	}
	.on .pbox {
		opacity: 1;
	}
	.pair-pic {
		background: var(--surface-soft);
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--space-2);
		padding: var(--space-3);
		align-content: center;
	}
	.pair-pic img {
		border-radius: var(--radius-tile);
		aspect-ratio: 4 / 5;
		height: auto;
	}
	.meter {
		grid-column: 1 / -1;
		height: 12px;
		border-radius: 6px;
		background: var(--canvas);
		overflow: hidden;
		margin-top: var(--space-3);
	}
	.meter-fill {
		display: block;
		height: 100%;
		background: var(--plain);
		border-radius: 6px;
		transition: width 1400ms 300ms cubic-bezier(0.2, 0.8, 0.2, 1);
	}
	.meter-l {
		grid-column: 1 / -1;
		margin: var(--space-1) 0 0;
		font-weight: 600;
		color: var(--slate);
	}
	.step-n {
		position: absolute;
		top: var(--space-3);
		left: var(--space-3);
		margin: 0;
		width: 2.4rem;
		height: 2.4rem;
		border-radius: 50%;
		display: grid;
		place-items: center;
		background: var(--peach);
		color: var(--ink);
		font-family: var(--font-display);
		font-weight: 800;
	}
	.cam h3 {
		margin-top: var(--space-4);
	}
	.more {
		font-weight: 500;
	}

	/* ---------- Gallery marquee ---------- */
	.gallery {
		padding: var(--space-8) 0 0;
	}
	.gal-head {
		max-width: 78rem;
		margin: 0 auto var(--space-5);
		padding: 0 var(--space-5);
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--space-2) var(--space-5);
	}
	.gal-head .hint {
		max-width: 30rem;
	}
	.marquee {
		overflow: hidden;
		mask-image: linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent);
	}
	.track {
		display: flex;
		gap: var(--space-4);
		width: max-content;
		animation: slide 70s linear infinite;
		padding: var(--space-3) 0;
	}
	.marquee:hover .track {
		animation-play-state: paused;
	}
	@keyframes slide {
		to {
			transform: translateX(-50%);
		}
	}
	.crop {
		width: 180px;
		height: 180px;
		object-fit: cover;
		display: block;
		background: var(--canvas);
	}
	.c0 {
		border-radius: 50% 50% 22px 22px / 40% 40% 22px 22px;
	}
	.c1 {
		border-radius: 58% 42% 46% 54% / 52% 58% 42% 48%;
	}
	.c2 {
		border-radius: 28px;
	}
	.c3 {
		border-radius: 50%;
	}
	@media (prefers-reduced-motion: reduce) {
		.track,
		.ring,
		.match-card,
		.kicker .dot {
			animation: none;
		}
		.marquee {
			overflow-x: auto;
		}
	}

	/* ---------- How a team runs it ---------- */
	.how {
		position: relative;
		background: var(--sage);
		margin-top: var(--space-8);
	}
	.how-body {
		display: grid;
		gap: var(--space-6);
		max-width: 78rem;
		margin: 0 auto;
		padding: var(--space-4) var(--space-5) var(--space-8);
	}
	@media (min-width: 900px) {
		.how-body {
			grid-template-columns: minmax(0, 0.7fr) minmax(0, 1.3fr);
			align-items: start;
		}
	}
	.blob-photo {
		margin: -5rem 0 0;
		width: min(100%, 340px);
		aspect-ratio: 1 / 1.05;
		border-radius: 58% 42% 46% 54% / 52% 58% 42% 48%;
		overflow: hidden;
		justify-self: center;
	}
	.blob-photo img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	@media (max-width: 899px) {
		.blob-photo {
			width: 58%;
			margin-top: -3rem;
		}
	}
	.steps {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: var(--space-5);
	}
	@media (min-width: 700px) {
		.steps {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: var(--space-6);
		}
	}
	.n {
		display: inline-grid;
		place-items: center;
		width: 2.6rem;
		height: 2.6rem;
		border-radius: 50%;
		background: var(--peach-wash);
		color: var(--slate);
		font-family: var(--font-display);
		font-weight: 700;
		margin-bottom: var(--space-2);
	}
	.steps h3 {
		margin-bottom: var(--space-2);
	}
	.steps p {
		margin: 0;
	}

	/* ---------- Sample report ---------- */
	.sample,
	.roles {
		max-width: 78rem;
		margin: 0 auto;
		padding: var(--space-8) var(--space-5) 0;
	}
	.sample-head {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--space-2) var(--space-5);
	}
	.sample-head .hint {
		max-width: 34rem;
	}
	.sample-panel {
		margin-top: var(--space-4);
		background: var(--surface-soft);
		border-radius: var(--radius-shell);
		padding: var(--space-6);
		display: grid;
		gap: var(--space-6);
	}
	@media (min-width: 900px) {
		.sample-panel {
			grid-template-columns: minmax(0, 0.8fr) minmax(0, 1.2fr);
			align-items: center;
		}
	}
	.big {
		font-family: var(--font-display);
		font-size: var(--step-3);
		font-weight: 700;
		line-height: 1.2;
		color: var(--slate);
	}
	.sample-strip {
		background: var(--surface);
		border-radius: var(--radius-tile);
		padding: var(--space-4);
		min-width: 0;
	}

	/* ---------- Roles ---------- */
	.roles h2 {
		text-align: center;
	}
	.role-row {
		display: grid;
		gap: var(--space-4);
	}
	@media (min-width: 800px) {
		.role-row {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
	}
	.role {
		border-radius: 6px 6px var(--radius-panel) var(--radius-panel);
		padding: var(--space-6) var(--space-5);
		text-align: center;
	}
	.role-icon {
		display: inline-grid;
		place-items: center;
		width: 3.2rem;
		height: 3.2rem;
		border-radius: 50%;
		background: var(--surface);
		color: var(--slate);
		margin-bottom: var(--space-3);
	}
	.role p {
		color: var(--ink-soft);
	}
	.role ul {
		margin: 0;
		padding: 0;
		list-style: none;
		display: grid;
		gap: var(--space-1);
	}
	.walker {
		background: var(--peach-wash);
	}
	.reviewer {
		background: var(--surface);
		border: 1.5px solid var(--sage-strong);
	}
	.reviewer .role-icon {
		background: var(--sage);
	}
	.admin {
		background: var(--sage);
	}

	/* ---------- Safety ---------- */
	.safety {
		max-width: 64rem;
		margin: 0 auto;
		padding: var(--space-8) var(--space-4) 0;
	}
	.safety-blob {
		background: var(--peach-wash);
		border-radius: 46% 54% 40% 60% / 22% 30% 70% 78%;
		padding: var(--space-7) clamp(1.5rem, 6vw, 5rem);
		display: grid;
		gap: var(--space-4);
	}
	@media (min-width: 800px) {
		.safety-blob {
			grid-template-columns: minmax(0, 0.8fr) minmax(0, 1.2fr);
			align-items: center;
		}
		.safety-blob .btn {
			grid-column: 2;
			justify-self: start;
		}
	}
	@media (max-width: 799px) {
		.safety-blob {
			border-radius: 40px 60px 40px 70px;
		}
	}
	.safety-title {
		color: var(--slate);
	}
	.safety-title h2 {
		margin-top: var(--space-2);
	}
	.safety ol {
		margin: 0;
		padding-left: 1.2rem;
	}
	.safety li {
		margin-bottom: var(--space-2);
	}
</style>

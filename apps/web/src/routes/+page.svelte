<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import Doodle from '$lib/components/Doodle.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import RouteStrip from '$lib/components/RouteStrip.svelte';
	import SiteFooter from '$lib/components/SiteFooter.svelte';
	import SiteHeader from '$lib/components/SiteHeader.svelte';
	import { SAMPLE_REPORT_NOTE, SAMPLE_REPORT_SLUG } from '$lib/site';
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
			body: 'You get how many dogs use the route and what share are sterilised, each with its range, on one page for the ward officer. Nothing is sent until a team member presses Approve.'
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
		<section class="hero">
			<div class="copy">
				<h1>Count the dogs on your street. Find out if sterilisation is really happening.</h1>
				<p class="lead">
					A vet cuts a small V from the ear of every dog it sterilises. Walk your lane on two mornings, photograph
					every dog, and NotchCount tells you how many dogs live there and how many carry that notch.
				</p>
				<div class="cta">
					<a class="btn peach" href="/app"><Icon name="camera" size={18} />Open the app</a>
					<a class="btn quiet" href={sampleHref}>Read a sample report</a>
				</div>
			</div>
			<div class="art">
				<Doodle shape="dashes" class="dash-fan" />
				<figure class="arch">
					<img src="/img/hero-dog.webp" alt="A ginger street dog standing on a paved courtyard" width="640" height="800" />
				</figure>
				<Doodle shape="loops" class="loops" />
			</div>
			<Doodle shape="bean" class="bean" />
		</section>

		<section class="how" id="how">
			<svg class="wave" viewBox="0 0 1200 120" preserveAspectRatio="none" aria-hidden="true">
				<path d="M0 120 V 70 C 300 120, 620 10, 900 30 S 1150 60, 1200 40 V 120 Z" />
			</svg>
			<div class="how-body">
				<figure class="blob-photo">
					<img src="/img/sitting-dog.webp" alt="A tan street dog sitting by a wall" width="640" height="800" loading="lazy" />
				</figure>
				<div class="how-copy">
					<h2>How it works</h2>
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
					<p>The sample report shows the count, its range, and how it was made.</p>
					<a class="btn" href={sampleHref}>Open the sample report</a>
				{/if}
			</div>
		</section>

		<section class="roles">
			<h2>Who does what</h2>
			<p class="intro">A team is a few neighbours. Each person gets a one-time sign-in link from the team admin.</p>
			<div class="role-row">
				<article class="role walker">
					<h3>Walkers</h3>
					<p>Walk the route on both mornings with the phone. Two photos per dog, side then head.</p>
					<ul>
						<li>Works offline</li>
						<li>Faces and plates are blurred</li>
						<li>Undo the last photo</li>
					</ul>
				</article>
				<article class="role reviewer">
					<h3>Reviewers</h3>
					<p>Sit at a laptop after the walks and answer two questions, one photo at a time.</p>
					<ul>
						<li>Same dog or different?</li>
						<li>Is the ear notched?</li>
						<li>Keyboard: S, D and N</li>
					</ul>
				</article>
				<article class="role admin">
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

	/* Hero: copy left, arch photo right, the dash fan behind it. */
	.hero {
		position: relative;
		display: grid;
		gap: var(--space-6);
		max-width: 76rem;
		margin: 0 auto;
		padding: var(--space-7) var(--space-5) var(--space-8);
		align-items: center;
	}
	@media (min-width: 900px) {
		.hero {
			grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
			padding-left: var(--space-8);
		}
	}
	h1 {
		font-size: clamp(2.1rem, 1.3rem + 3vw, 3.4rem);
		line-height: 1.12;
		max-width: 16ch;
		margin-bottom: var(--space-5);
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
	.art {
		position: relative;
		justify-self: center;
		width: min(100%, 420px);
	}
	.arch {
		position: relative;
		margin: 0;
		aspect-ratio: 4 / 4.4;
		border-radius: 50% 50% 28px 28px / 42% 42% 28px 28px;
		overflow: hidden;
		z-index: 1;
	}
	.arch img,
	.blob-photo img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.art :global(.dash-fan) {
		width: 70%;
		left: -28%;
		top: -12%;
	}
	.art :global(.loops) {
		width: 46%;
		right: -16%;
		bottom: -30%;
		z-index: 2;
	}
	.hero :global(.bean) {
		width: 64px;
		left: 2%;
		bottom: 10%;
	}

	/* How it works: a sage band with a wavy top edge. */
	.how {
		position: relative;
		background: var(--sage);
		margin-top: var(--space-6);
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
	.how-body {
		display: grid;
		gap: var(--space-6);
		max-width: 76rem;
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
		counter-reset: none;
	}
	@media (min-width: 700px) {
		.steps {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: var(--space-6) var(--space-6);
		}
	}
	.steps li {
		position: relative;
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
		color: var(--ink);
	}

	/* Sample report */
	.sample,
	.roles {
		max-width: 76rem;
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
		border-radius: var(--radius-panel);
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

	/* Roles: three tiles, each its own colour, after the package cards in the reference. */
	.roles h2 {
		text-align: center;
		font-size: var(--step-3);
	}
	.intro {
		text-align: center;
		margin: 0 auto var(--space-6);
		color: var(--ink-soft);
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
		border-radius: 6px 6px var(--radius-tile) var(--radius-tile);
		padding: var(--space-5);
	}
	.role h3 {
		text-align: center;
	}
	.role p {
		text-align: center;
		color: var(--ink-soft);
	}
	.role ul {
		margin: 0;
		padding-left: 1.1rem;
	}
	.role li {
		margin-bottom: var(--space-1);
	}
	.walker {
		background: var(--peach-wash);
	}
	.reviewer {
		background: var(--surface);
		border: 1.5px solid var(--sage-strong);
	}
	.admin {
		background: var(--sage);
	}

	/* Safety: the peach blob with the warning sign. */
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
		font-size: var(--step-3);
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

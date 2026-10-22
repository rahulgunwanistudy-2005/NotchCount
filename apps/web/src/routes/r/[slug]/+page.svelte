<script lang="ts">
	/** Public report: route-level numbers, each with its range, and how they were made. */
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import Doodle from '$lib/components/Doodle.svelte';
	import Icon from '$lib/components/Icon.svelte';
	import RangeBar from '$lib/components/RangeBar.svelte';
	import RouteStrip from '$lib/components/RouteStrip.svelte';
	import ShareGauge from '$lib/components/ShareGauge.svelte';
	import SiteFooter from '$lib/components/SiteFooter.svelte';
	import SiteHeader from '$lib/components/SiteHeader.svelte';
	import { SAMPLE_REPORT_NOTE, SAMPLE_REPORT_SLUG } from '$lib/site';
	import type { PublicReport } from '$lib/types';

	const slug = page.params.slug ?? '';
	let report = $state<PublicReport | null>(null);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			report = await api.get<PublicReport>(`/reports/${slug}`);
		} catch (e) {
			error = (e as Error).message;
		}
	});

	const wrong = [
		'Dogs that are hard to see (hidden, shy, or away that morning) are under-counted on both walks, so the total is more likely too low than too high.',
		'If the matching software joined two different dogs, or split one dog into two, the total moves. People checked every uncertain match, but the range can still be too narrow.',
		'Dogs whose ears were hidden in every photo are left out of the sterilised share.',
		'This is one route. It does not describe the whole ward.'
	];
	const round = (v: number) => Math.round(v);
	const pct = (v: number) => `${Math.round(v * 100)}%`;
</script>

<svelte:head>
	<title>{report?.title ?? 'NotchCount report'}</title>
</svelte:head>

<div class="page">
	<SiteHeader />

	<main class="report">
		{#if error}
			<p class="error">{error}</p>
		{:else if report}
			{@const r = report.results}
			<section class="hero">
				<div class="hero-copy">
					<h1>{report.title}</h1>
					<p class="byline">{report.route_name}, {report.city}. Counted by {report.team}.</p>
					{#if slug === SAMPLE_REPORT_SLUG}<p class="sample">{SAMPLE_REPORT_NOTE}</p>{/if}

					<div class="numbers" aria-label="Results">
						{#if report.headline.population}
							<p class="big">{report.headline.population}</p>
							{#if r.population}
								<RangeBar
									low={r.population.low}
									mid={r.population.median}
									high={r.population.high}
									seen={r.counts?.distinct ?? null}
									max={Math.max(r.population.high * 1.2, (r.counts?.distinct ?? 0) + 2)}
									label="Range of the dog count: {round(r.population.low)} to {round(r.population.high)}"
								/>
							{/if}
						{/if}
						{#if report.headline.share}
							<p class="big">{report.headline.share}</p>
							{#if r.share}
								<ShareGauge
									share={r.share.median}
									low={r.share.low}
									high={r.share.high}
									label="Sterilised share {pct(r.share.median)}, range {pct(r.share.low)} to {pct(r.share.high)}, against the 70% target"
								/>
							{/if}
						{/if}
						{#if report.headline.deficit}<p class="mid">{report.headline.deficit}</p>{/if}
						{#if report.headline.note}<p class="note">{report.headline.note}</p>{/if}
						{#each r.comparability_problems ?? [] as p (p)}<p class="error">{p}</p>{/each}
					</div>
				</div>

				<div class="viz">
					<Doodle shape="dots" class="viz-dots" />
					<div class="viz-card">
						<h2>Both walks, dog by dog</h2>
						<RouteStrip
							dogs={report.strip}
							population={r.population ?? null}
							seen={r.counts?.distinct ?? 0}
							label="Each dot is one dog. Top row: first walk. Bottom row: second walk. Lines join the same dog seen on both walks."
						/>
					</div>
				</div>
			</section>

			<section class="explain">
				<article class="peachy">
					<h2>How we counted</h2>
					{#each report.method_lines as line (line)}<p>{line}</p>{/each}
				</article>
				<article class="outlined">
					<h2>What we assumed</h2>
					<ul>{#each report.assumptions as a (a)}<li>{a}</li>{/each}</ul>
				</article>
				<article class="sagey">
					<h2>What could be wrong</h2>
					<ul>{#each wrong as w (w)}<li>{w}</li>{/each}</ul>
				</article>
			</section>

			<div class="actions">
				<a class="btn peach" href="/api/v1/reports/{report.slug}.pdf"><Icon name="download" size={18} />Download PDF</a>
			</div>
			<p class="provenance">
				Computed {new Date(report.computed_at).toLocaleString()} by {report.code_version}, method {report.method}, seed
				{report.seed}, data hash {report.data_hash?.slice(0, 16)}. Faces and number plates were blurred before any photo
				was stored. Where individual dogs were seen is not published.
			</p>
		{:else}
			<p class="loading">Loading the report.</p>
		{/if}
	</main>

	<SiteFooter photos={false} />
</div>

<style>
	.page {
		background: var(--surface);
		overflow-x: clip;
		min-height: 100vh;
	}
	.report {
		max-width: 76rem;
		margin: 0 auto;
		padding: var(--space-6) var(--space-5) 0;
	}
	.hero {
		display: grid;
		gap: var(--space-6);
		align-items: center;
	}
	@media (min-width: 960px) {
		.hero {
			grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
			padding-left: var(--space-6);
		}
	}
	h1 {
		font-size: clamp(2rem, 1.3rem + 2.6vw, 3.1rem);
		max-width: 18ch;
	}
	.byline {
		color: var(--ink-soft);
	}
	.sample {
		display: inline-block;
		background: var(--peach-wash);
		border-radius: var(--radius-tile);
		padding: var(--space-2) var(--space-4);
		font-size: 0.94rem;
	}
	.numbers {
		margin-top: var(--space-5);
	}
	.big {
		font-family: var(--font-display);
		font-size: var(--step-3);
		font-weight: 700;
		color: var(--slate);
		line-height: 1.2;
		margin: var(--space-5) 0 var(--space-2);
	}
	.mid {
		font-family: var(--font-display);
		font-size: var(--step-1);
		color: var(--slate);
		margin-top: var(--space-4);
	}
	.note {
		background: var(--peach-wash);
		border-radius: var(--radius-tile);
		padding: var(--space-3) var(--space-4);
		margin-top: var(--space-4);
	}

	/* The strip sits on a sage blob, like the booking panel in the reference. */
	.viz {
		position: relative;
		padding: var(--space-6) var(--space-4);
		isolation: isolate;
	}
	.viz::before {
		content: '';
		position: absolute;
		inset: 0;
		z-index: -1;
		background: var(--sage);
		border-radius: 46% 54% 42% 58% / 38% 44% 56% 62%;
	}
	.viz :global(.viz-dots) {
		width: 56px;
		left: 2%;
		top: 4%;
	}
	.viz-card {
		background: var(--surface);
		border-radius: var(--radius-panel);
		padding: var(--space-5);
		max-width: 40rem;
		margin: 0 auto;
	}
	.viz-card h2 {
		font-size: var(--step-1);
	}

	.explain {
		display: grid;
		gap: var(--space-4);
		margin-top: var(--space-8);
	}
	@media (min-width: 900px) {
		.explain {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
	}
	.explain article {
		border-radius: 6px 6px var(--radius-tile) var(--radius-tile);
		padding: var(--space-5);
	}
	.explain h2 {
		font-size: var(--step-1);
	}
	.explain li {
		margin-bottom: var(--space-2);
	}
	.explain ul {
		padding-left: 1.1rem;
		margin: 0;
	}
	.peachy {
		background: var(--peach-wash);
	}
	.outlined {
		border: 1.5px solid var(--sage-strong);
	}
	.sagey {
		background: var(--sage);
	}
	.actions {
		margin: var(--space-6) 0 var(--space-4);
	}
	.provenance {
		color: var(--fog-text);
		font-size: 0.94rem;
	}
	.loading {
		color: var(--fog-text);
		min-height: 40vh;
	}
</style>

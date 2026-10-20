<script lang="ts">
	/** Public report: route-level numbers, each with its range, and how they were made. */
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import NotchMark from '$lib/components/NotchMark.svelte';
	import RouteStrip, { type StripDog } from '$lib/components/RouteStrip.svelte';

	interface Report {
		slug: string;
		title: string;
		team: string;
		city: string;
		route_name: string;
		headline: { population: string | null; share: string | null; deficit: string | null; note: string | null };
		method: string;
		method_lines: string[];
		assumptions: string[];
		results: {
			counts?: { distinct: number };
			population?: { median: number; low: number; high: number } | null;
			comparability_problems?: string[];
			decided_pairs?: number;
			pairs?: number;
		};
		code_version: string;
		data_hash: string | null;
		seed: number;
		computed_at: string;
		strip: StripDog[];
	}

	const slug = page.params.slug ?? '';
	let report = $state<Report | null>(null);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			report = await api.get<Report>(`/reports/${slug}`);
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
</script>

<svelte:head>
	<title>{report?.title ?? 'NotchCount report'}</title>
</svelte:head>

<main class="report">
	<header class="top">
		<a class="brand" href="/"><NotchMark size={24} /><span>NotchCount</span></a>
	</header>

	{#if error}
		<p class="error">{error}</p>
	{:else if report}
		<h1>{report.title}</h1>
		<p class="byline">{report.route_name}, {report.city}. Counted by {report.team}.</p>

		<div class="grid">
			<section class="numbers" aria-label="Results">
				{#if report.headline.population}<p class="big">{report.headline.population}</p>{/if}
				{#if report.headline.share}<p class="big">{report.headline.share}</p>{/if}
				{#if report.headline.deficit}<p class="mid">{report.headline.deficit}</p>{/if}
				{#if report.headline.note}<p class="note">{report.headline.note}</p>{/if}
				{#each report.results.comparability_problems ?? [] as p (p)}<p class="error">{p}</p>{/each}
			</section>
			<section class="viz">
				<RouteStrip
					dogs={report.strip}
					population={report.results.population ?? null}
					seen={report.results.counts?.distinct ?? 0}
					label="Each dot is one dog. Top row: first walk. Bottom row: second walk. Lines join the same dog seen on both walks."
				/>
			</section>
		</div>

		<div class="explain">
			<section>
				<h2>How we counted</h2>
				{#each report.method_lines as line (line)}<p>{line}</p>{/each}
			</section>
			<section>
				<h2>What we assumed</h2>
				<ul>{#each report.assumptions as a (a)}<li>{a}</li>{/each}</ul>
			</section>
			<section>
				<h2>What could be wrong</h2>
				<ul>{#each wrong as w (w)}<li>{w}</li>{/each}</ul>
			</section>
		</div>

		<div class="actions">
			<a class="btn" href="/api/v1/reports/{report.slug}.pdf">Download PDF</a>
		</div>
		<p class="provenance">
			Computed {new Date(report.computed_at).toLocaleString()} by {report.code_version}, method {report.method}, seed
			{report.seed}, data hash {report.data_hash?.slice(0, 16)}. Faces and number plates were blurred before any photo
			was stored. Where individual dogs were seen is not published.
		</p>
	{/if}
</main>

<style>
	.report {
		max-width: 72rem;
		margin: 0 auto;
		padding: var(--space-4) var(--space-4) var(--space-7);
	}
	.top {
		margin-bottom: var(--space-6);
	}
	.brand {
		display: inline-flex;
		gap: var(--space-2);
		align-items: center;
		color: var(--ink);
		text-decoration: none;
		font-family: var(--font-display);
		font-weight: 650;
	}
	h1 {
		font-size: var(--step-5);
		font-variation-settings: 'wdth' 82;
		max-width: 20ch;
	}
	.byline {
		color: var(--ink-soft);
	}
	.grid {
		display: grid;
		gap: var(--space-6);
		margin: var(--space-6) 0;
	}
	@media (min-width: 900px) {
		.grid {
			grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
			align-items: start;
		}
	}
	.big {
		font-family: var(--font-display);
		font-size: var(--step-3);
		font-weight: 600;
		line-height: 1.15;
		font-variant-numeric: tabular-nums;
		margin-bottom: var(--space-4);
	}
	.mid {
		font-family: var(--font-display);
		font-size: var(--step-2);
		line-height: 1.2;
	}
	.note {
		border-left: 6px solid var(--sodium);
		padding-left: var(--space-3);
	}
	.explain {
		display: grid;
		gap: var(--space-5);
		border-top: 2px solid var(--ink);
		padding-top: var(--space-5);
	}
	@media (min-width: 900px) {
		.explain {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
	}
	.explain li {
		margin-bottom: var(--space-2);
	}
	.actions {
		margin: var(--space-5) 0;
	}
	.provenance {
		color: var(--fog-text);
		font-size: 0.94rem;
	}
</style>

<script lang="ts">
	import { untrack } from 'svelte';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { recall, remember } from '$lib/cache';
	import { t } from '$lib/i18n/index.svelte';
	import { getPass, passKey } from '$lib/queue';
	import { session } from '$lib/session.svelte';
	import type { Estimate, Progress, Survey } from '$lib/types';

	const id = $derived(page.params.id ?? '');
	let survey = $state<Survey | null>(null);
	let error = $state<string | null>(null);
	let localPasses = $state<number[]>([]);

	$effect(() => {
		const sid = id;
		untrack(() => loadSurvey(sid));
	});

	function loadSurvey(sid: string) {
		survey = recall<Survey>(`survey.${sid}`);
		api
			.get<Survey>(`/surveys/${sid}`)
			.then((s) => (survey = remember(`survey.${sid}`, s)))
			.catch((e: Error) => {
				if (!survey) error = e.message;
			});
		void (async () => {
			const found: number[] = [];
			for (let n = 1; n <= 5; n++) if (await getPass(passKey(sid, n))) found.push(n);
			localPasses = found;
		})();
	}

	const nextPassNo = $derived.by(() => {
		const used = new Set([...(survey?.passes.map((p) => p.pass_no) ?? []), ...localPasses]);
		let n = 1;
		while (used.has(n)) n++;
		return n;
	});

	const myOpenPass = $derived.by(() => {
		const me = session.me?.id;
		const remote = survey?.passes.find((p) => p.observer_id === me && !p.locked)?.pass_no;
		return remote ?? localPasses.find((n) => !survey?.passes.some((p) => p.pass_no === n && p.locked)) ?? null;
	});

	let progress = $state<Progress | null>(null);
	let estimates = $state<Estimate[]>([]);
	let notice = $state<string | null>(null);
	const role = $derived(session.me?.teams.find((x) => x.id === survey?.team_id)?.role ?? 'walker');

	async function loadAnalysis(sid: string) {
		try {
			[progress, estimates] = await Promise.all([
				api.get<Progress>(`/surveys/${sid}/progress`),
				api.get<Estimate[]>(`/surveys/${sid}/estimates`)
			]);
		} catch {
			/* offline: walkers do not need this panel */
		}
	}

	$effect(() => {
		const sid = id;
		if (role !== 'walker') untrack(() => void loadAnalysis(sid));
	});

	async function act(path: string, message: string) {
		notice = null;
		try {
			await api.post(`/surveys/${id}/${path}`);
			notice = message;
			setTimeout(() => void loadAnalysis(id), 4000);
		} catch (e) {
			notice = (e as Error).message;
		}
	}

	async function publish() {
		notice = null;
		try {
			const out = await api.post<{ slug: string; url: string }>(`/surveys/${id}/publish`);
			if (survey) survey.public_slug = out.slug;
			notice = 'Report published. Anyone with the link can read it; it shows route-level numbers only.';
		} catch (e) {
			notice = (e as Error).message;
		}
	}

	const latest = $derived(estimates.find((e) => e.status === 'done') ?? null);
	const pending = $derived(estimates.find((e) => e.status === 'queued' || e.status === 'running') ?? null);
	const round = (v: number | null | undefined) => (v === null || v === undefined ? '?' : Math.round(v));
	const pct = (v: number | null | undefined) => (v === null || v === undefined ? '?' : `${Math.round(v * 100)}%`);

	const fmt = (iso: string) =>
		new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
</script>

{#if error}
	<p class="error">{error}</p>
{:else if survey}
	<h1>{survey.name}</h1>
	<p class="meta">
		{survey.route.name}. {t('survey.routeLength', { km: (survey.route.length_m / 1000).toFixed(2) })}.
		{t('survey.startTime', { time: survey.start_window_local.slice(0, 5) })}.
	</p>

	<ol class="passes">
		{#each survey.passes as p (p.id)}
			<li>
				<span class="pass-no">{t('survey.pass', { n: p.pass_no })}</span>
				<span>{t('survey.walkedBy', { name: p.observer_name })}, {fmt(p.started_at)}</span>
				<span class="num">{t('survey.photos', { n: p.photo_count })}</span>
				<span class:done={p.locked}>{p.locked ? t('survey.ended') : t('survey.inProgress')}</span>
			</li>
		{/each}
	</ol>

	<div class="start">
		<p>{t('survey.startHint')}</p>
		{#if myOpenPass !== null}
			<a class="btn" href="/app/capture/{survey.id}/{myOpenPass}">{t('survey.continuePass', { n: myOpenPass })}</a>
		{:else}
			<a class="btn" href="/app/capture/{survey.id}/{nextPassNo}">{t('survey.startPass', { n: nextPassNo })}</a>
		{/if}
	</div>
{/if}

{#if survey && role !== 'walker'}
	<section class="analysis">
		<h2>Matching and estimate</h2>
		{#if progress}
			<dl class="stats num">
				<div><dt>Photos processed</dt><dd>{progress.photos.processed ?? 0} of {Object.values(progress.photos).reduce((a, b) => a + b, 0)}</dd></div>
				<div><dt>Dog crops usable</dt><dd>{progress.usable_detections} of {progress.detections}</dd></div>
				<div><dt>Pairs labelled</dt><dd>{progress.pairs_labelled} of {progress.pairs}</dd></div>
				<div><dt>Ears labelled</dt><dd>{progress.ears_labelled}</dd></div>
				<div><dt>Left to review</dt><dd>{progress.review_pairs_left + progress.review_ears_left}</dd></div>
			</dl>
			<p class="meta">
				Match model: {progress.match_model ?? 'not trained yet (labels needed)'}. Ear model:
				{progress.notch_model ?? 'not trained yet'}.
			</p>
		{/if}
		<div class="actions">
			<a class="btn" href="/app/survey/{survey.id}/check/pairs">Label pairs</a>
			<a class="btn" href="/app/survey/{survey.id}/check/ears">Label ears</a>
			<a class="btn" href="/app/survey/{survey.id}/check/review">Review queue</a>
			{#if role === 'admin'}<a class="btn quiet" href="/app/survey/{survey.id}/case">Case file</a>{/if}
		</div>
		{#if role === 'admin'}
			<div class="actions">
				<button class="btn quiet" onclick={() => act('match', 'Finding matches. This takes a minute.')}>Find matches</button>
				<button class="btn quiet" onclick={() => act('train', 'Training on your labels, then rescoring.')}>Train on labels</button>
				<button class="btn quiet" onclick={() => act('estimates', 'Estimate queued.')}>Run estimate</button>
				<button class="btn quiet" disabled={!latest} onclick={publish}>Publish report</button>
			</div>
		{/if}
		{#if notice}<p role="status">{notice}</p>{/if}
		{#if survey.public_slug}<p><a href="/r/{survey.public_slug}">Open the public report</a></p>{/if}
		{#if pending}<p class="meta">An estimate is {pending.status}.</p>{/if}
		{#if latest?.results}
			{@const r = latest.results}
			<div class="result">
				{#if r.population}
					<p class="headline">
						About <span class="num">{round(r.population.median)}</span> dogs use this route
						(<span class="num">{round(r.population.low)} to {round(r.population.high)}</span>).
					</p>
				{:else if r.single_pass}
					<p class="headline">
						<span class="num">{r.single_pass.individuals}</span> different dogs seen in pass {r.single_pass.pass_no}.
						Walk the route again to estimate how many use it.
					</p>
				{:else if r.counts}
					<p class="headline">Not enough matched dogs to estimate the total. Walk the route again.</p>
				{/if}
				{#if r.share}
					<p class="headline">
						<span class="num">{pct(r.share.median)}</span> are sterilised
						(<span class="num">{pct(r.share.low)} to {pct(r.share.high)}</span>).
					</p>
				{:else if r.single_pass?.share.share !== null && r.single_pass}
					<p class="headline">
						<span class="num">{pct(r.single_pass.share.share)}</span> are sterilised
						(<span class="num">{pct(r.single_pass.share.low)} to {pct(r.single_pass.share.high)}</span>).
					</p>
				{/if}
				{#if r.deficit}
					<p>Reaching 70% needs about <span class="num">{round(r.deficit.median)}</span> more {round(r.deficit.median) === 1 ? 'sterilisation' : 'sterilisations'}
						(<span class="num">{round(r.deficit.low)} to {round(r.deficit.high)}</span>).</p>
				{/if}
				{#each r.comparability_problems as problem (problem)}<p class="error">{problem}</p>{/each}
				<p class="meta">
					{latest.method}, {r.sightings} sightings, {r.decided_pairs} of {r.pairs} pairs decided by people,
					{latest.code_version}, seed {latest.seed}, data {latest.data_hash?.slice(0, 12)}.
				</p>
			</div>
		{/if}
	</section>
{/if}

<style>
	.analysis {
		margin-top: var(--space-7);
		border-top: 2px solid var(--ink);
		padding-top: var(--space-4);
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
		gap: var(--space-3);
		margin: 0 0 var(--space-3);
	}
	.stats div {
		display: grid;
	}
	.stats dt {
		font-family: var(--font-body);
		color: var(--fog-text);
	}
	.stats dd {
		margin: 0;
		font-size: var(--step-2);
		font-weight: 600;
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
		margin: var(--space-3) 0;
	}
	.result {
		margin-top: var(--space-4);
	}
	.headline {
		font-family: var(--font-display);
		font-size: var(--step-2);
		line-height: 1.2;
		margin-bottom: var(--space-2);
	}
	.meta {
		color: var(--fog-text);
	}
	.passes {
		list-style: none;
		padding: 0;
		margin: var(--space-5) 0;
		border-top: 1px solid var(--rule);
	}
	.passes li {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 2px var(--space-4);
		padding: var(--space-3) 0;
		border-bottom: 1px solid var(--rule);
	}
	.pass-no {
		font-family: var(--font-display);
		font-weight: 600;
		grid-row: span 3;
	}
	.done {
		color: var(--notch-teal);
		font-weight: 600;
	}
	.start {
		margin-top: var(--space-6);
	}
</style>

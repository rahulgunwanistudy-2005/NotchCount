<script lang="ts">
	import { untrack } from 'svelte';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { recall, remember } from '$lib/cache';
	import Icon from '$lib/components/Icon.svelte';
	import RangeBar from '$lib/components/RangeBar.svelte';
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
	let noticeIsError = $state(false);
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
			noticeIsError = false;
			setTimeout(() => void loadAnalysis(id), 4000);
		} catch (e) {
			notice = (e as Error).message;
			noticeIsError = true;
		}
	}

	async function publish() {
		notice = null;
		try {
			const out = await api.post<{ slug: string; url: string }>(`/surveys/${id}/publish`);
			if (survey) survey.public_slug = out.slug;
			notice = 'Report published. Anyone with the link can read it; it shows route-level numbers only.';
			noticeIsError = false;
		} catch (e) {
			notice = (e as Error).message;
			noticeIsError = true;
		}
	}

	const latest = $derived(estimates.find((e) => e.status === 'done') ?? null);
	const pending = $derived(estimates.find((e) => e.status === 'queued' || e.status === 'running') ?? null);
	const round = (v: number | null | undefined) => (v === null || v === undefined ? '?' : Math.round(v));
	const pct = (v: number | null | undefined) => (v === null || v === undefined ? '?' : `${Math.round(v * 100)}%`);
	const fmt = (iso: string) => {
		const d = new Date(iso);
		return `${d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}, ${d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false })}`;
	};
	const initial = (name: string) => name.trim().charAt(0).toUpperCase() || '?';

	const totalPhotos = $derived(progress ? Object.values(progress.photos).reduce((a, b) => a + b, 0) : 0);
	const meters = $derived(
		progress
			? [
					{ label: 'Photos processed', done: progress.photos.processed ?? 0, of: totalPhotos },
					{ label: 'Dog crops usable', done: progress.usable_detections, of: progress.detections },
					{ label: 'Pairs labelled', done: progress.pairs_labelled, of: progress.pairs }
				]
			: []
	);
	const reviewLeft = $derived(progress ? progress.review_pairs_left + progress.review_ears_left : 0);
</script>

{#if error}
	<p class="error">{error}</p>
{:else if survey}
	<div class="head">
		<div>
			<h1>{survey.name}</h1>
			<p class="meta">
				{survey.route.name}, {t('survey.routeLength', { km: (survey.route.length_m / 1000).toFixed(2) })}.
				{t('survey.startTime', { time: survey.start_window_local.slice(0, 5) })}.
			</p>
		</div>
		<div class="start">
			{#if myOpenPass !== null}
				<a class="btn peach" href="/app/capture/{survey.id}/{myOpenPass}"
					><Icon name="camera" size={18} />{t('survey.continuePass', { n: myOpenPass })}</a
				>
			{:else}
				<a class="btn peach" href="/app/capture/{survey.id}/{nextPassNo}"
					><Icon name="camera" size={18} />{t('survey.startPass', { n: nextPassNo })}</a
				>
			{/if}
		</div>
	</div>

	<div class="grid" class:walker={role === 'walker'}>
		<section class="panel walks">
			<div class="panel-head">
				<h2>Walks</h2>
				<span class="hint">{t('survey.startHint')}</span>
			</div>
			{#if survey.passes.length === 0}
				<p class="empty">No walk yet. Press {t('survey.startPass', { n: nextPassNo })} at the start point, at the agreed time.</p>
			{:else}
				<table>
					<thead>
						<tr>
							<th scope="col">Walk</th>
							<th scope="col">Walker</th>
							<th scope="col">Started</th>
							<th scope="col" class="r">Photos</th>
							<th scope="col">Status</th>
						</tr>
					</thead>
					<tbody>
						{#each survey.passes as p (p.id)}
							<tr>
								<td class="pass-no">{t('survey.pass', { n: p.pass_no })}</td>
								<td>
									<span class="who"
										><span class="avatar" aria-hidden="true">{initial(p.observer_name)}</span>{p.observer_name}</span
									>
								</td>
								<td>{fmt(p.started_at)}</td>
								<td class="r num">{p.photo_count}</td>
								<td><span class="chip" class:done={p.locked}>{p.locked ? t('survey.ended') : t('survey.inProgress')}</span></td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		</section>

		{#if role !== 'walker'}
			<section class="panel estimate">
				<div class="panel-head">
					<h2>Estimate</h2>
					{#if pending}<span class="chip warn">Estimate {pending.status}</span>{/if}
				</div>
				{#if latest?.results}
					{@const r = latest.results}
					{#if r.population}
						<p class="headline">
							About <span class="num">{round(r.population.median)}</span> dogs use this route
							<span class="range-text">(<span class="num">{round(r.population.low)} to {round(r.population.high)}</span>)</span>
						</p>
						<RangeBar
							low={r.population.low}
							mid={r.population.median}
							high={r.population.high}
							seen={r.counts?.distinct ?? null}
							max={Math.max(r.population.high * 1.2, (r.counts?.distinct ?? 0) + 2)}
							label="Range of the dog count: {round(r.population.low)} to {round(r.population.high)}, most likely {round(r.population.median)}; {r.counts?.distinct ?? 0} different dogs were seen"
						/>
						{#if r.counts}<p class="hint">Dashed mark: {r.counts.distinct} different dogs actually photographed.</p>{/if}
					{:else if r.single_pass}
						<p class="headline">
							<span class="num">{r.single_pass.individuals}</span> different dogs seen on walk {r.single_pass.pass_no}.
						</p>
						<p>Walk the route again to estimate how many use it.</p>
					{:else if r.counts}
						<p class="headline">Not enough matched dogs to estimate the total.</p>
						<p>Walk the route again, or label more pairs.</p>
					{/if}

					{#if r.share}
						<p class="headline small">
							<span class="num">{pct(r.share.median)}</span> are sterilised
							<span class="range-text">(<span class="num">{pct(r.share.low)} to {pct(r.share.high)}</span>)</span>
						</p>
						<RangeBar
							tone="notched"
							low={r.share.low}
							mid={r.share.median}
							high={r.share.high}
							max={1}
							format={(v) => `${Math.round(v * 100)}%`}
							label="Sterilised share: {pct(r.share.low)} to {pct(r.share.high)}, most likely {pct(r.share.median)}"
						/>
					{:else if r.single_pass && r.single_pass.share.share !== null}
						<p class="headline small">
							<span class="num">{pct(r.single_pass.share.share)}</span> are sterilised
							<span class="range-text">(<span class="num">{pct(r.single_pass.share.low)} to {pct(r.single_pass.share.high)}</span>)</span>
						</p>
					{:else}
						<p class="hint">No sterilised share yet: no ears have been labelled. Label ears, then run the estimate again.</p>
					{/if}
					{#if r.deficit}
						<p>
							Reaching 70% needs about <span class="num">{round(r.deficit.median)}</span>
							more {round(r.deficit.median) === 1 ? 'sterilisation' : 'sterilisations'}
							(<span class="num">{round(r.deficit.low)} to {round(r.deficit.high)}</span>).
						</p>
					{/if}
					{#each r.comparability_problems as problem (problem)}<p class="error">{problem}</p>{/each}
					<p class="provenance">
						{latest.method}, {r.sightings} sightings, {r.decided_pairs} of {r.pairs} pairs decided by people.
						Code {latest.code_version}, seed {latest.seed}, data {latest.data_hash?.slice(0, 12)}.
					</p>
					{#if survey.public_slug}
						<a class="btn quiet" href="/r/{survey.public_slug}">Open the public report</a>
					{/if}
				{:else}
					<p class="empty">
						No estimate yet. Label some pairs, then press Run estimate. With one walk you get a count of different dogs;
						with two you get the total and its range.
					</p>
				{/if}
			</section>

			<section class="panel checks">
				<div class="panel-head">
					<h2>Checks to do</h2>
					{#if reviewLeft > 0}<span class="chip warn">{reviewLeft} waiting for review</span>{/if}
				</div>
				<div class="tiles">
					<a class="tile" href="/app/survey/{survey.id}/check/pairs">
						<Icon name="pairs" size={22} />
						<span class="tile-title">Label pairs</span>
						<span class="tile-count num">{progress ? `${progress.pairs_labelled} of ${progress.pairs}` : ''}</span>
						<span class="hint">Same dog or different?</span>
					</a>
					<a class="tile" href="/app/survey/{survey.id}/check/ears">
						<Icon name="ear" size={22} />
						<span class="tile-title">Label ears</span>
						<span class="tile-count num">{progress ? `${progress.ears_labelled} labelled` : ''}</span>
						<span class="hint">Is the ear notched?</span>
					</a>
					<a class="tile" href="/app/survey/{survey.id}/check/review">
						<Icon name="review" size={22} />
						<span class="tile-title">Review queue</span>
						<span class="tile-count num">{progress ? `${reviewLeft} left` : ''}</span>
						<span class="hint">Where the model was unsure</span>
					</a>
					{#if role === 'admin'}
						<a class="tile" href="/app/survey/{survey.id}/case">
							<Icon name="case" size={22} />
							<span class="tile-title">Case file</span>
							<span class="tile-count">&nbsp;</span>
							<span class="hint">Send the report to the officer</span>
						</a>
					{/if}
				</div>
			</section>

			<section class="panel engine">
				<div class="panel-head"><h2>Matching</h2></div>
				{#if progress}
					<ul class="meters">
						{#each meters as m (m.label)}
							<li>
								<span class="m-label">{m.label}</span>
								<span class="m-value num">{m.done} of {m.of}</span>
								<span class="track" aria-hidden="true"
									><span class="fill" style="width: {m.of ? Math.round((100 * m.done) / m.of) : 0}%"></span></span
								>
							</li>
						{/each}
					</ul>
					<p class="hint">
						Match model: {progress.match_model ?? 'not trained yet (labels needed)'}. Ear model:
						{progress.notch_model ?? 'not trained yet'}.
					</p>
				{/if}
				{#if role === 'admin'}
					<div class="actions">
						<button class="btn quiet" onclick={() => act('match', 'Finding matches. This takes a minute.')}>Find matches</button>
						<button class="btn quiet" onclick={() => act('train', 'Training on your labels, then rescoring.')}>Train on labels</button>
						<button class="btn" onclick={() => act('estimates', 'Estimate queued.')}>Run estimate</button>
						<button class="btn peach" disabled={!latest} onclick={publish}>Publish report</button>
					</div>
				{/if}
				{#if notice}<p class={noticeIsError ? 'error' : 'notice'} role="status">{notice}</p>{/if}
			</section>
		{/if}
	</div>
{/if}

<style>
	.head {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		justify-content: space-between;
		gap: var(--space-3) var(--space-5);
		margin: var(--space-2) 0 var(--space-5);
	}
	.head h1 {
		margin-bottom: var(--space-1);
	}
	.meta {
		color: var(--fog-text);
		margin: 0;
	}
	.grid {
		display: grid;
		gap: var(--space-4);
	}
	@media (min-width: 1100px) {
		.grid:not(.walker) {
			grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
		}
	}
	.empty {
		background: var(--surface-soft);
		border-radius: var(--radius-tile);
		padding: var(--space-4) var(--space-5);
		margin: 0;
	}
	.panel-head .hint {
		max-width: 32rem;
	}

	/* Walks table */
	table {
		width: 100%;
		border-collapse: separate;
		border-spacing: 0 var(--space-2);
	}
	th {
		text-align: left;
		font-weight: 500;
		color: var(--fog-text);
		font-size: 0.9rem;
		padding: 0 var(--space-3);
	}
	td {
		background: var(--surface-soft);
		padding: var(--space-3);
	}
	td:first-child {
		border-radius: var(--radius-tile) 0 0 var(--radius-tile);
		padding-left: var(--space-4);
	}
	td:last-child {
		border-radius: 0 var(--radius-tile) var(--radius-tile) 0;
	}
	.r {
		text-align: right;
	}
	.pass-no {
		font-family: var(--font-display);
		font-weight: 700;
		color: var(--slate);
		white-space: nowrap;
	}
	td {
		white-space: nowrap;
	}
	.who {
		white-space: normal;
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
	}
	@media (max-width: 640px) {
		thead {
			position: absolute;
			width: 1px;
			height: 1px;
			overflow: hidden;
			clip: rect(0 0 0 0);
		}
		table,
		tbody,
		tr,
		td {
			display: block;
		}
		tr {
			background: var(--surface-soft);
			border-radius: var(--radius-tile);
			padding: var(--space-3) var(--space-4);
			margin-bottom: var(--space-2);
			display: grid;
			grid-template-columns: 1fr auto;
			gap: var(--space-1) var(--space-3);
		}
		td,
		td:first-child,
		td:last-child {
			background: none;
			padding: 0;
			border-radius: 0;
		}
		.r {
			text-align: left;
		}
		.r::after {
			content: ' photos';
		}
	}

	/* Estimate */
	.headline {
		font-family: var(--font-display);
		font-weight: 700;
		color: var(--slate);
		font-size: var(--step-2);
		line-height: 1.25;
		margin-bottom: var(--space-3);
	}
	.headline.small {
		font-size: var(--step-1);
		margin-top: var(--space-5);
	}
	.range-text {
		font-weight: 400;
		color: var(--ink-soft);
	}
	.provenance {
		color: var(--fog-text);
		font-size: 0.86rem;
		margin-top: var(--space-4);
	}

	/* Check tiles: cream cards, like the service cards in the reference */
	.tiles {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
		gap: var(--space-3);
	}
	.tile {
		display: grid;
		gap: var(--space-1);
		align-content: start;
		padding: var(--space-4);
		border-radius: var(--radius-tile);
		background: var(--surface-soft);
		color: var(--slate);
		text-decoration: none;
		min-height: 9rem;
	}
	.tile:hover {
		background: var(--sage);
	}
	.tile-title {
		font-family: var(--font-display);
		font-weight: 700;
		margin-top: var(--space-2);
	}
	.tile-count {
		font-size: var(--step-1);
		font-weight: 500;
		color: var(--ink);
	}
	.tile .hint {
		font-size: 0.86rem;
	}

	/* Meters: one measure each, done of total */
	.meters {
		list-style: none;
		margin: 0 0 var(--space-4);
		padding: 0;
		display: grid;
		gap: var(--space-4);
	}
	.meters li {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: var(--space-1) var(--space-3);
	}
	.m-label {
		color: var(--ink-soft);
	}
	.m-value {
		font-weight: 500;
	}
	.track {
		grid-column: 1 / -1;
		height: 10px;
		border-radius: 5px;
		background: var(--canvas);
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		border-radius: 5px;
		background: var(--moss);
	}
	.actions {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr));
		gap: var(--space-2);
		margin: var(--space-4) 0 var(--space-3);
	}
</style>

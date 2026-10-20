<script lang="ts">
	import { untrack } from 'svelte';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { recall, remember } from '$lib/cache';
	import { t } from '$lib/i18n/index.svelte';
	import { getPass, passKey } from '$lib/queue';
	import { session } from '$lib/session.svelte';
	import type { Survey } from '$lib/types';

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

<style>
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

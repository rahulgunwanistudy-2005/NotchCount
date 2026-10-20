<script lang="ts">
	/** Labelling (pairs, ears) and the review queue share this screen. */
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import EarReview from '$lib/components/EarReview.svelte';
	import PairReview from '$lib/components/PairReview.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import type { EarItem, PairItem } from '$lib/types';

	const surveyId = page.params.id ?? '';
	const mode = (page.params.mode ?? 'review') as 'pairs' | 'ears' | 'review';
	const titles = { pairs: 'Label pairs', ears: 'Label ears', review: 'Review queue' };
	const intro = {
		pairs: 'Are these two photos the same dog? Answer only what you can see. Not sure is a good answer.',
		ears: 'Is this dog ear-notched? A sterilised dog has a V-shaped cut at the tip of one ear.',
		review: 'The model was unsure about these. Your answers replace its guesses in the estimate.'
	};
	const path = { pairs: 'labeling/pairs', ears: 'labeling/ears', review: 'review/next' };

	let item = $state<PairItem | EarItem | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let done = $state(0);
	let busy = false;

	async function next() {
		loading = true;
		error = null;
		try {
			item = await api.get<PairItem | EarItem | null>(`/surveys/${surveyId}/${path[mode]}`);
		} catch (e) {
			error = (e as Error).message;
		} finally {
			loading = false;
		}
	}

	async function answer(decision: string) {
		if (!item || busy) return;
		busy = true;
		try {
			if (item.kind === 'pair') await api.post('/labels/pairs', { pair_id: item.pair_id, decision });
			else await api.post('/labels/ears', { detection_id: item.detection_id, decision });
			done += 1;
			await next();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	onMount(next);
</script>

<svelte:head><title>{titles[mode]}</title></svelte:head>

<div class="check">
	<div class="head">
		<h1>{titles[mode]}</h1>
		<a href="/app/survey/{surveyId}">Back to survey</a>
	</div>
	<p class="intro">{intro[mode]}</p>
	{#if error}<p class="error" role="alert">{error}</p>{/if}

	{#if item}
		{#if item.kind === 'pair'}
			<PairReview {item} onanswer={answer} />
		{:else}
			<EarReview {item} onanswer={answer} />
		{/if}
		<p class="count" aria-live="polite">
			{#if item.remaining > 0}{t('review.left', { n: item.remaining })}{/if}
			{#if done > 0}<span class="done">{done} answered this session.</span>{/if}
		</p>
		<p class="keys">{item.kind === 'pair' ? t('review.keys') : t('ears.keys')}</p>
	{:else if !loading}
		<p class="empty">{t('review.done')}</p>
		<a class="btn" href="/app/survey/{surveyId}">Back to survey</a>
	{/if}
</div>

<style>
	.check {
		max-width: 60rem;
	}
	.head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--space-4);
		flex-wrap: wrap;
	}
	.intro {
		color: var(--ink-soft);
	}
	.count {
		margin-top: var(--space-4);
		font-weight: 600;
	}
	.done {
		font-weight: 400;
		color: var(--fog-text);
		margin-left: var(--space-2);
	}
	.keys {
		color: var(--fog-text);
		font-size: 0.94rem;
	}
	.empty {
		font-size: var(--step-1);
	}
</style>

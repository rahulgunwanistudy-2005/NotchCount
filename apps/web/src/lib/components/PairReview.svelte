<script lang="ts">
	/** Two crops side by side with Same / Different / Not sure; keyboard S, D, N. */
	import { t } from '$lib/i18n/index.svelte';
	import type { PairItem } from '$lib/types';

	let {
		item,
		onanswer
	}: { item: PairItem; onanswer: (decision: 'same' | 'different' | 'unsure') => void } = $props();

	const distance = $derived(
		[
			item.route_m !== null ? t('review.apart', { m: item.route_m }) : null,
			item.a.pass_no === item.b.pass_no ? t('review.minutes', { m: Math.round(item.minutes_apart) }) : null
		]
			.filter(Boolean)
			.join(', ')
	);

	const time = (iso: string) => new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });

	function onkey(e: KeyboardEvent) {
		if (e.target instanceof HTMLInputElement || e.metaKey || e.ctrlKey) return;
		const k = e.key.toLowerCase();
		if (k === 's') onanswer('same');
		else if (k === 'd') onanswer('different');
		else if (k === 'n') onanswer('unsure');
	}
</script>

<svelte:window onkeydown={onkey} />

<div class="pair">
	<figure>
		<img src={item.a.url} alt="Dog photo A, pass {item.a.pass_no}" />
		<figcaption>{t('review.passAt', { n: item.a.pass_no, time: time(item.a.taken_at) })}</figcaption>
	</figure>
	<figure>
		<img src={item.b.url} alt="Dog photo B, pass {item.b.pass_no}" />
		<figcaption>{t('review.passAt', { n: item.b.pass_no, time: time(item.b.taken_at) })}</figcaption>
	</figure>
	<p class="gap">{distance}</p>
</div>

<div class="answers">
	<button class="btn same" onclick={() => onanswer('same')}>{t('review.same')} <kbd>S</kbd></button>
	<button class="btn peach" onclick={() => onanswer('different')}>{t('review.different')} <kbd>D</kbd></button>
	<button class="btn quiet" onclick={() => onanswer('unsure')}>{t('review.unsure')} <kbd>N</kbd></button>
</div>

<style>
	.pair {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--space-3);
	}
	figure {
		margin: 0;
		display: grid;
		gap: var(--space-2);
	}
	img {
		width: 100%;
		height: min(46vh, 420px);
		object-fit: contain;
		display: block;
		background: var(--ink);
		border-radius: var(--radius-tile);
	}
	figcaption {
		font-weight: 500;
		color: var(--slate);
	}
	.gap {
		grid-column: 1 / -1;
		margin: 0;
		color: var(--ink-soft);
	}
	.answers {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: var(--space-2);
		margin-top: var(--space-4);
	}
	.answers .btn {
		min-height: 56px;
		padding: var(--space-1) var(--space-2);
		border-radius: var(--radius-tile);
		line-height: 1.2;
	}
	@media (max-width: 480px) {
		kbd {
			display: none;
		}
		img {
			height: auto;
			max-height: 56vh;
		}
	}
</style>

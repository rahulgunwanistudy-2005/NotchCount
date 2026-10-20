<script lang="ts">
	/** One head crop with Notched / Not notched / Ear not visible; keyboard N, O, V. */
	import { t } from '$lib/i18n/index.svelte';
	import type { EarItem } from '$lib/types';

	type EarDecision = 'notched' | 'not_notched' | 'not_visible' | 'unsure';
	let { item, onanswer }: { item: EarItem; onanswer: (d: EarDecision) => void } = $props();

	function onkey(e: KeyboardEvent) {
		if (e.metaKey || e.ctrlKey) return;
		const k = e.key.toLowerCase();
		if (k === 'n') onanswer('notched');
		else if (k === 'o') onanswer('not_notched');
		else if (k === 'v') onanswer('not_visible');
	}
</script>

<svelte:window onkeydown={onkey} />

<figure>
	<img src={item.crop.url} alt="Dog {item.crop.view === 'head' ? 'head' : 'body'} photo, pass {item.crop.pass_no}" />
</figure>
<p class="hint">{t('ears.hint')}</p>
<div class="answers">
	<button class="btn notched" onclick={() => onanswer('notched')}>{t('ears.notched')} <kbd>N</kbd></button>
	<button class="btn plain" onclick={() => onanswer('not_notched')}>{t('ears.plain')} <kbd>O</kbd></button>
	<button class="btn quiet hidden" onclick={() => onanswer('not_visible')}>{t('ears.hidden')} <kbd>V</kbd></button>
</div>

<style>
	figure {
		margin: 0;
		background: var(--ink);
	}
	img {
		width: 100%;
		height: min(52vh, 480px);
		object-fit: contain;
		display: block;
	}
	.hint {
		color: var(--ink-soft);
		margin: var(--space-3) 0;
	}
	.answers {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: var(--space-2);
	}
	.answers .btn {
		min-height: 56px;
		padding: 0 var(--space-2);
	}
	.notched {
		background: var(--notch-teal);
		border-color: var(--notch-teal);
	}
	.plain {
		background: var(--sodium);
		border-color: var(--sodium);
		color: var(--ink);
	}
	.hidden {
		background-image: var(--hatch);
		background-color: #fff;
	}
	kbd {
		font: inherit;
		font-size: 0.8rem;
		opacity: 0.75;
		border: 1px solid currentColor;
		border-radius: 4px;
		padding: 0 4px;
	}
	@media (max-width: 480px) {
		kbd {
			display: none;
		}
	}
</style>

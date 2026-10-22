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
	}
	img {
		width: 100%;
		height: min(52vh, 480px);
		object-fit: contain;
		display: block;
		background: var(--ink);
		border-radius: var(--radius-tile);
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
		padding: var(--space-1) var(--space-2);
		border-radius: var(--radius-tile);
		line-height: 1.2;
	}
	.notched {
		background: var(--notched);
		border-color: var(--notched);
	}
	.plain {
		background: var(--plain);
		border-color: var(--plain);
		color: #1d1206;
	}
	.hidden {
		background-image: var(--hatch);
		background-color: var(--surface);
		color: var(--ink);
		text-shadow:
			0 0 4px #fff,
			0 0 4px #fff;
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

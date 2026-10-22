<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { forgetAll } from '$lib/cache';
	import Badge from '$lib/components/Badge.svelte';
	import Doodle from '$lib/components/Doodle.svelte';
	import { t } from '$lib/i18n/index.svelte';

	let message = $state(t('join.title'));
	let failed = $state(false);

	onMount(async () => {
		const code = location.hash.slice(1);
		history.replaceState(null, '', '/join');
		if (!code) {
			message = t('join.missing');
			failed = true;
			return;
		}
		try {
			await api.post('/auth/invite', { code });
			forgetAll();
			message = t('join.done');
			await goto('/app', { replaceState: true });
		} catch (err) {
			message = err instanceof Error ? err.message : String(err);
			failed = true;
		}
	});
</script>

<main class="join">
	<div class="card">
		<Doodle shape="bean" class="join-bean" />
		<Badge size={132} label="NotchCount" />
		<p class:error={failed} role="status">{message}</p>
		{#if failed}<a class="btn quiet" href="/">Go to the home page</a>{/if}
	</div>
</main>

<style>
	.join {
		min-height: 100vh;
		display: grid;
		place-items: center;
		padding: var(--space-5);
	}
	.card {
		position: relative;
		background: var(--surface);
		border-radius: var(--radius-shell);
		padding: var(--space-7) var(--space-6);
		max-width: 30rem;
		width: 100%;
		display: grid;
		justify-items: center;
		gap: var(--space-5);
		text-align: center;
	}
	.card p {
		margin: 0;
		font-size: var(--step-1);
	}
	.card :global(.join-bean) {
		width: 56px;
		right: -18px;
		bottom: -22px;
	}
</style>

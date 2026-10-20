<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { forgetAll } from '$lib/cache';
	import NotchMark from '$lib/components/NotchMark.svelte';
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
	<NotchMark size={56} />
	<p class:error={failed} role="status">{message}</p>
</main>

<style>
	.join {
		max-width: 32rem;
		margin: 0 auto;
		padding: var(--space-7) var(--space-4);
		display: grid;
		gap: var(--space-5);
		color: var(--ink);
	}
</style>

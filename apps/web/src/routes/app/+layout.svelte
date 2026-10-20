<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import NotchMark from '$lib/components/NotchMark.svelte';
	import { hindiAvailable, locale, setLang, t } from '$lib/i18n/index.svelte';
	import { loadMe, session } from '$lib/session.svelte';
	import { requestPersistence, sync } from '$lib/queue';

	let { children } = $props();
	const fullScreen = $derived(page.url.pathname.includes('/capture/'));

	onMount(() => {
		void loadMe();
		void requestPersistence();
		void sync();
		const onOnline = () => void sync();
		window.addEventListener('online', onOnline);
		return () => window.removeEventListener('online', onOnline);
	});
</script>

{#if fullScreen}
	{@render children()}
{:else}
	<header class="bar">
		<a class="brand" href="/app"><NotchMark size={26} /><span>NotchCount</span></a>
		<nav>
			<a href="/app/protocol">{t('nav.protocol')}</a>
			{#if hindiAvailable}
				<button class="link" onclick={() => setLang(locale.lang === 'en' ? 'hi' : 'en')}>{t('lang.switch')}</button>
			{/if}
		</nav>
	</header>
	<main class="page">
		{#if session.loaded && session.signedOut}
			<h1>Sign in with your team link</h1>
			<p>Your team admin sends each walker a one-time link. Open it on this phone to sign in.</p>
		{:else}
			{@render children()}
		{/if}
	</main>
{/if}

<style>
	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-4);
		padding: var(--space-3) var(--space-4);
		max-width: 72rem;
		margin: 0 auto;
	}
	.brand {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		color: var(--ink);
		text-decoration: none;
		font-family: var(--font-display);
		font-weight: 650;
		font-size: var(--step-1);
	}
	nav {
		display: flex;
		gap: var(--space-4);
		align-items: center;
	}
	nav a,
	.link {
		min-height: var(--target);
		display: inline-flex;
		align-items: center;
		background: none;
		border: 0;
		padding: 0;
		color: var(--survey-blue);
		text-decoration: underline;
		cursor: pointer;
	}
	.page {
		max-width: 72rem;
		margin: 0 auto;
		padding: var(--space-4) var(--space-4) var(--space-7);
	}
</style>

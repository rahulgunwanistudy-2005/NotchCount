<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { locale } from '$lib/i18n/index.svelte';

	let { children } = $props();

	$effect(() => {
		document.documentElement.lang = locale.lang;
	});

	onMount(() => {
		if ('serviceWorker' in navigator && !import.meta.env.DEV) {
			navigator.serviceWorker.register('/service-worker.js').catch(() => {
				/* the app still works online without offline caching */
			});
		}
	});
</script>

{@render children()}

<script lang="ts">
	import NotchMark from '$lib/components/NotchMark.svelte';
</script>

<main class="landing">
	<NotchMark size={64} />
	<h1>Count the dogs on your street. Find out if sterilisation is really happening.</h1>
	<p>
		Walk one route on two mornings and photograph every street dog. NotchCount matches the dogs across both
		walks, checks each ear for the notch a vet cuts at sterilisation, and estimates how many dogs use the route
		and what share are sterilised, with an honest range.
	</p>
	<p>Walkers sign in with the one-time link their team admin sends them.</p>
	<a class="btn" href="/app">Open the app</a>
</main>

<style>
	.landing {
		max-width: 44rem;
		margin: 0 auto;
		padding: var(--space-7) var(--space-4);
		color: var(--ink);
	}
	h1 {
		font-size: var(--step-5);
		font-variation-settings: 'wdth' 80;
		margin: var(--space-5) 0;
	}
</style>

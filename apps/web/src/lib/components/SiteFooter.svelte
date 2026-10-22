<script lang="ts">
	import { REPO_URL } from '$lib/site';
	import Badge from './Badge.svelte';

	let { photos = true }: { photos?: boolean } = $props();
</script>

<footer class="foot">
	<svg class="edge" viewBox="0 0 1200 80" preserveAspectRatio="none" aria-hidden="true">
		<path d="M0 60 C 240 10, 520 90, 820 40 S 1120 20, 1200 50 V 80 H 0 Z" />
	</svg>
	<div class="inner">
		<Badge size={72} label="NotchCount" />
		<div class="cols">
			<p>
				Faces and number plates are blurred before any photo is stored. Public reports show route-level numbers,
				never where a dog was seen.
			</p>
			<p class="links">
				<a href="/app/protocol">Field card</a>
				<a href={REPO_URL}>Source code</a>
				<a href="/app">Sign in</a>
			</p>
			{#if photos}
				<p class="credit">
					Photos: <a href="https://commons.wikimedia.org/wiki/File:Street_Dog_100.jpg">Street Dog 100</a> and
					<a href="https://commons.wikimedia.org/wiki/File:Street_Dog_105.jpg">Street Dog 105</a> by Slyronit,
					<a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>, cropped. Fonts: Merriweather and
					Jost (SIL Open Font License).
				</p>
			{/if}
		</div>
	</div>
</footer>

<style>
	.foot {
		position: relative;
		margin-top: var(--space-8);
		color: var(--ink-soft);
	}
	.edge {
		display: block;
		width: 100%;
		height: 60px;
	}
	.edge path {
		fill: var(--canvas);
	}
	.inner {
		background: var(--canvas);
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-5) var(--space-7);
		align-items: flex-start;
		padding: var(--space-4) max(var(--space-5), calc((100vw - 72rem) / 2)) var(--space-6);
	}
	.cols {
		flex: 1;
		min-width: min(100%, 18rem);
		font-size: 0.94rem;
	}
	.links {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2) var(--space-5);
	}
	.links a {
		min-height: var(--target);
		display: inline-flex;
		align-items: center;
	}
	.credit {
		color: var(--fog-text);
	}
</style>

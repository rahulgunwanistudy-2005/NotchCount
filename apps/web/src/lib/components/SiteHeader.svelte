<script lang="ts">
	/** Public pages: round badge on the left, links and the two pills on the right. */
	import Badge from './Badge.svelte';
	import Icon from './Icon.svelte';

	let { sample = null }: { sample?: string | null } = $props();
</script>

<header class="site">
	<svg class="swoosh" viewBox="0 0 520 200" aria-hidden="true" preserveAspectRatio="none">
		<path d="M-10 70 C 60 180, 230 190, 330 90 S 470 -20, 530 8" />
	</svg>
	<a class="home" href="/"><Badge size={92} /></a>
	<nav aria-label="Site">
		<a class="link" href="/#how">How it works</a>
		<a class="link" href="/app/protocol">Field card</a>
		{#if sample}<a class="link" href={sample}>Sample report</a>{/if}
		<a class="btn quiet" href="/app"><Icon name="user" size={18} />Sign in</a>
	</nav>
</header>

<style>
	.site {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: var(--space-4);
		max-width: 76rem;
		margin: 0 auto;
		padding: var(--space-5) var(--space-5) 0;
	}
	.swoosh {
		position: absolute;
		left: 0;
		top: 0;
		width: min(520px, 70vw);
		height: 200px;
		pointer-events: none;
		z-index: 0;
	}
	.swoosh path {
		fill: none;
		stroke: var(--moss);
		stroke-width: 1.3;
		opacity: 0.7;
	}
	.home {
		position: relative;
		z-index: 1;
		margin-left: var(--space-5);
		border-radius: 50%;
	}
	nav {
		position: relative;
		z-index: 1;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2) var(--space-5);
	}
	.link {
		color: var(--slate);
		text-decoration: none;
		font-weight: 500;
		min-height: var(--target);
		display: inline-flex;
		align-items: center;
	}
	.link:hover {
		text-decoration: underline;
	}
	@media (max-width: 640px) {
		.site {
			padding: var(--space-4) var(--space-4) 0;
		}
		.home {
			margin-left: 0;
		}
		.home :global(svg) {
			width: 72px;
			height: 72px;
		}
		nav {
			gap: 0 var(--space-4);
		}
		.link:not(:last-of-type) {
			display: none;
		}
	}
</style>

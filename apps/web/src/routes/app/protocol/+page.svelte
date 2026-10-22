<script lang="ts">
	import Icon from '$lib/components/Icon.svelte';
	import { t } from '$lib/i18n/index.svelte';
</script>

<article class="card panel">
	<h1>{t('protocol.title')}</h1>
	<p>Same route, same time, same pace, every dog. The estimate is only as good as the walks.</p>

	<h2>{t('protocol.before')}</h2>
	<ul>
		<li>An adult goes with every walker under 18. Tell your parents the route and time.</li>
		<li>Phone: automatic date and time on, location on at high accuracy, battery above 60%.</li>
		<li>Start within 15 minutes of the agreed time, at the start point, on both mornings.</li>
	</ul>

	<h2>{t('protocol.during')}</h2>
	<ol>
		<li>Press Start pass at the start point.</li>
		<li>Walk at an even, normal pace in the agreed direction. Do not double back for a dog you missed.</li>
		<li>Photograph every free-roaming dog you can see from the route, including sleeping dogs and puppies.</li>
		<li>Two shots per dog: the whole body from the side, then the head with both ears.</li>
		<li>Stay at least 3 metres away. Zoom instead of walking closer.</li>
		<li>Keep faces and number plates out of the frame where you can. The app blurs what it finds.</li>
		<li>Do not feed, call, chase or touch dogs. Do not wake a sleeping dog for a better photo.</li>
		<li>Press End pass at the finish point.</li>
	</ol>

	<h2>{t('protocol.safety')}</h2>
	<p>
		If a dog approaches or growls: stop, stand still, keep your arms close. Do not run or stare. Back away
		slowly once it settles. If a resident objects, explain politely and leave.
	</p>

	<div class="urgent">
		<div class="urgent-title"><Icon name="warning" size={34} /><h2>{t('protocol.bite')}</h2></div>
		<p>
			Wash the wound with soap and running water for about 15 minutes. Go to a hospital or health centre the same
			day for anti-rabies treatment. Do not wait to see if the dog seems sick. Stop the walk.
		</p>
	</div>
</article>

<style>
	.card {
		max-width: 52rem;
		padding: var(--space-6) clamp(1.25rem, 4vw, 3rem);
	}
	h2 {
		margin-top: var(--space-6);
	}
	li {
		margin-bottom: var(--space-2);
	}
	.urgent {
		margin-top: var(--space-6);
		background: var(--peach-wash);
		border-radius: 40px 60px 44px 70px / 50px 40px 60px 44px;
		padding: var(--space-6) clamp(1.25rem, 5vw, 3rem);
	}
	.urgent-title {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		color: var(--slate);
	}
	.urgent h2 {
		margin: 0;
	}
	.urgent p {
		font-weight: 500;
		margin: var(--space-3) 0 0;
	}
</style>

<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { api } from '$lib/api';
	import { recall, remember } from '$lib/cache';
	import Icon from '$lib/components/Icon.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import { counts, sync } from '$lib/queue';
	import { session } from '$lib/session.svelte';
	import type { Survey } from '$lib/types';

	let surveys = $state<Record<string, Survey[]>>({});
	let waiting = $state(0);
	let syncMessage = $state<string | null>(null);

	async function refreshQueue() {
		waiting = (await counts()).queued;
	}

	function loadSurveys(teams: { id: string }[]) {
		for (const team of teams) {
			surveys[team.id] ??= recall<Survey[]>(`surveys.${team.id}`) ?? [];
			api
				.get<Survey[]>(`/teams/${team.id}/surveys`)
				.then((list) => (surveys[team.id] = remember(`surveys.${team.id}`, list)))
				.catch(() => {
					/* offline: the cached list is shown */
				});
		}
	}

	$effect(() => {
		const teams = session.me?.teams ?? [];
		untrack(() => loadSurveys(teams));
	});

	onMount(() => {
		void refreshQueue();
		const timer = setInterval(refreshQueue, 5000);
		return () => clearInterval(timer);
	});

	async function syncNow() {
		const result = await sync();
		syncMessage = result.message;
		await refreshQueue();
	}

	const photos = (s: Survey) => s.passes.reduce((n, p) => n + p.photo_count, 0);
</script>

{#if session.me}
	<div class="hello">
		<h1>{t('home.hello', { name: session.me.display_name })}</h1>
		<a class="btn quiet" href="/app/protocol"><Icon name="card" size={18} />{t('nav.protocol')}</a>
	</div>

	{#if waiting > 0}
		<div class="pending" role="status">
			<Icon name="camera" size={22} />
			<span>{t('home.unsynced', { n: waiting })}</span>
			<button class="btn peach" onclick={syncNow}>{t('home.syncNow')}</button>
			{#if syncMessage}<p class="hint">{syncMessage}</p>{/if}
		</div>
	{/if}

	{#if session.me.teams.length === 0}
		<p class="panel">{t('home.noTeams')}</p>
	{/if}

	{#each session.me.teams as team (team.id)}
		<section class="panel team">
			<div class="panel-head">
				<div>
					<h2>{team.name}</h2>
					<span class="hint">{team.city}</span>
				</div>
				{#if team.role === 'admin'}
					<a class="btn quiet" href="/app/team/{team.id}"><Icon name="team" size={18} />{t('home.manageTeam')}</a>
				{/if}
			</div>
			{#if (surveys[team.id] ?? []).length === 0}
				<p class="empty">{t('home.noSurveys')}</p>
			{:else}
				<ul class="rows">
					{#each surveys[team.id] ?? [] as s (s.id)}
						<li>
							<a href="/app/survey/{s.id}">
								<span class="icon" aria-hidden="true"><Icon name="survey" size={20} /></span>
								<span class="name">{s.name}</span>
								<span class="meta">{s.route.name}</span>
								<span class="meta">{t('survey.startTime', { time: s.start_window_local.slice(0, 5) })}</span>
								<span class="meta num">{t('survey.photos', { n: photos(s) })}</span>
								<span class="passes">
									{#each s.passes as p (p.id)}
										<span class="chip" class:done={p.locked}>{t('survey.pass', { n: p.pass_no })}</span>
									{/each}
								</span>
							</a>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	{/each}
{:else if session.loaded}
	<p class="panel">{t('home.noTeams')}</p>
{/if}

<style>
	.hello {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-3);
		margin: var(--space-2) 0 var(--space-5);
	}
	.hello h1 {
		margin: 0;
	}
	.pending {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-3);
		align-items: center;
		background: var(--peach-wash);
		border-radius: var(--radius-panel);
		padding: var(--space-4) var(--space-5);
		margin-bottom: var(--space-4);
		font-weight: 500;
	}
	.pending .hint {
		flex-basis: 100%;
		margin: 0;
	}
	.team + .team {
		margin-top: var(--space-4);
	}
	.empty {
		background: var(--surface-soft);
		border-radius: var(--radius-tile);
		padding: var(--space-4) var(--space-5);
		margin: 0;
	}
	.rows {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: var(--space-2);
	}
	.rows a {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 2px var(--space-4);
		align-items: center;
		padding: var(--space-3) var(--space-4);
		border-radius: var(--radius-tile);
		background: var(--surface-soft);
		color: var(--ink);
		text-decoration: none;
	}
	.rows a:hover {
		background: var(--canvas);
	}
	.icon {
		grid-row: span 4;
		display: grid;
		place-items: center;
		width: 2.6rem;
		height: 2.6rem;
		border-radius: 50%;
		background: var(--sage);
		color: var(--slate);
	}
	.name {
		font-family: var(--font-display);
		font-weight: 700;
		color: var(--slate);
		font-size: var(--step-1);
	}
	.meta {
		color: var(--fog-text);
	}
	.passes {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
	}
	@media (min-width: 900px) {
		.rows a {
			grid-template-columns: auto minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 1fr) auto auto;
		}
		.icon {
			grid-row: auto;
		}
		.name {
			font-size: var(--step-0);
		}
	}
</style>

<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { api } from '$lib/api';
	import { recall, remember } from '$lib/cache';
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
</script>

{#if session.me}
	<h1>{t('home.hello', { name: session.me.display_name })}</h1>

	{#if waiting > 0}
		<div class="pending" role="status">
			<span>{t('home.unsynced', { n: waiting })}</span>
			<button class="btn" onclick={syncNow}>{t('home.syncNow')}</button>
			{#if syncMessage}<p class="hint">{syncMessage}</p>{/if}
		</div>
	{/if}

	{#if session.me.teams.length === 0}
		<p>{t('home.noTeams')}</p>
	{/if}

	{#each session.me.teams as team (team.id)}
		<section class="team">
			<div class="team-head">
				<h2>{team.name}</h2>
				<span class="city">{team.city}</span>
				{#if team.role === 'admin'}
					<a href="/app/team/{team.id}">{t('home.manageTeam')}</a>
				{/if}
			</div>
			{#if (surveys[team.id] ?? []).length === 0}
				<p class="hint">{t('home.noSurveys')}</p>
			{/if}
			<ul class="surveys">
				{#each surveys[team.id] ?? [] as s (s.id)}
					<li>
						<a href="/app/survey/{s.id}">
							<span class="name">{s.name}</span>
							<span class="meta">{s.route.name}, {t('survey.startTime', { time: s.start_window_local.slice(0, 5) })}</span>
							<span class="meta">
								{#each s.passes as p (p.id)}
									<span class="pass-chip" class:done={p.locked}>{t('survey.pass', { n: p.pass_no })}</span>
								{/each}
							</span>
						</a>
					</li>
				{/each}
			</ul>
		</section>
	{/each}
{:else if session.loaded}
	<p>{t('home.noTeams')}</p>
{/if}

<style>
	.pending {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-3);
		align-items: center;
		background: var(--sodium-wash);
		border-left: 6px solid var(--sodium);
		padding: var(--space-3) var(--space-4);
		margin-bottom: var(--space-5);
	}
	.team {
		margin-top: var(--space-6);
	}
	.team-head {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-3);
		margin-bottom: var(--space-3);
	}
	.team-head h2 {
		margin: 0;
	}
	.city,
	.hint,
	.meta {
		color: var(--fog-text);
	}
	.surveys {
		list-style: none;
		padding: 0;
		margin: 0;
		border-top: 1px solid var(--rule);
	}
	.surveys a {
		display: grid;
		gap: 2px;
		padding: var(--space-4) 0;
		border-bottom: 1px solid var(--rule);
		color: var(--ink);
		text-decoration: none;
		min-height: var(--target);
	}
	.name {
		font-family: var(--font-display);
		font-size: var(--step-1);
		font-weight: 600;
	}
	.pass-chip {
		display: inline-block;
		margin-right: var(--space-2);
		padding: 0 var(--space-2);
		border: 1px solid var(--fog);
		border-radius: 4px;
	}
	.pass-chip.done {
		border-color: var(--notch-teal);
		color: var(--notch-teal);
	}
</style>

<script lang="ts">
	import { untrack } from 'svelte';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import RouteEditor from '$lib/components/RouteEditor.svelte';
	import { session } from '$lib/session.svelte';
	import type { Member, MemberInvite, Role, Route, Survey } from '$lib/types';

	const teamId = $derived(page.params.id ?? '');
	const team = $derived(session.me?.teams.find((x) => x.id === teamId));

	let members = $state<Member[]>([]);
	let routes = $state<Route[]>([]);
	let surveys = $state<Survey[]>([]);
	let error = $state<string | null>(null);
	let lastInvite = $state<MemberInvite | null>(null);
	let copied = $state(false);

	let newName = $state('');
	let newRole = $state<Role>('walker');
	let routeName = $state('');
	let corridor = $state(40);
	let points = $state<[number, number][]>([]);
	let drawing = $state(false);
	let surveyName = $state('');
	let surveyRoute = $state('');
	let surveyTime = $state('06:30');

	async function load() {
		try {
			[members, routes, surveys] = await Promise.all([
				api.get<Member[]>(`/teams/${teamId}/members`),
				api.get<Route[]>(`/teams/${teamId}/routes`),
				api.get<Survey[]>(`/teams/${teamId}/surveys`)
			]);
			surveyRoute ||= routes[0]?.id ?? '';
		} catch (e) {
			error = (e as Error).message;
		}
	}

	$effect(() => {
		const id = teamId;
		if (id) untrack(() => void load());
	});

	async function run(action: () => Promise<void>) {
		error = null;
		try {
			await action();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	const addMember = () =>
		run(async () => {
			lastInvite = await api.post<MemberInvite>(`/teams/${teamId}/members`, { display_name: newName.trim(), role: newRole });
			newName = '';
			copied = false;
			await load();
		});

	const reinvite = (m: Member) =>
		run(async () => {
			lastInvite = await api.post<MemberInvite>(`/teams/${teamId}/members/${m.user_id}/invite`);
			copied = false;
		});

	async function share(invite: MemberInvite) {
		const text = `NotchCount sign-in link for ${invite.display_name} (one use):`;
		if (navigator.share) {
			try {
				await navigator.share({ title: 'NotchCount', text, url: invite.invite_url });
				return;
			} catch {
				/* fall through to copy */
			}
		}
		await navigator.clipboard.writeText(invite.invite_url);
		copied = true;
	}

	const saveRoute = () =>
		run(async () => {
			await api.post(`/teams/${teamId}/routes`, {
				name: routeName.trim(),
				corridor_m: corridor,
				geometry: { type: 'LineString', coordinates: points }
			});
			routeName = '';
			points = [];
			drawing = false;
			await load();
		});

	const createSurvey = () =>
		run(async () => {
			await api.post(`/teams/${teamId}/surveys`, {
				route_id: surveyRoute,
				name: surveyName.trim(),
				start_window_local: surveyTime
			});
			surveyName = '';
			await load();
		});
</script>

<h1>{team?.name ?? 'Team'}</h1>
{#if error}<p class="error" role="alert">{error}</p>{/if}

<div class="columns">
	<section>
		<h2>People</h2>
		<ul class="list">
			{#each members as m (m.user_id)}
				<li>
					<span>{m.display_name}</span>
					<span class="role">{m.role}</span>
					<button class="btn quiet" onclick={() => reinvite(m)}>New sign-in link</button>
				</li>
			{/each}
		</ul>
		<form
			onsubmit={(e) => {
				e.preventDefault();
				void addMember();
			}}
		>
			<div class="field">
				<label for="member-name">Name shown in the app</label>
				<input id="member-name" bind:value={newName} required maxlength="80" autocomplete="off" />
				<span class="hint">First name only. We do not store phone numbers here.</span>
			</div>
			<div class="field">
				<label for="member-role">Role</label>
				<select id="member-role" bind:value={newRole}>
					<option value="walker">Walker: walks passes and takes photos</option>
					<option value="reviewer">Reviewer: also confirms matches and ear calls</option>
					<option value="admin">Admin: also draws routes and files the case</option>
				</select>
			</div>
			<button class="btn" type="submit" disabled={!newName.trim()}>Add person and make a sign-in link</button>
		</form>
		{#if lastInvite}
			<div class="invite" role="status">
				<p>Send this link to {lastInvite.display_name}. It works once, for 7 days.</p>
				<code>{lastInvite.invite_url}</code>
				<button class="btn" onclick={() => lastInvite && share(lastInvite)}>{copied ? 'Copied' : 'Share link'}</button>
			</div>
		{/if}
	</section>

	<section>
		<h2>Routes</h2>
		<ul class="list">
			{#each routes as r (r.id)}
				<li>
					<span>{r.name}</span>
					<span class="num">{(r.length_m / 1000).toFixed(2)} km, corridor {r.corridor_m} m</span>
				</li>
			{/each}
		</ul>
		{#if drawing}
			<RouteEditor bind:points />
			<form
				onsubmit={(e) => {
					e.preventDefault();
					void saveRoute();
				}}
			>
				<div class="field">
					<label for="route-name">Route name</label>
					<input id="route-name" bind:value={routeName} required maxlength="120" placeholder="Gali No. 4 loop" />
				</div>
				<div class="field">
					<label for="corridor">Corridor width either side (metres)</label>
					<input id="corridor" type="number" min="5" max="500" bind:value={corridor} />
					<span class="hint">Photos taken farther than this from the route are flagged for review.</span>
				</div>
				<button class="btn" type="submit" disabled={points.length < 2 || !routeName.trim()}>Save route</button>
				<button class="btn quiet" type="button" onclick={() => (drawing = false)}>Cancel</button>
			</form>
		{:else}
			<button class="btn" onclick={() => (drawing = true)}>Draw a route</button>
		{/if}

		<h2 class="gap">Surveys</h2>
		<ul class="list">
			{#each surveys as s (s.id)}
				<li><a href="/app/survey/{s.id}">{s.name}</a><span>{s.route.name}, starts {s.start_window_local.slice(0, 5)}</span></li>
			{/each}
		</ul>
		{#if routes.length > 0}
			<form
				onsubmit={(e) => {
					e.preventDefault();
					void createSurvey();
				}}
			>
				<div class="field">
					<label for="survey-name">Survey name</label>
					<input id="survey-name" bind:value={surveyName} required maxlength="120" placeholder="October 2026" />
				</div>
				<div class="field">
					<label for="survey-route">Route</label>
					<select id="survey-route" bind:value={surveyRoute}>
						{#each routes as r (r.id)}<option value={r.id}>{r.name}</option>{/each}
					</select>
				</div>
				<div class="field">
					<label for="survey-time">Agreed start time</label>
					<input id="survey-time" type="time" bind:value={surveyTime} required />
					<span class="hint">Every pass starts within 15 minutes of this time.</span>
				</div>
				<button class="btn" type="submit" disabled={!surveyName.trim() || !surveyRoute}>Create survey</button>
			</form>
		{:else}
			<p class="hint">Draw a route first, then create a survey on it.</p>
		{/if}
	</section>
</div>

<style>
	.columns {
		display: grid;
		gap: var(--space-6);
	}
	@media (min-width: 900px) {
		.columns {
			grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
		}
	}
	.list {
		list-style: none;
		padding: 0;
		margin: 0 0 var(--space-4);
		border-top: 1px solid var(--rule);
	}
	.list li {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2) var(--space-4);
		align-items: center;
		padding: var(--space-2) 0;
		border-bottom: 1px solid var(--rule);
		min-height: var(--target);
	}
	.role {
		color: var(--fog-text);
		flex: 1;
	}
	.invite {
		margin-top: var(--space-4);
		padding: var(--space-4);
		background: #fff;
		border-left: 6px solid var(--notch-teal);
		display: grid;
		gap: var(--space-3);
	}
	.invite code {
		word-break: break-all;
		font-size: 0.9rem;
	}
	.gap {
		margin-top: var(--space-6);
	}
	form .btn {
		margin-right: var(--space-2);
	}
</style>

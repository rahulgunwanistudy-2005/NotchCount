<script lang="ts">
	/** Admin only: job queue by kind and state, jobs that gave up, photos by state, model versions. */
	import { onMount } from 'svelte';
	import { api } from '$lib/api';

	interface Health {
		queue: Record<string, number>;
		dead_jobs: { id: number; kind: string; attempts: number; error: string }[];
		photos: Record<string, number>;
		model_versions: string[];
	}

	let health = $state<Health | null>(null);
	let error = $state<string | null>(null);
	let checkedAt = $state<Date | null>(null);

	async function load() {
		try {
			health = await api.get<Health>('/admin/health');
			checkedAt = new Date();
			error = null;
		} catch (e) {
			error = (e as Error).message;
		}
	}

	onMount(() => {
		void load();
		const timer = setInterval(load, 10_000);
		return () => clearInterval(timer);
	});

	const states = ['queued', 'running', 'done', 'dead'] as const;
	const kinds = $derived(
		health ? [...new Set(Object.keys(health.queue).map((k) => k.split(':')[0]))].sort() : []
	);
	const count = (kind: string, st: string) => health?.queue[`${kind}:${st}`] ?? 0;
	const waiting = $derived(kinds.reduce((n, k) => n + count(k, 'queued') + count(k, 'running'), 0));
</script>

<div class="head">
	<h1>System health</h1>
	{#if checkedAt}<span class="hint">Checked {checkedAt.toLocaleTimeString()}. Refreshes every 10 seconds.</span>{/if}
</div>
{#if error}<p class="error" role="alert">{error}</p>{/if}

{#if health}
	<div class="grid">
		<section class="panel">
			<div class="panel-head">
				<h2>Job queue</h2>
				<span class="chip" class:done={waiting === 0} class:warn={waiting > 0}>
					{waiting === 0 ? 'Nothing waiting' : `${waiting} waiting or running`}
				</span>
			</div>
			{#if kinds.length === 0}
				<p class="hint">No jobs yet. Jobs appear when photos upload or someone runs matching.</p>
			{:else}
				<div class="scroll">
					<table>
						<thead>
							<tr>
								<th scope="col">Job</th>
								{#each states as st (st)}<th scope="col" class="r">{st}</th>{/each}
							</tr>
						</thead>
						<tbody>
							{#each kinds as k (k)}
								<tr>
									<th scope="row">{k.replace(/_/g, ' ')}</th>
									{#each states as st (st)}
										<td class="r num" class:bad={st === 'dead' && count(k, st) > 0}>{count(k, st)}</td>
									{/each}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>

		<section class="panel">
			<div class="panel-head"><h2>Photos</h2></div>
			<dl class="pairs">
				{#each Object.entries(health.photos) as [st, n] (st)}
					<div><dt>{st}</dt><dd class="num">{n}</dd></div>
				{:else}
					<p class="hint">No photos yet.</p>
				{/each}
			</dl>
			<h3>Models in use</h3>
			<ul class="models">
				{#each health.model_versions as v (v)}<li>{v}</li>{:else}<li class="hint">None yet</li>{/each}
			</ul>
		</section>

		<section class="panel wide">
			<div class="panel-head"><h2>Jobs that gave up</h2></div>
			{#if health.dead_jobs.length === 0}
				<p class="hint">None. A job gives up after repeated failures; it would be listed here with its error.</p>
			{:else}
				<ul class="dead">
					{#each health.dead_jobs as j (j.id)}
						<li>
							<strong>{j.kind.replace(/_/g, ' ')}</strong>, job {j.id}, {j.attempts} attempts
							<pre>{j.error}</pre>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	</div>
{/if}

<style>
	.head {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-2) var(--space-4);
		margin: var(--space-2) 0 var(--space-5);
	}
	.head h1 {
		margin: 0;
	}
	.grid {
		display: grid;
		gap: var(--space-4);
	}
	@media (min-width: 1000px) {
		.grid {
			grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
		}
		.wide {
			grid-column: 1 / -1;
		}
	}
	@media (max-width: 480px) {
		th,
		td {
			padding: var(--space-2) var(--space-1);
			font-size: 0.88rem;
		}
	}
	table {
		width: 100%;
		border-collapse: collapse;
	}
	th,
	td {
		padding: var(--space-2) var(--space-3);
		text-align: left;
		border-bottom: 1px solid var(--rule);
	}
	thead th {
		color: var(--fog-text);
		font-weight: 500;
	}
	tbody th {
		font-weight: 500;
	}
	.r {
		text-align: right;
	}
	.bad {
		color: var(--danger);
		font-weight: 700;
	}
	.pairs {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(7rem, 1fr));
		gap: var(--space-3);
		margin: 0 0 var(--space-5);
	}
	.pairs div {
		background: var(--surface-soft);
		border-radius: var(--radius-tile);
		padding: var(--space-3) var(--space-4);
	}
	dt {
		color: var(--fog-text);
	}
	dd {
		margin: 0;
		font-size: var(--step-2);
		font-weight: 500;
	}
	.models {
		margin: 0;
		padding-left: 1.1rem;
		overflow-wrap: anywhere;
	}
	.dead {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: var(--space-3);
	}
	.dead li {
		background: var(--surface-soft);
		border-radius: var(--radius-tile);
		padding: var(--space-3) var(--space-4);
	}
	pre {
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		font-size: 0.85rem;
		margin: var(--space-2) 0 0;
		color: var(--ink-soft);
	}
</style>

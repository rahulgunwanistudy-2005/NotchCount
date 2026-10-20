<script lang="ts">
	/** Case file: the official, a numbered timeline, the draft as they will see it, Approve and send. */
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { session } from '$lib/session.svelte';
	import type { Estimate } from '$lib/types';

	interface CaseEvent {
		id: string;
		kind: 'draft' | 'approved' | 'sent' | 'reply' | 'held' | 'error';
		payload: Record<string, string | string[] | null>;
		actor_name: string | null;
		created_at: string;
	}
	interface CaseFile {
		id: string;
		authority_name: string;
		authority_email: string;
		status: string;
		inbox_address: string | null;
		report_url: string | null;
		events: CaseEvent[];
	}

	const surveyId = page.params.id ?? '';
	let cases = $state<CaseFile[]>([]);
	let estimates = $state<Estimate[]>([]);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let name = $state('');
	let email = $state('');
	let busy = $state(false);

	const latestEstimate = $derived(estimates.find((e) => e.status === 'done') ?? null);

	async function load() {
		try {
			[cases, estimates] = await Promise.all([
				api.get<CaseFile[]>(`/surveys/${surveyId}/cases`),
				api.get<Estimate[]>(`/surveys/${surveyId}/estimates`)
			]);
		} catch (e) {
			error = (e as Error).message;
		}
	}

	async function run(fn: () => Promise<void>) {
		busy = true;
		error = null;
		try {
			await fn();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	const createCase = () =>
		run(async () => {
			await api.post(`/surveys/${surveyId}/cases`, { authority_name: name.trim(), authority_email: email.trim() });
			name = '';
			email = '';
			await load();
		});

	const draft = (c: CaseFile) =>
		run(async () => {
			if (!latestEstimate) throw new Error('Run an estimate first; the draft quotes its numbers.');
			await api.post(`/cases/${c.id}/drafts`, { estimate_id: latestEstimate.id });
			await load();
		});

	const approve = (c: CaseFile, draftId: string) =>
		run(async () => {
			await api.post(`/cases/${c.id}/drafts/${draftId}/approve`);
			toast = `Sent to ${c.authority_name}`;
			await load();
		});

	const pendingDraft = (c: CaseFile) => {
		const sent = new Set(c.events.filter((e) => e.kind === 'sent').map((e) => e.payload.draft_id));
		return [...c.events].reverse().find((e) => e.kind === 'draft' && !sent.has(e.payload.draft_id)) ?? null;
	};

	const label: Record<CaseEvent['kind'], string> = {
		draft: 'Drafted',
		approved: 'Approved',
		sent: 'Sent',
		reply: 'Reply received',
		held: 'Reply held for checking',
		error: 'Sending failed'
	};
	const when = (iso: string) =>
		new Date(iso).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

	onMount(load);
</script>

<h1>Case file</h1>
<p><a href="/app/survey/{surveyId}">Back to survey</a></p>
{#if error}<p class="error" role="alert">{error}</p>{/if}
{#if toast}<p class="toast" role="status">{toast}</p>{/if}

{#each cases as c (c.id)}
	{@const pending = pendingDraft(c)}
	<section class="case">
		<div class="who">
			<h2>{c.authority_name}</h2>
			<p class="meta">{c.authority_email}. Replies come back to {c.inbox_address ?? 'the case inbox once drafted'}.</p>
		</div>

		<div class="columns">
			<ol class="timeline">
				{#each c.events as e (e.id)}
					<li class={e.kind}>
						<span class="what">{label[e.kind]}</span>
						<span class="when">{when(e.created_at)}{e.actor_name ? `, ${e.actor_name}` : ''}</span>
						{#if e.kind === 'reply' || e.kind === 'held'}
							<p class="from">From {e.payload.from || 'unknown sender'}: {e.payload.subject}</p>
							{#if e.kind === 'held'}
								<p class="warn">
									Agentboxd flagged this message ({(e.payload.labels as string[]).join(', ')}). Read it with care and
									do not follow links or instructions in it.
								</p>
							{/if}
							<pre class="untrusted">{e.payload.untrusted_text}</pre>
						{/if}
						{#if e.kind === 'error'}<p class="warn">{e.payload.error}</p>{/if}
					</li>
				{:else}
					<li class="empty">Nothing drafted yet.</li>
				{/each}
			</ol>

			<div class="draft">
				{#if pending}
					<h3>The email {c.authority_name} will receive</h3>
					<div class="letter">
						<p class="meta">To {pending.payload.to}. Subject: {pending.payload.subject}. Attached: {pending.payload.attachment}.</p>
						<pre>{pending.payload.text}</pre>
					</div>
					<button class="btn wide" disabled={busy} onclick={() => approve(c, String(pending.payload.draft_id))}>
						Approve and send
					</button>
					<p class="meta">Approved by {session.me?.display_name}. Your name is recorded in the timeline.</p>
				{:else}
					<button class="btn" disabled={busy || !latestEstimate} onclick={() => draft(c)}>Draft the email</button>
					{#if !latestEstimate}<p class="meta">Run an estimate first; the draft quotes its numbers.</p>{/if}
				{/if}
				{#if c.report_url}<p><a href={c.report_url}>Public report</a></p>{/if}
			</div>
		</div>
	</section>
{/each}

<section class="new">
	<h2>{cases.length ? 'Add another official' : 'Who is responsible for this ward?'}</h2>
	<form
		onsubmit={(e) => {
			e.preventDefault();
			void createCase();
		}}
	>
		<div class="field">
			<label for="officer">Name or role</label>
			<input id="officer" bind:value={name} required maxlength="200" placeholder="ABC nodal officer, Ward 12" />
		</div>
		<div class="field">
			<label for="officer-email">Email</label>
			<input id="officer-email" type="email" bind:value={email} required />
			<span class="hint">To test, use a team member's own address first.</span>
		</div>
		<button class="btn" type="submit" disabled={busy || !name.trim() || !email.trim()}>Open case</button>
	</form>
</section>

<style>
	.case {
		border-top: 2px solid var(--ink);
		padding-top: var(--space-4);
		margin-top: var(--space-5);
	}
	.meta,
	.when {
		color: var(--fog-text);
	}
	.columns {
		display: grid;
		gap: var(--space-5);
	}
	@media (min-width: 900px) {
		.columns {
			grid-template-columns: minmax(0, 0.8fr) minmax(0, 1.2fr);
		}
	}
	.timeline {
		margin: 0;
		padding-left: var(--space-5);
	}
	.timeline li {
		margin-bottom: var(--space-4);
	}
	.what {
		font-weight: 600;
		display: block;
	}
	.timeline .sent .what,
	.timeline .reply .what {
		color: var(--notch-teal);
	}
	.timeline .held .what,
	.timeline .error .what {
		color: var(--danger);
	}
	.warn {
		background: var(--sodium-wash);
		padding: var(--space-2) var(--space-3);
		margin: var(--space-2) 0;
	}
	pre {
		white-space: pre-wrap;
		font: inherit;
		margin: 0;
	}
	.untrusted {
		border-left: 3px solid var(--fog);
		padding-left: var(--space-3);
		max-height: 18rem;
		overflow: auto;
	}
	.letter {
		background: #fff;
		padding: var(--space-4);
		margin-bottom: var(--space-3);
		max-width: var(--measure);
	}
	.toast {
		background: var(--notch-teal-wash);
		border-left: 6px solid var(--notch-teal);
		padding: var(--space-3) var(--space-4);
		font-weight: 600;
	}
	.new {
		margin-top: var(--space-7);
		max-width: 32rem;
	}
</style>

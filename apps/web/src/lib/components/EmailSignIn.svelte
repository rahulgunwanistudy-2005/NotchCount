<script lang="ts">
	/**
	 * Email sign-in with a one-time code (MojoAuth). In "link" mode a signed-in person adds email
	 * sign-in to their own account, so next time they need no link.
	 */
	import { api } from '$lib/api';

	let { mode = 'signin', ondone }: { mode?: 'signin' | 'link'; ondone: () => void } = $props();

	let email = $state('');
	let code = $state('');
	let stateId = $state<string | null>(null);
	let busy = $state(false);
	let error = $state<string | null>(null);

	async function send() {
		busy = true;
		error = null;
		try {
			stateId = (await api.post<{ state_id: string }>('/auth/email/start', { email: email.trim() })).state_id;
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	async function verify() {
		busy = true;
		error = null;
		try {
			await api.post('/auth/email/verify', { state_id: stateId, code: code.trim() });
			ondone();
		} catch (e) {
			error = (e as Error).message;
		} finally {
			busy = false;
		}
	}
</script>

{#if !stateId}
	<form
		class="row"
		onsubmit={(e) => {
			e.preventDefault();
			void send();
		}}
	>
		<div class="field grow">
			<label for="otp-email">{mode === 'link' ? 'Your email' : 'Email'}</label>
			<input id="otp-email" type="email" autocomplete="email" bind:value={email} required />
		</div>
		<button class="btn" type="submit" disabled={busy || !email.includes('@')}>Email me a code</button>
	</form>
{:else}
	<form
		class="row"
		onsubmit={(e) => {
			e.preventDefault();
			void verify();
		}}
	>
		<div class="field grow">
			<label for="otp-code">Code sent to {email}</label>
			<input
				id="otp-code"
				inputmode="numeric"
				autocomplete="one-time-code"
				maxlength="12"
				bind:value={code}
				required
			/>
		</div>
		<button class="btn peach" type="submit" disabled={busy || code.trim().length < 4}>
			{mode === 'link' ? 'Add email sign-in' : 'Sign in'}
		</button>
		<button class="btn quiet" type="button" onclick={() => (stateId = null)}>Use another email</button>
	</form>
{/if}
{#if error}<p class="error" role="alert">{error}</p>{/if}

<style>
	.row {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-end;
		gap: var(--space-3);
	}
	.grow {
		flex: 1;
		min-width: min(100%, 15rem);
		margin-bottom: 0;
	}
	.error {
		margin-top: var(--space-3);
	}
</style>

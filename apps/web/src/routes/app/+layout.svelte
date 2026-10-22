<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { forgetAll, recall } from '$lib/cache';
	import Badge from '$lib/components/Badge.svelte';
	import Doodle from '$lib/components/Doodle.svelte';
	import Icon, { type IconName } from '$lib/components/Icon.svelte';
	import { hindiAvailable, locale, setLang, t } from '$lib/i18n/index.svelte';
	import { counts, requestPersistence, sync } from '$lib/queue';
	import { loadMe, session } from '$lib/session.svelte';
	import { SAMPLE_REPORT_SLUG } from '$lib/site';
	import type { Survey } from '$lib/types';

	let { children } = $props();
	const path = $derived(page.url.pathname);
	const fullScreen = $derived(path.includes('/capture/'));
	// The field card is safety guidance; anyone may read it without signing in.
	const openToAll = $derived(path.startsWith('/app/protocol'));
	let menuOpen = $state(false);

	onMount(() => {
		void loadMe();
		void requestPersistence();
		void sync();
		const onOnline = () => void sync();
		window.addEventListener('online', onOnline);
		return () => window.removeEventListener('online', onOnline);
	});

	$effect(() => {
		void path;
		menuOpen = false;
	});

	interface NavItem {
		href: string;
		label: string;
		icon: IconName;
		sub?: boolean;
	}

	const surveyId = $derived(path.match(/^\/app\/survey\/([^/]+)/)?.[1] ?? null);
	// The sidebar names the open survey and shows its checks; it loads the survey itself (cache first).
	let navSurvey = $state<Survey | null>(null);
	$effect(() => {
		const sid = surveyId;
		if (!sid) return;
		navSurvey = recall<Survey>(`survey.${sid}`);
		api
			.get<Survey>(`/surveys/${sid}`)
			.then((s) => (navSurvey = s))
			.catch(() => {
				/* offline: the cached name, or a generic label */
			});
	});
	const surveyName = $derived(navSurvey?.id === surveyId ? navSurvey.name : t('nav.thisSurvey'));
	const surveyRole = $derived(
		navSurvey?.id === surveyId ? (session.me?.teams.find((x) => x.id === navSurvey?.team_id)?.role ?? null) : null
	);
	const isAdmin = $derived(session.me?.teams.some((x) => x.role === 'admin') ?? false);

	const nav = $derived.by(() => {
		const items: NavItem[] = [{ href: '/app', label: t('nav.home'), icon: 'home' }];
		if (surveyId) {
			items.push({ href: `/app/survey/${surveyId}`, label: surveyName ?? t('nav.thisSurvey'), icon: 'survey' });
			if (surveyRole && surveyRole !== 'walker') {
				items.push(
					{ href: `/app/survey/${surveyId}/check/pairs`, label: t('nav.pairs'), icon: 'pairs', sub: true },
					{ href: `/app/survey/${surveyId}/check/ears`, label: t('nav.ears'), icon: 'ear', sub: true },
					{ href: `/app/survey/${surveyId}/check/review`, label: t('nav.review'), icon: 'review', sub: true }
				);
			}
			if (surveyRole === 'admin') {
				items.push({ href: `/app/survey/${surveyId}/case`, label: t('nav.case'), icon: 'case', sub: true });
			}
		}
		for (const team of session.me?.teams ?? []) {
			if (team.role === 'admin') items.push({ href: `/app/team/${team.id}`, label: team.name, icon: 'team' });
		}
		items.push({ href: '/app/protocol', label: t('nav.protocol'), icon: 'card' });
		if (isAdmin) items.push({ href: '/app/health', label: t('nav.health'), icon: 'pulse' });
		return items;
	});

	const current = (href: string) => (href === '/app' ? path === '/app' || path === '/app/' : path === href);
	const initial = (name: string) => name.trim().charAt(0).toUpperCase() || '?';

	async function signOut() {
		const waiting = (await counts()).queued;
		if (waiting > 0 && !confirm(`${waiting} photos have not uploaded yet. They stay on this phone and upload after you sign in again. Sign out?`))
			return;
		try {
			await api.post('/auth/logout');
		} finally {
			forgetAll();
			session.me = null;
			await goto('/');
		}
	}
</script>

{#if fullScreen}
	{@render children()}
{:else}
	<div class="shell">
		<aside class="side" class:open={menuOpen}>
			<div class="side-top">
				<a class="badge-link" href="/app"><Badge size={112} label="NotchCount home" /></a>
				<button class="menu btn quiet" aria-expanded={menuOpen} aria-controls="side-nav" onclick={() => (menuOpen = !menuOpen)}>
					<Icon name="menu" size={18} />{t('nav.menu')}
				</button>
			</div>
			<nav id="side-nav" aria-label="App">
				<ul>
					{#each nav as item (item.href)}
						<li>
							<a href={item.href} class:sub={item.sub} aria-current={current(item.href) ? 'page' : undefined}>
								<Icon name={item.icon} size={18} /><span>{item.label}</span>
							</a>
						</li>
					{/each}
				</ul>
			</nav>
			<Doodle shape="dots" class="side-dots" />
		</aside>

		<div class="main">
			<header class="top">
				<p class="where">
					{#if session.me}{session.me.teams.map((x) => x.name).join(', ')}{/if}
				</p>
				<div class="tools">
					{#if hindiAvailable}
						<button class="round" onclick={() => setLang(locale.lang === 'en' ? 'hi' : 'en')} aria-label="Change language">
							<Icon name="globe" size={18} /><span class="round-label">{t('lang.switch')}</span>
						</button>
					{/if}
					{#if session.me}
						<span class="me"><span class="avatar" aria-hidden="true">{initial(session.me.display_name)}</span>{session.me.display_name}</span>
						<button class="round" onclick={signOut} aria-label={t('nav.signout')}>
							<Icon name="logout" size={18} /><span class="round-label">{t('nav.signout')}</span>
						</button>
					{/if}
				</div>
			</header>
			<main class="content">
				{#if session.loaded && session.signedOut && !openToAll}
					<section class="panel signin">
						<Badge size={120} label="NotchCount" />
						<div>
							<h1>{t('signin.title')}</h1>
							<p>{t('signin.body')}</p>
							<a class="btn peach" href="/r/{SAMPLE_REPORT_SLUG}">{t('signin.sample')}</a>
						</div>
					</section>
				{:else}
					{@render children()}
				{/if}
			</main>
		</div>
	</div>
{/if}

<style>
	.shell {
		display: grid;
		gap: var(--space-4);
		padding: var(--space-3);
		min-height: 100vh;
		max-width: 100rem;
		margin: 0 auto;
	}
	@media (min-width: 960px) {
		.shell {
			grid-template-columns: 15.5rem minmax(0, 1fr);
			gap: var(--space-5);
			padding: var(--space-5);
		}
	}

	/* The sidebar is one tall white card with the badge on top. */
	.side {
		position: relative;
		background: var(--surface);
		border-radius: var(--radius-shell);
		padding: var(--space-4);
		align-self: start;
	}
	@media (min-width: 960px) {
		.side {
			position: sticky;
			top: var(--space-5);
			min-height: calc(100vh - 2 * var(--space-5));
			padding: var(--space-6) var(--space-4);
		}
	}
	.side-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-3);
	}
	@media (min-width: 960px) {
		.side-top {
			justify-content: center;
			margin-bottom: var(--space-6);
		}
		.menu {
			display: none;
		}
	}
	@media (max-width: 959px) {
		.badge-link :global(svg) {
			width: 64px;
			height: 64px;
		}
		nav {
			display: none;
		}
		.side.open nav {
			display: block;
			margin-top: var(--space-3);
		}
	}
	.badge-link {
		border-radius: 50%;
	}
	nav ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 2px;
	}
	nav a {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		min-height: var(--target);
		padding: var(--space-2) var(--space-3);
		border-radius: var(--radius-field);
		color: var(--ink-soft);
		text-decoration: none;
		font-weight: 500;
		line-height: 1.25;
	}
	nav a span {
		min-width: 0;
		overflow-wrap: anywhere;
	}
	nav a.sub {
		padding-left: var(--space-6);
		font-size: 0.94rem;
	}
	nav a:hover {
		background: var(--surface-soft);
		color: var(--slate);
	}
	nav a[aria-current='page'] {
		background: var(--canvas);
		color: var(--slate);
	}
	.side :global(.side-dots) {
		width: 54px;
		left: var(--space-5);
		bottom: var(--space-6);
		opacity: 0.85;
	}
	@media (max-width: 959px) {
		.side :global(.side-dots) {
			display: none;
		}
	}

	.main {
		min-width: 0;
		display: grid;
		gap: var(--space-4);
		align-content: start;
	}
	.top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: var(--space-3);
		min-height: 3.5rem;
	}
	.where {
		margin: 0;
		color: var(--fog-text);
		background: var(--surface);
		border-radius: var(--radius-control);
		padding: var(--space-2) var(--space-5);
		min-width: 0;
		max-width: 28rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.where:empty {
		visibility: hidden;
	}
	.tools {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		margin-left: auto;
	}
	.me {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		font-family: var(--font-display);
		font-weight: 700;
		color: var(--ink);
	}
	.round {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		min-height: var(--target);
		min-width: var(--target);
		justify-content: center;
		padding: 0 var(--space-3);
		border-radius: var(--radius-control);
		border: 0;
		background: var(--slate);
		color: #fff;
		cursor: pointer;
	}
	.round-label {
		font-size: 0.9rem;
	}
	@media (max-width: 600px) {
		.where {
			display: none;
		}
		.round-label {
			display: none;
		}
		.round {
			padding: 0;
		}
	}
	.content {
		min-width: 0;
	}
	.signin {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-6);
		align-items: center;
		padding: var(--space-7) var(--space-6);
	}
	.signin > div {
		flex: 1;
		min-width: min(100%, 18rem);
	}
</style>

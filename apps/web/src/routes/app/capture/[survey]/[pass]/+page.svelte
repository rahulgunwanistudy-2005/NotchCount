<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { recall } from '$lib/cache';
	import { t } from '$lib/i18n/index.svelte';
	import { encodeFile, encodeFrame, sha256Hex } from '$lib/image';
	import {
		addPhoto,
		counts,
		endLocalPass,
		savePass,
		startLocalPass,
		sync,
		undoPhoto,
		UNDO_WINDOW_MS,
		type LocalPass,
		type QueueCounts
	} from '$lib/queue';
	import type { Shot, Survey } from '$lib/types';

	const surveyId = page.params.survey ?? '';
	const passNo = Number(page.params.pass);

	let pass = $state<LocalPass | null>(null);
	let video = $state<HTMLVideoElement | null>(null);
	let fileInput = $state<HTMLInputElement | null>(null);
	let stream: MediaStream | null = null;
	let cameraFailed = $state(false);
	let busy = $state(false);
	let flash = $state(false);
	let online = $state(typeof navigator === 'undefined' ? true : navigator.onLine);
	let queue = $state<QueueCounts>({ queued: 0, uploaded: 0, rejected: 0 });
	let notice = $state<string | null>(null);
	let confirmingEnd = $state(false);
	let lastPhotoId = $state<string | null>(null);
	let lastShotAt = $state(0);
	let now = $state(Date.now());

	type Fix = { lat: number; lon: number; accuracy: number; heading: number | null; at: number };
	let fix = $state<Fix | null>(null);
	let gpsDenied = $state(false);

	const routeName = recall<Survey>(`survey.${surveyId}`)?.route.name ?? '';
	const fixFresh = $derived(fix !== null && now - fix.at < 30_000);
	const canUndo = $derived(lastPhotoId !== null && now - lastShotAt < UNDO_WINDOW_MS);

	async function refreshQueue() {
		if (pass) queue = await counts(pass.key);
	}

	async function startCamera() {
		try {
			stream = await navigator.mediaDevices.getUserMedia({
				audio: false,
				video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1440 } }
			});
			if (video) {
				video.srcObject = stream;
				await video.play();
			}
			cameraFailed = false;
		} catch {
			cameraFailed = true;
		}
	}

	function stopCamera() {
		stream?.getTracks().forEach((track) => track.stop());
		stream = null;
	}

	async function store(blob: Blob) {
		if (!pass) return;
		const shot: Shot = pass.nextShot;
		const takenAt = new Date().toISOString();
		const sha256 = await sha256Hex(blob);
		const id = crypto.randomUUID();
		if (shot === 'side') pass.dogs += 1;
		await addPhoto({
			id,
			passKey: pass.key,
			blob,
			sha256,
			takenAt,
			lat: fixFresh && fix ? fix.lat : null,
			lon: fixFresh && fix ? fix.lon : null,
			accuracy: fixFresh && fix ? fix.accuracy : null,
			heading: fixFresh && fix ? fix.heading : null,
			shot,
			dog: pass.dogs
		});
		pass.nextShot = shot === 'side' ? 'head' : 'side';
		await savePass($state.snapshot(pass) as LocalPass);
		lastPhotoId = id;
		lastShotAt = Date.now();
		flash = true;
		setTimeout(() => (flash = false), 140);
		navigator.vibrate?.(30);
		await refreshQueue();
		setTimeout(() => void sync().then(refreshQueue), UNDO_WINDOW_MS + 200);
	}

	async function shoot() {
		if (busy || !pass || pass.endedAt) return;
		if (cameraFailed || !video || video.videoWidth === 0) {
			fileInput?.click();
			return;
		}
		busy = true;
		notice = null;
		try {
			await store(await encodeFrame(video, video.videoWidth, video.videoHeight));
		} catch (err) {
			notice = t('capture.saveFailed', { error: err instanceof Error ? err.message : String(err) });
		} finally {
			busy = false;
		}
	}

	async function fromFile(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		input.value = '';
		if (!file) return;
		busy = true;
		try {
			await store(await encodeFile(file));
		} catch (err) {
			notice = t('capture.saveFailed', { error: err instanceof Error ? err.message : String(err) });
		} finally {
			busy = false;
		}
	}

	async function skipHead() {
		if (!pass) return;
		pass.nextShot = 'side';
		await savePass($state.snapshot(pass) as LocalPass);
	}

	async function undo() {
		if (!pass || !lastPhotoId) return;
		if (await undoPhoto(lastPhotoId)) {
			if (pass.nextShot === 'head') {
				pass.dogs = Math.max(0, pass.dogs - 1);
				pass.nextShot = 'side';
			} else {
				pass.nextShot = 'head';
			}
			await savePass($state.snapshot(pass) as LocalPass);
			notice = t('capture.undone');
		}
		lastPhotoId = null;
		await refreshQueue();
	}

	async function endPass() {
		if (!pass) return;
		const ended = await endLocalPass(pass.key);
		if (ended) pass = ended;
		confirmingEnd = false;
		stopCamera();
		await sync();
		await refreshQueue();
	}

	onMount(() => {
		let watchId: number | null = null;
		let wakeLock: WakeLockSentinel | null = null;
		const tick = setInterval(() => (now = Date.now()), 1000);
		const syncTimer = setInterval(() => void sync().then(refreshQueue), 15_000);
		const setOnline = () => {
			online = navigator.onLine;
			if (online) void sync().then(refreshQueue);
		};
		window.addEventListener('online', setOnline);
		window.addEventListener('offline', setOnline);

		void (async () => {
			if (!surveyId || !Number.isInteger(passNo) || passNo < 1) {
				await goto('/app');
				return;
			}
			pass = await startLocalPass(surveyId, passNo, routeName);
			await refreshQueue();
			if (!pass.endedAt) {
				await startCamera();
				try {
					wakeLock = (await navigator.wakeLock?.request('screen')) ?? null;
				} catch {
					/* screen may dim; capture still works */
				}
			}
			void sync().then(refreshQueue);
		})();

		if ('geolocation' in navigator) {
			watchId = navigator.geolocation.watchPosition(
				(p) =>
					(fix = {
						lat: p.coords.latitude,
						lon: p.coords.longitude,
						accuracy: Math.round(p.coords.accuracy),
						heading: p.coords.heading,
						at: Date.now()
					}),
				(e) => {
					if (e.code === e.PERMISSION_DENIED) gpsDenied = true;
				},
				{ enableHighAccuracy: true, maximumAge: 5000, timeout: 20_000 }
			);
		}

		return () => {
			clearInterval(tick);
			clearInterval(syncTimer);
			window.removeEventListener('online', setOnline);
			window.removeEventListener('offline', setOnline);
			if (watchId !== null) navigator.geolocation.clearWatch(watchId);
			void wakeLock?.release();
			stopCamera();
		};
	});
</script>

<svelte:head><title>{t('capture.passOf', { n: passNo })}</title></svelte:head>

<div class="capture" class:ended={pass?.endedAt}>
	<header class="status" aria-live="polite">
		<div class="row">
			<strong>{t('capture.passOf', { n: passNo })}</strong>
			<span>
				{#if !online}<span class="offline">{t('capture.offline')}</span>{/if}
				{queue.queued > 0 ? t('capture.queued', { n: queue.queued }) : t('capture.allUploaded')}
			</span>
		</div>
		<div class="row">
			<span class="route">{pass?.routeName || routeName}</span>
			<span class="num">
				{#if gpsDenied}{t('capture.gpsOff')}{:else if fixFresh && fix}{t('capture.gps', { m: fix.accuracy })}{:else}{t(
						'capture.gpsWaiting'
					)}{/if}
			</span>
		</div>
	</header>

	{#if pass?.endedAt}
		<section class="summary">
			<h1>{t('capture.ended', { n: passNo, count: queue.queued + queue.uploaded })}</h1>
			<p class="num big">{pass.dogs === 1 ? t('capture.dogsOne') : t('capture.dogs', { n: pass.dogs })}</p>
			{#if queue.queued > 0}
				<p>{t('capture.queued', { n: queue.queued })}. {t('capture.keepClose')}</p>
			{:else}
				<p>{t('capture.allUploaded')}.</p>
			{/if}
			{#if queue.rejected > 0}<p class="error">{t('capture.rejected', { n: queue.rejected })}</p>{/if}
			<a class="btn" href="/app/survey/{surveyId}">{t('nav.home')}</a>
		</section>
	{:else}
		<div class="viewfinder">
			<video bind:this={video} playsinline muted autoplay aria-hidden="true"></video>
			{#if cameraFailed}
				<p class="camera-failed">{t('capture.noCamera')}</p>
			{/if}
			{#if flash}<div class="flash"></div>{/if}
		</div>

		<section class="controls">
			<ol class="steps" aria-label={t('capture.shutter')}>
				<li class:current={pass?.nextShot !== 'head'}>
					<span class="step-name">{t('capture.sideShot')}</span>
					<span class="step-hint">{t('capture.stepSide')}</span>
				</li>
				<li class:current={pass?.nextShot === 'head'}>
					<span class="step-name">{t('capture.headShot')}</span>
					<span class="step-hint">{t('capture.stepHead')}</span>
				</li>
			</ol>

			<p class="count num" aria-live="polite">
				{pass?.dogs === 1 ? t('capture.dogsOne') : t('capture.dogs', { n: pass?.dogs ?? 0 })}
			</p>
			{#if notice}<p class="notice" role="status">{notice}</p>{/if}
			{#if gpsDenied}<p class="notice">{t('capture.gpsDenied')}</p>{/if}
			{#if !gpsDenied && !fixFresh && now - (pass ? Date.parse(pass.startedAt) : now) > 30_000}
				<p class="notice">{t('capture.gpsNone')}</p>
			{/if}

			<div class="shutter-row">
				<button class="side-action" onclick={() => (confirmingEnd = true)}>{t('capture.endPass')}</button>
				<button
					class="shutter"
					onclick={shoot}
					disabled={busy || !pass}
					aria-label={t('capture.shutter')}
					data-testid="shutter"
				>
					<span class="shutter-ring"></span>
				</button>
				{#if canUndo}
					<button class="side-action" onclick={undo}>{t('capture.undo')}</button>
				{:else if pass?.nextShot === 'head'}
					<button class="side-action" onclick={skipHead}>{t('capture.skipHead')}</button>
				{:else}
					<span class="side-action placeholder"></span>
				{/if}
			</div>

			{#if cameraFailed}
				<button class="btn quiet wide" onclick={() => fileInput?.click()}>{t('capture.useFile')}</button>
			{/if}
		</section>
	{/if}

	<input
		bind:this={fileInput}
		class="visually-hidden"
		type="file"
		accept="image/jpeg,image/*"
		capture="environment"
		tabindex="-1"
		aria-hidden="true"
		onchange={fromFile}
	/>

	{#if confirmingEnd}
		<div class="sheet" role="dialog" aria-modal="true" aria-labelledby="end-title">
			<p id="end-title">{t('capture.endConfirm', { n: passNo })}</p>
			<button class="btn wide" onclick={endPass}>{t('capture.endYes')}</button>
			<button class="btn quiet wide" onclick={() => (confirmingEnd = false)}>{t('capture.endNo')}</button>
		</div>
	{/if}
</div>

<style>
	.capture {
		position: fixed;
		inset: 0;
		display: grid;
		grid-template-rows: auto 1fr auto;
		background: var(--limewash);
		padding-bottom: env(safe-area-inset-bottom);
	}
	.capture.ended {
		grid-template-rows: auto 1fr;
	}
	.status {
		padding: calc(var(--space-2) + env(safe-area-inset-top)) var(--space-4) var(--space-2);
		background: var(--limewash);
		color: var(--ink);
		font-size: var(--step-0);
		line-height: 1.3;
	}
	.row {
		display: flex;
		justify-content: space-between;
		gap: var(--space-3);
	}
	.route {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.offline {
		background: var(--sodium);
		color: var(--ink);
		font-weight: 600;
		padding: 0 var(--space-2);
		border-radius: 4px;
		margin-right: var(--space-2);
	}
	.viewfinder {
		position: relative;
		background: var(--ink);
		overflow: hidden;
		min-height: 0;
	}
	video {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.camera-failed {
		position: absolute;
		inset: auto var(--space-4) var(--space-4);
		color: #fff;
		margin: 0;
	}
	.flash {
		position: absolute;
		inset: 0;
		background: #fff;
		opacity: 0.7;
		animation: flash 140ms ease-out forwards;
	}
	@keyframes flash {
		to {
			opacity: 0;
		}
	}
	.controls {
		padding: var(--space-3) var(--space-4) var(--space-4);
		display: grid;
		gap: var(--space-2);
	}
	.steps {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--space-2);
	}
	.steps li {
		display: grid;
		padding: var(--space-2) var(--space-3);
		border: 2px solid var(--rule);
		border-radius: var(--radius-control);
		color: var(--fog-text);
	}
	.steps li.current {
		border-color: var(--ink);
		background: #fff;
		color: var(--ink);
	}
	.step-name {
		font-weight: 600;
	}
	.step-hint {
		font-size: 0.94rem;
	}
	.count {
		margin: 0;
		font-size: var(--step-2);
		font-weight: 600;
	}
	.notice {
		margin: 0;
		color: var(--ink);
		background: var(--sodium-wash);
		padding: var(--space-2) var(--space-3);
	}
	.shutter-row {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: center;
		gap: var(--space-3);
	}
	.side-action {
		min-height: var(--target);
		background: none;
		border: 2px solid var(--ink);
		border-radius: var(--radius-control);
		padding: 0 var(--space-3);
		font-weight: 600;
		cursor: pointer;
	}
	.side-action:last-child {
		justify-self: end;
	}
	.side-action.placeholder {
		border: 0;
	}
	.shutter {
		width: var(--shutter);
		height: var(--shutter);
		border-radius: 50%;
		background: var(--ink);
		border: 0;
		display: grid;
		place-items: center;
		cursor: pointer;
		touch-action: manipulation;
	}
	.shutter:active {
		transform: scale(0.95);
	}
	.shutter[disabled] {
		opacity: 0.6;
	}
	.shutter-ring {
		width: 60px;
		height: 60px;
		border-radius: 50%;
		border: 3px solid var(--limewash);
	}
	.summary {
		padding: var(--space-6) var(--space-4);
		max-width: 32rem;
	}
	.big {
		font-size: var(--step-3);
	}
	.sheet {
		position: fixed;
		inset: auto 0 0 0;
		background: #fff;
		padding: var(--space-5) var(--space-4) calc(var(--space-5) + env(safe-area-inset-bottom));
		display: grid;
		gap: var(--space-3);
		border-top: 2px solid var(--ink);
	}
	.sheet p {
		font-size: var(--step-1);
		margin: 0 0 var(--space-2);
	}
</style>

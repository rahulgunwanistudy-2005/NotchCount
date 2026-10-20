/**
 * Offline-first capture queue in IndexedDB. A photo is written here before anything else, so
 * closing the app, losing signal or a dead battery never loses a capture. The sync loop
 * uploads in order and is safe to run any number of times: every server call is idempotent.
 */
import { openDB, type DBSchema, type IDBPDatabase } from 'idb';
import { api, ApiError } from './api';
import type { Pass, PhotoOut, Shot } from './types';

/** A capture can be undone for this long before it becomes eligible to upload. */
export const UNDO_WINDOW_MS = 8000;

export interface LocalPass {
	key: string;
	surveyId: string;
	passNo: number;
	routeName: string;
	startedAt: string;
	endedAt: string | null;
	serverId: string | null;
	endSynced: boolean;
	dogs: number;
	nextShot: Shot;
	error: string | null;
}

export type PhotoStatus = 'queued' | 'uploaded' | 'rejected';

export interface LocalPhoto {
	id: string;
	passKey: string;
	blob: Blob | null;
	sha256: string;
	takenAt: string;
	readyAt: number;
	lat: number | null;
	lon: number | null;
	accuracy: number | null;
	heading: number | null;
	shot: Shot;
	dog: number;
	status: PhotoStatus;
	error: string | null;
	flags: string[];
}

interface Schema extends DBSchema {
	passes: { key: string; value: LocalPass };
	photos: { key: string; value: LocalPhoto; indexes: { byPass: string; byStatus: PhotoStatus } };
}

let dbPromise: Promise<IDBPDatabase<Schema>> | null = null;

export function db(): Promise<IDBPDatabase<Schema>> {
	dbPromise ??= openDB<Schema>('notchcount', 1, {
		upgrade(d) {
			d.createObjectStore('passes', { keyPath: 'key' });
			const photos = d.createObjectStore('photos', { keyPath: 'id' });
			photos.createIndex('byPass', 'passKey');
			photos.createIndex('byStatus', 'status');
		}
	});
	return dbPromise;
}

export const passKey = (surveyId: string, passNo: number) => `${surveyId}:${passNo}`;

export async function getPass(key: string): Promise<LocalPass | undefined> {
	return (await db()).get('passes', key);
}

export async function startLocalPass(surveyId: string, passNo: number, routeName: string): Promise<LocalPass> {
	const key = passKey(surveyId, passNo);
	const existing = await getPass(key);
	if (existing) return existing;
	const pass: LocalPass = {
		key,
		surveyId,
		passNo,
		routeName,
		startedAt: new Date().toISOString(),
		endedAt: null,
		serverId: null,
		endSynced: false,
		dogs: 0,
		nextShot: 'side',
		error: null
	};
	await (await db()).put('passes', pass);
	return pass;
}

export async function savePass(pass: LocalPass): Promise<void> {
	await (await db()).put('passes', pass);
}

export async function endLocalPass(key: string): Promise<LocalPass | undefined> {
	const pass = await getPass(key);
	if (!pass || pass.endedAt) return pass;
	pass.endedAt = new Date().toISOString();
	await savePass(pass);
	return pass;
}

export async function addPhoto(photo: Omit<LocalPhoto, 'status' | 'error' | 'flags' | 'readyAt'>): Promise<LocalPhoto> {
	const full: LocalPhoto = {
		...photo,
		readyAt: Date.parse(photo.takenAt) + UNDO_WINDOW_MS,
		status: 'queued',
		error: null,
		flags: []
	};
	await (await db()).put('photos', full);
	return full;
}

/** Remove a capture that has not reached the server yet. Returns false if it already uploaded. */
export async function undoPhoto(id: string): Promise<boolean> {
	const d = await db();
	const photo = await d.get('photos', id);
	if (!photo || photo.status !== 'queued') return false;
	await d.delete('photos', id);
	return true;
}

export async function photosFor(key: string): Promise<LocalPhoto[]> {
	const list = await (await db()).getAllFromIndex('photos', 'byPass', key);
	return list.sort((a, b) => a.takenAt.localeCompare(b.takenAt));
}

export interface QueueCounts {
	queued: number;
	uploaded: number;
	rejected: number;
}

export async function counts(key?: string): Promise<QueueCounts> {
	const d = await db();
	const all = key ? await d.getAllFromIndex('photos', 'byPass', key) : await d.getAll('photos');
	const c: QueueCounts = { queued: 0, uploaded: 0, rejected: 0 };
	for (const p of all) c[p.status] += 1;
	return c;
}

function isFinalRejection(err: unknown): err is ApiError {
	return err instanceof ApiError && !err.retryable && err.status !== 401;
}

async function syncPass(pass: LocalPass, now: number): Promise<void> {
	const d = await db();
	if (!pass.serverId) {
		const remote = await api.post<Pass>(`/surveys/${pass.surveyId}/passes`, {
			pass_no: pass.passNo,
			started_at: pass.startedAt
		});
		pass.serverId = remote.id;
		pass.error = null;
		await savePass(pass);
	}
	for (const photo of await photosFor(pass.key)) {
		if (photo.status !== 'queued' || photo.readyAt > now || !photo.blob) continue;
		const form = new FormData();
		form.set('file', photo.blob, `${photo.id}.jpg`);
		form.set('sha256', photo.sha256);
		form.set('taken_at', photo.takenAt);
		form.set('shot', photo.shot);
		if (photo.lat !== null && photo.lon !== null) {
			form.set('lat', String(photo.lat));
			form.set('lon', String(photo.lon));
		}
		if (photo.accuracy !== null) form.set('accuracy_m', String(photo.accuracy));
		if (photo.heading !== null && Number.isFinite(photo.heading)) form.set('heading', String(photo.heading));
		try {
			const out = await api.post<PhotoOut>(`/passes/${pass.serverId}/photos`, form);
			photo.status = 'uploaded';
			photo.flags = out.flags;
			photo.blob = null;
			photo.error = null;
		} catch (err) {
			if (!isFinalRejection(err)) throw err;
			photo.status = 'rejected';
			photo.error = err.message;
		}
		await d.put('photos', photo);
	}
	if (pass.endedAt && !pass.endSynced) {
		const pending = (await photosFor(pass.key)).some((p) => p.status === 'queued');
		if (!pending) {
			await api.post<Pass>(`/passes/${pass.serverId}/end`, { ended_at: pass.endedAt });
			pass.endSynced = true;
			await savePass(pass);
		}
	}
}

let running: Promise<SyncResult> | null = null;

export interface SyncResult {
	ok: boolean;
	message: string | null;
}

/** Upload everything that is ready. Concurrent calls share one run. */
export function sync(): Promise<SyncResult> {
	running ??= (async (): Promise<SyncResult> => {
		try {
			const passes = await (await db()).getAll('passes');
			for (const pass of passes) {
				try {
					await syncPass(pass, Date.now());
				} catch (err) {
					if (isFinalRejection(err)) {
						pass.error = err.message;
						await savePass(pass);
						continue;
					}
					return { ok: false, message: err instanceof Error ? err.message : String(err) };
				}
			}
			return { ok: true, message: null };
		} finally {
			running = null;
		}
	})();
	return running;
}

/** Ask the browser not to evict queued photos when storage runs low. */
export async function requestPersistence(): Promise<boolean> {
	if (!navigator.storage?.persist) return false;
	if (await navigator.storage.persisted()) return true;
	return navigator.storage.persist();
}

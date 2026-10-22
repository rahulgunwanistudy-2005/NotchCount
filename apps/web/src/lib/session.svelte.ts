import { api, ApiError } from './api';
import { recall, remember } from './cache';
import type { Me } from './types';

export const session = $state<{
	me: Me | null;
	offline: boolean;
	signedOut: boolean;
	loaded: boolean;
	/** The server can send email sign-in codes (MojoAuth key set). */
	emailCode: boolean;
}>({
	me: recall<Me>('me'),
	offline: false,
	signedOut: false,
	loaded: false,
	emailCode: false
});

export async function loadMethods(): Promise<void> {
	try {
		session.emailCode = (await api.get<{ email_code: boolean }>('/auth/methods')).email_code;
	} catch {
		session.emailCode = false;
	}
}

export async function loadMe(): Promise<void> {
	try {
		session.me = remember('me', await api.get<Me>('/me'));
		session.offline = false;
		session.signedOut = false;
	} catch (err) {
		if (err instanceof ApiError && err.status === 401) {
			session.signedOut = true;
			session.me = null;
		} else {
			session.offline = true;
		}
	} finally {
		session.loaded = true;
	}
}

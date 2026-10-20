/** Thin client for /api/v1. Every mutation carries the CSRF header the API requires. */

export class ApiError extends Error {
	constructor(
		readonly status: number,
		message: string
	) {
		super(message);
	}

	/** Errors worth retrying later (offline, server busy) rather than showing as final. */
	get retryable(): boolean {
		return this.status === 0 || this.status === 429 || this.status >= 500;
	}
}

const BASE = '/api/v1';

async function request<T>(method: string, path: string, body?: BodyInit | object): Promise<T> {
	const headers: Record<string, string> = { 'x-notchcount': '1' };
	let payload: BodyInit | undefined;
	if (body instanceof FormData) {
		payload = body;
	} else if (body !== undefined) {
		headers['content-type'] = 'application/json';
		payload = JSON.stringify(body);
	}
	let res: Response;
	try {
		res = await fetch(BASE + path, { method, headers, body: payload, credentials: 'same-origin' });
	} catch {
		throw new ApiError(0, 'No connection. Your photos are saved on this phone and will upload later.');
	}
	if (res.status === 204) return undefined as T;
	const text = await res.text();
	const data = text ? safeJson(text) : null;
	if (!res.ok) {
		throw new ApiError(res.status, detailOf(data) ?? `Request failed (${res.status}).`);
	}
	return data as T;
}

function safeJson(text: string): unknown {
	try {
		return JSON.parse(text);
	} catch {
		return null;
	}
}

function detailOf(data: unknown): string | null {
	if (data && typeof data === 'object' && 'detail' in data) {
		const d = (data as { detail: unknown }).detail;
		if (typeof d === 'string') return d;
		if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg);
	}
	return null;
}

export const api = {
	get: <T>(path: string) => request<T>('GET', path),
	post: <T>(path: string, body?: BodyInit | object) => request<T>('POST', path, body ?? {})
};

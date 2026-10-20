/** Small read-through cache in localStorage so field screens open without signal. */
export function remember<T>(key: string, value: T): T {
	try {
		localStorage.setItem(`nc.cache.${key}`, JSON.stringify(value));
	} catch {
		/* storage full or blocked: the screen still works online */
	}
	return value;
}

export function recall<T>(key: string): T | null {
	try {
		const raw = localStorage.getItem(`nc.cache.${key}`);
		return raw ? (JSON.parse(raw) as T) : null;
	} catch {
		return null;
	}
}

export function forgetAll(): void {
	try {
		for (const k of Object.keys(localStorage)) if (k.startsWith('nc.cache.')) localStorage.removeItem(k);
	} catch {
		/* nothing cached */
	}
}

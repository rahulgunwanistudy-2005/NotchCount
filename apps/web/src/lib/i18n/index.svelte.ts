import { en, type MessageKey } from './en';
import { hi, REVIEWED } from './hi';

export type Lang = 'en' | 'hi';

export const hindiAvailable = REVIEWED;

const stored = typeof localStorage !== 'undefined' ? safeRead() : null;
export const locale = $state<{ lang: Lang }>({ lang: hindiAvailable && stored === 'hi' ? 'hi' : 'en' });

function safeRead(): string | null {
	try {
		return localStorage.getItem('nc.lang');
	} catch {
		return null;
	}
}

export function setLang(lang: Lang): void {
	locale.lang = hindiAvailable ? lang : 'en';
	try {
		localStorage.setItem('nc.lang', locale.lang);
	} catch {
		/* private mode: the choice lasts for this visit only */
	}
}

export function t(key: MessageKey, vars: Record<string, string | number> = {}): string {
	const template = (locale.lang === 'hi' && hi[key]) || en[key];
	return template.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? `{${name}}`));
}

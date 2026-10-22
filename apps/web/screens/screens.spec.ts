import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { writeFileSync } from 'node:fs';

/**
 * Full-page screenshots of every screen at phone and desktop width, from real data, with an
 * overflow check and an axe audit per screen.
 *
 * SCREENS_OUT picks the folder (default docs/screens); SCREENS_ONLY limits to some screens by name,
 * for example "home,survey". The capture screen opens a new pass, so it runs only with
 * SCREENS_CAPTURE=1.
 */
const out = process.env.SCREENS_OUT ?? '../../docs/screens';
const only = process.env.SCREENS_ONLY?.split(',').map((s) => s.trim());
const audit: Record<string, { overflowPx: number; serious: string[] }> = {};
const env = (k: string) => {
	const v = process.env[k];
	if (!v) throw new Error(`set ${k}`);
	return v;
};

const sizes = [
	{ name: '375', width: 375, height: 812 },
	{ name: '1280', width: 1280, height: 900 }
].filter((s) => !process.env.SCREENS_SIZES || process.env.SCREENS_SIZES.split(',').includes(s.name));

const wanted = (name: string) => !only || only.includes(name);

async function shot(page: Page, name: string, size: string, path: string, waitFor?: string) {
	if (!wanted(name)) return;
	const file = `${name}-${size}.png`;
	await page.goto(path);
	if (waitFor)
		await page.getByText(waitFor, { exact: false }).filter({ visible: true }).first().waitFor({ timeout: 60_000 });
	// Full-page shots include what is below the fold, so load lazy images now.
	await page.evaluate(() => document.querySelectorAll('img[loading="lazy"]').forEach((i) => ((i as HTMLImageElement).loading = 'eager')));
	// Photos come through signed links from the database; wait until every image has loaded.
	await page.waitForFunction(() => [...document.images].every((i) => i.complete && i.naturalWidth > 0), null, {
		timeout: 60_000
	});
	await page.evaluate(() => Promise.all([...document.images].map((i) => i.decode().catch(() => undefined))));
	await page.waitForTimeout(Number(process.env.SCREENS_SETTLE_MS ?? 6000)); // strip animation and image paint
	await page.screenshot({ path: `${out}/${file}`, fullPage: true, animations: 'disabled' });
	const overflowPx = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
	const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
	const serious = axe.violations
		.filter((v) => v.impact === 'serious' || v.impact === 'critical')
		.map((v) => `${v.id}: ${v.nodes.length} node(s): ${v.nodes[0]?.target.join(' ')}`);
	audit[file] = { overflowPx, serious };
	expect.soft(overflowPx, `${file} scrolls sideways`).toBeLessThanOrEqual(0);
	expect.soft(serious, `${file} accessibility`).toEqual([]);
}

for (const size of sizes) {
	test(`screens at ${size.name}px`, async ({ browser }) => {
		const ctx = await browser.newContext({ viewport: { width: size.width, height: size.height } });
		const page = await ctx.newPage();
		const survey = env('SCREENS_SURVEY');
		const s = size.name;
		await shot(page, 'landing', s, '/', 'Count the dogs');
		if (process.env.SCREENS_SLUG) await shot(page, 'report', s, `/r/${process.env.SCREENS_SLUG}`, 'dogs use this route');
		await shot(page, 'signed-out', s, '/app', 'Sign in with your team link');
		const signedIn = ['home', 'survey', 'label-pairs', 'label-ears', 'review', 'case', 'team', 'field-card', 'health', 'capture'];
		if (!signedIn.some(wanted)) {
			writeFileSync(`${out}/audit-${s}.json`, JSON.stringify(audit, null, 1));
			return; // sign-in codes are one-use: do not spend one for public screens only
		}
		await page.goto(`/join#${env(s === '375' ? 'SCREENS_INVITE_A' : 'SCREENS_INVITE_B')}`);
		await page.waitForURL('**/app');
		await shot(page, 'home', s, '/app', 'Hello');
		await shot(page, 'survey', s, `/app/survey/${survey}`, 'dogs use this route');
		await shot(page, 'label-pairs', s, `/app/survey/${survey}/check/pairs`, 'Same dog');
		await shot(page, 'label-ears', s, `/app/survey/${survey}/check/ears`, 'Notched');
		await shot(page, 'review', s, `/app/survey/${survey}/check/review`, 'Review queue');
		await shot(page, 'case', s, `/app/survey/${survey}/case`, 'Case file');
		await shot(page, 'team', s, `/app/team/${env('SCREENS_TEAM')}`, 'People');
		await shot(page, 'field-card', s, '/app/protocol', 'Field card');
		await shot(page, 'health', s, '/app/health', 'System health');
		if (s === '375' && process.env.SCREENS_CAPTURE === '1') {
			await shot(page, 'capture', s, `/app/capture/${survey}/3`, 'dogs this pass');
		}
		await ctx.close();
		writeFileSync(`${out}/audit-${s}.json`, JSON.stringify(audit, null, 1));
	});
}

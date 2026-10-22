import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { writeFileSync } from 'node:fs';

const audit: Record<string, { overflowPx: number; serious: string[] }> = {};

/** Full-page screenshots of every screen at phone and desktop width, from real data. */
const out = '../../docs/screens';
const env = (k: string) => {
	const v = process.env[k];
	if (!v) throw new Error(`set ${k}`);
	return v;
};

const sizes = [
	{ name: '375', width: 375, height: 812 },
	{ name: '1280', width: 1280, height: 900 }
];

async function shot(page: Page, path: string, file: string, waitFor?: string) {
	await page.goto(path);
	if (waitFor) await page.getByText(waitFor, { exact: false }).first().waitFor({ timeout: 60_000 });
	// Photos come through signed links from the database; wait until every image has loaded.
	await page.waitForFunction(() => [...document.images].every((i) => i.complete && i.naturalWidth > 0), null, {
		timeout: 60_000
	});
	await page.evaluate(() => Promise.all([...document.images].map((i) => i.decode().catch(() => undefined))));
	await page.waitForTimeout(6000); // route-strip animation (2.5 s) and headless image paint
	await page.screenshot({ path: `${out}/${file}`, fullPage: true, animations: 'disabled' });
	const overflowPx = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
	const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
	const serious = axe.violations
		.filter((v) => v.impact === 'serious' || v.impact === 'critical')
		.map((v) => `${v.id}: ${v.nodes.length} node(s)`);
	audit[file] = { overflowPx, serious };
	expect.soft(overflowPx, `${file} scrolls sideways`).toBeLessThanOrEqual(0);
	expect.soft(serious, `${file} accessibility`).toEqual([]);
}

for (const size of sizes) {
	test(`screens at ${size.name}px`, async ({ browser }) => {
		const ctx = await browser.newContext({ viewport: { width: size.width, height: size.height } });
		const page = await ctx.newPage();
		const survey = env('SCREENS_SURVEY');
		const slug = env('SCREENS_SLUG');
		await shot(page, '/', `landing-${size.name}.png`, 'Count the dogs');
		await shot(page, `/r/${slug}`, `report-${size.name}.png`, 'dogs use this route');
		await page.goto(`/join#${env(size.name === '375' ? 'SCREENS_INVITE_A' : 'SCREENS_INVITE_B')}`);
		await page.waitForURL('**/app');
		await shot(page, '/app', `home-${size.name}.png`, 'Demo survey');
		await shot(page, `/app/survey/${survey}`, `survey-${size.name}.png`, 'dogs use this route');
		await shot(page, `/app/survey/${survey}/check/pairs`, `label-pairs-${size.name}.png`, 'Same dog');
		await shot(page, `/app/survey/${survey}/check/ears`, `label-ears-${size.name}.png`, 'Notched');
		await shot(page, `/app/survey/${survey}/check/review`, `review-${size.name}.png`, 'Review queue');
		await shot(page, `/app/survey/${survey}/case`, `case-${size.name}.png`, 'Case file');
		await shot(page, `/app/team/${env('SCREENS_TEAM')}`, `team-${size.name}.png`, 'People');
		await shot(page, '/app/protocol', `field-card-${size.name}.png`, 'Field card');
		if (size.name === '375') {
			await shot(page, `/app/capture/${survey}/3`, `capture-${size.name}.png`, 'dogs this pass');
		}
		await ctx.close();
		writeFileSync(`${out}/audit-${size.name}.json`, JSON.stringify(audit, null, 1));
	});
}

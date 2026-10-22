import { expect, test, type Page, type Route } from '@playwright/test';

/** Synthetic fixtures: the shapes the API returns, with made-up values. */
const PNG = Buffer.from(
	'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
	'base64'
);
const ME = { id: 'u1', display_name: 'Asha', teams: [{ id: 't1', name: 'Gali 4', city: 'Delhi', role: 'admin' }] };
const crop = (id: string, pass_no: number) => ({
	detection_id: id,
	url: `/api/v1/blobs/crops/${id}.jpg`,
	pass_no,
	taken_at: '2026-10-20T01:05:00Z',
	view: 'side',
	quality: 0.9
});
const PAIR = {
	kind: 'pair',
	pair_id: 'p1',
	a: crop('d1', 1),
	b: crop('d2', 2),
	p_same: 0.62,
	calibrated: true,
	route_m: 40,
	minutes_apart: 1440,
	remaining: 1
};
const REPORT = {
	slug: 'abc123',
	title: 'Street dogs on Gali 4',
	team: 'Gali 4 team',
	city: 'Delhi',
	route_name: 'Gali 4 loop',
	headline: {
		population: 'About 61 dogs use this route (56 to 74).',
		share: '59% are sterilised (45% to 72%).',
		deficit: 'Reaching 70% needs about 7 more sterilisations (0 to 16).',
		note: null
	},
	method: 'two_pass_sampled_chapman',
	method_lines: ['Line one.', 'Line two.', 'Dogs seen on walk 1: 40. On walk 2: 38. Seen on both: 25.'],
	assumptions: ['Same population on both mornings.'],
	results: {
		counts: { n1: 40, n2: 38, m2: 25, distinct: 53 },
		population: { median: 61, low: 56, high: 74 },
		share: { median: 0.59, low: 0.45, high: 0.72 },
		comparability_problems: []
	},
	code_version: 'notchcount_stats 0.1.0',
	data_hash: 'f00dfeedbeef',
	seed: 7,
	computed_at: '2026-10-21T03:00:00Z',
	strip: [
		{ passes: [1, 2], status: 'notched' },
		{ passes: [1], status: 'not_notched' },
		{ passes: [2], status: 'not_visible' }
	]
};

async function mockApi(page: Page, extra: (route: Route, path: string) => Promise<boolean> | boolean = () => false) {
	await page.route('**/api/v1/**', async (route) => {
		const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
		if (await extra(route, path)) return;
		if (path === '/me') return route.fulfill({ json: ME });
		if (path.startsWith('/blobs/')) return route.fulfill({ body: PNG, contentType: 'image/png' });
		if (path === `/reports/${REPORT.slug}`) return route.fulfill({ json: REPORT });
		if (path.startsWith('/surveys/')) return route.fulfill({ status: 404, json: { detail: 'Not found.' } });
		return route.fulfill({ json: [] });
	});
}

test('public report shows every number with its range and no dog locations', async ({ page }) => {
	await mockApi(page);
	await page.goto(`/r/${REPORT.slug}`);
	await expect(page.getByRole('heading', { name: 'Street dogs on Gali 4' })).toBeVisible();
	await expect(page.getByText('About 61 dogs use this route (56 to 74).')).toBeVisible();
	await expect(page.getByText('59% are sterilised (45% to 72%).')).toBeVisible();
	await expect(page.getByRole('img', { name: /Range of the dog count: 56 to 74/ })).toBeVisible();
	await expect(page.getByText('Dots are not placed where the dogs were seen.')).toBeVisible();
	await expect(page.getByRole('link', { name: 'Download PDF' })).toHaveAttribute('href', '/api/v1/reports/abc123.pdf');
});

test('review: the S key records "same dog" and moves on', async ({ page }) => {
	const posted: unknown[] = [];
	let served = false;
	await mockApi(page, async (route, path) => {
		if (path === '/surveys/s1/labeling/pairs') {
			const body = served ? null : PAIR;
			served = true;
			await route.fulfill({ json: body });
			return true;
		}
		if (path === '/labels/pairs') {
			expect(route.request().headers()['x-notchcount']).toBe('1');
			posted.push(route.request().postDataJSON());
			await route.fulfill({ status: 204 });
			return true;
		}
		return false;
	});
	await page.goto('/app/survey/s1/check/pairs');
	await expect(page.getByRole('button', { name: /Same dog/ })).toBeVisible();
	await expect(page.getByText('40 m apart along the route')).toBeVisible();
	await page.keyboard.press('s');
	await expect(page.getByText('Nothing left to check. Thank you.')).toBeVisible();
	expect(posted).toEqual([{ pair_id: 'p1', decision: 'same' }]);
});

test('signed-out visitors see how to sign in, and can still read the field card', async ({ page }) => {
	await mockApi(page, async (route, path) => {
		if (path !== '/me') return false;
		await route.fulfill({ status: 401, json: { detail: 'Sign in first.' } });
		return true;
	});
	await page.goto('/app');
	await expect(page.getByRole('heading', { name: 'Sign in with your team link' })).toBeVisible();
	await page.goto('/app/protocol');
	await expect(page.getByRole('heading', { name: 'Field card' })).toBeVisible();
	await expect(page.getByText(/anti-rabies treatment/).first()).toBeVisible();
});

test('landing page leads to the app and the sample report', async ({ page }) => {
	await mockApi(page);
	await page.goto('/');
	await expect(page.getByRole('heading', { level: 1 })).toContainText('Count the dogs on your street');
	await expect(page.getByRole('link', { name: 'Open the app' })).toHaveAttribute('href', '/app');
	const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
	expect(overflow).toBeLessThanOrEqual(0);
});

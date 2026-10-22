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

test('landing page: the street simulator walks twice and gives an estimate with its range', async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await mockApi(page);
	await page.goto('/');
	await expect(page.getByRole('heading', { level: 1 })).toContainText('Count the dogs on your street');
	await expect(page.getByRole('link', { name: 'Try it on a street' })).toHaveAttribute('href', '#try');
	const sim = page.locator('.sim');
	await sim.getByRole('button', { name: 'Start walk 1' }).click();
	await sim.getByRole('button', { name: 'Walk again next morning' }).click();
	await expect(sim.getByText(/dogs live on this street \(/)).toBeVisible();
	await sim.getByRole('button', { name: 'Reveal the whole street' }).click();
	await expect(sim.getByText(/The truth: \d+ dogs/)).toBeVisible();
	const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
	expect(overflow).toBeLessThanOrEqual(0);
});

test('survey dashboard: the dog gallery filters and the share sits on the 70% dial', async ({ page }) => {
	const crops = ['01', '02', '03', '04', '06', '07', '08', '09'].map((n) => `/img/crops/dog-${n}.webp`);
	const DOGS = crops.map((src, i) => ({
		individual_id: `i${i}`,
		crop: { ...crop(`d${i}`, 1), url: src },
		passes: i % 3 === 0 ? [1] : [1, 2],
		sightings: 2,
		status: i % 2 ? 'notched' : 'not_notched',
		checked: i < 4
	}));
	const SURVEY = {
		id: 's1',
		team_id: 't1',
		name: 'October walk',
		status: 'open',
		start_window_local: '06:30:00',
		timezone: 'Asia/Kolkata',
		route: { id: 'r1', team_id: 't1', name: 'Gali 4 loop', corridor_m: 40, length_m: 1200, geometry: { type: 'LineString', coordinates: [] } },
		passes: [],
		public_slug: null
	};
	await mockApi(page, async (route, path) => {
		const json = {
			'/surveys/s1': SURVEY,
			'/surveys/s1/dogs': DOGS,
			'/surveys/s1/progress': {
				photos: { processed: 30 },
				detections: 28,
				usable_detections: 26,
				pairs: 60,
				pairs_labelled: 40,
				positive_labels: 12,
				ears_labelled: 20,
				review_pairs_left: 2,
				review_ears_left: 1,
				match_model: 'match-lr-test',
				notch_model: 'notch-lr-test'
			},
			'/surveys/s1/estimates': [
				{
					id: 'e1',
					survey_id: 's1',
					method: 'two_pass_sampled_chapman',
					status: 'done',
					params: {},
					results: {
						passes: [],
						sightings: 48,
						pairs: 60,
						decided_pairs: 40,
						match_model: [],
						comparability_problems: [],
						git: 'test',
						counts: REPORT.results.counts,
						population: REPORT.results.population,
						share: REPORT.results.share
					},
					error: null,
					data_hash: 'abc',
					code_version: 'test',
					seed: 1,
					created_at: '2026-10-21T03:00:00Z'
				}
			]
		}[path];
		if (json === undefined) return false;
		await route.fulfill({ json });
		return true;
	});
	await page.goto('/app/survey/s1');
	await expect(page.getByRole('heading', { name: 'Dogs on this route' })).toBeVisible();
	await expect(page.locator('li.tile')).toHaveCount(8);
	await page.getByRole('button', { name: /Notched \d/ }).click();
	await expect(page.locator('li.tile')).toHaveCount(4);
	await expect(page.getByRole('img', { name: /against the 70% target/ })).toBeVisible();
	if (process.env.UI_SHOTS) await page.screenshot({ path: `${process.env.UI_SHOTS}/dashboard.png`, fullPage: true });
});

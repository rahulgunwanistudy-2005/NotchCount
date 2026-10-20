import { execFileSync } from 'node:child_process';
import { expect, test } from '@playwright/test';

/** G1: three photos captured offline all arrive with their metadata after reconnecting. */
test('offline capture uploads after reconnect', async ({ page, context, request }) => {
	const seed = JSON.parse(
		execFileSync('uv', ['run', 'python', 'apps/web/e2e/seed.py'], {
			cwd: '../..',
			encoding: 'utf8',
			env: { ...process.env, NC_DB_SCHEMA: process.env.E2E_SCHEMA ?? 'notchcount_test' }
		})
	) as { invite: string; survey_id: string };

	await page.goto(`/join#${seed.invite}`);
	await expect(page).toHaveURL(/\/app$/);
	await page.goto(`/app/capture/${seed.survey_id}/1`);
	await expect(page.getByText('0 dogs this pass')).toBeVisible();
	await expect(page.getByText(/GPS ±\d+ m/)).toBeVisible();
	await page.waitForFunction(() => (document.querySelector('video') as HTMLVideoElement)?.videoWidth > 0);

	await context.setOffline(true);
	const shutter = page.getByTestId('shutter');
	for (let i = 0; i < 3; i++) {
		await shutter.click();
		await expect(shutter).toBeEnabled();
	}
	await expect(page.getByText('2 dogs this pass')).toBeVisible();
	await expect(page.getByText('3 waiting to upload')).toBeVisible();
	await expect(page.getByText('Offline')).toBeVisible();

	await context.setOffline(false);
	await expect(page.getByText('All uploaded')).toBeVisible({ timeout: 45_000 });

	const cookies = await context.cookies();
	const session = cookies.find((c) => c.name === 'nc_session');
	expect(session).toBeTruthy();
	const survey = await (
		await request.get(`/api/v1/surveys/${seed.survey_id}`, { headers: { cookie: `nc_session=${session!.value}` } })
	).json();
	expect(survey.passes).toHaveLength(1);
	expect(survey.passes[0].photo_count).toBe(3);
	expect(survey.passes[0].observer_name).toBe('E2E walker');
	const photos = await (
		await request.get(`/api/v1/passes/${survey.passes[0].id}/photos`, {
			headers: { cookie: `nc_session=${session!.value}` }
		})
	).json();
	expect(photos.map((p: { shot: string }) => p.shot)).toEqual(['side', 'head', 'side']);
	for (const p of photos) {
		expect(p.has_location).toBe(true);
		expect(p.accuracy_m).toBe(6);
		expect(p.flags).toEqual([]);
	}
});

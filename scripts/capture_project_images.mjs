// Capture the real capture UI with isolated test API responses; no production writes.
import { chromium, expect } from '../apps/web/node_modules/@playwright/test/index.mjs';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
const out = `${root}docs/project-images/screens`;
await mkdir(out, { recursive: true });
const browser = await chromium.launch({ headless: true, args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] });
try {
  const context = await browser.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 2,
    permissions: ['camera', 'geolocation'], geolocation: { latitude: 28.61355, longitude: 77.2112, accuracy: 6 }, serviceWorkers: 'block' });
  const page = await context.newPage();
  const uploaded = [];
  const crop = pass_no => ({ detection_id: `demo-dog-${pass_no}`, url: '/api/v1/demo-crop.jpg', pass_no, taken_at: '2026-10-20T01:05:00Z', view: 'side', quality: 1 });
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname.replace('/api/v1', '');
    if (path === '/me') return route.fulfill({ json: { id: 'demo-user', display_name: 'Demo walker', teams: [{ id: 'demo-team', name: 'Demo route', city: 'Delhi', role: 'admin' }] } });
    if (path === '/demo-crop.jpg') return route.fulfill({ body: await readFile(`${root}docs/project-images/evidence/dog-crop.jpg`), contentType: 'image/jpeg' });
    if (path === '/surveys/image-demo/labeling/pairs') return route.fulfill({ json: { kind: 'pair', pair_id: 'demo-pair', a: crop(1), b: crop(2), p_same: null, calibrated: false, route_m: 0, minutes_apart: 1440, remaining: 1 } });
    if (path === '/surveys/image-demo/labeling/ears') return route.fulfill({ json: { kind: 'ear', detection_id: 'demo-dog-1', crop: crop(1), p_notched: null, p_not_visible: null, remaining: 1 } });
    if (path === '/surveys/image-demo/passes') return route.fulfill({ json: { id: 'demo-pass', pass_no: 1 } });
    if (path === '/passes/demo-pass/photos') {
      uploaded.push({ contentType: route.request().headers()['content-type'], bytes: route.request().postDataBuffer()?.length });
      return route.fulfill({ json: { id: `photo-${uploaded.length}`, flags: [] } });
    }
    return route.fulfill({ json: [] });
  });
  await page.addInitScript(() => localStorage.setItem('nc.cache.survey.image-demo', JSON.stringify({ route: { name: 'Demo street loop' } })));
  await page.goto('http://127.0.0.1:4176/app/capture/image-demo/1');
  await page.waitForLoadState('networkidle');
  await expect(page.getByText('0 dogs this pass')).toBeVisible();
  await page.waitForFunction(() => document.querySelector('video')?.videoWidth > 0);
  await page.screenshot({ path: `${out}/capture-ready-375.png`, animations: 'disabled' });
  await context.setOffline(true);
  for (let i = 0; i < 3; i++) {
    await page.getByTestId('shutter').click();
    await expect(page.getByTestId('shutter')).toBeEnabled();
  }
  await expect(page.getByText('3 waiting to upload')).toBeVisible();
  await expect(page.getByText('Offline', { exact: true })).toBeVisible();
  await expect(page.getByText('2 dogs this pass')).toBeVisible();
  await page.screenshot({ path: `${out}/capture-offline-375.png`, animations: 'disabled' });
  await context.setOffline(false);
  await expect(page.getByText('All uploaded')).toBeVisible({ timeout: 45000 });
  if (uploaded.length !== 3) throw new Error(`Expected 3 uploads, got ${uploaded.length}`);
  await page.screenshot({ path: `${out}/capture-synced-375.png`, animations: 'disabled' });
  await writeFile(`${root}docs/project-images/capture-check.json`, JSON.stringify({ api: 'mocked, no production writes', camera: 'Chromium synthetic test signal', queuedOffline: 3, uploadedAfterReconnect: uploaded.length, uiDogCount: 2, note: 'Three shots alternate side / head / side, so the UI counts two dogs.' }, null, 2));
  for (const width of [375, 1280]) {
    await page.setViewportSize({ width, height: width === 375 ? 812 : 900 });
    for (const mode of ['pairs', 'ears']) {
      await page.goto(`http://127.0.0.1:4176/app/survey/image-demo/check/${mode}`);
      await page.waitForLoadState('networkidle');
      await expect(page.getByRole('button', { name: mode === 'pairs' ? /Same dog/ : /^Notched/ })).toBeVisible();
      await page.waitForFunction(() => [...document.images].every(i => i.complete && i.naturalWidth > 0));
      await page.screenshot({ path: `${out}/label-${mode}-demo-${width}.png`, fullPage: true, animations: 'disabled' });
    }
  }
  console.log('Captured ready, offline queue and reconnect; verified 3 uploads.');
  await context.close();
} finally { await browser.close(); }

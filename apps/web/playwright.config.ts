import { defineConfig, devices } from '@playwright/test';

// E2E_BASE_URL runs the same tests against a live deployment (seeded into E2E_SCHEMA).
const live = process.env.E2E_BASE_URL;

export default defineConfig({
	testDir: 'e2e',
	timeout: 90_000,
	retries: 0,
	use: {
		baseURL: live ?? 'http://localhost:8001',
		trace: 'retain-on-failure',
		...devices['Pixel 7'],
		permissions: ['camera', 'geolocation'],
		geolocation: { latitude: 28.6137, longitude: 77.2092, accuracy: 6 },
		launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] }
	},
	webServer: live
		? undefined
		: {
		command:
			'cd ../.. && NC_DB_SCHEMA=notchcount_test NC_PUBLIC_BASE_URL=http://localhost:8001 uv run uvicorn notchcount_api.main:app --port 8001',
		url: 'http://localhost:8001/healthz',
		reuseExistingServer: false,
		timeout: 60_000
	}
});

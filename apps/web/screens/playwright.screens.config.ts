import { defineConfig } from '@playwright/test';

// Captures docs/screens at 375 and 1280 px from a running deployment (see screens/screens.spec.ts).
export default defineConfig({
	testDir: '.',
	timeout: 900_000,
	use: {
		baseURL: process.env.SCREENS_BASE_URL,
		permissions: ['camera', 'geolocation'],
		geolocation: { latitude: 28.61355, longitude: 77.2112, accuracy: 6 },
		launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] }
	}
});

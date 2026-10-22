import { defineConfig } from '@playwright/test';

// Interface tests against the built site with the API mocked: no database, so they run in CI.
export default defineConfig({
	testDir: '.',
	timeout: 30_000,
	retries: 0,
	use: { baseURL: 'http://localhost:4174', trace: 'retain-on-failure' },
	webServer: {
		command: 'pnpm exec vite preview --port 4174 --strictPort',
		cwd: '..',
		url: 'http://localhost:4174',
		reuseExistingServer: false,
		timeout: 60_000
	}
});

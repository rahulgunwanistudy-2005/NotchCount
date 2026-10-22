import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		// NC_API_PROXY points the dev server at another API, for example the live one, to preview real data.
		proxy: { '/api': { target: process.env.NC_API_PROXY ?? 'http://127.0.0.1:8000', changeOrigin: true } }
	},
	test: {
		include: ['src/**/*.test.ts'],
		environment: 'node'
	}
});

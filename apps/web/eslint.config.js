import js from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';
import ts from 'typescript-eslint';
import svelteConfig from './svelte.config.js';

export default ts.config(
	js.configs.recommended,
	...ts.configs.recommended,
	...svelte.configs.recommended,
	{ languageOptions: { globals: { ...globals.browser, ...globals.node } } },
	{
		files: ['**/*.svelte', '**/*.svelte.ts'],
		languageOptions: { parserOptions: { projectService: true, extraFileExtensions: ['.svelte'], parser: ts.parser, svelteConfig } }
	},
	// The app is served at the site root with no `paths.base`, so resolve() would be a no-op.
	{ rules: { 'svelte/no-navigation-without-resolve': 'off' } },
	{ ignores: ['build/', '.svelte-kit/', 'test-results/', 'playwright-report/'] }
);

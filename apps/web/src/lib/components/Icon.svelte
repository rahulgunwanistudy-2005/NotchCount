<script lang="ts" module>
	export type IconName =
		| 'home'
		| 'card'
		| 'team'
		| 'survey'
		| 'pairs'
		| 'ear'
		| 'review'
		| 'case'
		| 'pulse'
		| 'user'
		| 'logout'
		| 'camera'
		| 'download'
		| 'warning'
		| 'globe'
		| 'menu';
</script>

<script lang="ts">
	/** Line icons, 1.6 px stroke. Always shown next to a text label, never alone on field screens. */
	let { name, size = 20 }: { name: IconName; size?: number } = $props();
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width="1.6"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
>
	{#if name === 'home'}
		<path d="M4 11l8-6 8 6v8a1 1 0 0 1-1 1h-4v-5h-6v5H5a1 1 0 0 1-1-1z" />
	{:else if name === 'card'}
		<rect x="5" y="3.5" width="14" height="17" rx="2" /><path d="M8.5 8h7M8.5 12h7M8.5 16h4" />
	{:else if name === 'team'}
		<circle cx="9" cy="9" r="3" /><circle cx="17" cy="10" r="2.3" /><path d="M3.5 19c.6-3 2.8-4.5 5.5-4.5s4.9 1.5 5.5 4.5M15 15c2.5-.3 4.7.9 5.3 3.5" />
	{:else if name === 'survey'}
		<path d="M4 18c3-1 4-5 7-5s3 3 5 3 3-2 4-4" /><circle cx="4" cy="18" r="1.4" /><circle cx="20" cy="12" r="1.4" /><path d="M8 6h8" />
	{:else if name === 'pairs'}
		<rect x="3" y="6" width="8" height="12" rx="2" /><rect x="13" y="6" width="8" height="12" rx="2" />
	{:else if name === 'ear'}
		<path d="M6 20V9c0-3 2-5 5-5l7 2-2 5 4 3-6 2-2 4z" /><path d="M14.5 6.5l-1.5 3 3 .5" />
	{:else if name === 'review'}
		<path d="M5 12.5l4 4 10-10" /><path d="M4 20h16" />
	{:else if name === 'case'}
		<rect x="3.5" y="5.5" width="17" height="13" rx="2" /><path d="M4 7l8 6 8-6" />
	{:else if name === 'pulse'}
		<path d="M3 12h4l2-5 4 10 2-5h6" />
	{:else if name === 'user'}
		<circle cx="12" cy="8.5" r="3.5" /><path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5" />
	{:else if name === 'logout'}
		<path d="M14 5h4a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-4M10 8l-4 4 4 4M6 12h9" />
	{:else if name === 'camera'}
		<path d="M4 8h3l1.5-2.5h7L17 8h3v11H4z" /><circle cx="12" cy="13" r="3.5" />
	{:else if name === 'download'}
		<path d="M12 4v11M7.5 10.5L12 15l4.5-4.5M5 19.5h14" />
	{:else if name === 'warning'}
		<path d="M12 4l9 16H3z" /><path d="M12 10v4.5M12 17.2v.3" />
	{:else if name === 'globe'}
		<circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h17M12 3.5c2.5 2.5 2.5 14.5 0 17M12 3.5c-2.5 2.5-2.5 14.5 0 17" />
	{:else if name === 'menu'}
		<path d="M4 7h16M4 12h16M4 17h16" />
	{/if}
</svg>

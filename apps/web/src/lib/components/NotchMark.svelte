<script lang="ts">
	/** The brand mark: a disc with the V an ABC vet cuts from a sterilised dog's ear. */
	let { size = 28, label = 'NotchCount' }: { size?: number; label?: string } = $props();
	const id = `notch-${Math.random().toString(36).slice(2, 8)}`;
</script>

<svg width={size} height={size} viewBox="0 0 24 24" role="img" aria-label={label}>
	<mask {id}>
		<rect width="24" height="24" fill="#fff" />
		<polygon points="0,0 0.4,6.4 8.4,8.4 6.4,0.4" fill="#000" />
	</mask>
	<circle cx="12" cy="12" r="11" fill="currentColor" mask="url(#{id})" />
</svg>

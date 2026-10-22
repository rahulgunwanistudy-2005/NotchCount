<script lang="ts">
	/**
	 * Round badge: the notch mark (a disc with the V a vet cuts from a sterilised dog's ear) inside a
	 * ring of lettering, after the circular wordmark in the team's visual reference.
	 */
	let { size = 96, label = 'NotchCount home' }: { size?: number; label?: string } = $props();
	const uid = `b${Math.random().toString(36).slice(2, 8)}`;
</script>

<svg width={size} height={size} viewBox="0 0 120 120" role="img" aria-label={label} class="badge">
	<defs>
		<path id="{uid}-top" d="M 18 60 A 42 42 0 0 1 102 60" />
		<path id="{uid}-bottom" d="M 14 60 A 46 46 0 0 0 106 60" />
		<mask id="{uid}-notch">
			<rect width="120" height="120" fill="#fff" />
			<polygon points="36,52 52,36 50.5,50.5" fill="#000" />
		</mask>
	</defs>
	<circle cx="60" cy="60" r="22" fill="var(--slate)" mask="url(#{uid}-notch)" />
	<text class="top"><textPath href="#{uid}-top" startOffset="50%" text-anchor="middle">notchcount</textPath></text>
	<text class="bottom"
		><textPath href="#{uid}-bottom" startOffset="50%" text-anchor="middle">street dog census</textPath></text
	>
	<circle cx="13" cy="62" r="1.8" fill="var(--ink)" />
	<circle cx="107" cy="62" r="1.8" fill="var(--ink)" />
</svg>

<style>
	.badge {
		display: block;
		overflow: visible;
	}
	text {
		font-family: var(--font-display);
		fill: var(--ink);
	}
	.top {
		font-size: 15px;
		font-weight: 800;
		letter-spacing: 0.12em;
	}
	.bottom {
		font-family: var(--font-body);
		font-size: 10px;
		letter-spacing: 0.22em;
	}
</style>

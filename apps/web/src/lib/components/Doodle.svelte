<script lang="ts">
	/**
	 * Hand-drawn shapes from the visual reference: a sage bean, moss loops, a fan of peach dashes,
	 * a scatter of dots. Decorative only: hidden from assistive tech, never carry meaning.
	 */
	let { shape, class: klass = '' }: { shape: 'bean' | 'loops' | 'dashes' | 'dots' | 'blob'; class?: string } =
		$props();
	const uid = `d${Math.random().toString(36).slice(2, 8)}`;
</script>

{#if shape === 'bean'}
	<svg class="doodle {klass}" viewBox="0 0 80 90" aria-hidden="true">
		<path
			d="M22 6c16-6 30 8 28 26-1 10 6 16 16 22 14 9 10 32-10 33-18 1-30-12-40-30C6 42 4 14 22 6z"
			fill="var(--sage-strong)"
		/>
	</svg>
{:else if shape === 'blob'}
	<svg class="doodle {klass}" viewBox="0 0 200 160" aria-hidden="true">
		<path
			d="M40 20c30-22 90-24 125 4 30 24 42 72 14 104-26 30-86 36-128 20C10 134-4 100 4 70 9 48 22 33 40 20z"
			fill="var(--sage)"
		/>
	</svg>
{:else if shape === 'loops'}
	<svg class="doodle {klass}" viewBox="0 0 200 200" aria-hidden="true">
		<path
			d="M2 40 C 10 200, 60 200, 52 60 C 46 -10, 30 40, 44 120 C 56 200, 110 210, 100 70 C 92 -10, 78 40, 92 130 C 102 196, 150 200, 150 90 C 150 10, 130 30, 146 120 C 158 180, 196 170, 198 60"
			fill="none"
			stroke="var(--moss)"
			stroke-width="2"
		/>
	</svg>
{:else if shape === 'dashes'}
	<svg class="doodle {klass}" viewBox="0 0 200 200" aria-hidden="true">
		<defs>
			<pattern id="{uid}-p" width="16" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(-24)">
				<line x1="2" y1="7" x2="11" y2="7" stroke="var(--peach)" stroke-width="2" stroke-linecap="round" />
			</pattern>
			<radialGradient id="{uid}-g">
				<stop offset="0.55" stop-color="#fff" />
				<stop offset="1" stop-color="#000" />
			</radialGradient>
			<mask id="{uid}-m"><circle cx="100" cy="100" r="98" fill="url(#{uid}-g)" /></mask>
		</defs>
		<circle cx="100" cy="100" r="98" fill="url(#{uid}-p)" mask="url(#{uid}-m)" />
	</svg>
{:else}
	<svg class="doodle {klass}" viewBox="0 0 60 50" aria-hidden="true">
		<g fill="var(--slate)">
			<circle cx="8" cy="20" r="3.5" /><circle cx="20" cy="10" r="2.5" /><circle cx="22" cy="28" r="4" />
			<circle cx="36" cy="16" r="2" /><circle cx="40" cy="36" r="3" /><circle cx="12" cy="40" r="2.2" />
		</g>
	</svg>
{/if}

<style>
	.doodle {
		position: absolute;
		pointer-events: none;
		display: block;
	}
</style>

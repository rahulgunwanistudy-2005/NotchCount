<script lang="ts">
	/**
	 * Every dog the last estimate found, one tile each, with its clearest photo. A tile gets the
	 * notch-cut corner only when a person confirmed that dog's ear is notched (DESIGN_BRIEF: the
	 * cut encodes state, never decoration).
	 */
	import type { Dog } from '$lib/types';

	let { dogs }: { dogs: Dog[] | null } = $props();

	type Filter = 'all' | 'both' | 'notched' | 'not_notched' | 'unknown';
	let filter = $state<Filter>('all');

	const counts = $derived({
		all: dogs?.length ?? 0,
		both: dogs?.filter((d) => d.passes.length > 1).length ?? 0,
		notched: dogs?.filter((d) => d.status === 'notched').length ?? 0,
		not_notched: dogs?.filter((d) => d.status === 'not_notched').length ?? 0,
		unknown: dogs?.filter((d) => d.status === 'not_visible' || d.status === 'unknown').length ?? 0
	});

	const shown = $derived(
		(dogs ?? []).filter((d) =>
			filter === 'all'
				? true
				: filter === 'both'
					? d.passes.length > 1
					: filter === 'unknown'
						? d.status === 'not_visible' || d.status === 'unknown'
						: d.status === filter
		)
	);

	const FILTERS: { key: Filter; label: string }[] = [
		{ key: 'all', label: 'All dogs' },
		{ key: 'both', label: 'Seen on both walks' },
		{ key: 'notched', label: 'Notched' },
		{ key: 'not_notched', label: 'Not notched' },
		{ key: 'unknown', label: 'Ear not seen' }
	];

	const statusLabel = (d: Dog) =>
		({
			notched: 'Notched',
			not_notched: 'Not notched',
			not_visible: 'Ear not visible',
			unknown: 'Ear not checked'
		})[d.status];
</script>

<div class="head">
	<div>
		<h2>Dogs on this route</h2>
		<p class="hint">
			One tile per dog, as the last estimate grouped the photos. A model's ear call is marked "model"; a cut corner
			means a person confirmed the notch.
		</p>
	</div>
	{#if dogs && dogs.length}
		<div class="filters" role="group" aria-label="Show">
			{#each FILTERS as f (f.key)}
				<button class="fchip" class:on={filter === f.key} aria-pressed={filter === f.key} onclick={() => (filter = f.key)}>
					{f.label} <span class="num">{counts[f.key]}</span>
				</button>
			{/each}
		</div>
	{/if}
</div>

{#if dogs === null}
	<p class="hint">Loading the dogs.</p>
{:else if dogs.length === 0}
	<p class="empty">No dogs yet. They appear here after the first estimate runs.</p>
{:else}
	<ul class="grid">
		{#each shown as d, i (d.individual_id)}
			<li class="tile" class:cut={d.status === 'notched' && d.checked} style="--i: {Math.min(i, 30)}">
				<img src={d.crop.url} alt="Dog {i + 1}, {statusLabel(d)}, seen on walk {d.passes.join(' and ')}" loading="lazy" />
				<div class="meta">
					<span class="walks">
						{#each [1, 2] as w (w)}
							<span class="walk" class:on={d.passes.includes(w)}>{w}</span>
						{/each}
					</span>
					<span class="ear {d.status}">
						{statusLabel(d)}{#if !d.checked && (d.status === 'notched' || d.status === 'not_notched')}<em>model</em>{/if}
					</span>
				</div>
			</li>
		{/each}
	</ul>
{/if}

<style>
	.head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-end;
		gap: var(--space-3) var(--space-5);
		margin-bottom: var(--space-4);
	}
	.head h2 {
		margin: 0 0 var(--space-1);
		font-size: var(--step-1);
	}
	.head .hint {
		margin: 0;
		max-width: 38rem;
	}
	.filters {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
	}
	.fchip {
		min-height: 36px;
		padding: 0 var(--space-3);
		border-radius: var(--radius-control);
		border: 1.5px solid var(--rule);
		background: var(--surface);
		color: var(--ink-soft);
		cursor: pointer;
		font-size: 0.88rem;
	}
	.fchip .num {
		font-weight: 600;
		margin-left: 2px;
	}
	.fchip.on {
		background: var(--slate);
		border-color: var(--slate);
		color: #fff;
	}
	.empty {
		background: var(--surface-soft);
		border-radius: var(--radius-tile);
		padding: var(--space-4) var(--space-5);
		margin: 0;
	}
	.grid {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(9.5rem, 1fr));
		gap: var(--space-3);
	}
	.tile {
		position: relative;
		background: var(--surface-soft);
		border-radius: var(--radius-tile);
		overflow: hidden;
		animation: pop 420ms calc(var(--i) * 30ms) cubic-bezier(0.2, 0.8, 0.2, 1) both;
	}
	/* The notch: a V cut from the upper-left corner, only for a person-confirmed notched ear. */
	.tile.cut {
		clip-path: polygon(0 0, 9% 0, 15% 11%, 21% 0, 100% 0, 100% 100%, 0 100%);
	}
	@keyframes pop {
		from {
			opacity: 0;
			transform: translateY(10px) scale(0.97);
		}
	}
	img {
		display: block;
		width: 100%;
		aspect-ratio: 1;
		object-fit: cover;
		background: var(--ink);
	}
	.meta {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: var(--space-2);
		padding: var(--space-2) var(--space-3);
	}
	.walks {
		display: inline-flex;
		gap: 3px;
	}
	.walk {
		display: inline-grid;
		place-items: center;
		width: 1.4rem;
		height: 1.4rem;
		border-radius: 50%;
		font-size: 0.75rem;
		font-weight: 600;
		background: var(--canvas);
		color: var(--fog-text);
	}
	.walk.on {
		background: var(--slate);
		color: #fff;
	}
	.ear {
		font-size: 0.8rem;
		font-weight: 600;
		border-radius: var(--radius-control);
		padding: 1px 8px;
		text-align: right;
	}
	.ear em {
		margin-left: 4px;
		font-style: normal;
		font-weight: 400;
		opacity: 0.8;
	}
	.ear.notched {
		background: var(--notched-wash);
		color: #1b5a51;
	}
	.ear.not_notched {
		background: var(--plain-wash);
		color: #6d3a12;
	}
	.ear.not_visible {
		background-image: var(--hatch);
		background-color: var(--surface);
		color: var(--ink);
		text-shadow:
			0 0 3px #fff,
			0 0 3px #fff;
	}
	.ear.unknown {
		background: var(--canvas);
		color: var(--fog-text);
		font-weight: 500;
	}
	@media (prefers-reduced-motion: reduce) {
		.tile {
			animation: none;
		}
	}
</style>

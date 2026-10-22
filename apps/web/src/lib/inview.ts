/** Svelte action: calls `onenter` once, the first time the element scrolls into view. */
export function inview(node: Element, onenter: () => void) {
	if (typeof IntersectionObserver === 'undefined') {
		onenter();
		return {};
	}
	const io = new IntersectionObserver(
		(entries) => {
			if (entries.some((e) => e.isIntersecting)) {
				onenter();
				io.disconnect();
			}
		},
		{ threshold: 0.35 }
	);
	io.observe(node);
	return { destroy: () => io.disconnect() };
}

/** Animate a number from 0 to `to` over `ms`, calling `set` each frame (instant with reduced motion). */
export function countUp(to: number, set: (v: number) => void, ms = 1400) {
	if (typeof window === 'undefined' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
		set(to);
		return;
	}
	const start = performance.now();
	const step = (now: number) => {
		const k = Math.min(1, (now - start) / ms);
		set(to * (1 - Math.pow(1 - k, 3)));
		if (k < 1) requestAnimationFrame(step);
	};
	requestAnimationFrame(step);
}

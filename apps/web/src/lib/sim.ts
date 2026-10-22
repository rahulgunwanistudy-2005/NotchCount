/**
 * The landing page's street simulator. Same formulas as packages/notchcount_stats/closed.py
 * (Chapman with the Chao log-normal interval) and proportion.py (Wilson), so what visitors see is
 * how the real engine counts. The street itself is made up; the page says so.
 */

export const Z95 = 1.959963984540054;

export function mulberry32(seed: number): () => number {
	let a = seed >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) >>> 0;
		let t = a;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

export interface Chapman {
	nHat: number;
	low: number;
	high: number;
	distinct: number;
}

/** Chapman N-hat with the Chao log-normal 95% interval; null when nothing was seen twice. */
export function chapman(n1: number, n2: number, m2: number): Chapman | null {
	const distinct = n1 + n2 - m2;
	if (m2 === 0) return null;
	const nHat = ((n1 + 1) * (n2 + 1)) / (m2 + 1) - 1;
	const variance = ((n1 + 1) * (n2 + 1) * (n1 - m2) * (n2 - m2)) / ((m2 + 1) ** 2 * (m2 + 2));
	const f0 = nHat - distinct;
	if (f0 <= 0) return { nHat, low: distinct, high: distinct, distinct };
	const c = Math.exp(Z95 * Math.sqrt(Math.log1p(variance / (f0 * f0))));
	return { nHat, low: distinct + f0 / c, high: distinct + f0 * c, distinct };
}

/** Wilson score interval for k of n. */
export function wilson(k: number, n: number): { p: number; low: number; high: number } | null {
	if (n === 0) return null;
	const p = k / n;
	const z2 = Z95 * Z95;
	const denom = 1 + z2 / n;
	const centre = (p + z2 / (2 * n)) / denom;
	const half = (Z95 * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n))) / denom;
	return { p, low: Math.max(0, centre - half), high: Math.min(1, centre + half) };
}

export type Coat = 'tan' | 'ginger' | 'cream' | 'black' | 'patch';

export interface SimDog {
	id: number;
	/** Position along the lane, 0 to 1, on each walk (dogs move a little overnight). */
	t: [number, number];
	/** Distance from the lane centre in px; negative is the left kerb. */
	side: [number, number];
	coat: Coat;
	notched: boolean;
	/** Whether the walker spots this dog on walk 1 and walk 2. */
	seen: [boolean, boolean];
}

const COATS: Coat[] = ['tan', 'tan', 'ginger', 'cream', 'black', 'patch'];

/**
 * A street of dogs. Each dog has its own chance of being spotted, so some shy dogs are missed on
 * both walks, which is why real counts lean low.
 */
export function makeStreet(seed: number, visibility: number, sterilised = 0.55): SimDog[] {
	const rnd = mulberry32(seed);
	const n = 30 + Math.floor(rnd() * 16);
	const dogs: SimDog[] = [];
	for (let i = 0; i < n; i++) {
		const t0 = 0.03 + rnd() * 0.94;
		const t1 = Math.min(0.97, Math.max(0.03, t0 + (rnd() - 0.5) * 0.08));
		const s0 = (rnd() < 0.5 ? -1 : 1) * (26 + rnd() * 34);
		const s1 = Math.sign(s0) * (26 + rnd() * 34);
		const shy = rnd() < 0.25;
		const p = Math.min(0.97, Math.max(0.05, visibility * (shy ? 0.55 : 1.08)));
		dogs.push({
			id: i,
			t: [t0, t1],
			side: [s0, s1],
			coat: COATS[Math.floor(rnd() * COATS.length)],
			notched: rnd() < sterilised,
			seen: [rnd() < p, rnd() < p]
		});
	}
	return dogs;
}

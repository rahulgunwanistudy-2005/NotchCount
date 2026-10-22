import { describe, expect, it } from 'vitest';
import { chapman, makeStreet, wilson } from './sim';

// From notchcount_stats.closed.chapman(40, 38, 25).
const CHAO_LOW = 55.733414616300024;
const CHAO_HIGH = 73.57865633137666;

describe('street simulator maths matches the engine', () => {
	it('reproduces the BIBLE worked example (Chapman with the Chao interval)', () => {
		const est = chapman(40, 38, 25);
		expect(est).not.toBeNull();
		expect(est!.nHat).toBeCloseTo(60.5, 6);
		expect(est!.distinct).toBe(53);
		expect(est!.low).toBeCloseTo(CHAO_LOW, 3);
		expect(est!.high).toBeCloseTo(CHAO_HIGH, 3);
	});

	it('gives no estimate without recaptures', () => {
		expect(chapman(12, 9, 0)).toBeNull();
	});

	it('reproduces the worked example share (Wilson)', () => {
		const s = wilson(29, 49)!;
		expect(s.p).toBeCloseTo(0.592, 3);
		expect(s.low).toBeCloseTo(0.452, 3);
		expect(s.high).toBeCloseTo(0.718, 3);
	});

	it('makes the same street for the same seed', () => {
		expect(makeStreet(7, 0.6)).toEqual(makeStreet(7, 0.6));
	});
});

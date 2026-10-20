import { describe, expect, it } from 'vitest';
import { scaledSize, toHex } from './image';

describe('scaledSize', () => {
	it('shrinks the long edge to 1600 and keeps the aspect ratio', () => {
		expect(scaledSize(4000, 3000)).toEqual({ width: 1600, height: 1200 });
		expect(scaledSize(3000, 4000)).toEqual({ width: 1200, height: 1600 });
	});
	it('never enlarges a small photo', () => {
		expect(scaledSize(1280, 720)).toEqual({ width: 1280, height: 720 });
	});
	it('rejects empty frames', () => {
		expect(() => scaledSize(0, 720)).toThrow();
	});
});

describe('toHex', () => {
	it('pads bytes', () => {
		expect(toHex(new Uint8Array([0, 15, 255]).buffer)).toBe('000fff');
	});
});

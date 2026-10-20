/** Client-side photo preparation: resize to a 1600 px long edge, JPEG q 0.85, SHA-256. */

export const LONG_EDGE = 1600;
export const JPEG_QUALITY = 0.85;

export function scaledSize(width: number, height: number, longEdge = LONG_EDGE): { width: number; height: number } {
	if (width <= 0 || height <= 0) throw new Error('image has no size');
	const scale = Math.min(1, longEdge / Math.max(width, height));
	return { width: Math.round(width * scale), height: Math.round(height * scale) };
}

export function toHex(buffer: ArrayBuffer): string {
	return Array.from(new Uint8Array(buffer), (b) => b.toString(16).padStart(2, '0')).join('');
}

export async function sha256Hex(blob: Blob): Promise<string> {
	return toHex(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer()));
}

export async function encodeFrame(source: CanvasImageSource, width: number, height: number): Promise<Blob> {
	const size = scaledSize(width, height);
	const canvas = document.createElement('canvas');
	canvas.width = size.width;
	canvas.height = size.height;
	const ctx = canvas.getContext('2d');
	if (!ctx) throw new Error('This phone cannot prepare photos (no canvas).');
	ctx.drawImage(source, 0, 0, size.width, size.height);
	const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY));
	if (!blob) throw new Error('Could not save the photo. Try again.');
	return blob;
}

export async function encodeFile(file: File): Promise<Blob> {
	const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
	try {
		return await encodeFrame(bitmap, bitmap.width, bitmap.height);
	} finally {
		bitmap.close();
	}
}

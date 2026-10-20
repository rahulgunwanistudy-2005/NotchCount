"""Appearance features: DINOv2 embeddings (ONNX) and HSV colour histograms."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import onnxruntime as ort

from notchcount_pipeline.detect import Image

Vector = npt.NDArray[np.float32]

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
H_BINS, S_BINS, V_BINS = 12, 4, 3


def square_pad(rgb: Image, size: int) -> Image:
    """Fit the whole crop into a square (no cropping away of ears or tail), pad with grey."""
    h, w = rgb.shape[:2]
    scale = size / max(h, w)
    nh, nw = max(1, round(h * scale)), max(1, round(w * scale))
    resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.full((size, size, 3), 124, dtype=np.uint8)
    y, x = (size - nh) // 2, (size - nw) // 2
    canvas[y : y + nh, x : x + nw] = resized
    return canvas


class Embedder:
    """DINOv2 image encoder exported with a fixed input size; returns the L2-normalised CLS vector."""

    def __init__(self, model_path: Path, input_size: int = 224, threads: int = 2) -> None:
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model_path), opts, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = input_size
        self.version = f"{model_path.stem}@{input_size}"

    def __call__(self, crop_rgb: Image) -> Vector:
        img = square_pad(crop_rgb, self.input_size).astype(np.float32) / 255.0
        tensor = ((img - IMAGENET_MEAN) / IMAGENET_STD).transpose(2, 0, 1)[None].astype(np.float32)
        out = self.session.run(None, {self.input_name: tensor})[0]
        vec = np.asarray(out, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0 else vec


def color_histogram(crop_rgb: Image) -> Vector:
    """Normalised HSV histogram over the central 80% of the crop (less background)."""
    h, w = crop_rgb.shape[:2]
    inner = crop_rgb[int(h * 0.1) : max(int(h * 0.9), 1), int(w * 0.1) : max(int(w * 0.9), 1)]
    hsv = cv2.cvtColor(inner, cv2.COLOR_RGB2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [H_BINS, S_BINS, V_BINS], [0, 180, 0, 256, 0, 256])
    flat = hist.reshape(-1).astype(np.float32)
    total = float(flat.sum())
    return flat / total if total > 0 else flat


def chi_square(a: Vector, b: Vector) -> float:
    denom = a + b
    mask = denom > 0
    return float(0.5 * np.sum((a[mask] - b[mask]) ** 2 / denom[mask]))

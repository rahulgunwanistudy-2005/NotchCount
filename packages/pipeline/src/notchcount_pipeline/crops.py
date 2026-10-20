"""Dog crops and their quality score (BIBLE 5.2)."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from notchcount_pipeline.detect import Box, Image

PAD = 0.10
# Scales chosen so a sharp, well-framed dog filling a fifth of a 1600 px photo scores near 1.
AREA_FULL = 0.20
SHARP_FULL = 150.0


@dataclass(frozen=True, slots=True)
class CropQuality:
    area_score: float
    sharpness: float
    sharp_score: float
    truncated: bool
    score: float


def padded(box: Box, w: int, h: int, pad: float = PAD) -> tuple[int, int, int, int]:
    dx, dy = (box.x2 - box.x1) * pad, (box.y2 - box.y1) * pad
    return (
        max(0, int(box.x1 - dx)),
        max(0, int(box.y1 - dy)),
        min(w, int(np.ceil(box.x2 + dx))),
        min(h, int(np.ceil(box.y2 + dy))),
    )


def crop(rgb: Image, box: Box) -> Image:
    h, w = rgb.shape[:2]
    x1, y1, x2, y2 = padded(box, w, h)
    return rgb[y1:y2, x1:x2].copy()


def quality(rgb: Image, box: Box, crop_rgb: Image) -> CropQuality:
    h, w = rgb.shape[:2]
    area_frac = box.area / float(w * h)
    area_score = float(min(1.0, np.sqrt(area_frac / AREA_FULL)))
    gray = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2GRAY)
    if min(gray.shape) > 256:
        gray = cv2.resize(gray, (256, int(256 * gray.shape[0] / gray.shape[1])), interpolation=cv2.INTER_AREA)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    sharp_score = float(min(1.0, sharpness / SHARP_FULL))
    margin = 2
    truncated = box.x1 <= margin or box.y1 <= margin or box.x2 >= w - margin or box.y2 >= h - margin
    score = float(np.sqrt(area_score * sharp_score) * (0.7 if truncated else 1.0))
    return CropQuality(area_score, sharpness, sharp_score, truncated, score)

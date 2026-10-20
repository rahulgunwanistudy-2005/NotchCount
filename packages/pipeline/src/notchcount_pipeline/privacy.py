"""Blur people and vehicles before anything is stored (BIBLE 5.1).

No plate detector is bundled, so the whole vehicle box is blurred (the pack's fallback).
"""

from __future__ import annotations

import cv2
import numpy as np
import numpy.typing as npt

from notchcount_pipeline.detect import VEHICLES, Box, Coco, Image

EXPAND = 0.12
Mask = npt.NDArray[np.bool_]


def expand(box: Box, w: int, h: int, frac: float = EXPAND) -> tuple[int, int, int, int]:
    dx, dy = (box.x2 - box.x1) * frac, (box.y2 - box.y1) * frac
    return (
        max(0, int(box.x1 - dx)),
        max(0, int(box.y1 - dy)),
        min(w, int(np.ceil(box.x2 + dx))),
        min(h, int(np.ceil(box.y2 + dy))),
    )


def redact(rgb: Image, boxes: list[Box]) -> tuple[Image, Mask, int, int]:
    """Blurred copy, the mask of blurred pixels, and counts of people and vehicles blurred."""
    out = rgb.copy()
    h, w = rgb.shape[:2]
    mask = np.zeros((h, w), dtype=bool)
    persons = vehicles = 0
    for box in boxes:
        if box.cls == Coco.PERSON:
            persons += 1
        elif box.cls in VEHICLES:
            vehicles += 1
        else:
            continue
        x1, y1, x2, y2 = expand(box, w, h)
        if x2 <= x1 or y2 <= y1:
            continue
        region = out[y1:y2, x1:x2]
        # Pixelate, then blur: unreadable at any zoom and does not leave a sharp grid.
        small = cv2.resize(region, (max(1, (x2 - x1) // 16), max(1, (y2 - y1) // 16)), interpolation=cv2.INTER_AREA)
        coarse = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
        k = max(15, ((min(x2 - x1, y2 - y1) // 4) | 1))
        out[y1:y2, x1:x2] = cv2.GaussianBlur(coarse, (k, k), 0)
        mask[y1:y2, x1:x2] = True
    return out, mask, persons, vehicles


def unblurred_person_boxes(redetected: list[Box], mask: Mask, min_covered: float = 0.6) -> list[Box]:
    """Person boxes found on the stored image that are not mostly inside a blurred region."""
    bad: list[Box] = []
    for box in redetected:
        if box.cls != Coco.PERSON:
            continue
        x1, y1, x2, y2 = int(box.x1), int(box.y1), int(np.ceil(box.x2)), int(np.ceil(box.y2))
        area = max(1, (x2 - x1) * (y2 - y1))
        if mask[y1:y2, x1:x2].sum() / area < min_covered:
            bad.append(box)
    return bad

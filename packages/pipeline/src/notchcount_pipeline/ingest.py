"""One photo in, a privacy-safe photo and scored dog crops out. No database, no HTTP."""

from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image as PILImage
from PIL import ImageOps

from notchcount_pipeline.crops import crop, quality
from notchcount_pipeline.detect import Box, Coco, Detector, Image, Thresholds
from notchcount_pipeline.features import Embedder, Vector, color_histogram
from notchcount_pipeline.privacy import redact, unblurred_person_boxes

QUALITY_FLOOR = 0.35
STORE_QUALITY = 85


class PrivacyCheckFailed(Exception):
    """A person was still visible after blurring; nothing from this photo may be stored."""


@dataclass(frozen=True, slots=True)
class DogCrop:
    box: Box
    jpeg: bytes
    quality: float
    usable: bool
    embedding: Vector
    color_hist: Vector


@dataclass(frozen=True, slots=True)
class IngestResult:
    blurred_jpeg: bytes
    width: int
    height: int
    persons_blurred: int
    vehicles_blurred: int
    dogs: list[DogCrop]
    timings_ms: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Models:
    detector: Detector
    embedder: Embedder

    @property
    def version(self) -> str:
        return f"{self.detector.version}+{self.embedder.version}"

    @staticmethod
    def load(model_dir: Path, threads: int = 2) -> Models:
        return Models(
            Detector(model_dir / "detector.onnx", threads=threads),
            Embedder(model_dir / "dinov2_vits14.onnx", threads=threads),
        )


def decode(jpeg: bytes) -> Image:
    """Decode, apply the EXIF rotation, and drop all EXIF (GPS lives only in the database)."""
    with PILImage.open(io.BytesIO(jpeg)) as im:
        upright = ImageOps.exif_transpose(im).convert("RGB")
        return np.asarray(upright, dtype=np.uint8).copy()


def encode(rgb: Image, quality_: int = STORE_QUALITY) -> bytes:
    buf = io.BytesIO()
    PILImage.fromarray(rgb).save(buf, "JPEG", quality=quality_, optimize=True)
    return buf.getvalue()


def process(
    jpeg: bytes,
    models: Models,
    thresholds: Thresholds | None = None,
    quality_floor: float = QUALITY_FLOOR,
    verify_privacy: bool = True,
) -> IngestResult:
    t: dict[str, float] = {}
    start = time.perf_counter()
    rgb = decode(jpeg)
    t["decode"] = (time.perf_counter() - start) * 1000

    s = time.perf_counter()
    boxes = models.detector(rgb, thresholds)
    t["detect"] = (time.perf_counter() - s) * 1000

    s = time.perf_counter()
    blurred, mask, persons, vehicles = redact(rgb, boxes)
    if verify_privacy and persons:
        leftover = unblurred_person_boxes(models.detector(blurred, thresholds), mask)
        if leftover:
            raise PrivacyCheckFailed(f"{len(leftover)} person region(s) still visible after blurring")
    t["blur"] = (time.perf_counter() - s) * 1000

    s = time.perf_counter()
    dogs: list[DogCrop] = []
    for box in boxes:
        if box.cls != Coco.DOG:
            continue
        # Crops come from the blurred image so a person next to a dog stays blurred in the crop.
        patch = crop(blurred, box)
        if patch.size == 0:
            continue
        q = quality(blurred, box, patch)
        dogs.append(
            DogCrop(
                box=box,
                jpeg=encode(patch, 90),
                quality=q.score,
                usable=q.score >= quality_floor,
                embedding=models.embedder(patch),
                color_hist=color_histogram(patch),
            )
        )
    t["dogs"] = (time.perf_counter() - s) * 1000

    s = time.perf_counter()
    out = encode(blurred)
    t["encode"] = (time.perf_counter() - s) * 1000
    t["total"] = (time.perf_counter() - start) * 1000
    h, w = rgb.shape[:2]
    return IngestResult(out, w, h, persons, vehicles, dogs, t)

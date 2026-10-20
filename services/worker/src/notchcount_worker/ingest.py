"""Job `ingest_photo`: blur, crop, embed one uploaded photo, then delete the unblurred original.

Idempotent: a processed photo is skipped; a retried photo replaces its earlier detections.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from notchcount_api.blobs import Bucket, PostgresBlobStore
from notchcount_api.config import REPO_ROOT
from notchcount_api.db.models import Detection, Photo, PhotoStatus
from notchcount_pipeline.detect import Detector
from notchcount_pipeline.features import Embedder
from notchcount_pipeline.ingest import Models, PrivacyCheckFailed, process
from notchcount_worker.errors import PermanentJobError

log = logging.getLogger("notchcount.worker.ingest")

MODEL_DIR = Path(os.environ.get("NC_MODEL_DIR", REPO_ROOT / "models" / "cache"))
EMBEDDER = os.environ.get("NC_EMBEDDER", "dinov2_vits14_int8")
THREADS = int(os.environ.get("NC_MODEL_THREADS", "2"))


def models_ready() -> bool:
    return (MODEL_DIR / "detector.onnx").is_file() and (MODEL_DIR / f"{EMBEDDER}.onnx").is_file()


@lru_cache(maxsize=1)
def models() -> Models:
    return Models(
        Detector(MODEL_DIR / "detector.onnx", threads=THREADS),
        Embedder(MODEL_DIR / f"{EMBEDDER}.onnx", threads=THREADS),
    )


async def ingest_photo(db: AsyncSession, payload: dict[str, Any]) -> None:
    photo_id = uuid.UUID(str(payload["photo_id"]))
    photo = (
        await db.execute(select(Photo).where(Photo.id == photo_id).with_for_update())
    ).scalar_one_or_none()
    if photo is None:
        raise PermanentJobError(f"photo {photo_id} no longer exists")
    if photo.status is PhotoStatus.PROCESSED:
        return
    store = PostgresBlobStore(db)
    if photo.quarantine_key is None:
        raise PermanentJobError("photo has no stored original")
    found = await store.get(photo.quarantine_key)
    if found is None:
        raise PermanentJobError("original image is missing from quarantine")
    _, _, original = found

    m = models()
    try:
        result = await asyncio.to_thread(process, original, m)
    except PrivacyCheckFailed as exc:
        # Keep the original in quarantine (never served) so an admin can look, but store nothing.
        photo.status = PhotoStatus.FAILED
        photo.error = str(exc)
        await db.flush()
        log.warning("privacy check failed", extra={"photo_id": str(photo_id)})
        return

    blurred_key = f"blurred/{photo_id}.jpg"
    await store.put(Bucket.BLURRED, blurred_key, result.blurred_jpeg, "image/jpeg")
    await db.execute(delete(Detection).where(Detection.photo_id == photo_id))
    for i, dog in enumerate(result.dogs):
        crop_key = f"crops/{photo_id}_{i}.jpg"
        await store.put(Bucket.CROPS, crop_key, dog.jpeg, "image/jpeg")
        db.add(
            Detection(
                photo_id=photo_id,
                bbox=dog.box.as_list(),
                conf=dog.box.conf,
                crop_key=crop_key,
                quality=dog.quality,
                usable=dog.usable,
                embedding=dog.embedding.tolist(),
                color_hist=[float(v) for v in dog.color_hist],
                view=photo.shot,
                model_version=m.version,
            )
        )
    photo.storage_key = blurred_key
    photo.width, photo.height = result.width, result.height
    photo.persons_blurred = result.persons_blurred
    photo.vehicles_blurred = result.vehicles_blurred
    photo.status = PhotoStatus.PROCESSED
    photo.error = None
    old_key, photo.quarantine_key = photo.quarantine_key, None
    await store.delete(old_key)
    await db.flush()
    log.info(
        "photo ingested",
        extra={
            "photo_id": str(photo_id),
            "dogs": len(result.dogs),
            "persons": result.persons_blurred,
            "ms": round(result.timings_ms["total"]),
        },
    )

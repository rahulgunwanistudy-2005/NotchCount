"""Needs the exported ONNX models in models/cache (see models/export_models.py)."""

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from notchcount_pipeline.detect import Coco
from notchcount_pipeline.ingest import Models, decode, process
from notchcount_pipeline.privacy import unblurred_person_boxes

pytestmark = pytest.mark.models
HERE = Path(__file__).parent
MODELS = Path(__file__).resolve().parents[3] / "models" / "cache"


@pytest.fixture(scope="module")
def models() -> Models:
    if not (MODELS / "detector.onnx").exists():
        pytest.skip("models not exported")
    return Models.load(MODELS)


def test_people_are_blurred_and_stay_blurred(models: Models) -> None:
    original = (HERE / "fixture_people.jpg").read_bytes()
    before = [b for b in models.detector(decode(original)) if b.cls == Coco.PERSON]
    assert len(before) >= 3
    res = process(original, models)
    assert res.persons_blurred == len(before)
    stored = decode(res.blurred_jpeg)
    after = [b for b in models.detector(stored) if b.cls == Coco.PERSON]
    mask = np.zeros(stored.shape[:2], dtype=bool)
    from notchcount_pipeline.privacy import expand

    for b in before:
        x1, y1, x2, y2 = expand(b, stored.shape[1], stored.shape[0])
        mask[y1:y2, x1:x2] = True
    assert unblurred_person_boxes(after, mask) == []


def test_dog_crop_and_embedding(models: Models) -> None:
    res = process((HERE / "fixture_dog.jpg").read_bytes(), models)
    assert len(res.dogs) == 1
    dog = res.dogs[0]
    assert dog.usable and dog.box.conf > 0.5
    assert dog.embedding.shape == (384,)
    assert abs(float(np.linalg.norm(dog.embedding)) - 1.0) < 1e-4


def test_stored_image_has_no_exif(models: Models) -> None:
    img = Image.open(HERE / "fixture_dog.jpg")
    exif = Image.Exif()
    exif[0x9003] = "2026:10:21 06:45:00"
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    res = process(buf.getvalue(), models)
    assert len(Image.open(io.BytesIO(res.blurred_jpeg)).getexif()) == 0


def test_same_photo_same_result(models: Models) -> None:
    data = (HERE / "fixture_dog.jpg").read_bytes()
    a, b = process(data, models), process(data, models)
    assert a.blurred_jpeg == b.blurred_jpeg
    assert np.allclose(a.dogs[0].embedding, b.dogs[0].embedding)

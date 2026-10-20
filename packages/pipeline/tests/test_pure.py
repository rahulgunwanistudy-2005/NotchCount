import numpy as np

from notchcount_pipeline.crops import quality
from notchcount_pipeline.detect import Box, Coco, letterbox
from notchcount_pipeline.features import chi_square, color_histogram, square_pad
from notchcount_pipeline.privacy import redact, unblurred_person_boxes


def _noise(h: int, w: int, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, 255, (h, w, 3), dtype=np.uint8)


def test_redact_blurs_people_and_vehicles_but_not_dogs() -> None:
    img = _noise(200, 300)
    boxes = [
        Box(Coco.PERSON, 0.9, 10, 10, 60, 120),
        Box(Coco.CAR, 0.8, 150, 100, 280, 190),
        Box(Coco.DOG, 0.9, 100, 20, 140, 60),
    ]
    out, mask, persons, vehicles = redact(img, boxes)
    assert (persons, vehicles) == (1, 1)
    assert mask[50, 30] and mask[150, 200]
    assert not mask[40, 120]
    assert out[20:110, 15:55].std() < img[20:110, 15:55].std() / 3
    assert np.array_equal(out[25:55, 105:135], img[25:55, 105:135])


def test_person_outside_blurred_area_is_reported() -> None:
    mask = np.zeros((100, 100), dtype=bool)
    mask[0:50, 0:50] = True
    inside = Box(Coco.PERSON, 0.9, 5, 5, 45, 45)
    outside = Box(Coco.PERSON, 0.9, 55, 55, 95, 95)
    assert unblurred_person_boxes([inside, outside], mask) == [outside]


def test_letterbox_keeps_aspect_and_pads() -> None:
    tensor, scale, (px, py) = letterbox(_noise(480, 640), 640)
    assert tensor.shape == (1, 3, 640, 640)
    assert scale == 1.0 and px == 0 and py == 80


def test_quality_prefers_big_sharp_untruncated_crops() -> None:
    img = _noise(800, 800)
    big = Box(Coco.DOG, 0.9, 100, 100, 500, 500)
    small = Box(Coco.DOG, 0.9, 100, 100, 140, 140)
    edge = Box(Coco.DOG, 0.9, 0, 100, 400, 500)
    q_big = quality(img, big, img[100:500, 100:500])
    q_small = quality(img, small, img[100:140, 100:140])
    q_edge = quality(img, edge, img[100:500, 0:400])
    assert q_big.score > q_small.score
    assert q_edge.truncated and q_edge.score < q_big.score
    flat = np.full((400, 400, 3), 128, dtype=np.uint8)
    assert quality(img, big, flat).score < 0.1


def test_color_histogram_is_a_distribution() -> None:
    hist = color_histogram(_noise(64, 64))
    assert abs(float(hist.sum()) - 1.0) < 1e-5
    assert chi_square(hist, hist) == 0.0
    red = np.zeros((64, 64, 3), dtype=np.uint8)
    red[..., 0] = 220
    assert chi_square(hist, color_histogram(red)) > 0.5


def test_square_pad_keeps_whole_crop() -> None:
    out = square_pad(_noise(50, 200), 224)
    assert out.shape == (224, 224, 3)
    assert (out[0, 0] == 124).all()

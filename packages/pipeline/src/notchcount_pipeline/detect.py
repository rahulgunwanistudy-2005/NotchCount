"""COCO object detector (YOLO family, exported to ONNX) on CPU.

Expects an Ultralytics-style export: input `images` [1, 3, S, S] float32 in 0..1 (RGB,
letterboxed), output [1, 4 + 80, A] with cx, cy, w, h in input pixels and per-class scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import onnxruntime as ort

Image = npt.NDArray[np.uint8]


class Coco(IntEnum):
    PERSON = 0
    BICYCLE = 1
    CAR = 2
    MOTORCYCLE = 3
    BUS = 5
    TRUCK = 7
    DOG = 16


VEHICLES = frozenset({Coco.CAR, Coco.MOTORCYCLE, Coco.BUS, Coco.TRUCK})


@dataclass(frozen=True, slots=True)
class Box:
    cls: int
    conf: float
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)

    def as_list(self) -> list[float]:
        return [round(self.x1, 1), round(self.y1, 1), round(self.x2, 1), round(self.y2, 1)]


@dataclass(frozen=True, slots=True)
class Thresholds:
    dog: float = 0.35
    person: float = 0.25
    vehicle: float = 0.30
    nms_iou: float = 0.5

    def for_class(self, cls: int) -> float | None:
        if cls == Coco.DOG:
            return self.dog
        if cls == Coco.PERSON:
            return self.person
        if cls in VEHICLES:
            return self.vehicle
        return None


def letterbox(image: Image, size: int) -> tuple[npt.NDArray[np.float32], float, tuple[int, int]]:
    """Resize keeping aspect ratio, pad to a square; returns tensor, scale and (pad_x, pad_y)."""
    h, w = image.shape[:2]
    scale = size / max(h, w)
    nh, nw = round(h * scale), round(w * scale)
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR)
    pad_x, pad_y = (size - nw) // 2, (size - nh) // 2
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[pad_y : pad_y + nh, pad_x : pad_x + nw] = resized
    tensor = canvas.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
    return tensor, scale, (pad_x, pad_y)


class Detector:
    def __init__(self, model_path: Path, input_size: int = 640, threads: int = 2) -> None:
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        opts.enable_cpu_mem_arena = False
        self.session = ort.InferenceSession(str(model_path), opts, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = input_size
        self.version = f"{model_path.stem}@{input_size}"

    def __call__(self, rgb: Image, thresholds: Thresholds | None = None) -> list[Box]:
        th = thresholds or Thresholds()
        tensor, scale, (pad_x, pad_y) = letterbox(rgb, self.input_size)
        out = self.session.run(None, {self.input_name: tensor})[0][0]  # [84, A]
        scores = out[4:]
        cls = scores.argmax(axis=0)
        conf = scores.max(axis=0)
        keep_min = np.array([th.for_class(int(c)) or 2.0 for c in range(scores.shape[0])])
        mask = conf >= keep_min[cls]
        if not mask.any():
            return []
        cx, cy, bw, bh = out[0][mask], out[1][mask], out[2][mask], out[3][mask]
        conf, cls = conf[mask], cls[mask]
        h, w = rgb.shape[:2]
        x1 = np.clip((cx - bw / 2 - pad_x) / scale, 0, w)
        y1 = np.clip((cy - bh / 2 - pad_y) / scale, 0, h)
        x2 = np.clip((cx + bw / 2 - pad_x) / scale, 0, w)
        y2 = np.clip((cy + bh / 2 - pad_y) / scale, 0, h)
        boxes: list[Box] = []
        for c in np.unique(cls):
            idx = np.where(cls == c)[0]
            rects = [[float(x1[i]), float(y1[i]), float(x2[i] - x1[i]), float(y2[i] - y1[i])] for i in idx]
            kept = cv2.dnn.NMSBoxes(rects, conf[idx].tolist(), 0.0, th.nms_iou)
            for k in np.array(kept).reshape(-1):
                i = idx[int(k)]
                boxes.append(
                    Box(int(c), float(conf[i]), float(x1[i]), float(y1[i]), float(x2[i]), float(y2[i]))
                )
        return sorted(boxes, key=lambda b: -b.conf)

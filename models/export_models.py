"""Export the two ONNX models the worker needs. Run in a separate environment (needs torch):

    uv venv .export && VIRTUAL_ENV=.export uv pip install ultralytics onnx onnxslim transformers
    .export/bin/python models/export_models.py models/cache

Detector: Ultralytics YOLO11n (AGPL-3.0), COCO classes, 640 px input.
Embedder: DINOv2 ViT-S/14 (facebook/dinov2-small, Apache-2.0), 224 px, CLS token (384-d).
"""

import shutil
import sys
from pathlib import Path


def export_detector(out: Path) -> None:
    from ultralytics import YOLO

    model = YOLO("yolo11n.pt")
    path = model.export(format="onnx", imgsz=640, dynamic=False, simplify=True, opset=17)
    shutil.move(path, out / "detector.onnx")


def export_dinov2(out: Path) -> None:
    import torch
    from transformers import AutoModel

    model = AutoModel.from_pretrained("facebook/dinov2-small").eval()

    class Cls(torch.nn.Module):
        def __init__(self, m: torch.nn.Module) -> None:
            super().__init__()
            self.m = m

        def forward(self, pixel_values: torch.Tensor) -> torch.Tensor:
            return self.m(pixel_values=pixel_values).last_hidden_state[:, 0]

    dummy = torch.randn(1, 3, 224, 224)
    torch.onnx.export(
        Cls(model),
        (dummy,),
        str(out / "dinov2_vits14.onnx"),
        input_names=["pixel_values"],
        output_names=["cls"],
        opset_version=17,
        dynamo=False,
    )


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "models/cache")
    target.mkdir(parents=True, exist_ok=True)
    export_detector(target)
    export_dinov2(target)
    for f in sorted(target.glob("*.onnx")):
        print(f.name, f.stat().st_size)

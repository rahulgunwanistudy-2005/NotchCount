"""Make the landing page's pipeline pictures from the real models, so the page shows real output.

Runs the production detector, blur and embedder on the CC BY-SA sample photos and writes:
  apps/web/static/img/pipeline/street-blurred.webp  the street photo as it would be stored
  apps/web/static/img/crops/dog-NN.webp             the dog crops the pipeline cut
  apps/web/src/lib/landing-assets.json              boxes, scores and similarities, in image pixels

    uv run python scripts/landing_assets.py
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from notchcount_pipeline.detect import Coco
from notchcount_pipeline.ingest import Models, process

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "samples"
WEB = ROOT / "apps" / "web"
OUT_IMG = WEB / "static" / "img"


def webp(jpeg: bytes, dest: Path, max_side: int) -> tuple[int, int]:
    im = Image.open(io.BytesIO(jpeg)).convert("RGB")
    im.thumbnail((max_side, max_side))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "WEBP", quality=74)
    return im.size


def to_jpeg(path: Path) -> bytes:
    buf = io.BytesIO()
    Image.open(path).convert("RGB").save(buf, "JPEG", quality=92)
    return buf.getvalue()


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def main() -> None:
    models = Models.load(ROOT / "models" / "cache")
    out: dict[str, object] = {}

    # Hero photos: the dog box the detector draws on exactly the image the page shows.
    hero = {}
    embeddings = {}
    for name in ("hero-dog", "sitting-dog"):
        path = OUT_IMG / f"{name}.webp"
        res = process(to_jpeg(path), models)
        dog = max(res.dogs, key=lambda d: d.box.conf)
        hero[name] = {
            "w": res.width,
            "h": res.height,
            "box": dog.box.as_list(),
            "conf": round(dog.box.conf, 3),
        }
        embeddings[name] = np.asarray(dog.embedding)
    out["hero"] = hero
    out["hero_similarity"] = round(cosine(embeddings["hero-dog"], embeddings["sitting-dog"]), 3)

    # Street photo: blurred as stored, with the boxes that were blurred.
    street = process((SAMPLES / "people_bus.jpg").read_bytes(), models)
    w, h = webp(street.blurred_jpeg, OUT_IMG / "pipeline" / "street-blurred.webp", 900)
    scale = w / street.width
    boxes = models.detector(
        np.asarray(Image.open(SAMPLES / "people_bus.jpg").convert("RGB")), None
    )  # same boxes the blur used
    out["street"] = {
        "w": w,
        "h": h,
        "persons": street.persons_blurred,
        "vehicles": street.vehicles_blurred,
        "boxes": [
            {
                "kind": "person" if b.cls == Coco.PERSON else "vehicle",
                "box": [round(v * scale, 1) for v in b.as_list()],
            }
            for b in boxes
            if b.cls == Coco.PERSON or b.cls in (Coco.CAR, Coco.MOTORCYCLE, Coco.BUS, Coco.TRUCK)
        ],
    }

    # Crops of every sample dog, as the pipeline cuts them, for the gallery strip.
    crops = []
    for i, path in enumerate(sorted(SAMPLES.glob("dog_*.jpg")), start=1):
        res = process(path.read_bytes(), models)
        for d in res.dogs[:1]:
            name = f"dog-{i:02d}.webp"
            webp(d.jpeg, OUT_IMG / "crops" / name, 320)
            crops.append({"src": f"/img/crops/{name}", "file": path.name, "quality": round(d.quality, 2)})
    out["crops"] = crops
    out["model_version"] = models.version

    dest = WEB / "src" / "lib" / "landing-assets.json"
    dest.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "crops"}, indent=1))
    print(f"{len(crops)} crops written")


if __name__ == "__main__":
    main()

"""Dog re-identification benchmark for NotchCount's embedder on REAL identity-labelled photos.

Data: WildlifeReID-10k (Kaggle), dog subsets only: MPDD (whole-body, CC BY 4.0) and DogFaceNet
(faces, CC BY 4.0). Evaluation only; nothing is re-uploaded. Code: NotchCount's own pipeline
package installed from GitHub; models: the repo's release models-v1.

For each image: run NotchCount's detector, crop the top dog box the way production does (or use
the whole image if no box), embed with DINOv2 (int8 and fp32). Same-identity pairs vs
different-identity pairs: ROC-AUC of cosine similarity, plus rank-1 retrieval.
"""

import json
import os
import random
import subprocess
import sys
import time

REPO = "https://github.com/rahulgunwanistudy-2005/NotchCount"
subprocess.run(
    [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-q",
        "--ignore-requires-python",
        f"git+{REPO}#subdirectory=packages/notchcount_stats",
    ],
    check=True,
)
subprocess.run(
    [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-q",
        "--no-deps",
        "--ignore-requires-python",
        f"git+{REPO}#subdirectory=packages/pipeline",
    ],
    check=True,
)
subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q", "onnxruntime", "opencv-python-headless"], check=True
)

import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from sklearn.metrics import roc_auc_score

from notchcount_pipeline.crops import crop
from notchcount_pipeline.detect import Coco, Detector
from notchcount_pipeline.features import Embedder

MODELS = Path("/kaggle/working/models")
MODELS.mkdir(parents=True, exist_ok=True)
for f in ("detector.onnx", "dinov2_vits14_int8.onnx", "dinov2_vits14.onnx"):
    if not (MODELS / f).exists():
        urllib.request.urlretrieve(f"{REPO}/releases/download/models-v1/{f}", MODELS / f)

# Kaggle's mount path for attached datasets has changed over time; find it.
ROOT = next(p.parent for p in Path("/kaggle/input").rglob("metadata.csv") if (p.parent / "images").is_dir())
print("dataset root", ROOT, flush=True)
meta = pd.read_csv(ROOT / "metadata.csv")
threads = os.cpu_count() or 4
det = Detector(MODELS / "detector.onnx", threads=threads)
embedders = {
    "dinov2_int8": Embedder(MODELS / "dinov2_vits14_int8.onnx", threads=threads),
    "dinov2_fp32": Embedder(MODELS / "dinov2_vits14.onnx", threads=threads),
}
rng = random.Random(0)


def load(path: str) -> np.ndarray:
    return np.asarray(Image.open(ROOT / path).convert("RGB"))


def evaluate(name: str, df: pd.DataFrame, use_detector: bool) -> dict:
    t0 = time.time()
    vecs = {k: [] for k in embedders}
    ids, detected = [], 0
    for path, ident in zip(df["path"], df["identity"]):
        rgb = load(path)
        patch = rgb
        if use_detector:
            dogs = [b for b in det(rgb) if b.cls == Coco.DOG]
            if dogs:
                detected += 1
                patch = crop(rgb, max(dogs, key=lambda b: b.conf))
        for k, e in embedders.items():
            vecs[k].append(e(patch))
        ids.append(ident)
    ids = np.array(ids)
    out = {
        "dataset": name,
        "images": int(len(ids)),
        "identities": int(len(set(ids))),
        "dog_detected": detected if use_detector else None,
        "seconds": round(time.time() - t0),
    }
    same = ids[:, None] == ids[None, :]
    iu = np.triu_indices(len(ids), 1)
    pos = np.flatnonzero(same[iu])
    neg = np.flatnonzero(~same[iu])
    neg = np.array(rng.sample(list(neg), min(len(neg), 20 * len(pos))))
    for k, v in vecs.items():
        m = np.stack(v)
        sims = m @ m.T
        s = sims[iu]
        y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
        x = np.r_[s[pos], s[neg]]
        np.fill_diagonal(sims, -9)
        rank1 = float(np.mean(ids[sims.argmax(axis=1)] == ids))
        out[k] = {
            "auc": float(roc_auc_score(y, x)),
            "rank1": rank1,
            "pairs_pos": int(len(pos)),
            "pairs_neg": int(len(neg)),
            "cos_same_mean": float(s[pos].mean()),
            "cos_diff_mean": float(s[neg].mean()),
        }
    print(json.dumps(out), flush=True)
    return out


results = []
mpdd = meta[meta.dataset == "MPDD"]
results.append(evaluate("MPDD (whole body)", mpdd, use_detector=True))
dfn = meta[meta.dataset == "DogFaceNet"]
keep = rng.sample(sorted(dfn.identity.unique()), 300)
results.append(evaluate("DogFaceNet (faces, 300 dogs)", dfn[dfn.identity.isin(keep)], use_detector=False))
Path("/kaggle/working/reid_results.json").write_text(json.dumps(results, indent=1))

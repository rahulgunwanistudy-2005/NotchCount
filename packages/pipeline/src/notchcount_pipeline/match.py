"""Candidate pairs and the calibrated match model (BIBLE 5.3). Pure: arrays in, arrays out.

Features per pair of dog detections: cosine similarity of DINOv2 embeddings, distance along the
route between the two sightings, time gap, same-pass flag and HSV colour-histogram distance.
P(same dog) is a logistic regression fitted on the team's labelled pairs. Coefficients are stored
as JSON (never pickled) with a version hash.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import numpy.typing as npt

from notchcount_pipeline.features import chi_square

FloatArray = npt.NDArray[np.float64]

FEATURES = ("cosine", "route_km", "log_gap_min", "same_pass", "colour_chi2")


@dataclass(frozen=True, slots=True)
class Sighting:
    """One usable dog detection, with where and when it was seen."""

    id: str
    pass_no: int
    photo_id: str
    taken_at: datetime
    route_m: float | None
    embedding: npt.NDArray[np.float32]
    color_hist: npt.NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class CandidateRules:
    within_pass_gap_min: float = 15.0
    within_pass_route_m: float = 120.0
    across_pass_route_m: float = 300.0
    top_k: int = 8
    min_cosine: float = 0.35


def pair_features(a: Sighting, b: Sighting) -> dict[str, float]:
    cos = float(np.dot(a.embedding, b.embedding))
    route_m = abs(a.route_m - b.route_m) if a.route_m is not None and b.route_m is not None else 250.0
    gap = abs((a.taken_at - b.taken_at).total_seconds()) / 60.0
    return {
        "cosine": cos,
        "route_km": route_m / 1000.0,
        "log_gap_min": math.log1p(gap),
        "same_pass": 1.0 if a.pass_no == b.pass_no else 0.0,
        "colour_chi2": chi_square(a.color_hist, b.color_hist),
    }


def candidate_pairs(sightings: list[Sighting], rules: CandidateRules | None = None) -> list[tuple[str, str]]:
    """Pairs worth scoring, ordered (a < b). Detections in the same photo are never the same dog.

    Within a pass: close in time or along the route (side then head shot, or a dog met twice).
    Across passes: within a spatial gate along the route. Then each sighting keeps its top-k
    most similar partners by cosine, so a large survey stays tractable.
    """
    r = rules or CandidateRules()
    n = len(sightings)
    if n < 2:
        return []
    emb = np.stack([s.embedding for s in sightings]).astype(np.float32)
    sims = emb @ emb.T
    keep: set[tuple[int, int]] = set()
    for i in range(n):
        a = sightings[i]
        options: list[tuple[float, int]] = []
        for j in range(n):
            if i == j:
                continue
            b = sightings[j]
            if a.photo_id == b.photo_id:
                continue
            route = abs(a.route_m - b.route_m) if a.route_m is not None and b.route_m is not None else None
            if a.pass_no == b.pass_no:
                gap = abs((a.taken_at - b.taken_at).total_seconds()) / 60.0
                near = gap <= r.within_pass_gap_min or (route is not None and route <= r.within_pass_route_m)
                if not near:
                    continue
                if gap <= 1.0:
                    keep.add((min(i, j), max(i, j)))
                    continue
            elif route is not None and route > r.across_pass_route_m:
                continue
            if sims[i, j] >= r.min_cosine:
                options.append((float(sims[i, j]), j))
        for _, j in sorted(options, reverse=True)[: r.top_k]:
            keep.add((min(i, j), max(i, j)))
    out: list[tuple[str, str]] = []
    for i, j in sorted(keep):
        id_a, id_b = sightings[i].id, sightings[j].id
        out.append((id_a, id_b) if id_a < id_b else (id_b, id_a))
    return out


@dataclass(frozen=True, slots=True)
class MatchModel:
    """Logistic regression on standardised features."""

    mean: tuple[float, ...]
    scale: tuple[float, ...]
    coef: tuple[float, ...]
    intercept: float
    trained_on: int
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def version(self) -> str:
        blob = json.dumps([self.mean, self.scale, self.coef, self.intercept], sort_keys=True).encode()
        return "match-lr-" + hashlib.sha256(blob).hexdigest()[:12]

    def predict(self, x: FloatArray) -> FloatArray:
        z = ((x - np.array(self.mean)) / np.array(self.scale)) @ np.array(self.coef) + self.intercept
        out: FloatArray = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        return out

    def to_json(self) -> dict[str, object]:
        return {
            "kind": "match_lr",
            "features": list(FEATURES),
            "mean": list(self.mean),
            "scale": list(self.scale),
            "coef": list(self.coef),
            "intercept": self.intercept,
            "trained_on": self.trained_on,
            "metrics": self.metrics,
            "version": self.version,
        }

    @staticmethod
    def from_json(d: dict[str, object]) -> MatchModel:
        if list(d["features"]) != list(FEATURES):  # type: ignore[call-overload]
            raise ValueError("stored match model uses different features")
        return MatchModel(
            tuple(d["mean"]),  # type: ignore[arg-type]
            tuple(d["scale"]),  # type: ignore[arg-type]
            tuple(d["coef"]),  # type: ignore[arg-type]
            float(d["intercept"]),  # type: ignore[arg-type]
            int(d["trained_on"]),  # type: ignore[call-overload]
            dict(d.get("metrics") or {}),  # type: ignore[call-overload]
        )


def feature_matrix(rows: list[dict[str, float]]) -> FloatArray:
    return np.array([[r[f] for f in FEATURES] for r in rows], dtype=np.float64).reshape(-1, len(FEATURES))


# Hand-set prior used only until the team's labels exist: similarity dominates, nearby and
# same-colour helps. Its outputs are labelled "uncalibrated" everywhere they are shown.
PRIOR = MatchModel(
    mean=(0.6, 0.1, 5.0, 0.5, 0.5),
    scale=(0.15, 0.1, 2.5, 0.5, 0.3),
    coef=(2.2, -0.6, -0.3, 0.0, -0.8),
    intercept=-1.0,
    trained_on=0,
    metrics={"uncalibrated": 1.0},
)


@dataclass(frozen=True, slots=True)
class Evaluation:
    auc: float
    brier: float
    n_train: int
    n_test: int
    positives: int
    reliability: list[tuple[float, float, int]]


def reliability_bins(p: FloatArray, y: npt.NDArray[np.int_], bins: int = 5) -> list[tuple[float, float, int]]:
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in itertools.pairwise(edges):
        sel = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if sel.any():
            out.append((float(p[sel].mean()), float(y[sel].mean()), int(sel.sum())))
    return out


def fit(
    x: FloatArray, y: npt.NDArray[np.int_], seed: int = 0, test_size: float = 0.25
) -> tuple[MatchModel, Evaluation]:
    """Fit on a stratified 75% split, report AUC, Brier and reliability on the held-out 25%, then
    refit on everything for the stored model (the reported metrics stay the held-out ones)."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from sklearn.model_selection import train_test_split

    if len(set(y.tolist())) < 2:
        raise ValueError("need both same-dog and different-dog labels to fit")
    xtr, xte, ytr, yte = train_test_split(x, y, test_size=test_size, random_state=seed, stratify=y)

    def _fit(xa: FloatArray, ya: npt.NDArray[np.int_]) -> MatchModel:
        mean = xa.mean(axis=0)
        scale = np.where(xa.std(axis=0) > 1e-9, xa.std(axis=0), 1.0)
        lr = LogisticRegression(C=1.0, max_iter=1000).fit((xa - mean) / scale, ya)
        return MatchModel(
            tuple(float(v) for v in mean),
            tuple(float(v) for v in scale),
            tuple(float(v) for v in lr.coef_[0]),
            float(lr.intercept_[0]),
            len(ya),
        )

    held = _fit(xtr, ytr)
    p = held.predict(xte)
    ev = Evaluation(
        auc=float(roc_auc_score(yte, p)),
        brier=float(brier_score_loss(yte, p)),
        n_train=len(ytr),
        n_test=len(yte),
        positives=int(y.sum()),
        reliability=reliability_bins(p, yte),
    )
    final = _fit(x, y)
    final = MatchModel(
        final.mean,
        final.scale,
        final.coef,
        final.intercept,
        final.trained_on,
        {"heldout_auc": ev.auc, "heldout_brier": ev.brier, "n_test": float(ev.n_test)},
    )
    return final, ev

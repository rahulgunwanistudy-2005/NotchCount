"""Ear-notch classifier (BIBLE 5.4): notched, not notched, ear not visible.

Multinomial logistic regression with balanced class weights on the DINOv2 embedding of the head
crop (side crop when no head shot exists). Calls whose top probability is below the review
threshold go to a person. If held-out accuracy is weak the model only pre-sorts; humans decide.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

CLASSES = ("notched", "not_notched", "not_visible")
FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class NotchModel:
    coef: tuple[tuple[float, ...], ...]
    intercept: tuple[float, ...]
    trained_on: int
    metrics: dict[str, object] = field(default_factory=dict)

    @property
    def version(self) -> str:
        blob = json.dumps([self.coef, self.intercept]).encode()
        return "notch-lr-" + hashlib.sha256(blob).hexdigest()[:12]

    def predict(self, x: FloatArray) -> FloatArray:
        z = x @ np.array(self.coef).T + np.array(self.intercept)
        z -= z.max(axis=1, keepdims=True)
        e = np.exp(z)
        out: FloatArray = e / e.sum(axis=1, keepdims=True)
        return out

    def to_json(self) -> dict[str, object]:
        return {
            "kind": "notch_lr",
            "classes": list(CLASSES),
            "coef": [list(r) for r in self.coef],
            "intercept": list(self.intercept),
            "trained_on": self.trained_on,
            "metrics": self.metrics,
            "version": self.version,
        }

    @staticmethod
    def from_json(d: dict[str, object]) -> NotchModel:
        if list(d["classes"]) != list(CLASSES):  # type: ignore[call-overload]
            raise ValueError("stored notch model uses different classes")
        return NotchModel(
            tuple(tuple(float(v) for v in row) for row in d["coef"]),  # type: ignore[attr-defined]
            tuple(float(v) for v in d["intercept"]),  # type: ignore[attr-defined]
            int(d["trained_on"]),  # type: ignore[call-overload]
            dict(d.get("metrics") or {}),  # type: ignore[call-overload]
        )


def fit(x: FloatArray, labels: list[str], seed: int = 0) -> tuple[NotchModel, dict[str, object]]:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, confusion_matrix
    from sklearn.model_selection import train_test_split

    y = np.array([CLASSES.index(lab) for lab in labels])
    present = sorted(set(y.tolist()))
    if len(present) < 2:
        raise ValueError("need at least two different ear labels to fit")
    stratify = y if min(np.bincount(y)[present]) >= 2 else None
    xtr, xte, ytr, yte = train_test_split(x, y, test_size=0.25, random_state=seed, stratify=stratify)

    def _fit(xa: FloatArray, ya: npt.NDArray[np.int_]) -> NotchModel:
        lr = LogisticRegression(C=0.5, max_iter=2000, class_weight="balanced").fit(xa, ya)
        coef = np.zeros((len(CLASSES), xa.shape[1]))
        icpt = np.full(len(CLASSES), -30.0)
        for row, cls in enumerate(lr.classes_):
            if len(lr.classes_) == 2:
                # Binary sklearn models carry one row; expand to two symmetric logits.
                sign = 1.0 if row == 1 else -1.0
                coef[cls] = sign * lr.coef_[0] / 2
                icpt[cls] = sign * lr.intercept_[0] / 2
            else:
                coef[cls] = lr.coef_[row]
                icpt[cls] = lr.intercept_[row]
        return NotchModel(tuple(tuple(r) for r in coef.tolist()), tuple(icpt.tolist()), len(ya))

    held = _fit(xtr, ytr)
    pred = held.predict(xte).argmax(axis=1)
    metrics: dict[str, object] = {
        "heldout_accuracy": float(accuracy_score(yte, pred)),
        "confusion": confusion_matrix(yte, pred, labels=list(range(len(CLASSES)))).tolist(),
        "n_test": len(yte),
        "n_train": len(ytr),
        "label_counts": {c: int((y == i).sum()) for i, c in enumerate(CLASSES)},
    }
    final = _fit(x, y)
    return NotchModel(final.coef, final.intercept, final.trained_on, metrics), metrics

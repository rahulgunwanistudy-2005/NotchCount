"""Survey-level inputs to the estimator: sightings, candidate match pairs and notch calls.

These are plain value types; the API layer builds them from the database and the simulation
harness builds them from synthetic populations. Nothing here touches I/O.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum


class NotchClass(StrEnum):
    NOTCHED = "notched"
    NOT_NOTCHED = "not_notched"
    NOT_VISIBLE = "not_visible"


@dataclass(frozen=True, slots=True)
class NotchCall:
    """Calibrated three-way probabilities for one sighting, optionally fixed by a reviewer."""

    p_notched: float
    p_not_notched: float
    p_not_visible: float
    decision: NotchClass | None = None

    def __post_init__(self) -> None:
        probs = (self.p_notched, self.p_not_notched, self.p_not_visible)
        if any(p < 0 or p > 1 for p in probs) or abs(sum(probs) - 1.0) > 1e-6:
            raise ValueError(f"notch probabilities must be in [0, 1] and sum to 1, got {probs}")

    @staticmethod
    def decided(cls: NotchClass) -> NotchCall:
        p = {c: 1.0 if c is cls else 0.0 for c in NotchClass}
        return NotchCall(p[NotchClass.NOTCHED], p[NotchClass.NOT_NOTCHED], p[NotchClass.NOT_VISIBLE], cls)


@dataclass(frozen=True, slots=True)
class Sighting:
    id: str
    pass_no: int
    notch: NotchCall | None = None


@dataclass(frozen=True, slots=True)
class CandidatePair:
    """P(a and b are the same dog). A reviewer decision overrides the probability."""

    a: str
    b: str
    p_same: float
    decision: bool | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.p_same <= 1.0:
            raise ValueError(f"p_same must be in [0, 1], got {self.p_same}")
        if self.a == self.b:
            raise ValueError("a pair needs two different sightings")

    @property
    def resolved_p(self) -> float:
        if self.decision is None:
            return self.p_same
        return 1.0 if self.decision else 0.0


@dataclass(frozen=True, slots=True)
class SurveyData:
    sightings: tuple[Sighting, ...]
    pairs: tuple[CandidatePair, ...]
    pass_numbers: tuple[int, ...] = field(default=())

    def __post_init__(self) -> None:
        ids = [s.id for s in self.sightings]
        if len(set(ids)) != len(ids):
            raise ValueError("sighting ids must be unique")
        known = set(ids)
        for p in self.pairs:
            if p.a not in known or p.b not in known:
                raise ValueError(f"pair ({p.a}, {p.b}) refers to an unknown sighting")
        if not self.pass_numbers:
            object.__setattr__(self, "pass_numbers", tuple(sorted({s.pass_no for s in self.sightings})))

    def data_hash(self) -> str:
        """Order-independent SHA-256 of everything the estimate depends on."""
        payload = {
            "sightings": sorted(
                (
                    {
                        "id": s.id,
                        "pass_no": s.pass_no,
                        "notch": None if s.notch is None else asdict(s.notch),
                    }
                    for s in self.sightings
                ),
                key=lambda d: str(d["id"]),
            ),
            "pairs": sorted(
                (
                    {"a": min(p.a, p.b), "b": max(p.a, p.b), "p": round(p.p_same, 9), "d": p.decision}
                    for p in self.pairs
                ),
                key=lambda d: (str(d["a"]), str(d["b"])),
            ),
            "passes": list(self.pass_numbers),
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode()).hexdigest()

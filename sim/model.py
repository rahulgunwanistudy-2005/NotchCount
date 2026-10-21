"""Synthetic surveys with a known truth, pushed through the same estimator code as real data.

Everything in this module is SYNTHETIC. It exists to measure bias and interval coverage
(BIBLE 3.8); none of its numbers describe a real street.

Matcher model: each pass-2 sighting is a candidate pair with its true pass-1 partner (if that
dog was seen in pass 1) and with `decoys` random other pass-1 dogs. A pair's score comes from a
two-component mixture for true pairs and for decoys; the matcher reports the exact posterior
P(same | score), so it is calibrated by construction, the way a logistic model fitted to
labelled pairs aims to be. "False split" = a true pair the matcher scores below 0.5;
"false merge" = a pass-2 dog whose best decoy scores above 0.5.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from notchcount_stats import CandidatePair, NotchCall, NotchClass, Sighting, SurveyData

SD = 0.5
CLEAR_TRUE, AMBIGUOUS, CLEAR_DECOY, LOOKALIKE = 3.0, 0.6, 0.0, 2.4


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    n: int
    p: float
    beta: tuple[float, float] | None = None
    false_split: float = 0.0
    false_merge: float = 0.0
    modelled: bool = True
    notch_prevalence: float = 0.55
    ear_hidden: float = 0.2
    decoys: int = 3
    matching: str = "assignment"
    note: str = ""


SCENARIOS = (
    Scenario("S1", 60, 0.6, note="coverage about 0.95"),
    Scenario("S2", 60, 0.6, beta=(2.0, 1.33), note="heterogeneous catchability: negative bias expected"),
    Scenario("S3", 60, 0.6, false_split=0.05, note="5% false splits, modelled: coverage at least 0.93"),
    Scenario("S4", 60, 0.6, false_merge=0.05, note="5% false merges, modelled: coverage at least 0.93"),
    Scenario("S5", 15, 0.5, note="small population: wide intervals, m2 = 0 rate reported"),
    Scenario("S6", 60, 0.6, false_split=0.05, modelled=False, note="5% false splits, hard decisions"),
    Scenario(
        "S3p", 60, 0.6, false_split=0.05, matching="pairwise", note="S3 with the BIBLE pairwise sampler"
    ),
    Scenario(
        "S4p", 60, 0.6, false_merge=0.05, matching="pairwise", note="S4 with the BIBLE pairwise sampler"
    ),
)


def _normal_pdf(x: float, mu: float) -> float:
    return math.exp(-0.5 * ((x - mu) / SD) ** 2) / (SD * math.sqrt(2 * math.pi))


@dataclass(frozen=True, slots=True)
class Matcher:
    split: float
    merge_per_decoy: float

    def true_density(self, s: float) -> float:
        return (1 - self.split) * _normal_pdf(s, CLEAR_TRUE) + self.split * _normal_pdf(s, AMBIGUOUS)

    def decoy_density(self, s: float) -> float:
        m = self.merge_per_decoy
        return (1 - m) * _normal_pdf(s, CLEAR_DECOY) + m * _normal_pdf(s, LOOKALIKE)

    def sample(self, rng: np.random.Generator, is_true: bool) -> float:
        if is_true:
            mu = AMBIGUOUS if rng.random() < self.split else CLEAR_TRUE
        else:
            mu = LOOKALIKE if rng.random() < self.merge_per_decoy else CLEAR_DECOY
        return float(rng.normal(mu, SD))

    def posterior(self, s: float, prior_true: float) -> float:
        a = prior_true * self.true_density(s)
        b = (1 - prior_true) * self.decoy_density(s)
        return a / (a + b) if a + b > 0 else 0.0


@dataclass(frozen=True, slots=True)
class Truth:
    n: int
    notched_share: float


def simulate(sc: Scenario, rng: np.random.Generator) -> tuple[SurveyData, Truth]:
    if sc.beta is not None:
        a, b = sc.beta
        catch = rng.beta(a, b, sc.n)
    else:
        catch = np.full(sc.n, sc.p)
    notched = rng.random(sc.n) < sc.notch_prevalence
    seen1 = np.flatnonzero(rng.random(sc.n) < catch)
    seen2 = np.flatnonzero(rng.random(sc.n) < catch)

    def call(dog: int) -> NotchCall:
        if rng.random() < sc.ear_hidden:
            return NotchCall.decided(NotchClass.NOT_VISIBLE)
        return NotchCall.decided(NotchClass.NOTCHED if notched[dog] else NotchClass.NOT_NOTCHED)

    sightings = [Sighting(f"a{d}", 1, call(d)) for d in seen1] + [
        Sighting(f"b{d}", 2, call(d)) for d in seen2
    ]
    perfect = sc.false_split == 0 and sc.false_merge == 0
    matcher = Matcher(sc.false_split, sc.false_merge / sc.decoys)
    set1 = set(seen1.tolist())
    candidates: list[tuple[int, int, bool]] = []
    for d in seen2:
        if d in set1:
            candidates.append((int(d), int(d), True))
        others = [x for x in seen1 if x != d]
        for x in rng.choice(others, size=min(sc.decoys, len(others)), replace=False) if others else []:
            candidates.append((int(x), int(d), False))
    prior = sum(c[2] for c in candidates) / len(candidates) if candidates else 0.0

    pairs: list[CandidatePair] = []
    for a1, b2, is_true in candidates:
        if perfect:
            pairs.append(CandidatePair(f"a{a1}", f"b{b2}", 1.0 if is_true else 0.0, decision=is_true))
            continue
        p = matcher.posterior(matcher.sample(rng, is_true), prior)
        if not sc.modelled:
            pairs.append(CandidatePair(f"a{a1}", f"b{b2}", p, decision=p > 0.5))
        else:
            pairs.append(CandidatePair(f"a{a1}", f"b{b2}", p))
    data = SurveyData(tuple(sightings), tuple(pairs), pass_numbers=(1, 2))
    return data, Truth(sc.n, float(notched.mean()))

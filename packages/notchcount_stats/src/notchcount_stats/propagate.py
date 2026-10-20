"""Carry match and notch uncertainty into the population, share and deficit (BIBLE 3.4).

Each replicate samples a match configuration from the calibrated pair probabilities, repairs it
to a valid partition, samples notch status per individual, then draws N* from the Chao
log-normal for that configuration and s* from a Jeffreys Beta. Reviewer decisions are fixed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import numpy.typing as npt

from notchcount_stats.closed import EstimateStatus, PopulationEstimate, chao_lognormal_sigma, chapman
from notchcount_stats.partition import Link, build_partition
from notchcount_stats.proportion import COVERAGE_BENCHMARK, ShareEstimate, sterilised_share
from notchcount_stats.survey import NotchCall, NotchClass, SurveyData

FloatArray = npt.NDArray[np.float64]

DEFAULT_REPLICATES = 2000
# Above this fraction of replicates with no recaptures, no population range is reported.
MAX_NO_RECAPTURE_FRACTION = 0.5


class EstimateMode(StrEnum):
    SINGLE_PASS = "single_pass"
    TWO_PASS = "two_pass"


@dataclass(frozen=True, slots=True)
class Summary:
    median: float
    low: float
    high: float

    @staticmethod
    def of(values: FloatArray) -> Summary | None:
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            return None
        lo, med, hi = np.percentile(finite, [2.5, 50.0, 97.5])
        return Summary(float(med), float(lo), float(hi))


@dataclass(frozen=True, slots=True)
class Counts:
    n1: int
    n2: int
    m2: int

    @property
    def distinct(self) -> int:
        return self.n1 + self.n2 - self.m2


@dataclass(frozen=True, slots=True)
class TwoPassEstimate:
    mode: EstimateMode
    replicates: int
    seed: int
    target_share: float
    point_counts: Counts
    point_population: PopulationEstimate
    point_share: ShareEstimate
    population: Summary | None
    share: Summary | None
    deficit: Summary | None
    no_recapture_fraction: float
    no_visible_ear_fraction: float
    data_hash: str


@dataclass(frozen=True, slots=True)
class SinglePassEstimate:
    mode: EstimateMode
    pass_no: int
    individuals: int
    point_share: ShareEstimate
    data_hash: str


_CLASS_ORDER = (NotchClass.NOTCHED, NotchClass.NOT_NOTCHED, NotchClass.NOT_VISIBLE)


def _individual_status(classes: list[NotchClass]) -> NotchClass:
    """A seen notch wins (a cut ear cannot be faked by pose); else any visible unnotched ear."""
    if NotchClass.NOTCHED in classes:
        return NotchClass.NOTCHED
    if NotchClass.NOT_NOTCHED in classes:
        return NotchClass.NOT_NOTCHED
    return NotchClass.NOT_VISIBLE


def _point_class(call: NotchCall | None) -> NotchClass:
    if call is None:
        return NotchClass.NOT_VISIBLE
    if call.decision is not None:
        return call.decision
    probs = (call.p_notched, call.p_not_notched, call.p_not_visible)
    return _CLASS_ORDER[int(np.argmax(probs))]


class _Prepared:
    """Arrays reused across replicates."""

    def __init__(self, data: SurveyData) -> None:
        self.pass_of = {s.id: s.pass_no for s in data.sightings}
        order = sorted(
            range(len(data.pairs)),
            key=lambda i: (-data.pairs[i].resolved_p, data.pairs[i].a, data.pairs[i].b),
        )
        self.pairs = [data.pairs[i] for i in order]
        self.p = np.array([p.resolved_p for p in self.pairs], dtype=np.float64)
        self.sighting_ids = [s.id for s in data.sightings]
        calls = [s.notch for s in data.sightings]
        # A sighting without a notch call counts as "ear not visible".
        probs = np.array(
            [
                (0.0, 0.0, 1.0) if c is None else (c.p_notched, c.p_not_notched, c.p_not_visible)
                for c in calls
            ],
            dtype=np.float64,
        ).reshape(-1, 3)
        self.notch_cum = np.cumsum(probs, axis=1)
        self.point_classes = [_point_class(c) for c in calls]

    def partition(self, same_mask: npt.NDArray[np.bool_]) -> list[frozenset[str]]:
        same = [Link(pair.a, pair.b, float(self.p[i])) for i, pair in enumerate(self.pairs) if same_mask[i]]
        different = [(pair.a, pair.b) for i, pair in enumerate(self.pairs) if not same_mask[i]]
        return build_partition(self.pass_of, same, different)


def _counts(clusters: list[frozenset[str]], pass_of: dict[str, int], p1: int, p2: int) -> Counts:
    n1 = n2 = m2 = 0
    for members in clusters:
        passes = {pass_of[m] for m in members}
        in1, in2 = p1 in passes, p2 in passes
        n1 += in1
        n2 += in2
        m2 += in1 and in2
    return Counts(n1, n2, m2)


def _share_counts(clusters: list[frozenset[str]], classes: dict[str, NotchClass]) -> tuple[int, int, int]:
    tally = {c: 0 for c in NotchClass}
    for members in clusters:
        tally[_individual_status([classes[m] for m in members])] += 1
    return tally[NotchClass.NOTCHED], tally[NotchClass.NOT_NOTCHED], tally[NotchClass.NOT_VISIBLE]


def estimate_single_pass(data: SurveyData, pass_no: int) -> SinglePassEstimate:
    """Count of individuals seen in one pass and their notch share (no population estimate)."""
    keep = {s.id for s in data.sightings if s.pass_no == pass_no}
    if not keep:
        raise ValueError(f"no sightings in pass {pass_no}")
    sub = SurveyData(
        tuple(s for s in data.sightings if s.id in keep),
        tuple(p for p in data.pairs if p.a in keep and p.b in keep),
    )
    prep = _Prepared(sub)
    clusters = prep.partition(prep.p > 0.5)
    classes = dict(zip(prep.sighting_ids, prep.point_classes, strict=True))
    share = sterilised_share(*_share_counts(clusters, classes))
    return SinglePassEstimate(EstimateMode.SINGLE_PASS, pass_no, len(clusters), share, sub.data_hash())


def estimate_two_pass(
    data: SurveyData,
    *,
    replicates: int = DEFAULT_REPLICATES,
    seed: int = 0,
    target_share: float = COVERAGE_BENCHMARK,
) -> TwoPassEstimate:
    if len(data.pass_numbers) != 2:
        raise ValueError(f"two-pass estimate needs exactly two passes, got {data.pass_numbers}")
    if replicates < 1:
        raise ValueError("replicates must be positive")
    p1, p2 = data.pass_numbers
    prep = _Prepared(data)
    rng = np.random.default_rng(seed)

    point_clusters = prep.partition(prep.p > 0.5)
    point_counts = _counts(point_clusters, prep.pass_of, p1, p2)
    point_pop = chapman(point_counts.n1, point_counts.n2, point_counts.m2)
    point_classes = dict(zip(prep.sighting_ids, prep.point_classes, strict=True))
    point_share = sterilised_share(*_share_counts(point_clusters, point_classes))

    n_star = np.full(replicates, np.nan)
    s_star = np.full(replicates, np.nan)
    no_recap = 0
    no_visible = 0
    for b in range(replicates):
        same_mask = rng.random(prep.p.size) < prep.p
        clusters = prep.partition(same_mask)
        counts = _counts(clusters, prep.pass_of, p1, p2)

        u = rng.random(len(prep.sighting_ids))
        idx = (u[:, None] >= prep.notch_cum).sum(axis=1).clip(max=2)
        classes = {sid: _CLASS_ORDER[int(k)] for sid, k in zip(prep.sighting_ids, idx, strict=True)}
        x, not_x, _ = _share_counts(clusters, classes)
        k = x + not_x
        z = rng.standard_normal()
        if k > 0:
            s_star[b] = rng.beta(x + 0.5, not_x + 0.5)
        else:
            no_visible += 1

        if counts.m2 == 0:
            no_recap += 1
            continue
        est = chapman(counts.n1, counts.n2, counts.m2)
        assert est.n_hat is not None and est.variance is not None
        sigma = chao_lognormal_sigma(est.n_hat, est.variance, counts.distinct)
        f0 = est.n_hat - counts.distinct
        n_star[b] = counts.distinct if sigma is None else counts.distinct + f0 * math.exp(sigma * z)

    no_recap_frac = no_recap / replicates
    population = None if no_recap_frac > MAX_NO_RECAPTURE_FRACTION else Summary.of(n_star)
    deficit_vals = np.maximum(0.0, (target_share - s_star) * n_star)
    deficit = None if population is None else Summary.of(deficit_vals)
    if point_pop.status is EstimateStatus.NO_RECAPTURES:
        population, deficit = None, None
    return TwoPassEstimate(
        mode=EstimateMode.TWO_PASS,
        replicates=replicates,
        seed=seed,
        target_share=target_share,
        point_counts=point_counts,
        point_population=point_pop,
        point_share=point_share,
        population=population,
        share=Summary.of(s_star),
        deficit=deficit,
        no_recapture_fraction=no_recap_frac,
        no_visible_ear_fraction=no_visible / replicates,
        data_hash=data.data_hash(),
    )

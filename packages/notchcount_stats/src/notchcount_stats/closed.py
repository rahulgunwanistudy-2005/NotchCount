"""Closed-population mark-resight estimators: Chapman (two passes) and Schnabel (k passes).

Formulas follow docs/BIBLE.md sections 3.2 and 3.3. Every function here is pure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

Z95 = 1.959963984540054


class EstimateStatus(StrEnum):
    OK = "ok"
    NO_RECAPTURES = "no_recaptures"
    ALL_RECAPTURED = "all_recaptured"


class InvalidCounts(ValueError):
    """Counts that cannot come from a real survey (negative, or more recaptures than sightings)."""


@dataclass(frozen=True, slots=True)
class PopulationEstimate:
    status: EstimateStatus
    distinct_seen: int
    n_hat: float | None
    variance: float | None
    ci_low: float | None
    ci_high: float | None

    @property
    def se(self) -> float | None:
        return None if self.variance is None else math.sqrt(self.variance)


def _check_two_sample(n1: int, n2: int, m2: int) -> None:
    if min(n1, n2, m2) < 0:
        raise InvalidCounts(f"counts must be non-negative, got n1={n1} n2={n2} m2={m2}")
    if m2 > min(n1, n2):
        raise InvalidCounts(f"m2={m2} cannot exceed n1={n1} or n2={n2}")


def chapman_point(n1: int, n2: int, m2: int) -> tuple[float, float]:
    """Chapman N-hat and its variance. Defined for m2 = 0 but uninformative there."""
    _check_two_sample(n1, n2, m2)
    n_hat = (n1 + 1) * (n2 + 1) / (m2 + 1) - 1
    var = (n1 + 1) * (n2 + 1) * (n1 - m2) * (n2 - m2) / ((m2 + 1) ** 2 * (m2 + 2))
    return n_hat, var


def chao_lognormal_sigma(n_hat: float, variance: float, distinct_seen: int) -> float | None:
    """Log-scale sigma of the Chao log-normal for the unseen part f0 = N-hat - Mt1.

    Returns None when f0 <= 0 (every dog seen in both passes): the interval collapses to Mt1.
    """
    f0 = n_hat - distinct_seen
    if f0 <= 0:
        return None
    return math.sqrt(math.log1p(variance / (f0 * f0)))


def chao_interval(n_hat: float, variance: float, distinct_seen: int, z: float = Z95) -> tuple[float, float]:
    sigma = chao_lognormal_sigma(n_hat, variance, distinct_seen)
    if sigma is None:
        return float(distinct_seen), float(distinct_seen)
    f0 = n_hat - distinct_seen
    c = math.exp(z * sigma)
    return distinct_seen + f0 / c, distinct_seen + f0 * c


def chapman(n1: int, n2: int, m2: int, z: float = Z95) -> PopulationEstimate:
    """Chapman two-sample estimate with the Chao log-normal interval (never below Mt1)."""
    _check_two_sample(n1, n2, m2)
    mt1 = n1 + n2 - m2
    if m2 == 0:
        return PopulationEstimate(EstimateStatus.NO_RECAPTURES, mt1, None, None, None, None)
    n_hat, var = chapman_point(n1, n2, m2)
    lo, hi = chao_interval(n_hat, var, mt1, z)
    status = EstimateStatus.ALL_RECAPTURED if n_hat - mt1 <= 0 else EstimateStatus.OK
    return PopulationEstimate(status, mt1, n_hat, var, lo, hi)


@dataclass(frozen=True, slots=True)
class SchnabelTerms:
    caught: tuple[int, ...]
    marked_before: tuple[int, ...]
    recaptured: tuple[int, ...]


def schnabel_terms(passes: list[set[str]]) -> SchnabelTerms:
    """C_t, M_t, R_t from per-pass sets of individual ids."""
    seen: set[str] = set()
    caught: list[int] = []
    marked: list[int] = []
    recap: list[int] = []
    for ids in passes:
        caught.append(len(ids))
        marked.append(len(seen))
        recap.append(len(ids & seen))
        seen |= ids
    return SchnabelTerms(tuple(caught), tuple(marked), tuple(recap))


def schnabel(passes: list[set[str]], z: float = Z95) -> PopulationEstimate:
    """Schnabel estimate with the Chapman-style +1 correction.

    The interval treats sum(R_t) as Poisson and inverts it (normal approximation on the
    reciprocal, Krebs 1999 section 2.2); it is clamped below at the number of distinct dogs seen.
    """
    if len(passes) < 2:
        raise InvalidCounts("Schnabel needs at least two passes")
    terms = schnabel_terms(passes)
    distinct = len(set().union(*passes))
    sum_cm = sum(c * m for c, m in zip(terms.caught, terms.marked_before, strict=True))
    sum_r = sum(terms.recaptured)
    if sum_r == 0:
        return PopulationEstimate(EstimateStatus.NO_RECAPTURES, distinct, None, None, None, None)
    n_hat = sum_cm / (sum_r + 1)
    # Delta method: var(N) ~= N^4 * var(1/N), with var(1/N) = sum(R) / sum(CM)^2.
    inv = 1.0 / n_hat
    var_inv = sum_r / sum_cm**2
    var = var_inv / inv**4
    lo_inv = inv + z * math.sqrt(var_inv)
    hi_inv = inv - z * math.sqrt(var_inv)
    lo = max(float(distinct), 1.0 / lo_inv)
    hi = math.inf if hi_inv <= 0 else max(float(distinct), 1.0 / hi_inv)
    status = EstimateStatus.ALL_RECAPTURED if n_hat <= distinct else EstimateStatus.OK
    return PopulationEstimate(status, distinct, n_hat, var, lo, hi)

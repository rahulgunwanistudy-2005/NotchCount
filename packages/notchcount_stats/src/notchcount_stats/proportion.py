"""Sterilised share: Wilson score interval (BIBLE 3.5)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from notchcount_stats.closed import Z95, InvalidCounts

COVERAGE_BENCHMARK = 0.70


@dataclass(frozen=True, slots=True)
class ShareEstimate:
    notched: int
    with_visible_ear: int
    excluded_not_visible: int
    share: float | None
    ci_low: float | None
    ci_high: float | None


def wilson(x: int, k: int, z: float = Z95) -> tuple[float, float, float]:
    """Point share and Wilson score interval for x successes out of k (k > 0)."""
    if k <= 0:
        raise InvalidCounts("Wilson interval needs at least one observation")
    if not 0 <= x <= k:
        raise InvalidCounts(f"x={x} must be between 0 and k={k}")
    p = x / k
    z2 = z * z
    denom = 1 + z2 / k
    centre = (p + z2 / (2 * k)) / denom
    half = z * math.sqrt(p * (1 - p) / k + z2 / (4 * k * k)) / denom
    return p, min(p, max(0.0, centre - half)), max(p, min(1.0, centre + half))


def sterilised_share(notched: int, not_notched: int, not_visible: int) -> ShareEstimate:
    """Share of individuals with a visible ear that carry the notch; hidden ears are excluded."""
    if min(notched, not_notched, not_visible) < 0:
        raise InvalidCounts("counts must be non-negative")
    k = notched + not_notched
    if k == 0:
        return ShareEstimate(notched, 0, not_visible, None, None, None)
    p, lo, hi = wilson(notched, k)
    return ShareEstimate(notched, k, not_visible, p, lo, hi)


def coverage_deficit(population: float, share: float, target: float = COVERAGE_BENCHMARK) -> float:
    """Additional sterilisations needed to reach the target share, never negative."""
    return max(0.0, (target - share) * population)

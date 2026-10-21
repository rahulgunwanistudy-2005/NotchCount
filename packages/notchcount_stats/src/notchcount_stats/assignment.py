"""Assignment-level matching across two passes.

The pairwise sampler (BIBLE 3.4) draws every candidate pair independently and then repairs the
result to one-to-one. That throws probability away: when a walk-2 dog's true partner scores like a
look-alike, calibration moves its probability onto look-alikes, and the repair discards most of it
because those look-alikes already have clear partners. Intervals then come out too narrow (see
docs/ESTIMATOR_VALIDATION.md).

Here each walk-2 dog chooses exactly one of: one of its walk-1 candidates, or "not seen on walk 1".
For a pair with calibrated probability p, drawn from candidates whose base rate of true pairs is
pi, the likelihood ratio of "same dog" to "look-alike" is

    LR = [p / (1 - p)] / [pi / (1 - pi)]

With q = P(a dog was seen on walk 1) = n1 / N and a uniform prior over the K candidates:

    P(partner = a) ∝ (q / K) * LR_a,    P(no partner) ∝ 1 - q

q depends on N, which depends on how many dogs match, so q is found by a fixed-point iteration
on the expected number of matches. Walk-2 dogs then choose in random order, and a walk-1 dog
already taken leaves the choice set (one-to-one by construction, no repair). Reviewer decisions
are fixed: "same" forces the pair and "different" removes it.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from notchcount_stats.partition import Link, build_partition
from notchcount_stats.survey import CandidatePair

P_CLIP = 1e-6


def _odds(p: float) -> float:
    p = min(max(p, P_CLIP), 1 - P_CLIP)
    return p / (1 - p)


@dataclass(frozen=True, slots=True)
class CrossCandidates:
    """Walk-1 options for each walk-2 cluster, at cluster level."""

    lr: dict[int, dict[int, float]]
    forced: dict[int, int]


class AssignmentModel:
    def __init__(self, pass_of: dict[str, int], pairs: list[CandidatePair], p1: int, p2: int) -> None:
        self.pass_of = pass_of
        self.p1, self.p2 = p1, p2
        self.within = [p for p in pairs if pass_of[p.a] == pass_of[p.b]]
        self.cross = [p for p in pairs if pass_of[p.a] != pass_of[p.b]]
        self.within.sort(key=lambda p: (-p.resolved_p, p.a, p.b))
        self.within_p = np.array([p.resolved_p for p in self.within], dtype=np.float64)
        base = [p.p_same for p in self.cross]
        # Calibration means the mean model probability over the candidates is their base rate.
        self.pi = float(np.clip(np.mean(base), 1e-4, 0.5)) if base else 0.0

    def within_partition(self, same_mask: np.ndarray) -> tuple[list[frozenset[str]], list[frozenset[str]]]:
        same = [Link(p.a, p.b, float(self.within_p[i])) for i, p in enumerate(self.within) if same_mask[i]]
        different = [(p.a, p.b) for i, p in enumerate(self.within) if not same_mask[i]]
        clusters = build_partition(self.pass_of, same, different)
        one = sorted((c for c in clusters if self.pass_of[next(iter(c))] == self.p1), key=min)
        two = sorted((c for c in clusters if self.pass_of[next(iter(c))] == self.p2), key=min)
        return one, two

    def candidates(self, one: list[frozenset[str]], two: list[frozenset[str]]) -> CrossCandidates:
        where = {sid: (1, i) for i, c in enumerate(one) for sid in c}
        where |= {sid: (2, j) for j, c in enumerate(two) for sid in c}
        best: dict[tuple[int, int], float] = {}
        banned: set[tuple[int, int]] = set()
        forced: dict[int, int] = {}
        for p in self.cross:
            (pa, ia), (_, ib) = where[p.a], where[p.b]
            i, j = (ia, ib) if pa == 1 else (ib, ia)
            if p.decision is False:
                banned.add((i, j))
            elif p.decision is True:
                forced[j] = i
            else:
                best[(i, j)] = max(best.get((i, j), 0.0), p.p_same)
        lr: dict[int, dict[int, float]] = defaultdict(dict)
        prior_odds = _odds(self.pi) if self.pi > 0 else 1.0
        for (i, j), prob in best.items():
            if (i, j) not in banned and j not in forced:
                lr[j][i] = _odds(prob) / prior_odds
        return CrossCandidates(dict(lr), forced)

    @staticmethod
    def recapture_rate(n1: int, n2: int, cands: CrossCandidates, iterations: int = 60) -> float:
        """q = n1 / N at the fixed point where N is the Chapman estimate from the expected m2."""
        if n1 == 0 or n2 == 0:
            return 0.0
        q = min(0.9, n1 / max(n1 + n2, 1))
        for _ in range(iterations):
            m2 = float(len(cands.forced))
            for options in cands.lr.values():
                k = len(options)
                if k == 0:
                    continue
                mean_lr = sum(options.values()) / k
                m2 += q * mean_lr / ((1 - q) + q * mean_lr)
            n_hat = (n1 + 1) * (n2 + 1) / (m2 + 1) - 1
            new_q = min(0.99, max(1e-3, n1 / max(n_hat, n1)))
            if abs(new_q - q) < 1e-6:
                return new_q
            q = 0.5 * q + 0.5 * new_q
        return q

    def sample_matches(self, cands: CrossCandidates, q: float, rng: np.random.Generator) -> dict[int, int]:
        """Walk-2 cluster index to walk-1 cluster index, one-to-one."""
        taken: set[int] = set()
        out: dict[int, int] = {}
        for j, i in sorted(cands.forced.items()):
            if i not in taken:
                out[j] = i
                taken.add(i)
        order = [j for j in cands.lr if j not in out]
        rng.shuffle(order)
        for j in order:
            options = cands.lr[j]
            k = len(options)
            avail = [(i, lr) for i, lr in sorted(options.items()) if i not in taken]
            if not avail:
                continue
            weights = np.array([1 - q] + [q / k * lr for _, lr in avail], dtype=np.float64)
            total = weights.sum()
            if not math.isfinite(total) or total <= 0:
                continue
            pick = int(rng.choice(len(weights), p=weights / total))
            if pick > 0:
                i = avail[pick - 1][0]
                out[j] = i
                taken.add(i)
        return out


def merge(
    one: list[frozenset[str]], two: list[frozenset[str]], matches: dict[int, int]
) -> list[frozenset[str]]:
    joined = {i: set(c) for i, c in enumerate(one)}
    out: list[frozenset[str]] = []
    for j, c in enumerate(two):
        if j in matches:
            joined[matches[j]] |= c
        else:
            out.append(c)
    return [frozenset(s) for s in joined.values()] + out

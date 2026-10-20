"""Proposed individuals from pair probabilities (BIBLE 5.3).

Within a pass: average-linkage clustering on distance 1 - P, cut at 0.5; a cluster holding a
pair below 0.2 is flagged for review. Across passes: Hungarian assignment between pass clusters
on cost -log P, with a "no match" option priced at -log(0.5). Unscored pairs count as P = 0.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

EPS = 1e-6


@dataclass(frozen=True, slots=True)
class Assignment:
    individuals: list[frozenset[str]]
    flagged_clusters: list[frozenset[str]]


def _p(pairs: dict[tuple[str, str], float], a: str, b: str) -> float:
    return pairs.get((a, b) if a < b else (b, a), 0.0)


def cluster_pass(
    ids: list[str], pairs: dict[tuple[str, str], float], cut: float = 0.5
) -> list[frozenset[str]]:
    if len(ids) <= 1:
        return [frozenset(ids)] if ids else []
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    n = len(ids)
    dist = np.ones((n, n))
    for i in range(n):
        dist[i, i] = 0.0
        for j in range(i + 1, n):
            dist[i, j] = dist[j, i] = 1.0 - _p(pairs, ids[i], ids[j])
    labels = fcluster(linkage(squareform(dist, checks=False), method="average"), t=cut, criterion="distance")
    groups: dict[int, set[str]] = defaultdict(set)
    for sid, lab in zip(ids, labels, strict=True):
        groups[int(lab)].add(sid)
    return [frozenset(g) for g in groups.values()]


def assign(
    pass_of: dict[str, int],
    pairs: dict[tuple[str, str], float],
    cut: float = 0.5,
    review_below: float = 0.2,
    no_match_p: float = 0.5,
) -> Assignment:
    from scipy.optimize import linear_sum_assignment

    by_pass: dict[int, list[str]] = defaultdict(list)
    for sid, pn in sorted(pass_of.items()):
        by_pass[pn].append(sid)
    clusters: dict[int, list[frozenset[str]]] = {
        pn: cluster_pass(ids, pairs, cut) for pn, ids in by_pass.items()
    }
    flagged = [
        c
        for cs in clusters.values()
        for c in cs
        if any(_p(pairs, a, b) < review_below for a in c for b in c if a < b)
    ]

    passes = sorted(clusters)
    if not passes:
        return Assignment([], flagged)
    individuals = [set(c) for c in clusters[passes[0]]]
    for pn in passes[1:]:
        current = clusters[pn]
        m, k = len(individuals), len(current)
        no_match = -math.log(no_match_p)
        cost = np.full((m + k, k + m), no_match)
        for i, ind in enumerate(individuals):
            for j, cl in enumerate(current):
                best = max((_p(pairs, a, b) for a in ind for b in cl), default=0.0)
                cost[i, j] = -math.log(max(best, EPS))
        # Dummy rows and columns let any cluster stay unmatched at the no-match price.
        cost[m:, k:] = 0.0
        rows, cols = linear_sum_assignment(cost)
        matched_cols: set[int] = set()
        for i, j in zip(rows, cols, strict=True):
            if i < m and j < k and cost[i, j] < no_match:
                individuals[i] |= current[j]
                matched_cols.add(j)
        individuals.extend(set(current[j]) for j in range(k) if j not in matched_cols)
    return Assignment([frozenset(i) for i in individuals], flagged)


def m2_influence(
    pass_of: dict[str, int], pairs: dict[tuple[str, str], float]
) -> dict[tuple[str, str], float]:
    """How much a decision on each uncertain cross-pass pair could move m2: higher first in review."""
    out: dict[tuple[str, str], float] = {}
    for (a, b), p in pairs.items():
        if pass_of.get(a) != pass_of.get(b):
            out[(a, b)] = 1.0 + (0.5 - abs(p - 0.5))
        else:
            out[(a, b)] = 0.5 - abs(p - 0.5)
    return out

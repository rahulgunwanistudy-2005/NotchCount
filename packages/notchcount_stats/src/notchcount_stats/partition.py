"""Turn same/different decisions on candidate pairs into a valid partition of sightings.

A valid partition (BIBLE 3.4) is transitive and one-to-one across passes: an individual holds
any number of sightings from one pass (side and head shots, or the same dog met twice), but its
within-pass groups come from distinct passes. Conflicts are settled greedily: links are accepted
in descending score order, within-pass links first, and a link is refused if it would join two
groups that contain an explicit "different" pair or that both already hold a sighting from the
same pass.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Link:
    a: str
    b: str
    score: float


class _Groups:
    def __init__(self, ids: Iterable[str], pass_of: dict[str, int]) -> None:
        self.parent: dict[str, str] = {i: i for i in ids}
        self.members: dict[str, set[str]] = {i: {i} for i in self.parent}
        self.passes: dict[str, set[int]] = {i: {pass_of[i]} for i in self.parent}
        self.forbidden: dict[str, set[str]] = {i: set() for i in self.parent}

    def find(self, x: str) -> str:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def forbid(self, a: str, b: str) -> None:
        self.forbidden[self.find(a)].add(b)
        self.forbidden[self.find(b)].add(a)

    def try_merge(self, a: str, b: str, *, require_disjoint_passes: bool) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return True
        if self.forbidden[ra] & self.members[rb] or self.forbidden[rb] & self.members[ra]:
            return False
        if require_disjoint_passes and self.passes[ra] & self.passes[rb]:
            return False
        if len(self.members[ra]) < len(self.members[rb]):
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.members[ra] |= self.members.pop(rb)
        self.passes[ra] |= self.passes.pop(rb)
        self.forbidden[ra] |= self.forbidden.pop(rb)
        return True

    def clusters(self) -> list[frozenset[str]]:
        return [frozenset(m) for m in self.members.values()]


def build_partition(
    pass_of: dict[str, int],
    same: Sequence[Link],
    different: Iterable[tuple[str, str]],
) -> list[frozenset[str]]:
    """Clusters of sighting ids. `same` must already be sorted by descending score."""
    groups = _Groups(pass_of.keys(), pass_of)
    for a, b in different:
        groups.forbid(a, b)
    within = [link for link in same if pass_of[link.a] == pass_of[link.b]]
    across = [link for link in same if pass_of[link.a] != pass_of[link.b]]
    for link in within:
        groups.try_merge(link.a, link.b, require_disjoint_passes=False)
    for link in across:
        groups.try_merge(link.a, link.b, require_disjoint_passes=True)
    return groups.clusters()

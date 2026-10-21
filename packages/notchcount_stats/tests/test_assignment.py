"""Assignment-level matching (assignment.py). Synthetic fixtures."""

import numpy as np

from notchcount_stats import CandidatePair, NotchCall, NotchClass, Sighting, SurveyData, estimate_two_pass
from notchcount_stats.assignment import AssignmentModel, merge

PLAIN = NotchCall.decided(NotchClass.NOT_NOTCHED)


def _model(pairs: list[CandidatePair], n1: int, n2: int) -> tuple[AssignmentModel, dict[str, int]]:
    pass_of = {f"a{i}": 1 for i in range(n1)} | {f"b{j}": 2 for j in range(n2)}
    return AssignmentModel(pass_of, pairs, 1, 2), pass_of


def test_one_to_one_and_decisions() -> None:
    pairs = [
        CandidatePair("a0", "b0", 0.9),
        CandidatePair("a0", "b1", 0.9),
        CandidatePair("a1", "b2", 0.6, decision=True),
        CandidatePair("a2", "b2", 0.99, decision=False),
    ]
    model, _ = _model(pairs, 3, 3)
    one, two = model.within_partition(np.zeros(0, dtype=bool))
    cands = model.candidates(one, two)
    assert cands.forced == {2: 1}
    assert 2 not in cands.lr
    rng = np.random.default_rng(0)
    for _ in range(200):
        matches = model.sample_matches(cands, 0.7, rng)
        assert matches[2] == 1
        taken = list(matches.values())
        assert len(taken) == len(set(taken))


def test_ambiguous_true_match_keeps_its_probability() -> None:
    """Walk-2 dog b0's true partner a0 scores only 0.05, but b0 has no better option and most
    dogs are recaptured, so b0 should still match a0 in a fair share of draws (the pairwise
    sampler would give it about 5%)."""
    pairs = [CandidatePair("a0", "b0", 0.05)]
    for j in range(1, 20):
        pairs.append(CandidatePair(f"a{j}", f"b{j}", 0.97))
        pairs += [CandidatePair(f"a{(j + k) % 20}", f"b{j}", 0.01) for k in (3, 7, 11)]
    model, _ = _model(pairs, 20, 20)
    one, two = model.within_partition(np.zeros(0, dtype=bool))
    cands = model.candidates(one, two)
    q = model.recapture_rate(len(one), len(two), cands)
    assert q > 0.8
    rng = np.random.default_rng(1)
    b0 = next(j for j, c in enumerate(two) if "b0" in c)
    a0 = next(i for i, c in enumerate(one) if "a0" in c)
    hits = sum(model.sample_matches(cands, q, rng).get(b0) == a0 for _ in range(1000))
    assert hits / 1000 > 0.2


def test_merge_builds_individuals() -> None:
    one = [frozenset({"a0"}), frozenset({"a1"})]
    two = [frozenset({"b0"}), frozenset({"b1"})]
    out = merge(one, two, {1: 0})
    assert frozenset({"a0", "b1"}) in out and frozenset({"b0"}) in out and len(out) == 3


def test_both_samplers_agree_when_everything_is_reviewed() -> None:
    sightings = [Sighting(f"a{i}", 1, PLAIN) for i in range(30)] + [
        Sighting(f"b{i}", 2, PLAIN) for i in range(10, 40)
    ]
    pairs = [CandidatePair(f"a{i}", f"b{i}", 0.9, decision=True) for i in range(10, 30)]
    data = SurveyData(tuple(sightings), tuple(pairs))
    a = estimate_two_pass(data, replicates=400, seed=5, matching="assignment")
    p = estimate_two_pass(data, replicates=400, seed=5, matching="pairwise")
    assert a.population is not None and p.population is not None
    assert abs(a.population.median - p.population.median) < 1.0
    assert a.matching == "assignment"

import time

import pytest

from notchcount_stats import (
    CandidatePair,
    EstimateMode,
    NotchCall,
    NotchClass,
    Sighting,
    SurveyData,
    chapman,
    estimate_single_pass,
    estimate_two_pass,
)
from notchcount_stats.partition import Link, build_partition

NOTCHED = NotchCall.decided(NotchClass.NOTCHED)
PLAIN = NotchCall.decided(NotchClass.NOT_NOTCHED)
HIDDEN = NotchCall.decided(NotchClass.NOT_VISIBLE)


def _worked_example() -> SurveyData:
    """Synthetic: the BIBLE 3.7 counts as fully reviewed sightings (40, 38, 25 recaptured)."""
    sightings: list[Sighting] = []
    pairs: list[CandidatePair] = []
    for i in range(53):
        call = NOTCHED if i < 29 else PLAIN if i < 49 else HIDDEN
        if i < 40:
            sightings.append(Sighting(f"a{i}", 1, call))
        if 15 <= i < 53:
            sightings.append(Sighting(f"b{i}", 2, call))
        if 15 <= i < 40:
            pairs.append(CandidatePair(f"a{i}", f"b{i}", 0.9, decision=True))
    return SurveyData(tuple(sightings), tuple(pairs))


def test_fully_reviewed_survey_reproduces_plain_chapman() -> None:
    data = _worked_example()
    est = estimate_two_pass(data, replicates=400, seed=7)
    assert (est.point_counts.n1, est.point_counts.n2, est.point_counts.m2) == (40, 38, 25)
    assert est.point_population.n_hat == pytest.approx(60.5)
    assert est.population is not None and est.share is not None and est.deficit is not None
    assert est.population.low >= 53
    plain = chapman(40, 38, 25)
    assert plain.ci_low is not None and plain.ci_high is not None
    assert est.population.low == pytest.approx(plain.ci_low, rel=0.06)
    assert est.population.high == pytest.approx(plain.ci_high, rel=0.08)
    assert est.point_share.share == pytest.approx(29 / 49)


def test_same_seed_same_result() -> None:
    data = _worked_example()
    a = estimate_two_pass(data, replicates=200, seed=11)
    b = estimate_two_pass(data, replicates=200, seed=11)
    assert a == b


def test_uncertain_matches_widen_the_range() -> None:
    data = _worked_example()
    loose = SurveyData(
        data.sightings,
        tuple(CandidatePair(p.a, p.b, 0.75) for p in data.pairs),
    )
    tight = estimate_two_pass(data, replicates=600, seed=3)
    wide = estimate_two_pass(loose, replicates=600, seed=3)
    assert tight.population is not None and wide.population is not None
    assert wide.population.high - wide.population.low > tight.population.high - tight.population.low


def test_no_recaptures_reports_no_population() -> None:
    s = (Sighting("a", 1, PLAIN), Sighting("b", 2, NOTCHED))
    est = estimate_two_pass(SurveyData(s, (CandidatePair("a", "b", 0.1),)), replicates=100)
    assert est.population is None and est.deficit is None
    assert est.share is not None


def test_single_pass_counts_individuals_and_groups_two_shots() -> None:
    s = (Sighting("x1", 1, None), Sighting("x2", 1, NOTCHED), Sighting("y", 1, PLAIN))
    pairs = (CandidatePair("x1", "x2", 0.95), CandidatePair("x1", "y", 0.05))
    est = estimate_single_pass(SurveyData(s, pairs), pass_no=1)
    assert est.mode is EstimateMode.SINGLE_PASS
    assert est.individuals == 2
    assert est.point_share.notched == 1 and est.point_share.with_visible_ear == 2


def test_partition_is_one_to_one_across_passes() -> None:
    pass_of = {"a1": 1, "a2": 1, "b1": 2}
    links = [Link("a1", "b1", 0.9), Link("a2", "b1", 0.8)]
    clusters = build_partition(pass_of, links, different=[("a1", "a2")])
    assert sorted(len(c) for c in clusters) == [1, 2]
    assert frozenset({"a1", "b1"}) in clusters


def test_partition_respects_explicit_different() -> None:
    pass_of = {"a": 1, "b": 1, "c": 1}
    clusters = build_partition(pass_of, [Link("a", "b", 0.9), Link("b", "c", 0.8)], different=[("a", "c")])
    assert frozenset({"a", "b"}) in clusters and frozenset({"c"}) in clusters


def test_two_thousand_replicates_fit_the_budget() -> None:
    data = _worked_example()
    start = time.perf_counter()
    estimate_two_pass(data, replicates=2000, seed=1)
    assert time.perf_counter() - start < 10.0


def test_data_hash_ignores_order() -> None:
    data = _worked_example()
    shuffled = SurveyData(tuple(reversed(data.sightings)), tuple(reversed(data.pairs)))
    assert data.data_hash() == shuffled.data_hash()

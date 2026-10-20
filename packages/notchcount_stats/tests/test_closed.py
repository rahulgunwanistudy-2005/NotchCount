import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from notchcount_stats import (
    EstimateStatus,
    InvalidCounts,
    chapman,
    chapman_point,
    coverage_deficit,
    schnabel,
    sterilised_share,
    wilson,
)


def test_bible_worked_example_population() -> None:
    est = chapman(40, 38, 25)
    assert est.status is EstimateStatus.OK
    assert est.distinct_seen == 53
    assert est.n_hat == pytest.approx(60.5)
    assert est.variance == pytest.approx(17.083, abs=1e-3)
    assert est.se == pytest.approx(4.133, abs=1e-3)
    assert est.ci_low == pytest.approx(55.7, abs=0.05)
    assert est.ci_high == pytest.approx(73.6, abs=0.05)


def test_bible_worked_example_share_and_deficit() -> None:
    share = sterilised_share(notched=29, not_notched=20, not_visible=4)
    assert share.with_visible_ear == 49
    assert share.excluded_not_visible == 4
    assert share.share == pytest.approx(0.592, abs=5e-4)
    assert share.ci_low == pytest.approx(0.452, abs=5e-4)
    assert share.ci_high == pytest.approx(0.718, abs=5e-4)
    assert coverage_deficit(60.5, 29 / 49) == pytest.approx(6.55, abs=0.01)


def test_no_recaptures_gives_no_estimate() -> None:
    est = chapman(12, 9, 0)
    assert est.status is EstimateStatus.NO_RECAPTURES
    assert est.n_hat is None and est.ci_low is None
    assert est.distinct_seen == 21


def test_everyone_recaptured_collapses_to_count() -> None:
    est = chapman(10, 10, 10)
    assert est.status is EstimateStatus.ALL_RECAPTURED
    assert est.ci_low == est.ci_high == 10


@pytest.mark.parametrize("n1,n2,m2", [(-1, 3, 0), (3, 2, 3), (2, 5, 4)])
def test_impossible_counts_rejected(n1: int, n2: int, m2: int) -> None:
    with pytest.raises(InvalidCounts):
        chapman(n1, n2, m2)


def test_wilson_rejects_empty_and_out_of_range() -> None:
    with pytest.raises(InvalidCounts):
        wilson(0, 0)
    with pytest.raises(InvalidCounts):
        wilson(5, 4)


def test_share_with_all_ears_hidden() -> None:
    share = sterilised_share(0, 0, 7)
    assert share.share is None
    assert share.excluded_not_visible == 7


def test_schnabel_two_passes_matches_lincoln_form() -> None:
    p1 = {f"d{i}" for i in range(40)}
    p2 = {f"d{i}" for i in range(15, 53)}
    est = schnabel([p1, p2])
    assert est.n_hat == pytest.approx(40 * 38 / (25 + 1))


def test_schnabel_needs_two_passes() -> None:
    with pytest.raises(InvalidCounts):
        schnabel([{"a"}])


counts = (
    st.tuples(st.integers(0, 200), st.integers(0, 200))
    .flatmap(lambda t: st.tuples(st.just(t[0]), st.just(t[1]), st.integers(1, max(1, min(t)))))
    .filter(lambda t: t[2] <= min(t[0], t[1]))
)


@given(counts)
def test_estimate_never_below_distinct_and_interval_contains_point(t: tuple[int, int, int]) -> None:
    n1, n2, m2 = t
    est = chapman(n1, n2, m2)
    assert est.n_hat is not None and est.ci_low is not None and est.ci_high is not None
    assert est.n_hat >= est.distinct_seen - 1e-9
    assert est.ci_low >= est.distinct_seen - 1e-9
    assert est.ci_low - 1e-9 <= est.n_hat <= est.ci_high + 1e-9


@given(counts)
def test_estimate_non_increasing_in_recaptures(t: tuple[int, int, int]) -> None:
    n1, n2, m2 = t
    if m2 + 1 > min(n1, n2):
        return
    a, _ = chapman_point(n1, n2, m2)
    b, _ = chapman_point(n1, n2, m2 + 1)
    assert b <= a + 1e-9


@given(st.integers(1, 500).flatmap(lambda k: st.tuples(st.integers(0, k), st.just(k))))
def test_wilson_interval_is_ordered_and_bounded(t: tuple[int, int]) -> None:
    x, k = t
    p, lo, hi = wilson(x, k)
    assert 0.0 <= lo <= p <= hi <= 1.0
    assert not math.isnan(lo + hi)

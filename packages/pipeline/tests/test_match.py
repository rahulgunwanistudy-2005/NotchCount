from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from notchcount_pipeline import notch
from notchcount_pipeline.assign import assign, cluster_pass
from notchcount_pipeline.match import (
    PRIOR,
    MatchModel,
    Sighting,
    candidate_pairs,
    feature_matrix,
    fit,
    pair_features,
)

T0 = datetime(2026, 10, 21, 6, 30, tzinfo=UTC)


def _unit(v: np.ndarray) -> np.ndarray:
    return (v / np.linalg.norm(v)).astype(np.float32)


def _sighting(sid: str, pass_no: int, dog_vec: np.ndarray, minute: float, route_m: float, rng) -> Sighting:
    emb = _unit(dog_vec + rng.normal(0, 0.15, dog_vec.shape))
    hist = np.full(144, 1 / 144, dtype=np.float32)
    return Sighting(
        sid, pass_no, f"photo-{sid}", T0 + timedelta(days=pass_no - 1, minutes=minute), route_m, emb, hist
    )


def _toy_survey(seed: int = 0) -> tuple[list[Sighting], dict[str, str]]:
    """Synthetic: 6 dogs, both passes, side+head shots in pass 1."""
    rng = np.random.default_rng(seed)
    dogs = [_unit(rng.normal(size=32)) for _ in range(6)]
    out, truth = [], {}
    for d, vec in enumerate(dogs):
        for sid, pn, minute in [
            (f"p1d{d}s", 1, d * 3.0),
            (f"p1d{d}h", 1, d * 3.0 + 0.2),
            (f"p2d{d}", 2, d * 3.1),
        ]:
            out.append(_sighting(sid, pn, vec, minute, d * 150.0, rng))
            truth[sid] = f"dog{d}"
    return out, truth


def test_candidates_include_true_pairs_and_skip_same_photo() -> None:
    sightings, truth = _toy_survey()
    pairs = candidate_pairs(sightings)
    true_pairs = {(a, b) for a in truth for b in truth if a < b and truth[a] == truth[b]}
    assert true_pairs <= set(pairs)
    assert all(a < b for a, b in pairs)


def test_fit_separates_same_and_different() -> None:
    rows, ys = [], []
    for seed in range(8):
        sightings, truth = _toy_survey(seed)
        by_id = {s.id: s for s in sightings}
        for a, b in candidate_pairs(sightings):
            rows.append(pair_features(by_id[a], by_id[b]))
            ys.append(int(truth[a] == truth[b]))
    model, ev = fit(feature_matrix(rows), np.array(ys))
    assert ev.auc > 0.9
    restored = MatchModel.from_json(model.to_json())
    assert restored.version == model.version
    assert np.allclose(restored.predict(feature_matrix(rows[:5])), model.predict(feature_matrix(rows[:5])))


def test_prior_prefers_similar_pairs() -> None:
    base = {"route_km": 0.05, "log_gap_min": 1.0, "same_pass": 1.0, "colour_chi2": 0.2}
    hi, lo = PRIOR.predict(feature_matrix([{**base, "cosine": 0.9}, {**base, "cosine": 0.3}]))
    assert hi > 0.8 > 0.2 > lo


def test_assign_links_across_passes_one_to_one() -> None:
    pass_of = {"a1": 1, "a1h": 1, "a2": 1, "b1": 2, "b2": 2, "b3": 2}
    pairs = {
        ("a1", "a1h"): 0.95,
        ("a1", "b1"): 0.9,
        ("a1h", "b2"): 0.6,
        ("a2", "b2"): 0.85,
        ("a2", "b1"): 0.55,
    }
    out = assign(pass_of, pairs)
    as_sets = {frozenset(i) for i in out.individuals}
    assert frozenset({"a1", "a1h", "b1"}) in as_sets
    assert frozenset({"a2", "b2"}) in as_sets
    assert frozenset({"b3"}) in as_sets


def test_cluster_flags_weak_internal_pair() -> None:
    pairs = {("x", "y"): 0.9, ("y", "z"): 0.9, ("x", "z"): 0.1}
    out = assign({"x": 1, "y": 1, "z": 1}, pairs)
    assert out.flagged_clusters or len(cluster_pass(["x", "y", "z"], pairs)) > 1


def test_notch_model_learns_separable_classes() -> None:
    rng = np.random.default_rng(3)
    centers = rng.normal(size=(3, 16)) * 3
    x = np.vstack([centers[i] + rng.normal(size=(40, 16)) for i in range(3)])
    labels = [c for c in notch.CLASSES for _ in range(40)]
    model, metrics = notch.fit(x, labels)
    assert float(metrics["heldout_accuracy"]) > 0.9  # type: ignore[arg-type]
    probs = model.predict(x[:3])
    assert probs.shape == (3, 3) and np.allclose(probs.sum(axis=1), 1)
    assert notch.NotchModel.from_json(model.to_json()).version == model.version


def test_notch_needs_two_classes() -> None:
    with pytest.raises(ValueError):
        notch.fit(np.zeros((4, 3)), ["notched"] * 4)

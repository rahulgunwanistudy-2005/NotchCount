"""Small, fast checks of the simulator itself (SYNTHETIC). The full run is `make sim`."""

import numpy as np

from sim.model import SCENARIOS, Matcher, simulate
from sim.run import one, summarise


def test_simulated_matcher_is_calibrated() -> None:
    rng = np.random.default_rng(0)
    m = Matcher(split=0.05, merge_per_decoy=0.02)
    prior = 0.25
    labels, probs = [], []
    for _ in range(20000):
        is_true = rng.random() < prior
        probs.append(m.posterior(m.sample(rng, is_true), prior))
        labels.append(is_true)
    p, y = np.array(probs), np.array(labels)
    for lo, hi in [(0.0, 0.2), (0.2, 0.8), (0.8, 1.0)]:
        sel = (p >= lo) & (p < hi)
        if sel.sum() > 200:
            assert abs(y[sel].mean() - p[sel].mean()) < 0.05


def test_simulate_shapes_and_truth() -> None:
    sc = SCENARIOS[0]
    data, truth = simulate(sc, np.random.default_rng(1))
    assert truth.n == sc.n
    assert data.pass_numbers == (1, 2)
    assert all(p.decision is not None for p in data.pairs)


def test_reference_scenario_covers_on_a_small_run() -> None:
    reps = [one((SCENARIOS[0], seed, 150)) for seed in range(40)]
    summary = summarise(SCENARIOS[0], reps)
    assert float(summary["coverage_N"]) >= 0.8  # type: ignore[arg-type]
    assert abs(float(summary["median_relative_bias"])) < 0.1  # type: ignore[arg-type]

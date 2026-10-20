"""Run the BIBLE 3.8 scenarios and write docs/ESTIMATOR_VALIDATION.md (SYNTHETIC data only).

uv run python -m sim.run --replicates 1000 --bootstrap 400 --out docs/ESTIMATOR_VALIDATION.md
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from notchcount_stats import __version__, estimate_two_pass
from sim.model import SCENARIOS, Scenario, simulate


@dataclass(frozen=True, slots=True)
class Rep:
    n_true: int
    share_true: float
    point: float | None
    median: float | None
    low: float | None
    high: float | None
    share_low: float | None
    share_high: float | None
    m2: int
    split_rate: float | None
    merge_rate: float | None


def one(args: tuple[Scenario, int, int]) -> Rep:
    sc, seed, bootstrap = args
    rng = np.random.default_rng([seed, int.from_bytes(sc.id.encode(), "big")])
    data, truth = simulate(sc, rng)
    est = estimate_two_pass(data, replicates=bootstrap, seed=seed)
    trues = [p for p in data.pairs if p.a[1:] == p.b[1:]]
    split = sum(p.resolved_p <= 0.5 for p in trues) / len(trues) if trues else None
    seen2 = {s.id for s in data.sightings if s.pass_no == 2}
    merged = {p.b for p in data.pairs if p.a[1:] != p.b[1:] and p.resolved_p > 0.5}
    merge = len(merged) / len(seen2) if seen2 else None
    if sc.modelled:
        pop = est.population
        low, high, med = (pop.low, pop.high, pop.median) if pop else (None, None, None)
    else:
        pp = est.point_population
        low, high, med = pp.ci_low, pp.ci_high, pp.n_hat
    sh = est.point_share if not sc.modelled else None
    share_low = sh.ci_low if sh else (est.share.low if est.share else None)
    share_high = sh.ci_high if sh else (est.share.high if est.share else None)
    return Rep(
        truth.n,
        truth.notched_share,
        est.point_population.n_hat,
        med,
        low,
        high,
        share_low,
        share_high,
        est.point_counts.m2,
        split,
        merge,
    )


def summarise(sc: Scenario, reps: list[Rep]) -> dict[str, object]:
    est = [r for r in reps if r.low is not None and r.high is not None and r.median is not None]
    cover = [r.low <= r.n_true <= r.high for r in est]  # type: ignore[operator]
    rel = [r.median / r.n_true - 1 for r in est]  # type: ignore[operator]
    widths = [r.high - r.low for r in est]  # type: ignore[operator]
    shares = [r for r in reps if r.share_low is not None and r.share_high is not None]
    s_cover = [r.share_low <= r.share_true <= r.share_high for r in shares]  # type: ignore[operator]
    splits = [r.split_rate for r in reps if r.split_rate is not None]
    merges = [r.merge_rate for r in reps if r.merge_rate is not None]
    k = len(cover)
    cov = float(np.mean(cover)) if k else math.nan
    mc_se = math.sqrt(cov * (1 - cov) / k) if k else math.nan
    return {
        "id": sc.id,
        "scenario": asdict(sc),
        "replicates": len(reps),
        "with_estimate": k,
        "no_estimate_rate": 1 - k / len(reps),
        "m2_zero_rate": float(np.mean([r.m2 == 0 for r in reps])),
        "coverage_N": cov,
        "coverage_N_mc_se": mc_se,
        "median_relative_bias": float(np.median(rel)) if rel else math.nan,
        "mean_relative_bias": float(np.mean(rel)) if rel else math.nan,
        "median_width": float(np.median(widths)) if widths else math.nan,
        "coverage_share": float(np.mean(s_cover)) if s_cover else math.nan,
        "realised_false_split": float(np.mean(splits)) if splits else 0.0,
        "realised_false_merge": float(np.mean(merges)) if merges else 0.0,
    }


def plot(results: list[dict[str, object]], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ids = [str(r["id"]) for r in results]
    cov = [float(r["coverage_N"]) for r in results]  # type: ignore[arg-type]
    se = [1.96 * float(r["coverage_N_mc_se"]) for r in results]  # type: ignore[arg-type]
    bias = [100 * float(r["median_relative_bias"]) for r in results]  # type: ignore[arg-type]
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.6), constrained_layout=True)
    ink, teal, sodium = "#1f2b38", "#0b6b66", "#e8a317"
    colors = [teal if c >= 0.93 else sodium for c in cov]
    a.bar(ids, cov, yerr=se, color=colors, edgecolor=ink, capsize=3)
    a.axhline(0.95, color=ink, lw=1)
    a.axhline(0.93, color=ink, lw=1, ls="--")
    a.set_ylim(0.6, 1.0)
    a.set_title("95% interval coverage of the true N (synthetic)", fontsize=10)
    a.set_ylabel("share of simulated surveys")
    b.bar(ids, bias, color=[teal if abs(x) < 5 else sodium for x in bias], edgecolor=ink)
    b.axhline(0, color=ink, lw=1)
    b.set_title("Median relative bias of N (%)", fontsize=10)
    for ax in (a, b):
        ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(path, dpi=150)


def report(
    results: list[dict[str, object]], replicates: int, bootstrap: int, seconds: float, img: str
) -> str:
    rows = []
    for r in results:
        sc = r["scenario"]
        assert isinstance(sc, dict)
        rows.append(
            f"| {r['id']} | {sc['n']} | {sc['p']} | {'Beta' + str(tuple(sc['beta'])) if sc['beta'] else 'none'} "
            f"| {r['realised_false_split']:.3f} | {r['realised_false_merge']:.3f} | {'yes' if sc['modelled'] else 'no'} "
            f"| {r['coverage_N']:.3f} ± {1.96 * float(r['coverage_N_mc_se']):.3f} "  # type: ignore[arg-type]
            f"| {100 * float(r['median_relative_bias']):+.1f}% | {r['median_width']:.1f} "  # type: ignore[arg-type]
            f"| {r['coverage_share']:.3f} | {100 * float(r['no_estimate_rate']):.1f}% |"  # type: ignore[arg-type]
        )
    by = {str(r["id"]): r for r in results}
    lines = [
        "# Estimator validation (synthetic data)",
        "",
        "**Everything on this page comes from simulated surveys with a known true population. No real dog is "
        "described here.** The simulator (`sim/model.py`) feeds the same `notchcount_stats` code that runs on "
        "real data.",
        "",
        f"Generated by `uv run python -m sim.run`: {replicates} replicates per scenario, {bootstrap} sampler "
        f"draws per replicate (the production default is 2000; percentile intervals are stable at this size), "
        f"`notchcount_stats` {__version__}, {seconds / 60:.1f} minutes on {os.cpu_count()} cores. "
        "Seeds are fixed, so rerunning gives identical numbers.",
        "",
        f"![Coverage and bias by scenario]({img})",
        "",
        "| Scenario | N | Capture p | Heterogeneity | False split (realised) | False merge (realised) | Matcher "
        "uncertainty used | Coverage of N (95% MC band) | Median bias of N | Median interval width | Coverage "
        "of share | No estimate |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "Coverage is the share of simulated surveys whose 95% range contained the true N. The band after ± is "
        'the Monte Carlo uncertainty of that share. "No estimate" counts surveys where too few dogs were '
        "matched to report a population (BIBLE 3.2 and SESSION_PROMPT section 7).",
        "",
        "## What this shows",
        "",
    ]
    notes = {
        "S1": "Equal catchability, perfect matching: the reference case. Expected near 0.95; small "
        "shortfalls come from the log-normal approximation and the sampler size.",
        "S2": "Dogs differ in how easy they are to see (Beta(2, 1.33) catch probability). Easy dogs are seen "
        "in both passes, so recaptures run high and Chapman runs low. This is a property of the "
        "two-sample method, not of the code, and it is why the report calls the estimate a likely lower "
        "bound.",
        "S3": "Modelling helps (the same matcher with hard decisions, S6, covers less) but does not reach "
        "0.93. Why: an ambiguous true match scores like a decoy, so its calibrated pairwise probability is "
        "small (about 0.02 here) and it is rarely drawn. Calibration puts the missing probability on "
        "look-alike decoys instead, but the one-to-one repair throws most of that away, because those "
        "decoys' pass-2 dogs already have clear matches. So m2 runs low and N runs high. The fix is an "
        "assignment-level model (each pass-2 dog picks one candidate or none, with the recapture rate "
        "estimated jointly). It is not implemented yet; see docs/LIMITATIONS.md.",
        "S4": "A look-alike scored above 0.5 can win the one-to-one repair and push out the true partner, "
        "so a wrong merge often costs a right one. Net m2 falls and N rises, the opposite of what one wrong "
        "merge alone would do. The sampler sometimes rejects the look-alike, which widens the range, but not "
        "enough.",
        "S5": "Few recaptures: the Chapman variance and the log-normal interval are rough at small m2, so "
        "coverage drops and ranges are wide. Some surveys have too few matches to estimate at all.",
        "S6": "The same matcher as S3, but every pair is decided at 0.5 and fed to plain Chapman. Missed "
        "matches lower m2 and inflate N, and the interval knows nothing about it. This is what NotchCount "
        "would report without the sampler.",
    }
    for sid in ("S1", "S2", "S3", "S4", "S5", "S6"):
        r = by[sid]
        cov = float(r["coverage_N"])  # type: ignore[arg-type]
        verdict = "meets" if cov >= 0.93 else "falls below"
        lines.append(f"- **{sid}** ({verdict} 0.93, coverage {cov:.3f}). {notes[sid]}")
    lines += [
        "",
        "## Limits of this validation",
        "",
        "- The simulated matcher is calibrated by construction. The real matcher is a logistic model fitted to "
        "the team's labelled pairs (`docs/MODEL_REPORT.md`); if it is miscalibrated, real coverage will be "
        "worse than S3 and S4.",
        "- Each dog appears at most once per pass here. Real passes have side and head shots and repeat "
        "sightings, which the within-pass clustering must group correctly.",
        "- Notch calls are perfect apart from hidden ears. Real notch calls go through a classifier and human "
        "review.",
        "",
        "Raw numbers: `docs/estimator_validation.json`.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replicates", type=int, default=1000)
    ap.add_argument("--bootstrap", type=int, default=400)
    ap.add_argument("--out", type=Path, default=Path("docs/ESTIMATOR_VALIDATION.md"))
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    args = ap.parse_args()
    start = time.perf_counter()
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for sc in SCENARIOS:
            reps = list(pool.map(one, [(sc, s, args.bootstrap) for s in range(args.replicates)], chunksize=8))
            results.append(summarise(sc, reps))
            print(sc.id, {k: v for k, v in results[-1].items() if k != "scenario"}, flush=True)
    seconds = time.perf_counter() - start
    out: Path = args.out
    img = out.parent / "estimator_validation.png"
    plot(results, img)
    (out.parent / "estimator_validation.json").write_text(json.dumps(results, indent=1, default=str))
    out.write_text(report(results, args.replicates, args.bootstrap, seconds, img.name))


if __name__ == "__main__":
    main()

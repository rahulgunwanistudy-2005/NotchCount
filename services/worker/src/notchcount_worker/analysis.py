"""Survey-level jobs: match_survey, notch_survey, train_models, estimate.

Each loads what it needs from the database, calls pure code in notchcount_pipeline or
notchcount_stats, and writes results back. Reviewer decisions are never overwritten.
"""

from __future__ import annotations

import logging
import subprocess
import uuid
from typing import Any

import numpy as np
from geoalchemy2 import Geography
from sqlalchemy import cast, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from notchcount_api.config import REPO_ROOT
from notchcount_api.db.models import (
    Detection,
    Estimate,
    Individual,
    MatchPair,
    ModelVersion,
    NotchCallRow,
    NotchDecision,
    NotchLabel,
    PairDecision,
    PairLabel,
    PassRow,
    Photo,
    RouteRow,
    SightingRow,
    Survey,
)
from notchcount_api.domain.integrity import PassSummary, comparability_problems
from notchcount_pipeline import notch as notch_model
from notchcount_pipeline.assign import assign
from notchcount_pipeline.match import (
    PRIOR,
    MatchModel,
    Sighting,
    candidate_pairs,
    feature_matrix,
    pair_features,
)
from notchcount_pipeline.match import fit as fit_match
from notchcount_stats import (
    CandidatePair,
    NotchCall,
    NotchClass,
    SurveyData,
    estimate_single_pass,
    estimate_two_pass,
)
from notchcount_stats import Sighting as StatSighting
from notchcount_worker.errors import PermanentJobError

log = logging.getLogger("notchcount.worker.analysis")

MIN_PAIR_LABELS = 30
MIN_EAR_LABELS = 20


def git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


async def _survey_team(db: AsyncSession, survey_id: uuid.UUID) -> tuple[Survey, RouteRow]:
    row = (
        await db.execute(
            select(Survey, RouteRow)
            .join(RouteRow, RouteRow.id == Survey.route_id)
            .where(Survey.id == survey_id)
        )
    ).one_or_none()
    if row is None:
        raise PermanentJobError(f"survey {survey_id} not found")
    return row[0], row[1]


async def _latest_model(db: AsyncSession, team_id: uuid.UUID, kind: str) -> ModelVersion | None:
    return (
        await db.execute(
            select(ModelVersion)
            .where(ModelVersion.team_id == team_id, ModelVersion.kind == kind)
            .order_by(ModelVersion.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def load_sightings(db: AsyncSession, survey_id: uuid.UUID, route: RouteRow) -> list[Sighting]:
    """Usable detections with their position along the route (metres from the start)."""
    route_m = func.ST_LineLocatePoint(RouteRow.geom, Photo.geom) * func.ST_Length(
        cast(RouteRow.geom, Geography)
    )
    rows = (
        await db.execute(
            select(Detection, PassRow.pass_no, Photo.id, Photo.taken_at, route_m)
            .join(Photo, Photo.id == Detection.photo_id)
            .join(PassRow, PassRow.id == Photo.pass_id)
            .join(RouteRow, RouteRow.id == route.id)
            .where(PassRow.survey_id == survey_id, Detection.usable, Detection.embedding.is_not(None))
            .order_by(Photo.taken_at, Detection.id)
        )
    ).all()
    return [
        Sighting(
            id=str(d.id),
            pass_no=int(pn),
            photo_id=str(pid),
            taken_at=taken,
            route_m=None if rm is None else float(rm),
            embedding=np.asarray(d.embedding, dtype=np.float32),
            color_hist=np.asarray(d.color_hist or [], dtype=np.float32),
        )
        for d, pn, pid, taken, rm in rows
    ]


async def match_survey(db: AsyncSession, payload: dict[str, Any]) -> None:
    survey_id = uuid.UUID(str(payload["survey_id"]))
    _, route = await _survey_team(db, survey_id)
    sightings = await load_sightings(db, survey_id, route)
    by_id = {s.id: s for s in sightings}
    stored = await _latest_model(db, route.team_id, "match")
    model = MatchModel.from_json(stored.params) if stored else PRIOR
    version = model.version if stored else "prior-uncalibrated"
    pairs = candidate_pairs(sightings)
    if not pairs:
        log.info("no candidate pairs", extra={"survey_id": str(survey_id)})
        return
    feats = [pair_features(by_id[a], by_id[b]) for a, b in pairs]
    probs = model.predict(feature_matrix(feats))
    rows = [
        {
            "id": uuid.uuid4(),
            "survey_id": survey_id,
            "a_detection": uuid.UUID(a),
            "b_detection": uuid.UUID(b),
            "features": {k: round(v, 6) for k, v in f.items()},
            "p_same": float(p),
            "model_version": version,
        }
        for (a, b), f, p in zip(pairs, feats, probs, strict=True)
    ]
    for chunk in range(0, len(rows), 500):
        stmt = insert(MatchPair).values(rows[chunk : chunk + 500])
        await db.execute(
            stmt.on_conflict_do_update(
                constraint="uq_match_pairs_ab",
                set_={
                    "features": stmt.excluded.features,
                    "p_same": stmt.excluded.p_same,
                    "model_version": stmt.excluded.model_version,
                },
            )
        )
    log.info("pairs scored", extra={"survey_id": str(survey_id), "pairs": len(pairs), "model": version})


async def notch_survey(db: AsyncSession, payload: dict[str, Any]) -> None:
    survey_id = uuid.UUID(str(payload["survey_id"]))
    _, route = await _survey_team(db, survey_id)
    stored = await _latest_model(db, route.team_id, "notch")
    if stored is None:
        return
    model = notch_model.NotchModel.from_json(stored.params)
    rows = (
        await db.execute(
            select(Detection.id, Detection.embedding)
            .join(Photo, Photo.id == Detection.photo_id)
            .join(PassRow, PassRow.id == Photo.pass_id)
            .where(PassRow.survey_id == survey_id, Detection.usable, Detection.embedding.is_not(None))
        )
    ).all()
    if not rows:
        return
    probs = model.predict(np.array([np.asarray(e, dtype=np.float64) for _, e in rows]))
    values = [
        {
            "detection_id": det_id,
            "p_notched": float(p[0]),
            "p_not_notched": float(p[1]),
            "p_not_visible": float(p[2]),
            "model_version": model.version,
        }
        for (det_id, _), p in zip(rows, probs, strict=True)
    ]
    for chunk in range(0, len(values), 500):
        stmt = insert(NotchCallRow).values(values[chunk : chunk + 500])
        await db.execute(
            stmt.on_conflict_do_update(
                index_elements=[NotchCallRow.detection_id],
                set_={
                    "p_notched": stmt.excluded.p_notched,
                    "p_not_notched": stmt.excluded.p_not_notched,
                    "p_not_visible": stmt.excluded.p_not_visible,
                    "model_version": stmt.excluded.model_version,
                },
            )
        )


async def train_models(db: AsyncSession, payload: dict[str, Any]) -> None:
    """Refit the team's match and notch models from every label so far, then rescore the survey."""
    team_id = uuid.UUID(str(payload["team_id"]))
    team_surveys = (
        select(Survey.id).join(RouteRow, RouteRow.id == Survey.route_id).where(RouteRow.team_id == team_id)
    )
    labelled = (
        await db.execute(
            select(MatchPair.features, PairLabel.decision)
            .join(PairLabel, PairLabel.pair_id == MatchPair.id)
            .where(MatchPair.survey_id.in_(team_surveys), PairLabel.decision != PairDecision.UNSURE)
        )
    ).all()
    report: dict[str, Any] = {"pair_labels": len(labelled)}
    ys = np.array([1 if d is PairDecision.SAME else 0 for _, d in labelled])
    if len(labelled) >= MIN_PAIR_LABELS and 0 < ys.sum() < len(ys):
        model, ev = fit_match(feature_matrix([f for f, _ in labelled]), ys)
        metrics = {
            "auc": ev.auc,
            "brier": ev.brier,
            "n_train": ev.n_train,
            "n_test": ev.n_test,
            "positives": ev.positives,
            "reliability": ev.reliability,
        }
        db.add(
            ModelVersion(
                team_id=team_id, kind="match", version=model.version, params=model.to_json(), metrics=metrics
            )
        )
        report["match"] = metrics
    ears = (
        await db.execute(
            select(Detection.embedding, NotchLabel.decision)
            .join(NotchLabel, NotchLabel.detection_id == Detection.id)
            .join(Photo, Photo.id == Detection.photo_id)
            .join(PassRow, PassRow.id == Photo.pass_id)
            .where(PassRow.survey_id.in_(team_surveys), NotchLabel.decision != NotchDecision.UNSURE)
        )
    ).all()
    report["ear_labels"] = len(ears)
    if len(ears) >= MIN_EAR_LABELS and len({d for _, d in ears}) >= 2:
        x = np.array([np.asarray(e, dtype=np.float64) for e, _ in ears])
        nm, nmetrics = notch_model.fit(x, [d.value for _, d in ears])
        db.add(
            ModelVersion(
                team_id=team_id, kind="notch", version=nm.version, params=nm.to_json(), metrics=nmetrics
            )
        )
        report["notch"] = nmetrics
    await db.flush()
    log.info(
        "models trained", extra={"team_id": str(team_id), **{k: str(v)[:300] for k, v in report.items()}}
    )
    survey_id = payload.get("survey_id")
    if survey_id:
        await match_survey(db, {"survey_id": survey_id})
        await notch_survey(db, {"survey_id": survey_id})


def _notch_call(row: NotchCallRow | None) -> NotchCall | None:
    if row is None:
        return None
    if row.decision is not None and row.decision is not NotchDecision.UNSURE:
        return NotchCall.decided(NotchClass(row.decision.value))
    if row.p_notched is None or row.p_not_notched is None or row.p_not_visible is None:
        return None
    total = row.p_notched + row.p_not_notched + row.p_not_visible
    return NotchCall(row.p_notched / total, row.p_not_notched / total, row.p_not_visible / total)


async def estimate(db: AsyncSession, payload: dict[str, Any]) -> None:
    est_id = uuid.UUID(str(payload["estimate_id"]))
    est = (await db.execute(select(Estimate).where(Estimate.id == est_id))).scalar_one_or_none()
    if est is None:
        raise PermanentJobError("estimate row missing")
    try:
        await _run_estimate(db, est)
    except (ValueError, ArithmeticError) as exc:
        # Bad or degenerate data: record why on the estimate so the report can say it.
        await db.rollback()
        est = (await db.execute(select(Estimate).where(Estimate.id == est_id))).scalar_one()
        est.status, est.error = "failed", f"{type(exc).__name__}: {exc}"
        await db.flush()
        log.warning("estimate failed", extra={"estimate_id": str(est_id), "error": est.error})


async def _run_estimate(db: AsyncSession, est: Estimate) -> None:
    survey, route = await _survey_team(db, est.survey_id)
    est.status = "running"
    passes = (
        (await db.execute(select(PassRow).where(PassRow.survey_id == survey.id).order_by(PassRow.pass_no)))
        .scalars()
        .all()
    )
    sightings = await load_sightings(db, survey.id, route)
    det_ids = [uuid.UUID(s.id) for s in sightings]
    calls = {
        str(c.detection_id): c
        for c in (
            await db.execute(select(NotchCallRow).where(NotchCallRow.detection_id.in_(det_ids)))
        ).scalars()
    }
    pairs = (
        (
            await db.execute(
                select(MatchPair).where(MatchPair.survey_id == survey.id, MatchPair.p_same.is_not(None))
            )
        )
        .scalars()
        .all()
    )
    stat_pairs = tuple(
        CandidatePair(
            str(p.a_detection),
            str(p.b_detection),
            float(p.p_same or 0.0),
            decision=None if p.decision in (None, PairDecision.UNSURE) else p.decision is PairDecision.SAME,
        )
        for p in pairs
    )
    stat_sightings = tuple(StatSighting(s.id, s.pass_no, _notch_call(calls.get(s.id))) for s in sightings)
    seen_passes = sorted({s.pass_no for s in sightings})
    data = SurveyData(stat_sightings, stat_pairs, pass_numbers=tuple(seen_passes))
    problems = comparability_problems(
        [
            PassSummary(p.pass_no, p.started_at, p.ended_at, str(route.id))
            for p in passes
            if p.pass_no in seen_passes
        ],
        survey.start_window_local,
        survey.timezone,
        15,
    )
    replicates = int(est.params.get("replicates", 2000))
    results: dict[str, Any] = {
        "passes": [
            {
                "pass_no": p.pass_no,
                "started_at": p.started_at.isoformat(),
                "ended_at": p.ended_at.isoformat() if p.ended_at else None,
                "flags": list(p.flags),
            }
            for p in passes
        ],
        "sightings": len(sightings),
        "pairs": len(pairs),
        "decided_pairs": sum(1 for p in stat_pairs if p.decision is not None),
        "match_model": sorted({p.model_version or "" for p in pairs}),
        "comparability_problems": problems,
        "git": git_sha(),
    }
    if len(seen_passes) >= 2 and not problems:
        two = estimate_two_pass(
            SurveyData(stat_sightings, stat_pairs, pass_numbers=tuple(seen_passes[:2])),
            replicates=replicates,
            seed=est.seed,
        )
        est.method = "two_pass_sampled_chapman"
        results.update(_two_pass_json(two))
        est.data_hash = two.data_hash
    else:
        single = estimate_single_pass(data, seen_passes[-1]) if seen_passes else None
        est.method = "single_pass"
        if single is not None:
            results["single_pass"] = {
                "pass_no": single.pass_no,
                "individuals": single.individuals,
                "share": _share_json(single.point_share),
            }
            est.data_hash = single.data_hash
    proposed = assign({s.id: s.pass_no for s in sightings}, {(p.a, p.b): p.resolved_p for p in stat_pairs})
    await _store_individuals(db, survey.id, proposed.individuals, {s.id: s.pass_no for s in sightings})
    results["review_flagged_clusters"] = len(proposed.flagged_clusters)
    results["individuals"] = _individual_summaries(proposed.individuals, sightings, calls)
    est.results = results
    est.status = "done"
    est.error = None
    await db.flush()


def _individual_summaries(
    groups: list[frozenset[str]], sightings: list[Sighting], calls: dict[str, NotchCallRow]
) -> list[dict[str, Any]]:
    """Per proposed individual: which passes, ear status, mean position along the route.
    The position is for the team's own view; the public report drops it (see routers/reports.py)."""
    by_id = {s.id: s for s in sightings}
    out = []
    for g in sorted(groups, key=lambda g: min(g)):
        classes = []
        for sid in g:
            call = _notch_call(calls.get(sid))
            if call is None:
                continue
            if call.decision is not None:
                classes.append(call.decision.value)
            else:
                probs = {
                    "notched": call.p_notched,
                    "not_notched": call.p_not_notched,
                    "not_visible": call.p_not_visible,
                }
                classes.append(max(probs, key=lambda k: probs[k]))
        status_ = (
            "notched"
            if "notched" in classes
            else "not_notched"
            if "not_notched" in classes
            else "not_visible"
        )
        positions = [by_id[sid].route_m for sid in g if by_id[sid].route_m is not None]
        out.append(
            {
                "passes": sorted({by_id[sid].pass_no for sid in g}),
                "status": status_,
                "route_m": round(sum(positions) / len(positions)) if positions else None,  # type: ignore[arg-type]
            }
        )
    return out


def _share_json(s: Any) -> dict[str, Any]:
    return {
        "notched": s.notched,
        "with_visible_ear": s.with_visible_ear,
        "excluded_not_visible": s.excluded_not_visible,
        "share": s.share,
        "low": s.ci_low,
        "high": s.ci_high,
    }


def _summary(s: Any) -> dict[str, float] | None:
    return None if s is None else {"median": s.median, "low": s.low, "high": s.high}


def _two_pass_json(e: Any) -> dict[str, Any]:
    pp = e.point_population
    return {
        "counts": {
            "n1": e.point_counts.n1,
            "n2": e.point_counts.n2,
            "m2": e.point_counts.m2,
            "distinct": e.point_counts.distinct,
        },
        "chapman": {
            "status": pp.status.value,
            "n_hat": pp.n_hat,
            "se": pp.se,
            "low": pp.ci_low,
            "high": pp.ci_high,
        },
        "population": _summary(e.population),
        "share": _summary(e.share),
        "deficit": _summary(e.deficit),
        "point_share": _share_json(e.point_share),
        "replicates": e.replicates,
        "matching": e.matching,
        "no_recapture_fraction": e.no_recapture_fraction,
        "no_visible_ear_fraction": e.no_visible_ear_fraction,
        "target_share": e.target_share,
    }


async def _store_individuals(
    db: AsyncSession, survey_id: uuid.UUID, groups: list[frozenset[str]], pass_of: dict[str, int]
) -> None:
    run_id = uuid.uuid4()
    await db.execute(delete(Individual).where(Individual.survey_id == survey_id))
    inds = [{"id": uuid.uuid4(), "survey_id": survey_id, "run_id": run_id} for _ in groups]
    links = [
        {"detection_id": uuid.UUID(sid), "individual_id": ind["id"], "pass_no": pass_of[sid]}
        for ind, g in zip(inds, groups, strict=True)
        for sid in g
    ]
    if inds:
        await db.execute(insert(Individual).values(inds))
    for chunk in range(0, len(links), 1000):
        await db.execute(insert(SightingRow).values(links[chunk : chunk + 1000]))

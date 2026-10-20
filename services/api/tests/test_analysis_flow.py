"""Match, label, train and estimate on a SYNTHETIC survey written straight into the test schema."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta

import httpx
import numpy as np
import pytest
from geoalchemy2.functions import ST_GeomFromText
from sqlalchemy import func, select

from notchcount_api.db.models import (
    Detection,
    Estimate,
    MatchPair,
    ModelVersion,
    PassRow,
    Photo,
    PhotoStatus,
    Role,
    RouteRow,
    Survey,
    View,
)
from notchcount_api.db.session import get_sessionmaker
from notchcount_worker.runner import registry, run_once

from .conftest import make_member, sign_in

pytestmark = pytest.mark.db


def _unit(v: np.ndarray) -> list[float]:
    return (v / np.linalg.norm(v)).astype(np.float32).tolist()


async def _seed(team_id: uuid.UUID, walker: uuid.UUID) -> tuple[uuid.UUID, dict[uuid.UUID, int]]:
    """16 synthetic dogs: 13 seen in pass 1 (side + head), 12 in pass 2, 9 in both."""
    rng = np.random.default_rng(7)
    # A shared component makes different dogs look alike (cosine about 0.6), as real crops do.
    common = rng.normal(size=384) * 1.2
    dogs = [common + rng.normal(size=384) for _ in range(16)]
    truth: dict[uuid.UUID, int] = {}
    start = datetime.now(UTC).replace(hour=1, minute=0, second=0, microsecond=0) - timedelta(days=2)
    async with get_sessionmaker()() as db:
        route = RouteRow(
            team_id=team_id,
            name="Synthetic lane",
            geom=ST_GeomFromText("LINESTRING(77.2085 28.6135, 77.2185 28.6135)", 4326),
        )
        db.add(route)
        await db.flush()
        survey = Survey(route_id=route.id, name="Synthetic survey", start_window_local=time(6, 30))
        db.add(survey)
        await db.flush()
        seen = {1: range(0, 13), 2: range(4, 16)}
        for pn, dog_ids in seen.items():
            p = PassRow(
                survey_id=survey.id,
                pass_no=pn,
                observer_id=walker,
                started_at=start + timedelta(days=pn - 1),
                ended_at=start + timedelta(days=pn - 1, minutes=40),
                locked=True,
            )
            db.add(p)
            await db.flush()
            for k, d in enumerate(dog_ids):
                shots = [View.SIDE, View.HEAD] if pn == 1 else [View.SIDE]
                for s, view in enumerate(shots):
                    lon = 77.2085 + 0.0006 * d
                    photo = Photo(
                        pass_id=p.id,
                        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                        taken_at=p.started_at + timedelta(minutes=3 * k, seconds=10 * s),
                        geom=func.ST_SetSRID(func.ST_MakePoint(lon, 28.6135), 4326),
                        accuracy_m=5,
                        shot=view,
                        status=PhotoStatus.PROCESSED,
                    )
                    db.add(photo)
                    await db.flush()
                    det = Detection(
                        photo_id=photo.id,
                        bbox=[0, 0, 10, 10],
                        conf=0.9,
                        crop_key=f"crops/{photo.id}_0.jpg",
                        quality=0.9,
                        usable=True,
                        embedding=_unit(dogs[d] + rng.normal(0, 0.35, 384)),
                        color_hist=[1 / 144] * 144,
                        view=view,
                        model_version="synthetic",
                    )
                    db.add(det)
                    await db.flush()
                    truth[det.id] = d
        await db.commit()
        return survey.id, truth


async def test_match_label_train_estimate(client: httpx.AsyncClient) -> None:
    team_id, admin_id, code = await make_member(None, "Admin", Role.ADMIN)
    await sign_in(client, code)
    survey_id, truth = await _seed(team_id, admin_id)
    handlers = registry()

    assert (await client.post(f"/api/v1/surveys/{survey_id}/match")).status_code == 202
    while await run_once("test", handlers):
        pass
    progress = (await client.get(f"/api/v1/surveys/{survey_id}/progress")).json()
    assert progress["pairs"] > 10 and progress["match_model"] is None

    answered = 0
    while (item := (await client.get(f"/api/v1/surveys/{survey_id}/labeling/pairs")).json()) is not None:
        same = truth[uuid.UUID(item["a"]["detection_id"])] == truth[uuid.UUID(item["b"]["detection_id"])]
        r = await client.post(
            "/api/v1/labels/pairs",
            json={"pair_id": item["pair_id"], "decision": "same" if same else "different"},
        )
        assert r.status_code == 204
        answered += 1
        assert answered < 500
    assert answered == progress["pairs"]

    ear = (await client.get(f"/api/v1/surveys/{survey_id}/labeling/ears")).json()
    assert ear["crop"]["view"] == "head"
    for _ in range(25):
        ear = (await client.get(f"/api/v1/surveys/{survey_id}/labeling/ears")).json()
        if ear is None:
            break
        decision = "notched" if truth[uuid.UUID(ear["detection_id"])] % 2 == 0 else "not_notched"
        await client.post(
            "/api/v1/labels/ears", json={"detection_id": ear["detection_id"], "decision": decision}
        )

    assert (await client.post(f"/api/v1/surveys/{survey_id}/train")).status_code == 202
    est = (await client.post(f"/api/v1/surveys/{survey_id}/estimates?replicates=300")).json()
    while await run_once("test", handlers):
        pass

    async with get_sessionmaker()() as db:
        kinds = {m.kind for m in (await db.execute(select(ModelVersion))).scalars()}
        assert "match" in kinds
        undecided = (
            await db.execute(select(func.count()).select_from(MatchPair).where(MatchPair.decision.is_(None)))
        ).scalar_one()
        assert undecided == 0
        row = (await db.execute(select(Estimate).where(Estimate.id == uuid.UUID(est["id"])))).scalar_one()
    assert row.status == "done", row.error
    res = row.results
    assert res is not None
    # 01:00 UTC is 06:30 in Asia/Kolkata, the agreed start, so the two passes are comparable.
    assert res["comparability_problems"] == []
    assert row.method == "two_pass_sampled_chapman"
    assert res["counts"] == {"n1": 13, "n2": 12, "m2": 9, "distinct": 16}
    assert res["population"]["low"] >= 16
    assert row.data_hash and row.seed == 20261021

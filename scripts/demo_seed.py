"""Seed a clearly labelled DEMO team on a running NotchCount so every screen has something in it.

Walk 1 = real CC BY-SA street-dog photos (data/samples). Walk 2 = the same dogs re-shot by
transforms (SYNTHETIC). Photos go through the real API and are processed by a running worker.
Only `--label-fraction` of the candidate pairs are labelled (with the known truth), so the
labelling screen and review queue still have work for a person to try.

    uv run python scripts/demo_seed.py --api https://notchcount.onrender.com --schema notchcount
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from datetime import time as dtime
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--api", required=True)
ap.add_argument("--schema", default="notchcount")
ap.add_argument("--public-base", default=None)
ap.add_argument("--label-fraction", type=float, default=0.6)
args = ap.parse_args()
os.environ["NC_DB_SCHEMA"] = args.schema

import httpx  # noqa: E402
from geoalchemy2.functions import ST_GeomFromText  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from notchcount_api.auth.invites import create_invite  # noqa: E402
from notchcount_api.db.models import (  # noqa: E402
    Detection,
    Job,
    JobStatus,
    PassRow,
    Role,
    RouteRow,
    Survey,
    Team,
    TeamMember,
    User,
)
from notchcount_api.db.session import get_sessionmaker  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from engine_check import IST, LAT0, LON0, SAMPLES, STEP_DEG, reshoot  # noqa: E402


async def seed_db() -> dict[str, object]:
    async with get_sessionmaker()() as db:
        team = Team(name="Demo team (sample photos, synthetic walk 2)", city="Demo city")
        uploader = User(auth_subject=f"demo:{uuid.uuid4()}", display_name="Demo walker")
        admin = User(auth_subject=f"demo:{uuid.uuid4()}", display_name="Demo admin")
        db.add_all([team, uploader, admin])
        await db.flush()
        db.add_all(
            [
                TeamMember(team_id=team.id, user_id=uploader.id, role=Role.ADMIN),
                TeamMember(team_id=team.id, user_id=admin.id, role=Role.ADMIN),
            ]
        )
        route = RouteRow(
            team_id=team.id,
            name="Demo lane",
            corridor_m=40,
            geom=ST_GeomFromText(f"LINESTRING({LON0} {LAT0}, {LON0 + STEP_DEG * 17} {LAT0})", 4326),
        )
        db.add(route)
        await db.flush()
        survey = Survey(route_id=route.id, name="Demo survey", start_window_local=dtime(6, 30))
        db.add(survey)
        await db.flush()
        today = (datetime.now(UTC) + IST).date()
        passes = []
        for k in (1, 2):
            start = datetime.combine(today - timedelta(days=3 - k), dtime(1, 0), tzinfo=UTC)
            p = PassRow(
                survey_id=survey.id,
                pass_no=k,
                observer_id=uploader.id,
                started_at=start,
                ended_at=start + timedelta(minutes=45),
                locked=True,
            )
            db.add(p)
            passes.append(p)
        up_code = await create_invite(db, uploader.id)
        admin_code = await create_invite(db, admin.id)
        await db.commit()
        return {
            "survey": str(survey.id),
            "team": str(team.id),
            "up": up_code,
            "admin": admin_code,
            "passes": [(str(p.id), p.started_at) for p in passes],
        }


async def queue_empty() -> bool:
    async with get_sessionmaker()() as db:
        n = (
            await db.execute(
                select(func.count())
                .select_from(Job)
                .where(Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))
            )
        ).scalar_one()
        return int(n) == 0


async def wait_queue(limit_s: float = 1800) -> float:
    t0 = time.perf_counter()
    while not await queue_empty():
        if time.perf_counter() - t0 > limit_s:
            raise TimeoutError("worker did not finish; is it running?")
        await asyncio.sleep(3)
    return time.perf_counter() - t0


async def main() -> None:
    seed = await seed_db()
    files = sorted(SAMPLES.glob("dog_*.jpg"))
    truth: dict[str, int] = {}
    async with httpx.AsyncClient(base_url=args.api, headers={"x-notchcount": "1"}, timeout=120) as api:
        (await api.post("/api/v1/auth/invite", json={"code": seed["up"]})).raise_for_status()
        (p1, s1), (p2, s2) = seed["passes"]  # type: ignore[misc]
        n = len(files)
        plan = [(p1, s1, d, files[d].read_bytes(), 0.0) for d in range(0, n - 3)]
        plan += [(p2, s2, d, reshoot(files[d].read_bytes(), 100 + d), 0.00008) for d in range(3, n)]
        t0 = time.perf_counter()
        for k, (pid, start, d, data, jitter) in enumerate(plan):
            r = await api.post(
                f"/api/v1/passes/{pid}/photos",
                data={
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "taken_at": (start + timedelta(minutes=2 + 2 * (k % 13))).isoformat(),
                    "shot": "side",
                    "lat": str(LAT0 + 0.00005),
                    "lon": str(LON0 + STEP_DEG * (d + 0.5) + jitter),
                    "accuracy_m": "6",
                },
                files={"file": ("p.jpg", data, "image/jpeg")},
            )
            r.raise_for_status()
            truth[r.json()["id"]] = d
        upload_s = time.perf_counter() - t0
        ingest_s = await wait_queue()
        print(
            f"uploaded {len(plan)} photos in {upload_s:.0f}s; queue drained {ingest_s:.0f}s after the last upload",
            flush=True,
        )

        sid = seed["survey"]
        (await api.post(f"/api/v1/surveys/{sid}/match")).raise_for_status()
        await wait_queue()
        prog = (await api.get(f"/api/v1/surveys/{sid}/progress")).json()
        target = int(prog["pairs"] * args.label_fraction)
        async with get_sessionmaker()() as db:
            det_photo = {
                str(d): str(p) for d, p in (await db.execute(select(Detection.id, Detection.photo_id))).all()
            }
        done = 0
        while (
            done < target
            and (item := (await api.get(f"/api/v1/surveys/{sid}/labeling/pairs")).json()) is not None
        ):
            a, b = (
                truth.get(det_photo[item["a"]["detection_id"]]),
                truth.get(det_photo[item["b"]["detection_id"]]),
            )
            await api.post(
                "/api/v1/labels/pairs",
                json={"pair_id": item["pair_id"], "decision": "same" if a == b else "different"},
            )
            done += 1
        (await api.post(f"/api/v1/surveys/{sid}/train")).raise_for_status()
        await wait_queue()
        (await api.post(f"/api/v1/surveys/{sid}/estimates")).raise_for_status()
        await wait_queue()
        pub = (await api.post(f"/api/v1/surveys/{sid}/publish")).json()
        prog = (await api.get(f"/api/v1/surveys/{sid}/progress")).json()
    base = args.public_base or args.api
    print(f"labelled {done} of {prog['pairs']} pairs; review queue: {prog['review_pairs_left']} pairs")
    print(f"survey: {base}/app/survey/{sid}")
    print(f"public report: {pub['url']}")
    print(f"demo admin sign-in (one use): {base}/join#{seed['admin']}")


asyncio.run(main())

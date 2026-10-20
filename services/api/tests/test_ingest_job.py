"""Upload through the API, run the worker once, check what was stored (needs DB and models)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from notchcount_api.db.models import Blob, Detection, Job, JobStatus, Photo, PhotoStatus, Role
from notchcount_api.db.session import get_sessionmaker
from notchcount_worker.ingest import models_ready
from notchcount_worker.runner import registry, run_once

from .conftest import ROUTE, make_member, sign_in

pytestmark = [pytest.mark.db, pytest.mark.models]
FIXTURES = Path(__file__).resolve().parents[3] / "packages" / "pipeline" / "tests"


async def _pass(client: httpx.AsyncClient) -> str:
    team_id, _, code = await make_member(None, "Admin walker", Role.ADMIN)
    await sign_in(client, code)
    route = (
        await client.post(f"/api/v1/teams/{team_id}/routes", json={"name": "Lane", "geometry": ROUTE})
    ).json()
    survey = (
        await client.post(
            f"/api/v1/teams/{team_id}/surveys",
            json={"route_id": route["id"], "name": "Survey", "start_window_local": "06:30"},
        )
    ).json()
    started = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    return (
        await client.post(
            f"/api/v1/surveys/{survey['id']}/passes", json={"pass_no": 1, "started_at": started}
        )
    ).json()["id"]


async def _upload(client: httpx.AsyncClient, pass_id: str, name: str) -> str:
    data = (FIXTURES / name).read_bytes()
    r = await client.post(
        f"/api/v1/passes/{pass_id}/photos",
        data={
            "sha256": hashlib.sha256(data).hexdigest(),
            "taken_at": datetime.now(UTC).isoformat(),
            "shot": "side",
        },
        files={"file": ("p.jpg", data, "image/jpeg")},
    )
    assert r.status_code == 200, r.text
    return str(r.json()["id"])


async def test_ingest_stores_blurred_image_and_crops_and_drops_original(client: httpx.AsyncClient) -> None:
    if not models_ready():
        pytest.skip("models not exported")
    pass_id = await _pass(client)
    dog_id = await _upload(client, pass_id, "fixture_dog.jpg")
    people_id = await _upload(client, pass_id, "fixture_people.jpg")
    handlers = registry()
    assert "ingest_photo" in handlers
    assert await run_once("test", handlers)
    assert await run_once("test", handlers)
    assert not await run_once("test", handlers)

    async with get_sessionmaker()() as db:
        photos = {p.id.hex: p for p in (await db.execute(select(Photo))).scalars()}
        dog, people = photos[dog_id.replace("-", "")], photos[people_id.replace("-", "")]
        assert dog.status is PhotoStatus.PROCESSED and people.status is PhotoStatus.PROCESSED
        assert dog.quarantine_key is None and people.persons_blurred and people.persons_blurred >= 3
        buckets = dict((await db.execute(select(Blob.bucket, func.count()).group_by(Blob.bucket))).all())
        assert buckets.get("quarantine", 0) == 0
        assert buckets["blurred"] == 2 and buckets["crops"] >= 1
        dets = (await db.execute(select(Detection).where(Detection.photo_id == dog.id))).scalars().all()
        assert len(dets) == 1 and dets[0].usable and dets[0].view.value == "side"
        jobs = (await db.execute(select(Job.status))).scalars().all()
        assert set(jobs) == {JobStatus.DONE}

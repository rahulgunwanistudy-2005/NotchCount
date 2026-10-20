"""API tests run against a real Postgres (PostGIS + pgvector) in a separate schema.

Set NC_DATABASE_URL (the repo .env works). Tables are truncated before each test. Data here is
synthetic test data only.
"""

from __future__ import annotations

import io
import os
import uuid
from collections.abc import AsyncIterator

os.environ.setdefault("NC_DB_SCHEMA", "notchcount_test")
os.environ["NC_ENV"] = "test"
os.environ["NC_STATIC_DIR"] = ""

import httpx
import pytest
from PIL import Image
from sqlalchemy import text

from notchcount_api.auth.invites import create_invite
from notchcount_api.config import get_settings
from notchcount_api.db.models import Base, Role, Team, TeamMember, User
from notchcount_api.db.session import get_engine, get_sessionmaker
from notchcount_api.main import create_app

pytestmark = pytest.mark.db

ROUTE = {
    "type": "LineString",
    "coordinates": [[77.2090, 28.6139], [77.2100, 28.6139], [77.2100, 28.6149]],
}


@pytest.fixture(scope="session", autouse=True)
def _guard_schema() -> None:
    assert get_settings().db_schema.endswith("_test"), "API tests must not run against the live schema"


@pytest.fixture(autouse=True)
async def clean_db() -> AsyncIterator[None]:
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    async with get_engine().begin() as conn:
        await conn.execute(text(f"truncate {tables} restart identity cascade"))
    yield
    await get_engine().dispose()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(get_settings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"x-notchcount": "1"}
    ) as c:
        yield c


async def make_member(team_id: uuid.UUID | None, name: str, role: Role) -> tuple[uuid.UUID, uuid.UUID, str]:
    """Returns (team_id, user_id, invite code). Creates the team when team_id is None."""
    async with get_sessionmaker()() as db:
        if team_id is None:
            team = Team(name=f"Team of {name}", city="Test city")
            db.add(team)
            await db.flush()
            team_id = team.id
        user = User(auth_subject=f"test:{uuid.uuid4()}", display_name=name)
        db.add(user)
        await db.flush()
        db.add(TeamMember(team_id=team_id, user_id=user.id, role=role))
        code = await create_invite(db, user.id)
        await db.commit()
        return team_id, user.id, code


async def sign_in(client: httpx.AsyncClient, code: str) -> None:
    r = await client.post("/api/v1/auth/invite", json={"code": code})
    assert r.status_code == 204, r.text


def jpeg_bytes(seed: int = 0) -> bytes:
    img = Image.new("RGB", (64, 48), (seed % 256, (seed * 7) % 256, 90))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()

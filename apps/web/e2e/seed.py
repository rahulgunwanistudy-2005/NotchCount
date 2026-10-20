"""Seed a synthetic team, route, survey and walker invite for the Playwright tests (test schema only)."""

import asyncio
import json
import os
import uuid
from datetime import time

os.environ.setdefault("NC_DB_SCHEMA", "notchcount_test")

from geoalchemy2.functions import ST_GeomFromText  # noqa: E402
from notchcount_api.auth.invites import create_invite  # noqa: E402
from notchcount_api.config import get_settings  # noqa: E402
from notchcount_api.db.models import Role, RouteRow, Survey, Team, TeamMember, User  # noqa: E402
from notchcount_api.db.session import get_sessionmaker  # noqa: E402


async def main() -> None:
    schema = get_settings().db_schema
    assert schema.endswith("_test") or os.environ.get("E2E_LIVE") == "1", schema
    async with get_sessionmaker()() as db:
        team = Team(name="E2E check (synthetic, delete me)", city="Test city")
        walker = User(auth_subject=f"e2e:{uuid.uuid4()}", display_name="E2E walker")
        db.add_all([team, walker])
        await db.flush()
        db.add(TeamMember(team_id=team.id, user_id=walker.id, role=Role.WALKER))
        route = RouteRow(
            team_id=team.id,
            name="E2E lane",
            corridor_m=40,
            geom=ST_GeomFromText("LINESTRING(77.2085 28.6135, 77.2100 28.6136, 77.2101 28.6148)", 4326),
        )
        db.add(route)
        await db.flush()
        survey = Survey(route_id=route.id, name="E2E survey", start_window_local=time(6, 30))
        db.add(survey)
        code = await create_invite(db, walker.id)
        await db.commit()
        print(json.dumps({"invite": code, "survey_id": str(survey.id)}))


asyncio.run(main())

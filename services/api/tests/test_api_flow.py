from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from notchcount_api.db.models import Role

from .conftest import ROUTE, jpeg_bytes, make_member, sign_in

pytestmark = pytest.mark.db


async def _upload(client: httpx.AsyncClient, pass_id: str, data: bytes, taken_at: datetime, **fields: object):
    form = {
        "sha256": hashlib.sha256(data).hexdigest(),
        "taken_at": taken_at.isoformat(),
        **{k: str(v) for k, v in fields.items()},
    }
    return await client.post(
        f"/api/v1/passes/{pass_id}/photos", data=form, files={"file": ("p.jpg", data, "image/jpeg")}
    )


@pytest.fixture
async def walker_pass(client: httpx.AsyncClient) -> dict[str, str]:
    team_id, _, admin_code = await make_member(None, "Admin", Role.ADMIN)
    await sign_in(client, admin_code)
    route = (
        await client.post(f"/api/v1/teams/{team_id}/routes", json={"name": "Lane loop", "geometry": ROUTE})
    ).json()
    survey = (
        await client.post(
            f"/api/v1/teams/{team_id}/surveys",
            json={"route_id": route["id"], "name": "October", "start_window_local": "06:30"},
        )
    ).json()
    invite = (
        await client.post(
            f"/api/v1/teams/{team_id}/members", json={"display_name": "Walker", "role": "walker"}
        )
    ).json()
    client.cookies.clear()
    await sign_in(client, invite["invite_url"].split("#", 1)[1])
    started = datetime.now(UTC) - timedelta(minutes=10)
    r = await client.post(
        f"/api/v1/surveys/{survey['id']}/passes", json={"pass_no": 1, "started_at": started.isoformat()}
    )
    assert r.status_code == 200, r.text
    return {"team_id": str(team_id), "survey_id": survey["id"], "pass_id": r.json()["id"]}


async def test_every_api_route_needs_a_session(client: httpx.AsyncClient) -> None:
    app_routes = client._transport.app.openapi()["paths"]  # type: ignore[attr-defined]
    open_paths = {"/api/v1/auth/invite", "/api/v1/auth/logout", "/api/v1/blobs/{key}"}
    for path, methods in app_routes.items():
        if path in open_paths:
            continue
        url = path.replace("{team_id}", "00000000-0000-0000-0000-000000000000")
        for name in ("{survey_id}", "{pass_id}", "{member_id}"):
            url = url.replace(name, "00000000-0000-0000-0000-000000000000")
        for method in methods:
            r = await client.request(method.upper(), url)
            assert r.status_code in (401, 422), f"{method} {path} -> {r.status_code}"
            if r.status_code == 422:
                r = await client.request(method.upper(), url, json={})
                assert r.status_code in (401, 422)


async def test_invite_is_single_use(client: httpx.AsyncClient) -> None:
    _, _, code = await make_member(None, "Asha", Role.WALKER)
    await sign_in(client, code)
    me = (await client.get("/api/v1/me")).json()
    assert me["display_name"] == "Asha" and me["teams"][0]["role"] == "walker"
    client.cookies.clear()
    r = await client.post("/api/v1/auth/invite", json={"code": code})
    assert r.status_code == 400 and "already used" in r.json()["detail"]


async def test_mutations_need_csrf_header(client: httpx.AsyncClient) -> None:
    _, _, code = await make_member(None, "Asha", Role.ADMIN)
    r = await client.post("/api/v1/auth/invite", json={"code": code}, headers={"x-notchcount": ""})
    assert r.status_code == 403


async def test_other_team_cannot_see_or_upload(
    client: httpx.AsyncClient, walker_pass: dict[str, str]
) -> None:
    _, _, outsider = await make_member(None, "Outsider", Role.ADMIN)
    client.cookies.clear()
    await sign_in(client, outsider)
    assert (await client.get(f"/api/v1/surveys/{walker_pass['survey_id']}")).status_code == 404
    assert (await client.get(f"/api/v1/teams/{walker_pass['team_id']}/routes")).status_code == 404
    r = await _upload(client, walker_pass["pass_id"], jpeg_bytes(1), datetime.now(UTC))
    assert r.status_code == 404


async def test_walker_cannot_create_routes(client: httpx.AsyncClient, walker_pass: dict[str, str]) -> None:
    r = await client.post(
        f"/api/v1/teams/{walker_pass['team_id']}/routes", json={"name": "x route", "geometry": ROUTE}
    )
    assert r.status_code == 403


async def test_upload_is_idempotent_and_flags_location(
    client: httpx.AsyncClient, walker_pass: dict[str, str]
) -> None:
    data = jpeg_bytes(2)
    now = datetime.now(UTC)
    first = await _upload(client, walker_pass["pass_id"], data, now, lat=28.6139, lon=77.2095, accuracy_m=6)
    assert first.status_code == 200, first.text
    assert first.json()["duplicate"] is False and first.json()["flags"] == []
    again = await _upload(client, walker_pass["pass_id"], data, now, lat=28.6139, lon=77.2095, accuracy_m=6)
    assert again.json()["duplicate"] is True and again.json()["id"] == first.json()["id"]

    far = await _upload(
        client, walker_pass["pass_id"], jpeg_bytes(3), now, lat=28.70, lon=77.30, accuracy_m=80
    )
    assert set(far.json()["flags"]) == {"poor_gps", "outside_corridor"}
    none = await _upload(client, walker_pass["pass_id"], jpeg_bytes(4), now)
    assert none.json()["flags"] == ["no_gps"]

    p = (await client.get(f"/api/v1/passes/{walker_pass['pass_id']}")).json()
    assert p["photo_count"] == 3


async def test_upload_rejects_bad_bytes_and_times(
    client: httpx.AsyncClient, walker_pass: dict[str, str]
) -> None:
    data = jpeg_bytes(5)
    form = {"sha256": "0" * 64, "taken_at": datetime.now(UTC).isoformat()}
    r = await client.post(
        f"/api/v1/passes/{walker_pass['pass_id']}/photos",
        data=form,
        files={"file": ("p.jpg", data, "image/jpeg")},
    )
    assert r.status_code == 422
    r = await _upload(client, walker_pass["pass_id"], b"GIF89a....", datetime.now(UTC))
    assert r.status_code == 415
    early = datetime.now(UTC) - timedelta(hours=1)
    r = await _upload(client, walker_pass["pass_id"], jpeg_bytes(6), early)
    assert r.status_code == 422 and "before this pass started" in r.json()["detail"]


async def test_ended_pass_accepts_queued_photos_but_not_later_ones(
    client: httpx.AsyncClient, walker_pass: dict[str, str]
) -> None:
    taken = datetime.now(UTC) - timedelta(minutes=2)
    ended = datetime.now(UTC) - timedelta(minutes=1)
    r = await client.post(
        f"/api/v1/passes/{walker_pass['pass_id']}/end", json={"ended_at": ended.isoformat()}
    )
    assert r.status_code == 200 and r.json()["locked"] is True
    ok = await _upload(client, walker_pass["pass_id"], jpeg_bytes(7), taken)
    assert ok.status_code == 200
    late = await _upload(
        client, walker_pass["pass_id"], jpeg_bytes(8), datetime.now(UTC) + timedelta(minutes=4)
    )
    assert late.status_code == 422


async def test_second_walker_cannot_take_the_same_pass(
    client: httpx.AsyncClient, walker_pass: dict[str, str]
) -> None:
    _, _, code = await make_member(uuid.UUID(walker_pass["team_id"]), "Second walker", Role.WALKER)
    client.cookies.clear()
    await sign_in(client, code)
    r = await client.post(
        f"/api/v1/surveys/{walker_pass['survey_id']}/passes",
        json={"pass_no": 1, "started_at": datetime.now(UTC).isoformat()},
    )
    assert r.status_code == 409 and "already recorded by Walker" in r.json()["detail"]

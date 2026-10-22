"""Signed blob reads and the admin health page."""

from __future__ import annotations

import asyncio
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from notchcount_api.blobs import SERVABLE, PostgresBlobStore, verify
from notchcount_api.config import Settings
from notchcount_api.db.models import Detection, Job, JobStatus, Photo, Role, TeamMember
from notchcount_api.deps import DbDep, SettingsDep, UserDep
from notchcount_api.schemas import HealthOut, IntegrationOut

router = APIRouter(tags=["ops"])


@router.get("/blobs/{key:path}")
async def read_blob(
    key: str,
    db: DbDep,
    settings: SettingsDep,
    exp: Annotated[int, Query()],
    sig: Annotated[str, Query(min_length=64, max_length=64)],
) -> Response:
    if not verify(settings.blob_signing_secret.get_secret_value(), key, exp, sig):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This image link has expired. Reload the page.")
    found = await PostgresBlobStore(db).get(key)
    if found is None or found[0] not in SERVABLE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    _, content_type, data = found
    return Response(
        data,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )


async def _agentboxd_key(name: str, base: str, key: str | None, purpose: str) -> IntegrationOut:
    """A read-only call (list inboxes) that every key we ask for may make. Never sends anything."""
    if not key:
        return IntegrationOut(name=name, status="missing", detail=f"Not set on this server. {purpose}")
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            res = await client.get(f"{base.rstrip('/')}/inboxes", headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError:
        return IntegrationOut(name=name, status="unreachable", detail="Agentboxd did not answer.")
    if res.status_code == 200:
        return IntegrationOut(name=name, status="ok", detail=f"Key accepted. {purpose}")
    if res.status_code == 401:
        return IntegrationOut(name=name, status="invalid", detail="Agentboxd refused this key.")
    if res.status_code == 403:
        return IntegrationOut(name=name, status="no_permission", detail="The key lacks inboxes:read.")
    return IntegrationOut(name=name, status="unreachable", detail=f"Agentboxd answered {res.status_code}.")


async def _mojoauth(settings: Settings) -> IntegrationOut:
    if settings.mojoauth_api_key is None:
        return IntegrationOut(name="MojoAuth email codes", status="missing", detail="Not set on this server.")
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            res = await client.get(
                f"{settings.mojoauth_base_url.rstrip('/')}/token/jwks",
                headers={"x-api-key": settings.mojoauth_api_key.get_secret_value()},
            )
    except httpx.HTTPError:
        return IntegrationOut(
            name="MojoAuth email codes", status="unreachable", detail="MojoAuth did not answer."
        )
    if res.status_code == 200:
        return IntegrationOut(
            name="MojoAuth email codes", status="ok", detail="Key accepted. Sign-in by email code is on."
        )
    if res.status_code in (401, 403):
        return IntegrationOut(
            name="MojoAuth email codes", status="invalid", detail="MojoAuth refused this key."
        )
    return IntegrationOut(
        name="MojoAuth email codes", status="unreachable", detail=f"MojoAuth answered {res.status_code}."
    )


async def integrations(settings: Settings) -> list[IntegrationOut]:
    secret = (
        settings.agentboxd_webhook_secret.get_secret_value() if settings.agentboxd_webhook_secret else None
    )
    checks = await asyncio.gather(
        _mojoauth(settings),
        _agentboxd_key(
            "Agentboxd draft key",
            settings.agentboxd_base_url,
            settings.agentboxd_draft_key.get_secret_value() if settings.agentboxd_draft_key else None,
            "Writes the email draft.",
        ),
        _agentboxd_key(
            "Agentboxd send key",
            settings.agentboxd_base_url,
            settings.agentboxd_send_key.get_secret_value() if settings.agentboxd_send_key else None,
            "Used only when a person presses Approve and send.",
        ),
    )
    webhook = IntegrationOut(
        name="Agentboxd reply webhook",
        status="ok" if secret else "missing",
        detail="Secret set; replies are checked before they are stored."
        if secret
        else "Not set on this server. Replies cannot be received.",
    )
    return [*checks, webhook]


@router.get("/admin/health", response_model=HealthOut)
async def health(user: UserDep, db: DbDep, settings: SettingsDep) -> HealthOut:
    is_admin = (
        await db.execute(
            select(func.count())
            .select_from(TeamMember)
            .where(TeamMember.user_id == user.id, TeamMember.role == Role.ADMIN)
        )
    ).scalar_one()
    if not is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a team admin can see system health.")
    queue = {
        f"{kind}:{st.value}": n
        for kind, st, n in (
            await db.execute(select(Job.kind, Job.status, func.count()).group_by(Job.kind, Job.status))
        ).all()
    }
    dead = [
        {"id": j.id, "kind": j.kind, "attempts": j.attempts, "error": (j.last_error or "")[:300]}
        for j in (
            await db.execute(
                select(Job).where(Job.status == JobStatus.DEAD).order_by(Job.id.desc()).limit(20)
            )
        ).scalars()
    ]
    photos = {
        st.value: n
        for st, n in (await db.execute(select(Photo.status, func.count()).group_by(Photo.status))).all()
    }
    versions = [v for (v,) in (await db.execute(select(Detection.model_version).distinct())).all()]
    return HealthOut(
        integrations=await integrations(settings),
        public_base_url=settings.public_base_url,
        queue=queue,
        dead_jobs=dead,
        photos=photos,
        model_versions=versions,
    )

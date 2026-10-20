"""Signed blob reads and the admin health page."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from notchcount_api.blobs import SERVABLE, PostgresBlobStore, verify
from notchcount_api.db.models import Detection, Job, JobStatus, Photo, Role, TeamMember
from notchcount_api.deps import DbDep, SettingsDep, UserDep
from notchcount_api.schemas import HealthOut

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


@router.get("/admin/health", response_model=HealthOut)
async def health(user: UserDep, db: DbDep) -> HealthOut:
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
    return HealthOut(queue=queue, dead_jobs=dead, photos=photos, model_versions=versions)

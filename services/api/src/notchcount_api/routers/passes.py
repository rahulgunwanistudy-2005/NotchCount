"""Pass lifecycle and photo upload. The capture app may call these minutes or hours after the
fact (offline queue), so start and end times come from the phone and every call is idempotent."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from notchcount_api import jobs, ratelimit
from notchcount_api.blobs import Bucket, PostgresBlobStore
from notchcount_api.db.models import PassRow, Photo, Role, RouteRow, Survey, User, View
from notchcount_api.deps import DbDep, SettingsDep, UserDep, require_role
from notchcount_api.domain.integrity import PassWindow, PhotoRejected, check_photo, pass_start_flags
from notchcount_api.routers.setup import pass_out, survey_team
from notchcount_api.schemas import PassEnd, PassOut, PassStart, PhotoMeta, PhotoOut

router = APIRouter(tags=["passes"])

MAX_START_AGE = timedelta(hours=12)
JPEG_MAGIC = b"\xff\xd8\xff"


async def _pass_with_team(db: AsyncSession, pass_id: uuid.UUID) -> tuple[PassRow, Survey, RouteRow]:
    row = (
        await db.execute(
            select(PassRow, Survey, RouteRow)
            .join(Survey, Survey.id == PassRow.survey_id)
            .join(RouteRow, RouteRow.id == Survey.route_id)
            .where(PassRow.id == pass_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    return row[0], row[1], row[2]


async def _photo_count(db: AsyncSession, pass_id: uuid.UUID) -> int:
    return int(
        (
            await db.execute(select(func.count()).select_from(Photo).where(Photo.pass_id == pass_id))
        ).scalar_one()
    )


@router.post("/surveys/{survey_id}/passes", response_model=PassOut)
async def start_pass(
    survey_id: uuid.UUID, body: PassStart, user: UserDep, db: DbDep, settings: SettingsDep
) -> PassOut:
    found = await survey_team(db, survey_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    survey, team_id = found
    await require_role(db, user, team_id, Role.WALKER)
    now = datetime.now(UTC)
    started = body.started_at
    if started.tzinfo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Start time needs a time zone.")
    if started > now + timedelta(minutes=5) or started < now - MAX_START_AGE:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "The phone's clock looks wrong. Turn on automatic date and time, then start the pass again.",
        )
    existing = (
        await db.execute(
            select(PassRow).where(PassRow.survey_id == survey_id, PassRow.pass_no == body.pass_no)
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.observer_id != user.id:
            observer = (
                await db.execute(select(User.display_name).where(User.id == existing.observer_id))
            ).scalar_one()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Pass {body.pass_no} is already recorded by {observer}. Pick the next pass number.",
            )
        return pass_out(existing, user.display_name, await _photo_count(db, existing.id))
    row = PassRow(
        survey_id=survey_id,
        pass_no=body.pass_no,
        observer_id=user.id,
        started_at=started,
        flags=pass_start_flags(
            started, survey.start_window_local, survey.timezone, settings.pass_start_tolerance_min
        ),
    )
    db.add(row)
    await db.commit()
    return pass_out(row, user.display_name, 0)


@router.get("/passes/{pass_id}", response_model=PassOut)
async def get_pass(pass_id: uuid.UUID, user: UserDep, db: DbDep) -> PassOut:
    p, _, route = await _pass_with_team(db, pass_id)
    await require_role(db, user, route.team_id, Role.WALKER)
    name = (await db.execute(select(User.display_name).where(User.id == p.observer_id))).scalar_one()
    return pass_out(p, name, await _photo_count(db, p.id))


@router.get("/passes/{pass_id}/photos", response_model=list[PhotoMeta])
async def list_photos(pass_id: uuid.UUID, user: UserDep, db: DbDep) -> list[PhotoMeta]:
    _, _, route = await _pass_with_team(db, pass_id)
    await require_role(db, user, route.team_id, Role.WALKER)
    photos = (
        await db.execute(select(Photo).where(Photo.pass_id == pass_id).order_by(Photo.taken_at))
    ).scalars()
    return [
        PhotoMeta(
            id=p.id,
            taken_at=p.taken_at,
            shot=p.shot,
            accuracy_m=p.accuracy_m,
            has_location=p.geom is not None,
            flags=list(p.flags),
            status=p.status,
        )
        for p in photos
    ]


@router.post("/passes/{pass_id}/end", response_model=PassOut)
async def end_pass(pass_id: uuid.UUID, body: PassEnd, user: UserDep, db: DbDep) -> PassOut:
    p, _, route = await _pass_with_team(db, pass_id)
    role = await require_role(db, user, route.team_id, Role.WALKER)
    if p.observer_id != user.id and role is not Role.ADMIN:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the walker of this pass or a team admin can end it."
        )
    if not p.locked:
        ended = body.ended_at
        if ended.tzinfo is None or ended < p.started_at:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "End time must be after the start time."
            )
        p.ended_at = min(ended, datetime.now(UTC))
        p.locked = True
        await db.commit()
    name = (await db.execute(select(User.display_name).where(User.id == p.observer_id))).scalar_one()
    return pass_out(p, name, await _photo_count(db, p.id))


@router.post("/passes/{pass_id}/photos", response_model=PhotoOut)
async def upload_photo(
    pass_id: uuid.UUID,
    user: UserDep,
    db: DbDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
    sha256: Annotated[str, Form(min_length=64, max_length=64)],
    taken_at: Annotated[datetime, Form()],
    lat: Annotated[float | None, Form(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Form(ge=-180, le=180)] = None,
    accuracy_m: Annotated[float | None, Form(ge=0)] = None,
    heading: Annotated[float | None, Form(ge=0, le=360)] = None,
    shot: Annotated[View, Form()] = View.UNKNOWN,
) -> PhotoOut:
    p, _, route = await _pass_with_team(db, pass_id)
    await require_role(db, user, route.team_id, Role.WALKER)
    if p.observer_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the walker of this pass can add photos to it.")

    existing = (await db.execute(select(Photo).where(Photo.sha256 == sha256.lower()))).scalar_one_or_none()
    if existing is not None:
        if existing.pass_id != pass_id:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "This photo was already uploaded to a different pass."
            )
        return PhotoOut(
            id=existing.id,
            pass_id=pass_id,
            sha256=existing.sha256,
            duplicate=True,
            flags=list(existing.flags),
        )

    await ratelimit.hit(
        db,
        f"upload:{user.id}",
        settings.upload_rate_per_minute,
        timedelta(minutes=1),
        "Uploading too fast. The app will retry in a minute.",
    )
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Photo is too large.")
    if not data.startswith(JPEG_MAGIC):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only JPEG photos are accepted.")
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256.lower():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Photo was damaged in upload. The app will retry."
        )

    has_location = lat is not None and lon is not None
    inside: bool | None = None
    if has_location:
        point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        inside = bool(
            (
                await db.execute(
                    select(
                        func.ST_DWithin(
                            cast(RouteRow.geom, Geography), cast(point, Geography), route.corridor_m
                        )
                    ).where(RouteRow.id == route.id)
                )
            ).scalar_one()
        )
    try:
        check = check_photo(
            PassWindow(p.started_at, p.ended_at),
            taken_at,
            datetime.now(UTC),
            accuracy_m,
            has_location,
            inside,
            poor_accuracy_m=settings.poor_gps_accuracy_m,
            grace_after_end=timedelta(minutes=settings.upload_grace_after_end_min),
        )
    except PhotoRejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    photo_id = uuid.uuid4()
    qkey = f"quarantine/{photo_id}.jpg"
    await PostgresBlobStore(db).put(Bucket.QUARANTINE, qkey, data, "image/jpeg")
    db.add(
        Photo(
            id=photo_id,
            pass_id=pass_id,
            sha256=digest,
            taken_at=taken_at,
            geom=func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326) if has_location else None,
            accuracy_m=accuracy_m,
            heading=heading,
            shot=shot,
            quarantine_key=qkey,
            flags=check.flags,
        )
    )
    await jobs.enqueue(db, "ingest_photo", {"photo_id": str(photo_id)}, dedupe_key=f"ingest:{photo_id}")
    try:
        await db.commit()
    except IntegrityError:
        # The same photo arrived twice at once (the app retried); the other request stored it.
        await db.rollback()
        stored = (await db.execute(select(Photo).where(Photo.sha256 == digest))).scalar_one()
        return PhotoOut(
            id=stored.id, pass_id=stored.pass_id, sha256=digest, duplicate=True, flags=list(stored.flags)
        )
    return PhotoOut(id=photo_id, pass_id=pass_id, sha256=digest, duplicate=False, flags=check.flags)

"""Labelling, review, model training and estimates for a survey."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import Text, and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from notchcount_api import jobs
from notchcount_api.blobs import sign
from notchcount_api.db.models import (
    Detection,
    Estimate,
    MatchPair,
    ModelVersion,
    NotchCallRow,
    NotchDecision,
    NotchLabel,
    PairDecision,
    PairLabel,
    PassRow,
    Photo,
    Role,
    Survey,
    User,
)
from notchcount_api.deps import DbDep, SettingsDep, UserDep, require_role
from notchcount_api.routers.setup import survey_team

router = APIRouter(tags=["analysis"])

REVIEW_LOW, REVIEW_HIGH = 0.2, 0.8
NOTCH_REVIEW_BELOW = 0.8
COSINE_BANDS = (0.0, 0.55, 0.7, 0.82, 1.01)


class CropOut(BaseModel):
    detection_id: uuid.UUID
    url: str
    pass_no: int
    taken_at: datetime
    view: str
    quality: float


class PairItem(BaseModel):
    kind: Literal["pair"] = "pair"
    pair_id: uuid.UUID
    a: CropOut
    b: CropOut
    p_same: float | None
    calibrated: bool
    route_m: float | None
    minutes_apart: float
    remaining: int


class EarItem(BaseModel):
    kind: Literal["ear"] = "ear"
    detection_id: uuid.UUID
    crop: CropOut
    p_notched: float | None
    p_not_visible: float | None
    remaining: int


class PairAnswer(BaseModel):
    pair_id: uuid.UUID
    decision: PairDecision


class EarAnswer(BaseModel):
    detection_id: uuid.UUID
    decision: NotchDecision


class ProgressOut(BaseModel):
    photos: dict[str, int]
    detections: int
    usable_detections: int
    pairs: int
    pairs_labelled: int
    positive_labels: int
    ears_labelled: int
    review_pairs_left: int
    review_ears_left: int
    match_model: str | None
    notch_model: str | None


class EstimateOut(BaseModel):
    id: uuid.UUID
    survey_id: uuid.UUID
    method: str
    status: str
    params: dict[str, Any]
    results: dict[str, Any] | None
    error: str | None
    data_hash: str | None
    code_version: str
    seed: int
    created_at: datetime


async def _survey_for(
    db: AsyncSession, user: User, survey_id: uuid.UUID, role: Role
) -> tuple[Survey, uuid.UUID]:
    found = await survey_team(db, survey_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    await require_role(db, user, found[1], role)
    return found


def _crop(settings: SettingsDep, det: Detection, pass_no: int, taken_at: datetime) -> CropOut:
    return CropOut(
        detection_id=det.id,
        url=sign(settings.blob_signing_secret.get_secret_value(), det.crop_key, settings.signed_url_seconds),
        pass_no=pass_no,
        taken_at=taken_at,
        view=det.view.value,
        quality=det.quality,
    )


def _survey_detections(survey_id: uuid.UUID) -> Any:
    return (
        select(Detection.id)
        .join(Photo, Photo.id == Detection.photo_id)
        .join(PassRow, PassRow.id == Photo.pass_id)
        .where(PassRow.survey_id == survey_id)
    )


async def _pair_item(db: AsyncSession, settings: SettingsDep, pair: MatchPair, remaining: int) -> PairItem:
    rows = (
        await db.execute(
            select(Detection, PassRow.pass_no, Photo.taken_at)
            .join(Photo, Photo.id == Detection.photo_id)
            .join(PassRow, PassRow.id == Photo.pass_id)
            .where(Detection.id.in_([pair.a_detection, pair.b_detection]))
        )
    ).all()
    by_id = {d.id: (d, pn, t) for d, pn, t in rows}
    a, b = by_id[pair.a_detection], by_id[pair.b_detection]
    route_km = pair.features.get("route_km")
    return PairItem(
        pair_id=pair.id,
        a=_crop(settings, *a),
        b=_crop(settings, *b),
        p_same=pair.p_same,
        calibrated=bool(pair.model_version and not pair.model_version.startswith("prior")),
        route_m=None if route_km is None else round(route_km * 1000),
        minutes_apart=abs((a[2] - b[2]).total_seconds()) / 60,
        remaining=remaining,
    )


@router.get("/surveys/{survey_id}/progress", response_model=ProgressOut)
async def progress(survey_id: uuid.UUID, user: UserDep, db: DbDep) -> ProgressOut:
    _, team_id = await _survey_for(db, user, survey_id, Role.WALKER)
    photos = dict(
        (
            await db.execute(
                select(Photo.status, func.count())
                .join(PassRow, PassRow.id == Photo.pass_id)
                .where(PassRow.survey_id == survey_id)
                .group_by(Photo.status)
            )
        ).all()
    )
    dets = _survey_detections(survey_id).subquery()
    n_det, n_usable = (
        await db.execute(
            select(func.count(), func.count().filter(Detection.usable)).where(
                Detection.id.in_(select(dets.c.id))
            )
        )
    ).one()
    pair_stats = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(MatchPair.decision.is_not(None)),
                func.count().filter(MatchPair.decision == PairDecision.SAME),
                func.count().filter(
                    and_(
                        MatchPair.decision.is_(None),
                        MatchPair.p_same > REVIEW_LOW,
                        MatchPair.p_same < REVIEW_HIGH,
                    )
                ),
            ).where(MatchPair.survey_id == survey_id)
        )
    ).one()
    ears = (
        await db.execute(
            select(
                func.count().filter(NotchCallRow.decision.is_not(None)),
                func.count().filter(
                    and_(
                        NotchCallRow.decision.is_(None),
                        NotchCallRow.p_notched.is_not(None),
                        func.greatest(
                            NotchCallRow.p_notched, NotchCallRow.p_not_notched, NotchCallRow.p_not_visible
                        )
                        < NOTCH_REVIEW_BELOW,
                    )
                ),
            ).where(NotchCallRow.detection_id.in_(select(dets.c.id)))
        )
    ).one()
    latest = {
        kind: (
            await db.execute(
                select(ModelVersion.version)
                .where(ModelVersion.team_id == team_id, ModelVersion.kind == kind)
                .order_by(ModelVersion.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        for kind in ("match", "notch")
    }
    return ProgressOut(
        photos={k.value: int(v) for k, v in photos.items()},
        detections=int(n_det),
        usable_detections=int(n_usable),
        pairs=int(pair_stats[0]),
        pairs_labelled=int(pair_stats[1]),
        positive_labels=int(pair_stats[2]),
        ears_labelled=int(ears[0]),
        review_pairs_left=int(pair_stats[3]),
        review_ears_left=int(ears[1]),
        match_model=latest["match"],
        notch_model=latest["notch"],
    )


@router.post("/surveys/{survey_id}/match", status_code=status.HTTP_202_ACCEPTED)
async def find_matches(survey_id: uuid.UUID, user: UserDep, db: DbDep) -> dict[str, str]:
    await _survey_for(db, user, survey_id, Role.ADMIN)
    await jobs.enqueue(db, "match_survey", {"survey_id": str(survey_id)}, dedupe_key=None)
    await db.commit()
    return {"status": "queued"}


class PublishOut(BaseModel):
    slug: str
    url: str


@router.post("/surveys/{survey_id}/publish", response_model=PublishOut)
async def publish_report(survey_id: uuid.UUID, user: UserDep, db: DbDep, settings: SettingsDep) -> PublishOut:
    """Give the survey a public report address (route-level numbers only). Idempotent."""
    survey, _ = await _survey_for(db, user, survey_id, Role.ADMIN)
    if survey.public_slug is None:
        survey.public_slug = secrets.token_urlsafe(9)
        await db.commit()
    return PublishOut(slug=survey.public_slug, url=f"{settings.public_base_url}/r/{survey.public_slug}")


@router.post("/surveys/{survey_id}/train", status_code=status.HTTP_202_ACCEPTED)
async def train(survey_id: uuid.UUID, user: UserDep, db: DbDep) -> dict[str, str]:
    _, team_id = await _survey_for(db, user, survey_id, Role.ADMIN)
    await jobs.enqueue(db, "train_models", {"team_id": str(team_id), "survey_id": str(survey_id)})
    await db.commit()
    return {"status": "queued"}


@router.get("/surveys/{survey_id}/labeling/pairs", response_model=PairItem | None)
async def next_label_pair(
    survey_id: uuid.UUID, user: UserDep, db: DbDep, settings: SettingsDep
) -> PairItem | None:
    """Next pair this person has not answered, cycling through similarity bands so the labels
    cover easy and hard cases (BIBLE 5.3: stratified by similarity band)."""
    await _survey_for(db, user, survey_id, Role.REVIEWER)
    mine = select(PairLabel.pair_id).where(PairLabel.user_id == user.id)
    base = select(MatchPair).where(MatchPair.survey_id == survey_id, MatchPair.id.not_in(mine))
    answered = (
        await db.execute(select(func.count()).select_from(PairLabel).where(PairLabel.user_id == user.id))
    ).scalar_one()
    remaining = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    if remaining == 0:
        return None
    cos = MatchPair.features["cosine"].as_float()
    bands = len(COSINE_BANDS) - 1
    for k in range(bands):
        lo, hi = COSINE_BANDS[(answered + k) % bands], COSINE_BANDS[(answered + k) % bands + 1]
        pair = (
            await db.execute(
                base.where(cos >= lo, cos < hi)
                .order_by(MatchPair.decision.is_not(None), func.md5(cast(MatchPair.id, Text)))
                .limit(1)
            )
        ).scalar_one_or_none()
        if pair is not None:
            return await _pair_item(db, settings, pair, int(remaining))
    return None


@router.post("/labels/pairs", status_code=status.HTTP_204_NO_CONTENT)
async def answer_pair(body: PairAnswer, user: UserDep, db: DbDep) -> None:
    pair = (await db.execute(select(MatchPair).where(MatchPair.id == body.pair_id))).scalar_one_or_none()
    if pair is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    await _survey_for(db, user, pair.survey_id, Role.REVIEWER)
    db.add(PairLabel(pair_id=pair.id, user_id=user.id, decision=body.decision))
    await db.flush()
    answers = (
        (
            await db.execute(
                select(PairLabel.decision)
                .where(PairLabel.pair_id == pair.id)
                .order_by(PairLabel.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    definite = {a for a in answers if a is not PairDecision.UNSURE}
    # Disagreeing people leave the pair undecided (the model's probability stands); agreement decides.
    pair.decision = definite.pop() if len(definite) == 1 else (PairDecision.UNSURE if not definite else None)
    pair.decided_by, pair.decided_at = user.id, datetime.now(UTC)
    await db.commit()


@router.get("/surveys/{survey_id}/labeling/ears", response_model=EarItem | None)
async def next_label_ear(
    survey_id: uuid.UUID, user: UserDep, db: DbDep, settings: SettingsDep
) -> EarItem | None:
    """Head shots first, then other crops, that this person has not labelled."""
    await _survey_for(db, user, survey_id, Role.REVIEWER)
    mine = select(NotchLabel.detection_id).where(NotchLabel.user_id == user.id)
    q = (
        select(Detection, PassRow.pass_no, Photo.taken_at)
        .join(Photo, Photo.id == Detection.photo_id)
        .join(PassRow, PassRow.id == Photo.pass_id)
        .where(PassRow.survey_id == survey_id, Detection.usable, Detection.id.not_in(mine))
    )
    remaining = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    row = (
        await db.execute(
            q.order_by(
                case((Detection.view == "head", 0), else_=1), Detection.quality.desc(), Detection.id
            ).limit(1)
        )
    ).one_or_none()
    if row is None:
        return None
    det, pass_no, taken_at = row
    call = (
        await db.execute(select(NotchCallRow).where(NotchCallRow.detection_id == det.id))
    ).scalar_one_or_none()
    return EarItem(
        detection_id=det.id,
        crop=_crop(settings, det, pass_no, taken_at),
        p_notched=call.p_notched if call else None,
        p_not_visible=call.p_not_visible if call else None,
        remaining=int(remaining),
    )


@router.post("/labels/ears", status_code=status.HTTP_204_NO_CONTENT)
async def answer_ear(body: EarAnswer, user: UserDep, db: DbDep) -> None:
    row = (
        await db.execute(
            select(PassRow.survey_id)
            .join(Photo, Photo.pass_id == PassRow.id)
            .join(Detection, Detection.photo_id == Photo.id)
            .where(Detection.id == body.detection_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    await _survey_for(db, user, row, Role.REVIEWER)
    db.add(NotchLabel(detection_id=body.detection_id, user_id=user.id, decision=body.decision))
    await db.flush()
    answers = (
        (await db.execute(select(NotchLabel.decision).where(NotchLabel.detection_id == body.detection_id)))
        .scalars()
        .all()
    )
    definite = {a for a in answers if a is not NotchDecision.UNSURE}
    decision = definite.pop() if len(definite) == 1 else None
    call = (
        await db.execute(select(NotchCallRow).where(NotchCallRow.detection_id == body.detection_id))
    ).scalar_one_or_none()
    if call is None:
        call = NotchCallRow(detection_id=body.detection_id)
        db.add(call)
    call.decision = decision
    call.decided_by, call.decided_at = user.id, datetime.now(UTC)
    await db.commit()


@router.get("/surveys/{survey_id}/review/next", response_model=PairItem | EarItem | None)
async def review_next(
    survey_id: uuid.UUID, user: UserDep, db: DbDep, settings: SettingsDep
) -> PairItem | EarItem | None:
    """Uncertain matches first (those that can change m2 come first), then uncertain ear calls."""
    await _survey_for(db, user, survey_id, Role.REVIEWER)
    a_pass, b_pass = aliased(PassRow), aliased(PassRow)
    a_photo, b_photo = aliased(Photo), aliased(Photo)
    a_det, b_det = aliased(Detection), aliased(Detection)
    uncertain = (
        select(MatchPair)
        .join(a_det, a_det.id == MatchPair.a_detection)
        .join(b_det, b_det.id == MatchPair.b_detection)
        .join(a_photo, a_photo.id == a_det.photo_id)
        .join(b_photo, b_photo.id == b_det.photo_id)
        .join(a_pass, a_pass.id == a_photo.pass_id)
        .join(b_pass, b_pass.id == b_photo.pass_id)
        .where(
            MatchPair.survey_id == survey_id,
            or_(MatchPair.decision.is_(None), MatchPair.decision == PairDecision.UNSURE),
            MatchPair.p_same > REVIEW_LOW,
            MatchPair.p_same < REVIEW_HIGH,
            MatchPair.id.not_in(select(PairLabel.pair_id).where(PairLabel.user_id == user.id)),
        )
    )
    remaining = (await db.execute(select(func.count()).select_from(uncertain.subquery()))).scalar_one()
    pair = (
        await db.execute(
            uncertain.order_by(
                case((a_pass.pass_no != b_pass.pass_no, 0), else_=1), func.abs(MatchPair.p_same - 0.5)
            ).limit(1)
        )
    ).scalar_one_or_none()
    if pair is not None:
        return await _pair_item(db, settings, pair, int(remaining))
    row = (
        await db.execute(
            select(Detection, PassRow.pass_no, Photo.taken_at, NotchCallRow)
            .join(NotchCallRow, NotchCallRow.detection_id == Detection.id)
            .join(Photo, Photo.id == Detection.photo_id)
            .join(PassRow, PassRow.id == Photo.pass_id)
            .where(
                PassRow.survey_id == survey_id,
                NotchCallRow.decision.is_(None),
                NotchCallRow.p_notched.is_not(None),
                func.greatest(NotchCallRow.p_notched, NotchCallRow.p_not_notched, NotchCallRow.p_not_visible)
                < NOTCH_REVIEW_BELOW,
                Detection.id.not_in(select(NotchLabel.detection_id).where(NotchLabel.user_id == user.id)),
            )
            .order_by(Detection.quality.desc())
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        return None
    det, pass_no, taken_at, call = row
    return EarItem(
        detection_id=det.id,
        crop=_crop(settings, det, pass_no, taken_at),
        p_notched=call.p_notched,
        p_not_visible=call.p_not_visible,
        remaining=0,
    )


@router.post(
    "/surveys/{survey_id}/estimates", response_model=EstimateOut, status_code=status.HTTP_202_ACCEPTED
)
async def request_estimate(
    survey_id: uuid.UUID,
    user: UserDep,
    db: DbDep,
    replicates: Annotated[int, Query(ge=100, le=5000)] = 2000,
    seed: Annotated[int, Query(ge=0, le=2**31 - 1)] = 20261021,
) -> EstimateOut:
    await _survey_for(db, user, survey_id, Role.ADMIN)
    from notchcount_stats import __version__

    est = Estimate(
        survey_id=survey_id,
        method="pending",
        params={"replicates": replicates, "target_share": 0.7},
        code_version=f"notchcount_stats {__version__}",
        seed=seed,
        status="queued",
        created_by=user.id,
    )
    db.add(est)
    await db.flush()
    await jobs.enqueue(db, "estimate", {"estimate_id": str(est.id)}, dedupe_key=f"estimate:{est.id}")
    await db.commit()
    return _estimate_out(est)


def _estimate_out(e: Estimate) -> EstimateOut:
    return EstimateOut(
        id=e.id,
        survey_id=e.survey_id,
        method=e.method,
        status=e.status,
        params=e.params,
        results=e.results,
        error=e.error,
        data_hash=e.data_hash,
        code_version=e.code_version,
        seed=e.seed,
        created_at=e.created_at,
    )


@router.get("/surveys/{survey_id}/estimates", response_model=list[EstimateOut])
async def list_estimates(survey_id: uuid.UUID, user: UserDep, db: DbDep) -> list[EstimateOut]:
    await _survey_for(db, user, survey_id, Role.WALKER)
    rows = (
        await db.execute(
            select(Estimate)
            .where(Estimate.survey_id == survey_id)
            .order_by(Estimate.created_at.desc())
            .limit(20)
        )
    ).scalars()
    return [_estimate_out(e) for e in rows]

"""Relational model (BIBLE 4.2). Every team-owned row is reachable from a team id; queries in
the routers always filter by the caller's team memberships."""

from __future__ import annotations

import uuid
from datetime import datetime, time
from enum import StrEnum
from typing import Any

from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 384

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _enum(cls: type[StrEnum], name: str) -> SAEnum:
    return SAEnum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class Role(StrEnum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    WALKER = "walker"


class SurveyStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class PhotoStatus(StrEnum):
    QUARANTINED = "quarantined"
    PROCESSED = "processed"
    FAILED = "failed"


class View(StrEnum):
    SIDE = "side"
    HEAD = "head"
    UNKNOWN = "unknown"


class PairDecision(StrEnum):
    SAME = "same"
    DIFFERENT = "different"
    UNSURE = "unsure"


class NotchDecision(StrEnum):
    NOTCHED = "notched"
    NOT_NOTCHED = "not_notched"
    NOT_VISIBLE = "not_visible"
    UNSURE = "unsure"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    DEAD = "dead"


class CaseEventKind(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SENT = "sent"
    REPLY = "reply"
    HELD = "held"
    ERROR = "error"


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _uuid_pk()
    auth_subject: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    phone_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created()


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    notch_convention: Mapped[str] = mapped_column(String(40), nullable=False, default="default")
    created_at: Mapped[datetime] = _created()


class TeamMember(Base):
    __tablename__ = "team_members"
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[Role] = mapped_column(_enum(Role, "role"), nullable=False)


class Invite(Base):
    """One-time sign-in code for the interim invite auth provider (see docs/DECISIONS.md)."""

    __tablename__ = "invites"
    id: Mapped[uuid.UUID] = _uuid_pk()
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class RouteRow(Base):
    __tablename__ = "routes"
    id: Mapped[uuid.UUID] = _uuid_pk()
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    geom: Mapped[Any] = mapped_column(Geometry("LINESTRING", srid=4326), nullable=False)
    corridor_m: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (CheckConstraint("corridor_m between 5 and 500", name="corridor_range"),)


class Survey(Base):
    __tablename__ = "surveys"
    id: Mapped[uuid.UUID] = _uuid_pk()
    route_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    start_window_local: Mapped[time] = mapped_column(Time, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    status: Mapped[SurveyStatus] = mapped_column(
        _enum(SurveyStatus, "survey_status"), nullable=False, default=SurveyStatus.OPEN
    )
    public_slug: Mapped[str | None] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = _created()


class PassRow(Base):
    __tablename__ = "passes"
    id: Mapped[uuid.UUID] = _uuid_pk()
    survey_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False)
    pass_no: Mapped[int] = mapped_column(Integer, nullable=False)
    observer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    flags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False, default=list)
    __table_args__ = (
        UniqueConstraint("survey_id", "pass_no", name="uq_passes_survey_pass_no"),
        CheckConstraint("pass_no between 1 and 5", name="pass_no_range"),
    )


class Photo(Base):
    __tablename__ = "photos"
    id: Mapped[uuid.UUID] = _uuid_pk()
    pass_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("passes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = _created()
    geom: Mapped[Any | None] = mapped_column(Geometry("POINT", srid=4326))
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    heading: Mapped[float | None] = mapped_column(Float)
    shot: Mapped[View] = mapped_column(_enum(View, "photo_view"), nullable=False, default=View.UNKNOWN)
    storage_key: Mapped[str | None] = mapped_column(String(200))
    quarantine_key: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[PhotoStatus] = mapped_column(
        _enum(PhotoStatus, "photo_status"), nullable=False, default=PhotoStatus.QUARANTINED
    )
    flags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    persons_blurred: Mapped[int | None] = mapped_column(Integer)
    vehicles_blurred: Mapped[int | None] = mapped_column(Integer)


class Detection(Base):
    __tablename__ = "detections"
    id: Mapped[uuid.UUID] = _uuid_pk()
    photo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bbox: Mapped[list[float]] = mapped_column(ARRAY(Float), nullable=False)
    conf: Mapped[float] = mapped_column(Float, nullable=False)
    crop_key: Mapped[str] = mapped_column(String(200), nullable=False)
    quality: Mapped[float] = mapped_column(Float, nullable=False)
    usable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    embedding: Mapped[Any | None] = mapped_column(Vector(EMBEDDING_DIM))
    color_hist: Mapped[list[float] | None] = mapped_column(ARRAY(Float))
    view: Mapped[View] = mapped_column(_enum(View, "photo_view"), nullable=False, default=View.UNKNOWN)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = _created()
    __table_args__ = (
        Index(
            "ix_detections_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class MatchPair(Base):
    __tablename__ = "match_pairs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    survey_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    a_detection: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("detections.id", ondelete="CASCADE"), nullable=False
    )
    b_detection: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("detections.id", ondelete="CASCADE"), nullable=False
    )
    features: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False, default=dict)
    p_same: Mapped[float | None] = mapped_column(Float)
    model_version: Mapped[str | None] = mapped_column(String(80))
    purpose: Mapped[str] = mapped_column(String(20), nullable=False, default="match")
    decision: Mapped[PairDecision | None] = mapped_column(_enum(PairDecision, "pair_decision"))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("a_detection", "b_detection", name="uq_match_pairs_ab"),
        CheckConstraint("a_detection < b_detection", name="ordered"),
    )


class PairLabel(Base):
    """Every individual reviewer answer, so agreement between labellers can be reported."""

    __tablename__ = "pair_labels"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    pair_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("match_pairs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    decision: Mapped[PairDecision] = mapped_column(_enum(PairDecision, "pair_decision"), nullable=False)
    created_at: Mapped[datetime] = _created()


class Individual(Base):
    __tablename__ = "individuals"
    id: Mapped[uuid.UUID] = _uuid_pk()
    survey_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)


class SightingRow(Base):
    __tablename__ = "sightings"
    detection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("detections.id", ondelete="CASCADE"), primary_key=True
    )
    individual_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("individuals.id", ondelete="CASCADE"), primary_key=True
    )
    pass_no: Mapped[int] = mapped_column(Integer, nullable=False)


class NotchCallRow(Base):
    __tablename__ = "notch_calls"
    detection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("detections.id", ondelete="CASCADE"), primary_key=True
    )
    p_notched: Mapped[float | None] = mapped_column(Float)
    p_not_notched: Mapped[float | None] = mapped_column(Float)
    p_not_visible: Mapped[float | None] = mapped_column(Float)
    model_version: Mapped[str | None] = mapped_column(String(80))
    decision: Mapped[NotchDecision | None] = mapped_column(_enum(NotchDecision, "notch_decision"))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotchLabel(Base):
    __tablename__ = "notch_labels"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    detection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("detections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    decision: Mapped[NotchDecision] = mapped_column(_enum(NotchDecision, "notch_decision"), nullable=False)
    created_at: Mapped[datetime] = _created()


class Estimate(Base):
    __tablename__ = "estimates"
    id: Mapped[uuid.UUID] = _uuid_pk()
    survey_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    results: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    data_hash: Mapped[str | None] = mapped_column(String(64))
    code_version: Mapped[str] = mapped_column(String(80), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = _created()


class ModelVersion(Base):
    """A fitted match or notch model for a team, stored as JSON coefficients (never pickled)."""

    __tablename__ = "model_versions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = _created()


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[uuid.UUID] = _uuid_pk()
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    authority: Mapped[str] = mapped_column(String(200), nullable=False)
    area_desc: Mapped[str] = mapped_column(Text, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    period: Mapped[str] = mapped_column(String(80), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[uuid.UUID] = _uuid_pk()
    survey_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    authority_name: Mapped[str] = mapped_column(String(200), nullable=False)
    authority_email: Mapped[str] = mapped_column(String(254), nullable=False)
    agentboxd_inbox_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = _created()


class CaseEvent(Base):
    __tablename__ = "case_events"
    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[CaseEventKind] = mapped_column(_enum(CaseEventKind, "case_event_kind"), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    external_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime] = _created()


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    status: Mapped[JobStatus] = mapped_column(
        _enum(JobStatus, "job_status"), nullable=False, default=JobStatus.QUEUED
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    locked_by: Mapped[str | None] = mapped_column(String(80))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_jobs_ready", "status", "run_after"),)


class Blob(Base):
    """Private object storage inside Postgres; used until a Supabase Storage key is configured."""

    __tablename__ = "blobs"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    bucket: Mapped[str] = mapped_column(String(20), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = _created()


class RateEvent(Base):
    __tablename__ = "rate_events"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    bucket: Mapped[str] = mapped_column(String(120), nullable=False)
    at: Mapped[datetime] = _created()
    __table_args__ = (Index("ix_rate_events_bucket_at", "bucket", "at"),)

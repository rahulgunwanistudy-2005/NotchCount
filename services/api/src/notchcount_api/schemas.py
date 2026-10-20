"""Request and response bodies. Field names are what the web app sees."""

from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from notchcount_api.db.models import Role, SurveyStatus

Lon = Annotated[float, Field(ge=-180, le=180)]
Lat = Annotated[float, Field(ge=-90, le=90)]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class InviteRedeem(BaseModel):
    code: str = Field(min_length=10, max_length=64)


class TeamOut(Out):
    id: uuid.UUID
    name: str
    city: str
    role: Role


class MeOut(Out):
    id: uuid.UUID
    display_name: str
    teams: list[TeamOut]


class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    city: str = Field(min_length=2, max_length=120)


class MemberCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    role: Role = Role.WALKER


class MemberInviteOut(Out):
    user_id: uuid.UUID
    display_name: str
    role: Role
    invite_url: str


class MemberOut(Out):
    user_id: uuid.UUID
    display_name: str
    role: Role


class LineString(BaseModel):
    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[Lon, Lat]] = Field(min_length=2, max_length=2000)


class RouteCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    geometry: LineString
    corridor_m: int = Field(default=40, ge=5, le=500)


class RouteOut(Out):
    id: uuid.UUID
    team_id: uuid.UUID
    name: str
    corridor_m: int
    length_m: float
    geometry: LineString


class SurveyCreate(BaseModel):
    route_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)
    start_window_local: time

    @field_validator("start_window_local")
    @classmethod
    def _no_tz(cls, v: time) -> time:
        return v.replace(tzinfo=None, second=0, microsecond=0)


class PassOut(Out):
    id: uuid.UUID
    survey_id: uuid.UUID
    pass_no: int
    observer_id: uuid.UUID
    observer_name: str
    started_at: datetime
    ended_at: datetime | None
    locked: bool
    flags: list[str]
    photo_count: int


class SurveyOut(Out):
    id: uuid.UUID
    team_id: uuid.UUID
    name: str
    status: SurveyStatus
    start_window_local: time
    timezone: str
    route: RouteOut
    passes: list[PassOut]


class PassStart(BaseModel):
    pass_no: int = Field(ge=1, le=5)
    started_at: datetime


class PassEnd(BaseModel):
    ended_at: datetime


class PhotoOut(Out):
    id: uuid.UUID
    pass_id: uuid.UUID
    sha256: str
    duplicate: bool
    flags: list[str]


class HealthOut(Out):
    queue: dict[str, int]
    dead_jobs: list[dict[str, str | int | None]]
    photos: dict[str, int]
    model_versions: list[str]

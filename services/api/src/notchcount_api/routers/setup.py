"""Teams, members, routes and surveys."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_AsGeoJSON, ST_GeomFromGeoJSON, ST_Length
from sqlalchemy import Select, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from notchcount_api.auth.invites import create_invite
from notchcount_api.db.models import (
    PassRow,
    Photo,
    Role,
    RouteRow,
    Survey,
    Team,
    TeamMember,
    User,
)
from notchcount_api.deps import DbDep, SettingsDep, UserDep, require_role
from notchcount_api.schemas import (
    LineString,
    MemberCreate,
    MemberInviteOut,
    MemberOut,
    MeOut,
    PassOut,
    RouteCreate,
    RouteOut,
    SurveyCreate,
    SurveyOut,
    TeamCreate,
    TeamOut,
)

router = APIRouter(tags=["setup"])


async def my_teams(db: AsyncSession, user: User) -> list[TeamOut]:
    rows = (
        await db.execute(
            select(Team, TeamMember.role)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(TeamMember.user_id == user.id)
            .order_by(Team.created_at)
        )
    ).all()
    return [TeamOut(id=t.id, name=t.name, city=t.city, role=r) for t, r in rows]


@router.get("/me", response_model=MeOut)
async def me(user: UserDep, db: DbDep) -> MeOut:
    return MeOut(id=user.id, display_name=user.display_name, teams=await my_teams(db, user))


@router.post("/teams", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
async def create_team(body: TeamCreate, user: UserDep, db: DbDep) -> TeamOut:
    team = Team(name=body.name, city=body.city)
    db.add(team)
    await db.flush()
    db.add(TeamMember(team_id=team.id, user_id=user.id, role=Role.ADMIN))
    await db.commit()
    return TeamOut(id=team.id, name=team.name, city=team.city, role=Role.ADMIN)


@router.get("/teams/{team_id}/members", response_model=list[MemberOut])
async def list_members(team_id: uuid.UUID, user: UserDep, db: DbDep) -> list[MemberOut]:
    await require_role(db, user, team_id, Role.REVIEWER)
    rows = (
        await db.execute(
            select(User, TeamMember.role)
            .join(TeamMember, TeamMember.user_id == User.id)
            .where(TeamMember.team_id == team_id)
            .order_by(User.display_name)
        )
    ).all()
    return [MemberOut(user_id=u.id, display_name=u.display_name, role=r) for u, r in rows]


@router.post("/teams/{team_id}/members", response_model=MemberInviteOut, status_code=status.HTTP_201_CREATED)
async def add_member(
    team_id: uuid.UUID, body: MemberCreate, user: UserDep, db: DbDep, settings: SettingsDep
) -> MemberInviteOut:
    """Create a team member and a one-time sign-in link for them."""
    await require_role(db, user, team_id, Role.ADMIN)
    member = User(auth_subject=f"invite:{uuid.uuid4()}", display_name=body.display_name)
    db.add(member)
    await db.flush()
    db.add(TeamMember(team_id=team_id, user_id=member.id, role=body.role))
    code = await create_invite(db, member.id)
    await db.commit()
    return MemberInviteOut(
        user_id=member.id,
        display_name=member.display_name,
        role=body.role,
        invite_url=f"{settings.public_base_url}/join#{code}",
    )


@router.post("/teams/{team_id}/members/{member_id}/invite", response_model=MemberInviteOut)
async def reissue_invite(
    team_id: uuid.UUID, member_id: uuid.UUID, user: UserDep, db: DbDep, settings: SettingsDep
) -> MemberInviteOut:
    await require_role(db, user, team_id, Role.ADMIN)
    row = (
        await db.execute(
            select(User, TeamMember.role)
            .join(TeamMember, TeamMember.user_id == User.id)
            .where(TeamMember.team_id == team_id, User.id == member_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    code = await create_invite(db, member_id)
    await db.commit()
    return MemberInviteOut(
        user_id=member_id,
        display_name=row[0].display_name,
        role=row[1],
        invite_url=f"{settings.public_base_url}/join#{code}",
    )


def _route_select() -> Select[Any]:
    return select(
        RouteRow,
        ST_AsGeoJSON(RouteRow.geom).label("geojson"),
        ST_Length(cast(RouteRow.geom, Geography)).label("length_m"),
    )


def _route_out(route: RouteRow, geojson: str, length_m: float) -> RouteOut:
    return RouteOut(
        id=route.id,
        team_id=route.team_id,
        name=route.name,
        corridor_m=route.corridor_m,
        length_m=float(length_m),
        geometry=LineString.model_validate(json.loads(geojson)),
    )


async def load_route(db: AsyncSession, route_id: uuid.UUID) -> RouteOut | None:
    row = (await db.execute(_route_select().where(RouteRow.id == route_id))).one_or_none()
    return None if row is None else _route_out(row[0], row[1], row[2])


@router.get("/teams/{team_id}/routes", response_model=list[RouteOut])
async def list_routes(team_id: uuid.UUID, user: UserDep, db: DbDep) -> list[RouteOut]:
    await require_role(db, user, team_id, Role.WALKER)
    rows = (
        await db.execute(_route_select().where(RouteRow.team_id == team_id).order_by(RouteRow.created_at))
    ).all()
    return [_route_out(r[0], r[1], r[2]) for r in rows]


@router.post("/teams/{team_id}/routes", response_model=RouteOut, status_code=status.HTTP_201_CREATED)
async def create_route(team_id: uuid.UUID, body: RouteCreate, user: UserDep, db: DbDep) -> RouteOut:
    await require_role(db, user, team_id, Role.ADMIN)
    route = RouteRow(
        team_id=team_id,
        name=body.name,
        corridor_m=body.corridor_m,
        geom=func.ST_SetSRID(ST_GeomFromGeoJSON(body.geometry.model_dump_json()), 4326),
    )
    db.add(route)
    await db.commit()
    out = await load_route(db, route.id)
    assert out is not None
    return out


async def survey_team(db: AsyncSession, survey_id: uuid.UUID) -> tuple[Survey, uuid.UUID] | None:
    row = (
        await db.execute(
            select(Survey, RouteRow.team_id)
            .join(RouteRow, RouteRow.id == Survey.route_id)
            .where(Survey.id == survey_id)
        )
    ).one_or_none()
    return None if row is None else (row[0], row[1])


async def pass_outs(db: AsyncSession, survey_id: uuid.UUID) -> list[PassOut]:
    counts = select(Photo.pass_id, func.count().label("n")).group_by(Photo.pass_id).subquery()
    rows = (
        await db.execute(
            select(PassRow, User.display_name, func.coalesce(counts.c.n, 0))
            .join(User, User.id == PassRow.observer_id)
            .outerjoin(counts, counts.c.pass_id == PassRow.id)
            .where(PassRow.survey_id == survey_id)
            .order_by(PassRow.pass_no)
        )
    ).all()
    return [pass_out(p, name, int(n)) for p, name, n in rows]


def pass_out(p: PassRow, observer_name: str, photo_count: int) -> PassOut:
    return PassOut(
        id=p.id,
        survey_id=p.survey_id,
        pass_no=p.pass_no,
        observer_id=p.observer_id,
        observer_name=observer_name,
        started_at=p.started_at,
        ended_at=p.ended_at,
        locked=p.locked,
        flags=list(p.flags),
        photo_count=photo_count,
    )


async def survey_out(db: AsyncSession, survey: Survey, team_id: uuid.UUID) -> SurveyOut:
    route = await load_route(db, survey.route_id)
    assert route is not None
    return SurveyOut(
        id=survey.id,
        team_id=team_id,
        name=survey.name,
        status=survey.status,
        start_window_local=survey.start_window_local,
        timezone=survey.timezone,
        route=route,
        passes=await pass_outs(db, survey.id),
    )


@router.get("/teams/{team_id}/surveys", response_model=list[SurveyOut])
async def list_surveys(team_id: uuid.UUID, user: UserDep, db: DbDep) -> list[SurveyOut]:
    await require_role(db, user, team_id, Role.WALKER)
    surveys = (
        (
            await db.execute(
                select(Survey)
                .join(RouteRow, RouteRow.id == Survey.route_id)
                .where(RouteRow.team_id == team_id)
                .order_by(Survey.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [await survey_out(db, s, team_id) for s in surveys]


@router.post("/teams/{team_id}/surveys", response_model=SurveyOut, status_code=status.HTTP_201_CREATED)
async def create_survey(team_id: uuid.UUID, body: SurveyCreate, user: UserDep, db: DbDep) -> SurveyOut:
    await require_role(db, user, team_id, Role.ADMIN)
    route = (
        await db.execute(select(RouteRow).where(RouteRow.id == body.route_id, RouteRow.team_id == team_id))
    ).scalar_one_or_none()
    if route is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That route is not in this team.")
    survey = Survey(route_id=route.id, name=body.name, start_window_local=body.start_window_local)
    db.add(survey)
    await db.commit()
    return await survey_out(db, survey, team_id)


@router.get("/surveys/{survey_id}", response_model=SurveyOut)
async def get_survey(survey_id: uuid.UUID, user: UserDep, db: DbDep) -> SurveyOut:
    found = await survey_team(db, survey_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    survey, team_id = found
    await require_role(db, user, team_id, Role.WALKER)
    return await survey_out(db, survey, team_id)

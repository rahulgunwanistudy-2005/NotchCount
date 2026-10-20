"""Request dependencies: settings, database session, current user and team-role checks."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from notchcount_api.auth import sessions
from notchcount_api.config import Settings, get_settings
from notchcount_api.db.models import Role, TeamMember, User
from notchcount_api.db.session import get_db

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[AsyncSession, Depends(get_db)]

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER = "x-notchcount"


async def csrf_guard(request: Request, x_notchcount: Annotated[str | None, Header()] = None) -> None:
    """Cookie sessions need a CSRF check: browsers will not add a custom header cross-site."""
    if request.method in UNSAFE_METHODS and x_notchcount != "1":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing X-NotchCount header.")


async def current_user(
    settings: SettingsDep,
    db: DbDep,
    nc_session: Annotated[str | None, Cookie(alias=sessions.COOKIE_NAME)] = None,
) -> User:
    user_id = sessions.read(settings, nc_session) if nc_session else None
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    return user


UserDep = Annotated[User, Depends(current_user)]

ROLE_RANK = {Role.WALKER: 0, Role.REVIEWER: 1, Role.ADMIN: 2}


async def require_role(db: AsyncSession, user: User, team_id: uuid.UUID, at_least: Role) -> Role:
    """The caller's role in the team, or 404 if they are not a member (no existence leak)."""
    role = (
        await db.execute(
            select(TeamMember.role).where(TeamMember.team_id == team_id, TeamMember.user_id == user.id)
        )
    ).scalar_one_or_none()
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    if ROLE_RANK[role] < ROLE_RANK[at_least]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Only a team {at_least.value} can do this.")
    return role

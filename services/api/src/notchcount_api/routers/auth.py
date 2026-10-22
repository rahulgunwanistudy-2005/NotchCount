from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from notchcount_api import ratelimit
from notchcount_api.auth import sessions
from notchcount_api.auth.invites import redeem_invite
from notchcount_api.auth.mojoauth import MojoAuthEmail
from notchcount_api.auth.provider import AuthError
from notchcount_api.config import Settings
from notchcount_api.db.models import User
from notchcount_api.deps import DbDep, SettingsDep
from notchcount_api.schemas import InviteRedeem

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _set_session(response: Response, settings: Settings, user_id: uuid.UUID) -> None:
    response.set_cookie(
        sessions.COOKIE_NAME,
        sessions.issue(settings, user_id),
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


async def _limit(request: Request, db: DbDep, settings: Settings, kind: str, per_10min: int) -> None:
    await ratelimit.hit(
        db,
        f"{kind}:{_client_ip(request)}",
        per_10min,
        timedelta(minutes=10),
        "Too many sign-in attempts. Wait 10 minutes and try again.",
    )
    await db.commit()


def _email_provider(settings: Settings) -> MojoAuthEmail:
    if settings.mojoauth_api_key is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Email sign-in is not set up. Use your team link."
        )
    return MojoAuthEmail(
        settings.mojoauth_api_key.get_secret_value(),
        settings.mojoauth_base_url,
        settings.session_secret.get_secret_value(),
    )


class AuthMethods(BaseModel):
    invite_link: bool = True
    email_code: bool


class EmailStart(BaseModel):
    email: EmailStr


class EmailStarted(BaseModel):
    state_id: str


class EmailVerify(BaseModel):
    state_id: str = Field(min_length=4, max_length=200)
    code: str = Field(min_length=4, max_length=12)


@router.get("/methods", response_model=AuthMethods)
async def methods(settings: SettingsDep) -> AuthMethods:
    return AuthMethods(email_code=settings.mojoauth_api_key is not None)


@router.post("/email/start", response_model=EmailStarted)
async def email_start(body: EmailStart, request: Request, db: DbDep, settings: SettingsDep) -> EmailStarted:
    """Send a one-time code by email (MojoAuth). It is sent whether or not the address is on a
    team, so the answer never tells anyone who is registered."""
    provider = _email_provider(settings)
    await _limit(request, db, settings, "otp-start", settings.auth_rate_per_10min)
    try:
        started = await provider.start(str(body.email))
    except AuthError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return EmailStarted(state_id=started.state_id or "")


@router.post("/email/verify", status_code=status.HTTP_204_NO_CONTENT)
async def email_verify(
    body: EmailVerify, request: Request, response: Response, db: DbDep, settings: SettingsDep
) -> None:
    """Check the code. A known address signs its person in. An unknown address is linked to
    whoever is already signed in on this browser (adding email sign-in to an invited walker);
    otherwise it is refused: only a team admin adds people."""
    provider = _email_provider(settings)
    await _limit(request, db, settings, "otp-verify", settings.auth_rate_per_10min * 4)
    try:
        identity = await provider.verify(body.state_id, body.code)
    except AuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    user = (await db.execute(select(User).where(User.phone_hash == identity.phone_hash))).scalars().first()
    if user is None:
        token = request.cookies.get(sessions.COOKIE_NAME)
        current_id = sessions.read(settings, token) if token else None
        user = await db.get(User, current_id) if current_id else None
        if user is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "This email is not on a team yet. Ask your team admin to add it, or sign in with your team link first.",
            )
        user.phone_hash = identity.phone_hash
        await db.commit()
    _set_session(response, settings, user.id)


@router.post("/invite", status_code=status.HTTP_204_NO_CONTENT)
async def redeem(
    body: InviteRedeem, request: Request, response: Response, db: DbDep, settings: SettingsDep
) -> None:
    await ratelimit.hit(
        db,
        f"auth:{_client_ip(request)}",
        settings.auth_rate_per_10min * 4,
        timedelta(minutes=10),
        "Too many sign-in attempts. Wait 10 minutes and try again.",
    )
    await db.commit()
    try:
        user = await redeem_invite(db, body.code)
    except AuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await db.commit()
    _set_session(response, settings, user.id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(sessions.COOKIE_NAME, path="/")

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status

from notchcount_api import ratelimit
from notchcount_api.auth import sessions
from notchcount_api.auth.invites import redeem_invite
from notchcount_api.auth.provider import AuthError
from notchcount_api.deps import DbDep, SettingsDep
from notchcount_api.schemas import InviteRedeem

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


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
    response.set_cookie(
        sessions.COOKIE_NAME,
        sessions.issue(settings, user.id),
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(sessions.COOKIE_NAME, path="/")

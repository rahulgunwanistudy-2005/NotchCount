"""Our own short-lived session JWTs, carried in an httpOnly cookie."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from notchcount_api.config import Settings

COOKIE_NAME = "nc_session"
ALGORITHM = "HS256"
ISSUER = "notchcount"


def issue(settings: Settings, user_id: uuid.UUID, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "iss": ISSUER,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.session_days)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, settings.session_secret.get_secret_value(), algorithm=ALGORITHM)


def read(settings: Settings, token: str) -> uuid.UUID | None:
    try:
        claims = jwt.decode(
            token,
            settings.session_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={"require": ["sub", "exp", "iss"]},
        )
        return uuid.UUID(str(claims["sub"]))
    except (jwt.PyJWTError, ValueError):
        return None

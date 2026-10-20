"""Interim sign-in: an admin issues each walker a one-time link. Used until MojoAuth keys arrive.

Codes are random 128-bit tokens; only their SHA-256 is stored.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from notchcount_api.auth.provider import AuthError
from notchcount_api.db.models import Invite, User

INVITE_DAYS = 7


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


async def create_invite(db: AsyncSession, user_id: uuid.UUID, days: int = INVITE_DAYS) -> str:
    code = secrets.token_urlsafe(16)
    db.add(
        Invite(
            code_hash=_hash(code),
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(days=days),
        )
    )
    await db.flush()
    return code


async def redeem_invite(db: AsyncSession, code: str) -> User:
    """Atomically mark the invite used and return its user."""
    now = datetime.now(UTC)
    result = await db.execute(
        update(Invite)
        .where(Invite.code_hash == _hash(code), Invite.used_at.is_(None), Invite.expires_at > now)
        .values(used_at=now)
        .returning(Invite.user_id)
    )
    user_id = result.scalar_one_or_none()
    if user_id is None:
        raise AuthError(
            "This sign-in link has expired or was already used. Ask your team admin for a new one."
        )
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    return user

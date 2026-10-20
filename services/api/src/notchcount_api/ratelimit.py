"""Sliding-window rate limits stored in Postgres, so they hold across API instances."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from notchcount_api.db.models import RateEvent


async def hit(db: AsyncSession, bucket: str, limit: int, window: timedelta, message: str) -> None:
    now = datetime.now(UTC)
    await db.execute(delete(RateEvent).where(RateEvent.bucket == bucket, RateEvent.at < now - window))
    count = (
        await db.execute(select(func.count()).select_from(RateEvent).where(RateEvent.bucket == bucket))
    ).scalar_one()
    if count >= limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, message)
    db.add(RateEvent(bucket=bucket, at=now))
    await db.flush()

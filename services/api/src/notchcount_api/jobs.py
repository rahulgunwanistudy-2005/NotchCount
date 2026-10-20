"""Postgres job queue: enqueue with a dedupe key, claim with FOR UPDATE SKIP LOCKED."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from notchcount_api.db.models import Job, JobStatus

STALE_LOCK = timedelta(minutes=10)


async def enqueue(
    db: AsyncSession, kind: str, payload: dict[str, Any], dedupe_key: str | None = None
) -> None:
    stmt = insert(Job).values(kind=kind, payload=payload, dedupe_key=dedupe_key)
    if dedupe_key is not None:
        stmt = stmt.on_conflict_do_nothing(index_elements=[Job.dedupe_key])
    await db.execute(stmt)


async def claim(db: AsyncSession, worker_id: str, kinds: list[str]) -> Job | None:
    """Lock and return one ready job; jobs whose worker died are reclaimed after STALE_LOCK."""
    now = datetime.now(UTC)
    ready = or_(
        and_(Job.status == JobStatus.QUEUED, Job.run_after <= now),
        and_(Job.status == JobStatus.RUNNING, Job.locked_at < now - STALE_LOCK),
    )
    job = (
        await db.execute(
            select(Job)
            .where(ready, Job.kind.in_(kinds))
            .order_by(Job.run_after, Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
    ).scalar_one_or_none()
    if job is None:
        return None
    job.status = JobStatus.RUNNING
    job.locked_by = worker_id
    job.locked_at = now
    job.attempts += 1
    await db.flush()
    return job


def backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(600, 5 * 2 ** max(0, attempts - 1)))


async def finish(db: AsyncSession, job_id: int) -> None:
    await db.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status=JobStatus.DONE, finished_at=datetime.now(UTC), last_error=None)
    )


async def fail(db: AsyncSession, job: Job, error: str) -> None:
    """Retry with exponential backoff, or dead-letter once attempts run out."""
    dead = job.attempts >= job.max_attempts
    await db.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(
            status=JobStatus.DEAD if dead else JobStatus.QUEUED,
            last_error=error[:4000],
            run_after=datetime.now(UTC) + backoff(job.attempts),
            locked_by=None,
            locked_at=None,
            finished_at=datetime.now(UTC) if dead else None,
        )
    )

"""Job runner: claims jobs from Postgres and dispatches them to registered handlers.

Run several copies safely; FOR UPDATE SKIP LOCKED keeps them from taking the same job.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from notchcount_api import jobs
from notchcount_api.db.session import get_sessionmaker

log = logging.getLogger("notchcount.worker")

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]
IDLE_SECONDS = 2.0


class PermanentJobError(Exception):
    """The job can never succeed (bad input); dead-letter it immediately."""


def registry() -> dict[str, Handler]:
    from notchcount_worker.handlers import available_handlers

    return available_handlers()


async def run_once(worker_id: str, handlers: dict[str, Handler]) -> bool:
    """Process at most one job. Returns False when the queue had nothing ready."""
    sm = get_sessionmaker()
    async with sm() as db:
        job = await jobs.claim(db, worker_id, list(handlers))
        if job is None:
            await db.rollback()
            return False
        await db.commit()
        job_id, kind, payload = job.id, job.kind, dict(job.payload)
    log.info("job start", extra={"job_id": job_id, "kind": kind, "attempt": job.attempts})
    async with sm() as db:
        try:
            await handlers[kind](db, payload)
            await jobs.finish(db, job_id)
            await db.commit()
            log.info("job done", extra={"job_id": job_id, "kind": kind})
        except Exception as exc:
            await db.rollback()
            if isinstance(exc, PermanentJobError):
                job.attempts = job.max_attempts
            await jobs.fail(db, job, f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=5)}")
            await db.commit()
            log.exception("job failed", extra={"job_id": job_id, "kind": kind})
    return True


async def run_forever(stop: asyncio.Event | None) -> None:
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    handlers = registry()
    log.info("worker ready", extra={"worker_id": worker_id, "kinds": sorted(handlers)})
    while stop is None or not stop.is_set():
        try:
            busy = await run_once(worker_id, handlers)
        except Exception:
            log.exception("worker loop error")
            busy = False
        if not busy:
            await asyncio.sleep(IDLE_SECONDS)


def main() -> None:
    from notchcount_api.logs import configure

    configure()
    stop = asyncio.Event()

    async def _run() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        await run_forever(stop)

    asyncio.run(_run())


if __name__ == "__main__":
    main()

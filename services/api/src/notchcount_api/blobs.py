"""Private image storage and short-lived signed URLs.

Buckets: `quarantine` (unblurred originals, never served), `blurred`, `crops`. The Postgres
store keeps bytes in the `blobs` table; a Supabase Storage store can replace it behind the same
interface once a service key is available.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from enum import StrEnum
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from notchcount_api.db.models import Blob


class Bucket(StrEnum):
    QUARANTINE = "quarantine"
    BLURRED = "blurred"
    CROPS = "crops"


SERVABLE = {Bucket.BLURRED, Bucket.CROPS}


class BlobStore(Protocol):
    async def put(self, bucket: Bucket, key: str, data: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> tuple[Bucket, str, bytes] | None: ...
    async def delete(self, key: str) -> None: ...


class PostgresBlobStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def put(self, bucket: Bucket, key: str, data: bytes, content_type: str) -> None:
        stmt = insert(Blob).values(
            key=key, bucket=bucket.value, content_type=content_type, data=data, size=len(data)
        )
        await self._db.execute(stmt.on_conflict_do_nothing(index_elements=[Blob.key]))

    async def get(self, key: str) -> tuple[Bucket, str, bytes] | None:
        row = (
            await self._db.execute(select(Blob.bucket, Blob.content_type, Blob.data).where(Blob.key == key))
        ).one_or_none()
        if row is None:
            return None
        return Bucket(row.bucket), row.content_type, row.data

    async def delete(self, key: str) -> None:
        await self._db.execute(delete(Blob).where(Blob.key == key))


def sign(secret: str, key: str, ttl_seconds: int, now: float | None = None) -> str:
    """Relative URL for a servable blob, valid for ttl_seconds."""
    exp = int((now or time.time()) + ttl_seconds)
    mac = hmac.new(secret.encode(), f"{key}:{exp}".encode(), hashlib.sha256).hexdigest()
    return f"/api/v1/blobs/{key}?exp={exp}&sig={mac}"


def verify(secret: str, key: str, exp: int, sig: str, now: float | None = None) -> bool:
    if exp < (now or time.time()):
        return False
    mac = hmac.new(secret.encode(), f"{key}:{exp}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, sig)

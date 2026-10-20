"""Identity providers sit behind one interface so MojoAuth can replace the interim invite codes
without touching routes. Providers only prove who someone is; sessions are our own."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AuthError(Exception):
    """The proof was wrong, expired or already used. Message is safe to show the user."""


@dataclass(frozen=True, slots=True)
class StartResult:
    state_id: str | None
    channel: str


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    subject: str
    channel: str
    phone_hash: str | None = None


class AuthProvider(Protocol):
    name: str

    async def start(self, identifier: str) -> StartResult: ...

    async def verify(self, state_id: str | None, code: str) -> VerifiedIdentity: ...

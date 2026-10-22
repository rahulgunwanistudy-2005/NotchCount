"""MojoAuth email one-time codes (https://mojoauth.com/docs/api-reference/, checked 2026-10-23).

`POST /users/emailotp` sends a code and returns a `state_id`; `POST /users/emailotp/verify` takes
the code and the `state_id` as a form and says whether the person is authenticated, with their
email as `user.identifier`. Both need the `x-api-key` header. We never store the address: a
person is known by a keyed hash of it, kept in `users.phone_hash` (DECISIONS D-28).
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx

from notchcount_api.auth.provider import AuthError, StartResult, VerifiedIdentity

TIMEOUT_S = 15.0


def contact_hash(secret: str, email: str) -> str:
    """Keyed hash of a normalised email address, so a leaked table does not list addresses."""
    normal = email.strip().lower()
    return hmac.new(secret.encode(), f"email:{normal}".encode(), hashlib.sha256).hexdigest()


class MojoAuthEmail:
    name = "mojoauth-email"

    def __init__(
        self, api_key: str, base_url: str, hash_secret: str, client: httpx.AsyncClient | None = None
    ):
        self._key = api_key
        self._base = base_url.rstrip("/")
        self._secret = hash_secret
        self._client = client

    async def _post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = {"x-api-key": self._key, "Accept": "application/json"}
        client = self._client or httpx.AsyncClient(timeout=TIMEOUT_S)
        try:
            res = await client.post(f"{self._base}{path}", headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise AuthError("Could not reach the sign-in service. Try again in a minute.") from exc
        finally:
            if self._client is None:
                await client.aclose()
        if res.status_code in (400, 401, 403, 404, 422):
            raise AuthError("That code is wrong or has expired. Ask for a new one.")
        if res.status_code == 429:
            raise AuthError("Too many codes asked for. Wait a few minutes and try again.")
        if res.status_code >= 400:
            raise AuthError("The sign-in service had a problem. Try again in a minute.")
        data: dict[str, Any] = res.json()
        return data

    async def start(self, identifier: str) -> StartResult:
        data = await self._post("/users/emailotp", json={"email": identifier.strip()})
        state = data.get("state_id")
        if not isinstance(state, str) or not state:
            raise AuthError("The sign-in service did not send a code. Try again in a minute.")
        return StartResult(state_id=state, channel="email")

    async def verify(self, state_id: str | None, code: str) -> VerifiedIdentity:
        if not state_id:
            raise AuthError("Ask for a code first.")
        data = await self._post("/users/emailotp/verify", data={"OTP": code.strip(), "state_id": state_id})
        user = data.get("user") or {}
        email = user.get("identifier") if isinstance(user, dict) else None
        if not data.get("authenticated") or not isinstance(email, str) or "@" not in email:
            raise AuthError("That code is wrong or has expired. Ask for a new one.")
        digest = contact_hash(self._secret, email)
        return VerifiedIdentity(subject=f"email:{digest}", channel="email", phone_hash=digest)

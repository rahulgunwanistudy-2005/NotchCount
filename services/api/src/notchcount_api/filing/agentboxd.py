"""Agentboxd client for case filing (verified against agentboxd.com/docs, see DECISIONS).

Two keys: the draft key (drafts:read, drafts:write) creates inboxes and drafts; only the approve
route uses the send key (adds messages:send), and only after a signed-in team admin presses
Approve. Sends pin `expected_content_sha256` so what goes out is exactly what was reviewed.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any

import httpx


class FilingError(Exception):
    """Agentboxd refused or failed; message is safe to show an admin."""


class FilingNotConfigured(FilingError):
    pass


@dataclass(frozen=True, slots=True)
class Attachment:
    filename: str
    content_type: str
    content_base64: str


class AgentboxdClient:
    def __init__(
        self,
        base_url: str,
        key: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 20.0,
    ) -> None:
        if not key:
            raise FilingNotConfigured("Filing is not set up: the Agentboxd API key is missing.")
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )

    async def __aenter__(self) -> AgentboxdClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    async def _call(
        self, method: str, path: str, idempotency_key: str | None = None, **kw: Any
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        try:
            r = await self._client.request(method, path, headers=headers, **kw)
        except httpx.HTTPError as exc:
            raise FilingError(f"Could not reach Agentboxd: {type(exc).__name__}") from exc
        if r.status_code >= 400:
            try:
                err = r.json().get("error", {})
                detail = f"{err.get('code', r.status_code)}: {err.get('message', '')}".strip(": ")
            except ValueError:
                detail = str(r.status_code)
            raise FilingError(f"Agentboxd refused the request ({detail}).")
        data: dict[str, Any] = r.json() if r.content else {}
        return data

    async def ensure_inbox(self, client_id: str, display_name: str) -> dict[str, Any]:
        """Idempotent on client_id: a repeat returns the existing inbox."""
        out = await self._call(
            "POST", "/inboxes", json={"client_id": client_id, "display_name": display_name[:80]}
        )
        inbox: dict[str, Any] = out.get("inbox", out)
        return inbox

    async def create_draft(
        self,
        inbox_id: str,
        *,
        to: list[str],
        subject: str,
        text: str,
        html: str | None,
        attachments: list[Attachment],
        idempotency_key: str,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"to": to, "subject": subject, "text": text}
        if html:
            body["html"] = html
        if attachments:
            body["attachments"] = [_att(a) for a in attachments]
        out = await self._call(
            "POST", f"/inboxes/{inbox_id}/drafts", idempotency_key=idempotency_key, json=body
        )
        draft: dict[str, Any] = out.get("draft", out)
        return draft

    async def send_draft(self, inbox_id: str, draft_id: str, content_sha256: str | None) -> dict[str, Any]:
        body = {"expected_content_sha256": content_sha256} if content_sha256 else {}
        return await self._call(
            "POST",
            f"/inboxes/{inbox_id}/drafts/{draft_id}/send",
            idempotency_key=f"send-{draft_id}",
            json=body,
        )


def _att(a: Attachment) -> dict[str, str]:
    return {"filename": a.filename, "content_type": a.content_type, "content_base64": a.content_base64}


MAX_SKEW_SECONDS = 300


def verify_webhook(
    secret: str, timestamp: str | None, signature: str | None, raw: bytes, now: float | None = None
) -> bool:
    """hex(HMAC-SHA256(secret, "<timestamp>.<raw body>")), timestamp within 300 s."""
    if not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs((now or time.time()) - ts) > MAX_SKEW_SECONDS:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


# Labels that mean a person must look before the reply is shown as normal. Agentboxd's docs say
# injection-risk and SPF/DMARC failures are labelled but do not list the names, so any label that
# mentions these words holds the message, and unknown risk labels are treated the same way.
HOLD_WORDS = ("inject", "dmarc", "spf", "dkim", "spoof", "phish", "risk", "suspicious", "held", "quarantine")


def should_hold(labels: list[str]) -> bool:
    return any(w in label.lower() for label in labels for w in HOLD_WORDS)

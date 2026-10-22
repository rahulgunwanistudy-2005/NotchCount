"""MojoAuth email codes, against a fake of the documented API (no network, synthetic addresses)."""

from __future__ import annotations

from urllib.parse import parse_qs

import httpx
import pytest

from notchcount_api.auth.mojoauth import MojoAuthEmail, contact_hash
from notchcount_api.auth.provider import AuthError

KEY = "test-key"


def fake(code_ok: str = "123456") -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == KEY
        if request.url.path == "/users/emailotp":
            return httpx.Response(200, json={"state_id": "st-1"})
        if request.url.path == "/users/emailotp/verify":
            # The spec sends the verify call as a form, with the field named OTP.
            form = parse_qs(request.content.decode())
            ok = form.get("OTP") == [code_ok] and form.get("state_id") == ["st-1"]
            if not ok:
                return httpx.Response(400, json={"code": 400, "description": "Invalid OTP"})
            return httpx.Response(
                200,
                json={"authenticated": True, "user": {"identifier": "Walker@Example.org", "user_id": "u1"}},
            )
        return httpx.Response(404)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.mojoauth.com")


async def test_start_then_verify_gives_a_hashed_identity() -> None:
    p = MojoAuthEmail(KEY, "https://api.mojoauth.com", "secret", client=fake())
    started = await p.start("walker@example.org")
    assert started.state_id == "st-1"
    who = await p.verify(started.state_id, "123456")
    assert who.phone_hash == contact_hash("secret", "walker@example.org")
    assert "example" not in who.subject  # the address itself is never kept


async def test_wrong_code_is_refused_in_plain_words() -> None:
    p = MojoAuthEmail(KEY, "https://api.mojoauth.com", "secret", client=fake())
    with pytest.raises(AuthError, match="wrong or has expired"):
        await p.verify("st-1", "000000")


def test_hash_ignores_case_and_spaces_but_depends_on_the_secret() -> None:
    assert contact_hash("s", " A@B.org ") == contact_hash("s", "a@b.org")
    assert contact_hash("s", "a@b.org") != contact_hash("t", "a@b.org")

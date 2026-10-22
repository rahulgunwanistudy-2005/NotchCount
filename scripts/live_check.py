"""Check a running NotchCount deployment from the outside.

    uv run python scripts/live_check.py https://your-host
    uv run python scripts/live_check.py https://your-host --code ONE_USE_SIGN_IN_CODE

Without a code it checks what anyone can reach: the page, the API, the sample report and its PDF,
and which sign-in methods are on. With a one-use sign-in code from a team admin it also reads the
admin health page, which checks the MojoAuth and Agentboxd keys set on that server. Prints one
line per check and exits non-zero if any check failed. Sends no email and changes nothing except
using up the code.
"""

from __future__ import annotations

import argparse
import sys

import httpx

SAMPLE_REPORT = "bJriBIPv6Xv0"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--code", default=None)
    args = ap.parse_args()
    base = args.base.rstrip("/")
    failed = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failed
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name}{': ' + detail if detail else ''}")

    with httpx.Client(base_url=base, timeout=90, headers={"x-notchcount": "1"}, follow_redirects=True) as c:
        r = c.get("/healthz")
        check("server answers /healthz", r.status_code == 200, r.text[:60])
        r = c.get("/")
        check("web app is served", r.status_code == 200 and "<html" in r.text.lower())
        r = c.get("/api/v1/auth/methods")
        methods = r.json() if r.status_code == 200 else {}
        check(
            "sign-in methods",
            r.status_code == 200,
            f"invite links {methods.get('invite_link')}, email codes {methods.get('email_code')}",
        )
        r = c.get(f"/api/v1/reports/{SAMPLE_REPORT}")
        check(
            "sample report",
            r.status_code == 200,
            (r.json().get("headline") or {}).get("population", "")
            if r.status_code == 200
            else str(r.status_code),
        )
        r = c.get(f"/api/v1/reports/{SAMPLE_REPORT}.pdf")
        check("report PDF", r.status_code == 200 and r.content.startswith(b"%PDF"))
        if args.code:
            r = c.post("/api/v1/auth/invite", json={"code": args.code})
            check("sign in with the code", r.status_code == 204, "" if r.status_code == 204 else r.text[:120])
            if r.status_code == 204:
                r = c.get("/api/v1/admin/health")
                check("admin health", r.status_code == 200)
                if r.status_code == 200:
                    h = r.json()
                    print(f"     public address set on the server: {h.get('public_base_url')}")
                    for i in h.get("integrations", []):
                        check(i["name"], i["status"] == "ok", f"{i['status']}: {i['detail']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

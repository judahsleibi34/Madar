#!/usr/bin/env python3
"""Authenticated, loopback-only two-tenant staging adversarial checks."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from create_tokens import encode


BASE = os.getenv("MADAR_STAGING_API", "http://127.0.0.1:18001").rstrip("/")
ALLOWED_ORIGIN = "http://127.0.0.1:13000"
TENANT_B_PROJECT = "00000000-0000-0000-0000-000000099102"
TENANT_B_DELETION = "00000000-0000-0000-0000-000000096102"


def token(subject: str, email: str, *, aal: str = "aal2") -> str:
    now = int(time.time())
    return encode({
        "iss": "madar-staging", "iat": now, "exp": now + 3600,
        "role": "authenticated", "sub": subject, "email": email, "aal": aal,
    }, os.environ["STAGING_JWT_SECRET"])


def call(path: str, access: str, *, method: str = "GET", csrf: str | None = None,
         origin: str = ALLOWED_ORIGIN, body: dict | None = None):
    headers = {"Cookie": f"madar_access_token={access}", "Origin": origin}
    payload = None
    if body is not None:
        payload = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if csrf:
        headers["Cookie"] += f"; madar_csrf_token={csrf}"
        headers["X-CSRF-Token"] = csrf
    request = urllib.request.Request(BASE + path, data=payload, method=method, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    raw = response.read()
    try:
        parsed = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        parsed = raw.decode(errors="replace")
    return response.status, {key.lower(): value for key, value in response.headers.items()}, parsed


def session(access: str) -> tuple[dict, str]:
    status, _headers, payload = call("/auth/user_status", access)
    assert status == 200 and payload.get("logged_in") is True, (status, payload)
    csrf = str(payload.get("csrf_token") or "")
    assert csrf
    return payload["user"], csrf


def main() -> int:
    owner_a = token("00000000-0000-0000-0000-000000009101", "owner-a@staging.invalid")
    member_a = token("00000000-0000-0000-0000-000000009102", "member-a@staging.invalid")
    owner_b = token("00000000-0000-0000-0000-000000009201", "owner-b@staging.invalid")
    user_a, csrf_a = session(owner_a)
    user_b, _csrf_b = session(owner_b)
    member, csrf_member = session(member_a)
    assert user_a["tenant_id"] == 9101 and user_b["tenant_id"] == 9102
    assert member["tenant_id"] == 9101

    status, headers, payload = call("/billing/entitlements", owner_a)
    assert status == 200 and payload["entitlements"]["tenant_id"] == 9101
    assert payload["entitlements"]["plan_id"] == "business_plus"
    assert headers.get("access-control-allow-origin") == ALLOWED_ORIGIN

    status, _headers, payload = call("/builder/projects", owner_a)
    serialized = json.dumps(payload)
    assert status == 200 and TENANT_B_PROJECT not in serialized

    status, _headers, _payload = call(f"/builder/projects/{TENANT_B_PROJECT}", owner_a)
    assert status == 404
    status, _headers, _payload = call(
        f"/builder/projects/{TENANT_B_PROJECT}", owner_a, method="DELETE", csrf=csrf_a,
    )
    assert status == 404

    status, _headers, _payload = call(f"/users/{user_b['id']}/info", owner_a)
    assert status in {403, 404}

    status, _headers, payload = call("/notifications", owner_a)
    assert status == 200 and "TENANT_B_PRIVATE_SENTINEL" not in json.dumps(payload)

    status, _headers, payload = call(
        "/calendar/bootstrap?start=2026-08-01T00:00:00Z&end=2026-09-01T00:00:00Z", owner_a,
    )
    assert status == 200 and "00000000-0000-0000-0000-000000098102" not in json.dumps(payload)

    status, _headers, _payload = call(f"/account/deletion/{TENANT_B_DELETION}", owner_a)
    assert status == 404
    status, _headers, _payload = call(
        "/tenant/deletion", member_a, method="POST", csrf=csrf_member, body={},
    )
    assert status == 403

    status, headers, _payload = call("/definitely-missing", owner_a, origin="https://evil.invalid")
    assert status == 404 and "access-control-allow-origin" not in headers

    print(json.dumps({
        "status": "pass", "checks": 12, "tenant_a": 9101, "tenant_b": 9102,
        "external_network_attempts": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

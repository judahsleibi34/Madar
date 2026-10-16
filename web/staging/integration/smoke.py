#!/usr/bin/env python3
"""Actual native-provider/API assertions with generated synthetic identities."""

import base64
import hashlib
import hmac
from http.cookies import SimpleCookie
import json
import re
import secrets
import struct
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from uuid import UUID

import manage


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


OPENER = build_opener(ProxyHandler({}), NoRedirect())
PROVIDER = "http://127.0.0.1:18081"
APPLICATION = "http://127.0.0.1:18080/api"


def http(method, path, *, token=None, body=None, headers=None, expected=(200,), application=False):
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    if token:
        request_headers["Authorization"] = "Bearer " + token
    request = Request((APPLICATION if application else PROVIDER) + path,
                      data=data, method=method, headers=request_headers)
    try:
        response = OPENER.open(request, timeout=15)
    except HTTPError as error:
        response = error
    with response:
        content = response.read()
        if response.status not in expected:
            raise RuntimeError(f"Unexpected HTTP status {response.status} for {method} {path.split('?')[0]}")
        parsed = json.loads(content) if "application/json" in response.headers.get("Content-Type", "") else content
        return parsed, response.headers


def cookies(headers):
    result = {}
    for value in headers.get_all("Set-Cookie", []):
        jar = SimpleCookie()
        jar.load(value)
        result.update({name: item.value for name, item in jar.items() if item.value})
    return result


def cookie_header(values):
    return {"Cookie": "; ".join(f"{key}={value}" for key, value in values.items())}


def totp(secret):
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", int(time.time()) // 30), hashlib.sha1).digest()
    offset = digest[-1] & 15
    number = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7fffffff
    return f"{number % 1000000:06d}"


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def main():
    manage.require_database_marker()
    values = dict(line.split("=", 1) for line in (manage.RUNTIME / "application.env").read_text().splitlines())
    service, anon = values["SUPABASE_SERVICE_KEY"], values["SUPABASE_ANON_KEY"]
    fixture = secrets.token_hex(8)
    email, password = f"hardening-{fixture}@example.com", secrets.token_urlsafe(24)
    created, _ = http("POST", "/auth/v1/admin/users", token=service,
                      body={"email": email, "password": password, "email_confirm": True})
    auth_id = str(UUID(created["id"]))
    actor = int(manage.sql(
        "insert into public.users(auth_id,first_name,last_name,email,user_type,account_kind,"
        "account_status,email_verified,email_verified_at) values("
        f"{literal(auth_id)},'Synthetic','Administrator',{literal(email)},'admin','platform','active',true,now()) returning id;"))
    session, _ = http("POST", "/auth/v1/token?grant_type=password", body={"email": email, "password": password})
    http("POST", "/auth/v1/token?grant_type=password", body={"email": email, "password": "incorrect-fixture"}, expected=(400,))
    http("GET", "/auth/v1/user", token="invalid-synthetic-jwt", expected=(401, 403))
    factor, _ = http("POST", "/auth/v1/factors", token=session["access_token"],
                     body={"factor_type": "totp", "friendly_name": "Isolated rehearsal"})
    factor_id, secret = str(UUID(factor["id"])), factor["totp"]["secret"]
    challenge, _ = http("POST", f"/auth/v1/factors/{factor_id}/challenge", token=session["access_token"], body={})
    elevated, _ = http("POST", f"/auth/v1/factors/{factor_id}/verify", token=session["access_token"],
                       body={"challenge_id": challenge["id"], "code": totp(secret)})
    session_cookies = {"madar_access_token": session["access_token"], "madar_refresh_token": session["refresh_token"]}
    http("GET", "/admin/users", application=True, headers=cookie_header(session_cookies), expected=(403,))
    elevated_cookies = {"madar_access_token": elevated["access_token"], "madar_refresh_token": elevated["refresh_token"]}
    http("GET", "/admin/users", application=True, headers=cookie_header(elevated_cookies))
    login, login_headers = http("POST", "/auth/login", application=True, body={"email": email, "password": password})
    assert login.get("mfa_required") is True
    pending = cookies(login_headers)
    assert "madar_mfa_pending" in pending and "madar_access_token" not in pending
    http("POST", "/auth/mfa/login/challenge", application=True, body={"factor_id": factor_id},
         headers={**cookie_header(pending), "Origin": "https://untrusted.example"}, expected=(403,))
    headers = {**cookie_header(pending), "Origin": "http://127.0.0.1:18080"}
    application_challenge, _ = http("POST", "/auth/mfa/login/challenge", application=True,
                                    body={"factor_id": factor_id}, headers=headers)
    # Native TOTP verification forbids replaying a code from the enrollment.
    step = int(time.time()) // 30
    while int(time.time()) // 30 == step:
        time.sleep(0.2)
    verification = {"factor_id": factor_id, "challenge_id": application_challenge["challenge_id"], "code": totp(secret)}
    completed, completed_headers = http("POST", "/auth/mfa/login/verify", application=True, body=verification, headers=headers)
    ordinary = cookies(completed_headers)
    assert "madar_access_token" in ordinary and "madar_refresh_token" in ordinary
    http("GET", "/admin/users", application=True, headers=cookie_header(ordinary))
    http("POST", "/auth/mfa/login/verify", application=True, body=verification, headers=headers, expected=(401, 403, 409))
    refreshed, _ = http("POST", "/auth/v1/token?grant_type=refresh_token", body={"refresh_token": elevated["refresh_token"]})
    assert refreshed["refresh_token"] != elevated["refresh_token"]
    print("PASS native password login/rejection, invalid JWT, TOTP, admin AAL1 rejection/AAL2 access, restricted login, CSRF rejection, single-use MFA admission, refresh rotation")

    bucket = "hardening-private-" + fixture
    http("POST", "/storage/v1/bucket", token=service, body={"id": bucket, "name": bucket, "public": False})
    contents = b"synthetic private storage fixture"
    http("POST", f"/storage/v1/object/{bucket}/fixture.txt", token=service, body=contents, headers={"Content-Type": "text/plain"})
    downloaded, _ = http("GET", f"/storage/v1/object/{bucket}/fixture.txt", token=service)
    assert downloaded == contents
    http("GET", f"/storage/v1/object/{bucket}/fixture.txt", token=anon, expected=(400, 403, 404))
    avatar = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=")
    avatar_path = f"{auth_id}/{fixture}.png"
    http("POST", f"/storage/v1/object/avatars/{avatar_path}", token=service, body=avatar, headers={"Content-Type": "image/png"})
    mediated, _ = http("GET", f"/assets/avatars/{avatar_path}", application=True)
    assert mediated == avatar
    print("PASS native private Storage upload/download, anonymous denial and mediated legacy avatar delivery")

    tenant = int(manage.sql("insert into public.tenants(brand_name,owner_name) values('Synthetic worker','Hardening') returning tenant_id;"))
    owner_email = f"worker-{fixture}@example.com"
    owner, _ = http("POST", "/auth/v1/admin/users", token=service,
                    body={"email": owner_email, "password": secrets.token_urlsafe(24), "email_confirm": True})
    owner_auth = str(UUID(owner["id"]))
    user_id = int(manage.sql(
        "insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified,email_verified_at) "
        f"values({literal(owner_auth)},'Synthetic','Owner',{literal(owner_email)},{tenant},'active',true,now()) returning id;"))
    manage.sql("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) "
               f"values({tenant},{user_id},{literal(owner_auth)},'owner','active');")
    intent = {"p_tenant_id": tenant, "p_event_type": "builder.form_submitted", "p_source_type": "form",
              "p_source_id": "synthetic-" + fixture, "p_title": "Synthetic submission", "p_body": "Isolated worker rehearsal",
              "p_data": {"block_type": "form"}, "p_deduplication_key": fixture}
    first, _ = http("POST", "/rest/v1/rpc/create_notification_event_intent", token=service, body=intent)
    replay, _ = http("POST", "/rest/v1/rpc/create_notification_event_intent", token=service, body=intent)
    assert first == replay
    event = first[0] if isinstance(first, list) else first
    event_id = str(UUID(event["id"]))
    deadline = time.monotonic() + 30
    count = "0"
    while time.monotonic() < deadline:
        count = manage.sql(f"select count(*) from public.user_notifications where event_id={literal(event_id)} and user_id={user_id};")
        if count == "1":
            break
        time.sleep(0.5)
    assert count == "1", "Native notification worker did not deliver exactly one internal fixture notification"
    http("GET", "/health/live", application=True)
    ready, _ = http("GET", "/health/ready", application=True)
    assert ready["ready"] is True
    assert ready["commercial_entitlements_enforced"] is True
    manage.private_write("smoke-fixture.json", json.dumps({"admin_email": email, "admin_password": password,
        "admin_auth_id": auth_id, "admin_user_id": actor, "mfa_secret": secret, "cookies": ordinary,
        "tenant_id": tenant, "worker_user_id": user_id, "event_id": event_id,
        "private_bucket": bucket, "avatar_path": avatar_path}, indent=2))
    print("PASS durable PostgREST notification intent/replay, actual worker delivery, frontend API proxy and readiness")


if __name__ == "__main__":
    main()

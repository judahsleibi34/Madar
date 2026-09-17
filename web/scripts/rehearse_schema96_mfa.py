#!/usr/bin/env python3
"""Run a secret-safe, real-middleware MFA/AAL2 rehearsal on isolated Supabase."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import shlex
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid


def load_environment(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        parsed = shlex.split(raw_value, comments=True)
        values[key] = parsed[0] if parsed else ""
    return values


def totp_code(seed: str, counter: int | None = None) -> str:
    interval = int(time.time()) // 30 if counter is None else counter
    key = base64.b32decode(seed + "=" * ((-len(seed)) % 8))
    digest = hmac.new(key, struct.pack(">Q", interval), hashlib.sha1).digest()
    offset = digest[-1] & 15
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 1_000_000).zfill(6)


class AuthApi:
    def __init__(self, base_url: str, publishable_key: str, secret_key: str):
        self.base_url = base_url.rstrip("/")
        self.publishable_key = publishable_key
        self.secret_key = secret_key

    def call(
        self,
        path: str,
        body: dict | None = None,
        *,
        token: str | None = None,
        admin: bool = False,
        method: str | None = None,
    ) -> dict:
        headers = {
            "apikey": self.secret_key if admin else self.publishable_key,
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            endpoint = path.split("?", 1)[0]
            raise RuntimeError(f"auth_http_{error.code}_{endpoint}") from None


def response_code(response) -> str | None:
    try:
        detail = response.json().get("detail")
        return detail.get("code") if isinstance(detail, dict) else None
    except (AttributeError, json.JSONDecodeError, TypeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--supabase-env-file", type=Path, required=True)
    parser.add_argument("--supabase-url", required=True)
    parser.add_argument("--source-root", type=Path, default=Path("/source"))
    parser.add_argument("--evidence-output", type=Path, required=True)
    args = parser.parse_args()

    report: dict[str, object] = {
        "status": "failed",
        "synthetic_only": True,
        "managed_project_accessed": False,
        "real_application_middleware": True,
        "real_auth_provider": True,
        "expected_schema": 96,
    }
    auth_id: str | None = None
    tenant_id: int | None = None
    api: AuthApi | None = None
    service_supabase = None
    phase = "configuration"

    try:
        config = load_environment(args.supabase_env_file)
        publishable_key = config["SUPABASE_PUBLISHABLE_KEY"]
        secret_key = config["SUPABASE_SECRET_KEY"]
        if not publishable_key or not secret_key:
            raise RuntimeError("isolated_auth_keys_missing")
        if args.supabase_url.rstrip("/") != "http://api-gw:8000":
            raise RuntimeError("isolated_auth_url_required")
        if "supabase.co" in args.supabase_url.lower():
            raise RuntimeError("managed_auth_url_forbidden")

        scratch = Path("/tmp/madar-schema96-mfa")
        scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.environ.update(
            APP_ENV="test",
            MADAR_ENV_OVERRIDE="false",
            MADAR_ENV_FILE="/tmp/madar-schema96-no-env-file",
            SUPABASE_URL=args.supabase_url.rstrip("/"),
            SUPABASE_ANON_KEY=publishable_key,
            SUPABASE_SERVICE_KEY=secret_key,
            FRONTEND_URLS="https://testserver",
            CSRF_TRUSTED_ORIGINS="https://testserver",
            ADMIN_MFA_LOGIN_ENFORCEMENT="true",
            RATE_LIMIT_ENABLED="false",
            EMAIL_CHANNEL_ENABLED="false",
            WEB_PUSH_ENABLED="false",
            COOKIE_SECURE="true",
            COOKIE_SAMESITE="lax",
            DATA_UPLOAD_DIR=str(scratch / "data"),
            AVATAR_UPLOAD_DIR=str(scratch / "avatars"),
            PUBLIC_UPLOADS_DIR=str(scratch / "public"),
            PRIVATE_CHARTS_DIR=str(scratch / "charts"),
        )
        sys.path.insert(0, str(args.source_root))

        from fastapi.testclient import TestClient
        from app import app
        from database import service_supabase
        from routes.public_site_routes import hash_public_identifier

        api = AuthApi(args.supabase_url, publishable_key, secret_key)
        phase = "schema_gate"
        schema_rows = (
            service_supabase.table("application_schema_state")
            .select("schema_version")
            .eq("contract_key", "core")
            .limit(1)
            .execute()
            .data
        )
        if len(schema_rows) != 1 or schema_rows[0].get("schema_version") != 96:
            raise RuntimeError("schema96_required")
        report["schema_96_verified"] = True

        phase = "synthetic_identity"
        suffix = uuid.uuid4().hex
        email = f"schema96-mfa-{suffix}@example.com"
        password = secrets.token_urlsafe(32)
        provider_user = api.call(
            "/auth/v1/admin/users",
            {"email": email, "password": password, "email_confirm": True},
            admin=True,
        )
        auth_id = str(provider_user["id"])
        tenant_id = secrets.randbelow(800_000_000) + 100_000_000
        tenant = (
            service_supabase.table("tenants")
            .insert(
                {
                    "tenant_id": tenant_id,
                    "brand_name": "Schema96 MFA Rehearsal",
                    "owner_name": "Disposable Operator",
                }
            )
            .execute()
            .data[0]
        )
        local_user = (
            service_supabase.table("users")
            .insert(
                {
                    "auth_id": auth_id,
                    "first_name": "Disposable",
                    "last_name": "Administrator",
                    "email": email,
                    "tenant_id": tenant["tenant_id"],
                    "user_type": "admin",
                    "account_status": "active",
                    "account_kind": "platform",
                    "email_verified": True,
                    "email_verified_at": "2026-09-15T00:00:00Z",
                }
            )
            .execute()
            .data[0]
        )
        user_id = int(local_user["id"])
        service_supabase.table("tenant_memberships").insert(
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "auth_id": auth_id,
                "role": "owner",
                "status": "active",
            }
        ).execute()
        service_supabase.table("user_security_settings").upsert(
            {
                "user_id": user_id,
                "auth_id": auth_id,
                "mfa_required": True,
                "mfa_required_at": "2026-09-15T00:00:00Z",
            },
            on_conflict="user_id",
        ).execute()
        report["disposable_user_only"] = True

        phase = "schema96_order_fixture"
        site_slug = f"schema96-{suffix[:16]}"
        service_supabase.table("website_settings").insert(
            {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "subdomain": site_slug,
                "standard_path_slug": site_slug,
                "brand": "Schema96 Disposable Store",
                "ecommerce_currency": "ILS",
            }
        ).execute()
        confirmation_token = secrets.token_hex(32)
        order = service_supabase.table("ecommerce_orders").insert(
            {
                "tenant_id": tenant_id,
                "order_number": f"SCHEMA96-{suffix[:12]}",
                "status": "pending",
                "payment_status": "unpaid",
                "payment_method": "cash_on_delivery",
                "currency": "ILS",
                "subtotal": 10,
                "discount_total": 0,
                "total": 10,
                "customer_name": "Synthetic Customer",
                "customer_email": "synthetic@example.com",
                "customer_phone": "000",
                "address_line_1": "Disposable fixture",
                "city": "Ramallah",
                "country": "PS",
                "confirmation_token_hash": hash_public_identifier(
                    f"ecommerce-confirmation-token:{confirmation_token}"
                ),
            }
        ).execute().data[0]
        service_supabase.table("ecommerce_order_items").insert(
            {
                "tenant_id": tenant_id,
                "order_id": order["id"],
                "sku": "SCHEMA96-FIXTURE",
                "product_name": "Synthetic item",
                "product_slug": "synthetic-item",
                "product_snapshot": {},
                "variant_snapshot": {},
                "selected_options_snapshot": {},
                "quantity": 1,
                "list_unit_price": 10,
                "discount_amount": 0,
                "unit_price": 10,
                "line_total": 10,
            }
        ).execute()
        service_supabase.table("ecommerce_order_status_history").insert(
            {
                "tenant_id": tenant_id,
                "order_id": order["id"],
                "new_status": "pending",
                "note": "Synthetic schema96 confirmation fixture",
                "idempotency_key_hash": hashlib.sha256(
                    f"schema96-status:{suffix}".encode("utf-8")
                ).hexdigest(),
            }
        ).execute()

        phase = "factor_enrollment"
        enrollment_session = api.call(
            "/auth/v1/token?grant_type=password",
            {"email": email, "password": password},
        )
        factor = api.call(
            "/auth/v1/factors",
            {"factor_type": "totp", "friendly_name": "Isolated schema96 rehearsal"},
            token=enrollment_session["access_token"],
        )
        seed = factor["totp"]["secret"]
        enrollment_counter = int(time.time()) // 30
        challenge = api.call(
            f"/auth/v1/factors/{factor['id']}/challenge",
            {},
            token=enrollment_session["access_token"],
        )
        api.call(
            f"/auth/v1/factors/{factor['id']}/verify",
            {
                "challenge_id": challenge["id"],
                "code": totp_code(seed, enrollment_counter),
            },
            token=enrollment_session["access_token"],
        )
        report["mfa_factor_enrolled_with_real_auth"] = True

        phase = "application_flow"
        with TestClient(app, base_url="https://testserver") as primary, TestClient(
            app, base_url="https://testserver"
        ) as secondary:
            confirmation = primary.get(
                f"/public/sites/{site_slug}/orders/confirmation/{confirmation_token}"
            )
            confirmation_token = ""
            confirmation_body = confirmation.json()
            if (
                confirmation.status_code != 200
                or confirmation_body.get("order", {}).get("id") != order["id"]
                or len(confirmation_body.get("items") or []) != 1
                or len(confirmation_body.get("status_history") or []) != 1
                or "loyalty_entitlement_id" in (confirmation_body.get("items") or [{}])[0]
            ):
                raise RuntimeError("schema96_order_confirmation_failed")
            report["schema96_existing_order_readable"] = True
            report["schema96_order_confirmation_path"] = "passed"
            report["schema96_post96_column_not_accessed"] = True

            unauthenticated = primary.get("/admin/data-deletions?limit=1")
            if unauthenticated.status_code != 401:
                raise RuntimeError("unauthenticated_privilege_not_denied")
            report["A_unauthenticated_privileged_denied"] = True

            login = primary.post(
                "/auth/login", json={"email": email, "password": password}
            )
            login_body = login.json()
            factors = login_body.get("factors") or []
            if login.status_code != 200 or not login_body.get("mfa_required") or not factors:
                raise RuntimeError("application_login_did_not_require_mfa")
            if "madar_access_token" in primary.cookies:
                raise RuntimeError("aal1_admin_received_normal_cookie")
            report["B_normal_login_succeeded"] = True
            report["C_enrolled_factor_challenge_required"] = True

            before_mfa = primary.get("/admin/data-deletions?limit=1")
            if before_mfa.status_code != 401:
                raise RuntimeError("pending_mfa_privilege_not_denied")
            report["D_before_mfa_privileged_denied"] = True

            secondary_session = api.call(
                "/auth/v1/token?grant_type=password",
                {"email": email, "password": password},
            )
            secondary.cookies.set(
                "madar_access_token", secondary_session["access_token"]
            )
            secondary.cookies.set(
                "madar_refresh_token", secondary_session["refresh_token"]
            )
            secondary_denied_before = secondary.get("/admin/data-deletions?limit=1")
            if secondary_denied_before.status_code != 403:
                raise RuntimeError("aal1_session_privilege_not_denied")

            challenge_response = primary.post(
                "/auth/mfa/login/challenge", json={"factor_id": factors[0]["id"]}
            )
            if challenge_response.status_code != 200:
                raise RuntimeError("application_mfa_challenge_failed")
            while int(time.time()) // 30 == enrollment_counter:
                time.sleep(0.2)
            verify = primary.post(
                "/auth/mfa/login/verify",
                json={
                    "factor_id": factors[0]["id"],
                    "challenge_id": challenge_response.json()["challenge_id"],
                    "code": totp_code(seed),
                },
            )
            seed = ""
            if verify.status_code != 200 or "madar_access_token" not in primary.cookies:
                raise RuntimeError("application_mfa_verify_failed")
            if verify.json().get("user", {}).get("tenant_id") != tenant_id:
                raise RuntimeError("tenant_context_changed_at_mfa")
            status = primary.get("/auth/mfa/status")
            if status.status_code != 200 or status.json().get("aal", {}).get(
                "current_level"
            ) != "aal2":
                raise RuntimeError("application_aal2_not_observed")
            report["E_valid_mfa_raised_aal2"] = True

            privileged = primary.get("/admin/data-deletions?limit=1")
            if privileged.status_code != 200:
                raise RuntimeError("aal2_privileged_endpoint_denied")
            report["F_after_aal2_privileged_succeeded"] = True

            secondary_denied_after = secondary.get("/admin/data-deletions?limit=1")
            if secondary_denied_after.status_code not in {401, 403}:
                raise RuntimeError("aal2_assurance_leaked_between_sessions")
            report["G_other_session_remained_aal1"] = True
            report["G_other_session_denial_status"] = secondary_denied_after.status_code

            stale_access = primary.cookies.get("madar_access_token")
            stale_refresh = primary.cookies.get("madar_refresh_token")
            logout = primary.post(
                "/auth/log_out", headers={"Origin": "https://testserver"}
            )
            report["logout_status"] = logout.status_code
            set_cookie_headers = logout.headers.get_list("set-cookie")
            deleted_cookie_names = {
                header.split("=", 1)[0]
                for header in set_cookie_headers
                if "max-age=0" in header.lower()
            }
            logout_clears_auth_cookies = {
                "madar_access_token",
                "madar_refresh_token",
                "madar_csrf_token",
            }.issubset(deleted_cookie_names)
            report["logout_cookie_delete_headers"] = logout_clears_auth_cookies
            logout_code = response_code(logout)
            if logout_code:
                report["logout_error_code"] = logout_code
            if logout.status_code != 200 or not logout_clears_auth_cookies:
                raise RuntimeError("logout_did_not_revoke_session")
            report["H_logout_revoked_expected_session"] = True

            with TestClient(app, base_url="https://testserver") as stale:
                stale.cookies.set("madar_access_token", stale_access)
                stale.cookies.set("madar_refresh_token", stale_refresh)
                stale_result = stale.get("/admin/data-deletions?limit=1")
                if stale_result.status_code != 401:
                    raise RuntimeError("stale_session_retained_privilege")
            report["I_stale_auth_privilege_denied"] = True

            membership = (
                service_supabase.table("tenant_memberships")
                .select("tenant_id,user_id,auth_id,role,status")
                .eq("user_id", user_id)
                .eq("tenant_id", tenant_id)
                .limit(1)
                .execute()
                .data
            )
            if (
                len(membership) != 1
                or membership[0].get("status") != "active"
                or membership[0].get("role") != "owner"
                or str(membership[0].get("auth_id")) != auth_id
            ):
                raise RuntimeError("tenant_membership_context_changed")
            report["J_tenant_workspace_context_preserved"] = True

        report["status"] = "passed"
    except Exception as error:
        report["failure_phase"] = phase
        report["error_type"] = type(error).__name__
        if isinstance(error, RuntimeError):
            report["error_code"] = str(error)
    finally:
        # Never output the seed, credentials, tokens, email, or provider response bodies.
        try:
            seed = ""
        except UnboundLocalError:
            pass
        synthetic_user_removed = auth_id is None
        synthetic_tenant_removed = tenant_id is None
        if auth_id and api is not None:
            try:
                api.call(f"/auth/v1/admin/users/{auth_id}", admin=True, method="DELETE")
                synthetic_user_removed = True
            except Exception as cleanup_error:
                synthetic_user_removed = False
                report["synthetic_user_cleanup_error_type"] = type(cleanup_error).__name__
        if tenant_id is not None and service_supabase is not None:
            try:
                service_supabase.table("tenants").delete().eq(
                    "tenant_id", tenant_id
                ).execute()
                synthetic_tenant_removed = True
            except Exception as cleanup_error:
                synthetic_tenant_removed = False
                report["synthetic_tenant_cleanup_error_type"] = type(cleanup_error).__name__
        report["synthetic_user_removed"] = synthetic_user_removed
        report["synthetic_tenant_fixture_removed"] = synthetic_tenant_removed
        if report.get("status") == "passed" and not synthetic_user_removed:
            report["status"] = "failed"
            report["failure_phase"] = "cleanup"
            report["error_type"] = "SyntheticCleanupError"
        args.evidence_output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        args.evidence_output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2, sort_keys=True))

    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

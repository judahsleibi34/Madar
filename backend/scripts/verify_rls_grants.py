#!/usr/bin/env python3
"""Read-only live Postgres/Supabase RLS and grant verification.

This script checks catalog metadata only. It does not read, insert, update, or
delete application rows.

Run from Docker:
    docker compose run --rm -e SUPABASE_DB_URL="$SUPABASE_DB_URL" backend \
      python backend/scripts/verify_rls_grants.py

Run locally:
    SUPABASE_DB_URL="postgresql://..." python backend/scripts/verify_rls_grants.py

Accepted connection env vars, in order:
    SUPABASE_DB_URL, DATABASE_URL, POSTGRES_URL, POSTGRES_PRISMA_URL,
    POSTGRES_URL_NON_POOLING

Uses the Python `psycopg` driver installed in the backend environment.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

CONNECTION_ENV_VARS = (
    "SUPABASE_DB_URL",
    "DATABASE_URL",
    "POSTGRES_URL",
    "POSTGRES_PRISMA_URL",
    "POSTGRES_URL_NON_POOLING",
)

SENSITIVE_TABLES = (
    "users",
    "contacts",
    "tenants",
    "tenant_memberships",
    "tenant_site_memberships",
    "website_settings",
    "builder_projects",
    "builder_form_submissions",
    "builder_reservations",
    "builder_assets",
    "builder_asset_references",
    "storage_accounts",
    "storage_reservations",
    "storage_objects",
    "tenant_site_project_roles",
    "tenant_site_project_role_assignments",
    "features",
    "user_security_settings",
    "audit_logs",
    "admin_account_access_requests",
    "admin_account_access_sessions",
    "notification_events",
    "user_notifications",
    "web_push_subscriptions",
    "notification_outbox",
    "ai_usage_daily",
    "billing_webhook_events",
    "email_verification_attempts",
    "pending_account_onboarding",
    "password_reset_requests",
    "calendars",
    "calendar_memberships",
    "calendar_events",
    "calendar_event_attendees",
    "calendar_event_reminders",
    "calendar_event_changes",
    "calendar_tasks",
    "calendar_task_dependencies",
    "calendar_task_reminders",
    "calendar_sync_connections",
    "calendar_sync_conflicts",
    "calendar_invitation_reviews",
    "calendar_oauth_states",
)

SENSITIVE_SECURITY_DEFINER_FUNCTIONS = (
    "admin_update_user_type_safely",
    "assign_tenant_site_project_role",
    "apply_billing_webhook_event",
    "claim_notification_outbox",
    "claim_password_reset_request",
    "create_builder_form_submission_safe",
    "finish_notification_outbox",
    "finish_password_reset_request",
    "increment_ai_usage_daily",
    "provision_verified_account",
    "publish_builder_project_atomic",
    "publish_validated_builder_project_atomic",
    "reserve_ai_usage_daily",
    "reserve_storage_bytes",
    "finish_storage_reservation",
    "release_storage_object",
    "consume_calendar_oauth_state",
)

PROTECTED_FUNCTIONS = (
    "set_updated_at",
    "get_tables",
    "get_columns",
    "touch_ai_usage_daily_updated_at",
    "increment_ai_usage_daily",
    "reserve_ai_usage_daily",
    "publish_builder_project_atomic",
    "publish_validated_builder_project_atomic",
    "apply_billing_webhook_event",
    "protect_last_system_admin",
    "admin_update_user_type_safely",
    "provision_verified_account",
    "claim_password_reset_request",
    "finish_password_reset_request",
    "validate_website_settings_published_project",
    "claim_notification_outbox",
    "finish_notification_outbox",
    "create_builder_reservation_safe",
    "cancel_builder_reservation_safe",
    "create_builder_form_submission_safe",
    "reserve_storage_bytes",
    "finish_storage_reservation",
    "release_storage_object",
    "assign_tenant_site_project_role",
    "consume_calendar_oauth_state",
)

TABLE_CRUD_GRANTS = {"SELECT", "INSERT", "UPDATE", "DELETE"}

# Direct browser access is an explicit allowlist. Tenant-scoped SELECT policies
# may expose safe reads, but privileged mutations must pass through backend
# service-role routes where validation, audit, revision and authorization rules
# are enforced.
ALLOWED_DIRECT_GRANTS = {
    "users": {"anon": set(), "authenticated": {"SELECT"}, "service_role": TABLE_CRUD_GRANTS},
    "contacts": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "tenants": {"anon": set(), "authenticated": {"SELECT"}, "service_role": TABLE_CRUD_GRANTS},
    "tenant_memberships": {
        "anon": set(),
        "authenticated": {"SELECT"},
        "service_role": TABLE_CRUD_GRANTS,
    },
    "website_settings": {
        "anon": set(),
        "authenticated": {"SELECT"},
        "service_role": TABLE_CRUD_GRANTS,
    },
    "builder_projects": {
        "anon": set(),
        "authenticated": {"SELECT"},
        "service_role": TABLE_CRUD_GRANTS,
    },
    "builder_form_submissions": {
        "anon": set(),
        "authenticated": {"SELECT"},
        "service_role": TABLE_CRUD_GRANTS,
    },
    "builder_reservations": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "builder_assets": {
        "anon": set(),
        "authenticated": set(),
        "service_role": TABLE_CRUD_GRANTS,
    },
    "builder_asset_references": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "storage_accounts": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "storage_reservations": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "storage_objects": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "tenant_site_project_roles": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "tenant_site_project_role_assignments": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "features": {"anon": set(), "authenticated": {"SELECT"}, "service_role": TABLE_CRUD_GRANTS},
    "audit_logs": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "calendars": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "calendar_memberships": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "calendar_events": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "calendar_event_attendees": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "calendar_event_reminders": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "calendar_event_changes": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "calendar_tasks": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "calendar_task_dependencies": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "calendar_task_reminders": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "calendar_sync_connections": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "calendar_sync_conflicts": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "calendar_invitation_reviews": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    "calendar_oauth_states": {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
}

# Every table not given a narrower browser-read exception is backend-only.
for _table in SENSITIVE_TABLES:
    ALLOWED_DIRECT_GRANTS.setdefault(
        _table,
        {"anon": set(), "authenticated": set(), "service_role": TABLE_CRUD_GRANTS},
    )

EXPECTED_GRANTEES = ("public", "anon", "authenticated", "service_role")
EXPECTED_OWNER = "postgres"
SEQUENCE_SERVICE_GRANTS = {"USAGE", "SELECT"}

# These backend-owned tables have an intentionally narrower browser contract
# than the general sensitive-table matrix: authenticated may read them and may
# hold no other table privilege. Keeping the exact tuple-keyed allowlist visible
# prevents future PostgreSQL privileges from passing by default.
AUTHENTICATED_SELECT_ONLY_GRANTS = {
    ("authenticated", "public", "users"): {"SELECT"},
    ("authenticated", "public", "builder_projects"): {"SELECT"},
    ("authenticated", "public", "website_settings"): {"SELECT"},
}

EXPECTED_POLICIES: dict[str, dict[str, Callable[[str, str], bool]]] = {
    "tenants": {
        "tenant member access": lambda name, expr: has_all(expr, "tenant_memberships", "auth.uid")
    },
    "tenant_memberships": {
        "scoped member access": lambda name, expr: "auth.uid" in expr
        and ("tenant_memberships" in expr or "auth_id" in expr)
    },
    "website_settings": {
        "tenant member access": lambda name, expr: has_all(expr, "tenant_memberships", "auth.uid")
    },
    "builder_projects": {
        "tenant member access": lambda name, expr: has_all(expr, "tenant_memberships", "auth.uid")
    },
    "builder_form_submissions": {
        "tenant member read access": lambda name, expr: "select" in name
        and has_all(expr, "tenant_memberships", "auth.uid")
    },
    "features": {
        "scoped select": lambda name, expr: "select" in name
        and has_all(expr, "tenant_memberships", "auth.uid")
    },
}


@dataclass
class TableReport:
    table: str
    exists: bool
    rls_enabled: bool
    owner_safe: bool
    unsafe_grants: list[str]
    missing_policies: list[str]


@dataclass
class FunctionReport:
    signature: str
    safe_search_path: bool
    unsafe_execute_roles: list[str]
    owner_safe: bool = True
    service_execute_correct: bool = True
    security_mode_correct: bool = True


def has_all(value: str, *needles: str) -> bool:
    return all(needle in value for needle in needles)


def load_dotenv_file() -> None:
    """Load simple KEY=value or KEY: value entries without overriding env."""
    env_path = Path(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_connection_url() -> tuple[str | None, str | None]:
    for name in CONNECTION_ENV_VARS:
        value = os.getenv(name)
        if value:
            return name, value
    return None, None


def run_catalog_query(connection_url: str, sql: str) -> list[dict[str, str]]:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("Missing required Python dependency: psycopg", file=sys.stderr)
        print("Install backend requirements or rebuild the backend Docker image, then rerun the check.", file=sys.stderr)
        return raise_config_error()

    try:
        with psycopg.connect(
            connection_url,
            autocommit=True,
            connect_timeout=10,
            options="-c default_transaction_read_only=on -c statement_timeout=30000",
            row_factory=dict_row,
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                return [dict(row) for row in cursor.fetchall()]
    except psycopg.Error as exc:
        print("Failed to query Postgres catalog metadata with psycopg.", file=sys.stderr)
        print(redact_known_secrets(str(exc)), file=sys.stderr)
        raise SystemExit(2) from None


def raise_config_error() -> list[dict[str, str]]:
    raise SystemExit(2)


def redact_known_secrets(value: str) -> str:
    for env_name in CONNECTION_ENV_VARS:
        secret = os.getenv(env_name)
        if secret:
            value = value.replace(secret, f"<{env_name} redacted>")
    return value


def fetch_catalog(
    connection_url: str,
) -> tuple[
    dict[str, dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    table_names = ", ".join(sql_literal(table) for table in SENSITIVE_TABLES)
    tables = run_catalog_query(
        connection_url,
        f"""
        select
          c.relname as table_name,
          c.relrowsecurity::text as rls_enabled,
          pg_get_userbyid(c.relowner) as owner_name
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public'
          and c.relkind in ('r', 'p')
          and c.relname in ({table_names})
        order by c.relname;
        """,
    )
    policies = run_catalog_query(
        connection_url,
        f"""
        select
          c.relname as table_name,
          p.polname as policy_name,
          case p.polcmd
            when 'r' then 'select'
            when 'a' then 'insert'
            when 'w' then 'update'
            when 'd' then 'delete'
            when '*' then 'all'
            else p.polcmd::text
          end as command,
          coalesce(
            (
              select string_agg(r.rolname, ',')
              from unnest(p.polroles) as role_oid
              join pg_roles r on r.oid = role_oid
            ),
            'public'
          ) as roles,
          coalesce(pg_get_expr(p.polqual, p.polrelid), '') as using_expression,
          coalesce(pg_get_expr(p.polwithcheck, p.polrelid), '') as check_expression
        from pg_policy p
        join pg_class c on c.oid = p.polrelid
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public'
          and c.relname in ({table_names})
        order by c.relname, p.polname;
        """,
    )
    grants = run_catalog_query(
        connection_url,
        f"""
        select
          c.relname as table_name,
          coalesce(role.rolname, 'public') as grantee,
          acl.privilege_type
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        cross join lateral aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) acl
        left join pg_roles role on role.oid = acl.grantee
        where n.nspname = 'public'
          and c.relkind in ('r', 'p')
          and c.relname in ({table_names})
          and (acl.grantee = 0 or role.rolname in ('anon', 'authenticated', 'service_role', 'postgres'))
        order by c.relname, grantee, acl.privilege_type;
        """,
    )
    function_names = ", ".join(sql_literal(name) for name in PROTECTED_FUNCTIONS)
    functions = run_catalog_query(
        connection_url,
        f"""
        select
          p.oid::regprocedure::text as signature,
          p.proname as function_name,
          p.prosecdef::text as security_definer,
          pg_get_userbyid(p.proowner) as owner_name,
          coalesce(array_to_string(p.proconfig, ','), '') as settings,
          exists (
            select 1
            from aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) acl
            where acl.grantee = 0 and acl.privilege_type = 'EXECUTE'
          )::text as public_execute,
          exists (
            select 1
            from aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) acl
            join pg_roles role on role.oid = acl.grantee
            where role.rolname = 'anon' and acl.privilege_type = 'EXECUTE'
          )::text as anon_execute,
          exists (
            select 1
            from aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) acl
            join pg_roles role on role.oid = acl.grantee
            where role.rolname = 'authenticated' and acl.privilege_type = 'EXECUTE'
          )::text as authenticated_execute
          ,exists (
            select 1
            from aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) acl
            join pg_roles role on role.oid = acl.grantee
            where role.rolname = 'service_role' and acl.privilege_type = 'EXECUTE'
          )::text as service_role_execute
        from pg_proc p
        join pg_namespace n on n.oid = p.pronamespace
        where n.nspname = 'public'
          and p.proname in ({function_names})
        order by p.proname, p.oid::regprocedure::text;
        """,
    )
    return ({row["table_name"]: row for row in tables}, policies, grants, functions)


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_reports(
    tables: dict[str, dict[str, str]], policies: list[dict[str, str]], grants: list[dict[str, str]]
) -> list[TableReport]:
    policies_by_table: dict[str, list[dict[str, str]]] = {table: [] for table in SENSITIVE_TABLES}
    for policy in policies:
        policies_by_table.setdefault(policy["table_name"], []).append(policy)

    grants_by_table: dict[str, list[dict[str, str]]] = {table: [] for table in SENSITIVE_TABLES}
    for grant in grants:
        grants_by_table.setdefault(grant["table_name"], []).append(grant)

    reports: list[TableReport] = []
    for table in SENSITIVE_TABLES:
        table_row = tables.get(table)
        unsafe_grants = find_grant_mismatches(table, grants_by_table.get(table, []))
        missing_policies = find_missing_policies(table, policies_by_table.get(table, []))
        reports.append(
            TableReport(
                table=table,
                exists=table_row is not None,
                rls_enabled=table_row is not None and str(table_row.get("rls_enabled")).lower() == "true",
                owner_safe=table_row is not None and table_row.get("owner_name") == EXPECTED_OWNER,
                unsafe_grants=unsafe_grants,
                missing_policies=missing_policies,
            )
        )
    return reports


def find_unsafe_grants(table: str, grants: list[dict[str, str]]) -> list[str]:
    unsafe: list[str] = []
    allowed_for_table = ALLOWED_DIRECT_GRANTS.get(table, {})
    for grant in grants:
        grantee = str(grant["grantee"]).lower()
        privilege = str(grant["privilege_type"]).upper()
        allowed = AUTHENTICATED_SELECT_ONLY_GRANTS.get(
            (grantee, "public", table),
            allowed_for_table.get(grantee, set()),
        )
        if privilege not in allowed:
            unsafe.append(f"{grantee}:{privilege}")
    return sorted(set(unsafe))


def expected_table_grants(table: str, grantee: str) -> set[str]:
    if grantee == "public":
        return set()
    return set(ALLOWED_DIRECT_GRANTS.get(table, {}).get(grantee, set()))


def find_grant_mismatches(table: str, grants: list[dict[str, str]]) -> list[str]:
    """Return both unexpected and missing direct privileges for the exact ACL."""
    actual = {role: set() for role in EXPECTED_GRANTEES}
    for row in grants:
        role = str(row["grantee"]).lower()
        if role in actual:
            actual[role].add(str(row["privilege_type"]).upper())
    mismatches: list[str] = []
    for role in EXPECTED_GRANTEES:
        expected = expected_table_grants(table, role)
        for privilege in sorted(actual[role] - expected):
            mismatches.append(f"{role}:unexpected:{privilege}")
        for privilege in sorted(expected - actual[role]):
            mismatches.append(f"{role}:missing:{privilege}")
    return mismatches


def describe_unsafe_grants(table: str, unsafe_grants: list[str]) -> list[str]:
    descriptions: list[str] = []
    for value in unsafe_grants:
        parts = value.split(":", 2)
        if len(parts) == 3:
            role, kind, privilege = parts
        else:
            role, privilege = parts
            kind = "unexpected"
        allowed = AUTHENTICATED_SELECT_ONLY_GRANTS.get(
            (role, "public", table),
            ALLOWED_DIRECT_GRANTS.get(table, {}).get(role, set()),
        )
        expected = ",".join(sorted(allowed)) if allowed else "none"
        descriptions.append(
            f"role={role} table=public.{table} {kind}={privilege} expected={expected}"
        )
    return descriptions


def find_missing_policies(table: str, policies: list[dict[str, str]]) -> list[str]:
    expected = EXPECTED_POLICIES.get(table, {})
    missing: list[str] = []
    for label, matcher in expected.items():
        found = False
        for policy in policies:
            name = policy.get("policy_name", "").lower()
            expr = " ".join(
                [
                    policy.get("command", ""),
                    policy.get("roles", ""),
                    policy.get("using_expression", ""),
                    policy.get("check_expression", ""),
                ]
            ).lower()
            if matcher(name, expr):
                found = True
                break
        if not found:
            missing.append(label)
    return missing


def build_function_reports(functions: list[dict[str, str]]) -> list[FunctionReport]:
    reports: list[FunctionReport] = []
    for function in functions:
        settings = str(function.get("settings") or "").lower().replace(" ", "")
        unsafe_roles = [
            role
            for role in ("public", "anon", "authenticated")
            if str(function.get(f"{role}_execute") or "").lower() == "true"
        ]
        reports.append(
            FunctionReport(
                signature=str(function.get("signature") or function.get("function_name") or "unknown"),
                safe_search_path="search_path=public" in settings or "search_path=''" in settings,
                unsafe_execute_roles=unsafe_roles,
                owner_safe=str(function.get("owner_name") or EXPECTED_OWNER) == EXPECTED_OWNER,
                service_execute_correct=(
                    str(function.get("service_role_execute") or "true").lower() == "true"
                ) != (str(function.get("function_name") or "") == "publish_builder_project_atomic"),
                security_mode_correct=(
                    str(function.get("function_name") or "") not in SENSITIVE_SECURITY_DEFINER_FUNCTIONS
                    or str(function.get("security_definer") or "true").lower() == "true"
                ),
            )
        )
    return reports


def find_sequence_mismatches(rows: list[dict[str, str]]) -> list[str]:
    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        name = str(row["sequence_name"])
        entry = grouped.setdefault(
            name,
            {"owner": row.get("owner_name"), "grants": {role: set() for role in EXPECTED_GRANTEES}},
        )
        role = str(row.get("grantee") or "").lower()
        privilege = str(row.get("privilege_type") or "").upper()
        if role in entry["grants"] and privilege:  # type: ignore[operator]
            entry["grants"][role].add(privilege)  # type: ignore[index]
    mismatches: list[str] = []
    for name, entry in sorted(grouped.items()):
        if entry["owner"] != EXPECTED_OWNER:
            mismatches.append(f"sequence=public.{name} owner={entry['owner']} expected={EXPECTED_OWNER}")
        grants = entry["grants"]
        for role in EXPECTED_GRANTEES:
            expected = SEQUENCE_SERVICE_GRANTS if role == "service_role" else set()
            actual = grants[role]  # type: ignore[index]
            for privilege in sorted(actual - expected):
                mismatches.append(
                    f"role={role} sequence=public.{name} unexpected={privilege} expected={','.join(sorted(expected)) or 'none'}"
                )
            for privilege in sorted(expected - actual):
                mismatches.append(
                    f"role={role} sequence=public.{name} missing={privilege} expected={','.join(sorted(expected))}"
                )
    return mismatches


def find_function_mismatches(functions: list[dict[str, str]]) -> list[str]:
    mismatches: list[str] = []
    found_names = {str(row.get("function_name")) for row in functions}
    for name in PROTECTED_FUNCTIONS:
        if name not in found_names:
            mismatches.append(f"function=public.{name} missing")
    for report in build_function_reports(functions):
        if not report.owner_safe:
            mismatches.append(
                f"function={report.signature} owner=unexpected expected={EXPECTED_OWNER}"
            )
        if not report.safe_search_path:
            mismatches.append(f"function={report.signature} unsafe_search_path")
        for role in report.unsafe_execute_roles:
            mismatches.append(f"role={role} function={report.signature} unexpected=EXECUTE expected=none")
        if not report.service_execute_correct:
            mismatches.append(f"role=service_role function={report.signature} execute_mismatch")
        if not report.security_mode_correct:
            mismatches.append(f"function={report.signature} missing=SECURITY_DEFINER")
    return mismatches


def find_default_acl_mismatches(rows: list[dict[str, str]]) -> list[str]:
    actual = {
        object_type: {role: set() for role in EXPECTED_GRANTEES}
        for object_type in ("tables", "sequences", "functions")
    }
    for row in rows:
        object_type = str(row["object_type"])
        role = str(row["grantee"]).lower()
        if object_type in actual and role in actual[object_type]:
            actual[object_type][role].add(str(row["privilege_type"]).upper())
    expected_service = {
        "tables": TABLE_CRUD_GRANTS,
        "sequences": SEQUENCE_SERVICE_GRANTS,
        "functions": {"EXECUTE"},
    }
    mismatches: list[str] = []
    for object_type, roles in actual.items():
        for role, privileges in roles.items():
            expected = expected_service[object_type] if role == "service_role" else set()
            for privilege in sorted(privileges - expected):
                mismatches.append(
                    f"default={object_type} role={role} unexpected={privilege} expected={','.join(sorted(expected)) or 'none'}"
                )
            for privilege in sorted(expected - privileges):
                mismatches.append(
                    f"default={object_type} role={role} missing={privilege} expected={','.join(sorted(expected))}"
                )
    return mismatches


def fetch_extended_contract(connection_url: str) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    table_names = ", ".join(sql_literal(table) for table in SENSITIVE_TABLES)
    sequences = run_catalog_query(
        connection_url,
        f"""
        with owned_sequences as (
          select distinct seq.oid, seq.relname, seq.relowner, seq.relacl
          from pg_class seq
          join pg_namespace ns on ns.oid = seq.relnamespace
          join pg_depend d on d.objid = seq.oid and d.deptype in ('a', 'i')
          join pg_class parent on parent.oid = d.refobjid
          join pg_namespace parent_ns on parent_ns.oid = parent.relnamespace
          where seq.relkind = 'S' and ns.nspname = 'public'
            and parent_ns.nspname = 'public' and parent.relname in ({table_names})
        )
        select seq.relname as sequence_name, pg_get_userbyid(seq.relowner) as owner_name,
          coalesce(role.rolname, 'public') as grantee, acl.privilege_type
        from owned_sequences seq
        left join lateral aclexplode(coalesce(seq.relacl, acldefault('S', seq.relowner))) acl on true
        left join pg_roles role on role.oid = acl.grantee
        where acl.grantee = 0 or role.rolname in ('anon', 'authenticated', 'service_role', 'postgres')
        order by seq.relname, grantee, acl.privilege_type;
        """,
    )
    default_acls = run_catalog_query(
        connection_url,
        """
        select case d.defaclobjtype when 'r' then 'tables' when 'S' then 'sequences' when 'f' then 'functions' end as object_type,
          coalesce(grantee.rolname, 'public') as grantee, acl.privilege_type
        from pg_default_acl d
        join pg_roles owner on owner.oid = d.defaclrole
        join pg_namespace n on n.oid = d.defaclnamespace
        cross join lateral aclexplode(d.defaclacl) acl
        left join pg_roles grantee on grantee.oid = acl.grantee
        where owner.rolname = 'postgres' and n.nspname = 'public'
          and d.defaclobjtype in ('r', 'S', 'f')
          and (acl.grantee = 0 or grantee.rolname in ('anon', 'authenticated', 'service_role'))
        order by object_type, grantee, acl.privilege_type;
        """,
    )
    schema_privileges = run_catalog_query(
        connection_url,
        """
        select role_name,
          has_schema_privilege(role_name, 'public', 'USAGE')::text as has_usage,
          has_schema_privilege(role_name, 'public', 'CREATE')::text as has_create
        from unnest(array['anon','authenticated','service_role']) role_name;
        """,
    )
    dangerous_memberships = run_catalog_query(
        connection_url,
        """
        select member.rolname as member_role, granted.rolname as granted_role
        from pg_auth_members membership
        join pg_roles member on member.oid = membership.member
        join pg_roles granted on granted.oid = membership.roleid
        where member.rolname in ('anon', 'authenticated', 'service_role')
          and granted.rolname in ('postgres', 'supabase_admin', 'anon', 'authenticated', 'service_role');
        """,
    )
    sensitive_views = run_catalog_query(
        connection_url,
        f"""
        select distinct view_class.relname as view_name,
          pg_get_userbyid(view_class.relowner) as owner_name
        from pg_rewrite rewrite
        join pg_class view_class on view_class.oid = rewrite.ev_class
        join pg_namespace view_ns on view_ns.oid = view_class.relnamespace
        join pg_depend dependency on dependency.objid = rewrite.oid
        join pg_class source_class on source_class.oid = dependency.refobjid
        join pg_namespace source_ns on source_ns.oid = source_class.relnamespace
        where view_ns.nspname = 'public' and view_class.relkind in ('v', 'm')
          and source_ns.nspname = 'public' and source_class.relname in ({table_names});
        """,
    )
    return sequences, default_acls, schema_privileges, dangerous_memberships, sensitive_views


def find_environment_mismatches(
    schema_privileges: list[dict[str, str]], dangerous_memberships: list[dict[str, str]],
    sensitive_views: list[dict[str, str]] | None = None,
) -> list[str]:
    mismatches = []
    for row in schema_privileges:
        role = row["role_name"]
        if str(row.get("has_create")).lower() == "true":
            mismatches.append(f"role={role} schema=public unexpected=CREATE expected=USAGE")
        if str(row.get("has_usage")).lower() != "true":
            mismatches.append(f"role={role} schema=public missing=USAGE")
    for row in dangerous_memberships:
        mismatches.append(
            f"role={row['member_role']} inherits={row['granted_role']} invalidates_direct_acl_contract"
        )
    for row in sensitive_views or []:
        mismatches.append(
            f"view=public.{row['view_name']} depends_on_sensitive_table without_explicit_allowlist"
        )
    return mismatches


def print_report(
    reports: list[TableReport],
    policies: list[dict[str, str]],
    grants: list[dict[str, str]],
    function_reports: list[FunctionReport],
) -> None:
    print("Live Supabase/Postgres RLS and grant verification")
    print("Catalog-only check: pg_class, pg_namespace, pg_policy, information_schema.role_table_grants")
    print()
    print(f"{'table':34} {'exists':7} {'rls':7} {'owner':7} {'ACL mismatches':28} expected policies")
    print("-" * 110)
    for report in reports:
        unsafe = ", ".join(report.unsafe_grants) if report.unsafe_grants else "none"
        missing = ", ".join(report.missing_policies) if report.missing_policies else "ok"
        print(
            f"{report.table:34} {yes_no(report.exists):7} {yes_no(report.rls_enabled):7} "
            f"{yes_no(report.owner_safe):7} "
            f"{unsafe[:28]:28} {missing}"
        )

    print("\nPolicies discovered:")
    for policy in policies:
        print(
            f"- {policy['table_name']}.{policy['policy_name']} "
            f"command={policy['command']} roles={policy['roles']}"
        )

    print("\nGrants discovered for anon/authenticated/service_role:")
    compact_grants: dict[str, dict[str, list[str]]] = {}
    for grant in grants:
        compact_grants.setdefault(grant["table_name"], {}).setdefault(grant["grantee"], []).append(
            grant["privilege_type"]
        )
    print(json.dumps(compact_grants, indent=2, sort_keys=True))

    print("\nSensitive SECURITY DEFINER functions:")
    for report in function_reports:
        execute = ",".join(report.unsafe_execute_roles) if report.unsafe_execute_roles else "service-only"
        print(
            f"- {report.signature}: search_path={'safe' if report.safe_search_path else 'unsafe'} "
            f"execute={execute}"
        )

    failures = [
        report
        for report in reports
        if not report.exists or not report.rls_enabled or not report.owner_safe or report.unsafe_grants or report.missing_policies
    ]
    print("\nSummary:")
    function_failures = [
        report
        for report in function_reports
        if not report.safe_search_path or report.unsafe_execute_roles or not report.owner_safe
        or not report.service_execute_correct or not report.security_mode_correct
    ]
    if failures or function_failures:
        print(
            f"FAIL: {len(failures)} table(s) and {len(function_failures)} sensitive function(s) "
            "need attention."
        )
        for report in failures:
            reasons = []
            if not report.exists:
                reasons.append("missing table")
            if report.exists and not report.rls_enabled:
                reasons.append("RLS disabled")
            if report.exists and not report.owner_safe:
                reasons.append(f"unexpected owner (expected {EXPECTED_OWNER})")
            if report.unsafe_grants:
                reasons.append(
                    "unsafe grants: "
                    + "; ".join(describe_unsafe_grants(report.table, report.unsafe_grants))
                )
            if report.missing_policies:
                reasons.append("missing policies: " + ", ".join(report.missing_policies))
            print(f"- {report.table}: {'; '.join(reasons)}")
        for report in function_failures:
            reasons = []
            if not report.safe_search_path:
                reasons.append("unsafe search_path")
            if report.unsafe_execute_roles:
                reasons.append("unsafe execute: " + ", ".join(report.unsafe_execute_roles))
            if not report.owner_safe:
                reasons.append("unexpected owner")
            if not report.service_execute_correct:
                reasons.append("service-role execute mismatch")
            if not report.security_mode_correct:
                reasons.append("SECURITY DEFINER mismatch")
            print(f"- {report.signature}: {'; '.join(reasons)}")
    else:
        print("PASS: all checked tables have RLS enabled, only explicitly allowed grants, and expected policies.")


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def main() -> int:
    load_dotenv_file()
    env_name, connection_url = get_connection_url()
    if not connection_url:
        print("Missing live Postgres connection URL.", file=sys.stderr)
        print("Set one of these env vars:", file=sys.stderr)
        for name in CONNECTION_ENV_VARS:
            print(f"  - {name}", file=sys.stderr)
        print("The value should be a Postgres connection string with catalog read access.", file=sys.stderr)
        return 2

    tables, policies, grants, functions = fetch_catalog(connection_url)
    reports = build_reports(tables, policies, grants)
    function_reports = build_function_reports(functions)
    print_report(reports, policies, grants, function_reports)
    sequences, default_acls, schema_privileges, dangerous_memberships, sensitive_views = fetch_extended_contract(connection_url)
    extended_failures = (
        find_sequence_mismatches(sequences)
        + find_function_mismatches(functions)
        + find_default_acl_mismatches(default_acls)
        + find_environment_mismatches(schema_privileges, dangerous_memberships, sensitive_views)
    )
    print("\nExact sequence/function/default/schema/role contract:")
    if extended_failures:
        for failure in extended_failures:
            print(f"- {failure}")
    else:
        print("PASS: exact extended ACL contract matches the repository allowlist.")
    failed = any(
        not report.exists or not report.rls_enabled or not report.owner_safe or report.unsafe_grants or report.missing_policies
        for report in reports
    ) or any(
        not report.safe_search_path or report.unsafe_execute_roles or not report.owner_safe
        or not report.service_execute_correct or not report.security_mode_correct
        for report in function_reports
    ) or bool(extended_failures)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

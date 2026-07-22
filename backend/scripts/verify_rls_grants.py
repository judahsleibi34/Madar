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
    "website_settings",
    "builder_projects",
    "builder_form_submissions",
    "builder_assets",
    "storage_accounts",
    "storage_reservations",
    "storage_objects",
    "tenant_site_project_roles",
    "tenant_site_project_role_assignments",
    "features",
    "audit_logs",
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
    "builder_assets": {
        "anon": set(),
        "authenticated": set(),
        "service_role": TABLE_CRUD_GRANTS,
    },
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
    unsafe_grants: list[str]
    missing_policies: list[str]


@dataclass
class FunctionReport:
    signature: str
    safe_search_path: bool
    unsafe_execute_roles: list[str]


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
          c.relrowsecurity::text as rls_enabled
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
          table_name,
          grantee,
          privilege_type
        from information_schema.role_table_grants
        where table_schema = 'public'
          and table_name in ({table_names})
          and grantee in ('anon', 'authenticated', 'service_role')
        order by table_name, grantee, privilege_type;
        """,
    )
    function_names = ", ".join(sql_literal(name) for name in SENSITIVE_SECURITY_DEFINER_FUNCTIONS)
    functions = run_catalog_query(
        connection_url,
        f"""
        select
          p.oid::regprocedure::text as signature,
          p.proname as function_name,
          p.prosecdef::text as security_definer,
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
        unsafe_grants = find_unsafe_grants(table, grants_by_table.get(table, []))
        missing_policies = find_missing_policies(table, policies_by_table.get(table, []))
        reports.append(
            TableReport(
                table=table,
                exists=table_row is not None,
                rls_enabled=table_row is not None and str(table_row.get("rls_enabled")).lower() == "true",
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


def describe_unsafe_grants(table: str, unsafe_grants: list[str]) -> list[str]:
    descriptions: list[str] = []
    for value in unsafe_grants:
        role, privilege = value.split(":", 1)
        allowed = AUTHENTICATED_SELECT_ONLY_GRANTS.get(
            (role, "public", table),
            ALLOWED_DIRECT_GRANTS.get(table, {}).get(role, set()),
        )
        expected = ",".join(sorted(allowed)) if allowed else "none"
        descriptions.append(
            f"role={role} table=public.{table} unexpected={privilege} expected={expected}"
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
                safe_search_path="search_path=public" in settings,
                unsafe_execute_roles=unsafe_roles,
            )
        )
    return reports


def print_report(
    reports: list[TableReport],
    policies: list[dict[str, str]],
    grants: list[dict[str, str]],
    function_reports: list[FunctionReport],
) -> None:
    print("Live Supabase/Postgres RLS and grant verification")
    print("Catalog-only check: pg_class, pg_namespace, pg_policy, information_schema.role_table_grants")
    print()
    print(f"{'table':34} {'exists':7} {'rls':7} {'unsafe grants':28} expected policies")
    print("-" * 110)
    for report in reports:
        unsafe = ", ".join(report.unsafe_grants) if report.unsafe_grants else "none"
        missing = ", ".join(report.missing_policies) if report.missing_policies else "ok"
        print(
            f"{report.table:34} {yes_no(report.exists):7} {yes_no(report.rls_enabled):7} "
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
        if not report.exists or not report.rls_enabled or report.unsafe_grants or report.missing_policies
    ]
    print("\nSummary:")
    function_failures = [
        report
        for report in function_reports
        if not report.safe_search_path or report.unsafe_execute_roles
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
    failed = any(
        not report.exists or not report.rls_enabled or report.unsafe_grants or report.missing_policies
        for report in reports
    ) or any(
        not report.safe_search_path or report.unsafe_execute_roles
        for report in function_reports
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

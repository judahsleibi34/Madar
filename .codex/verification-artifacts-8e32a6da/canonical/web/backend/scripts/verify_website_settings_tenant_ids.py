
#!/usr/bin/env python3
"""Read-only live verification for legacy website_settings tenant_id fallback.

This script inspects only public.website_settings and public.users metadata.
It does not read, insert, update, or delete application rows.

Run from Docker:
    docker compose run --rm -e SUPABASE_DB_URL="$SUPABASE_DB_URL" backend           python backend/scripts/verify_website_settings_tenant_ids.py

Run locally:
    SUPABASE_DB_URL="postgresql://..." python backend/scripts/verify_website_settings_tenant_ids.py

Accepted connection env vars, in order:
    SUPABASE_DB_URL, DATABASE_URL, POSTGRES_URL, POSTGRES_PRISMA_URL,
    POSTGRES_URL_NON_POOLING

Uses the Python `psycopg` driver installed in the backend environment.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

CONNECTION_ENV_VARS = (
    "SUPABASE_DB_URL",
    "DATABASE_URL",
    "POSTGRES_URL",
    "POSTGRES_PRISMA_URL",
    "POSTGRES_URL_NON_POOLING",
)


@dataclass(frozen=True)
class WebsiteSettingsFallbackSummary:
    total_rows: int
    tenant_id_null_rows: int
    tenant_id_null_user_id_null_rows: int
    tenant_id_null_user_fallback_resolves_rows: int
    tenant_id_null_user_fallback_unresolvable_rows: int
    tenant_id_present_user_fallback_disagree_rows: int

    @property
    def has_legacy_rows(self) -> bool:
        return self.tenant_id_null_rows > 0

    @property
    def has_unresolvable_rows(self) -> bool:
        return self.tenant_id_null_user_fallback_unresolvable_rows > 0

    @property
    def has_disagreements(self) -> bool:
        return self.tenant_id_present_user_fallback_disagree_rows > 0


def get_connection_url() -> tuple[str | None, str | None]:
    for name in CONNECTION_ENV_VARS:
        value = os.getenv(name)
        if value:
            return name, value
    return None, None


def redact_known_secrets(value: str) -> str:
    for env_name in CONNECTION_ENV_VARS:
        secret = os.getenv(env_name)
        if secret:
            value = value.replace(secret, f"<{env_name} redacted>")
    return value


def run_query(connection_url: str, sql: str):
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("Missing required Python dependency: psycopg", file=sys.stderr)
        print(
            "Install backend requirements or rebuild the backend Docker image, then rerun the check.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None

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
                return cursor.fetchall()
    except psycopg.Error as exc:
        print("Failed to query Postgres metadata with psycopg.", file=sys.stderr)
        print(redact_known_secrets(str(exc)), file=sys.stderr)
        raise SystemExit(2) from None


def fetch_summary(connection_url: str) -> WebsiteSettingsFallbackSummary:
    rows = run_query(
        connection_url,
        """
        with website_settings_joined as (
            select
                ws.id,
                ws.tenant_id,
                ws.user_id,
                u.tenant_id as user_tenant_id
            from public.website_settings as ws
            left join public.users as u on u.id = ws.user_id
        )
        select
            count(*)::int as total_rows,
            count(*) filter (where tenant_id is null)::int as tenant_id_null_rows,
            count(*) filter (where tenant_id is null and user_id is null)::int as tenant_id_null_user_id_null_rows,
            count(*) filter (
                where tenant_id is null
                  and user_id is not null
                  and user_tenant_id is not null
            )::int as tenant_id_null_user_fallback_resolves_rows,
            count(*) filter (
                where tenant_id is null
                  and user_id is not null
                  and user_tenant_id is null
            )::int as tenant_id_null_user_fallback_unresolvable_rows,
            count(*) filter (
                where tenant_id is not null
                  and user_id is not null
                  and user_tenant_id is not null
                  and tenant_id <> user_tenant_id
            )::int as tenant_id_present_user_fallback_disagree_rows
        from website_settings_joined;
        """,
    )
    if not rows:
        return WebsiteSettingsFallbackSummary(0, 0, 0, 0, 0, 0)

    row = rows[0]
    return WebsiteSettingsFallbackSummary(
        total_rows=int(row["total_rows"] or 0),
        tenant_id_null_rows=int(row["tenant_id_null_rows"] or 0),
        tenant_id_null_user_id_null_rows=int(row["tenant_id_null_user_id_null_rows"] or 0),
        tenant_id_null_user_fallback_resolves_rows=int(
            row["tenant_id_null_user_fallback_resolves_rows"] or 0
        ),
        tenant_id_null_user_fallback_unresolvable_rows=int(
            row["tenant_id_null_user_fallback_unresolvable_rows"] or 0
        ),
        tenant_id_present_user_fallback_disagree_rows=int(
            row["tenant_id_present_user_fallback_disagree_rows"] or 0
        ),
    )


def summarize(summary: WebsiteSettingsFallbackSummary) -> tuple[str, str]:
    if summary.total_rows == 0:
        return (
            "WARN",
            "No website_settings rows were found. Fallback removal cannot be validated from empty data.",
        )
    if summary.has_disagreements or summary.has_unresolvable_rows:
        return (
            "FAIL",
            "Live data still depends on the legacy fallback, and some rows are missing a resolvable tenant_id.",
        )
    if summary.has_legacy_rows:
        return (
            "WARN",
            "Live data still contains legacy website_settings rows without tenant_id. Keep the fallback until cleanup completes.",
        )
    return (
        "PASS",
        "No website_settings rows need the legacy fallback. It should be removable after a migration-level cleanup check.",
    )


def main() -> int:
    env_name, connection_url = get_connection_url()
    if not connection_url:
        print(
            "Missing database connection URL. Set one of: " + ", ".join(CONNECTION_ENV_VARS),
            file=sys.stderr,
        )
        return 2

    summary = fetch_summary(connection_url)
    status, recommendation = summarize(summary)

    print("Website settings legacy fallback verification")
    print(f"- connection env: {env_name}")
    print(f"- total website_settings rows: {summary.total_rows}")
    print(f"- rows with tenant_id NULL: {summary.tenant_id_null_rows}")
    print(f"- rows with tenant_id NULL and user_id NULL: {summary.tenant_id_null_user_id_null_rows}")
    print(
        "- rows with tenant_id NULL and user_id resolving to users.tenant_id: "
        f"{summary.tenant_id_null_user_fallback_resolves_rows}"
    )
    print(
        "- rows with tenant_id NULL and user_id not resolving to users.tenant_id: "
        f"{summary.tenant_id_null_user_fallback_unresolvable_rows}"
    )
    print(
        "- rows with tenant_id present but legacy fallback would disagree: "
        f"{summary.tenant_id_present_user_fallback_disagree_rows}"
    )
    print(f"Summary: {status}")
    print(f"Recommendation: {recommendation}")

    if status == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

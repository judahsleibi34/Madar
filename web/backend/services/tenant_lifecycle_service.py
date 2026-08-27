"""Fail-closed tenant lifecycle gate shared by private and public routes."""

from __future__ import annotations

import os

from database import service_supabase


def enforcement_enabled() -> bool:
    if os.getenv("APP_ENV", "").strip().lower() != "test":
        return True
    return os.getenv("MADAR_TEST_TENANT_LIFECYCLE_LOOKUPS", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


def tenant_is_active(tenant_id: int | str, *, client=None) -> bool:
    if not enforcement_enabled():
        return True
    database_client = client or service_supabase
    try:
        response = (
            database_client.table("tenants")
            .select("tenant_id")
            .eq("tenant_id", int(tenant_id))
            .eq("lifecycle_state", "active")
            .limit(1)
            .execute()
        )
        return bool(getattr(response, "data", None) or [])
    except Exception as error:
        # Schema 083 is expand-only. This release deliberately acts as the
        # compatibility bridge on schemas 081/082, where no deletion-pending
        # tenant state can exist yet. Any other lookup error fails closed.
        detail = str(error).lower()
        missing_column = "lifecycle_state" in detail and (
            "does not exist" in detail or "could not find" in detail
        )
        if not missing_column:
            return False
        try:
            state = (
                database_client.table("application_schema_state")
                .select("schema_version")
                .eq("contract_key", "core")
                .limit(1)
                .execute()
            )
            rows = getattr(state, "data", None) or []
            return len(rows) == 1 and int(rows[0].get("schema_version") or 0) in {81, 82}
        except Exception:
            return False

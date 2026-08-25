#!/usr/bin/env python3
"""Read-only, redaction-safe tenant commercial-state inventory.

Only ``select`` queries are issued. Customer names are omitted unless an
operator explicitly requests them with ``--include-names``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from database import service_supabase
from services.commercial_catalog import BASE_PLAN_IDS, PRODUCTS


ENTITLED_STATES = {"active", "trial", "grace"}


def rows(table: str, columns: str, tenant_id: int | None = None) -> list[dict]:
    """The inventory's only database primitive: a bounded SELECT."""
    query = service_supabase.table(table).select(columns)
    if tenant_id is not None:
        query = query.eq("tenant_id", tenant_id)
    response = query.limit(10000).execute()
    return [item for item in (getattr(response, "data", None) or []) if isinstance(item, dict)]


def optional_rows(table: str, columns: str, tenant_id: int) -> tuple[list[dict], str | None]:
    try:
        return rows(table, columns, tenant_id), None
    except Exception as error:
        return [], f"lookup_unavailable:{type(error).__name__}"


def optional_all_rows(table: str, columns: str) -> tuple[list[dict], str | None]:
    try:
        return rows(table, columns), None
    except Exception as error:
        return [], f"lookup_unavailable:{type(error).__name__}"


def by_tenant(records: list[dict]) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}
    for record in records:
        try:
            tenant_id = int(record.get("tenant_id"))
        except (TypeError, ValueError):
            continue
        grouped.setdefault(tenant_id, []).append(record)
    return grouped


def _count_forms(projects: list[dict[str, Any]]) -> int:
    form_ids: set[tuple[str, str]] = set()
    for project in projects:
        project_id = str(project.get("id") or "")
        for field in ("draft_schema", "published_schema"):
            schema = project.get(field)
            if not isinstance(schema, dict):
                continue
            for form in schema.get("forms") or []:
                if isinstance(form, dict) and form.get("id"):
                    form_ids.add((project_id, str(form["id"])))
    return len(form_ids)


def _effective_state(subscriptions: list[dict], addons: list[dict]) -> dict[str, Any]:
    entitled = [
        item for item in subscriptions
        if str(item.get("state") or "").strip().lower() in ENTITLED_STATES
    ]
    if len(entitled) > 1:
        return {"state": "ambiguous", "plan_id": None, "source": "canonical", "reason": "multiple_entitled_subscriptions", "capabilities": []}
    if len(entitled) == 1:
        plan_id = str(entitled[0].get("plan_id") or "").strip().lower()
        product = PRODUCTS.get(plan_id)
        if not product or plan_id not in BASE_PLAN_IDS:
            return {"state": "malformed", "plan_id": plan_id or None, "source": "canonical", "reason": "unknown_base_plan", "capabilities": []}
        capabilities = set(product.get("capabilities") or [])
        for addon in addons:
            if str(addon.get("state") or "").strip().lower() != "active":
                continue
            addon_product = PRODUCTS.get(str(addon.get("addon_id") or "").strip().lower())
            if addon_product:
                capabilities.update(addon_product.get("capabilities") or [])
        return {
            "state": str(entitled[0].get("state") or "").lower(),
            "plan_id": plan_id,
            "source": "canonical",
            "reason": "single_entitled_subscription",
            "capabilities": sorted(capabilities),
        }
    return {
        "state": "inactive" if subscriptions else "missing",
        "plan_id": None,
        "source": "canonical" if subscriptions else "missing_canonical_subscription",
        "reason": "no_entitled_subscription",
        "capabilities": [],
    }


def _usage_capabilities(usage: dict[str, int]) -> list[str]:
    capabilities: set[str] = set()
    if usage["forms"] or usage["form_submissions"] or usage["quiz_attempts"]:
        capabilities.update({"forms", "public_form_links", "response_management"})
    if usage["builder_projects"] or usage["published_sites"] or usage["builder_assets"]:
        capabilities.update({"page_builder", "website_publish", "image_uploads"})
    if usage["datasets"] or usage["generated_artifacts"]:
        capabilities.update({"data_import", "standard_data_analysis"})
    if usage["reservations"]:
        capabilities.update({"reservations", "reservation_management"})
    if usage["calendars"] or usage["calendar_connections"]:
        capabilities.add("internal_calendar")
    if usage["ai_usage_records"]:
        capabilities.add("ai_analytics")
    return sorted(capabilities)


def _suggest_mapping(usage_capabilities: list[str], subscriptions: list[dict]) -> dict[str, str | bool]:
    if any(str(row.get("state") or "").lower() in ENTITLED_STATES for row in subscriptions):
        return {"mapping": "existing canonical state", "confidence": "high", "human_approval_needed": False}
    used = set(usage_capabilities)
    if not used:
        return {"mapping": "inactive or trial candidate", "confidence": "low", "human_approval_needed": True}
    if used & {"reservations", "reservation_management", "internal_calendar"}:
        candidate = "business_plus candidate"
    elif used & {"data_import", "standard_data_analysis"} and used & {"page_builder", "website_publish"}:
        candidate = "business candidate"
    elif used & {"page_builder", "website_publish", "image_uploads"}:
        candidate = "website candidate"
    elif used & {"forms", "public_form_links", "response_management"}:
        candidate = "forms candidate"
    else:
        candidate = "unknown"
    return {"mapping": candidate, "confidence": "usage-derived-only", "human_approval_needed": True}


def build_report(*, include_names: bool = False) -> dict:
    tenants = rows("tenants", "tenant_id,brand_name,owner_name,created_at")
    table_specs = {
        "subscriptions": ("tenant_subscriptions", "tenant_id,id,plan_id,state,catalog_version,source,period_start,period_end,updated_at"),
        "addons": ("tenant_addons", "tenant_id,id,addon_id,state,quantity,catalog_version,updated_at"),
        "legacy": ("features", "tenant_id,id,subscription_type,plan,builder_type,payment_status,updated_at"),
        "projects": ("builder_projects", "tenant_id,id,status,draft_schema,published_schema"),
        "memberships": ("tenant_memberships", "tenant_id,id,status"),
        "storage": ("storage_objects", "tenant_id,id,category,size_bytes,status"),
        "builder_assets": ("builder_assets", "tenant_id,id,status"),
        "form_submissions": ("builder_form_submissions", "tenant_id,id"),
        "quiz_attempts": ("public_quiz_attempts", "tenant_id,id"),
        "reservations": ("builder_reservations", "tenant_id,id"),
        "calendars": ("calendars", "tenant_id,id"),
        "calendar_connections": ("calendar_sync_connections", "tenant_id,id,status"),
        "ai_usage": ("ai_usage_daily", "tenant_id,id"),
        "commercial_usage": ("commercial_usage_monthly", "tenant_id,period_key,forms_created,form_submissions,reservation_requests"),
        "website_settings": ("website_settings", "tenant_id,id,published_project_id,branded_subdomain_commercial_status"),
    }
    grouped: dict[str, dict[int, list[dict]]] = {}
    lookup_failures: dict[str, str] = {}
    for key, (table, columns) in table_specs.items():
        records, error = optional_all_rows(table, columns)
        grouped[key] = by_tenant(records)
        if error:
            lookup_failures[key] = f"{table}:{error}"
    report = []
    for tenant in sorted(tenants, key=lambda item: int(item["tenant_id"])):
        tenant_id = int(tenant["tenant_id"])
        subscriptions = grouped["subscriptions"].get(tenant_id, [])
        addons = grouped["addons"].get(tenant_id, [])
        legacy = grouped["legacy"].get(tenant_id, [])
        projects = grouped["projects"].get(tenant_id, [])
        evidence = {key: values.get(tenant_id, []) for key, values in grouped.items()}
        lookup_errors = list(lookup_failures.values())
        storage = evidence["storage"]
        usage = {
            "active_users": sum(str(row.get("status") or "") == "active" for row in evidence["memberships"]),
            "storage_bytes": sum(int(row.get("size_bytes") or 0) for row in storage if row.get("status") == "active"),
            "storage_objects": sum(row.get("status") == "active" for row in storage),
            "builder_projects": len(projects),
            "published_sites": sum(bool(row.get("published_project_id")) for row in evidence["website_settings"]),
            "forms": _count_forms(projects),
            "form_submissions": len(evidence["form_submissions"]),
            "quiz_attempts": len(evidence["quiz_attempts"]),
            "reservations": len(evidence["reservations"]),
            "builder_assets": len(evidence["builder_assets"]),
            "datasets": sum(row.get("category") == "dataset" and row.get("status") == "active" for row in storage),
            "generated_artifacts": sum(row.get("category") == "generated_artifact" and row.get("status") == "active" for row in storage),
            "calendars": len(evidence["calendars"]),
            "calendar_connections": len(evidence["calendar_connections"]),
            "ai_usage_records": len(evidence["ai_usage"]),
        }
        capabilities_in_use = _usage_capabilities(usage)
        effective = _effective_state(subscriptions, addons)
        suggestion = _suggest_mapping(capabilities_in_use, subscriptions)
        branded = [
            row.get("branded_subdomain_commercial_status")
            for row in evidence["website_settings"]
            if row.get("branded_subdomain_commercial_status") not in {None, "not_applicable"}
        ]
        tenant_record: dict[str, Any] = {
            "tenant_id": tenant_id,
            "tenant_label": f"tenant-{tenant_id}",
            "tenant_name_hash": hashlib.sha256(str(tenant.get("brand_name") or "").strip().lower().encode()).hexdigest() if tenant.get("brand_name") else None,
            "created_at": tenant.get("created_at"),
            "canonical_subscriptions": subscriptions,
            "canonical_addons": addons,
            "legacy_features": legacy,
            "explicit_hosted_address_states": sorted(set(str(item) for item in branded)),
            "observed_usage": usage,
            "capabilities_in_use": capabilities_in_use,
            "effective_entitlement": effective,
            "suggested_mapping": suggestion,
            "lookup_errors": sorted(set(lookup_errors)),
        }
        if include_names:
            tenant_record["tenant_display_name"] = tenant.get("brand_name")
        report.append(tenant_record)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_select_only",
        "names_included": bool(include_names),
        "tenant_count": len(report),
        "tenants": report,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Optional new JSON output path")
    parser.add_argument("--include-names", action="store_true", help="Include tenant display names")
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON")
    args = parser.parse_args()
    payload = json.dumps(
        build_report(include_names=args.include_names),
        indent=None if args.compact else 2,
        separators=(",", ":") if args.compact else None,
        sort_keys=True,
    )
    if args.output:
        with open(args.output, "x", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

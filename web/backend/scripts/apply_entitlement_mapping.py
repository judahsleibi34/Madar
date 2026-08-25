#!/usr/bin/env python3
"""Dry-run-first application of an operator-approved entitlement mapping."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from database import service_supabase
from services.commercial_catalog import ADD_ON_IDS, BASE_PLAN_IDS


TARGET_STATES = {"active", "trial", "grace", "grandfathered", "inactive"}


class MappingValidationError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict) or not isinstance(value.get("tenants"), list):
        raise MappingValidationError("mapping document must contain a tenants array")
    return value


def validate_mapping(document: dict[str, Any], existing_tenant_ids: set[int]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    seen: set[int] = set()
    for index, raw in enumerate(document.get("tenants") or []):
        if not isinstance(raw, dict):
            raise MappingValidationError(f"mapping record {index} must be an object")
        try:
            tenant_id = int(raw.get("tenant_id"))
        except (TypeError, ValueError) as error:
            raise MappingValidationError(f"mapping record {index} has invalid tenant_id") from error
        if tenant_id in seen:
            raise MappingValidationError(f"duplicate tenant mapping: {tenant_id}")
        if tenant_id not in existing_tenant_ids:
            raise MappingValidationError(f"unknown tenant mapping: {tenant_id}")
        seen.add(tenant_id)
        state = str(raw.get("target_state") or "").strip().lower()
        if state not in TARGET_STATES:
            raise MappingValidationError(f"tenant {tenant_id} has invalid target_state")
        plan_id = str(raw.get("plan_id") or "").strip().lower() or None
        if state != "inactive" and plan_id not in BASE_PLAN_IDS:
            raise MappingValidationError(f"tenant {tenant_id} requires a valid base plan")
        if state == "inactive" and plan_id is not None:
            raise MappingValidationError(f"inactive tenant {tenant_id} must not specify a plan")
        if state in {"grace", "grandfathered"} and not raw.get("grace_until"):
            raise MappingValidationError(f"tenant {tenant_id} requires grace_until")
        if state == "grandfathered" and not str(raw.get("grandfather_reason") or "").strip():
            raise MappingValidationError(f"tenant {tenant_id} requires grandfather_reason")
        if not str(raw.get("approved_by") or "").strip() or not raw.get("approved_at"):
            raise MappingValidationError(f"tenant {tenant_id} lacks approval evidence")
        mapping_id = str(raw.get("mapping_id") or "").strip()
        if not mapping_id or len(mapping_id) > 120:
            raise MappingValidationError(f"tenant {tenant_id} requires a bounded mapping_id")
        addons = raw.get("addons") or []
        if not isinstance(addons, list):
            raise MappingValidationError(f"tenant {tenant_id} addons must be an array")
        normalized_addons: list[dict[str, Any]] = []
        addon_ids: set[str] = set()
        for addon in addons:
            if not isinstance(addon, dict):
                raise MappingValidationError(f"tenant {tenant_id} has invalid addon")
            addon_id = str(addon.get("addon_id") or "").strip().lower()
            if addon_id not in ADD_ON_IDS or addon_id in addon_ids:
                raise MappingValidationError(f"tenant {tenant_id} has invalid or duplicate addon")
            addon_ids.add(addon_id)
            try:
                quantity = int(addon.get("quantity") or 1)
            except (TypeError, ValueError) as error:
                raise MappingValidationError(f"tenant {tenant_id} has invalid addon quantity") from error
            if not 1 <= quantity <= 1000:
                raise MappingValidationError(f"tenant {tenant_id} has invalid addon quantity")
            normalized_addons.append({"addon_id": addon_id, "quantity": quantity})
        validated.append({
            "tenant_id": tenant_id,
            "target_state": state,
            "plan_id": plan_id,
            "grace_until": raw.get("grace_until"),
            "grandfather_reason": str(raw.get("grandfather_reason") or "")[:500] or None,
            "approved_by": str(raw["approved_by"])[:120],
            "approved_at": raw["approved_at"],
            "notes": str(raw.get("notes") or "")[:1000] or None,
            "mapping_id": mapping_id,
            "addons": normalized_addons,
        })
    if seen != existing_tenant_ids:
        missing = sorted(existing_tenant_ids - seen)
        raise MappingValidationError(f"mapping is incomplete; missing tenant ids: {missing}")
    return validated


def current_tenant_ids() -> set[int]:
    response = service_supabase.table("tenants").select("tenant_id").limit(10000).execute()
    return {int(row["tenant_id"]) for row in (response.data or [])}


def before_summary(tenant_ids: set[int]) -> dict[str, int]:
    response = service_supabase.table("tenant_subscriptions").select("tenant_id,state").in_("tenant_id", sorted(tenant_ids)).limit(10000).execute()
    records = response.data or []
    return {
        "tenants": len(tenant_ids),
        "subscription_rows": len(records),
        "entitled_rows": sum(str(row.get("state") or "").lower() in {"active", "trial", "grace"} for row in records),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mapping", type=Path)
    parser.add_argument("--apply", action="store_true", help="Apply through the transaction-scoped RPC")
    args = parser.parse_args()
    tenant_ids = current_tenant_ids()
    mappings = validate_mapping(_load(args.mapping), tenant_ids)
    before = before_summary(tenant_ids)
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "valid": True, "before": before, "mapping_count": len(mappings)}, sort_keys=True))
        return 0
    response = service_supabase.rpc("apply_tenant_entitlement_mapping_batch", {"p_mappings": mappings}).execute()
    data = response.data[0] if isinstance(response.data, list) and response.data else response.data
    if not isinstance(data, dict) or int(data.get("applied") or 0) != len(mappings):
        raise RuntimeError("entitlement mapping transaction did not confirm every tenant")
    print(json.dumps({"mode": "apply", "before": before, "result": data}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MappingValidationError as error:
        print(json.dumps({"valid": False, "error": str(error)}, sort_keys=True))
        raise SystemExit(2)

"""Manual commercial plan/add-on lifecycle operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from database import service_supabase
from services.api_errors import error_detail
from services.commercial_catalog import CATALOG_VERSION, get_product
from services.entitlement_service import get_tenant_entitlements


def _rows(response: Any) -> list[dict[str, Any]]:
    return [
        row for row in (getattr(response, "data", None) or [])
        if isinstance(row, dict)
    ]


def _require_product(product_id: str, expected_type: str | None = None) -> dict[str, Any]:
    product = get_product(product_id)
    if not product or (expected_type and product.get("type") != expected_type):
        raise HTTPException(status_code=400, detail="Unknown commercial product.")
    return product


def request_plan(*, tenant_id: int, user_id: int, plan_id: str) -> dict[str, Any]:
    product = _require_product(plan_id, "base_plan")
    now = datetime.now(timezone.utc).isoformat()
    existing = _rows(
        service_supabase.table("tenant_subscriptions")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("plan_id", plan_id)
        .in_("state", ["requested", "pending_review"])
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    if existing:
        return existing[0]
    result = service_supabase.table("tenant_subscriptions").insert(
        {
            "tenant_id": tenant_id,
            "plan_id": plan_id,
            "state": "pending_review",
            "catalog_version": CATALOG_VERSION,
            "currency": product["currency"],
            "price_minor": product["price_minor"],
            "billing_interval": product["billing_interval"],
            "source": "customer_request",
            "requested_by_user_id": user_id,
            "migration_provenance": {"request": "public_manual_activation"},
            "updated_at": now,
        }
    ).execute()
    rows = _rows(result)
    return rows[0] if rows else {}


def request_addon(
    *,
    tenant_id: int,
    user_id: int,
    addon_id: str,
    quantity: int,
    idempotency_key: str,
) -> dict[str, Any]:
    product = _require_product(addon_id)
    if product.get("coming_soon") or not product.get("publicly_available"):
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "addon_unavailable",
                "This add-on is not currently available for activation.",
            ),
        )
    required = product.get("requires_capability")
    state = get_tenant_entitlements(tenant_id)
    if required and required not in set(state["capabilities"]):
        raise HTTPException(
            status_code=402,
            detail=error_detail(
                "base_plan_required",
                "This add-on requires an eligible active base plan.",
                context={"required_capability": required},
            ),
        )
    existing = _rows(
        service_supabase.table("billing_addon_requests")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("idempotency_key", idempotency_key)
        .limit(1)
        .execute()
    )
    if existing:
        row = existing[0]
        if row.get("addon_id") != addon_id or int(row.get("quantity") or 0) != quantity:
            raise HTTPException(status_code=409, detail="Idempotency key was used for another request.")
        return row
    result = service_supabase.table("billing_addon_requests").insert(
        {
            "tenant_id": tenant_id,
            "addon_id": addon_id,
            "quantity": quantity,
            "state": "pending_review",
            "catalog_version": CATALOG_VERSION,
            "idempotency_key": idempotency_key,
            "requested_by_user_id": user_id,
        }
    ).execute()
    rows = _rows(result)
    return rows[0] if rows else {}


def assign_plan(
    *,
    tenant_id: int,
    plan_id: str,
    state: str,
    admin_user_id: int,
    reason: str,
    idempotency_key: str,
) -> dict[str, Any]:
    from services.commercial_access_service import read_commercial_snapshot
    if read_commercial_snapshot(tenant_id) is not None:
        raise HTTPException(status_code=409, detail={"code": "commercial_ledger_required", "message": "Use the reviewed commercial access workflow to record a payment or grant."})
    product = _require_product(plan_id, "base_plan")
    response = service_supabase.rpc(
        "assign_commercial_subscription",
        {
            "p_tenant_id": tenant_id,
            "p_plan_id": plan_id,
            "p_state": state,
            "p_catalog_version": CATALOG_VERSION,
            "p_price_minor": product["price_minor"],
            "p_admin_user_id": admin_user_id,
            "p_reason": reason,
            "p_idempotency_key": idempotency_key,
        },
    ).execute()
    rows = _rows(response)
    if state == "active":
        from services.storage_quota_service import sync_tenant_storage_quota

        sync_tenant_storage_quota(tenant_id)
    return rows[0] if rows else {}


def assign_addon(
    *,
    tenant_id: int,
    addon_id: str,
    quantity: int,
    state: str,
    admin_user_id: int,
    reason: str,
    idempotency_key: str,
) -> dict[str, Any]:
    product = _require_product(addon_id)
    if (
        product.get("coming_soon")
        and not product.get("administratively_assignable")
        and state == "active"
    ):
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "addon_unavailable",
                "Coming-soon add-ons cannot be activated.",
            ),
        )
    required = product.get("requires_capability")
    if state == "active" and required:
        entitlements = get_tenant_entitlements(tenant_id)
        if required not in set(entitlements["capabilities"]):
            raise HTTPException(status_code=402, detail="The tenant base plan is not eligible for this add-on.")
    response = service_supabase.rpc(
        "assign_commercial_addon",
        {
            "p_tenant_id": tenant_id,
            "p_addon_id": addon_id,
            "p_quantity": quantity,
            "p_state": state,
            "p_catalog_version": CATALOG_VERSION,
            "p_price_minor": product.get("price_minor"),
            "p_billing_interval": product["billing_interval"],
            "p_admin_user_id": admin_user_id,
            "p_reason": reason,
            "p_idempotency_key": idempotency_key,
        },
    ).execute()
    rows = _rows(response)
    if addon_id == "additional_storage_5gb":
        from services.storage_quota_service import sync_tenant_storage_quota

        sync_tenant_storage_quota(tenant_id)
    return rows[0] if rows else {}


def allocate_tokens(
    *,
    tenant_id: int,
    product_id: str,
    quantity: int,
    period_key: str,
    admin_user_id: int,
    reason: str,
    idempotency_key: str,
    allocation_type: str = "token_pack",
    explicit_standard_tokens: int | None = None,
) -> dict[str, Any]:
    product = _require_product(product_id) if explicit_standard_tokens is None else None
    tokens = (
        int(explicit_standard_tokens)
        if explicit_standard_tokens is not None
        else int((product or {}).get("allowances", {}).get("standard_tokens") or 0) * quantity
    )
    payload = {
        "tenant_id": tenant_id,
        "period_key": period_key,
        "allocation_type": allocation_type,
        "product_id": product_id,
        "standard_tokens": tokens,
        "state": "active",
        "idempotency_key": idempotency_key,
        "assigned_by_user_id": admin_user_id,
        "reason": reason,
    }
    response = service_supabase.table("ai_token_allocations").upsert(
        payload,
        on_conflict="tenant_id,idempotency_key",
    ).execute()
    rows = _rows(response)
    return rows[0] if rows else payload

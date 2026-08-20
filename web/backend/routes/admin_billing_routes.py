from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from classes import (
    AdminBillingUpdateRequest,
    AdminCommercialAddonUpdate,
    AdminCommercialPlanUpdate,
    AdminTokenAdjustmentRequest,
    AdminTokenAllocationRequest,
)
from services.audit_service import record_audit_event
from services.auth_service import require_system_admin
from services.billing_service import apply_verified_billing_update
from services.commercial_billing_service import (
    allocate_tokens,
    assign_addon,
    assign_plan,
)
from services.entitlement_service import (
    get_operational_usage,
    get_tenant_entitlements,
    get_workspace_seat_capacity,
    get_workspace_seat_usage,
)
from database import service_supabase


router = APIRouter(prefix="/admin/billing", tags=["Admin Billing"])


class AdminSubdomainGrandfatherRequest(BaseModel):
    tenant_id: int
    enabled: bool = True
    reason: str = Field(..., min_length=3, max_length=500)


def _admin(request: Request, response: Response):
    return require_system_admin(request, response, require_aal2=True)[1]


@router.post("/subscriptions")
def assign_canonical_plan(
    update: AdminCommercialPlanUpdate,
    request: Request,
    response: Response,
):
    admin_user = _admin(request, response)
    record = assign_plan(
        tenant_id=update.tenant_id,
        plan_id=update.plan_id,
        state=update.state,
        admin_user_id=admin_user["id"],
        reason=update.reason,
        idempotency_key=update.idempotency_key,
    )
    record_audit_event(
        request=request,
        tenant_id=update.tenant_id,
        actor_user_id=admin_user["id"],
        action="admin.commercial_plan_assigned",
        target_type="tenant_subscription",
        target_id=record.get("id") or update.tenant_id,
        metadata={
            "plan_id": update.plan_id,
            "state": update.state,
            "reason": update.reason,
        },
    )
    return {"success": True, "subscription": record}


@router.post("/addons")
def assign_canonical_addon(
    update: AdminCommercialAddonUpdate,
    request: Request,
    response: Response,
):
    admin_user = _admin(request, response)
    record = assign_addon(
        tenant_id=update.tenant_id,
        addon_id=update.addon_id,
        quantity=update.quantity,
        state=update.state,
        admin_user_id=admin_user["id"],
        reason=update.reason,
        idempotency_key=update.idempotency_key,
    )
    record_audit_event(
        request=request,
        tenant_id=update.tenant_id,
        actor_user_id=admin_user["id"],
        action="admin.commercial_addon_assigned",
        target_type="tenant_addon",
        target_id=record.get("id") or update.tenant_id,
        metadata={
            "addon_id": update.addon_id,
            "quantity": update.quantity,
            "state": update.state,
            "reason": update.reason,
        },
    )
    return {"success": True, "addon": record}


@router.post("/token-packs")
def allocate_token_pack(
    update: AdminTokenAllocationRequest,
    request: Request,
    response: Response,
):
    admin_user = _admin(request, response)
    record = allocate_tokens(
        tenant_id=update.tenant_id,
        product_id=update.product_id,
        quantity=update.quantity,
        period_key=update.period_key,
        admin_user_id=admin_user["id"],
        reason=update.reason,
        idempotency_key=update.idempotency_key,
    )
    record_audit_event(
        request=request,
        tenant_id=update.tenant_id,
        actor_user_id=admin_user["id"],
        action="admin.ai_token_pack_allocated",
        target_type="ai_token_allocation",
        target_id=record.get("id") or update.tenant_id,
        metadata={
            "product_id": update.product_id,
            "quantity": update.quantity,
            "period_key": update.period_key,
            "reason": update.reason,
        },
    )
    return {"success": True, "allocation": record}


@router.post("/token-adjustments")
def adjust_token_balance(
    update: AdminTokenAdjustmentRequest,
    request: Request,
    response: Response,
):
    admin_user = _admin(request, response)
    record = allocate_tokens(
        tenant_id=update.tenant_id,
        product_id="admin_adjustment",
        quantity=1,
        period_key=update.period_key,
        admin_user_id=admin_user["id"],
        reason=update.reason,
        idempotency_key=update.idempotency_key,
        allocation_type="admin_adjustment",
        explicit_standard_tokens=update.standard_tokens,
    )
    record_audit_event(
        request=request,
        tenant_id=update.tenant_id,
        actor_user_id=admin_user["id"],
        action="admin.ai_token_balance_adjusted",
        target_type="ai_token_allocation",
        target_id=record.get("id") or update.tenant_id,
        metadata={
            "standard_tokens": update.standard_tokens,
            "period_key": update.period_key,
            "reason": update.reason,
        },
    )
    return {"success": True, "allocation": record}


@router.post("/subdomain-grandfathering")
def set_subdomain_grandfathering(
    update: AdminSubdomainGrandfatherRequest,
    request: Request,
    response: Response,
):
    admin_user = _admin(request, response)
    result = (
        service_supabase.table("website_settings")
        .update(
            {
                "branded_subdomain_commercial_status": (
                    "grandfathered" if update.enabled else "removed"
                ),
                "branded_subdomain_reviewed_at": datetime.now(timezone.utc).isoformat(),
                "branded_subdomain_reviewed_by_user_id": admin_user["id"],
                "branded_subdomain_review_reason": update.reason,
            }
        )
        .eq("tenant_id", update.tenant_id)
        .execute()
    )
    rows = getattr(result, "data", None) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Website settings were not found.")
    (
        service_supabase.table("hosted_address_migration_reviews")
        .update(
            {
                "commercial_review_state": (
                    "grandfathered" if update.enabled else "removed"
                ),
                "review_reason": update.reason,
                "resolved_by_user_id": admin_user["id"],
                "resolved_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("website_settings_id", rows[0]["id"])
        .execute()
    )
    record_audit_event(
        request=request,
        tenant_id=update.tenant_id,
        actor_user_id=admin_user["id"],
        action="admin.branded_subdomain_grandfathering_updated",
        target_type="website_settings",
        target_id=rows[0].get("id") or update.tenant_id,
        metadata={"enabled": update.enabled, "reason": update.reason},
    )
    return {"success": True, "website": rows[0]}


@router.get("/tenants/{tenant_id}/commercial-state")
def inspect_commercial_state(
    tenant_id: int,
    request: Request,
    response: Response,
):
    _admin(request, response)
    from data_analysis.ai.token_metering import get_token_summary
    from services.storage_quota_service import get_tenant_storage_usage

    review = getattr(
        service_supabase.table("legacy_billing_migration_reviews")
        .select("*")
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute(),
        "data",
        None,
    ) or []
    return {
        "success": True,
        "entitlements": get_tenant_entitlements(tenant_id),
        "storage": get_tenant_storage_usage(tenant_id),
        "workspace_seats": {
            "capacity": get_workspace_seat_capacity(tenant_id),
            "used": get_workspace_seat_usage(tenant_id),
        },
        "operational_usage": get_operational_usage(tenant_id),
        "ai_tokens": get_token_summary(tenant_id),
        "migration_review": review[0] if review else None,
    }


@router.post("/features")
def update_tenant_feature(
    update: AdminBillingUpdateRequest,
    request: Request,
    response: Response,
):
    _, admin_user = require_system_admin(request, response, require_aal2=True)

    feature = apply_verified_billing_update(
        tenant_id=update.tenant_id,
        subscription_type=update.subscription_type,
        plan=update.plan,
        builder_type=update.builder_type,
        payment_status=update.payment_status,
        source="admin",
        updated_by_user_id=admin_user.get("id"),
    )

    record_audit_event(
        request=request,
        tenant_id=feature.get("tenant_id", update.tenant_id),
        actor_user_id=admin_user.get("id"),
        action="admin.billing_feature_updated",
        target_type="billing_feature",
        target_id=feature.get("id") or update.tenant_id,
        metadata={
            "plan_type": feature.get("subscription_type"),
            "subscription_type": feature.get("subscription_type"),
            "plan": feature.get("plan"),
            "builder_type": feature.get("builder_type"),
            "payment_status": feature.get("payment_status"),
            "source": "admin",
        },
    )

    return {
        "success": True,
        "data": feature,
    }

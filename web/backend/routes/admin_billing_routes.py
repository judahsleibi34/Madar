from datetime import datetime, timezone
from calendar import monthrange
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from classes import (
    AdminBillingUpdateRequest,
    AdminCommercialAddonUpdate,
    AdminCommercialPlanUpdate,
    AdminTokenAdjustmentRequest,
    AdminTokenAllocationRequest,
)
from services.audit_service import record_audit_event
from services.commercial_access_service import apply_commercial_command, resolve_commercial_access
from services.commercial_catalog import CATALOG_VERSION, get_product
from services.observability_service import CORRELATION_ID, correlation_id
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


class CommercialCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(..., ge=1, strict=True)
    idempotency_key: str = Field(..., min_length=16, max_length=128)
    reason: str = Field(..., min_length=3, max_length=1000)
    reference: str | None = Field(default=None, max_length=200)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("A reason is required")
        return value


class CommercialGrantRequest(CommercialCommandRequest):
    plan_id: Literal["forms", "website", "business", "business_plus"]
    valid_from: datetime
    valid_until: datetime
    supersedes_period_id: UUID | None = None

    @model_validator(mode="after")
    def dated_grant(self):
        if self.valid_from.tzinfo is None or self.valid_until.tzinfo is None or self.valid_until <= self.valid_from:
            raise ValueError("A finite ordered access period with timezone is required")
        return self


class CommercialPaymentRequest(CommercialGrantRequest):
    method: Literal["cash", "bank_transfer", "other_manual"]
    actual_minor: int = Field(..., ge=1, le=1000000000000, strict=True)
    billing_months: int = Field(..., ge=1, le=120, strict=True)
    paid_at: datetime
    currency: Literal["USD"] = "USD"
    receipt_reference: str = Field(..., min_length=1, max_length=200)
    override_reason: str | None = Field(default=None, min_length=3, max_length=1000)

    @model_validator(mode="after")
    def payment_evidence(self):
        if self.paid_at.tzinfo is None:
            raise ValueError("Payment time must include timezone")
        offset = self.valid_from.year * 12 + self.valid_from.month - 1 + self.billing_months
        year, month = divmod(offset, 12)
        expected_end = self.valid_from.replace(year=year, month=month + 1,
            day=min(self.valid_from.day, monthrange(year, month + 1)[1]))
        if self.valid_until != expected_end:
            raise ValueError("Paid access dates must match the billing months")
        # The database validates the server quote after durable replay. A
        # catalog price change must not invalidate an identical payment retry.
        if self.override_reason is not None and len(self.override_reason.strip()) < 3:
            raise ValueError("An amount override requires a reason")
        if not self.receipt_reference.strip():
            raise ValueError("A payment reference is required")
        return self


class CommercialRevokeRequest(CommercialCommandRequest):
    period_id: UUID


def _commercial_command(tenant_id: int, payload: CommercialCommandRequest, operation: str,
                        request: Request, response: Response, *, quote=None):
    # Future Billing Admin permission hook: keep this one authorization seam.
    admin = _admin(request, response)
    request_id = CORRELATION_ID.get() or correlation_id(request.headers.get("X-Request-ID"))
    response.headers["X-Request-ID"] = request_id
    command = payload.model_dump(mode="json", exclude_none=True)
    command.pop("idempotency_key")
    result = apply_commercial_command(
        tenant_id=tenant_id, actor_user_id=admin["id"], operation=operation,
        idempotency_key=payload.idempotency_key, request_id=request_id,
        command=command, quote=quote,
    )
    return {"success": True, "commercial_access": result}


@router.get("/tenants/{tenant_id}/access-history")
def inspect_commercial_access_history(tenant_id: int, request: Request, response: Response):
    _admin(request, response)
    state = resolve_commercial_access(tenant_id)
    history = {}
    for key, table in (("events", "commercial_access_events"), ("periods", "commercial_access_periods"),
                       ("payments", "commercial_manual_payments")):
        history[key] = service_supabase.table(table).select("*").eq("tenant_id", tenant_id).order("created_at", desc=True).limit(100).execute().data or []
    return {"success": True, "commercial_access": state, **history}


@router.post("/tenants/{tenant_id}/suspend")
def suspend_commercial_access(tenant_id: int, payload: CommercialCommandRequest, request: Request, response: Response):
    return _commercial_command(tenant_id, payload, "suspend", request, response)


@router.post("/tenants/{tenant_id}/reactivate")
def reactivate_commercial_access(tenant_id: int, payload: CommercialCommandRequest, request: Request, response: Response):
    return _commercial_command(tenant_id, payload, "reactivate", request, response)


@router.post("/tenants/{tenant_id}/manual-payments")
def record_commercial_manual_payment(tenant_id: int, payload: CommercialPaymentRequest, request: Request, response: Response):
    quote = {"expected_minor": get_product(payload.plan_id)["price_minor"] * payload.billing_months,
             "catalog_version": CATALOG_VERSION}
    return _commercial_command(tenant_id, payload, "manual_payment", request, response, quote=quote)


@router.post("/tenants/{tenant_id}/complimentary-access")
def grant_complimentary_access(tenant_id: int, payload: CommercialGrantRequest, request: Request, response: Response):
    return _commercial_command(tenant_id, payload, "complimentary", request, response)


@router.post("/tenants/{tenant_id}/revoke-access")
def revoke_commercial_access(tenant_id: int, payload: CommercialRevokeRequest, request: Request, response: Response):
    return _commercial_command(tenant_id, payload, "revoke", request, response)


class CommercialPaymentCorrectionRequest(CommercialCommandRequest):
    payment_id: UUID
    actual_minor: int = Field(..., ge=1, le=1000000000000, strict=True)
    paid_at: datetime
    receipt_reference: str = Field(..., min_length=1, max_length=200)
    override_reason: str | None = Field(default=None, min_length=3, max_length=1000)

    @model_validator(mode="after")
    def correction_evidence(self):
        if self.paid_at.tzinfo is None or not self.receipt_reference.strip():
            raise ValueError("Dated payment evidence and reference are required")
        if self.override_reason is not None and len(self.override_reason.strip()) < 3:
            raise ValueError("An override requires a reason")
        return self


@router.post("/tenants/{tenant_id}/correct-payment")
def correct_commercial_manual_payment(tenant_id: int, payload: CommercialPaymentCorrectionRequest, request: Request, response: Response):
    return _commercial_command(tenant_id, payload, "correct_payment", request, response)


@router.post("/tenants/{tenant_id}/review-inactive")
def review_inactive_commercial_access(tenant_id: int, payload: CommercialCommandRequest, request: Request, response: Response):
    return _commercial_command(tenant_id, payload, "review_inactive", request, response)

import os
import secrets
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from classes import (
    BillingCheckoutRequest,
    BillingWebhookUpdateRequest,
    CommercialAddonRequest,
    CommercialPlanRequest,
)
from services.api_errors import error_detail
from services.audit_service import record_audit_event
from services.tenant_service import TenantContext, require_active_tenant_member
from services.billing_service import (
    apply_billing_webhook_event,
    apply_pending_checkout_selection,
    get_current_billing_state,
)
from services.commercial_billing_service import request_addon, request_plan
from services.commercial_catalog import get_catalog
from services.commercial_access_service import resolve_commercial_access
from services.entitlement_service import (
    get_operational_usage,
    get_tenant_entitlements,
    get_workspace_seat_capacity,
    get_workspace_seat_usage,
)
from database import service_supabase


router = APIRouter(tags=["Billing"])


@router.get("/billing/catalog")
def billing_catalog(response: Response):
    response.headers["Cache-Control"] = "no-store"
    catalog = get_catalog(public_only=True)
    catalog["price_book"] = None
    try:
        rows = (
            service_supabase.table("commercial_price_books")
            .select(
                "id,version,effective_from,currency,billing_interval,"
                "standalone_minor,bundle_minor,sales_start_at,sales_end_at"
            )
            .eq("id", catalog["price_book_id"])
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows:
            book = rows[0]
            now = datetime.now(timezone.utc)
            start = book.get("sales_start_at")
            end = book.get("sales_end_at")
            starts_at = datetime.fromisoformat(start.replace("Z", "+00:00")) if start else None
            ends_at = datetime.fromisoformat(end.replace("Z", "+00:00")) if end else None
            book["new_sales_active"] = bool(
                starts_at and starts_at <= now and (ends_at is None or ends_at > now)
            )
            catalog["price_book"] = book
    except Exception:
        # Public clients must fail closed instead of falling back to duplicated
        # or stale frontend prices when the commercial catalog is unavailable.
        pass
    return {"success": True, "catalog": catalog}


def _commercial_context(request: Request, response: Response) -> TenantContext:
    return require_active_tenant_member(
        request,
        response,
        allow_admin_account_access=False,
    )


@router.get("/billing/entitlements")
def current_entitlements(request: Request, response: Response):
    context = _commercial_context(request, response)
    return {
        "success": True,
        "entitlements": get_tenant_entitlements(context.tenant_id),
    }


@router.get("/billing/current-plan")
def current_commercial_plan(request: Request, response: Response):
    context = _commercial_context(request, response)
    entitlements = get_tenant_entitlements(context.tenant_id)
    return {
        "success": True,
        "plan": entitlements.get("assigned_subscription") or entitlements.get("subscription"),
        "plan_id": entitlements.get("assigned_plan_id") or entitlements.get("plan_id"),
        "assigned_modules": entitlements.get("assigned_modules", []),
        "module_commercial_basis": entitlements.get("module_commercial_basis"),
        "pricing": entitlements.get("pricing"),
        "commercial_access_state": entitlements.get("commercial_access_state"),
        "commercial_denial_code": entitlements.get("commercial_denial_code"),
        "commercial_revision": entitlements.get("commercial_revision"),
        "access_period": entitlements.get("access_period"),
        "paid_through": (entitlements.get("access_period") or {}).get("valid_until"),
        "next_transition_at": entitlements.get("next_transition_at"),
        "effective_at": entitlements.get("effective_at"),
        "commercial_suspended_at": entitlements.get("commercial_suspended_at"),
        "protection_contract_version": entitlements.get("protection_contract_version"),
        "protection_policy": entitlements.get("protection_policy"),
        "state": (
            (entitlements.get("assigned_subscription") or entitlements.get("subscription") or {}).get("state")
            or ("review_required" if entitlements.get("review_required") else "legacy")
        ),
        "source": entitlements.get("source"),
        "review_required": entitlements.get("review_required", False),
    }


class CustomerModuleQuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    module_ids: list[Literal["forms", "website", "ecommerce"]] = Field(
        ..., min_length=1, max_length=3
    )

    @model_validator(mode="after")
    def unique_modules(self):
        if len(self.module_ids) != len(set(self.module_ids)):
            raise ValueError("Unique modules are required")
        return self


@router.post("/billing/module-quote")
def customer_module_quote(
    selection: CustomerModuleQuoteRequest,
    request: Request,
    response: Response,
):
    """Return a ledger-authoritative quote for the signed-in tenant.

    This endpoint is deliberately read-only. Subscription changes remain in
    the existing reviewed commercial workflow.
    """
    context = _commercial_context(request, response)
    state = resolve_commercial_access(context.tenant_id)
    if (
        state.get("protection_contract_version") != 145
        or state.get("protection_policy") != "strict_paid_continuity_v1"
    ):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "commercial_protection_upgrade_required",
                "message": "Subscription quoting is temporarily unavailable.",
            },
        )
    try:
        quote = service_supabase.rpc(
            "quote_commercial_modules",
            {
                "p_tenant_id": context.tenant_id,
                "r": {"module_ids": selection.module_ids, "price_books": {}},
            },
        ).execute().data
        pricing = quote.get("pricing") if isinstance(quote, dict) else None
        if (
            not isinstance(quote, dict)
            or not isinstance(quote.get("revision"), int)
            or isinstance(quote.get("revision"), bool)
            or not isinstance(quote.get("module_basis"), dict)
            or set(quote.get("module_basis") or {}) != set(selection.module_ids)
            or not isinstance(pricing, dict)
            or pricing.get("module_ids") != sorted(selection.module_ids)
            or not isinstance(pricing.get("recurring_minor"), int)
            or isinstance(pricing.get("recurring_minor"), bool)
        ):
            raise ValueError("invalid_quote")
        response.headers["Cache-Control"] = "no-store"
        return {"success": True, "quote": quote}
    except HTTPException:
        raise
    except Exception as error:
        if getattr(error, "code", None) in {"22023", "P0002"}:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "commercial_price_book_unavailable",
                    "message": "No eligible price book is available for this module selection.",
                },
            ) from error
        raise HTTPException(
            status_code=503,
            detail={
                "code": "commercial_dependency_unavailable",
                "message": "Subscription quoting is temporarily unavailable.",
            },
        ) from error


@router.get("/billing/add-ons")
def current_addons(request: Request, response: Response):
    context = _commercial_context(request, response)
    entitlements = get_tenant_entitlements(context.tenant_id)
    catalog = get_catalog(public_only=True)
    return {
        "success": True,
        "active": entitlements.get("active_addons", []),
        "available": [
            product for product in catalog["products"]
            if product.get("type") in {"add_on", "token_pack"}
        ],
    }


@router.get("/billing/usage")
def current_usage(request: Request, response: Response):
    context = _commercial_context(request, response)
    from data_analysis.ai.token_metering import get_token_summary
    from services.storage_quota_service import get_tenant_storage_usage

    return {
        "success": True,
        "storage": get_tenant_storage_usage(context.tenant_id),
        "workspace_seats": {
            "included_and_added": get_workspace_seat_capacity(context.tenant_id),
            "used": get_workspace_seat_usage(context.tenant_id),
        },
        "operations": get_operational_usage(context.tenant_id),
        "ai_tokens": get_token_summary(context.tenant_id),
    }


@router.post("/billing/plan-request")
def create_plan_request(
    selection: CommercialPlanRequest,
    request: Request,
    response: Response,
):
    context = _commercial_context(request, response)
    record = request_plan(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        plan_id=selection.plan_id,
    )
    record_audit_event(
        request=request,
        tenant_id=context.tenant_id,
        actor_user_id=context.user_id,
        action="billing.plan_requested",
        target_type="tenant_subscription",
        target_id=record.get("id") or context.tenant_id,
        metadata={"plan_id": selection.plan_id, "state": "pending_review"},
    )
    return {
        "success": True,
        "request_status": "pending_manual_activation",
        "message": "Your plan request was saved for manual review. No payment was taken.",
        "plan_request": record,
    }


@router.post("/billing/add-on-request")
def create_addon_request(
    selection: CommercialAddonRequest,
    request: Request,
    response: Response,
):
    context = _commercial_context(request, response)
    record = request_addon(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        addon_id=selection.addon_id,
        quantity=selection.quantity,
        idempotency_key=selection.idempotency_key,
    )
    record_audit_event(
        request=request,
        tenant_id=context.tenant_id,
        actor_user_id=context.user_id,
        action="billing.addon_requested",
        target_type="billing_addon_request",
        target_id=record.get("id") or context.tenant_id,
        metadata={
            "addon_id": selection.addon_id,
            "quantity": selection.quantity,
            "state": "pending_review",
        },
    )
    return {
        "success": True,
        "request_status": "pending_manual_activation",
        "message": "Your add-on request was saved for manual review. No payment was taken.",
        "addon_request": record,
    }


def assert_context_user(context: TenantContext, user_id: int | str | None) -> None:
    if user_id is None:
        return

    try:
        if int(context.user_id) != int(user_id):
            raise ValueError
    except (TypeError, ValueError):
        raise HTTPException(status_code=403, detail="User id does not match session")


def build_checkout_response(
    checkout: BillingCheckoutRequest,
    context: TenantContext,
    request: Request | None = None,
):
    tenant_id = context.tenant_id
    user_id = context.user_id

    feature = apply_pending_checkout_selection(
        tenant_id=tenant_id,
        subscription_type=checkout.subscription_type,
        plan=checkout.plan,
        builder_type=checkout.builder_type,
        updated_by_user_id=user_id,
    )

    record_audit_event(
        request=request,
        tenant_id=feature.get("tenant_id", tenant_id),
        actor_user_id=user_id,
        action="billing.checkout_selected",
        target_type="billing_selection",
        target_id=feature.get("id") or tenant_id,
        metadata={
            "plan_type": feature.get("subscription_type"),
            "subscription_type": feature.get("subscription_type"),
            "plan": feature.get("plan"),
            "builder_type": feature.get("builder_type"),
            "selected_features": [feature.get("builder_type")] if feature.get("builder_type") else [feature.get("subscription_type")],
            "payment_status": feature.get("payment_status"),
            "source": "checkout",
        },
    )

    return {
        "success": True,
        "code": "billing_not_configured",
        "checkout_available": False,
        "requires_payment": False,
        "request_status": "pending_manual_activation",
        "message": "Online checkout is not available yet. Your access request was saved for manual review.",
        "checkout": {
            "tenant_id": feature.get("tenant_id", tenant_id),
            "subscription_type": feature.get("subscription_type"),
            "plan": feature.get("plan"),
            "builder_type": feature.get("builder_type"),
            "payment_status": feature.get("payment_status"),
        },
        "data": feature,
    }


@router.post("/billing/checkout")
def create_canonical_checkout(
    checkout: BillingCheckoutRequest,
    request: Request,
    response: Response,
):
    context = require_active_tenant_member(
        request,
        response,
        allow_admin_account_access=False,
    )
    return build_checkout_response(checkout, context, request=request)


@router.get("/billing/current")
def current_billing_state(request: Request, response: Response):
    context = require_active_tenant_member(
        request,
        response,
        allow_admin_account_access=False,
    )
    return {
        "success": True,
        "billing": get_current_billing_state(context.tenant_id),
    }


@router.post("/users/{user_id}/billing/checkout")
def create_checkout(
    user_id: int,
    checkout: BillingCheckoutRequest,
    request: Request,
    response: Response,
):
    context = require_active_tenant_member(
        request,
        response,
        allow_admin_account_access=False,
    )
    assert_context_user(context, user_id)
    return build_checkout_response(checkout, context, request=request)


@router.post("/billing/webhook")
def billing_webhook(
    update: BillingWebhookUpdateRequest,
    x_madar_webhook_secret: str = Header(default=""),
):
    app_env = (
        os.getenv("APP_ENV")
        or os.getenv("ENV")
        or os.getenv("FASTAPI_ENV")
        or "development"
    ).strip().lower()
    expected_secret = os.getenv("BILLING_WEBHOOK_SECRET", "")

    if app_env in {"prod", "production"}:
        raise HTTPException(
            status_code=503,
            detail=error_detail(
                "billing_not_configured",
                "A signed billing provider webhook is not configured.",
            ),
        )

    if not expected_secret:
        raise HTTPException(
            status_code=503,
            detail=error_detail(
                "billing_not_configured",
                "Billing webhook processing is not configured.",
            ),
        )

    if not secrets.compare_digest(x_madar_webhook_secret, expected_secret):
        raise HTTPException(
            status_code=401,
            detail=error_detail(
                "webhook_signature_invalid",
                "Invalid webhook signature.",
            ),
        )

    event_result = apply_billing_webhook_event(
        tenant_id=update.tenant_id,
        subscription_type=update.subscription_type,
        plan=update.plan,
        builder_type=update.builder_type,
        payment_status=update.payment_status,
        provider_event_id=update.provider_event_id,
        provider_occurred_at=update.provider_occurred_at,
    )

    return {
        "success": True,
        "duplicate": event_result.get("duplicate", False),
        "event_id": event_result.get("event_id"),
        "ignored": event_result.get("ignored", False),
        "data": event_result.get("feature"),
    }

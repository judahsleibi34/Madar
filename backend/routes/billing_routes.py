import os
import secrets

from fastapi import APIRouter, Header, HTTPException, Request, Response

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
from services.entitlement_service import (
    get_operational_usage,
    get_tenant_entitlements,
    get_workspace_seat_capacity,
    get_workspace_seat_usage,
)


router = APIRouter(tags=["Billing"])


@router.get("/billing/catalog")
def billing_catalog():
    return {"success": True, "catalog": get_catalog(public_only=True)}


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
        "plan": entitlements.get("subscription"),
        "plan_id": entitlements.get("plan_id"),
        "state": (
            (entitlements.get("subscription") or {}).get("state")
            or ("review_required" if entitlements.get("review_required") else "legacy")
        ),
        "source": entitlements.get("source"),
        "review_required": entitlements.get("review_required", False),
    }


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

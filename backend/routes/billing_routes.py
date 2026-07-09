import os
import secrets

from fastapi import APIRouter, Header, HTTPException, Request, Response

from classes import BillingCheckoutRequest, BillingWebhookUpdateRequest
from services.audit_service import record_audit_event
from services.tenant_service import TenantContext, require_active_tenant_member
from services.billing_service import apply_pending_checkout_selection, apply_verified_billing_update


router = APIRouter(tags=["Billing"])


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
        "requires_payment": True,
        "message": "Checkout request saved. Payment provider integration is not configured yet.",
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
    expected_secret = os.getenv("BILLING_WEBHOOK_SECRET", "")

    if not expected_secret:
        raise HTTPException(status_code=503, detail="Billing webhook is not configured.")

    if not secrets.compare_digest(x_madar_webhook_secret, expected_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    feature = apply_verified_billing_update(
        tenant_id=update.tenant_id,
        subscription_type=update.subscription_type,
        plan=update.plan,
        builder_type=update.builder_type,
        payment_status=update.payment_status,
        source="webhook",
        provider_event_id=update.provider_event_id,
    )

    return {
        "success": True,
        "data": feature,
    }

import os
import secrets

from fastapi import APIRouter, Header, HTTPException, Request, Response

from classes import BillingCheckoutRequest, BillingWebhookUpdateRequest
from services.auth_service import require_regular_user, require_regular_user_id
from services.billing_service import apply_pending_checkout_selection, apply_verified_billing_update


router = APIRouter(tags=["Billing"])


def build_checkout_response(
    checkout: BillingCheckoutRequest,
    user_data: dict,
):
    tenant_id = user_data.get("tenant_id")

    if tenant_id is None:
        raise HTTPException(status_code=400, detail="User does not have a tenant_id.")

    feature = apply_pending_checkout_selection(
        tenant_id=tenant_id,
        subscription_type=checkout.subscription_type,
        plan=checkout.plan,
        builder_type=checkout.builder_type,
        updated_by_user_id=user_data.get("id"),
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
    _, user_data = require_regular_user(request, response)
    return build_checkout_response(checkout, user_data)


@router.post("/users/{user_id}/billing/checkout")
def create_checkout(
    user_id: int,
    checkout: BillingCheckoutRequest,
    request: Request,
    response: Response,
):
    _, user_data = require_regular_user_id(user_id, request, response)
    return build_checkout_response(checkout, user_data)


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

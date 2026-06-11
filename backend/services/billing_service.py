from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from database import service_supabase

logger = logging.getLogger(__name__)


FULL_PLATFORM_PLANS = {"starter", "pro", "business"}
BUILDER_PLANS = {"basic", "premium"}
BUILDER_TYPES = {"website", "forms", "quiz", "reservation", "reports", "data"}
PAYMENT_STATUSES = {"pending", "active", "past_due", "canceled"}


def validate_billing_plan(
    *,
    subscription_type: str,
    plan: str,
    builder_type: str | None = None,
) -> dict[str, str | None]:
    normalized_subscription_type = str(subscription_type or "").strip().lower()
    normalized_plan = str(plan or "").strip().lower()
    normalized_builder_type = (
        str(builder_type).strip().lower()
        if builder_type is not None
        else None
    )

    if normalized_subscription_type == "full_platform":
        if normalized_plan not in FULL_PLATFORM_PLANS:
            raise HTTPException(status_code=400, detail="Invalid full platform plan.")
        if normalized_builder_type is not None:
            raise HTTPException(
                status_code=400,
                detail="builder_type must be null for full platform subscriptions.",
            )

    elif normalized_subscription_type == "individual_builder":
        if normalized_plan not in BUILDER_PLANS:
            raise HTTPException(status_code=400, detail="Invalid builder plan.")
        if normalized_builder_type not in BUILDER_TYPES:
            raise HTTPException(
                status_code=400,
                detail="builder_type is required for individual builder subscriptions.",
            )

    else:
        raise HTTPException(status_code=400, detail="Invalid subscription type.")

    return {
        "subscription_type": normalized_subscription_type,
        "plan": normalized_plan,
        "builder_type": normalized_builder_type,
    }


def get_existing_feature_for_tenant(
    *,
    tenant_id: int | str,
    subscription_type: str,
    builder_type: str | None = None,
) -> dict[str, Any] | None:
    query = (
        service_supabase
        .table("features")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("subscription_type", subscription_type)
    )

    if builder_type is None:
        query = query.is_("builder_type", "null")
    else:
        query = query.eq("builder_type", builder_type)

    result = query.limit(1).execute()
    return result.data[0] if result.data else None


def get_billing_summary_for_tenant(tenant_id: int | str | None) -> dict[str, Any]:
    if tenant_id is None or str(tenant_id).strip() == "":
        return {}

    try:
        result = (
            service_supabase
            .table("features")
            .select("subscription_type, plan, builder_type, payment_status")
            .eq("tenant_id", tenant_id)
            .limit(10)
            .execute()
        )

    except Exception as error:
        logger.warning("billing.summary_failed", extra={"tenant_id": tenant_id, "error_type": type(error).__name__})
        return {}

    features = result.data or []
    active_feature = next(
        (
            feature
            for feature in features
            if feature.get("payment_status") == "active"
        ),
        features[0] if features else None,
    )

    if not active_feature:
        return {}

    return {
        "subscription_type": active_feature.get("subscription_type") or "",
        "payment_status": active_feature.get("payment_status") or "",
        "plan": active_feature.get("plan") or "",
        "builder_type": active_feature.get("builder_type") or "",
        "features": features,
    }


def persist_feature_selection(
    *,
    tenant_id: int | str,
    subscription_type: str,
    plan: str,
    builder_type: str | None = None,
    payment_status: str,
    source: str,
    updated_by_user_id: int | str | None = None,
    provider_event_id: str | None = None,
) -> dict[str, Any]:
    if tenant_id is None or str(tenant_id).strip() == "":
        raise HTTPException(status_code=400, detail="tenant_id is required.")

    normalized = validate_billing_plan(
        subscription_type=subscription_type,
        plan=plan,
        builder_type=builder_type,
    )
    normalized_payment_status = str(payment_status or "").strip().lower()

    if normalized_payment_status not in PAYMENT_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid payment status.")

    payload: dict[str, Any] = {
        "tenant_id": tenant_id,
        "subscription_type": normalized["subscription_type"],
        "plan": normalized["plan"],
        "builder_type": normalized["builder_type"],
        "payment_status": normalized_payment_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _ = provider_event_id

    existing = get_existing_feature_for_tenant(
        tenant_id=tenant_id,
        subscription_type=str(normalized["subscription_type"]),
        builder_type=normalized["builder_type"],
    )

    try:
        if existing:
            result = (
                service_supabase
                .table("features")
                .update(payload)
                .eq("id", existing["id"])
                .eq("tenant_id", tenant_id)
                .execute()
            )
        else:
            result = service_supabase.table("features").insert(payload).execute()

    except Exception as error:
        logger.warning("billing.features_update_failed", extra={"tenant_id": tenant_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=500, detail="Could not apply billing update.")

    feature = result.data[0] if result.data else payload
    logger.info(
        "billing.features_updated",
        extra={
            "tenant_id": tenant_id,
            "subscription_type": payload.get("subscription_type"),
            "plan": payload.get("plan"),
            "builder_type": payload.get("builder_type"),
            "payment_status": payload.get("payment_status"),
            "source": source,
            "updated_by_user_id": updated_by_user_id,
        },
    )
    return feature


def apply_pending_checkout_selection(
    *,
    tenant_id: int | str,
    subscription_type: str,
    plan: str,
    builder_type: str | None = None,
    updated_by_user_id: int | str | None = None,
) -> dict[str, Any]:
    return persist_feature_selection(
        tenant_id=tenant_id,
        subscription_type=subscription_type,
        plan=plan,
        builder_type=builder_type,
        payment_status="pending",
        source="checkout",
        updated_by_user_id=updated_by_user_id,
    )


def apply_verified_billing_update(
    *,
    tenant_id: int | str,
    subscription_type: str,
    plan: str,
    builder_type: str | None = None,
    payment_status: str = "active",
    source: str = "billing",
    updated_by_user_id: int | str | None = None,
    provider_event_id: str | None = None,
) -> dict[str, Any]:
    return persist_feature_selection(
        tenant_id=tenant_id,
        subscription_type=subscription_type,
        plan=plan,
        builder_type=builder_type,
        payment_status=payment_status,
        source=source,
        updated_by_user_id=updated_by_user_id,
        provider_event_id=provider_event_id,
    )

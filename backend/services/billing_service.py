from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from database import service_supabase
from services.api_errors import error_detail

logger = logging.getLogger(__name__)


FULL_PLATFORM_PLANS = {
    "starter",
    "pro",
    "business",
    "cms",
    "forms_data",
    "cms_plus",
    "complete",
}
BUILDER_PLANS = {"basic", "pro", "premium"}
BUILDER_TYPES = {"website", "forms", "quiz", "reservation", "reports", "data"}
PAYMENT_STATUSES = {"pending", "active", "past_due", "canceled", "expired"}
PUBLISH_ENTITLEMENT_BUILDER_TYPES = {"website"}


def _env_enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _beta_publish_tenant_ids() -> set[str]:
    return {
        value.strip()
        for value in os.getenv("PUBLISH_BETA_TENANT_IDS", "").split(",")
        if value.strip()
    }


def is_publish_entitlement_enforced() -> bool:
    """Return the rollout switch dynamically so tests and deployments can override it."""

    return _env_enabled("ENFORCE_PUBLISH_ENTITLEMENT", False)


def require_publish_entitlement(tenant_id: int | str) -> dict[str, Any]:
    """Require an active website/full-platform feature when enforcement is enabled.

    Enforcement defaults off to preserve existing beta tenants. Deployments can turn it
    on globally and still explicitly allow known beta tenants during a staged rollout.
    """

    tenant_key = str(tenant_id or "").strip()
    if not tenant_key:
        raise HTTPException(
            status_code=403,
            detail=error_detail("entitlement_inactive", "A tenant is required to publish."),
        )

    from services.entitlement_service import require_any_entitlement

    return require_any_entitlement(
        tenant_id,
        {"website_publish", "public_form_links"},
        message="An active website or public-form publishing entitlement is required.",
    )


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

    result = query.limit(50).execute()
    features = [item for item in (result.data or []) if isinstance(item, dict)]
    features.sort(
        key=lambda feature: (
            str(feature.get("payment_status") or "").strip().lower() == "active",
            _feature_timestamp(feature),
            str(feature.get("id") or ""),
        ),
        reverse=True,
    )
    return features[0] if features else None


def _feature_timestamp(feature: dict[str, Any]) -> str:
    return str(
        feature.get("billing_state_changed_at")
        or feature.get("updated_at")
        or feature.get("created_at")
        or ""
    )


def _feature_plan_key(feature: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(feature.get("subscription_type") or "").strip().lower(),
        str(feature.get("builder_type") or "").strip().lower(),
        str(feature.get("plan") or "").strip().lower(),
    )


def normalize_current_billing_features(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse historical duplicates into one safe current billing view."""
    safe_fields = {
        "id",
        "subscription_type",
        "plan",
        "builder_type",
        "payment_status",
        "billing_state_changed_at",
        "updated_at",
        "created_at",
    }
    features = [
        {key: feature.get(key) for key in safe_fields if key in feature}
        for feature in rows
        if isinstance(feature, dict)
    ]
    features.sort(
        key=lambda feature: (_feature_timestamp(feature), str(feature.get("id") or "")),
        reverse=True,
    )

    active = next(
        (feature for feature in features if str(feature.get("payment_status") or "").lower() == "active"),
        None,
    )
    pending = next(
        (feature for feature in features if str(feature.get("payment_status") or "").lower() == "pending"),
        None,
    )
    if active and pending and _feature_plan_key(active) == _feature_plan_key(pending):
        pending = None

    selected_ids = {
        str(feature.get("id"))
        for feature in (active, pending)
        if feature and feature.get("id") is not None
    }
    seen_other_states: set[tuple[str, str, str, str]] = set()
    other_states = []
    for feature in features:
        status = str(feature.get("payment_status") or "").strip().lower()
        if status in {"active", "pending"} or str(feature.get("id")) in selected_ids:
            continue
        key = (*_feature_plan_key(feature), status)
        if key in seen_other_states:
            continue
        seen_other_states.add(key)
        other_states.append(feature)

    current = active or pending or (other_states[0] if other_states else None)
    current_features = [feature for feature in (active, pending) if feature] + other_states
    if pending:
        pending = {**pending, "requested_at": _feature_timestamp(pending)}

    return {
        "state": str((current or {}).get("payment_status") or "none"),
        "current": current,
        "active": active,
        "pending_request": pending,
        "other_states": other_states,
        # Compatibility field: only normalized current states, never raw duplicate rows.
        "features": current_features,
    }


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


def get_current_billing_state(tenant_id: int | str) -> dict[str, Any]:
    """Return persisted, tenant-scoped plan state without invented billing data."""
    try:
        result = (
            service_supabase
            .table("features")
            .select(
                "id, subscription_type, plan, builder_type, payment_status, "
                "billing_state_changed_at, updated_at, created_at"
            )
            .eq("tenant_id", tenant_id)
            .limit(50)
            .execute()
        )
    except Exception as error:
        logger.warning(
            "billing.current_state_failed",
            extra={"tenant_id": tenant_id, "error_type": type(error).__name__},
        )
        raise HTTPException(
            status_code=503,
            detail=error_detail(
                "dependency_unavailable",
                "Billing state is temporarily unavailable.",
            ),
        )

    return normalize_current_billing_features(result.data or [])


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

    changed_at = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "tenant_id": tenant_id,
        "subscription_type": normalized["subscription_type"],
        "plan": normalized["plan"],
        "builder_type": normalized["builder_type"],
        "payment_status": normalized_payment_status,
        "billing_state_changed_at": changed_at,
        "updated_at": changed_at,
    }
    _ = provider_event_id

    existing = get_existing_feature_for_tenant(
        tenant_id=tenant_id,
        subscription_type=str(normalized["subscription_type"]),
        builder_type=normalized["builder_type"],
    )

    if (
        source == "checkout"
        and normalized_payment_status == "pending"
        and existing
        and str(existing.get("payment_status") or "").strip().lower() == "active"
    ):
        logger.info(
            "billing.active_feature_preserved_for_placeholder_checkout",
            extra={
                "tenant_id": tenant_id,
                "subscription_type": normalized["subscription_type"],
                "builder_type": normalized["builder_type"],
            },
        )
        return existing

    if (
        source == "checkout"
        and normalized_payment_status == "pending"
        and existing
        and str(existing.get("payment_status") or "").strip().lower() == "pending"
        and _feature_plan_key(existing) == _feature_plan_key(payload)
    ):
        logger.info(
            "billing.pending_request_reused",
            extra={
                "tenant_id": tenant_id,
                "subscription_type": normalized["subscription_type"],
                "builder_type": normalized["builder_type"],
            },
        )
        return existing

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
        if source == "checkout" and normalized_payment_status == "pending":
            try:
                concurrent = get_existing_feature_for_tenant(
                    tenant_id=tenant_id,
                    subscription_type=str(normalized["subscription_type"]),
                    builder_type=normalized["builder_type"],
                )
            except Exception:
                concurrent = None
            if (
                concurrent
                and str(concurrent.get("payment_status") or "").strip().lower() == "pending"
                and _feature_plan_key(concurrent) == _feature_plan_key(payload)
            ):
                logger.info(
                    "billing.concurrent_pending_request_reused",
                    extra={"tenant_id": tenant_id},
                )
                return concurrent
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


def _normalize_provider_event_id(provider_event_id: str | None) -> str:
    normalized = str(provider_event_id or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "billing_event_id_required",
                "A provider event id is required.",
            ),
        )
    if len(normalized) > 200:
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "billing_event_id_invalid",
                "The provider event id is invalid.",
            ),
        )
    return normalized


def _billing_event_payload_hash(
    *,
    tenant_id: int | str,
    subscription_type: str,
    plan: str,
    builder_type: str | None,
    payment_status: str,
    provider_occurred_at: str | None = None,
) -> str:
    # Hash only stable provider data. When an event does not carry an occurrence
    # timestamp the server assigns receipt time; including that generated value
    # would make a byte-for-byte retry look like conflicting data. The first
    # stored occurrence time remains authoritative for event ordering.
    _ = provider_occurred_at
    canonical_payload = json.dumps(
        {
            "tenant_id": tenant_id,
            "subscription_type": subscription_type,
            "plan": plan,
            "builder_type": builder_type,
            "payment_status": payment_status,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical_payload).hexdigest()


def get_billing_webhook_event(
    *,
    provider: str,
    provider_event_id: str,
) -> dict[str, Any] | None:
    response = (
        service_supabase
        .table("billing_webhook_events")
        .select("id, provider, provider_event_id, tenant_id, status, payload_hash, processed_at")
        .eq("provider", provider)
        .eq("provider_event_id", provider_event_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def apply_billing_webhook_event(
    *,
    tenant_id: int | str,
    subscription_type: str,
    plan: str,
    builder_type: str | None,
    payment_status: str,
    provider_event_id: str | None,
    provider_occurred_at: datetime | str | None = None,
    provider: str = "madar_manual",
) -> dict[str, Any]:
    """Record and apply a manual/development billing event transactionally.

    The database RPC owns the transaction and unique event constraint. A preliminary
    read provides deterministic replay responses; the RPC remains authoritative for
    concurrent deliveries.
    """

    event_id = _normalize_provider_event_id(provider_event_id)
    normalized_provider = str(provider or "").strip().lower() or "madar_manual"
    normalized = validate_billing_plan(
        subscription_type=subscription_type,
        plan=plan,
        builder_type=builder_type,
    )
    normalized_status = str(payment_status or "").strip().lower()
    if normalized_status not in PAYMENT_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid payment status.")

    if isinstance(provider_occurred_at, datetime):
        occurred_at = provider_occurred_at
    elif isinstance(provider_occurred_at, str) and provider_occurred_at.strip():
        try:
            occurred_at = datetime.fromisoformat(
                provider_occurred_at.strip().replace("Z", "+00:00")
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=error_detail(
                    "billing_event_time_invalid",
                    "The provider event time is invalid.",
                ),
            )
    else:
        occurred_at = datetime.now(timezone.utc)
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    occurred_at_iso = occurred_at.astimezone(timezone.utc).isoformat()

    payload_hash = _billing_event_payload_hash(
        tenant_id=tenant_id,
        subscription_type=str(normalized["subscription_type"]),
        plan=str(normalized["plan"]),
        builder_type=normalized["builder_type"],
        payment_status=normalized_status,
        provider_occurred_at=occurred_at_iso,
    )

    try:
        existing = get_billing_webhook_event(
            provider=normalized_provider,
            provider_event_id=event_id,
        )
    except Exception as error:
        logger.warning(
            "billing.webhook_event_lookup_failed",
            extra={"error_type": type(error).__name__},
        )
        raise HTTPException(
            status_code=503,
            detail=error_detail(
                "dependency_unavailable",
                "Billing event storage is unavailable.",
            ),
        )

    if existing:
        if not secrets_compare_hash(existing.get("payload_hash"), payload_hash):
            raise HTTPException(
                status_code=409,
                detail=error_detail(
                    "idempotency_conflict",
                    "The provider event id was already used for different billing data.",
                ),
            )
        feature = get_existing_feature_for_tenant(
            tenant_id=tenant_id,
            subscription_type=str(normalized["subscription_type"]),
            builder_type=normalized["builder_type"],
        )
        return {
            "duplicate": True,
            "event_id": existing.get("id"),
            "event_status": existing.get("status"),
            "feature": feature,
        }

    rpc = getattr(service_supabase, "rpc", None)
    if not callable(rpc):
        raise HTTPException(
            status_code=503,
            detail=error_detail(
                "billing_not_configured",
                "Durable billing event processing is not available.",
            ),
        )

    params = {
        "p_provider": normalized_provider,
        "p_provider_event_id": event_id,
        "p_event_type": f"feature.{normalized_status}",
        "p_tenant_id": tenant_id,
        "p_subscription_type": normalized["subscription_type"],
        "p_plan": normalized["plan"],
        "p_builder_type": normalized["builder_type"],
        "p_payment_status": normalized_status,
        "p_payload_hash": payload_hash,
        "p_provider_occurred_at": occurred_at_iso,
    }

    try:
        response = rpc("apply_billing_webhook_event", params).execute()
    except Exception as error:
        error_text = str(error).lower()
        if "idempotency_conflict" in error_text:
            raise HTTPException(
                status_code=409,
                detail=error_detail(
                    "idempotency_conflict",
                    "The provider event id was already used for different billing data.",
                ),
            )
        logger.warning(
            "billing.webhook_event_apply_failed",
            extra={"error_type": type(error).__name__},
        )
        raise HTTPException(
            status_code=500,
            detail=error_detail(
                "billing_update_failed",
                "The billing event could not be applied.",
            ),
        )

    data = response.data
    result = data[0] if isinstance(data, list) and data else (data or {})
    if isinstance(result, dict) and isinstance(result.get("result"), dict):
        result = result["result"]
    feature = result.get("feature") if isinstance(result, dict) else None
    return {
        "duplicate": bool(result.get("duplicate")) if isinstance(result, dict) else False,
        "event_id": result.get("event_id") if isinstance(result, dict) else None,
        "event_status": result.get("status", "processed") if isinstance(result, dict) else "processed",
        "ignored": bool(result.get("ignored")) if isinstance(result, dict) else False,
        "feature": feature,
    }


def secrets_compare_hash(value: Any, expected: str) -> bool:
    """Compare fixed-length public payload hashes without leaking timing detail."""

    return secrets.compare_digest(str(value or ""), expected)

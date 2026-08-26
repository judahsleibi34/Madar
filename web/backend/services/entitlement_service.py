"""Server-authoritative commercial entitlement evaluation.

Canonical records are authoritative. Missing, malformed, ambiguous, or
unmigrated commercial state grants no paid capability. Existing published-site
continuity is handled narrowly by ``require_public_runtime_entitlement`` rather
than by a catalog-wide compatibility grant.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from database import service_supabase
from services.api_errors import error_detail
from services.commercial_catalog import CAPABILITIES, GIB, get_product


logger = logging.getLogger(__name__)
ACTIVE_STATE = "active"
ENTITLED_STATES = frozenset({"active", "trial", "grace"})
LEGACY_PLAN_MAP = {
    "forms_data": "forms",
    "cms": "website",
    "cms_plus": "business",
    "complete": "business_plus",
}
LEGACY_BUILDER_MAP = {
    "forms": "forms",
    "data": "forms",
    "website": "website",
    "reservation": "business_plus",
}

# TODO(payment-gateway): TEMPORARY operational override only. Production sets
# COMMERCIAL_ENTITLEMENTS_ENFORCED=false until payment gateway integration and
# commercial tenant assignments are ready. Set it back to true to restore the
# canonical subscription/add-on policy; no data migration is required.
TEMPORARY_OVERRIDE_ALLOWANCES = {
    "storage_bytes": 10 * GIB,
    "included_workspace_operators": 10_000,
    "workspace_seats": 0,
    "published_websites": 1,
    "active_builder_projects": None,
    "forms": None,
    "form_submissions": None,
    "reservation_requests": None,
    "standard_tokens": 1_500_000,
}


def _offline_test_compatibility() -> bool:
    return (
        os.getenv("APP_ENV", "").strip().lower() == "test"
        and os.getenv("COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS", "").strip().lower()
        not in {"1", "true", "yes", "on"}
    )


def utc_period_key(moment: datetime | None = None) -> str:
    current = moment or datetime.now(timezone.utc)
    return f"{current.year:04d}-{current.month:02d}"


def utc_period_bounds(moment: datetime | None = None) -> tuple[str, str]:
    current = (moment or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.isoformat(), end.isoformat()


def _rows(response: Any) -> list[dict[str, Any]]:
    return [
        row for row in (getattr(response, "data", None) or [])
        if isinstance(row, dict)
    ]


def _canonical_records(tenant_id: int | str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    try:
        subscriptions = _rows(
            service_supabase.table("tenant_subscriptions")
            .select("*")
            .eq("tenant_id", int(tenant_id))
            .order("updated_at", desc=True)
            .limit(100)
            .execute()
        )
        addons = _rows(
            service_supabase.table("tenant_addons")
            .select("*")
            .eq("tenant_id", int(tenant_id))
            .order("updated_at", desc=True)
            .limit(200)
            .execute()
        )
        return subscriptions, addons
    except (AttributeError, KeyError):
        # Lightweight route-test doubles and pre-commercial empty fixtures may
        # not model billing tables. They represent an unmigrated tenant, not an
        # active canonical subscription.
        return None
    except Exception as error:
        logger.warning(
            "entitlements.canonical_lookup_failed",
            extra={"tenant_id": tenant_id, "error_type": type(error).__name__},
        )
        raise HTTPException(
            status_code=503,
            detail=error_detail(
                "entitlement_dependency_unavailable",
                "Subscription access could not be verified.",
            ),
        ) from error


def _legacy_features(tenant_id: int | str) -> list[dict[str, Any]]:
    try:
        return _rows(
            service_supabase.table("features")
            .select("id,subscription_type,plan,builder_type,payment_status,updated_at")
            .eq("tenant_id", int(tenant_id))
            .limit(100)
            .execute()
        )
    except (AttributeError, KeyError):
        return []
    except Exception as error:
        logger.warning(
            "entitlements.legacy_lookup_failed",
            extra={"tenant_id": tenant_id, "error_type": type(error).__name__},
        )
        raise HTTPException(
            status_code=503,
            detail=error_detail(
                "entitlement_dependency_unavailable",
                "Subscription access could not be verified.",
            ),
        )


def _legacy_plan_id(rows: list[dict[str, Any]]) -> str | None:
    active = [
        row for row in rows
        if str(row.get("payment_status") or "").strip().lower() == "active"
    ]
    if len(active) != 1:
        return None
    row = active[0]
    plan = str(row.get("plan") or "").strip().lower()
    if plan in LEGACY_PLAN_MAP:
        return LEGACY_PLAN_MAP[plan]
    if str(row.get("subscription_type") or "").strip().lower() == "individual_builder":
        return LEGACY_BUILDER_MAP.get(str(row.get("builder_type") or "").strip().lower())
    return None


def _plan_entitlements(plan_id: str | None) -> tuple[set[str], dict[str, int | None]]:
    product = get_product(plan_id or "")
    if not product or product.get("type") != "base_plan":
        return set(), {}
    return set(product.get("capabilities") or []), dict(product.get("allowances") or {})


def _ai_provider_configured() -> bool:
    provider = os.getenv("AI_PROVIDER", "gemini").strip().lower()
    if not _env_enabled("AI_FEATURE_ENABLED", False):
        return False
    if provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY", "").strip())
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY", "").strip())
    return False


def _env_enabled(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def commercial_entitlements_enforced() -> bool:
    """Return the reversible operator-controlled commercial policy state."""
    return _env_enabled("COMMERCIAL_ENTITLEMENTS_ENFORCED", True)


def _temporary_operator_override_state(tenant_id: int | str) -> dict[str, Any]:
    capabilities = set(CAPABILITIES)
    operational, availability = _operational_capabilities(capabilities)
    return {
        "tenant_id": int(tenant_id),
        "source": "operator_configuration_override",
        "plan_id": "temporary_all_capabilities",
        "subscription": None,
        "subscriptions": [],
        # Preserve the existing AI metering integration while the tenant's
        # canonical commercial records are intentionally ignored.
        "active_addons": [
            {"addon_id": "ai_analytics_plus", "state": ACTIVE_STATE, "quantity": 1}
        ],
        "capabilities": sorted(capabilities),
        "operational_capabilities": sorted(operational),
        "capability_availability": availability,
        "allowances": dict(TEMPORARY_OVERRIDE_ALLOWANCES),
        "legacy_features": [],
        "review_required": False,
        "commercial_entitlements_enforced": False,
    }


if not commercial_entitlements_enforced():
    # This runs once per backend process, never once per request.
    logger.warning(
        "commercial entitlement enforcement disabled by operator configuration"
    )


def _operational_capabilities(capabilities: set[str]) -> tuple[set[str], dict[str, str]]:
    operational = set(capabilities)
    availability: dict[str, str] = {}
    if "ai_analytics" in operational and not _ai_provider_configured():
        operational.remove("ai_analytics")
        availability["ai_analytics"] = "provider_unavailable"
    elif "ai_analytics" in operational:
        availability["ai_analytics"] = "operational"
    return operational, availability


def _unentitled_state(
    tenant_id: int | str,
    *,
    source: str,
    subscriptions: list[dict[str, Any]] | None = None,
    addons: list[dict[str, Any]] | None = None,
    legacy: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "source": source,
        "plan_id": None,
        "subscription": None,
        "subscriptions": list(subscriptions or []),
        "active_addons": list(addons or []),
        "capabilities": [],
        "operational_capabilities": [],
        "capability_availability": {},
        "allowances": {},
        "legacy_features": list(legacy or []),
        "review_required": True,
    }


def get_tenant_entitlements(tenant_id: int | str) -> dict[str, Any]:
    if not commercial_entitlements_enforced():
        return _temporary_operator_override_state(tenant_id)

    # The repository's offline suite intentionally uses dummy Supabase URLs.
    # Tests that exercise canonical lookup behavior opt in explicitly.
    if _offline_test_compatibility():
        return _unentitled_state(tenant_id, source="offline_test_unentitled")

    records = _canonical_records(tenant_id)
    if records is not None:
        subscriptions, addons = records
        entitled_subscriptions = [
            row for row in subscriptions
            if str(row.get("state") or "").strip().lower() in ENTITLED_STATES
        ]
        if len(entitled_subscriptions) > 1:
            logger.error(
                "entitlements.ambiguous_subscription_state",
                extra={"tenant_id": tenant_id, "count": len(entitled_subscriptions)},
            )
            raise HTTPException(
                status_code=503,
                detail=error_detail(
                    "entitlement_state_ambiguous",
                    "Subscription access could not be verified.",
                ),
            )
        active_subscription = entitled_subscriptions[0] if entitled_subscriptions else None
        if subscriptions or addons:
            plan_id = str((active_subscription or {}).get("plan_id") or "") or None
            if active_subscription:
                capabilities, allowances = _plan_entitlements(plan_id)
                source = "canonical"
            else:
                return _unentitled_state(
                    tenant_id,
                    source="canonical_inactive",
                    subscriptions=subscriptions,
                    addons=addons,
                    legacy=_legacy_features(tenant_id),
                )
            active_addons: list[dict[str, Any]] = []
            for addon in addons:
                if addon.get("state") != ACTIVE_STATE:
                    continue
                product = get_product(str(addon.get("addon_id") or ""))
                if not product:
                    continue
                quantity = max(int(addon.get("quantity") or 0), 0)
                if quantity <= 0:
                    continue
                active_addons.append(addon)
                capabilities.update(product.get("capabilities") or [])
                for key, value in (product.get("allowances") or {}).items():
                    if isinstance(value, int):
                        allowances[key] = int(allowances.get(key) or 0) + value * quantity
            try:
                website_rows = _rows(
                    service_supabase.table("website_settings")
                    .select("branded_subdomain_commercial_status")
                    .eq("tenant_id", int(tenant_id))
                    .eq("branded_subdomain_commercial_status", "grandfathered")
                    .limit(1)
                    .execute()
                )
                if website_rows:
                    capabilities.add("branded_madar_subdomain")
            except Exception:
                logger.info(
                    "entitlements.subdomain_grandfather_lookup_unavailable",
                    extra={"tenant_id": tenant_id},
                )
            operational, availability = _operational_capabilities(capabilities)
            return {
                "tenant_id": int(tenant_id),
                "source": source,
                "plan_id": plan_id,
                "subscription": active_subscription,
                "subscriptions": subscriptions,
                "active_addons": active_addons,
                "capabilities": sorted(capabilities),
                "operational_capabilities": sorted(operational),
                "capability_availability": availability,
                "allowances": allowances,
                "review_required": not bool(active_subscription),
            }

    legacy = _legacy_features(tenant_id)
    return _unentitled_state(
        tenant_id,
        source="missing_canonical_subscription",
        legacy=legacy,
    )


def has_entitlement(tenant_id: int | str, capability: str) -> bool:
    normalized = str(capability or "").strip().lower()
    if normalized not in CAPABILITIES:
        return False
    return normalized in set(get_tenant_entitlements(tenant_id)["capabilities"])


def require_entitlement(
    tenant_id: int | str,
    capability: str,
    *,
    message: str | None = None,
) -> dict[str, Any]:
    state = get_tenant_entitlements(tenant_id)
    active = set(state.get("operational_capabilities", state["capabilities"]))
    if capability in active:
        return state
    if capability in set(state["capabilities"]):
        raise HTTPException(
            status_code=503,
            detail=error_detail(
                "capability_dependency_unavailable",
                f"The {capability.replace('_', ' ')} dependency is unavailable.",
                context={"capability": capability},
            ),
        )
    raise HTTPException(
        status_code=402,
        detail=error_detail(
            "entitlement_required",
            message or f"An active {capability.replace('_', ' ')} entitlement is required.",
            context={"capability": capability, "plan_id": state.get("plan_id")},
        ),
    )


def require_any_entitlement(
    tenant_id: int | str,
    capabilities: set[str] | tuple[str, ...] | list[str],
    *,
    message: str,
) -> dict[str, Any]:
    state = get_tenant_entitlements(tenant_id)
    active = set(state.get("operational_capabilities", state["capabilities"]))
    if any(capability in active for capability in capabilities):
        return state
    raise HTTPException(
        status_code=402,
        detail=error_detail(
            "entitlement_required",
            message,
            context={"capabilities": sorted(capabilities), "plan_id": state.get("plan_id")},
        ),
    )


def get_storage_quota_bytes(tenant_id: int | str) -> int:
    state = get_tenant_entitlements(tenant_id)
    quota = int(state.get("allowances", {}).get("storage_bytes") or 0)
    if quota <= 0:
        raise HTTPException(
            status_code=402,
            detail=error_detail(
                "storage_entitlement_required",
                "An active plan with hosted storage is required.",
            ),
        )
    return quota


def get_workspace_seat_capacity(tenant_id: int | str) -> int:
    state = get_tenant_entitlements(tenant_id)
    allowances = state.get("allowances", {})
    included = int(allowances.get("included_workspace_operators") or 1)
    added = int(allowances.get("workspace_seats") or 0)
    return max(included + added, 1)


def get_workspace_seat_usage(tenant_id: int | str) -> int:
    rows = _rows(
        service_supabase.table("tenant_memberships")
        .select("id")
        .eq("tenant_id", int(tenant_id))
        .eq("status", "active")
        .limit(10000)
        .execute()
    )
    return len(rows)


def require_workspace_seat_available(tenant_id: int | str) -> dict[str, int]:
    capacity = get_workspace_seat_capacity(tenant_id)
    used = get_workspace_seat_usage(tenant_id)
    if used >= capacity:
        raise HTTPException(
            status_code=402,
            detail=error_detail(
                "workspace_seat_limit_reached",
                "No workspace member seats remain.",
                context={"capacity": capacity, "used": used},
            ),
        )
    return {"capacity": capacity, "used": used, "remaining": capacity - used}


def branded_subdomain_allowed(
    settings: dict[str, Any],
    *,
    allow_legacy_routing: bool = False,
) -> bool:
    commercial_status = str(
        settings.get("branded_subdomain_commercial_status") or "not_applicable"
    ).strip().lower()
    if commercial_status == "grandfathered":
        return True
    tenant_id = settings.get("tenant_id")
    if tenant_id is not None and has_entitlement(
        tenant_id, "branded_madar_subdomain"
    ):
        return True
    return bool(
        allow_legacy_routing
        and commercial_status == "pending_review"
        and settings.get("legacy_subdomain_routing_preserved")
        and settings.get("published_project_id")
    )


def require_branded_subdomain(
    settings: dict[str, Any],
    *,
    allow_legacy_routing: bool = False,
) -> None:
    if branded_subdomain_allowed(
        settings,
        allow_legacy_routing=allow_legacy_routing,
    ):
        return
    raise HTTPException(
        status_code=402,
        detail=error_detail(
            "branded_subdomain_entitlement_required",
            "This branded Madar subdomain requires an active add-on.",
        ),
    )


def require_public_runtime_entitlement(
    settings: dict[str, Any],
    capability: str,
) -> dict[str, Any]:
    """Keep an already-published runtime available during billing outages.

    Canonical inactive/suspended tenants are denied normally. Only dependency
    failures fall back, and only for a record already bound to published content.
    """
    try:
        return require_entitlement(settings.get("tenant_id"), capability)
    except HTTPException as error:
        if (
            error.status_code == 503
            and settings.get("published_project_id")
        ):
            logger.warning(
                "entitlements.public_runtime_compatibility",
                extra={
                    "tenant_id": settings.get("tenant_id"),
                    "capability": capability,
                },
            )
            return {"source": "published_runtime_dependency_fallback"}
        raise


def increment_operational_usage(
    tenant_id: int | str,
    metric: str,
    *,
    delta: int = 1,
) -> None:
    """Best-effort aggregate telemetry; never a commercial write quota."""
    if _offline_test_compatibility():
        return
    try:
        service_supabase.rpc(
            "increment_commercial_usage",
            {
                "p_tenant_id": int(tenant_id),
                "p_period_key": utc_period_key(),
                "p_metric": metric,
                "p_delta": max(int(delta), 0),
            },
        ).execute()
    except Exception as error:
        logger.warning(
            "commercial_usage.increment_failed",
            extra={
                "tenant_id": tenant_id,
                "metric": metric,
                "error_type": type(error).__name__,
            },
        )


def get_operational_usage(tenant_id: int | str) -> dict[str, int | str]:
    period_key = utc_period_key()
    if _offline_test_compatibility():
        return {
            "period_key": period_key,
            "forms_created": 0,
            "form_submissions": 0,
            "reservation_requests": 0,
            "commercial_limits_apply": False,
        }
    try:
        rows = _rows(
            service_supabase.table("commercial_usage_monthly")
            .select("period_key,forms_created,form_submissions,reservation_requests")
            .eq("tenant_id", int(tenant_id))
            .eq("period_key", period_key)
            .limit(1)
            .execute()
        )
    except Exception:
        rows = []
    row = rows[0] if rows else {}
    return {
        "period_key": period_key,
        "forms_created": int(row.get("forms_created") or 0),
        "form_submissions": int(row.get("form_submissions") or 0),
        "reservation_requests": int(row.get("reservation_requests") or 0),
        "commercial_limits_apply": False,
    }

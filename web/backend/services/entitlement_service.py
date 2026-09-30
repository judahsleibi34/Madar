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
from services.commercial_catalog import CAPABILITIES, GIB, get_product, module_entitlements, CORE_MODULE_IDS
from services.commercial_access_service import resolve_commercial_access


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
# canonical assignment/dated-ledger/add-on policy after tenant review. This
# flag never overrides an explicit administrative hold from the ledger.
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
    provider = os.getenv("AI_PROVIDER", "").strip().lower()
    if not _env_enabled("AI_FEATURE_ENABLED", False):
        return False
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


def get_tenant_entitlements(tenant_id: int | str, *, commercial_snapshot: dict | None = None) -> dict[str, Any]:
    """Assignment describes the product; the ledger authorizes effective use.

    No entitlement cache is used. Every request reads a new database snapshot,
    including revision and time transitions, before considering the bypass.
    Public runtime can supply its validated same-statement ledger snapshot to
    avoid a second WAN round trip. This is never a browser-supplied argument.
    """
    ledger = resolve_commercial_access(tenant_id) if commercial_snapshot is None else commercial_snapshot
    assigned_rows = ledger.get("subscriptions") or []
    candidates = [row for row in assigned_rows if isinstance(row, dict) and isinstance(row.get("state"), str) and row["state"] in ENTITLED_STATES] if isinstance(assigned_rows, list) else []
    assignment = candidates[0] if len(candidates) == 1 else None
    metadata = {
        "assigned_plan_id": (assignment or {}).get("plan_id"),
        "assigned_subscription": assignment,
        "assigned_modules": sorted((assignment or {}).get("module_basis") or {}) if isinstance((assignment or {}).get("module_basis"), dict) else [],
        "module_commercial_basis": (assignment or {}).get("module_basis"),
        "pricing": (assignment or {}).get("pricing"),
        "legacy_assignment_requires_review": bool(assignment and assignment.get("module_basis") is None),
        "commercial_revision": ledger.get("revision"),
        "commercial_access_state": ledger.get("access_state"),
        "next_transition_at": ledger.get("next_transition_at"),
        "effective_at": ledger.get("effective_at"),
        "access_period": ledger.get("period"),
        "commercial_entitlements_enforced": commercial_entitlements_enforced(),
        "commercial_suspended_at": ledger.get("commercial_suspended_at"),
    }

    def denied(code: str, source: str) -> dict[str, Any]:
        return {
            **_unentitled_state(tenant_id, source=source), **metadata,
            "commercial_denial_code": code,
            "review_required": code in {"commercial_review_required", "commercial_state_invalid"},
        }

    if ledger.get("commercial_suspended_at") is not None:
        return denied("commercial_access_suspended", "commercial_ledger_suspended")
    if not commercial_entitlements_enforced():
        return {**_temporary_operator_override_state(tenant_id), **metadata}
    if not ledger or ledger.get("review_state") != "reviewed":
        return denied("commercial_review_required", "commercial_ledger_review_required")
    period = ledger.get("period")
    if period is None:
        code = "commercial_access_expired" if ledger.get("access_state") == "expired" else "commercial_access_required"
        return denied(code, "commercial_ledger_inactive")
    if not isinstance(period, dict) or period.get("tenant_id") != int(tenant_id):
        return denied("commercial_state_invalid", "commercial_ledger_invalid")
    # The SQL snapshot evaluates effective_during. Validate its finite bounds
    # against the same statement time as defense against malformed responses.
    if not _valid_at(period, ledger.get("effective_at"), "valid_from", "valid_until", required=True):
        return denied("commercial_state_invalid", "commercial_ledger_invalid")
    subscriptions = ledger.get("subscriptions")
    if subscriptions is None:
        if ledger.get("contract_version", 114) >= 115:
            return denied("commercial_state_invalid", "commercial_assignment_invalid")
        # Schema-114 bridge: the old ledger resolver predates assignment in its
        # snapshot. New privileged commands stay unavailable until schema 115.
        records = _canonical_records(tenant_id)
        subscriptions = records[0] if records is not None else []
    if not isinstance(subscriptions, list) or any(not isinstance(row, dict) for row in subscriptions):
        return denied("commercial_state_invalid", "commercial_assignment_invalid")
    assigned = [row for row in subscriptions if isinstance(row.get("state"), str) and row["state"] in ENTITLED_STATES]
    if len(assigned) > 1:
        raise HTTPException(status_code=503, detail=error_detail(
            "entitlement_state_ambiguous", "Subscription access could not be verified."))
    subscription = assigned[0] if assigned else None
    if not subscription:
        return {**denied("commercial_access_required", "canonical_inactive"), "subscriptions": subscriptions, "review_required": not bool(subscriptions)}
    if subscription.get("tenant_id") != int(tenant_id):
        return denied("commercial_state_invalid", "commercial_assignment_invalid")
    basis = subscription.get("module_basis")
    if basis is None or subscription.get("plan_id") is not None:
        return denied("commercial_review_required", "legacy_module_mapping_required")
    if (not isinstance(basis, dict) or not basis or any(module not in CORE_MODULE_IDS for module in basis)
        or any(not isinstance(value, dict) or not isinstance(value.get("price_book_id"), str) for value in basis.values())):
        return denied("commercial_state_invalid", "commercial_assignment_invalid")
    covered = period.get("module_ids")
    if (period.get("plan_id") is not None or not isinstance(covered, list)
        or any(not isinstance(module,str) or module not in CORE_MODULE_IDS for module in covered)
        or len(covered)!=len(set(covered))):
        return denied("commercial_review_required", "legacy_access_mapping_required")
    effective_modules = sorted(set(basis) & set(covered))
    if not effective_modules:
        return denied("commercial_access_required", "commercial_modules_uncovered")
    if isinstance(subscription.get("pricing"), dict) and subscription["pricing"].get("pricing_status") == "review_required":
        return denied("commercial_review_required", "commercial_price_basis_requires_review")
    capabilities, allowances = module_entitlements(effective_modules)
    plan_id = None
    # Optional assignment bounds further restrict a grant; an active row never
    # extends the dated ledger period. Legacy null bounds remain permissible.
    if not _valid_at(subscription, ledger.get("effective_at"), "period_start", "period_end"):
        return denied("commercial_access_expired", "commercial_assignment_inactive")
    addons = ledger.get("addons")
    if not isinstance(addons, list):
        return denied("commercial_state_invalid", "commercial_addons_invalid")
    active_addons = []
    for addon in addons:
        if not isinstance(addon, dict):
            return denied("commercial_state_invalid", "commercial_addons_invalid")
        if addon.get("state") != ACTIVE_STATE or not _valid_at(
            addon, ledger.get("effective_at"), "period_start", "period_end"
        ):
            continue
        product = get_product(str(addon.get("addon_id") or ""))
        quantity = addon.get("quantity")
        if (not product or product.get("type") not in {"add_on", "token_pack"}
            or not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0):
            return denied("commercial_state_invalid", "commercial_addons_invalid")
        required = product.get("requires_capability")
        if required and required not in capabilities:
            continue
        active_addons.append(addon)
        capabilities.update(product.get("capabilities") or [])
        for key, value in (product.get("allowances") or {}).items():
            if isinstance(value, int):
                allowances[key] = int(allowances.get(key) or 0) + value * quantity
    if ledger.get("grandfathered_subdomain"):
        capabilities.add("branded_madar_subdomain")
    operational, availability = _operational_capabilities(capabilities)
    return {
        "tenant_id": int(tenant_id), "source": "canonical_commercial_ledger",
        "plan_id": None,
        "effective_modules": effective_modules, "subscription": subscription,
        "subscriptions": subscriptions, "active_addons": active_addons,
        "capabilities": sorted(capabilities), "operational_capabilities": sorted(operational),
        "capability_availability": availability, "allowances": allowances,
        "review_required": False, **metadata,
    }


def _valid_at(record: dict, effective_at: Any, start_key: str, end_key: str, *, required=False) -> bool:
    try:
        now = datetime.fromisoformat(str(effective_at).replace("Z", "+00:00"))
        if now.tzinfo is None:
            return False
        bounds = []
        for key in (start_key, end_key):
            raw = record.get(key)
            if raw is None:
                if required:
                    return False
                bounds.append(None)
                continue
            value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if value.tzinfo is None:
                return False
            bounds.append(value)
        start, end = bounds
        return ((start is None or start <= now) and (end is None or now < end)
                and (start is None or end is None or start < end))
    except (ValueError, TypeError, OverflowError):
        return False


def _require_commercial_state(state: dict[str, Any]) -> None:
    code = state.get("commercial_denial_code")
    if code:
        messages = {
            "commercial_access_suspended": "Workspace commercial access is suspended. Contact support for review. Your data is retained.",
            "commercial_access_expired": "Workspace commercial access has expired.",
            "commercial_review_required": "Workspace commercial access requires review.",
        }
        raise HTTPException(status_code={
            "commercial_access_required": 402, "commercial_access_expired": 402,
            "commercial_access_suspended": 403, "commercial_review_required": 403,
            "commercial_state_invalid": 503,
        }.get(code, 503), detail=error_detail(
            code, messages.get(code, "Workspace commercial access is unavailable.")))


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
    commercial_snapshot: dict | None = None,
) -> dict[str, Any]:
    state = (get_tenant_entitlements(tenant_id) if commercial_snapshot is None
             else get_tenant_entitlements(tenant_id, commercial_snapshot=commercial_snapshot))
    _require_commercial_state(state)
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
    _require_commercial_state(state)
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
    _require_commercial_state(state)
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
    *, commercial_snapshot: dict | None = None,
) -> dict[str, Any]:
    """Authorize published use without disclosing internal commercial state."""
    try:
        if commercial_snapshot is None:
            return require_entitlement(settings.get("tenant_id"), capability)
        return require_entitlement(settings.get("tenant_id"), capability, commercial_snapshot=commercial_snapshot)
    except HTTPException as error:
        if error.status_code in {402, 403, 503}:
            raise HTTPException(status_code=503, detail=error_detail(
                "tenant_service_unavailable", "This service is temporarily unavailable."
            ), headers={"Cache-Control": "no-store"}) from error
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

"""Tenant-level AI standard-token accounting.

Provider usage is captured server-side. Database RPCs own reservation and
finalization concurrency; no client token count is accepted.
"""

from __future__ import annotations

import contextvars
import json
import math
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from fastapi import HTTPException

from database import service_supabase
from services.api_errors import error_detail
from services.commercial_catalog import CATALOG_VERSION, get_product
from services.entitlement_service import get_tenant_entitlements, utc_period_bounds, utc_period_key


MULTIPLIER_SCALE = 1_000_000
DEFAULT_MULTIPLIERS = {
    "version": "v1",
    "input_multiplier_micros": 1_000_000,
    "cached_input_multiplier_micros": 1_000_000,
    "output_multiplier_micros": 2_000_000,
}
_CAPTURED_USAGE: contextvars.ContextVar[list[dict[str, Any]] | None] = (
    contextvars.ContextVar("madar_ai_provider_usage", default=None)
)


def _rows(response: Any) -> list[dict[str, Any]]:
    return [
        row for row in (getattr(response, "data", None) or [])
        if isinstance(row, dict)
    ]


@contextmanager
def capture_provider_usage() -> Iterator[list[dict[str, Any]]]:
    captured: list[dict[str, Any]] = []
    token = _CAPTURED_USAGE.set(captured)
    try:
        yield captured
    finally:
        _CAPTURED_USAGE.reset(token)


def record_provider_usage(usage: dict[str, Any]) -> None:
    captured = _CAPTURED_USAGE.get()
    if captured is not None and isinstance(usage, dict):
        captured.append(
            {
                "provider": str(usage.get("provider") or "unknown"),
                "model": str(usage.get("model") or "unknown"),
                "input_tokens": max(int(usage.get("input_tokens") or 0), 0),
                "cached_input_tokens": max(int(usage.get("cached_input_tokens") or 0), 0),
                "output_tokens": max(int(usage.get("output_tokens") or 0), 0),
                "total_provider_tokens": max(int(usage.get("total_provider_tokens") or 0), 0),
                "usage_source": str(usage.get("usage_source") or "provider"),
                "estimated": bool(usage.get("estimated", False)),
            }
        )


def estimate_text_tokens(value: Any) -> int:
    """Conservative server-side estimate used only when metadata is unavailable."""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    if not text:
        return 0
    # Mixed Arabic/Latin JSON is conservatively estimated at roughly three
    # characters per token. This intentionally rounds upward.
    return max(1, math.ceil(len(text.encode("utf-8")) / 3))


def get_model_multipliers(provider: str, model: str) -> dict[str, Any]:
    try:
        rows = _rows(
            service_supabase.table("ai_token_model_multipliers")
            .select(
                "version,provider,model_pattern,input_multiplier_micros,"
                "cached_input_multiplier_micros,output_multiplier_micros"
            )
            .eq("active", True)
            .execute()
        )
    except Exception:
        rows = []
    normalized_provider = str(provider or "").lower()
    normalized_model = str(model or "").lower()
    ranked = sorted(
        rows,
        key=lambda row: (
            str(row.get("provider") or "") in {normalized_provider, "*"},
            str(row.get("provider") or "") == normalized_provider,
            str(row.get("model_pattern") or "") in {normalized_model, "*"},
            str(row.get("model_pattern") or "") == normalized_model,
        ),
        reverse=True,
    )
    return ranked[0] if ranked else dict(DEFAULT_MULTIPLIERS)


def normalize_standard_tokens(
    *,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    multipliers: dict[str, Any],
) -> int:
    weighted = (
        max(int(input_tokens), 0) * int(multipliers["input_multiplier_micros"])
        + max(int(cached_input_tokens), 0)
        * int(multipliers["cached_input_multiplier_micros"])
        + max(int(output_tokens), 0) * int(multipliers["output_multiplier_micros"])
    )
    return (weighted + MULTIPLIER_SCALE - 1) // MULTIPLIER_SCALE


def _monthly_ai_product(entitlements: dict[str, Any]) -> dict[str, Any] | None:
    active_ids = {
        str(addon.get("addon_id") or "")
        for addon in entitlements.get("active_addons", [])
    }
    if "ai_analytics_plus" in active_ids:
        return get_product("ai_analytics_plus")
    if "ai_analytics_starter" in active_ids:
        return get_product("ai_analytics_starter")
    return None


def ensure_monthly_allocation(tenant_id: int, *, period_key: str | None = None) -> int:
    entitlements = get_tenant_entitlements(tenant_id)
    product = _monthly_ai_product(entitlements)
    if not product:
        raise HTTPException(
            status_code=402,
            detail=error_detail(
                "ai_analytics_addon_required",
                "An active AI Analytics token package is required.",
            ),
        )
    key = period_key or utc_period_key()
    allowance = int(product.get("allowances", {}).get("standard_tokens") or 0)
    try:
        service_supabase.rpc(
            "ensure_ai_monthly_allocation",
            {
                "p_tenant_id": int(tenant_id),
                "p_period_key": key,
                "p_product_id": product["id"],
                "p_standard_tokens": allowance,
                "p_idempotency_key": f"monthly:{product['id']}:{key}",
                "p_reason": f"Canonical catalog {CATALOG_VERSION} monthly allocation",
            },
        ).execute()
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=error_detail(
                "ai_token_accounting_unavailable",
                "AI token accounting is temporarily unavailable.",
            ),
        ) from error
    return allowance


def reserve_tokens(
    *,
    tenant_id: int,
    user_id: int,
    operation_type: str,
    maximum_standard_tokens: int,
    request_id: str | None = None,
) -> dict[str, Any]:
    period_key = utc_period_key()
    ensure_monthly_allocation(tenant_id, period_key=period_key)
    clean_request_id = str(request_id or f"ai_{secrets.token_urlsafe(24)}")[:160]
    response = service_supabase.rpc(
        "reserve_ai_standard_tokens",
        {
            "p_tenant_id": int(tenant_id),
            "p_user_id": int(user_id),
            "p_period_key": period_key,
            "p_request_id": clean_request_id,
            "p_operation_type": str(operation_type or "analytics")[:80],
            "p_reserved_tokens": max(int(maximum_standard_tokens), 1),
            "p_expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=15)
            ).isoformat(),
        },
    ).execute()
    rows = _rows(response)
    row = rows[0] if rows else {}
    if row.get("reservation_status") in {"finalized", "released", "expired"}:
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "ai_request_already_processed",
                "This AI request identifier has already been processed.",
            ),
        )
    if not row.get("accepted"):
        raise HTTPException(
            status_code=402,
            detail=error_detail(
                "ai_tokens_exhausted",
                "No AI standard tokens remain in this billing period.",
                context={"remaining_standard_tokens": int(row.get("remaining_tokens") or 0)},
            ),
        )
    return row


def aggregate_usage(
    captured: list[dict[str, Any]],
    *,
    fallback_input: Any,
    fallback_output: Any,
    provider: str,
    model: str,
) -> dict[str, Any]:
    if captured:
        providers = {row["provider"] for row in captured}
        models = {row["model"] for row in captured}
        return {
            "provider": next(iter(providers)) if len(providers) == 1 else "multiple",
            "model": next(iter(models)) if len(models) == 1 else "multiple",
            "input_tokens": sum(row["input_tokens"] for row in captured),
            "cached_input_tokens": sum(row["cached_input_tokens"] for row in captured),
            "output_tokens": sum(row["output_tokens"] for row in captured),
            "total_provider_tokens": sum(row["total_provider_tokens"] for row in captured),
            "usage_source": (
                "provider"
                if all(row["usage_source"] == "provider" for row in captured)
                else "provider_partial"
            ),
            "estimated": any(row["estimated"] for row in captured),
        }
    input_tokens = estimate_text_tokens(fallback_input)
    output_tokens = estimate_text_tokens(fallback_output)
    return {
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "cached_input_tokens": 0,
        "output_tokens": output_tokens,
        "total_provider_tokens": input_tokens + output_tokens,
        "usage_source": "server_estimate",
        "estimated": True,
    }


def finalize_tokens(
    request_id: str,
    usage: dict[str, Any],
    *,
    request_status: str,
) -> int:
    multipliers = get_model_multipliers(usage["provider"], usage["model"])
    standard_tokens = normalize_standard_tokens(
        input_tokens=usage["input_tokens"],
        cached_input_tokens=usage["cached_input_tokens"],
        output_tokens=usage["output_tokens"],
        multipliers=multipliers,
    )
    response = service_supabase.rpc(
        "finalize_ai_standard_tokens",
        {
            "p_request_id": request_id,
            "p_provider": usage["provider"],
            "p_model": usage["model"],
            "p_multiplier_version": str(multipliers.get("version") or "v1"),
            "p_input_tokens": usage["input_tokens"],
            "p_cached_input_tokens": usage["cached_input_tokens"],
            "p_output_tokens": usage["output_tokens"],
            "p_total_provider_tokens": usage["total_provider_tokens"],
            "p_standard_tokens": standard_tokens,
            "p_request_status": request_status,
            "p_usage_source": usage["usage_source"],
            "p_estimated": usage["estimated"],
        },
    ).execute()
    value = getattr(response, "data", None)
    if isinstance(value, list):
        value = value[0] if value else standard_tokens
    if isinstance(value, dict):
        value = value.get("standard_tokens", standard_tokens)
    return int(value if value is not None else standard_tokens)


def release_tokens(request_id: str) -> None:
    service_supabase.rpc(
        "release_ai_standard_tokens",
        {"p_request_id": request_id},
    ).execute()


def get_token_summary(tenant_id: int) -> dict[str, Any]:
    period_key = utc_period_key()
    start, end = utc_period_bounds()
    try:
        allocations = _rows(
            service_supabase.table("ai_token_allocations")
            .select("allocation_type,product_id,standard_tokens,state")
            .eq("tenant_id", int(tenant_id))
            .eq("period_key", period_key)
            .eq("state", "active")
            .execute()
        )
        ledger = _rows(
            service_supabase.table("ai_token_ledger")
            .select("standard_tokens,covered_standard_tokens,deficit_standard_tokens")
            .eq("tenant_id", int(tenant_id))
            .eq("period_key", period_key)
            .execute()
        )
        reservations = _rows(
            service_supabase.table("ai_token_reservations")
            .select("reserved_standard_tokens")
            .eq("tenant_id", int(tenant_id))
            .eq("period_key", period_key)
            .eq("status", "reserved")
            .gt("expires_at", datetime.now(timezone.utc).isoformat())
            .execute()
        )
    except Exception:
        allocations, ledger, reservations = [], [], []
    allocated = sum(int(row.get("standard_tokens") or 0) for row in allocations)
    used = sum(int(row.get("standard_tokens") or 0) for row in ledger)
    covered = sum(int(row.get("covered_standard_tokens") or 0) for row in ledger)
    deficit = sum(int(row.get("deficit_standard_tokens") or 0) for row in ledger)
    reserved = sum(int(row.get("reserved_standard_tokens") or 0) for row in reservations)
    package = next(
        (
            row.get("product_id")
            for row in allocations
            if row.get("allocation_type") == "monthly_package"
        ),
        None,
    )
    packs = sum(
        int(row.get("standard_tokens") or 0)
        for row in allocations
        if row.get("allocation_type") == "token_pack"
    )
    return {
        "period_key": period_key,
        "period_start": start,
        "period_end": end,
        "package": package,
        "included_standard_tokens": allocated - packs,
        "purchased_pack_tokens": packs,
        "allocated_standard_tokens": allocated,
        "used_standard_tokens": used,
        "covered_standard_tokens": covered,
        "deficit_standard_tokens": deficit,
        "reserved_standard_tokens": reserved,
        "remaining_standard_tokens": max(allocated - used - reserved, 0),
    }

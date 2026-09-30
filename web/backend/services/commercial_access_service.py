"""Canonical commercial ledger read/command boundary.

No process or Redis entitlement cache: each access check sees a statement-time
snapshot. The schema-114 bridge can read access, but mutations require 115.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from database import service_supabase
from services.api_errors import error_detail

logger = logging.getLogger(__name__)


def resolve_commercial_access(tenant_id: int | str) -> dict[str, Any]:
    if (os.getenv("APP_ENV", "").lower() == "test"
        and os.getenv("COMMERCIAL_ENTITLEMENT_TEST_LOOKUPS", "").lower() not in {"1", "true", "yes", "on"}):
        return {"tenant_id": int(tenant_id), "revision": 1, "review_state": "review_required",
                "commercial_suspended_at": None, "period": None, "has_history": False,
                "addons": [], "effective_at": datetime.now(timezone.utc).isoformat()}
    try:
        data = service_supabase.rpc("resolve_commercial_access", {"p_tenant_id": int(tenant_id)}).execute().data
        if data is None:
            # Missing state cannot hide an explicit hold: the canonical RPC is
            # required even under temporary compatibility policy.
            raise ValueError("missing_commercial_state")
        if (not isinstance(data, dict) or data.get("tenant_id") != int(tenant_id)
            or not isinstance(data.get("revision"), int) or isinstance(data.get("revision"), bool)
            or data["revision"] <= 0 or data.get("review_state") not in {"reviewed", "review_required"}):
            raise ValueError("invalid_commercial_state")
        # Schema 099–114 cannot contain a hold. Schema 115 requires an explicit
        # hold field; a malformed upgraded snapshot must never enter the bypass.
        version = data.get("contract_version", 114)
        if isinstance(version, bool) or version not in {114, 115}:
            raise ValueError("unknown_commercial_contract")
        if version == 115 and (
            "commercial_suspended_at" not in data or "subscriptions" not in data
        ):
            raise ValueError("incomplete_commercial_snapshot")
        return data
    except Exception as error:
        logger.warning("commercial.access_lookup_failed", extra={"tenant_id": tenant_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=503, detail=error_detail(
            "commercial_dependency_unavailable", "Commercial access could not be verified.")) from error


def apply_commercial_command(*, tenant_id: int, actor_user_id: int, operation: str,
                             idempotency_key: str, request_id: str, command: dict,
                             quote: dict | None = None) -> dict:
    state = resolve_commercial_access(tenant_id)
    if state.get("contract_version", 114) < 115:
        raise HTTPException(status_code=503, detail=error_detail(
            "commercial_upgrade_required", "Commercial administration is unavailable until the schema upgrade is complete."))
    try:
        result = service_supabase.rpc("apply_commercial_access_command", {
            "p_tenant_id": tenant_id, "p_actor_user_id": actor_user_id, "p_aal": "aal2",
            "p_operation": operation, "p_idempotency_key": idempotency_key,
            "p_request_id": request_id, "p_payload": {"request": command, "quote": quote or {}},
        }).execute().data
        if (not isinstance(result, dict) or result.get("tenant_id") != tenant_id
            or result.get("operation") != operation or not isinstance(result.get("revision"), int)
            or isinstance(result.get("revision"), bool) or result["revision"] <= 0):
            raise ValueError("invalid_commercial_command_result")
        return result
    except Exception as error:
        # PostgREST SQL exceptions expose message/code through their structured
        # error object. Provider details are never returned to the client.
        message = getattr(error, "message", "")
        errors = {
            "commercial_revision_conflict": (409, "commercial_revision_conflict", "Commercial state changed. Reload and retry."),
            "commercial_idempotency_conflict": (409, "commercial_idempotency_conflict", "This command key was used for a different request."),
            "platform_admin_aal2_required": (403, "aal2_required", "MFA verification is required for this admin action."),
            "commercial_tenant_not_found": (404, "commercial_tenant_not_found", "Tenant was not found."),
        }
        if message in errors:
            status, code, text = errors[message]
        elif getattr(error, "code", None) in {"22023", "23514", "23P01", "23505", "P0002"}:
            status, code, text = 409, "commercial_command_conflict", "The commercial command is invalid or conflicts with current records."
        else:
            status, code, text = 503, "commercial_command_unavailable", "The commercial command could not be completed."
        logger.warning("commercial.command_failed", extra={"tenant_id": tenant_id, "actor_user_id": actor_user_id,
                       "operation": operation, "request_id": request_id, "error_code": code})
        raise HTTPException(status_code=status, detail=error_detail(code, text)) from error

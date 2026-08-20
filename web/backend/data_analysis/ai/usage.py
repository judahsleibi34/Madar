from __future__ import annotations

from datetime import date
from typing import Any

from database import service_supabase


def _date_value(usage_date: date | str | None) -> str:
    if usage_date is None:
        return date.today().isoformat()

    if isinstance(usage_date, date):
        return usage_date.isoformat()

    return str(usage_date)


def get_daily_ai_usage(
    *,
    user_id: int | str,
    usage_date: date | str | None = None,
) -> dict[str, int]:
    response = (
        service_supabase.table("ai_usage_daily")
        .select("message_count,code_generation_count")
        .eq("user_id", int(user_id))
        .eq("usage_date", _date_value(usage_date))
        .limit(1)
        .execute()
    )

    rows = response.data or []

    if not rows:
        return {
            "message_count": 0,
            "code_generation_count": 0,
        }

    row = rows[0]

    return {
        "message_count": int(row.get("message_count") or 0),
        "code_generation_count": int(row.get("code_generation_count") or 0),
    }


def get_global_daily_ai_usage(
    *,
    usage_date: date | str | None = None,
) -> dict[str, int]:
    response = (
        service_supabase.table("ai_usage_daily")
        .select("message_count,code_generation_count")
        .eq("usage_date", _date_value(usage_date))
        .execute()
    )

    rows = response.data or []

    return {
        "message_count": sum(int(row.get("message_count") or 0) for row in rows),
        "code_generation_count": sum(int(row.get("code_generation_count") or 0) for row in rows),
    }


def reserve_daily_ai_usage(
    *,
    user_id: int | str,
    tenant_id: int | str | None = None,
    usage_date: date | str | None = None,
    message_limit: int,
    code_generation_limit: int,
    message_delta: int = 1,
    code_generation_delta: int = 0,
) -> dict[str, int | bool]:
    params: dict[str, Any] = {
        "p_user_id": int(user_id),
        "p_tenant_id": int(tenant_id) if tenant_id is not None else None,
        "p_usage_date": _date_value(usage_date),
        "p_message_limit": int(message_limit),
        "p_code_generation_limit": int(code_generation_limit),
        "p_message_delta": max(int(message_delta), 0),
        "p_code_generation_delta": max(int(code_generation_delta), 0),
    }
    response = service_supabase.rpc("reserve_ai_usage_daily", params).execute()
    rows = response.data or []

    if not rows:
        current = get_daily_ai_usage(user_id=user_id, usage_date=usage_date)
        return {
            "accepted": False,
            **current,
        }

    row = rows[0]

    return {
        "accepted": bool(row.get("accepted")),
        "message_count": int(row.get("message_count") or 0),
        "code_generation_count": int(row.get("code_generation_count") or 0),
    }


def increment_daily_ai_usage(
    *,
    user_id: int | str,
    tenant_id: int | str | None = None,
    usage_date: date | str | None = None,
    message_delta: int = 1,
    code_generation_delta: int = 0,
) -> dict[str, int]:
    params: dict[str, Any] = {
        "p_user_id": int(user_id),
        "p_tenant_id": int(tenant_id) if tenant_id is not None else None,
        "p_usage_date": _date_value(usage_date),
        "p_message_delta": max(int(message_delta), 0),
        "p_code_generation_delta": max(int(code_generation_delta), 0),
    }
    response = service_supabase.rpc("increment_ai_usage_daily", params).execute()
    rows = response.data or []

    if not rows:
        return get_daily_ai_usage(user_id=user_id, usage_date=usage_date)

    row = rows[0]

    return {
        "message_count": int(row.get("message_count") or 0),
        "code_generation_count": int(row.get("code_generation_count") or 0),
    }

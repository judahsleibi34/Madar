"""Candidate167 recovery admission; never grants irreversible erasure authority."""
from fastapi import HTTPException


def require_capability(*, client):
    try:
        value = client.rpc("account_recovery_capability167", {}).execute().data
    except Exception:
        value = None
    if not isinstance(value, dict) or type(value.get("version")) is not int or value.get("version") != 1 \
            or type(value.get("recovery_hours")) is not int or value.get("recovery_hours") != 2160 \
            or value.get("permanent_erasure") is not False \
            or type(value.get("request_admission")) is not bool \
            or value.get("recovery_authority") != "aal2_system_admin":
        raise HTTPException(status_code=503, detail={"code": "account_recovery_upgrade_required",
            "message": "Account deletion is currently unavailable. Contact support."})
    return value


def require_request_admission(*, client):
    value = require_capability(client=client)
    if value["request_admission"] is not True:
        raise HTTPException(status_code=503, detail={"code": "account_recovery_acceptance_required",
            "message": "Account deletion is currently unavailable. Contact support."})


def recover(*, request_id: str, actor_user_id: int, client):
    require_capability(client=client)
    try:
        result = client.rpc("recover_account_deletion167", {
            "p_request_id": request_id, "p_actor_user_id": int(actor_user_id)}).execute().data
    except Exception:
        raise HTTPException(status_code=409, detail={"code": "account_recovery_unavailable",
            "message": "Account recovery could not be authorized safely."}) from None
    if not isinstance(result, dict) or result.get("state") != "cancelled_before_execution":
        raise HTTPException(status_code=503, detail="Account recovery was not acknowledged.")
    return result


def require_processing_account(*, tenant_id: int, user_id: int, client):
    """Fence new167 worker entry before network/filesystem work. Not a lease."""
    from services.project_dataset_service import schema_version
    version = schema_version(client=client)
    if 146 <= version <= 166:
        return
    if version != 167:
        raise HTTPException(status_code=503, detail="Account processing schema is unsupported.")
    rows = client.table("users").select("id,account_status").eq(
        "id", int(user_id)).eq("tenant_id", int(tenant_id)).limit(1).execute().data
    if not rows or rows[0].get("account_status") != "active":
        raise HTTPException(status_code=409, detail={"code": "account_processing_frozen",
            "message": "Account processing is disabled."})

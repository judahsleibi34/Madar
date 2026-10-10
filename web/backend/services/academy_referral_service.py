"""Tenant-scoped referral attribution; monetary credits are atomic SQL payment effects."""
from fastapi import HTTPException
from postgrest.exceptions import APIError
from database import service_supabase
from services.elearning_settings_service import settings_available


def account(member):
    if not settings_available(136):
        return {"available": False, "enabled": False, "balances": [], "history": []}
    return service_supabase.rpc("get_academy_referral_account", {
        "p_tenant_id": member.tenant_id, "p_user_id": member.user_id,
    }).execute().data


def attach(tenant_id, user_id, code):
    if not settings_available(136):
        raise HTTPException(503, detail={"code": "academy_referrals_upgrade_required"})
    try:
        service_supabase.rpc("attach_academy_referral", {
            "p_tenant_id": tenant_id, "p_referred_id": user_id, "p_code": code,
        }).execute()
    except APIError as error:
        if error.code in {"22023", "42501", "23505"}:
            raise HTTPException(400, detail={"code": "academy_referral_invalid"}) from error
        raise

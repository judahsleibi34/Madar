"""Tenant-scoped referral attribution; monetary credits are atomic SQL payment effects."""
from fastapi import HTTPException
from postgrest.exceptions import APIError
from database import service_supabase
from services.elearning_settings_service import settings_available
from services.academy_capability_service import require_capability, capabilities, permitted_wallet


def account(member):
    if not settings_available(136):
        return {"available": False, "enabled": False, "balances": [], "history": []}
    grants = capabilities(member.tenant_id)
    if not grants["referrals"]:
        return {"available": False, "enabled": False, "balances": [], "history": []}
    result = service_supabase.rpc("get_academy_referral_account", {
        "p_tenant_id": member.tenant_id, "p_user_id": member.user_id,
    }).execute().data
    if result.get('wallet'): result['wallet'] = permitted_wallet(result['wallet'], grants)
    if result.get('code'):
        result['clicks'] = own_clicks(member)
    return result


def own_clicks(member):
    """Clicks on the member's own referral link (counted by
    academy_record_referral_click); None when unavailable."""
    try:
        rows = service_supabase.table("academy_referral_codes").select("clicks").eq("tenant_id", member.tenant_id).eq("user_id", member.user_id).limit(1).execute().data or []
        return int(rows[0]["clicks"]) if rows else 0
    except Exception:
        return None


def attach(tenant_id, user_id, code):
    require_capability(tenant_id, "referrals")
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

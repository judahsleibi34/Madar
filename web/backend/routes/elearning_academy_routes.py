from urllib.parse import quote
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request, Response
from routes.public_site_routes import resolve_website_settings, resolve_tenant_id
from routes.elearning_structure_routes import operation
from services.tenant_service import require_active_tenant_member
from services.rate_limit_service import enforce_public_rate_limit
from services import elearning_academy_service as service

router = APIRouter(prefix="/public/academies", tags=["Learning Academy"])


def academy(identifier, request, response, course_id=None):
    enforce_public_rate_limit(request, "academy_lookup", identifier)
    website = resolve_website_settings(identifier, request=request)
    tenant_id = resolve_tenant_id(website)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Cookie"
    actor = None
    try:
        context = require_active_tenant_member(request, response, allow_admin_account_access=False, allow_learner=True)
        if context.tenant_id == tenant_id:
            actor = context
    except HTTPException as error:
        if error.status_code not in {401, 403}:
            raise
    return operation(lambda: service.storefront(tenant_id, website, actor, course_id))


@router.get("/{identifier}")
def home(identifier: str, request: Request, response: Response):
    return academy(identifier, request, response)


@router.get("/{identifier}/courses/{course_id}")
def course(identifier: str, course_id: UUID, request: Request, response: Response):
    return academy(identifier, request, response, course_id)


@router.get("/{identifier}/preview")
def preview(identifier: str, request: Request, response: Response):
    from services.elearning_access_service import require_elearning_access
    from services.entitlement_service import require_entitlement
    actor = require_elearning_access(request, response, "elearning.manage")
    require_entitlement(actor.tenant_id, "page_builder")
    website = resolve_website_settings(identifier, request=request)
    if resolve_tenant_id(website) != actor.tenant_id:
        raise HTTPException(403, "Academy preview tenant does not match session")
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Cookie"
    # Builder supplies the authorized draft; this endpoint supplies live data only.
    return operation(lambda: service.storefront(actor.tenant_id, website, actor, preview=True))


@router.post("/management/landing")
def initialize_landing(request: Request, response: Response):
    from services.elearning_access_service import require_elearning_access
    from services.elearning_settings_service import get_settings, settings_available
    from services.academy_builder_service import default_landing, validate_academy_schema
    from routes.builder_routes import require_supported_builder_client, require_builder_context, require_builder_write_access, require_any_entitlement, require_schema_asset_tenant
    from database import service_supabase
    require_supported_builder_client(request)
    actor = require_elearning_access(request, response, "elearning.manage")
    builder_actor = require_builder_context(request, response, require_builder_write_access)
    if builder_actor.tenant_id != actor.tenant_id or builder_actor.user_id != actor.user_id:
        raise HTTPException(403, detail={"code": "academy_management_forbidden"})
    require_any_entitlement(actor.tenant_id, {"page_builder"}, message="An active page-builder plan is required.")
    if not settings_available(133):
        raise HTTPException(503, detail={"code": "academy_builder_upgrade_required"})
    website_rows = service_supabase.table("website_settings").select("subdomain").eq("tenant_id", actor.tenant_id).limit(1).execute().data or []
    if not website_rows or not website_rows[0].get("subdomain"):
        raise HTTPException(409, detail={"code": "academy_address_required"})
    initial = default_landing(get_settings(actor.tenant_id), website_rows[0]["subdomain"])
    validate_academy_schema(initial)
    require_schema_asset_tenant(initial, actor.tenant_id)
    result = operation(lambda: service_supabase.rpc("ensure_academy_builder_project", {"p_tenant_id": actor.tenant_id, "p_user_id": actor.user_id, "p_initial_schema": initial}).execute())
    project = result.data if isinstance(result.data, dict) else (result.data[0] if result.data else None)
    if not project or not project.get("id"):
        raise HTTPException(409, detail={"code": "academy_project_missing"})
    return {"success": True, "project": project}



from pydantic import BaseModel, Field
from routes.public_site_routes import TenantLoginRequest, TenantRegisterRequest


class AcademyLoginRequest(TenantLoginRequest):
    return_to: str = Field(default="", max_length=2048)


class AcademyRegisterRequest(TenantRegisterRequest):
    return_to: str = Field(default="", max_length=2048)
    referral_code: UUID | None = None
    # Optional per-academy profile fields, required only when the academy's
    # published website asks for them (see registration_profile).
    country: str | None = Field(default=None, max_length=120)
    university: str | None = Field(default=None, max_length=200)
    terms_accepted: bool = False


def registration_profile(tenant_id, website):
    """The tenant-owned registration options stored in its published website."""
    from database import service_supabase
    from services.elearning_settings_service import settings_available
    if not website.get("academy_project_id") or not settings_available(132):
        return {}
    rows = service_supabase.table("builder_projects").select("published_schema").eq("id", website["academy_project_id"]).eq("tenant_id", tenant_id).eq("usage_profile", "academy").limit(1).execute().data or []
    value = ((rows[0].get("published_schema") or {}) if rows else {}).get("academyRegistration")
    return value if isinstance(value, dict) else {}


def institution_member(settings, email):
    """True when the email's domain (or a subdomain) is one of the owner's
    institution domains (Settings → Institution, e.g. PAU). This only selects
    the institution welcome and label; it never requires email confirmation,
    and it never marks a student verified (an admin does that manually)."""
    if not (settings or {}).get("institution_enabled"):
        return False
    domain = str(email).rsplit("@", 1)[-1].strip().lower()
    listed = [str(item).strip().lower() for item in settings.get("institution_email_domains", []) if str(item).strip()]
    return any(domain == item or domain.endswith("." + item) for item in listed)


def auth_return(payload, website, request):
    from services.academy_auth_service import safe_return_path
    from services.hosted_address_service import request_hosted_tenant
    base = "/academy" if request_hosted_tenant(request) else f"/academy/{website['subdomain']}"
    return safe_return_path(payload.return_to, base)


@router.post("/{identifier}/auth/login")
def login(identifier: str, payload: AcademyLoginRequest, request: Request, response: Response):
    from services.academy_auth_service import academy_auth_settings
    from routes.public_site_routes import login_tenant_account, get_tenant_staff_membership
    website, tenant_id, settings = academy_auth_settings(identifier, request)
    target = auth_return(payload, website, request)
    result = login_tenant_account(
        identifier,
        payload,
        request,
        response,
        allow_learning_membership=True,
        email_verification_required=settings.get("academy_email_verification_required", True),
    )
    user = result.get("user") or {}
    # The shared learning runtime uses the existing current tenant membership.
    if user.get("tenant_id") != tenant_id or not get_tenant_staff_membership(tenant_id, user.get("id")):
        raise HTTPException(403, "An active Academy tenant membership is required")
    return {**result, "return_to": target, "institution_member": institution_member(settings, payload.email)}


@router.post("/{identifier}/auth/register")
def register(identifier: str, payload: AcademyRegisterRequest, request: Request):
    from services.academy_auth_service import academy_auth_settings, verification_redirect
    from routes.public_site_routes import register_tenant_account
    website, tenant_id, settings = academy_auth_settings(identifier, request)
    if settings["academy_registration"] not in {"open", "email_domain"}:
        raise HTTPException(403, detail={"code": "academy_invitation_required"})
    if settings["academy_registration"] == "email_domain":
        from services.elearning_settings_service import normalize_academy_email_domain
        domain = normalize_academy_email_domain(str(payload.email).rsplit("@", 1)[1])
        if domain not in settings.get("academy_email_domains", []):
            raise HTTPException(403, detail={"code": "academy_email_domain_not_allowed"})
    profile_options = registration_profile(tenant_id, website)
    requested = {key for key in profile_options.get("fields", []) if key in {"country", "university"}}
    if "country" in requested and not (payload.country or "").strip():
        raise HTTPException(422, detail={"code": "academy_country_required"})
    if profile_options.get("requireTerms") and not payload.terms_accepted:
        raise HTTPException(422, detail={"code": "academy_terms_required"})
    profile = {key: getattr(payload, key).strip() for key in requested if (getattr(payload, key) or "").strip()}
    if profile_options.get("requireTerms"):
        from datetime import datetime, timezone
        profile["terms_accepted_at"] = datetime.now(timezone.utc).isoformat()
    target = auth_return(payload, website, request)
    # Shared registration sends a canonical tenant-hosted verification link.
    # Convert a compatible main-app URL to the equivalent path on that host.
    main_base = f"/academy/{website['subdomain']}"
    verification_target = target
    if target == main_base or target.startswith(main_base + "/"):
        verification_target = "/academy" + target[len(main_base):]
    result = register_tenant_account(identifier, payload, request, academy_context={"return_to": f"/academy/login?returnTo={quote(verification_target, safe='')}", "email_redirect_to": verification_redirect(website['subdomain'], request, target), "email_verification_required": settings.get("academy_email_verification_required", True), "referral_code": str(payload.referral_code) if payload.referral_code else None, "profile": profile})
    return {**result, "return_to": target, "institution_member": institution_member(settings, payload.email)}


@router.post('/{identifier}/referrals/{code}/click')
def referral_click(identifier: str, code: UUID, request: Request):
    from services.elearning_settings_service import settings_available
    from database import service_supabase
    enforce_public_rate_limit(request, 'academy_referral_click', identifier)
    website = resolve_website_settings(identifier, request=request)
    tenant_id = resolve_tenant_id(website)
    from services.academy_capability_service import capabilities
    if settings_available(139) and capabilities(tenant_id)["referrals"]:
        service_supabase.rpc('academy_record_referral_click', {'p_tenant': tenant_id, 'p_code': str(code)}).execute()
    # No disclosure of code ownership or private membership to an anonymous visitor.
    return {'success': True}

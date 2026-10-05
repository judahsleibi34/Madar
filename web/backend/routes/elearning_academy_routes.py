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
    if not settings_available(132):
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


def auth_return(payload, website, request):
    from services.academy_auth_service import safe_return_path
    from services.hosted_address_service import request_hosted_tenant
    base = "/academy" if request_hosted_tenant(request) else f"/academy/{website['subdomain']}"
    return safe_return_path(payload.return_to, base)


@router.post("/{identifier}/auth/login")
def login(identifier: str, payload: AcademyLoginRequest, request: Request, response: Response):
    from services.academy_auth_service import academy_auth_settings
    from routes.public_site_routes import login_tenant_account, get_tenant_staff_membership
    website, tenant_id, _ = academy_auth_settings(identifier, request)
    target = auth_return(payload, website, request)
    result = login_tenant_account(identifier, payload, request, response, allow_learning_membership=True)
    user = result.get("user") or {}
    # The shared learning runtime uses the existing current tenant membership.
    if user.get("tenant_id") != tenant_id or not get_tenant_staff_membership(tenant_id, user.get("id")):
        raise HTTPException(403, "An active Academy tenant membership is required")
    return {**result, "return_to": target}


@router.post("/{identifier}/auth/register")
def register(identifier: str, payload: AcademyRegisterRequest, request: Request):
    from services.academy_auth_service import academy_auth_settings
    from routes.public_site_routes import register_tenant_account
    website, _, settings = academy_auth_settings(identifier, request)
    if settings["academy_registration"] not in {"open", "email_domain"}:
        raise HTTPException(403, detail={"code": "academy_invitation_required"})
    if settings["academy_registration"] == "email_domain":
        from services.elearning_settings_service import normalize_academy_email_domain
        domain = normalize_academy_email_domain(str(payload.email).rsplit("@", 1)[1])
        if domain not in settings.get("academy_email_domains", []):
            raise HTTPException(403, detail={"code": "academy_email_domain_not_allowed"})
    target = auth_return(payload, website, request)
    # Shared registration sends a canonical tenant-hosted verification link.
    # Convert a compatible main-app URL to the equivalent path on that host.
    main_base = f"/academy/{website['subdomain']}"
    verification_target = target
    if target == main_base or target.startswith(main_base + "/"):
        verification_target = "/academy" + target[len(main_base):]
    result = register_tenant_account(identifier, payload, request, academy_context={"return_to": f"/academy/login?returnTo={quote(verification_target, safe='')}"})
    return {**result, "return_to": target}

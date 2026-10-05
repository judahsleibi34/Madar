"""Fixed public Academy projection; mutations stay in existing learning services."""
from fastapi import HTTPException
from postgrest.exceptions import APIError
from database import service_supabase
from services.elearning_settings_service import get_settings, settings_available


PUBLIC_SETTINGS = (
    "academy_registration", "academy_hero_title", "academy_hero_description", "academy_hero_image", "academy_cta_text",
    "academy_benefits", "course_label", "section_label", "lesson_label", "instructor_label",
)


def profile(tenant_id, website):
    cfg = get_settings(tenant_id)
    return {
        "subdomain": website["subdomain"],
        "brand": cfg["primary_display_name"] or website.get("brand") or cfg["platform_name"],
        "logo_url": cfg["logo_url"] or website.get("logo_url") or "",
        "description": cfg["description"] or website.get("description") or "",
        "theme": {key: value for key, value in (website.get("ecommerce_theme") or {}).items()
                  if key in {"accent", "text", "muted", "surface", "background"}},
        **{key: cfg[key] for key in PUBLIC_SETTINGS},
    }


def storefront(tenant_id, website, actor=None, course_id=None):
    if not settings_available(130):
        raise HTTPException(503, detail={"code": "academy_upgrade_required"})
    try:
        result = service_supabase.rpc("get_elearning_academy", {
            "p_tenant_id": tenant_id, "p_user_id": actor.user_id if actor else None,
            "p_course_id": str(course_id) if course_id else None,
        }).execute().data
    except APIError as error:
        if error.code == "P0002":
            raise HTTPException(404, "Academy content not found") from error
        if error.code == "42501":
            raise HTTPException(403, "Academy access denied") from error
        raise
    continuing = []
    if actor and course_id is None:
        # Consume the existing bounded My Learning feed, including authorized
        # private courses. These records never enter the public catalog.
        learning = service_supabase.rpc("get_elearning_my_learning", {
            "p_tenant_id": tenant_id, "p_user_id": actor.user_id, "p_limit": 101, "p_offset": 0,
        }).execute().data or []
        public_cards = {card["id"]: card for card in result["courses"]}
        for runtime in learning:
            progress = runtime["progress"]
            if progress.get("progress_status") != "active":
                continue
            course = runtime["course"]
            resume = f"/my-learning/courses/{course['id']}"
            if runtime.get("continue_lesson_id"):
                resume += f"/lessons/{runtime['continue_lesson_id']}"
            elif runtime.get("continue_assessment_id"):
                resume += f"/assessments/{runtime['continue_assessment_id']}"
            continuing.append(public_cards.get(course["id"]) or {
                **course, "cover_asset": course.get("cover_url"), "cta": {"action": "continue"},
                "progress": progress, "resume": resume, "view_path": resume,
                "plans": [], "instructors": [], "outline": [], "credential": runtime.get("credential"),
            })
            if len(continuing) == 3:
                break
    from services.academy_builder_service import default_landing, validate_academy_schema
    landing = default_landing(get_settings(tenant_id), website["subdomain"])
    if settings_available(131) and website.get("academy_project_id"):
        projects = service_supabase.table("builder_projects").select("published_schema,status").eq("id", website["academy_project_id"]).eq("tenant_id", tenant_id).eq("usage_profile", "academy").limit(1).execute().data or []
        if projects and projects[0].get("status") == "published" and projects[0].get("published_schema"):
            landing = validate_academy_schema(projects[0]["published_schema"])
    instructors = []
    if settings_available(132):
        instructors = service_supabase.rpc("get_academy_public_instructors", {"p_tenant_id": tenant_id, "p_course_ids": [card["id"] for card in result["courses"]]}).execute().data or []
    site = profile(tenant_id, website)
    if actor and actor.role in {"owner", "admin"}:
        site["management_path"] = "/e-learning/settings/academy"
    return {**result, "continue_courses": continuing, "instructors": instructors, "site": site, "landing": landing}


def member_profile(tenant_id):
    # Navigation only, no commerce/account data and no second branding store.
    cfg = get_settings(tenant_id)
    if not cfg["enabled"] or not cfg["academy_enabled"] or not settings_available(130):
        return None
    rows = (service_supabase.table("website_settings").select("subdomain,brand,logo_url,description,ecommerce_theme")
            .eq("tenant_id", tenant_id).limit(1).execute()).data or []
    return profile(tenant_id, rows[0]) if rows and rows[0].get("subdomain") else None

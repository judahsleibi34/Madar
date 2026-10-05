"""Academy composition profile for the existing Builder engine."""
from uuid import UUID, uuid4
from fastapi import HTTPException

ALLOWED_TYPES = frozenset({"heading", "text", "button", "image", "imageButton", "imageCardButton", "card", "carousel", "logoSlider", "list", "divider", "thinDivider", "metric", "academyFeaturedCourses", "academyCourseCollection", "academyPlans", "academyContinueLearning", "academyInstructors"})
DATA_TYPES = frozenset(t for t in ALLOWED_TYPES if t.startswith("academy"))
DATA_FIELDS = {"heading", "description", "maxItems", "courseIds", "planIds", "variant", "featuredOnly", "instructorIds"}


def management_profile(tenant_id):
    """Owner-only navigation metadata; reuse persisted Builder state without seeding."""
    from database import service_supabase
    from services.elearning_settings_service import settings_available
    if not settings_available(131):
        return None
    websites = service_supabase.table("website_settings").select("subdomain,academy_project_id" + (",academy_editor_project_id" if settings_available(132) else "")).eq("tenant_id", tenant_id).limit(1).execute().data or []
    projects = service_supabase.table("builder_projects").select("id,status,draft_revision,published_revision,last_published_at,draft_schema,published_schema").eq("tenant_id", tenant_id).eq("usage_profile", "academy").neq("status", "archived").order("created_at").limit(1).execute().data or []
    editor = websites[0].get("academy_editor_project_id") if websites else None
    if editor and settings_available(132):
        bound = service_supabase.table("builder_projects").select("*").eq("tenant_id", tenant_id).eq("id", editor).eq("usage_profile", "academy").neq("status", "archived").limit(1).execute().data or []
        if bound: projects = bound
    return {"editor_project_id": editor, "full_builder_available": settings_available(132), "subdomain": websites[0].get("subdomain") if websites else None, "published_project_id": websites[0].get("academy_project_id") if websites else None, "landing_project": projects[0] if projects else None}


def validate_academy_schema(schema):
    def reject():
        raise HTTPException(400, detail={"code": "academy_component_not_allowed", "message": "This component or data is not allowed in an Academy landing page."})
    if not isinstance(schema, dict) or not isinstance(schema.get("pages"), list) or not 1 <= len(schema["pages"]) <= 50:
        reject()
    from services.elearning_settings_service import settings_available
    def has_instructors(value):
        if isinstance(value, dict):
            return value.get("type") == "academyInstructors" or any(has_instructors(child) for child in value.values())
        return isinstance(value, list) and any(has_instructors(child) for child in value)
    if (len(schema["pages"]) > 1 or has_instructors(schema)) and not settings_available(132):
        raise HTTPException(503, detail={"code": "academy_builder_upgrade_required"})
    reserved = {"courses", "plans", "login", "signup", "auth", "my-learning", "account", "checkout", "assessments", "api", "admin", "dashboard", "settings", "builder", "page-builder"}
    import re
    slugs, ids = set(), set()
    for page in schema["pages"]:
        if not isinstance(page, dict): reject()
        slug, page_id = page.get("slug"), page.get("id")
        if not isinstance(slug, str) or not re.fullmatch(r"/([a-z0-9-]+(?:/[a-z0-9-]+)*)?", slug) or slug.strip("/").split("/")[0] in reserved or slug in slugs or not isinstance(page_id, str) or not page_id or page_id in ids or page.get("access", "public") != "public": reject()
        slugs.add(slug); ids.add(page_id)
    if "/" not in slugs: reject()
    for collection in ("forms", "collections", "workflows", "roles", "users"):
        if schema.get(collection):
            reject()
    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"elements", "freeElements"}:
                    if not isinstance(child, list):
                        reject()
                    for element in child:
                        if not isinstance(element, dict) or not isinstance(element.get("type"), str) or element.get("type") not in ALLOWED_TYPES:
                            reject()
                        if element["type"] in DATA_TYPES:
                            allowed = {"id", "type", "name", "content", "mode", "position", "styles", "action", "connectedFormId", "academy"}
                            if set(element) - allowed:
                                reject()
                            config = element.get("academy", {})
                            if not isinstance(config, dict) or set(config) - DATA_FIELDS:
                                reject()
                            if not isinstance(config.get("variant", "grid"), str) or config.get("variant", "grid") not in {"grid", "compact"}:
                                reject()
                            for field, maximum in (("heading", 160), ("description", 1200)):
                                if field in config and (not isinstance(config[field], str) or len(config[field]) > maximum):
                                    reject()
                            if "featuredOnly" in config and not isinstance(config["featuredOnly"], bool):
                                reject()
                            maximum = config.get("maxItems", 4)
                            if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 24:
                                reject()
                            for ids_key in ("courseIds", "planIds", "instructorIds"):
                                ids = config.get(ids_key, [])
                                if not isinstance(ids, list) or len(ids) > 24:
                                    reject()
                                try:
                                    for item in ids:
                                        UUID(str(item))
                                except (ValueError, TypeError):
                                    reject()
                        if element.get("connectedFormId"):
                            reject()
                        action = element.get("action") or {}
                        if not isinstance(action, dict):
                            reject()
                        if not isinstance(action.get("type", "none"), str) or action.get("type", "none") not in {"none", "openUrl", "scrollToSection", "goToPage"}:
                            reject()
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(schema)
    return schema


def default_landing(settings, subdomain):
    """Translate saved schema-130 presentation without overwriting it."""
    def uid(prefix):
        return f"{prefix}_{uuid4().hex}"
    def element(kind, content="", **extra):
        return {"id": uid("element"), "type": kind, "name": kind, "content": content,
                "styles": {"width": "100%"} if kind in DATA_TYPES else {}, "action": {"type": "none"}, **extra}
    base = f"/academy/{subdomain}"
    blocks = [
        ("Hero", [element("heading", settings.get("academy_hero_title") or settings.get("primary_display_name") or settings["platform_name"], headingTag="h1"), element("text", settings.get("academy_hero_description") or settings.get("description", "")), element("button", settings.get("academy_cta_text") or "Explore courses", action={"type": "openUrl", "url": f"{base}/courses"})]),
        ("Continue Learning", [element("academyContinueLearning", academy={"heading": "Continue Learning", "maxItems": 3})]),
        ("Featured Courses", [element("academyFeaturedCourses", academy={"heading": "Featured Courses", "maxItems": 4, "courseIds": settings.get("academy_featured_courses", [])})]),
        ("Course Collection", [element("academyCourseCollection", academy={"heading": "Explore Courses", "maxItems": 4})]),
        ("Plans / Pricing", [element("academyPlans", academy={"heading": "Choose your access", "maxItems": 4})]),
        ("Benefits", [element("heading", "Learn at your own pace"), element("text", settings.get("academy_benefits") or "Build your skills with focused lessons, audio and video.")]),
        ("CTA", [element("heading", "Start learning"), element("button", settings.get("academy_cta_text") or "Explore courses", action={"type": "openUrl", "url": f"{base}/courses"})]),
    ]
    if settings.get("academy_hero_image"):
        blocks[0][1].append(element("image", settings["academy_hero_image"]))
    page_id = uid("page")
    sections = [{"id": uid("section"), "name": name, "layout": {"width": "large", "paddingY": "medium", "minHeight": 320 if name == "Hero" else 200}, "rows": [{"id": uid("row"), "columns": [{"id": uid("column"), "elements": elements}]}]} for name, elements in blocks]
    return {"version": 1, "name": "Academy Landing", "defaultPageId": page_id, "activePageId": page_id, "pages": [{"id": page_id, "name": "Academy Home", "slug": "/", "isDefault": True, "access": "public", "sections": sections}], "forms": [], "collections": [], "workflows": [], "users": [], "roles": [], "siteChrome": {"brand": settings.get("primary_display_name") or settings["platform_name"], "footerStoreName": settings.get("primary_display_name") or settings["platform_name"], "rights": "", "footerSocialLinks": "", "footerPaymentMethods": "", "logoUrl": settings.get("logo_url", ""), "description": settings.get("description", ""), "showHeader": True, "showFooter": True, "headerButtonLabel": "Courses", "headerButtonHref": base + "/courses", "footerShopLinks": "", "footerHelpLinks": "", "contactEmail": "", "phone": ""}}

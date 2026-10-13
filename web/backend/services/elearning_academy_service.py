"""Fixed public Academy projection; mutations stay in existing learning services."""
from fastapi import HTTPException
from postgrest.exceptions import APIError
from database import service_supabase
from services.elearning_settings_service import get_settings, settings_available
from services.entitlement_service import require_public_runtime_entitlement, get_tenant_entitlements


PUBLIC_SETTINGS = (
    "academy_registration", "academy_hero_title", "academy_hero_description", "academy_hero_image", "academy_cta_text",
    "certificates_enabled", "academy_benefits", "course_label", "section_label", "lesson_label", "instructor_label",
)


def form_application_paths(tenant_id,website,schema):
    """Navigation from published placements and current tenant Form bindings."""
    if not settings_available(144) or not isinstance(schema,dict):return {}
    references={}
    def walk(value,path):
        if isinstance(value,dict):
            if value.get('type')=='academyForm' and value.get('academy',{}).get('formId'):references.setdefault(value['academy']['formId'],path)
            for child in value.values():walk(child,path)
        elif isinstance(value,list):
            for child in value:walk(child,path)
    for page in schema.get('pages',[]):
        walk(page,f"/academy/{website['subdomain']}"+(page['slug'] if page['slug']!='/' else ''))
    if not references:return {}
    forms=service_supabase.table('elearning_forms').select('id,version').eq('tenant_id',tenant_id).eq('status','active').in_('id',list(references)).limit(100).execute().data or []
    if not forms:return {}
    filters=','.join(f"and(form_id.eq.{row['id']},version.eq.{row['version']})" for row in forms)
    versions=service_supabase.table('elearning_form_versions').select('form_id,schema').eq('tenant_id',tenant_id).or_(filters).limit(100).execute().data or []
    paths={}
    for row in versions:
        kind=row['schema'].get('workflow',{}).get('kind')
        if kind in {'affiliate','tuition','exchange'}:paths.setdefault(kind,references[row['form_id']])
    return paths


def attach_public_topics(tenant_id, courses):
    """Published topic names let guests preview a course; lesson content and drafts stay private."""
    ids = [card["id"] for card in courses if card.get("outline")]
    if not ids:
        return
    sections = (service_supabase.table("elearning_sections").select("id,course_id,name").eq("tenant_id", tenant_id).eq("status", "published")
                .in_("course_id", ids).order("position").order("id").limit(2000).execute().data or [])
    lessons = (service_supabase.table("elearning_lessons").select("section_id,name").eq("tenant_id", tenant_id).eq("status", "published")
               .in_("course_id", ids).order("position").order("id").limit(5000).execute().data or [])
    topics, by_course = {}, {}
    for lesson in lessons:
        topics.setdefault(lesson["section_id"], []).append(lesson["name"])
    for section in sections:
        by_course.setdefault(section["course_id"], []).append(section)
    for card in courses:
        published = by_course.get(card["id"], [])
        # The RPC outline uses the same published filter and order; skip on any drift.
        if [s["name"] for s in published] != [entry["name"] for entry in card.get("outline") or []]:
            continue
        for entry, section in zip(card["outline"], published):
            entry["topics"] = topics.get(section["id"], [])[:entry["lesson_count"]]


def profile(tenant_id, website, academy_theme=None, application_paths=None):
    cfg = get_settings(tenant_id)
    return {
        "subdomain": website["subdomain"],
        "brand": cfg["primary_display_name"] or website.get("brand") or cfg["platform_name"],
        "logo_url": cfg["logo_url"] or website.get("logo_url") or "",
        "description": cfg["description"] or website.get("description") or "",
        "application_paths":application_paths or {},
        "theme": {key: value for key, value in (academy_theme if isinstance(academy_theme,dict) else website.get("ecommerce_theme") or {}).items()
                  if key in {"primary", "accent", "accentDark", "buttonText", "text", "muted", "surface", "softSurface", "background", "border", "fontFamily"}},
        **{key: cfg[key] for key in PUBLIC_SETTINGS},
    }


def storefront(tenant_id, website, actor=None, course_id=None, *, preview=False):
    if not settings_available(131):
        raise HTTPException(503, detail={"code": "academy_upgrade_required"})
    if not preview:
        require_public_runtime_entitlement({**website, 'tenant_id': tenant_id}, 'website_publish')
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
    attach_public_topics(tenant_id, result["courses"])
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
    if settings_available(132) and website.get("academy_project_id"):
        projects = service_supabase.table("builder_projects").select("published_schema,status").eq("id", website["academy_project_id"]).eq("tenant_id", tenant_id).eq("usage_profile", "academy").limit(1).execute().data or []
        if not projects or projects[0].get("status") != "published" or not projects[0].get("published_schema"):
            if not preview:
                raise HTTPException(404, "Academy website not published")
        else:
            landing = validate_academy_schema(projects[0]["published_schema"])
    instructors = []
    if settings_available(133):
        instructors = service_supabase.rpc("get_academy_public_instructors", {"p_tenant_id": tenant_id, "p_course_ids": [card["id"] for card in result["courses"]]}).execute().data or []
    site = profile(tenant_id, website, landing.get('theme'),form_application_paths(tenant_id,website,landing))
    if learning_experience(landing).get("liveEnrollmentOnly"):
        # Opt-in academies show "Enrollment opens soon" until a live provider is set.
        from services.elearning_commerce_service import enrollment_open, payment_state
        site["enrollment"] = {"open": enrollment_open(payment_state())}
    if actor and actor.role in {"owner", "admin"}:
        site["management_path"] = "/e-learning/settings/academy"
    contact_enabled = False
    from routes.builder_routes import schema_contains_element_type
    if settings_available(140) and schema_contains_element_type(landing, "academyContact"):
        from services.academy_capability_service import capabilities
        contact_enabled = capabilities(tenant_id)["contact"]
    programme_info = None
    opportunities = []
    if settings_available(140):
        from services.academy_capability_service import capabilities
        cfg = get_settings(tenant_id)
        if cfg.get('programmes_enabled'):
            grants = capabilities(tenant_id)
            programme_info = {key: cfg[key] for capability, key in [('affiliate', 'affiliate_terms'), ('tuition', 'support_programme_name'), ('tuition', 'tuition_terms'), ('exchange', 'exchange_programme_name'), ('exchange', 'exchange_terms')] if grants[capability] and cfg.get({'affiliate':'affiliates_enabled','tuition':'tuition_support_enabled','exchange':'exchange_programme_enabled'}[capability])}
            exchange_available = grants['exchange'] and grants['forms'] and settings_available(142) and cfg['exchange_programme_enabled']
            if exchange_available:
                entitlements = get_tenant_entitlements(tenant_id)
                exchange_available = 'public_form_links' in entitlements.get('operational_capabilities', entitlements.get('capabilities', []))
            if not exchange_available:
                programme_info = {key: value for key, value in programme_info.items() if key not in {'exchange_programme_name', 'exchange_terms'}}
            if exchange_available:
                opportunities = service_supabase.rpc('get_academy_open_opportunities', {'p_tenant': tenant_id, 'p_user': None, 'p_limit': 24}).execute().data or []
    return {**result, 'contact_enabled': contact_enabled, 'programme_info': programme_info, 'exchange_opportunities': opportunities, "continue_courses": continuing, "instructors": instructors, "site": site, "landing": landing}


def member_profile(tenant_id):
    # Navigation only, no commerce/account data and no second branding store.
    cfg = get_settings(tenant_id)
    if not cfg["enabled"] or not cfg["academy_enabled"] or not settings_available(131):
        return None
    rows = (service_supabase.table("website_settings").select("subdomain,brand,logo_url,description,ecommerce_theme" + (",academy_project_id" if settings_available(132) else ""))
            .eq("tenant_id", tenant_id).limit(1).execute()).data or []
    if not rows or not rows[0].get('subdomain'):return None
    theme=None;schema=None
    if rows[0].get('academy_project_id') and settings_available(132):
        projects=service_supabase.table('builder_projects').select('published_schema,status').eq('tenant_id',tenant_id).eq('id',rows[0]['academy_project_id']).eq('usage_profile','academy').limit(1).execute().data or []
        if projects and projects[0]['status']=='published':
            schema=projects[0].get('published_schema') or {};theme=schema.get('theme')
    return {**profile(tenant_id, rows[0], theme,form_application_paths(tenant_id,rows[0],schema)), "experience": learning_experience(schema)}


# Opt-in learner-app improvements, switched on per academy in its own website.
EXPERIENCE_FLAGS = frozenset({"lessonComponents", "studentDashboard", "liveEnrollmentOnly"})


def learning_experience(schema):
    value = (schema or {}).get("academyExperience")
    return {key: value[key] is True for key in EXPERIENCE_FLAGS if key in value} if isinstance(value, dict) else {}


def experience_for_tenant(tenant_id):
    """The academy's opt-in flags from its published website ({} when none)."""
    try:
        if not settings_available(132):
            return {}
        rows = service_supabase.table("website_settings").select("academy_project_id").eq("tenant_id", tenant_id).limit(1).execute().data or []
        project = rows[0].get("academy_project_id") if rows else None
        if not project:
            return {}
        projects = service_supabase.table("builder_projects").select("published_schema,status").eq("tenant_id", tenant_id).eq("id", project).eq("usage_profile", "academy").limit(1).execute().data or []
        return learning_experience(projects[0].get("published_schema")) if projects and projects[0].get("status") == "published" else {}
    except Exception:
        return {}


def institution_for_member(tenant_id, user_id):
    """Institution (e.g. PAU) membership for the signed-in learner: the email
    domain matches the owner's Settings → Institution domains. Selects the
    welcome and "PAU Student" label only; it never marks anyone verified."""
    try:
        cfg = get_settings(tenant_id)
        if not cfg.get("institution_enabled") or not cfg.get("institution_email_domains"):
            return None
        rows = service_supabase.table("users").select("email").eq("id", user_id).limit(1).execute().data or []
        email = (rows[0].get("email") if rows else "") or ""
        from routes.elearning_academy_routes import institution_member
        if not institution_member(cfg, email):
            return None
        return {"member": True, "name": cfg.get("institution_name") or "", "label": cfg.get("institution_student_label") or ""}
    except Exception:
        return None

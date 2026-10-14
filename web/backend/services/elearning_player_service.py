"""Private learner runtime backed by the existing enrollment/progress engine."""
from fastapi import HTTPException
from postgrest.exceptions import APIError
from database import service_supabase
from services.elearning_settings_service import settings_available, get_settings


def call(name, member, **args):
    if not settings_available(125):
        raise HTTPException(503, detail={"code": "elearning_player_upgrade_required"})
    try:
        return service_supabase.rpc(name, {"p_tenant_id": member.tenant_id, "p_user_id": member.user_id, **args}).execute().data
    except APIError as error:
        if error.code == "P0002": raise HTTPException(404, "Learning content not found") from error
        if error.code == "42501": raise HTTPException(403, detail={"code": "elearning_assessment_required" if error.message == "elearning_assessment_required" else "elearning_lesson_locked"}) from error
        raise


def my_learning(member, limit, offset):
    courses = call("get_elearning_my_learning", member, p_limit=limit + 1, p_offset=offset)
    from services.elearning_academy_service import member_profile
    settings = get_settings(member.tenant_id)
    academy = member_profile(member.tenant_id) if settings.get("enabled") and settings.get("academy_enabled") else None
    if academy:
        from services.elearning_academy_service import institution_for_member
        institution = institution_for_member(member.tenant_id, member.user_id)
        if institution:
            academy = {**academy, "institution": institution}
    if academy and member.role in {"owner", "admin"}:
        academy = {**academy, "management_path": "/e-learning/settings/academy"}
    return {**({"academy": academy} if academy else {}), "courses": courses[:limit], "has_more": len(courses) > limit, "settings": settings}


def course(member, course_id, lesson_id=None, complete=False):
    result = call("complete_elearning_learner_lesson" if complete else "get_elearning_learner_course", member,
                  p_course_id=str(course_id), p_lesson_id=str(lesson_id) if lesson_id else None)
    return with_question_types(member.tenant_id, result)


def with_question_types(tenant_id, result):
    """Add each lesson assessment's question TYPES (never prompts or answers) so
    the opt-in lesson step tracker can place it in the book's topic order."""
    blocks = (result or {}).get("blocks") if isinstance(result, dict) else None
    ids = [block["assessment"]["id"] for block in blocks or [] if block.get("type") == "assessment" and isinstance(block.get("assessment"), dict) and block["assessment"].get("id")]
    if not ids:
        return result
    try:
        rows = service_supabase.table("elearning_assessment_questions").select("assessment_id,type").eq("tenant_id", tenant_id).in_("assessment_id", ids).is_("archived_at", "null").execute().data or []
    except Exception:
        return result
    types = {}
    for row in rows:
        types.setdefault(row["assessment_id"], set()).add(row["type"])
    for block in blocks:
        assessment = block.get("assessment") if block.get("type") == "assessment" else None
        if isinstance(assessment, dict) and assessment.get("id") in types:
            assessment["question_types"] = sorted(types[assessment["id"]])
    return result



def media_access(tenant_id, user_id, storage_key):
    # Old compatible schemas retain their existing file rules; player APIs fail closed.
    if not settings_available(125): return True
    result = service_supabase.rpc("elearning_learner_media_access", {"p_tenant_id": tenant_id, "p_user_id": user_id, "p_storage_key": storage_key}).execute().data
    if result is not None and type(result) is not bool: raise ValueError("Invalid learning media authorization")
    return result is not False

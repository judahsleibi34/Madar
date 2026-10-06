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
    if academy and member.role in {"owner", "admin"}:
        academy = {**academy, "management_path": "/e-learning/settings/academy"}
    return {**({"academy": academy} if academy else {}), "courses": courses[:limit], "has_more": len(courses) > limit, "settings": settings}


def course(member, course_id, lesson_id=None, complete=False):
    return call("complete_elearning_learner_lesson" if complete else "get_elearning_learner_course", member,
                p_course_id=str(course_id), p_lesson_id=str(lesson_id) if lesson_id else None)



def media_access(tenant_id, user_id, storage_key):
    # Old compatible schemas retain their existing file rules; player APIs fail closed.
    if not settings_available(125): return True
    result = service_supabase.rpc("elearning_learner_media_access", {"p_tenant_id": tenant_id, "p_user_id": user_id, "p_storage_key": storage_key}).execute().data
    if result is not None and type(result) is not bool: raise ValueError("Invalid learning media authorization")
    return result is not False

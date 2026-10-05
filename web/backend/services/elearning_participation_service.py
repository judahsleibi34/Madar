"""Tenant-owned learner profiles and lesson-derived progress; no payment engine."""
from typing import Literal
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from postgrest.exceptions import APIError
from database import service_supabase
from services.elearning_settings_service import settings_available


class LearnerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    status: Literal["active", "archived"] = "active"

    @field_validator("email")
    @classmethod
    def email_address(cls, value):
        value = value.lower()
        if value.count("@") != 1 or any(char.isspace() for char in value) or not all(value.split("@")):
            raise ValueError("A valid contact email is required")
        return value


class LearnerUpdate(LearnerPayload):
    expected_revision: int = Field(ge=1, strict=True)


class EnrollmentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    learner_id: UUID
    access_source: Literal["free", "manual"] = "manual"


class CompletionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completed: StrictBool


def participation_available():
    return settings_available(120)


def require_available():
    if not participation_available():
        raise HTTPException(503, detail={"code": "elearning_participation_upgrade_required", "message": "Learners and progress require the database upgrade."})


def translate(error):
    if error.code == "P0002": raise HTTPException(404, "Learning record not found") from error
    if error.code == "42501": raise HTTPException(403, "Tenant owner or admin access required") from error
    if error.code == "23505": raise HTTPException(409, "This learner email already exists in this tenant") from error
    if error.code in {"22023", "23503", "23514"}:
        raise HTTPException(400, "Only active learners and published course content may be enrolled or completed; use free access for free courses or explicit manual assignment") from error
    raise error


def list_learners(tenant_id, limit=50, offset=0):
    if not participation_available(): return {"available": False, "learners": [], "has_more": False}
    rows = service_supabase.table("elearning_learners").select("*").eq("tenant_id", tenant_id).order("name").order("id").range(offset, offset + limit).execute().data or []
    return {"available": True, "learners": rows[:limit], "has_more": len(rows) > limit}


def save_learner(tenant_id, user_id, payload, learner_id=None):
    require_available()
    values = payload.model_dump(exclude={"expected_revision"})
    try:
        if learner_id is None:
            rows = service_supabase.table("elearning_learners").insert({**values, "tenant_id": tenant_id, "created_by": user_id}).execute().data
        else:
            current = service_supabase.table("elearning_learners").select("id").eq("tenant_id", tenant_id).eq("id", str(learner_id)).limit(1).execute().data
            if not current: raise HTTPException(404, "Learner not found")
            rows = service_supabase.table("elearning_learners").update({**values, "revision": payload.expected_revision + 1}).eq("tenant_id", tenant_id).eq("id", str(learner_id)).eq("revision", payload.expected_revision).execute().data
            if not rows: raise HTTPException(409, "Learner changed. Reload before saving.")
        return {"learner": rows[0]}
    except APIError as error: translate(error)


def command(tenant_id, course_id, user_id, action, payload):
    require_available()
    try:
        return service_supabase.rpc("manage_elearning_participation", {"p_tenant_id": tenant_id, "p_course_id": str(course_id), "p_user_id": user_id, "p_action": action, "p_payload": payload}).execute().data
    except APIError as error: translate(error)


def progress(tenant_id, course_id):
    require_available()
    try:
        return service_supabase.rpc("get_elearning_progress", {"p_tenant_id": tenant_id, "p_course_id": str(course_id)}).execute().data
    except APIError as error: translate(error)


class UserEnrollmentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_ids: list[int] = Field(min_length=1, max_length=100)
    access_source: Literal["free", "manual"] = "manual"

    @field_validator("user_ids", mode="before")
    @classmethod
    def strict_user_ids(cls, value):
        if not isinstance(value, list) or any(type(item) is not int or item < 1 for item in value) or len(value) != len(set(value)):
            raise ValueError("Select unique existing user IDs")
        return value


class EnrollmentStatusPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["suspend", "reactivate", "cancel"]
    expected_status: Literal["active", "suspended", "archived"]
    confirmed: StrictBool = False


def require_enrollment_management():
    if not settings_available(122):
        raise HTTPException(503, detail={"code": "elearning_enrollment_upgrade_required", "message": "Enrollment management requires the database upgrade."})


def enrollment_report(tenant_id, course_id):
    require_enrollment_management()
    try:
        return service_supabase.rpc("get_elearning_enrollment_report", {"p_tenant_id": tenant_id, "p_course_id": str(course_id)}).execute().data
    except APIError as error: translate(error)


def enrollment_candidates(tenant_id, course_id, query, limit, offset):
    require_enrollment_management()
    try:
        rows = service_supabase.rpc("get_elearning_enrollment_candidates", {"p_tenant_id": tenant_id, "p_course_id": str(course_id), "p_query": query.strip(), "p_limit": limit, "p_offset": offset}).execute().data or []
        return {"users": rows[:limit], "has_more": len(rows) > limit}
    except APIError as error: translate(error)


def manage_enrollments(tenant_id, course_id, actor_id, payload, enrollment_id=None):
    require_enrollment_management()
    if enrollment_id is not None and payload.action in {"suspend", "cancel"} and not payload.confirmed:
        raise HTTPException(400, "Confirm the enrollment access change")
    args = {"p_tenant_id": tenant_id, "p_course_id": str(course_id), "p_actor_id": actor_id, "p_action": "enroll_users" if enrollment_id is None else payload.action, "p_user_ids": payload.user_ids if enrollment_id is None else None, "p_enrollment_id": str(enrollment_id) if enrollment_id else None, "p_expected_status": payload.expected_status if enrollment_id else None, "p_access_source": payload.access_source if enrollment_id is None else None, "p_confirmed": payload.confirmed if enrollment_id else False}
    try:
        return service_supabase.rpc("manage_elearning_enrollments", args).execute().data
    except APIError as error:
        if error.code == "23505": raise HTTPException(409, detail={"code": "elearning_already_enrolled", "message": "One or more selected users are already enrolled. No enrollments were changed."}) from error
        if error.code == "P0001": raise HTTPException(409, "Enrollment changed. Reload before trying again.") from error
        translate(error)

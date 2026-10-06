"""Stable course entities; learning labels are presentation-only settings."""
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from postgrest.exceptions import APIError
from database import service_supabase
from services.asset_registry_service import ASSET_URL_PATTERN
from services.elearning_settings_service import require_owned_image, settings_available
from services.elearning_structure_service import structure_available
from services.elearning_participation_service import participation_available


class CoursePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    cover_asset: str = Field(default="", max_length=2048)
    status: Literal["draft", "published", "archived"] = "draft"
    access_type: Literal["free", "paid", "private"] = "private"
    catalog_visible: StrictBool | None = None

    @field_validator("cover_asset")
    @classmethod
    def validate_cover(cls, value):
        if value and (not ASSET_URL_PATTERN.fullmatch(value) or not value.endswith((".png", ".jpg", ".webp"))):
            raise ValueError("Cover must be a managed PNG, JPG, or WebP image")
        return value


class CourseUpdate(CoursePayload):
    expected_revision: int = Field(ge=1, strict=True)


class CourseCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1, strict=True)


class CourseDelete(CourseCommand):
    expected_structure_revision: int = Field(ge=1, strict=True)
    confirmation_name: str = Field(min_length=1, max_length=120)
    confirmed: StrictBool


def courses_available():
    return settings_available(118)


def require_courses_available():
    if not courses_available():
        raise HTTPException(status_code=503, detail={"code": "elearning_courses_upgrade_required", "message": "Courses are unavailable until the database upgrade completes."})


def present_course(row, counts=None, deletion_available=False):
    return {**row, "section_count": (counts or {}).get("section_count", 0), "lesson_count": (counts or {}).get("lesson_count", 0), "learner_count": (counts or {}).get("learner_count", 0), "average_progress": (counts or {}).get("average_progress", 0), "deletion_available": deletion_available}


def present_courses(rows, tenant_id):
    counts = {}
    if rows and structure_available():
        counts = service_supabase.rpc("get_elearning_course_counts", {"p_tenant_id": tenant_id, "p_course_ids": [row["id"] for row in rows]}).execute().data or {}
    if rows and participation_available():
        participation = service_supabase.rpc("get_elearning_participation_counts", {"p_tenant_id": tenant_id, "p_course_ids": [row["id"] for row in rows]}).execute().data or {}
        for key, value in participation.items():
            counts[key] = {**counts.get(key, {}), **value}
    deletion_available = settings_available(122) if rows else False
    return [present_course(row, counts.get(row["id"]), deletion_available) for row in rows]


def list_courses(tenant_id, limit=50, offset=0):
    rows = (service_supabase.table("elearning_courses").select("*")
            .eq("tenant_id", tenant_id).order("created_at", desc=True).order("id")
            .range(offset, offset + limit).execute()).data or []
    return {"courses": present_courses(rows[:limit], tenant_id), "has_more": len(rows) > limit}


def get_course(tenant_id, course_id):
    rows = (service_supabase.table("elearning_courses").select("*")
            .eq("tenant_id", tenant_id).eq("id", str(course_id)).limit(1).execute()).data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Course not found")
    return present_courses(rows, tenant_id)[0]


def create_course(tenant_id, user_id, payload):
    if payload.status == "archived":
        raise HTTPException(status_code=400, detail="New courses must be draft or published")
    require_owned_image(tenant_id, payload.cover_asset)
    row = {**payload.model_dump(exclude_none=True), "tenant_id": tenant_id, "created_by": user_id}
    if not settings_available(129):
        if row.get("catalog_visible") is False:
            raise HTTPException(503, "Catalog configuration requires the database upgrade")
        row.pop("catalog_visible", None)
    rows = service_supabase.table("elearning_courses").insert(row).execute().data or []
    if not rows:
        raise RuntimeError("Course insert failed")
    return present_course(rows[0], deletion_available=settings_available(122))


def update_course(tenant_id, course_id, payload):
    current = get_course(tenant_id, course_id)
    require_owned_image(tenant_id, payload.cover_asset)
    row = payload.model_dump(exclude={"expected_revision"}, exclude_none=True)
    if not settings_available(129):
        if "catalog_visible" in row:
            raise HTTPException(503, "Catalog configuration requires the database upgrade")
    row["revision"] = payload.expected_revision + 1
    rows = (service_supabase.table("elearning_courses").update(row)
            .eq("tenant_id", tenant_id).eq("id", str(course_id))
            .eq("revision", payload.expected_revision).execute()).data or []
    if not rows:
        raise HTTPException(status_code=409, detail="Course changed. Reload before saving.")
    return present_course(rows[0], current, current["deletion_available"])


def archive_course(tenant_id, course_id, expected_revision):
    current = get_course(tenant_id, course_id)
    rows = (service_supabase.table("elearning_courses")
            .update({"status": "archived", "revision": expected_revision + 1})
            .eq("tenant_id", tenant_id).eq("id", str(course_id))
            .eq("revision", expected_revision).execute()).data or []
    if not rows:
        raise HTTPException(status_code=409, detail="Course changed. Reload before archiving.")
    return present_course(rows[0], current, current["deletion_available"])


def duplicate_course(tenant_id, user_id, course_id, expected_revision):
    source = get_course(tenant_id, course_id)
    if source["revision"] != expected_revision:
        raise HTTPException(status_code=409, detail="Course changed. Reload before duplicating.")
    payload = CoursePayload(name=f"Copy of {source['name']}"[:120], description=source["description"],
                            cover_asset=source["cover_asset"], status="draft", access_type=source["access_type"])
    return create_course(tenant_id, user_id, payload)


def delete_course(tenant_id, user_id, course_id, payload):
    if not settings_available(122):
        raise HTTPException(503, detail={"code": "elearning_course_delete_upgrade_required", "message": "Course deletion requires the database upgrade."})
    if not payload.confirmed:
        raise HTTPException(400, "Permanent deletion must be confirmed")
    try:
        return service_supabase.rpc("delete_elearning_course", {"p_tenant_id": tenant_id, "p_course_id": str(course_id), "p_user_id": user_id, "p_expected_revision": payload.expected_revision, "p_expected_structure_revision": payload.expected_structure_revision, "p_confirmation_name": payload.confirmation_name, "p_confirmed": payload.confirmed}).execute().data
    except APIError as error:
        if error.code == "P0002": raise HTTPException(404, "Course not found") from error
        if error.code == "42501": raise HTTPException(403, "Tenant owner or admin access required") from error
        if error.code == "P0001": raise HTTPException(409, "Course changed. Reload before deleting.") from error
        if error.code == "22023": raise HTTPException(400, "Type the exact course name to confirm deletion") from error
        if error.code == "23503": raise HTTPException(409, detail={"code": "elearning_course_delete_protected", "message": "This course has protected references. Archive it instead."}) from error
        raise

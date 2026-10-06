"""Generic lessons and atomic course structure operations, independent of media."""
from typing import Literal
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
from postgrest.exceptions import APIError
from database import service_supabase
from services.elearning_settings_service import settings_available


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Details(Payload):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    status: Literal["draft", "published", "archived"] = "draft"


class LessonDetails(Details):
    section_id: UUID


class Destination(Payload):
    section_id: UUID


class Direction(Payload):
    direction: Literal["up", "down"]


class Confirmation(Payload):
    confirmed: StrictBool

    @model_validator(mode="after")
    def require_confirmation(self):
        if not self.confirmed:
            raise ValueError("Permanent deletion must be confirmed")
        return self


class StructureCommand(Payload):
    action: Literal["create_section", "update_section", "duplicate_section", "archive_section", "delete_section", "reorder_section", "create_lesson", "update_lesson", "duplicate_lesson", "archive_lesson", "delete_lesson", "reorder_lesson", "move_lesson"]
    expected_revision: int = Field(ge=1, strict=True)
    entity_id: UUID | None = None
    payload: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_action_payload(self):
        creating = self.action.startswith("create_")
        if creating == (self.entity_id is not None):
            raise ValueError("Entity ID is required only for existing records")
        payload_type = (LessonDetails if self.action == "create_lesson" else
                        Details if self.action in {"create_section", "update_section", "update_lesson"} else
                        Destination if self.action == "move_lesson" else
                        Direction if self.action.startswith("reorder_") else
                        Confirmation if self.action.startswith("delete_") else Payload)
        self.payload = payload_type.model_validate(self.payload).model_dump(mode="json")
        if creating and self.payload.get("status") == "archived":
            raise ValueError("New learning records must be Draft or Published")
        return self


def structure_available():
    return settings_available(120)


def require_available():
    if not structure_available():
        raise HTTPException(503, detail={"code": "elearning_structure_upgrade_required", "message": "Structure management requires the database upgrade."})


def translate_error(error):
    if error.code == "P0002":
        raise HTTPException(404, "Learning structure record not found") from error
    if error.code == "P0001" and error.message == "elearning_structure_conflict":
        raise HTTPException(409, detail={"code": "elearning_structure_conflict", "message": "Structure changed. Reload before saving."}) from error
    if error.code == "P0001" and error.message == "elearning_section_not_empty":
        raise HTTPException(409, detail={"code": "elearning_section_not_empty", "message": "Archive sections containing lessons instead of deleting them."}) from error
    if error.code == "42501":
        raise HTTPException(403, "Structure management access required") from error
    if error.code == "23503":
        raise HTTPException(409, detail={"code": "elearning_lesson_in_use", "message": "This lesson has completion history. Archive it instead of deleting it."}) from error
    if error.code in {"22023", "23514"}:
        raise HTTPException(400, "Invalid structure operation") from error
    raise error


def get_structure(tenant_id, course_id):
    if not structure_available():
        if not settings_available(118):
            raise HTTPException(503, detail={"code": "elearning_structure_upgrade_required", "message": "Structure management requires the database upgrade."})
        rows = service_supabase.table("elearning_courses").select("id").eq("tenant_id", tenant_id).eq("id", str(course_id)).limit(1).execute().data or []
        if not rows: raise HTTPException(404, "Course not found")
        return {"available": False, "revision": None, "sections": [], "section_count": 0, "lesson_count": 0, "published_count": 0, "draft_count": 0}
    try:
        return service_supabase.rpc("get_elearning_structure", {"p_tenant_id": tenant_id, "p_course_id": str(course_id)}).execute().data
    except APIError as error:
        translate_error(error)


def execute_command(tenant_id, course_id, user_id, command):
    require_available()
    try:
        return service_supabase.rpc("manage_elearning_structure", {
            "p_tenant_id": tenant_id, "p_course_id": str(course_id), "p_user_id": user_id,
            "p_expected_revision": command.expected_revision, "p_action": command.action,
            "p_entity_id": str(command.entity_id) if command.entity_id else None, "p_payload": command.payload,
        }).execute().data
    except APIError as error:
        translate_error(error)


def get_lesson(tenant_id, course_id, lesson_id):
    require_available()
    structure = get_structure(tenant_id, course_id)
    for section in structure["sections"]:
        for lesson in section["lessons"]:
            if lesson["id"] == str(lesson_id):
                return {"lesson": lesson, "section": {key: value for key, value in section.items() if key != "lessons"}}
    raise HTTPException(404, "Lesson not found")

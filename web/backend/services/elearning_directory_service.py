"""Tenant-owned group and instructor records; no implicit accounts or invitations."""
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StrictBool
from postgrest.exceptions import APIError
from database import service_supabase
from services.elearning_settings_service import settings_available


class GroupPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    status: Literal["active", "archived"] = "active"


class InstructorPayload(GroupPayload):
    email: EmailStr | Literal[""] = Field(default="", max_length=254)


class GroupUpdate(GroupPayload):
    expected_revision: int = Field(ge=1, strict=True)


class InstructorUpdate(InstructorPayload):
    expected_revision: int = Field(ge=1, strict=True)


class ArchiveCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1, strict=True)


class DeleteCommand(ArchiveCommand):
    confirmed: StrictBool


def require_group_management_upgrade():
    if not settings_available(133):
        raise HTTPException(503, detail={"code": "elearning_directory_upgrade_required"})


def database_operation(callback):
    try:
        return callback()
    except APIError as error:
        if error.code == "23505" and "elearning_group_name_exists" in error.message:
            raise HTTPException(409, detail={"code": "elearning_group_name_exists"}) from error
        if error.code == "P0002":
            raise HTTPException(404, "Record not found") from error
        if error.code == "42501":
            raise HTTPException(403, "Tenant owner or admin access required") from error
        if error.code == "40001":
            raise HTTPException(409, "Record changed. Reload before saving.") from error
        if error.code == "22023":
            raise HTTPException(400, "Confirm deletion") from error
        raise


def delete_group(tenant_id, user_id, item_id, payload):
    require_group_management_upgrade()
    return database_operation(lambda: service_supabase.rpc("delete_elearning_group", {
        "p_tenant_id": tenant_id, "p_actor_id": user_id, "p_group_id": str(item_id),
        "p_revision": payload.expected_revision, "p_confirmed": payload.confirmed,
    }).execute().data)


def delete_instructor(tenant_id, user_id, item_id, payload):
    if not settings_available(134):
        raise HTTPException(503, detail={"code": "elearning_directory_upgrade_required"})
    return database_operation(lambda: service_supabase.rpc("delete_elearning_instructor", {
        "p_tenant_id": tenant_id, "p_actor_id": user_id, "p_instructor_id": str(item_id),
        "p_revision": payload.expected_revision, "p_confirmed": payload.confirmed,
    }).execute().data)


def table(kind):
    if kind not in {"groups", "instructors"}:
        raise ValueError("Unknown E-Learning directory")
    return service_supabase.table(f"elearning_{kind}")


def directory_available():
    return settings_available(118)


def require_available():
    if not directory_available():
        raise HTTPException(503, detail={"code": "elearning_directory_upgrade_required", "message": "Group and instructor management requires the database upgrade."})


def list_items(kind, tenant_id, limit, offset):
    rows = (table(kind).select("*").eq("tenant_id", tenant_id)
            .order("created_at", desc=True).order("id").range(offset, offset + limit).execute()).data or []
    return {"items": rows[:limit], "has_more": len(rows) > limit}


def get_item(kind, tenant_id, item_id):
    rows = table(kind).select("*").eq("tenant_id", tenant_id).eq("id", str(item_id)).limit(1).execute().data or []
    if not rows:
        raise HTTPException(404, "Record not found")
    return rows[0]


def create_item(kind, tenant_id, user_id, payload):
    if kind == "groups":
        require_group_management_upgrade()
    rows = database_operation(lambda: table(kind).insert({**payload.model_dump(), "tenant_id": tenant_id, "created_by": user_id}).execute()).data or []
    if not rows:
        raise RuntimeError("Record insert failed")
    return rows[0]


def update_item(kind, tenant_id, item_id, payload):
    if kind == "groups":
        require_group_management_upgrade()
    return update_fields(kind, tenant_id, item_id, payload.model_dump(exclude={"expected_revision"}), payload.expected_revision)


def update_fields(kind, tenant_id, item_id, fields, revision):
    get_item(kind, tenant_id, item_id)
    rows = database_operation(lambda: table(kind).update({**fields, "revision": revision + 1})
            .eq("tenant_id", tenant_id).eq("id", str(item_id)).eq("revision", revision).execute()).data or []
    if not rows:
        raise HTTPException(409, "Record changed. Reload before saving.")
    return rows[0]

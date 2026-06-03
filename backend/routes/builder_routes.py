import re
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from database import service_supabase
from services.tenant_service import (
    TenantContext,
    require_active_tenant_member,
    require_builder_admin_access,
    require_builder_write_access,
)

router = APIRouter(prefix="/builder", tags=["Builder"])

SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
PROJECT_STATUSES = {"draft", "published", "archived"}


def normalize_slug(value: str) -> str:
    slug = (value or "").strip().lower()

    if not slug:
        raise HTTPException(status_code=400, detail="Project slug is required")

    if not SLUG_PATTERN.match(slug):
        raise HTTPException(
            status_code=400,
            detail="Project slug can only contain lowercase letters, numbers, and hyphens",
        )

    return slug


def normalize_name(value: str) -> str:
    name = (value or "").strip()

    if not name:
        raise HTTPException(status_code=400, detail="Project name is required")

    if len(name) > 120:
        raise HTTPException(
            status_code=400,
            detail="Project name must be 120 characters or less",
        )

    return name


def assert_json_object(value: Any, field_name: str = "draft_schema") -> dict:
    if value is None:
        return {}

    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a JSON object")

    return value


class BuilderProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1)
    draft_schema: dict[str, Any] = Field(default_factory=dict)

    @field_validator("draft_schema")
    @classmethod
    def validate_draft_schema(cls, value):
        return assert_json_object(value)


class BuilderProjectUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    status: Optional[str] = None
    draft_schema: Optional[dict[str, Any]] = None

    @field_validator("draft_schema")
    @classmethod
    def validate_draft_schema(cls, value):
        return assert_json_object(value)


class BuilderProjectPublish(BaseModel):
    message: Optional[str] = None


def get_project_for_tenant(project_id: str, tenant_id: int):
    project_response = (
        service_supabase.table("builder_projects")
        .select("*")
        .eq("id", project_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )

    project_rows = getattr(project_response, "data", None) or []

    if not project_rows:
        raise HTTPException(status_code=404, detail="Builder project not found")

    return project_rows[0]


def first_row(response):
    if not response.data:
        raise HTTPException(status_code=500, detail="Builder project was not saved")

    return response.data[0]


@router.get("/projects")
def list_builder_projects(request: Request, response: Response):
    context = require_active_tenant_member(request, response)

    projects_response = (
        service_supabase.table("builder_projects")
        .select("*")
        .eq("tenant_id", context.tenant_id)
        .neq("status", "archived")
        .order("updated_at", desc=True)
        .execute()
    )

    return {
        "success": True,
        "projects": projects_response.data or [],
    }


@router.post("/projects")
def create_builder_project(
    project: BuilderProjectCreate,
    request: Request,
    response: Response,
):
    context = require_builder_write_access(request, response)

    payload = {
        "tenant_id": context.tenant_id,
        "owner_user_id": context.user_id,
        "name": normalize_name(project.name),
        "slug": normalize_slug(project.slug),
        "status": "draft",
        "draft_schema": assert_json_object(project.draft_schema),
    }

    try:
        create_response = service_supabase.table("builder_projects").insert(payload).execute()
    except Exception as error:
        if "duplicate" in str(error).lower() or "unique" in str(error).lower():
            raise HTTPException(status_code=409, detail="Project slug already exists")

        print("BUILDER PROJECT CREATE ERROR:", repr(error))
        raise HTTPException(status_code=500, detail="Could not create builder project")

    return {
        "success": True,
        "project": first_row(create_response),
    }


@router.get("/projects/{project_id}")
def get_builder_project(project_id: str, request: Request, response: Response):
    context = require_active_tenant_member(request, response)

    return {
        "success": True,
        "project": get_project_for_tenant(project_id, context.tenant_id),
    }


@router.put("/projects/{project_id}")
def update_builder_project(
    project_id: str,
    project: BuilderProjectUpdate,
    request: Request,
    response: Response,
):
    context = require_builder_write_access(request, response)
    get_project_for_tenant(project_id, context.tenant_id)

    update_payload = {}

    if project.name is not None:
        update_payload["name"] = normalize_name(project.name)

    if project.slug is not None:
        update_payload["slug"] = normalize_slug(project.slug)

    if project.status is not None:
        status = project.status.strip().lower()

        if status not in PROJECT_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid project status")

        update_payload["status"] = status

    if project.draft_schema is not None:
        update_payload["draft_schema"] = assert_json_object(project.draft_schema)

    if not update_payload:
        return {
            "success": True,
            "project": get_project_for_tenant(project_id, context.tenant_id),
        }

    try:
        update_response = (
            service_supabase.table("builder_projects")
            .update(update_payload)
            .eq("id", project_id)
            .eq("tenant_id", context.tenant_id)
            .execute()
        )
    except Exception as error:
        if "duplicate" in str(error).lower() or "unique" in str(error).lower():
            raise HTTPException(status_code=409, detail="Project slug already exists")

        print("BUILDER PROJECT UPDATE ERROR:", repr(error))
        raise HTTPException(status_code=500, detail="Could not update builder project")

    return {
        "success": True,
        "project": first_row(update_response),
    }


@router.delete("/projects/{project_id}")
def archive_builder_project(project_id: str, request: Request, response: Response):
    context = require_builder_admin_access(request, response)
    get_project_for_tenant(project_id, context.tenant_id)

    archive_response = (
        service_supabase.table("builder_projects")
        .update({"status": "archived"})
        .eq("id", project_id)
        .eq("tenant_id", context.tenant_id)
        .execute()
    )

    return {
        "success": True,
        "project": first_row(archive_response),
    }


@router.post("/projects/{project_id}/publish")
def publish_builder_project(
    project_id: str,
    request: Request,
    response: Response,
    publish: Optional[BuilderProjectPublish] = Body(default=None),
):
    context = require_builder_write_access(request, response)
    project = get_project_for_tenant(project_id, context.tenant_id)

    publish_payload = {
        "published_schema": assert_json_object(project.get("draft_schema") or {}),
        "published_version": int(project.get("published_version") or 0) + 1,
        "last_published_at": datetime.now(timezone.utc).isoformat(),
        "status": "published",
    }

    publish_response = (
        service_supabase.table("builder_projects")
        .update(publish_payload)
        .eq("id", project_id)
        .eq("tenant_id", context.tenant_id)
        .execute()
    )

    return {
        "success": True,
        "project": first_row(publish_response),
    }

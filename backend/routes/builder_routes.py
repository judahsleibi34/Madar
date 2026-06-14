import json
import os
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Body, File, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field, field_validator
from postgrest.exceptions import APIError

from database import service_supabase
from services.rate_limit_service import enforce_builder_asset_upload_rate_limit
from services.website_settings_service import require_public_subdomain
from services.url_validation import validate_builder_schema_urls
from services.tenant_service import (
    TenantContext,
    require_active_tenant_member,
    require_builder_admin_access,
    require_builder_write_access,
)

router = APIRouter(tags=["Builder"])
logger = logging.getLogger(__name__)

SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
PROJECT_STATUSES = {"draft", "published", "archived"}
SUBMISSION_STATUS_LABELS = {
    "new": "New",
    "contacted": "Contacted",
    "closed": "Closed",
    "spam": "Spam",
    "archived": "Archived",
}
SUBMISSION_STATUS_VALUES = {label.lower(): value for value, label in SUBMISSION_STATUS_LABELS.items()}
MAX_BUILDER_SCHEMA_BYTES = int(os.getenv("MAX_BUILDER_SCHEMA_BYTES", str(2 * 1024 * 1024)))
BUILDER_ASSET_MAX_BYTES = int(os.getenv("BUILDER_ASSET_MAX_BYTES", str(5 * 1024 * 1024)))
BUILDER_ASSET_UPLOAD_DIR = Path(os.getenv("UPLOADS_DIR", "uploads")).resolve()
BUILDER_ASSET_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


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


def detect_builder_asset_content_type(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"

    return None


def normalize_tenant_asset_directory(tenant_id: int | str) -> str:
    try:
        tenant_value = int(tenant_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=403, detail="A valid tenant context is required")

    if tenant_value <= 0:
        raise HTTPException(status_code=403, detail="A valid tenant context is required")

    return f"tenant_{tenant_value}"


def get_builder_asset_target(tenant_id: int | str, filename: str) -> tuple[Path, Path, str]:
    tenant_dir = normalize_tenant_asset_directory(tenant_id)
    target_dir = BUILDER_ASSET_UPLOAD_DIR / tenant_dir / "builder_assets"
    target_path = target_dir / filename
    uploads_root = BUILDER_ASSET_UPLOAD_DIR.resolve()
    resolved_target = target_path.resolve()

    if uploads_root != resolved_target and uploads_root not in resolved_target.parents:
        raise HTTPException(status_code=400, detail="Invalid asset path")

    return target_dir, resolved_target, tenant_dir


def assert_json_object(value: Any, field_name: str = "draft_schema") -> dict:
    if value is None:
        return {}

    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a JSON object")

    try:
        size_bytes = len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{field_name} must be JSON serializable")

    if size_bytes > MAX_BUILDER_SCHEMA_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"{field_name} is too large",
        )

    return validate_builder_schema_urls(value, field_name=field_name)


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


class BuilderFormSubmissionStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1)


def normalize_submission_status(value: str) -> str:
    status = (value or "").strip().lower()
    db_status = SUBMISSION_STATUS_VALUES.get(status) or (status if status in SUBMISSION_STATUS_LABELS else None)

    if db_status:
        return db_status

    raise HTTPException(status_code=400, detail="Invalid submission status")


def format_submission_status(value: str | None) -> str:
    status = (value or "new").strip().lower()
    return SUBMISSION_STATUS_LABELS.get(status, "New")


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



def format_form_submission(row: dict):
    return {
        "id": row.get("id"),
        "form_id": row.get("form_id"),
        "form_title": row.get("form_title"),
        "form_version": row.get("form_version"),
        "createdAt": row.get("submitted_at") or row.get("created_at"),
        "submitted_at": row.get("submitted_at"),
        "status": format_submission_status(row.get("status")),
        "answers": row.get("answers") or {},
        "quiz": row.get("quiz_result"),
        "field_snapshot": row.get("field_snapshot") or [],
    }


def pagination_response(rows: list[Any], limit: int, offset: int):
    items = rows[:limit]
    return items, {
        "limit": limit,
        "offset": offset,
        "count": len(items),
        "has_more": len(rows) > limit,
    }


def assert_context_user(context: TenantContext, user_id: int | str | None) -> None:
    if user_id is None:
        return

    try:
        if int(context.user_id) != int(user_id):
            raise ValueError
    except (TypeError, ValueError):
        raise HTTPException(status_code=403, detail="User id does not match session")


def require_builder_context(request: Request, response: Response, access_checker) -> TenantContext:
    context = access_checker(request, response)
    assert_context_user(context, request.path_params.get("user_id"))
    return context


def first_row(response):
    if not response.data:
        raise HTTPException(status_code=500, detail="Builder project was not saved")

    return response.data[0]


@router.post("/builder/assets/upload")
async def upload_builder_asset(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
):
    context = require_builder_context(request, response, require_builder_write_access)
    enforce_builder_asset_upload_rate_limit(request, context.user_id, context.tenant_id)

    declared_content_type = (file.content_type or "").split(";", 1)[0].strip().lower()

    if declared_content_type and declared_content_type not in BUILDER_ASSET_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Please upload a PNG, JPG, or WebP image")

    content = await file.read(BUILDER_ASSET_MAX_BYTES + 1)

    if not content:
        raise HTTPException(status_code=400, detail="Image file is required")

    if len(content) > BUILDER_ASSET_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image file must be 5MB or smaller")

    detected_content_type = detect_builder_asset_content_type(content)

    if not detected_content_type:
        raise HTTPException(status_code=400, detail="Please upload a PNG, JPG, or WebP image")

    if declared_content_type and declared_content_type != detected_content_type:
        raise HTTPException(status_code=400, detail="Image content does not match the declared file type")

    extension = BUILDER_ASSET_EXTENSIONS[detected_content_type]
    filename = f"{uuid4().hex}{extension}"
    target_dir, target_path, tenant_dir = get_builder_asset_target(context.tenant_id, filename)

    target_dir.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)

    asset_url = f"/uploads/{tenant_dir}/builder_assets/{filename}"

    return {
        "success": True,
        "asset_url": asset_url,
        "url": asset_url,
        "content_type": detected_content_type,
    }


@router.get("/users/{user_id}/builder/projects", include_in_schema=False)
@router.get("/builder/projects")
def list_builder_projects(
    request: Request,
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    context = require_builder_context(request, response, require_active_tenant_member)

    projects_response = (
        service_supabase.table("builder_projects")
        .select("*")
        .eq("tenant_id", context.tenant_id)
        .neq("status", "archived")
        .order("updated_at", desc=True)
        .range(offset, offset + limit)
        .execute()
    )
    projects, pagination = pagination_response(projects_response.data or [], limit, offset)

    return {
        "success": True,
        "items": projects,
        "projects": projects,
        "pagination": pagination,
    }


@router.post("/users/{user_id}/builder/projects", include_in_schema=False)
@router.post("/builder/projects")
def create_builder_project(
    project: BuilderProjectCreate,
    request: Request,
    response: Response,
):
    context = require_builder_context(request, response, require_builder_write_access)

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

        logger.warning("builder.project_create_failed", extra={"tenant_id": context.tenant_id, "user_id": context.user_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=500, detail="Could not create builder project")

    return {
        "success": True,
        "project": first_row(create_response),
    }


@router.get("/users/{user_id}/builder/projects/{project_id}", include_in_schema=False)
@router.get("/builder/projects/{project_id}")
def get_builder_project(project_id: str, request: Request, response: Response):
    context = require_builder_context(request, response, require_active_tenant_member)

    return {
        "success": True,
        "project": get_project_for_tenant(project_id, context.tenant_id),
    }


@router.put("/users/{user_id}/builder/projects/{project_id}", include_in_schema=False)
@router.put("/builder/projects/{project_id}")
def update_builder_project(
    project_id: str,
    project: BuilderProjectUpdate,
    request: Request,
    response: Response,
):
    context = require_builder_context(request, response, require_builder_write_access)
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

        logger.warning("builder.project_update_failed", extra={"tenant_id": context.tenant_id, "user_id": context.user_id, "project_id": project_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=500, detail="Could not update builder project")

    return {
        "success": True,
        "project": first_row(update_response),
    }


@router.delete("/users/{user_id}/builder/projects/{project_id}", include_in_schema=False)
@router.delete("/builder/projects/{project_id}")
def archive_builder_project(project_id: str, request: Request, response: Response):
    context = require_builder_context(request, response, require_builder_admin_access)
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


@router.get("/users/{user_id}/builder/projects/{project_id}/form-submissions", include_in_schema=False)
@router.get("/builder/projects/{project_id}/form-submissions")
def list_builder_form_submissions(
    project_id: str,
    request: Request,
    response: Response,
    form_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    context = require_builder_context(request, response, require_active_tenant_member)
    get_project_for_tenant(project_id, context.tenant_id)

    query = (
        service_supabase.table("builder_form_submissions")
        .select("*")
        .eq("tenant_id", context.tenant_id)
        .eq("project_id", project_id)
    )

    if form_id:
        query = query.eq("form_id", form_id.strip())

    submissions_response = (
        query.order("submitted_at", desc=True)
        .range(offset, offset + limit)
        .execute()
    )
    submissions, pagination = pagination_response(
        [
            format_form_submission(row)
            for row in (submissions_response.data or [])
        ],
        limit,
        offset,
    )

    return {
        "success": True,
        "project_id": project_id,
        "items": submissions,
        "submissions": submissions,
        "pagination": pagination,
        "limit": limit,
        "offset": offset,
    }


@router.get("/users/{user_id}/builder/projects/{project_id}/form-submissions/{submission_id}", include_in_schema=False)
@router.get("/builder/projects/{project_id}/form-submissions/{submission_id}")
def get_builder_form_submission(
    project_id: str,
    submission_id: str,
    request: Request,
    response: Response,
):
    context = require_builder_context(request, response, require_active_tenant_member)
    get_project_for_tenant(project_id, context.tenant_id)

    submission_response = (
        service_supabase.table("builder_form_submissions")
        .select("*")
        .eq("tenant_id", context.tenant_id)
        .eq("project_id", project_id)
        .eq("id", submission_id)
        .limit(1)
        .execute()
    )

    submission_rows = getattr(submission_response, "data", None) or []
    submission = submission_rows[0] if submission_rows else None

    if not submission:
        raise HTTPException(status_code=404, detail="Form submission not found")

    return {
        "success": True,
        "submission": format_form_submission(submission),
    }


@router.put("/users/{user_id}/builder/projects/{project_id}/form-submissions/{submission_id}", include_in_schema=False)
@router.put("/builder/projects/{project_id}/form-submissions/{submission_id}")
def update_builder_form_submission_status(
    project_id: str,
    submission_id: str,
    submission_update: BuilderFormSubmissionStatusUpdate,
    request: Request,
    response: Response,
):
    context = require_builder_context(request, response, require_active_tenant_member)
    get_project_for_tenant(project_id, context.tenant_id)

    status = normalize_submission_status(submission_update.status)

    try:
        update_response = (
            service_supabase.table("builder_form_submissions")
            .update({"status": status})
            .eq("tenant_id", context.tenant_id)
            .eq("project_id", project_id)
            .eq("id", submission_id)
            .execute()
        )
    except APIError as error:
        logger.warning(
            "builder.form_submission_status_update_failed",
            extra={
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "project_id": project_id,
                "submission_id": submission_id,
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(status_code=500, detail="Could not update form submission status")

    submission_rows = getattr(update_response, "data", None) or []
    submission = submission_rows[0] if submission_rows else None

    if not submission:
        raise HTTPException(status_code=404, detail="Form submission not found")

    return {
        "success": True,
        "submission": format_form_submission(submission),
    }


@router.post("/users/{user_id}/builder/projects/{project_id}/publish", include_in_schema=False)
@router.post("/builder/projects/{project_id}/publish")
def publish_builder_project(
    project_id: str,
    request: Request,
    response: Response,
    publish: Optional[BuilderProjectPublish] = Body(default=None),
):
    context = require_builder_context(request, response, require_builder_write_access)
    project = get_project_for_tenant(project_id, context.tenant_id)
    website_settings = require_public_subdomain(context.tenant_id, context.user_id)

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

    logger.info(
        "builder.project_published",
        extra={"tenant_id": context.tenant_id, "user_id": context.user_id, "project_id": project_id},
    )

    return {
        "success": True,
        "project": first_row(publish_response),
        "site": {
            "subdomain": website_settings.get("subdomain"),
            "tenant_id": website_settings.get("tenant_id"),
        },
    }

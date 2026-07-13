import copy
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
from services.audit_service import hash_audit_identifier, record_audit_event
from services.api_errors import error_detail
from services.billing_service import require_publish_entitlement
from services.notification_outbox_service import enqueue_notification
from services.rate_limit_service import enforce_builder_asset_upload_rate_limit
from services.website_settings_service import require_public_subdomain
from services.url_validation import validate_builder_schema_urls, validate_public_url
from services.tenant_service import (
    TenantContext,
    require_active_tenant_member,
    require_builder_admin_access,
    require_builder_write_access,
)
from services.upload_config import get_public_uploads_dir

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
RESERVATION_STATUSES = {"new", "confirmed", "cancelled", "completed", "rejected"}
MAX_BUILDER_SCHEMA_BYTES = int(os.getenv("MAX_BUILDER_SCHEMA_BYTES", str(2 * 1024 * 1024)))
UNSAFE_BUILDER_ELEMENT_TYPES = {"html", "rawhtml", "script", "iframe"}
PUBLIC_PAGE_SLUG_PATTERN = re.compile(r"^/[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED_PUBLIC_PAGE_SLUGS = {
    "admin", "api", "auth", "builder", "dashboard", "forgot-password",
    "login", "reset-password", "settings", "signup", "verify-email",
}
BUILDER_ASSET_MAX_BYTES = int(os.getenv("BUILDER_ASSET_MAX_BYTES", str(5 * 1024 * 1024)))
BUILDER_ASSET_UPLOAD_DIR = get_public_uploads_dir()
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


def _page_slug_from_name(value: Any, index: int) -> str:
    segment = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return f"/{segment or f'page-{index + 1}'}"


def normalize_published_page_routes(schema: dict[str, Any]) -> dict[str, Any]:
    pages = schema.get("pages") or []
    if not pages:
        return schema

    explicit_default_id = str(schema.get("defaultPageId") or "").strip()
    explicit_default_pages = [page for page in pages if page.get("isDefault") is True or page.get("is_default") is True]
    if len(explicit_default_pages) > 1:
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "publish_validation_failed",
                "Exactly one published page must be the homepage.",
                context={
                    "issue_type": "missing_default_page",
                    "occurrences": [
                        {"page_id": str(page.get("id") or ""), "page_name": str(page.get("name") or page.get("title") or "Untitled page")}
                        for page in explicit_default_pages
                    ],
                },
            ),
        )

    default_page = next((page for page in pages if str(page.get("id") or "") == explicit_default_id), None)
    default_page = default_page or (explicit_default_pages[0] if explicit_default_pages else None)
    default_page = default_page or next(
        (page for page in pages if str(page.get("slug", page.get("path", ""))).strip() == "/"),
        None,
    )
    default_page = default_page or next(
        (page for page in pages if str(page.get("name") or page.get("title") or "").strip().lower() == "home"),
        pages[0],
    )
    default_page_id = str(default_page.get("id") or "")
    schema["defaultPageId"] = default_page_id

    route_occurrences: dict[str, list[dict[str, Any]]] = {}
    for index, page in enumerate(pages):
        page_id = str(page.get("id") or "")
        page_name = str(page.get("name") or page.get("title") or "Untitled page")
        page_route_name = page.get("name") or page.get("title")
        is_default = page_id == default_page_id
        raw_route = str(page.get("slug", page.get("path", page.get("route", ""))) or "").strip()
        if is_default:
            route = "/"
        elif not raw_route or raw_route == "/":
            route = _page_slug_from_name(page_route_name, index)
        else:
            route = "/" + raw_route.lstrip("/").rstrip("/")
            if not PUBLIC_PAGE_SLUG_PATTERN.fullmatch(route):
                raise HTTPException(
                    status_code=400,
                    detail=error_detail(
                        "publish_validation_failed",
                        "A published page link is invalid.",
                        context={
                            "issue_type": "invalid_page_slug",
                            "page_id": page_id,
                            "page_name": page_name,
                            "page_slug": raw_route,
                        },
                    ),
                )
        if not is_default and route.lstrip("/") in RESERVED_PUBLIC_PAGE_SLUGS:
            raise HTTPException(
                status_code=400,
                detail=error_detail(
                    "publish_validation_failed",
                    "A published page link uses a reserved route.",
                    context={
                        "issue_type": "reserved_page_slug",
                        "page_id": page_id,
                        "page_name": page_name,
                        "page_slug": route,
                    },
                ),
            )
        page["slug"] = route
        page["isDefault"] = is_default
        page["showInNavigation"] = page.get("showInNavigation", page.get("show_in_header", True)) is not False
        page["order"] = index
        page.pop("is_default", None)
        page.pop("show_in_header", None)
        context = {"page_id": page_id, "page_name": page_name, "page_slug": route}
        route_occurrences.setdefault(route, []).append(context)

    for route, occurrences in route_occurrences.items():
        if len(occurrences) > 1:
            raise HTTPException(
                status_code=400,
                detail=error_detail(
                    "publish_validation_failed",
                    "Published pages must use unique page links.",
                    context={
                        "issue_type": "duplicate_page_slug",
                        "duplicate_slug": route,
                        "occurrences": occurrences,
                    },
                ),
            )
    return schema


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


def assert_json_object(
    value: Any,
    field_name: str = "draft_schema",
    *,
    validate_urls: bool = True,
) -> dict:
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

    return (
        validate_builder_schema_urls(value, field_name=field_name)
        if validate_urls
        else value
    )


def _project_revision(project: dict[str, Any]) -> int:
    try:
        revision = int(project.get("draft_revision") or 0)
    except (TypeError, ValueError):
        revision = 0
    return max(revision, 0)


def _raise_revision_conflict(project_id: str, tenant_id: int | str) -> None:
    try:
        current = get_project_for_tenant(project_id, int(tenant_id))
        current_revision = _project_revision(current)
    except HTTPException:
        current_revision = None

    context = {"current_revision": current_revision} if current_revision is not None else None
    raise HTTPException(
        status_code=409,
        detail=error_detail(
            "project_revision_conflict",
            "This project was updated elsewhere.",
            context=context,
        ),
    )


def validate_publish_schema(
    value: Any,
    *,
    project_schema_version: Any = None,
) -> tuple[dict[str, Any], int]:
    """Revalidate persisted builder JSON and its supported schema version at publish."""

    schema = copy.deepcopy(
        assert_json_object(value, field_name="draft_schema", validate_urls=False)
    )
    raw_schema_version = schema.get(
        "schema_version",
        schema.get("version", project_schema_version if project_schema_version is not None else 1),
    )
    if isinstance(raw_schema_version, bool):
        raw_schema_version = None

    try:
        schema_version = int(raw_schema_version)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "publish_validation_failed",
                "The project schema version is invalid.",
            ),
        )

    supported_versions = {
        int(version.strip())
        for version in os.getenv("BUILDER_SUPPORTED_SCHEMA_VERSIONS", "1").split(",")
        if version.strip().isdigit()
    } or {1}
    if schema_version not in supported_versions:
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "publish_validation_failed",
                "This project schema version cannot be published.",
                context={"schema_version": schema_version},
            ),
        )

    for collection_name in ("pages", "forms"):
        collection = schema.get(collection_name)
        if collection is not None and not isinstance(collection, list):
            raise HTTPException(
                status_code=400,
                detail=error_detail(
                    "publish_validation_failed",
                    f"Project {collection_name} must be a list.",
                ),
            )

        occurrences: dict[str, list[dict[str, Any]]] = {}
        for index, item in enumerate(collection or []):
            if not isinstance(item, dict):
                raise HTTPException(
                    status_code=400,
                    detail=error_detail(
                        "publish_validation_failed",
                        f"Project {collection_name} entries must be objects.",
                    ),
                )
            item_id = str(item.get("id") or "").strip()
            item_context = {
                "occurrence_index": index,
                f"{collection_name[:-1]}_id": item_id,
                f"{collection_name[:-1]}_name": str(
                    item.get("name") or item.get("title") or f"Untitled {collection_name[:-1]}"
                ),
            }
            if not item_id:
                raise HTTPException(
                    status_code=400,
                    detail=error_detail(
                        "publish_validation_failed",
                        f"Every project {collection_name[:-1]} must have an id.",
                        context={
                            "issue_type": f"missing_{collection_name[:-1]}_id",
                            "occurrences": [item_context],
                        },
                    ),
                )
            occurrences.setdefault(item_id, []).append(item_context)
        for item_id, item_occurrences in occurrences.items():
            if len(item_occurrences) > 1:
                raise HTTPException(
                    status_code=400,
                    detail=error_detail(
                        "publish_validation_failed",
                        f"Project {collection_name} must have unique ids.",
                        context={
                            "issue_type": f"duplicate_{collection_name[:-1]}_id",
                            "duplicate_id": item_id,
                            "occurrences": item_occurrences,
                        },
                    ),
                )

    schema = normalize_published_page_routes(schema)

    form_ids = {
        str(form.get("id") or "").strip()
        for form in schema.get("forms") or []
        if isinstance(form, dict) and str(form.get("id") or "").strip()
    }

    def page_elements(page: dict[str, Any]):
        """Yield real builder elements, not nested config objects with a `type` key."""
        for section in page.get("sections") or []:
            if not isinstance(section, dict):
                continue
            for element in section.get("elements") or []:  # legacy section shape
                if isinstance(element, dict):
                    yield element
            for element in section.get("freeElements") or []:
                if isinstance(element, dict):
                    yield element
            for row in section.get("rows") or []:
                if not isinstance(row, dict):
                    continue
                for column in row.get("columns") or []:
                    if not isinstance(column, dict):
                        continue
                    for element in column.get("elements") or []:
                        if isinstance(element, dict):
                            yield element

    block_occurrences: dict[str, list[dict[str, Any]]] = {}
    for page in schema.get("pages") or []:
        if not isinstance(page, dict):
            continue
        for occurrence_index, element in enumerate(page_elements(page)):
            element_type = str(element.get("type") or "").strip()
            block_id = str(element.get("id") or "").strip()
            occurrence = {
                "page_id": str(page.get("id") or ""),
                "page_name": str(page.get("name") or page.get("title") or "Untitled page"),
                "block_id": block_id,
                "block_type": element_type or "unknown",
                "occurrence_index": occurrence_index,
            }
            if not element_type or not block_id:
                raise HTTPException(
                    status_code=400,
                    detail=error_detail(
                        "publish_validation_failed",
                        "Every published block must have a type and id.",
                        context={
                            "issue_type": "missing_block_id" if not block_id else "missing_block_type",
                            "occurrences": [occurrence],
                        },
                    ),
                )
            block_occurrences.setdefault(block_id, []).append(occurrence)

    for block_id, occurrences in block_occurrences.items():
        if len(occurrences) > 1:
            raise HTTPException(
                status_code=400,
                detail=error_detail(
                    "publish_validation_failed",
                    "Published blocks must have unique ids.",
                    context={
                        "issue_type": "duplicate_block_id",
                        "duplicate_id": block_id,
                        "occurrences": occurrences,
                    },
                ),
            )

    def inspect_element(page: dict[str, Any], element: dict[str, Any]) -> None:
        element_type = str(element.get("type") or "").strip()
        block_id = str(element.get("id") or "").strip()
        if element_type.lower() in UNSAFE_BUILDER_ELEMENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=error_detail(
                    "publish_validation_failed",
                    "The project contains an unsupported unsafe block type.",
                ),
            )
        if element_type == "formBlock":
            raw_connected_form_id = (
                element.get("connectedFormId")
                if "connectedFormId" in element
                else element.get("formId", element.get("form_id"))
            )
            connected_form_id = str(raw_connected_form_id or "").strip()
            if not connected_form_id or connected_form_id not in form_ids:
                raise HTTPException(
                    status_code=400,
                    detail=error_detail(
                        "publish_validation_failed",
                        "A published form block is not connected to a valid form.",
                        context={
                            "issue_type": "orphaned_form_block",
                            "page_id": str(page.get("id") or ""),
                            "page_name": str(page.get("name") or page.get("title") or ""),
                            "block_id": block_id,
                            "block_label": str(element.get("name") or element.get("label") or "Form"),
                            "form_id": connected_form_id,
                        },
                    ),
                )
            element["connectedFormId"] = connected_form_id
            element.pop("formId", None)
            element.pop("form_id", None)
        if element_type == "reservationBlock" and not isinstance(
            element.get("reservation"), dict
        ):
            raise HTTPException(
                status_code=400,
                detail=error_detail(
                    "publish_validation_failed",
                    "A reservation block has invalid configuration.",
                ),
            )
        if element_type == "button":
            raw_action = element.get("action")
            action = raw_action if isinstance(raw_action, dict) else {}
            raw_action_type = str(
                action.get("type")
                or action.get("actionType")
                or action.get("action_type")
                or "none"
            ).strip()
            action_type = {
                "page": "goToPage",
                "gotopage": "goToPage",
                "internal": "goToPage",
                "url": "openUrl",
                "openurl": "openUrl",
                "external": "openUrl",
                "message": "showMessage",
                "showmessage": "showMessage",
                "none": "none",
            }.get(raw_action_type.lower())
            action_context = {
                "page_id": str(page.get("id") or ""),
                "page_name": str(page.get("name") or page.get("title") or "Untitled page"),
                "block_id": block_id,
                "action_type": action_type or raw_action_type,
            }
            if action_type == "goToPage":
                target_page_id = str(
                    action.get("pageId")
                    or action.get("targetPageId")
                    or action.get("page_id")
                    or ""
                ).strip()
                if target_page_id not in {
                    str(item.get("id") or "")
                    for item in schema.get("pages") or []
                    if isinstance(item, dict)
                }:
                    raise HTTPException(
                        status_code=400,
                        detail=error_detail(
                            "publish_validation_failed",
                            "A button must target a published page.",
                            context={**action_context, "issue_type": "invalid_button_page_target"},
                        ),
                    )
                action = {**action, "type": action_type, "pageId": target_page_id}
            elif action_type == "openUrl":
                action_url = str(action.get("url") or action.get("href") or "").strip()
                try:
                    validate_public_url(
                        action_url,
                        field_name="Button action URL",
                        allow_empty=False,
                        allow_relative=False,
                    )
                except HTTPException:
                    raise HTTPException(
                        status_code=400,
                        detail=error_detail(
                            "publish_validation_failed",
                            "A button must use a valid HTTPS URL.",
                            context={**action_context, "issue_type": "invalid_button_url"},
                        ),
                    ) from None
                action = {**action, "type": action_type, "url": action_url}
            elif action_type == "showMessage":
                message = str(action.get("message") or "")
                if not message.strip():
                    raise HTTPException(
                        status_code=400,
                        detail=error_detail(
                            "publish_validation_failed",
                            "A message button must contain a message.",
                            context={**action_context, "issue_type": "empty_button_message"},
                        ),
                    )
                action = {**action, "type": action_type, "message": message}
            elif action_type is None:
                raise HTTPException(
                    status_code=400,
                    detail=error_detail(
                        "publish_validation_failed",
                        "A button has an unsupported action.",
                        context={**action_context, "issue_type": "invalid_button_action"},
                    ),
                )
            element["action"] = action

    for page in schema.get("pages") or []:
        if isinstance(page, dict):
            for element in page_elements(page):
                inspect_element(page, element)

    validate_builder_schema_urls(schema, field_name="draft_schema")
    return schema, schema_version


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
    expected_revision: Optional[int] = Field(default=None, ge=0)

    @field_validator("draft_schema")
    @classmethod
    def validate_draft_schema(cls, value):
        return assert_json_object(value)


class BuilderProjectPublish(BaseModel):
    message: Optional[str] = None
    expected_revision: Optional[int] = Field(default=None, ge=0)


class BuilderProjectUnpublish(BaseModel):
    expected_revision: Optional[int] = Field(default=None, ge=0)


class BuilderFormSubmissionStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1)


class BuilderReservationStatusUpdate(BaseModel):
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


def normalize_reservation_status(value: str) -> str:
    status = (value or "").strip().lower()

    if status in RESERVATION_STATUSES:
        return status

    raise HTTPException(status_code=400, detail="Invalid reservation status")


def format_reservation(row: dict):
    return {
        "id": row.get("id"),
        "project_id": row.get("project_id"),
        "site_subdomain": row.get("site_subdomain"),
        "block_id": row.get("block_id"),
        "block_type": row.get("block_type"),
        "reservation_title": row.get("reservation_title"),
        "customer_name": row.get("customer_name"),
        "customer_email": row.get("customer_email"),
        "customer_phone": row.get("customer_phone"),
        "starts_at": row.get("starts_at"),
        "ends_at": row.get("ends_at"),
        "timezone": row.get("timezone"),
        "status": row.get("status") or "new",
        "payload": row.get("payload") or {},
        "field_snapshot": row.get("field_snapshot") or [],
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


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

    project = project_rows[0]

    if str(project.get("status") or "").strip().lower() == "archived":
        raise HTTPException(status_code=404, detail="Builder project not found")

    return project

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


def require_builder_context_without_admin_account_access(
    request: Request,
    response: Response,
) -> TenantContext:
    context = require_active_tenant_member(
        request,
        response,
        allow_admin_account_access=False,
    )
    assert_context_user(context, request.path_params.get("user_id"))
    return context


def first_row(response):
    if not response.data:
        raise HTTPException(status_code=500, detail="Builder project was not saved")

    return response.data[0]


def publish_project_atomically(
    *,
    project: dict[str, Any],
    project_id: str,
    tenant_id: int,
    expected_revision: int,
    schema_version: int,
    published_at: str,
    require_active_entitlement: bool,
) -> dict[str, Any]:
    """Publish through the locking database RPC, with a test/legacy-client fallback."""

    rpc = getattr(service_supabase, "rpc", None)
    if callable(rpc):
        try:
            response = rpc(
                "publish_builder_project_atomic",
                {
                    "p_project_id": project_id,
                    "p_tenant_id": tenant_id,
                    "p_expected_revision": expected_revision,
                    "p_published_at": published_at,
                    "p_schema_version": schema_version,
                    "p_require_active_entitlement": require_active_entitlement,
                },
            ).execute()
        except Exception as error:
            error_text = str(error).lower()
            if "project_revision_conflict" in error_text or "serialization" in error_text:
                _raise_revision_conflict(project_id, tenant_id)
            if "builder_project_not_found" in error_text:
                raise HTTPException(status_code=404, detail="Builder project not found")
            if "entitlement_inactive" in error_text:
                raise HTTPException(
                    status_code=402,
                    detail=error_detail(
                        "entitlement_inactive",
                        "An active publishing entitlement is required.",
                    ),
                )
            logger.warning(
                "builder.project_publish_failed",
                extra={
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "error_type": type(error).__name__,
                },
            )
            raise HTTPException(
                status_code=500,
                detail=error_detail(
                    "publish_failed",
                    "The project could not be published.",
                ),
            )

        rows = response.data or []
        if isinstance(rows, dict):
            if isinstance(rows.get("result"), dict):
                return rows["result"]
            return rows
        if rows:
            row = rows[0]
            if isinstance(row, dict) and isinstance(row.get("result"), dict):
                return row["result"]
            return row
        _raise_revision_conflict(project_id, tenant_id)

    # Simple test doubles and pre-RPC local fixtures use the same conditional
    # single-statement update. Real deployments use the RPC above.
    publish_payload: dict[str, Any] = {
        "published_schema": project.get("draft_schema") or {},
        "published_version": int(project.get("published_version") or 0) + 1,
        "last_published_at": published_at,
        "status": "published",
    }
    if "draft_revision" in project:
        publish_payload["published_revision"] = expected_revision
        publish_payload["schema_version"] = schema_version
    query = (
        service_supabase.table("builder_projects")
        .update(publish_payload)
        .eq("id", project_id)
        .eq("tenant_id", tenant_id)
    )
    if "draft_revision" in project:
        query = query.eq("draft_revision", expected_revision)
    if "published_version" in project:
        query = query.eq("published_version", int(project.get("published_version") or 0))

    response = query.execute()
    rows = getattr(response, "data", None) or []
    if not rows:
        _raise_revision_conflict(project_id, tenant_id)
    return rows[0]


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

    record_audit_event(
        request=request,
        tenant_id=context.tenant_id,
        actor_user_id=context.user_id,
        action="builder.asset_uploaded",
        target_type="builder_asset",
        target_id=filename,
        metadata={
            "asset_url": asset_url,
            "content_type": detected_content_type,
            "size_bytes": len(content),
            "extension": extension,
        },
    )

    return {
        "success": True,
        "asset_url": asset_url,
        "url": asset_url,
        "content_type": detected_content_type,
    }


@router.get("/builder/reservations")
def list_builder_reservations(
    request: Request,
    response: Response,
    status: Optional[str] = Query(default=None),
    project_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    context = require_builder_context(request, response, require_active_tenant_member)
    query = (
        service_supabase.table("builder_reservations")
        .select("*")
        .eq("tenant_id", context.tenant_id)
    )

    if status:
        query = query.eq("status", normalize_reservation_status(status))

    if project_id:
        query = query.eq("project_id", project_id.strip())

    reservations_response = (
        query.order("created_at", desc=True)
        .range(offset, offset + limit)
        .execute()
    )
    reservations, pagination = pagination_response(
        [format_reservation(row) for row in (reservations_response.data or [])],
        limit,
        offset,
    )

    return {
        "success": True,
        "items": reservations,
        "reservations": reservations,
        "pagination": pagination,
    }


@router.get("/builder/reservations/{reservation_id}")
def get_builder_reservation(reservation_id: str, request: Request, response: Response):
    context = require_builder_context(request, response, require_active_tenant_member)
    reservation_response = (
        service_supabase.table("builder_reservations")
        .select("*")
        .eq("id", reservation_id)
        .eq("tenant_id", context.tenant_id)
        .limit(1)
        .execute()
    )
    reservation_rows = getattr(reservation_response, "data", None) or []
    reservation = reservation_rows[0] if reservation_rows else None

    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    return {"success": True, "reservation": format_reservation(reservation)}


@router.patch("/builder/reservations/{reservation_id}/status")
def update_builder_reservation_status(
    reservation_id: str,
    status_update: BuilderReservationStatusUpdate,
    request: Request,
    response: Response,
):
    context = require_builder_context(request, response, require_builder_write_access)
    status = normalize_reservation_status(status_update.status)

    update_response = (
        service_supabase.table("builder_reservations")
        .update({"status": status, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", reservation_id)
        .eq("tenant_id", context.tenant_id)
        .execute()
    )
    reservation_rows = getattr(update_response, "data", None) or []
    reservation = reservation_rows[0] if reservation_rows else None

    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    customer_email = str(reservation.get("customer_email") or "").strip().lower()
    if customer_email:
        enqueue_notification(
            channel="email",
            template="reservation_status_changed",
            tenant_id=context.tenant_id,
            recipient_hash=hash_audit_identifier(customer_email),
            recipient_reference=f"reservation:{reservation_id}",
            deduplication_key=hash_audit_identifier(
                f"reservation-status:{reservation_id}:{status}"
            ),
            payload={"reservation_id": reservation_id, "status": status},
            client=service_supabase,
        )

    return {"success": True, "reservation": format_reservation(reservation)}


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
        "draft_revision": 0,
        "schema_version": 1,
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
    existing_project = get_project_for_tenant(project_id, context.tenant_id)
    current_revision = _project_revision(existing_project)
    requested_expected_revision = getattr(project, "expected_revision", None)
    if "draft_revision" in existing_project and requested_expected_revision is None:
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "project_revision_required",
                "Reload the project before saving changes.",
                context={"current_revision": current_revision},
            ),
        )
    expected_revision = (
        requested_expected_revision
        if requested_expected_revision is not None
        else current_revision
    )
    if expected_revision != current_revision:
        _raise_revision_conflict(project_id, context.tenant_id)

    update_payload = {}

    if project.name is not None:
        update_payload["name"] = normalize_name(project.name)

    if project.slug is not None:
        update_payload["slug"] = normalize_slug(project.slug)

    if project.status is not None:
        status = project.status.strip().lower()

        if status not in PROJECT_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid project status")
        current_status = str(existing_project.get("status") or "draft").strip().lower()
        if status != current_status:
            raise HTTPException(
                status_code=400,
                detail=error_detail(
                    "project_status_transition_required",
                    "Use the publish, unpublish, or archive action to change project status.",
                ),
            )

    if project.draft_schema is not None:
        update_payload["draft_schema"] = assert_json_object(project.draft_schema)

    if not update_payload:
        return {
            "success": True,
            "project": get_project_for_tenant(project_id, context.tenant_id),
        }

    revision_supported = "draft_revision" in existing_project or requested_expected_revision is not None
    if revision_supported:
        update_payload["draft_revision"] = current_revision + 1

    try:
        update_query = (
            service_supabase.table("builder_projects")
            .update(update_payload)
            .eq("id", project_id)
            .eq("tenant_id", context.tenant_id)
        )
        if "status" in existing_project:
            update_query = update_query.eq("status", existing_project.get("status"))
        if revision_supported:
            update_query = update_query.eq("draft_revision", expected_revision)
        update_response = update_query.execute()
    except Exception as error:
        if "duplicate" in str(error).lower() or "unique" in str(error).lower():
            raise HTTPException(status_code=409, detail="Project slug already exists")

        logger.warning("builder.project_update_failed", extra={"tenant_id": context.tenant_id, "user_id": context.user_id, "project_id": project_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=500, detail="Could not update builder project")

    if not (getattr(update_response, "data", None) or []):
        _raise_revision_conflict(project_id, context.tenant_id)

    return {
        "success": True,
        "project": first_row(update_response),
    }


@router.delete("/users/{user_id}/builder/projects/{project_id}", include_in_schema=False)
@router.delete("/builder/projects/{project_id}")
def archive_builder_project(project_id: str, request: Request, response: Response):
    context = require_builder_context(request, response, require_builder_admin_access)
    project = get_project_for_tenant(project_id, context.tenant_id)

    archive_query = (
        service_supabase.table("builder_projects")
        .update({"status": "archived"})
        .eq("id", project_id)
        .eq("tenant_id", context.tenant_id)
        .eq("status", project.get("status"))
    )
    if "draft_revision" in project:
        archive_query = archive_query.eq("draft_revision", _project_revision(project))
    archive_response = archive_query.execute()
    archive_rows = getattr(archive_response, "data", None) or []
    if not archive_rows:
        _raise_revision_conflict(project_id, context.tenant_id)
    archived_project = archive_rows[0]

    record_audit_event(
        request=request,
        tenant_id=context.tenant_id,
        actor_user_id=context.user_id,
        action="builder.project_archived",
        target_type="builder_project",
        target_id=project_id,
        metadata={
            "project_slug": project.get("slug"),
            "project_name": project.get("name"),
            "status": archived_project.get("status"),
        },
    )

    return {
        "success": True,
        "project": archived_project,
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
    context = require_builder_context_without_admin_account_access(request, response)
    get_project_for_tenant(project_id, context.tenant_id)

    status = normalize_submission_status(submission_update.status)

    existing_submission_response = (
        service_supabase.table("builder_form_submissions")
        .select("id, tenant_id, project_id, form_id, status")
        .eq("tenant_id", context.tenant_id)
        .eq("project_id", project_id)
        .eq("id", submission_id)
        .limit(1)
        .execute()
    )
    existing_submission_rows = getattr(existing_submission_response, "data", None) or []
    existing_submission = existing_submission_rows[0] if existing_submission_rows else None

    if not existing_submission:
        raise HTTPException(status_code=404, detail="Form submission not found")

    old_status = str(existing_submission.get("status") or "new").strip().lower()

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

    record_audit_event(
        request=request,
        tenant_id=context.tenant_id,
        actor_user_id=context.user_id,
        action="builder.form_submission_status_updated",
        target_type="builder_form_submission",
        target_id=submission_id,
        metadata={
            "project_id": project_id,
            "form_id": submission.get("form_id") or existing_submission.get("form_id"),
            "old_status": format_submission_status(old_status),
            "new_status": format_submission_status(submission.get("status")),
        },
    )

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
    entitlement = require_publish_entitlement(context.tenant_id)
    website_settings = require_public_subdomain(context.tenant_id, context.user_id)
    current_revision = _project_revision(project)
    requested_revision = getattr(publish, "expected_revision", None) if publish else None
    if "draft_revision" in project and requested_revision is None:
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "project_revision_required",
                "Reload the project before publishing.",
                context={"current_revision": current_revision},
            ),
        )
    expected_revision = requested_revision if requested_revision is not None else current_revision
    if expected_revision != current_revision:
        _raise_revision_conflict(project_id, context.tenant_id)

    validated_schema, schema_version = validate_publish_schema(
        project.get("draft_schema") or {},
        project_schema_version=project.get("schema_version"),
    )
    project_for_publish = {**project, "draft_schema": validated_schema}
    published_project = publish_project_atomically(
        project=project_for_publish,
        project_id=project_id,
        tenant_id=context.tenant_id,
        expected_revision=expected_revision,
        schema_version=schema_version,
        published_at=datetime.now(timezone.utc).isoformat(),
        require_active_entitlement=bool(
            entitlement.get("enforced") and entitlement.get("source") == "feature"
        ),
    )

    logger.info(
        "builder.project_published",
        extra={"tenant_id": context.tenant_id, "user_id": context.user_id, "project_id": project_id},
    )
    record_audit_event(
        request=request,
        tenant_id=context.tenant_id,
        actor_user_id=context.user_id,
        action="builder.project_published",
        target_type="builder_project",
        target_id=project_id,
        metadata={
            "project_slug": project.get("slug"),
            "project_name": project.get("name"),
            "published_version": published_project.get("published_version"),
        },
    )

    return {
        "success": True,
        "project": published_project,
        "site": {
            "subdomain": website_settings.get("subdomain"),
            "tenant_id": website_settings.get("tenant_id"),
        },
    }


@router.post("/users/{user_id}/builder/projects/{project_id}/unpublish", include_in_schema=False)
@router.post("/builder/projects/{project_id}/unpublish")
def unpublish_builder_project(
    project_id: str,
    request: Request,
    response: Response,
    unpublish: Optional[BuilderProjectUnpublish] = Body(default=None),
):
    context = require_builder_context(request, response, require_builder_write_access)
    project = get_project_for_tenant(project_id, context.tenant_id)
    current_revision = _project_revision(project)
    requested_revision = getattr(unpublish, "expected_revision", None) if unpublish else None
    if "draft_revision" in project and requested_revision is None:
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "project_revision_required",
                "Reload the project before unpublishing.",
                context={"current_revision": current_revision},
            ),
        )
    expected_revision = requested_revision if requested_revision is not None else current_revision
    if expected_revision != current_revision:
        _raise_revision_conflict(project_id, context.tenant_id)

    update_query = (
        service_supabase.table("builder_projects")
        .update({"status": "draft"})
        .eq("id", project_id)
        .eq("tenant_id", context.tenant_id)
        .eq("status", "published")
    )
    if "draft_revision" in project:
        update_query = update_query.eq("draft_revision", expected_revision)
    update_response = update_query.execute()
    rows = getattr(update_response, "data", None) or []
    if not rows:
        if str(project.get("status") or "").strip().lower() != "published":
            raise HTTPException(
                status_code=409,
                detail=error_detail(
                    "project_not_published",
                    "This project is not currently published.",
                ),
            )
        _raise_revision_conflict(project_id, context.tenant_id)

    unpublished_project = rows[0]
    record_audit_event(
        request=request,
        tenant_id=context.tenant_id,
        actor_user_id=context.user_id,
        action="builder.project_unpublished",
        target_type="builder_project",
        target_id=project_id,
        metadata={
            "project_slug": project.get("slug"),
            "project_name": project.get("name"),
            "published_version": project.get("published_version"),
        },
    )
    return {"success": True, "project": unpublished_project}

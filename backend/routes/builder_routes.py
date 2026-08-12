import copy
import hashlib
import json
import os
import re
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Body, File, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel, EmailStr, Field, field_validator
from postgrest.exceptions import APIError

from database import service_supabase
from services.asset_registry_service import (
    reconcile_project_asset_references,
    register_builder_asset,
    require_builder_asset_tenant_ownership,
)
from services.builder_asset_storage import (
    BuilderAssetStorageError,
    delete_builder_asset,
    store_builder_asset,
)
from services.builder_asset_validation import (
    BuilderAssetValidationError,
    detect_builder_asset_content_type,
    validate_builder_asset_file,
)
from services.audit_service import record_audit_event
from services.api_errors import error_detail
from services.billing_service import require_publish_entitlement
from services.rate_limit_service import enforce_builder_asset_upload_rate_limit
from services.site_permission_service import assign_project_role, project_role_keys
from services.storage_quota_service import (
    StorageSafetyError,
    finish_storage,
    get_tenant_storage_usage,
    reserve_storage,
)
from services.website_settings_service import require_public_subdomain
from services.url_validation import validate_builder_schema_urls, validate_public_url
from services.tenant_service import (
    TenantContext,
    require_active_tenant_member,
    require_builder_admin_access,
    require_builder_write_access,
)
from services.upload_config import get_public_uploads_dir
from services.entitlement_service import (
    increment_operational_usage,
    require_any_entitlement,
    require_entitlement,
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
RESERVATION_STATUSES = {"new", "confirmed", "cancelled", "completed", "rejected"}
SITE_MEMBER_STATUSES = {"active", "disabled"}
MAX_BUILDER_SCHEMA_BYTES = int(os.getenv("MAX_BUILDER_SCHEMA_BYTES", str(2 * 1024 * 1024)))
MIN_BUILDER_TEXT_FONT_SIZE_PX = 8
MAX_BUILDER_TEXT_FONT_SIZE_PX = 256
UNSAFE_BUILDER_ELEMENT_TYPES = {"html", "rawhtml", "script", "iframe"}
PUBLIC_PAGE_SLUG_PATTERN = re.compile(
    r"^/[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$"
)
RESERVED_PUBLIC_PAGE_SLUGS = {
    "admin", "api", "auth", "builder", "dashboard", "forgot-password",
    "login", "reset-password", "settings", "signup", "verify-email",
}


def validate_builder_text_font_sizes(value: Any) -> None:
    """Reject builder text sizes outside the editor's finite persisted range."""

    def validate_size(raw_value: Any, field_name: str) -> None:
        if raw_value in (None, ""):
            return
        if isinstance(raw_value, bool):
            numeric_value = None
        elif isinstance(raw_value, (int, float)):
            numeric_value = float(raw_value)
        else:
            match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)px", str(raw_value).strip(), re.IGNORECASE)
            numeric_value = float(match.group(1)) if match else None
        if (
            numeric_value is None
            or not math.isfinite(numeric_value)
            or numeric_value < MIN_BUILDER_TEXT_FONT_SIZE_PX
            or numeric_value > MAX_BUILDER_TEXT_FONT_SIZE_PX
        ):
            raise HTTPException(
                status_code=400,
                detail=error_detail(
                    "publish_validation_failed",
                    f"{field_name} must be between {MIN_BUILDER_TEXT_FONT_SIZE_PX}px and "
                    f"{MAX_BUILDER_TEXT_FONT_SIZE_PX}px.",
                    context={"issue_type": "invalid_text_font_size", "field": field_name},
                ),
            )

    def inspect(node: Any, path: str) -> None:
        if isinstance(node, list):
            for index, item in enumerate(node):
                inspect(item, f"{path}[{index}]")
            return
        if not isinstance(node, dict):
            return

        styles = node.get("styles")
        if isinstance(styles, dict):
            for key in ("fontSize", "selectedTextFontSize"):
                if key in styles:
                    validate_size(styles.get(key), f"{path}.styles.{key}")
        for collection_name in ("richTextSizes", "richTextStyles"):
            ranges = node.get(collection_name)
            if isinstance(ranges, list):
                for index, text_range in enumerate(ranges):
                    if isinstance(text_range, dict) and "fontSize" in text_range:
                        validate_size(
                            text_range.get("fontSize"),
                            f"{path}.{collection_name}[{index}].fontSize",
                        )
        for key, child in node.items():
            if key not in {"styles", "richTextSizes", "richTextStyles"}:
                inspect(child, f"{path}.{key}")

    inspect(value, "draft_schema")


def schema_contains_element_type(value: Any, element_type: str) -> bool:
    if isinstance(value, dict):
        if str(value.get("type") or "") == element_type:
            return True
        return any(
            schema_contains_element_type(item, element_type)
            for item in value.values()
        )
    if isinstance(value, list):
        return any(
            schema_contains_element_type(item, element_type)
            for item in value
        )
    return False
BUILDER_ASSET_MAX_BYTES = int(os.getenv("BUILDER_ASSET_MAX_BYTES", str(5 * 1024 * 1024)))
BUILDER_VIDEO_MAX_BYTES = int(os.getenv("BUILDER_VIDEO_MAX_BYTES", str(250 * 1024 * 1024)))
BUILDER_DOCUMENT_MAX_BYTES = int(os.getenv("BUILDER_DOCUMENT_MAX_BYTES", str(50 * 1024 * 1024)))
BUILDER_ASSET_COPY_CHUNK_BYTES = 1024 * 1024
BUILDER_ASSET_UPLOAD_DIR = get_public_uploads_dir()
BUILDER_CLIENT_CONTRACT = "cloud-draft-v1"
BUILDER_ASSET_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
MANAGED_TENANT_ASSET_PATTERN = re.compile(r"^/uploads/tenant_(\d+)/")


def validate_managed_asset_ownership(value: Any, tenant_id: int) -> None:
    if isinstance(value, dict):
        for child in value.values():
            validate_managed_asset_ownership(child, tenant_id)
    elif isinstance(value, list):
        for child in value:
            validate_managed_asset_ownership(child, tenant_id)
    elif isinstance(value, str):
        match = MANAGED_TENANT_ASSET_PATTERN.match(value.strip())
        if match and str(match.group(1)) != str(tenant_id):
            raise HTTPException(
                status_code=400,
                detail=error_detail(
                    "publish_validation_failed",
                    "A managed asset belongs to a different workspace.",
                    context={"issue_type": "asset_tenant_mismatch"},
                ),
            )


def require_supported_builder_client(request: Request) -> str:
    headers = getattr(request, "headers", None) or {}
    supplied = str(headers.get("X-Madar-Builder-Contract") or "").strip()
    supported = {
        item.strip()
        for item in os.getenv(
            "SUPPORTED_BUILDER_CLIENT_CONTRACTS",
            BUILDER_CLIENT_CONTRACT,
        ).split(",")
        if item.strip()
    }
    enforce_missing = os.getenv(
        "ENFORCE_BUILDER_CLIENT_CONTRACT",
        "false",
    ).strip().lower() in {"1", "true", "yes", "on"}
    if (supplied and supplied in supported) or (not supplied and not enforce_missing):
        return supplied
    raise HTTPException(
        status_code=409,
        detail=error_detail(
            "builder_client_upgrade_required",
            "Reload Madar before editing this project.",
        ),
    )


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

    explicit_id_matches = [
        page for page in pages if str(page.get("id") or "") == explicit_default_id
    ] if explicit_default_id else []
    root_pages = [
        page
        for page in pages
        if str(page.get("slug", page.get("path", page.get("route", ""))) or "").strip() == "/"
    ]
    named_home_pages = [
        page
        for page in pages
        if str(page.get("name") or page.get("title") or "").strip().lower() == "home"
    ]
    legacy_unambiguous_pages = named_home_pages if len(named_home_pages) == 1 else (pages if len(pages) == 1 else [])
    candidate_ids = {
        str(page.get("id") or "")
        for page in [
            *explicit_id_matches,
            *explicit_default_pages,
            *root_pages,
            *legacy_unambiguous_pages,
        ]
        if str(page.get("id") or "")
    }
    if (
        (explicit_default_id and len(explicit_id_matches) != 1)
        or len(root_pages) > 1
        or len(candidate_ids) != 1
    ):
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "publish_validation_failed",
                "Exactly one published page must be the homepage.",
                context={
                    "issue_type": "ambiguous_default_page",
                    "default_page_id": explicit_default_id,
                },
            ),
        )
    default_page_id = next(iter(candidate_ids), "")
    default_page = next(
        (page for page in pages if str(page.get("id") or "") == default_page_id),
        None,
    )
    if not default_page:
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "publish_validation_failed",
                "Select a homepage before publishing.",
                context={"issue_type": "missing_default_page"},
            ),
        )
    schema["defaultPageId"] = default_page_id

    # The public root route must stay reachable without role membership.
    for role in schema.get("roles") or []:
        resource_access = role.get("resourceAccess") if isinstance(role, dict) else None
        page_ids = resource_access.get("pageIds") if isinstance(resource_access, dict) else None
        if isinstance(page_ids, list):
            resource_access["pageIds"] = [
                page_id
                for page_id in page_ids
                if str(page_id) != default_page_id
            ]

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

    validated = (
        validate_builder_schema_urls(value, field_name=field_name)
        if validate_urls
        else value
    )
    validate_builder_button_colors(validated, field_name=field_name)
    return validated


BUTTON_COLOR_FIELDS = (
    "backgroundColor",
    "textColor",
    "hoverBackgroundColor",
    "hoverTextColor",
    "borderColor",
)
BUTTON_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _iter_builder_elements(schema: dict[str, Any]):
    for page in schema.get("pages") or []:
        if not isinstance(page, dict):
            continue
        for section in page.get("sections") or []:
            if not isinstance(section, dict):
                continue
            for element in section.get("elements") or []:
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


def validate_builder_button_colors(schema: dict[str, Any], *, field_name: str) -> None:
    for element in _iter_builder_elements(schema):
        if str(element.get("type") or "") != "button":
            continue
        if "style" in element or "buttonColors" in element:
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} button colors must use explicit fields",
            )
        styles = element.get("styles")
        if isinstance(styles, dict) and any(
            field in styles
            for field in ("textColor", "hoverBackgroundColor", "hoverTextColor", "borderColor")
        ):
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} button colors must use explicit fields",
            )
        for color_field in BUTTON_COLOR_FIELDS:
            if color_field not in element:
                continue
            raw_value = element.get(color_field)
            if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
                element.pop(color_field, None)
                continue
            if not isinstance(raw_value, str) or not BUTTON_COLOR_PATTERN.fullmatch(raw_value.strip()):
                raise HTTPException(
                    status_code=400,
                    detail=f"{field_name}.{color_field} must be a six-digit hexadecimal color",
                )
            element[color_field] = raw_value.strip().upper()


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


def _validate_smart_responsive_geometry(schema: dict[str, Any]) -> None:
    responsive_layout = schema.get("responsiveLayout")
    if not isinstance(responsive_layout, dict) or responsive_layout.get("mode") != "smart":
        return
    try:
        engine_version = int(responsive_layout.get("engineVersion"))
    except (TypeError, ValueError):
        engine_version = 0
    if engine_version != 1:
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "publish_validation_failed",
                "This smart responsive engine version cannot be published.",
                context={"issue_type": "unsupported_responsive_engine", "engine_version": engine_version},
            ),
        )

    anchor_widths = {"desktop": 1200.0, "tablet": 768.0, "mobile": 390.0}

    def finite_rect(value: Any) -> dict[str, float] | None:
        if not isinstance(value, dict):
            return None
        try:
            rect = {key: float(value.get(key)) for key in ("x", "y", "width", "height")}
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(item) for item in rect.values()) or rect["width"] <= 0 or rect["height"] <= 0:
            return None
        return rect

    for page in schema.get("pages") or []:
        if not isinstance(page, dict):
            continue
        for section in page.get("sections") or []:
            if not isinstance(section, dict):
                continue
            elements = [element for element in section.get("freeElements") or [] if isinstance(element, dict)]
            for viewport_mode, logical_width in anchor_widths.items():
                manual_solids: list[dict[str, Any]] = []
                for element in elements:
                    capabilities = element.get("responsive", {}).get("capabilities", {})
                    collision_policy = capabilities.get("collisionPolicy") if isinstance(capabilities, dict) else None
                    overrides = element.get("responsive", {}).get("overrides", {})
                    override = overrides.get(viewport_mode) if isinstance(overrides, dict) else None
                    if not isinstance(override, dict) or override.get("mode") != "manual":
                        continue
                    rect = finite_rect(override.get("rect"))
                    block_id = str(element.get("id") or "")
                    if rect is None:
                        raise HTTPException(
                            status_code=400,
                            detail=error_detail(
                                "publish_validation_failed",
                                "A smart responsive manual override has invalid geometry.",
                                context={"issue_type": "invalid_manual_responsive_rect", "block_id": block_id, "viewport": viewport_mode},
                            ),
                        )
                    if rect["y"] < 0:
                        raise HTTPException(
                            status_code=400,
                            detail=error_detail(
                                "publish_validation_failed",
                                "A smart responsive manual override is outside its artboard.",
                                context={"issue_type": "manual_responsive_out_of_bounds", "block_id": block_id, "viewport": viewport_mode},
                            ),
                        )
                    if element.get("layer") == "behindText" or collision_policy in {"overlay", "background"}:
                        continue
                    if rect["x"] < 0 or rect["x"] + rect["width"] > logical_width:
                        raise HTTPException(
                            status_code=400,
                            detail=error_detail(
                                "publish_validation_failed",
                                "A smart responsive manual override is outside its artboard.",
                                context={"issue_type": "manual_responsive_out_of_bounds", "block_id": block_id, "viewport": viewport_mode},
                            ),
                        )
                    manual_solids.append({"id": block_id, "rect": rect})

                active: list[dict[str, Any]] = []
                for current in sorted(manual_solids, key=lambda item: (item["rect"]["x"], item["rect"]["y"], item["id"])):
                    current_rect = current["rect"]
                    active = [
                        item for item in active
                        if item["rect"]["x"] + item["rect"]["width"] > current_rect["x"]
                    ]
                    for other in active:
                        other_rect = other["rect"]
                        vertical_overlap = (
                            current_rect["y"] < other_rect["y"] + other_rect["height"]
                            and current_rect["y"] + current_rect["height"] > other_rect["y"]
                        )
                        if vertical_overlap:
                            raise HTTPException(
                                status_code=400,
                                detail=error_detail(
                                    "publish_validation_failed",
                                    "Smart responsive manual components overlap.",
                                    context={
                                        "issue_type": "unresolved_manual_responsive_collision",
                                        "page_id": str(page.get("id") or ""),
                                        "section_id": str(section.get("id") or ""),
                                        "viewport": viewport_mode,
                                        "block_ids": sorted([other["id"], current["id"]]),
                                    },
                                ),
                            )
                    active.append(current)


def require_schema_asset_tenant(schema: dict[str, Any], tenant_id: int) -> None:
    try:
        require_builder_asset_tenant_ownership(schema, tenant_id=tenant_id)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=error_detail(
                "builder_asset_tenant_mismatch",
                "Managed assets must belong to the active workspace.",
            ),
        ) from error


def validate_publish_schema(
    value: Any,
    *,
    project_schema_version: Any = None,
    tenant_id: int | None = None,
) -> tuple[dict[str, Any], int]:
    """Revalidate persisted builder JSON and its supported schema version at publish."""

    schema = copy.deepcopy(
        assert_json_object(value, field_name="draft_schema", validate_urls=False)
    )
    validate_builder_text_font_sizes(schema)
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
    if tenant_id is not None:
        validate_managed_asset_ownership(schema, tenant_id)

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
        if element_type in {"button", "imageButton"}:
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

    _validate_smart_responsive_geometry(schema)
    validate_builder_schema_urls(schema, field_name="draft_schema")
    return schema, schema_version


class BuilderProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1)
    draft_schema: dict[str, Any] = Field(default_factory=dict)

    @field_validator("draft_schema")
    @classmethod
    def validate_draft_schema(cls, value):
        validated = assert_json_object(value)
        validate_builder_text_font_sizes(validated)
        return validated


class BuilderProjectUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    status: Optional[str] = None
    draft_schema: Optional[dict[str, Any]] = None
    expected_revision: Optional[int] = Field(default=None, ge=0)

    @field_validator("draft_schema")
    @classmethod
    def validate_draft_schema(cls, value):
        validated = assert_json_object(value)
        validate_builder_text_font_sizes(validated)
        return validated


class BuilderProjectPublish(BaseModel):
    message: Optional[str] = None
    expected_revision: Optional[int] = Field(default=None, ge=0)


class BuilderProjectUnpublish(BaseModel):
    expected_revision: Optional[int] = Field(default=None, ge=0)


class BuilderPublicProjectBindingUpdate(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=80)


class BuilderFormSubmissionStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1)


class BuilderReservationStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1)


class BuilderSiteMemberCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=200)
    role_id: Optional[str] = Field(default=None, max_length=160)
    status: str = Field(default="active", min_length=1, max_length=32)


class BuilderSiteMemberUpdate(BaseModel):
    role_id: Optional[str] = Field(default=None, max_length=160)
    status: Optional[str] = Field(default=None, min_length=1, max_length=32)


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


def normalize_site_member_status(value: str) -> str:
    status = (value or "").strip().lower()
    if status in SITE_MEMBER_STATUSES:
        return status
    raise HTTPException(status_code=400, detail="Invalid site member status")


def normalize_site_member_role(project: dict, value: str | None) -> str:
    role = str(value or "").strip()
    if not role:
        return "customer"
    if role not in project_role_keys(project):
        raise HTTPException(status_code=400, detail="Selected role is invalid")
    return role


def format_site_member(membership: dict, user: dict | None) -> dict:
    user = user or {}
    first_name = str(user.get("first_name") or "").strip()
    last_name = str(user.get("last_name") or "").strip()
    full_name = " ".join(part for part in (first_name, last_name) if part).strip()
    status = str(membership.get("status") or "active").strip().lower()
    return {
        "id": str(membership.get("id") or ""),
        "userId": user.get("id") or membership.get("user_id"),
        "authId": str(user.get("auth_id") or membership.get("auth_id") or ""),
        "name": full_name or str(user.get("email") or "Site member"),
        "email": str(user.get("email") or ""),
        "roleId": str(membership.get("role") or "customer"),
        "status": "Disabled" if status == "disabled" else "Active",
        "source": str(membership.get("source") or "registered"),
        "createdAt": membership.get("created_at"),
        "updatedAt": membership.get("updated_at"),
    }


def get_site_members_for_project(tenant_id: int, project_id: str) -> list[dict]:
    assignment_response = (
        service_supabase.table("tenant_site_project_role_assignments")
        .select("membership_id,role_id")
        .eq("project_id", project_id)
        .execute()
    )
    assignments = getattr(assignment_response, "data", None) or []
    membership_ids = [row.get("membership_id") for row in assignments if row.get("membership_id") is not None]
    if not membership_ids:
        return []
    membership_response = (
        service_supabase.table("tenant_site_memberships")
        .select("*")
        .eq("tenant_id", tenant_id)
        .in_("id", membership_ids)
        .order("created_at", desc=True)
        .execute()
    )
    memberships = getattr(membership_response, "data", None) or []
    role_ids = [row.get("role_id") for row in assignments if row.get("role_id") is not None]
    role_keys_by_id = {}
    if role_ids:
        roles_response = (
            service_supabase.table("tenant_site_project_roles")
            .select("id,role_key,deleted_at")
            .eq("project_id", project_id)
            .in_("id", role_ids)
            .execute()
        )
        role_keys_by_id = {
            str(role.get("id")): role.get("role_key")
            for role in (getattr(roles_response, "data", None) or [])
            if not role.get("deleted_at")
        }
    role_by_membership_id = {
        str(row.get("membership_id")): role_keys_by_id.get(str(row.get("role_id")))
        for row in assignments
    }
    user_ids = [membership.get("user_id") for membership in memberships if membership.get("user_id") is not None]
    users_by_id = {}
    if user_ids:
        users_response = (
            service_supabase.table("users")
            .select("id, auth_id, first_name, last_name, email, account_status, email_verified")
            .in_("id", user_ids)
            .execute()
        )
        users_by_id = {
            str(user.get("id")): user
            for user in (getattr(users_response, "data", None) or [])
        }
    return [
        format_site_member(
            {**membership, "role": role_by_membership_id.get(str(membership.get("id"))) or "customer"},
            users_by_id.get(str(membership.get("user_id"))),
        )
        for membership in memberships
        if role_by_membership_id.get(str(membership.get("id")))
    ]


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


def get_website_settings_record(tenant_id: int) -> dict | None:
    response = (
        service_supabase.table("website_settings")
        .select("*")
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    return rows[0] if rows else None


def get_public_project_binding(tenant_id: int, user_id: int) -> tuple[dict, dict | None]:
    settings = get_website_settings_record(tenant_id) or {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "published_project_id": None,
    }
    project_id = str(settings.get("published_project_id") or "").strip()
    if not project_id:
        return settings, None

    project_response = (
        service_supabase.table("builder_projects")
        .select("id, tenant_id, name, slug, status, published_version, last_published_at")
        .eq("id", project_id)
        .eq("tenant_id", tenant_id)
        .eq("status", "published")
        .limit(1)
        .execute()
    )
    projects = getattr(project_response, "data", None) or []
    return settings, projects[0] if projects else None


def format_public_project_binding(settings: dict, project: dict | None) -> dict:
    public_project = None
    if project:
        public_project = {
            key: project.get(key)
            for key in (
                "id",
                "name",
                "slug",
                "status",
                "published_version",
                "last_published_at",
            )
        }
    return {
        "project_id": project.get("id") if project else None,
        "project": public_project,
        "subdomain": settings.get("subdomain"),
    }


def reject_bound_project_transition(project_id: str, tenant_id: int) -> None:
    settings = get_website_settings_record(tenant_id)
    if settings and str(settings.get("published_project_id") or "") == str(project_id):
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "public_project_bound",
                "Select another live project before changing this project's published state.",
            ),
        )


def bind_first_published_project_if_unbound(
    *, settings: dict, project: dict, tenant_id: int
) -> tuple[dict, bool]:
    if settings.get("published_project_id"):
        return settings, False

    if not settings.get("id"):
        return settings, False

    project_id = str(project.get("id") or "")
    existing_response = (
        service_supabase.table("builder_projects")
        .select("id")
        .eq("tenant_id", tenant_id)
        .eq("status", "published")
        .not_.is_("published_schema", "null")
        .limit(2)
        .execute()
    )
    other_projects = [
        row
        for row in (getattr(existing_response, "data", None) or [])
        if str(row.get("id") or "") != project_id
    ]
    if other_projects:
        return settings, False

    update_response = (
        service_supabase.table("website_settings")
        .update({"published_project_id": project_id})
        .eq("id", settings.get("id"))
        .eq("tenant_id", tenant_id)
        .execute()
    )
    rows = getattr(update_response, "data", None) or []
    if not rows:
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "public_project_binding_conflict",
                "The live project selection changed. Reload and try again.",
            ),
        )
    return rows[0], True

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
                "publish_validated_builder_project_atomic",
                {
                    "p_project_id": project_id,
                    "p_tenant_id": tenant_id,
                    "p_expected_revision": expected_revision,
                    "p_published_schema": project.get("draft_schema") or {},
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
    require_entitlement(context.tenant_id, "image_uploads")
    enforce_builder_asset_upload_rate_limit(request, context.user_id, context.tenant_id)

    declared_content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    source_extension = Path(file.filename or "").suffix.lower()
    is_declared_video = declared_content_type.startswith("video/") or (
        not declared_content_type and source_extension in {".mp4", ".webm"}
    )
    is_declared_document = declared_content_type in {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    } or (not declared_content_type and source_extension in {".pdf", ".doc", ".docx"})
    asset_kind = "video" if is_declared_video else "document" if is_declared_document else "image"

    if declared_content_type and declared_content_type not in BUILDER_ASSET_EXTENSIONS:
        detail = (
            "Please upload an MP4 or WebM video"
            if is_declared_video
            else "Please upload a PDF, DOC, or DOCX document"
            if declared_content_type.startswith("application/")
            else "Please upload a PNG, JPG, or WebP image"
        )
        raise HTTPException(status_code=400, detail=detail)

    accepted_source_extensions = {
        "image/png": {".png"},
        "image/jpeg": {".jpg", ".jpeg"},
        "image/webp": {".webp"},
        "video/mp4": {".mp4"},
        "video/webm": {".webm"},
        "application/pdf": {".pdf"},
        "application/msword": {".doc"},
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
    }
    if (
        declared_content_type
        and source_extension not in accepted_source_extensions[declared_content_type]
    ):
        raise HTTPException(
            status_code=400,
            detail=f"{asset_kind.title()} filename does not match the declared file type",
        )

    read_limit = (
        BUILDER_VIDEO_MAX_BYTES
        if asset_kind == "video"
        else BUILDER_DOCUMENT_MAX_BYTES
        if asset_kind == "document"
        else BUILDER_ASSET_MAX_BYTES
    )
    file_size = file.size
    if file_size is None:
        current_position = file.file.tell()
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(current_position)

    if not file_size:
        detail = f"{asset_kind.title()} file is required"
        raise HTTPException(status_code=400, detail=detail)

    if file_size > read_limit:
        detail = (
            "Video file must be 250MB or smaller"
            if asset_kind == "video"
            else "Document file must be 50MB or smaller"
            if asset_kind == "document"
            else "Image file must be 5MB or smaller"
        )
        raise HTTPException(status_code=413, detail=detail)

    header = await file.read(32)
    await file.seek(0)
    detected_content_type = detect_builder_asset_content_type(header)

    if not detected_content_type:
        detail = (
            "Please upload an MP4 or WebM video"
            if asset_kind == "video"
            else "Please upload a PDF, DOC, or DOCX document"
            if asset_kind == "document"
            else "Please upload a PNG, JPG, or WebP image"
        )
        raise HTTPException(status_code=400, detail=detail)

    if declared_content_type and declared_content_type != detected_content_type:
        detail = f"{asset_kind.title()} content does not match the declared file type"
        raise HTTPException(status_code=400, detail=detail)

    if source_extension not in accepted_source_extensions[detected_content_type]:
        detected_kind = (
            "video"
            if detected_content_type.startswith("video/")
            else "document"
            if detected_content_type.startswith("application/")
            else "image"
        )
        raise HTTPException(
            status_code=400,
            detail=f"{detected_kind.title()} filename does not match the file content",
        )

    extension = BUILDER_ASSET_EXTENSIONS[detected_content_type]
    filename = f"{uuid4().hex}{extension}"
    target_dir, target_path, tenant_dir = get_builder_asset_target(context.tenant_id, filename)

    try:
        storage_reservation_id = reserve_storage(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            category="builder_asset",
            size_bytes=file_size,
            storage_root=BUILDER_ASSET_UPLOAD_DIR,
        )
    except StorageSafetyError as error:
        raise HTTPException(
            status_code=507,
            detail=error_detail(error.code, "Storage capacity is unavailable."),
        ) from error

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        bytes_written = 0
        with target_path.open("xb") as destination:
            while chunk := await file.read(BUILDER_ASSET_COPY_CHUNK_BYTES):
                bytes_written += len(chunk)
                if bytes_written > read_limit:
                    raise ValueError("builder_asset_too_large")
                digest.update(chunk)
                destination.write(chunk)
        if bytes_written != file_size:
            raise OSError("Uploaded asset size changed while saving")
        validate_builder_asset_file(target_path, detected_content_type)
        sha256_hex = digest.hexdigest()
    except BuilderAssetValidationError as error:
        target_path.unlink(missing_ok=True)
        finish_storage(reservation_id=storage_reservation_id, succeeded=False)
        raise HTTPException(
            status_code=400,
            detail=f"{asset_kind.title()} file content is invalid",
        ) from error
    except ValueError as error:
        target_path.unlink(missing_ok=True)
        finish_storage(reservation_id=storage_reservation_id, succeeded=False)
        detail = (
            "Video file must be 250MB or smaller"
            if asset_kind == "video"
            else "Document file must be 50MB or smaller"
            if asset_kind == "document"
            else "Image file must be 5MB or smaller"
        )
        raise HTTPException(status_code=413, detail=detail) from error
    except OSError as error:
        target_path.unlink(missing_ok=True)
        try:
            finish_storage(reservation_id=storage_reservation_id, succeeded=False)
        except Exception as accounting_error:
            logger.error(
                "builder.asset_reservation_release_failed",
                extra={
                    "tenant_id": context.tenant_id,
                    "error_type": type(accounting_error).__name__,
                },
            )
        logger.error(
            "builder.asset_write_failed",
            extra={
                "tenant_id": context.tenant_id,
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(
            status_code=503,
            detail=error_detail(
                "asset_storage_unavailable",
                "Asset storage is temporarily unavailable.",
            ),
        ) from error
    except BaseException:
        # Upload cancellation (including a disconnected client) is not an
        # Exception on every Python version. Always remove partial local data
        # and release the reservation before propagating cancellation/failure.
        target_path.unlink(missing_ok=True)
        try:
            finish_storage(reservation_id=storage_reservation_id, succeeded=False)
        except Exception as accounting_error:
            logger.error(
                "builder.asset_reservation_release_failed",
                extra={
                    "tenant_id": context.tenant_id,
                    "error_type": type(accounting_error).__name__,
                },
            )
        raise

    storage_key = f"{tenant_dir}/builder_assets/{filename}"
    asset_url = f"/uploads/{storage_key}"
    try:
        store_builder_asset(
            storage_key=storage_key,
            source_path=target_path,
            content_type=detected_content_type,
        )
    except BuilderAssetStorageError as error:
        target_path.unlink(missing_ok=True)
        finish_storage(reservation_id=storage_reservation_id, succeeded=False)
        raise HTTPException(
            status_code=503,
            detail=error_detail(
                "asset_storage_unavailable",
                "Asset storage is temporarily unavailable.",
            ),
        ) from error

    try:
        registered_asset = register_builder_asset(
            tenant_id=context.tenant_id,
            uploader_user_id=context.user_id,
            storage_key=storage_key,
            original_filename=file.filename or "asset",
            managed_filename=filename,
            mime_type=detected_content_type,
            size_bytes=bytes_written,
            sha256_hex=sha256_hex,
        )
    except Exception as error:
        target_path.unlink(missing_ok=True)
        try:
            delete_builder_asset(storage_key=storage_key)
        except Exception:
            logger.warning("builder.asset_durable_rollback_failed", extra={"storage_key": storage_key})
        finish_storage(reservation_id=storage_reservation_id, succeeded=False)
        logger.error(
            "builder.asset_registry_failed",
            extra={
                "tenant_id": context.tenant_id,
                "error_type": type(error).__name__,
            },
        )
        raise HTTPException(
            status_code=503,
            detail="Asset storage is temporarily unavailable",
        ) from error
    try:
        finish_storage(
            reservation_id=storage_reservation_id,
            succeeded=True,
            storage_key=storage_key,
            sha256_hex=sha256_hex,
        )
    except Exception as error:
        target_path.unlink(missing_ok=True)
        try:
            delete_builder_asset(storage_key=storage_key)
        except Exception:
            logger.warning("builder.asset_durable_rollback_failed", extra={"storage_key": storage_key})
        logger.error(
            "builder.asset_accounting_failed",
            extra={"tenant_id": context.tenant_id, "error_type": type(error).__name__},
        )
        raise HTTPException(status_code=503, detail="Asset accounting is temporarily unavailable") from error

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
            "size_bytes": bytes_written,
            "extension": extension,
        },
    )

    return {
        "success": True,
        "asset_url": asset_url,
        "url": asset_url,
        "content_type": detected_content_type,
        "asset_id": registered_asset.get("id"),
    }


@router.get("/builder/storage/usage")
def get_builder_storage_usage(request: Request, response: Response):
    context = require_builder_context(request, response, require_active_tenant_member)
    return {"success": True, "storage": get_tenant_storage_usage(context.tenant_id)}


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
    require_entitlement(context.tenant_id, "reservation_management")
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
    require_entitlement(context.tenant_id, "reservation_management")
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
    require_entitlement(context.tenant_id, "reservation_management")
    status = normalize_reservation_status(status_update.status)

    rpc = getattr(service_supabase, "rpc", None)
    if callable(rpc):
        update_response = rpc(
            "update_builder_reservation_status_notified_safe",
            {
                "p_reservation_id": reservation_id,
                "p_tenant_id": context.tenant_id,
                "p_status": status,
                "p_updated_at": datetime.now(timezone.utc).isoformat(),
            },
        ).execute()
    else:
        # Lightweight in-memory unit-test clients do not implement RPC.
        # Production status mutation and email intent share the RPC transaction.
        update_response = (
            service_supabase.table("builder_reservations")
            .update({"status": status, "updated_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", reservation_id)
            .eq("tenant_id", context.tenant_id)
            .execute()
        )
    update_data = getattr(update_response, "data", None)
    reservation = update_data[0] if isinstance(update_data, list) and update_data else update_data

    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    return {"success": True, "reservation": format_reservation(reservation)}


@router.get("/builder/site-binding")
def get_builder_site_binding(request: Request, response: Response):
    context = require_builder_context(request, response, require_active_tenant_member)
    settings, project = get_public_project_binding(context.tenant_id, context.user_id)
    return {
        "success": True,
        "binding": format_public_project_binding(settings, project),
    }


@router.put("/builder/site-binding")
def update_builder_site_binding(
    binding: BuilderPublicProjectBindingUpdate,
    request: Request,
    response: Response,
):
    require_supported_builder_client(request)
    context = require_builder_context(request, response, require_builder_admin_access)
    project = get_project_for_tenant(binding.project_id, context.tenant_id)
    if (
        str(project.get("status") or "").lower() != "published"
        or not isinstance(project.get("published_schema"), dict)
    ):
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "public_project_not_published",
                "Publish this project before making it live.",
            ),
        )

    settings = get_website_settings_record(context.tenant_id)
    if not settings:
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "website_settings_required",
                "Configure website settings before selecting a live project.",
            ),
        )
    previous_project_id = settings.get("published_project_id")
    try:
        update_response = (
            service_supabase.table("website_settings")
            .update({"published_project_id": project.get("id")})
            .eq("id", settings.get("id"))
            .eq("tenant_id", context.tenant_id)
            .execute()
        )
    except Exception as error:
        if "public_project_binding_invalid" in str(error).lower():
            raise HTTPException(
                status_code=409,
                detail=error_detail(
                    "public_project_binding_invalid",
                    "The selected project cannot be made live.",
                ),
            )
        raise
    rows = getattr(update_response, "data", None) or []
    if not rows:
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "public_project_binding_conflict",
                "The live project selection changed. Reload and try again.",
            ),
        )

    record_audit_event(
        request=request,
        tenant_id=context.tenant_id,
        actor_user_id=context.user_id,
        action="builder.public_project_bound",
        target_type="builder_project",
        target_id=str(project.get("id") or ""),
        metadata={"previous_project_id": previous_project_id},
    )
    return {
        "success": True,
        "binding": format_public_project_binding(rows[0], project),
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
    require_supported_builder_client(request)
    context = require_builder_context(request, response, require_builder_write_access)
    require_any_entitlement(
        context.tenant_id,
        {"forms", "page_builder"},
        message="An active Forms or page-builder plan is required.",
    )

    draft_schema = assert_json_object(project.draft_schema)
    require_schema_asset_tenant(draft_schema, context.tenant_id)
    payload = {
        "tenant_id": context.tenant_id,
        "owner_user_id": context.user_id,
        "name": normalize_name(project.name),
        "slug": normalize_slug(project.slug),
        "status": "draft",
        "draft_schema": draft_schema,
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

    form_count = len(draft_schema.get("forms") or []) if isinstance(draft_schema.get("forms"), list) else 0
    if form_count:
        increment_operational_usage(context.tenant_id, "forms_created", delta=form_count)
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


@router.get("/builder/projects/{project_id}/site-members")
def list_builder_site_members(project_id: str, request: Request, response: Response):
    context = require_builder_context(request, response, require_builder_admin_access)
    get_project_for_tenant(project_id, context.tenant_id)
    return {
        "success": True,
        "members": get_site_members_for_project(context.tenant_id, project_id),
    }


@router.post("/builder/projects/{project_id}/site-members", status_code=201)
def create_builder_site_member(
    project_id: str,
    member: BuilderSiteMemberCreate,
    request: Request,
    response: Response,
):
    context = require_builder_context(request, response, require_builder_admin_access)
    project = get_project_for_tenant(project_id, context.tenant_id)
    clean_email = str(member.email).strip().lower()
    clean_name = member.full_name.strip()
    name_parts = clean_name.split(None, 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    role = normalize_site_member_role(project, member.role_id)
    status = normalize_site_member_status(member.status)

    existing_user_response = (
        service_supabase.table("users")
        .select("id, auth_id, first_name, last_name, email")
        .eq("email", clean_email)
        .limit(1)
        .execute()
    )
    existing_users = getattr(existing_user_response, "data", None) or []
    local_user = existing_users[0] if existing_users else None
    auth_user_id = str((local_user or {}).get("auth_id") or "")
    created_auth_user = False
    created_local_user = False

    if local_user:
        existing_membership_response = (
            service_supabase.table("tenant_site_memberships")
            .select("id")
            .eq("tenant_id", context.tenant_id)
            .eq("user_id", local_user.get("id"))
            .limit(1)
            .execute()
        )
        if getattr(existing_membership_response, "data", None):
            raise HTTPException(status_code=409, detail="This user already belongs to the website")
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Use a different email.",
        )
    else:
        try:
            auth_response = service_supabase.auth.admin.create_user(
                {
                    "email": clean_email,
                    "password": member.password,
                    "email_confirm": True,
                    "user_metadata": {
                        "first_name": first_name,
                        "last_name": last_name,
                    },
                }
            )
        except Exception as error:
            logger.warning(
                "builder.site_member_auth_create_failed",
                extra={"tenant_id": context.tenant_id, "error_type": type(error).__name__},
            )
            raise HTTPException(status_code=409, detail="Could not create this user account") from error

        auth_user = getattr(auth_response, "user", None)
        auth_user_id = str(getattr(auth_user, "id", "") or "")
        if not auth_user_id:
            raise HTTPException(status_code=500, detail="Could not create this user account")
        created_auth_user = True

        try:
            local_user_response = service_supabase.table("users").insert(
                {
                    "auth_id": auth_user_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": clean_email,
                    "tenant_id": None,
                    "account_kind": "site_visitor",
                    "account_status": "active",
                    "email_verified": True,
                    "email_verified_at": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()
            local_users = getattr(local_user_response, "data", None) or []
            local_user = local_users[0] if local_users else None
            if not local_user:
                raise RuntimeError("Local user row was not returned")
            created_local_user = True
        except Exception as error:
            try:
                service_supabase.auth.admin.delete_user(auth_user_id)
            except Exception:
                pass
            raise HTTPException(status_code=500, detail="Could not save this user account") from error

    try:
        membership_response = service_supabase.table("tenant_site_memberships").insert(
            {
                "tenant_id": context.tenant_id,
                "user_id": local_user["id"],
                "auth_id": auth_user_id,
                "role": role,
                "status": status,
                "source": "admin",
            }
        ).execute()
        memberships = getattr(membership_response, "data", None) or []
        membership = memberships[0] if memberships else None
        if not membership:
            raise RuntimeError("Membership row was not returned")
        assign_project_role(
            membership_id=int(membership["id"]),
            tenant_id=context.tenant_id,
            project=project,
            role_key=role,
            actor_user_id=context.user_id,
            client=service_supabase,
        )
    except Exception as error:
        if 'membership' in locals() and membership:
            try:
                service_supabase.table("tenant_site_memberships").delete().eq("id", membership["id"]).eq("tenant_id", context.tenant_id).execute()
            except Exception:
                pass
        if created_local_user:
            try:
                service_supabase.table("users").delete().eq("id", local_user["id"]).execute()
            except Exception:
                pass
        if created_auth_user:
            try:
                service_supabase.auth.admin.delete_user(auth_user_id)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="Could not add this user to the website") from error

    record_audit_event(
        request=request,
        tenant_id=context.tenant_id,
        actor_user_id=context.user_id,
        action="builder.site_member_created",
        target_type="tenant_site_membership",
        target_id=str(membership.get("id") or ""),
        metadata={"project_id": project_id, "role": role, "status": status},
    )
    return {
        "success": True,
        "member": format_site_member(membership, local_user),
    }


@router.patch("/builder/projects/{project_id}/site-members/{membership_id}")
def update_builder_site_member(
    project_id: str,
    membership_id: int,
    update: BuilderSiteMemberUpdate,
    request: Request,
    response: Response,
):
    context = require_builder_context(request, response, require_builder_admin_access)
    project = get_project_for_tenant(project_id, context.tenant_id)
    update_payload = {}
    role = None
    if update.role_id is not None:
        role = normalize_site_member_role(project, update.role_id)
    if update.status is not None:
        update_payload["status"] = normalize_site_member_status(update.status)
    if not update_payload and role is None:
        raise HTTPException(status_code=400, detail="No member changes were provided")

    membership_query = service_supabase.table("tenant_site_memberships")
    if update_payload:
        membership_query = membership_query.update({**update_payload, "updated_at": datetime.now(timezone.utc).isoformat()})
    else:
        membership_query = membership_query.select("*")
    membership_response = (
        membership_query
        .eq("id", membership_id)
        .eq("tenant_id", context.tenant_id)
        .execute()
    )
    memberships = getattr(membership_response, "data", None) or []
    if not memberships:
        raise HTTPException(status_code=404, detail="Site member not found")
    membership = memberships[0]
    if role is not None:
        try:
            assign_project_role(
                membership_id=membership_id,
                tenant_id=context.tenant_id,
                project=project,
                role_key=role,
                actor_user_id=context.user_id,
                client=service_supabase,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Selected role is invalid") from error
        membership = {**membership, "role": role}
    user_response = (
        service_supabase.table("users")
        .select("id, auth_id, first_name, last_name, email")
        .eq("id", membership.get("user_id"))
        .limit(1)
        .execute()
    )
    users = getattr(user_response, "data", None) or []

    record_audit_event(
        request=request,
        tenant_id=context.tenant_id,
        actor_user_id=context.user_id,
        action="builder.site_member_updated",
        target_type="tenant_site_membership",
        target_id=str(membership_id),
        metadata={"project_id": project_id, **update_payload, **({"role": role} if role else {})},
    )
    return {
        "success": True,
        "member": format_site_member(membership, users[0] if users else None),
    }


@router.delete("/builder/projects/{project_id}/site-members/{membership_id}")
def delete_builder_site_member(
    project_id: str,
    membership_id: int,
    request: Request,
    response: Response,
):
    context = require_builder_context(request, response, require_builder_admin_access)
    get_project_for_tenant(project_id, context.tenant_id)
    membership_response = (
        service_supabase.table("tenant_site_memberships")
        .select("id")
        .eq("id", membership_id)
        .eq("tenant_id", context.tenant_id)
        .limit(1)
        .execute()
    )
    if not (getattr(membership_response, "data", None) or []):
        raise HTTPException(status_code=404, detail="Site member not found")
    delete_response = (
        service_supabase.table("tenant_site_project_role_assignments")
        .delete()
        .eq("membership_id", membership_id)
        .eq("project_id", project_id)
        .execute()
    )
    deleted = getattr(delete_response, "data", None) or []
    if not deleted:
        raise HTTPException(status_code=404, detail="Site member not found")

    record_audit_event(
        request=request,
        tenant_id=context.tenant_id,
        actor_user_id=context.user_id,
        action="builder.site_member_removed",
        target_type="tenant_site_membership",
        target_id=str(membership_id),
        metadata={"project_id": project_id},
    )
    return {"success": True, "removed": True}


@router.put("/users/{user_id}/builder/projects/{project_id}", include_in_schema=False)
@router.put("/builder/projects/{project_id}")
def update_builder_project(
    project_id: str,
    project: BuilderProjectUpdate,
    request: Request,
    response: Response,
):
    require_supported_builder_client(request)
    context = require_builder_context(request, response, require_builder_write_access)
    existing_project = get_project_for_tenant(project_id, context.tenant_id)
    if str(existing_project.get("status") or "draft").strip().lower() == "archived":
        raise HTTPException(
            status_code=409,
            detail=error_detail(
                "builder_project_archived",
                "Archived projects cannot be edited.",
            ),
        )
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
        require_schema_asset_tenant(update_payload["draft_schema"], context.tenant_id)

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
        if "draft_schema" in update_payload:
            previous_forms = (existing_project.get("draft_schema") or {}).get("forms") or []
            next_forms = update_payload["draft_schema"].get("forms") or []
            added_forms = max(
                (len(next_forms) if isinstance(next_forms, list) else 0)
                - (len(previous_forms) if isinstance(previous_forms, list) else 0),
                0,
            )
            if added_forms:
                increment_operational_usage(
                    context.tenant_id,
                    "forms_created",
                    delta=added_forms,
                )
    except Exception as error:
        if "duplicate" in str(error).lower() or "unique" in str(error).lower():
            raise HTTPException(status_code=409, detail="Project slug already exists")

        logger.warning("builder.project_update_failed", extra={"tenant_id": context.tenant_id, "user_id": context.user_id, "project_id": project_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=500, detail="Could not update builder project")

    if not (getattr(update_response, "data", None) or []):
        _raise_revision_conflict(project_id, context.tenant_id)

    if project.draft_schema is not None:
        try:
            reconcile_project_asset_references(
                project_id=project_id,
                tenant_id=context.tenant_id,
                schema=update_payload["draft_schema"],
                client=service_supabase,
            )
        except Exception as error:
            # The canonical project save has already committed. Keep the upload
            # grace period intact and let the bounded reconciliation job repair
            # registry metadata; never report the committed save as failed.
            logger.error(
                "builder.asset_reconciliation_failed",
                extra={
                    "tenant_id": context.tenant_id,
                    "project_id": project_id,
                    "error_type": type(error).__name__,
                },
            )

    return {
        "success": True,
        "project": first_row(update_response),
    }


@router.delete("/users/{user_id}/builder/projects/{project_id}", include_in_schema=False)
@router.delete("/builder/projects/{project_id}")
def archive_builder_project(project_id: str, request: Request, response: Response):
    require_supported_builder_client(request)
    context = require_builder_context(request, response, require_builder_admin_access)
    project = get_project_for_tenant(project_id, context.tenant_id)
    reject_bound_project_transition(project_id, context.tenant_id)

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
    try:
        reconcile_project_asset_references(
            project_id=project_id,
            tenant_id=context.tenant_id,
            schema={},
            client=service_supabase,
        )
    except Exception as error:
        logger.error(
            "builder.asset_archive_reconciliation_failed",
            extra={
                "tenant_id": context.tenant_id,
                "project_id": project_id,
                "error_type": type(error).__name__,
            },
        )
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
    require_entitlement(context.tenant_id, "response_management")
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
    require_entitlement(context.tenant_id, "response_management")
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
    require_entitlement(context.tenant_id, "response_management")
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
    require_supported_builder_client(request)
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
        tenant_id=context.tenant_id,
    )
    require_schema_asset_tenant(validated_schema, context.tenant_id)
    if schema_contains_element_type(validated_schema, "reservationBlock"):
        require_entitlement(
            context.tenant_id,
            "reservations",
            message="Business Plus is required to publish reservation blocks.",
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
    # Migration 072 performs an unambiguous first publication binding inside
    # this same RPC transaction. Never follow a successful RPC with a second
    # activation write: that would recreate the old hybrid-publication window.
    binding_created = not bool(website_settings.get("published_project_id"))
    if binding_created:
        website_settings = {**website_settings, "published_project_id": project_id}

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
            "public_binding_created": binding_created,
        },
    )

    return {
        "success": True,
        "project": published_project,
        "site": {
            "subdomain": website_settings.get("subdomain"),
            "standard_path_slug": (
                website_settings.get("standard_path_slug")
                or website_settings.get("subdomain")
            ),
            "tenant_id": website_settings.get("tenant_id"),
            "published_project_id": website_settings.get("published_project_id"),
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
    require_supported_builder_client(request)
    context = require_builder_context(request, response, require_builder_write_access)
    project = get_project_for_tenant(project_id, context.tenant_id)
    reject_bound_project_transition(project_id, context.tenant_id)
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

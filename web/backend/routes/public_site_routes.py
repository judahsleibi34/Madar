import logging
import base64
import copy
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.parse import quote, urlparse
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from database import service_supabase, supabase
from services.auth_service import (
    auth_user_email_is_verified,
    build_user_payload,
    delete_auth_cookies,
    get_authenticated_user_row,
    set_auth_cookies,
)
from services.frontend_url import resolve_frontend_url
from services.rate_limit_service import (
    enforce_auth_rate_limit,
    enforce_public_form_submission_rate_limit,
    enforce_public_rate_limit,
    get_client_ip,
)
from services.api_errors import api_error
from services.form_draft_service import build_form_draft_token, parse_form_draft_token
from services.account_lifecycle_service import synchronize_verified_account
from services.ecommerce_cache_service import (
    ecommerce_cache_key,
    get_or_create_ecommerce_cache,
)
from services.screen_time_service import record_screen_time
from services.site_permission_service import (
    assign_project_role,
    has_project_permission,
    resource_is_role_restricted,
)
from services.entitlement_service import (
    increment_operational_usage,
    require_branded_subdomain,
    require_public_runtime_entitlement,
    require_entitlement,
)
from services.tenant_lifecycle_service import tenant_is_active
from services.hosted_address_service import (
    HOSTED_ADDRESS_PATTERN,
    normalize_hosted_address,
)
from services.notification_action_service import build_notification_action
from services.calendar_workspace_cache_service import invalidate_calendar_workspace_cache
from services.public_quiz_service import (
    build_attempt_payload,
    grade as grade_public_quiz,
    is_quiz as is_public_quiz,
    public_form as serialize_public_form,
    redact_public_value,
    validate_submission_order,
)

router = APIRouter(prefix="/public", tags=["Public Sites"])
logger = logging.getLogger(__name__)

SUBDOMAIN_PATTERN = HOSTED_ADDRESS_PATTERN
MAX_PUBLIC_FORM_ANSWER_FIELDS = 100
MAX_PUBLIC_FORM_ANSWER_STRING_LENGTH = 5000
MAX_PUBLIC_FORM_ANSWERS_JSON_BYTES = 64 * 1024
MAX_PUBLIC_BLOCK_EVENT_FIELDS = 100
MAX_PUBLIC_BLOCK_EVENT_STRING_LENGTH = 5000
MAX_PUBLIC_BLOCK_EVENT_JSON_BYTES = 64 * 1024
BLOCK_TYPE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,200}$")
MANAGED_TENANT_ASSET_PATTERN = re.compile(r"^/uploads/tenant_(\d+)/")
MIN_PUBLIC_SUBMISSION_ELAPSED_MS = int(
    os.getenv("MIN_PUBLIC_SUBMISSION_ELAPSED_MS", "750")
)
RESERVATION_CANCELLATION_TTL_DAYS = int(
    os.getenv("RESERVATION_CANCELLATION_TTL_DAYS", "30")
)
DEFAULT_RESERVATION_DURATION_MINUTES = 30
FRONTEND_URL = resolve_frontend_url()


class PublicScreenTimeHeartbeat(BaseModel):
    active_seconds: int = Field(..., ge=1, le=60)


class PublicSiteVisitCreate(BaseModel):
    surface: Literal["website", "store"]


class PublicFormSubmissionCreate(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    form_element_id: Optional[str] = None
    honeypot: Optional[str] = Field(default=None, max_length=200)
    submission_elapsed_ms: Optional[int] = Field(default=None, ge=0, le=86_400_000)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=200)
    resume_token: Optional[str] = Field(default=None, max_length=300)


class PublicFormDraftUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, Any] = Field(default_factory=dict)
    form_element_id: Optional[str] = Field(default=None, max_length=200)
    page_index: int = Field(default=0, ge=0, le=1000)
    language: str = Field(default="en", min_length=1, max_length=12)
    resume_token: Optional[str] = Field(default=None, max_length=300)
    draft_name: Optional[str] = Field(default=None, max_length=120)
    honeypot: Optional[str] = Field(default=None, max_length=200)
    submission_elapsed_ms: Optional[int] = Field(default=None, ge=0, le=86_400_000)

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("answers must be a JSON object")
        return value


class PublicQuizAttemptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    honeypot: Optional[str] = Field(default=None, max_length=200)
    submission_elapsed_ms: Optional[int] = Field(default=None, ge=0, le=86_400_000)


class PublicQuizFinalizeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, Any] = Field(default_factory=dict)

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, value):
        if not isinstance(value, dict):
            raise ValueError("answers must be a JSON object")
        return value


class PublicBuilderBlockEventCreate(BaseModel):
    block_type: str = Field(..., max_length=80)
    block_id: Optional[str] = Field(default=None, max_length=200)
    event_type: Optional[str] = Field(default=None, max_length=120)
    title: Optional[str] = Field(default=None, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=200)
    honeypot: Optional[str] = Field(default=None, max_length=200)
    submission_elapsed_ms: Optional[int] = Field(default=None, ge=0, le=86_400_000)

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("payload must be a JSON object")
        return value


class TenantRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=200)


class TenantLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=200)


class PublicReservationCancellationRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=256)


class PublicStoreOrderItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    variant_id: UUID | None = None
    quantity: int = Field(..., ge=1, le=99)


class PublicStoreOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(..., min_length=16, max_length=128)
    customer_name: str = Field(..., min_length=2, max_length=160)
    email: EmailStr
    phone: str = Field(..., min_length=5, max_length=50)
    service_area_id: UUID
    street: str = Field(..., min_length=3, max_length=240)
    building: str = Field(default="", max_length=120)
    floor_apartment: str = Field(default="", max_length=120)
    address_description: str = Field(default="", max_length=500)
    delivery_notes: str = Field(default="", max_length=1000)
    address_line_1: str = Field(default="", max_length=240)
    address_line_2: str = Field(default="", max_length=240)
    city: str = Field(default="", max_length=120)
    postal_code: str = Field(default="", max_length=30)
    country: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=1000)
    payment_method: Literal["cash_on_delivery"] = "cash_on_delivery"
    items: list[PublicStoreOrderItemCreate] = Field(..., min_length=1, max_length=50)

    @field_validator("items")
    @classmethod
    def unique_products(cls, value):
        identities = [(item.product_id, item.variant_id) for item in value]
        if len(identities) != len(set(identities)):
            raise ValueError("Each product variant can appear only once")
        return value


class PublicStoreCartReconcile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[PublicStoreOrderItemCreate] = Field(..., min_length=1, max_length=50)


def rows(response):
    return getattr(response, "data", None) or []


def first_row(response):
    result_rows = rows(response)
    return result_rows[0] if result_rows else None


def unique_public_row(
    response,
    *,
    missing_detail: str,
    ambiguous_code: str,
) -> dict:
    """Resolve exactly one public row; public routing must never pick a first match."""

    result_rows = rows(response)
    if not result_rows:
        raise HTTPException(status_code=404, detail=missing_detail)
    if len(result_rows) != 1:
        raise api_error(
            409,
            ambiguous_code,
            "The published site configuration is inconsistent.",
        )
    return result_rows[0]


def _normalized_public_page_route(page: dict) -> str:
    raw = str(page.get("slug", page.get("path", page.get("route", ""))) or "").strip()
    if not raw:
        return ""
    if raw == "/":
        return "/"
    return "/" + raw.strip("/").lower()


def validate_published_snapshot(
    project: dict,
    *,
    expected_tenant_id: int,
    expected_project_id: str,
    require_pages: bool = True,
) -> dict:
    """Validate the immutable project snapshot before any public resource uses it."""

    if str(project.get("id") or "") != str(expected_project_id):
        raise api_error(409, "publication_project_mismatch", "The published site configuration is inconsistent.")
    if str(project.get("tenant_id") or "") != str(expected_tenant_id):
        raise api_error(409, "publication_tenant_mismatch", "The published site configuration is inconsistent.")
    if str(project.get("status") or "").lower() != "published":
        raise HTTPException(status_code=404, detail="Published site not found")

    schema = project.get("published_schema")
    if not isinstance(schema, dict):
        raise HTTPException(status_code=404, detail="Published site not found")

    def validate_asset_owner(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values():
                validate_asset_owner(child)
        elif isinstance(value, list):
            for child in value:
                validate_asset_owner(child)
        elif isinstance(value, str):
            match = MANAGED_TENANT_ASSET_PATTERN.match(value.strip())
            if match and str(match.group(1)) != str(expected_tenant_id):
                raise api_error(409, "publication_asset_tenant_mismatch", "The published site contains an invalid asset reference.")

    validate_asset_owner(schema)
    pages = schema.get("pages")
    if not require_pages and (pages is None or pages == []):
        return schema
    if not isinstance(pages, list) or not pages or any(not isinstance(page, dict) for page in pages):
        raise api_error(409, "publication_pages_invalid", "The published site configuration is inconsistent.")

    page_ids = [str(page.get("id") or "").strip() for page in pages]
    if any(not page_id for page_id in page_ids) or len(set(page_ids)) != len(page_ids):
        raise api_error(409, "publication_page_ids_ambiguous", "The published site configuration is inconsistent.")

    page_routes = [_normalized_public_page_route(page) for page in pages]
    if any(not route for route in page_routes) or len(set(page_routes)) != len(page_routes):
        raise api_error(409, "publication_page_routes_ambiguous", "The published site configuration is inconsistent.")

    default_page_id = str(schema.get("defaultPageId") or "").strip()
    default_matches = [page for page in pages if str(page.get("id") or "").strip() == default_page_id]
    root_matches = [page for page in pages if _normalized_public_page_route(page) == "/"]
    flagged_matches = [page for page in pages if page.get("isDefault") is True or page.get("is_default") is True]
    if not default_page_id or len(default_matches) != 1 or len(root_matches) != 1:
        raise api_error(409, "publication_homepage_ambiguous", "The published site homepage is inconsistent.")
    homepage_id = str(default_matches[0].get("id") or "")
    if str(root_matches[0].get("id") or "") != homepage_id:
        raise api_error(409, "publication_homepage_mismatch", "The published site homepage is inconsistent.")
    if flagged_matches and (
        len(flagged_matches) != 1 or str(flagged_matches[0].get("id") or "") != homepage_id
    ):
        raise api_error(409, "publication_homepage_mismatch", "The published site homepage is inconsistent.")

    forms = schema.get("forms", [])
    if forms is not None:
        if not isinstance(forms, list) or any(not isinstance(form, dict) for form in forms):
            raise api_error(409, "publication_forms_invalid", "The published site forms are inconsistent.")
        form_ids = [str(form.get("id") or "").strip() for form in forms]
        if any(not form_id for form_id in form_ids) or len(set(form_ids)) != len(form_ids):
            raise api_error(409, "publication_form_ids_ambiguous", "The published site forms are inconsistent.")

    return schema


def _public_token_secret() -> bytes:
    value = (
        os.getenv("RESERVATION_TOKEN_SECRET")
        or os.getenv("CSRF_SECRET")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SECRET_KEY")
        or "madar-development-public-token-secret"
    )
    return value.encode("utf-8")


def hash_public_identifier(value: str) -> str:
    return hmac.new(
        _public_token_secret(),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def reject_suspicious_public_submission(
    *,
    honeypot: str | None,
    submission_elapsed_ms: int | None,
    route_name: str,
) -> None:
    suspicious = bool((honeypot or "").strip()) or (
        submission_elapsed_ms is not None
        and submission_elapsed_ms < MIN_PUBLIC_SUBMISSION_ELAPSED_MS
    )
    if not suspicious:
        return
    logger.info(
        "public.submission_spam_rejected",
        extra={"route_name": route_name},
    )
    raise api_error(
        400,
        "submission_rejected",
        "The submission could not be accepted.",
    )


def normalize_idempotency_key(event: Any, request: Request) -> str | None:
    body_key = (event.idempotency_key or "").strip()
    header_key = (request.headers.get("idempotency-key") or "").strip()
    if body_key and header_key and not hmac.compare_digest(body_key, header_key):
        raise api_error(
            409,
            "idempotency_conflict",
            "The idempotency key does not match this request.",
        )
    key = header_key or body_key
    if not key:
        return None
    if not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
        raise api_error(
            400,
            "idempotency_key_invalid",
            "The idempotency key is invalid.",
        )
    return key


def canonical_request_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _form_submission_storage_error(error: Exception) -> HTTPException:
    text = str(error).lower()
    if "idempotency_conflict" in text:
        return api_error(
            409,
            "idempotency_conflict",
            "This idempotency key was already used for a different request.",
        )
    if "idempotency_key_invalid" in text or "form_submission_payload_invalid" in text:
        return api_error(400, "idempotency_key_invalid", "The idempotency key is invalid.")
    return api_error(
        503,
        "dependency_unavailable",
        "The form submission could not be saved. Try again shortly.",
    )


def insert_builder_form_submission(
    payload: dict[str, Any],
    *,
    idempotency_key_hash: str | None,
    request_hash: str,
    notification: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    try:
        rpc = getattr(service_supabase, "rpc", None)
        if callable(rpc):
            response = rpc(
                "create_builder_form_submission_notified_safe",
                {
                    "p_submission": payload,
                    "p_idempotency_key_hash": idempotency_key_hash,
                    "p_request_hash": request_hash,
                    "p_notification": notification,
                },
            ).execute()
            data = getattr(response, "data", None)
            result = data[0] if isinstance(data, list) and data else data
            if not isinstance(result, dict) or not isinstance(result.get("submission"), dict):
                raise RuntimeError("form_submission_rpc_empty_result")
            return result["submission"], bool(result.get("duplicate"))

        # Test-only in-memory clients do not implement RPC. Production always
        # uses the transaction-scoped database function above.
        if idempotency_key_hash:
            existing_response = (
                service_supabase.table("builder_form_submissions")
                .select("*")
                .eq("tenant_id", payload["tenant_id"])
                .eq("project_id", payload["project_id"])
                .eq("form_id", payload["form_id"])
                .eq("idempotency_key_hash", idempotency_key_hash)
                .limit(1)
                .execute()
            )
            existing = first_row(existing_response)
            if existing:
                if existing.get("request_hash") != request_hash:
                    raise RuntimeError("idempotency_conflict")
                return existing, True
        response = service_supabase.table("builder_form_submissions").insert({
            **payload,
            "idempotency_key_hash": idempotency_key_hash,
            "request_hash": request_hash,
        }).execute()
        saved = first_row(response)
        if not saved:
            raise RuntimeError("form_submission_empty_result")
        return saved, False
    except HTTPException:
        raise
    except Exception as error:
        logger.warning(
            "public.form_submission_failed",
            extra={
                "tenant_id": payload.get("tenant_id"),
                "project_id": payload.get("project_id"),
                "form_id": payload.get("form_id"),
                "error_type": type(error).__name__,
            },
        )
        raise _form_submission_storage_error(error)


def build_cancellation_token(
    *,
    tenant_id: int,
    project_id: str,
    block_id: str,
    idempotency_key_hash: str | None,
    request_hash: str,
) -> str:
    if idempotency_key_hash:
        material = ":".join(
            (
                "reservation-cancellation",
                str(tenant_id),
                project_id,
                block_id,
                idempotency_key_hash,
                request_hash,
            )
        )
        digest = hmac.new(
            _public_token_secret(),
            material.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return secrets.token_urlsafe(32)


def get_bound_published_project(settings: dict, *, require_pages: bool = True):
    tenant_id = resolve_tenant_id(settings)
    project_id = str(settings.get("published_project_id") or "").strip()
    if not project_id:
        raise HTTPException(status_code=404, detail="Published site not found")

    project_response = (
        service_supabase.table("builder_projects")
        .select(
            "id, tenant_id, name, slug, status, published_schema, "
            "published_version, published_revision, schema_version, "
            "last_published_at, updated_at"
        )
        .eq("id", project_id)
        .eq("tenant_id", tenant_id)
        .eq("status", "published")
        .not_.is_("published_schema", "null")
        .limit(2)
        .execute()
    )
    project = unique_public_row(
        project_response,
        missing_detail="Published site not found",
        ambiguous_code="publication_project_ambiguous",
    )
    validate_published_snapshot(
        project,
        expected_tenant_id=tenant_id,
        expected_project_id=project_id,
        require_pages=require_pages,
    )
    return project


PROTECTED_PAGE_VISIBILITIES = {"private", "authenticated", "members"}
PUBLIC_RUNTIME_PRIVATE_KEYS = {
    "activeFormId",
    "activePageId",
    "activeRoleId",
    "activeWorkflowId",
    "collections",
    "reservations",
    "roles",
    "users",
    "workflows",
}


def collect_auth_destination_page_ids(value: Any) -> set[str]:
    destinations: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            if str(item.get("type") or "") == "loginBlock":
                destination = (item.get("auth") or {}).get("successPageId")
                if destination:
                    destinations.add(str(destination))
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return destinations


def page_access_kind(page: dict, auth_destination_ids: set[str]) -> str:
    page_id = str(page.get("id") or "")
    visibility = str(page.get("visibility") or "public").strip().lower()
    if page_id in auth_destination_ids or visibility in PROTECTED_PAGE_VISIBILITIES:
        return "member"
    if visibility in {"", "public"}:
        return "public"
    return "unsupported_role"


def collect_referenced_form_ids(pages: list[dict]) -> set[str]:
    form_ids: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key in ("connectedFormId", "formId"):
                value = item.get(key)
                if value:
                    form_ids.add(str(value))
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(pages)
    return form_ids


def build_authorized_public_schema(
    schema: dict,
    *,
    authorized_page_ids: set[str] | None = None,
) -> dict:
    # Redact the entire publication before selecting visible resources.  Forms
    # are the expected location for grading material, but treating arbitrary
    # publication JSON as public prevents a future/custom component from
    # accidentally carrying an answer key in a page or settings object.
    source = redact_public_value(schema if isinstance(schema, dict) else {})
    pages = [page for page in source.get("pages", []) if isinstance(page, dict)]
    auth_destination_ids = collect_auth_destination_page_ids(pages)
    allowed_ids = authorized_page_ids or set()
    visible_pages = [
        page
        for page in pages
        if (
            page_access_kind(page, auth_destination_ids) == "public"
            and not resource_is_role_restricted(
                project={"published_schema": source},
                resource_type="page",
                resource_id=str(page.get("id") or ""),
            )
        )
        or str(page.get("id") or "") in allowed_ids
    ]
    source["pages"] = visible_pages

    visible_page_ids = {str(page.get("id") or "") for page in visible_pages}
    default_page_id = str(source.get("defaultPageId") or "")
    if default_page_id and default_page_id not in visible_page_ids:
        # Never reinterpret another page as the homepage. Protected-page
        # authorization may omit the homepage, but the publication identity is
        # retained so the client fails closed rather than selecting pages[0].
        source["defaultPageId"] = default_page_id

    referenced_form_ids = collect_referenced_form_ids(visible_pages)
    source["forms"] = [
        form
        for form in source.get("forms", [])
        if isinstance(form, dict) and str(form.get("id") or "") in referenced_form_ids
    ]
    source["forms"] = [serialize_public_form(form) for form in source["forms"]]

    for key in PUBLIC_RUNTIME_PRIVATE_KEYS:
        source.pop(key, None)
    return source


def find_published_page(project: dict, page_reference: str) -> tuple[dict, dict, set[str]]:
    schema = validate_published_snapshot(
        project,
        expected_tenant_id=project.get("tenant_id"),
        expected_project_id=str(project.get("id") or ""),
    )
    pages = [page for page in schema.get("pages", []) if isinstance(page, dict)]
    normalized_reference = str(page_reference or "").strip().strip("/").lower()
    matches = [
        item
        for item in pages
        if str(item.get("id") or "").lower() == normalized_reference
        or str(item.get("slug") or "").strip().strip("/").lower() == normalized_reference
    ]
    if not matches:
        raise HTTPException(status_code=404, detail="Page not found")
    if len(matches) != 1:
        raise api_error(409, "publication_page_reference_ambiguous", "The published page reference is ambiguous.")
    return schema, matches[0], collect_auth_destination_page_ids(pages)


def build_publication_metadata(project: dict, schema: dict, *, settings: dict, site_identifier: str) -> dict:
    canonical_schema = json.dumps(
        schema,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    schema_hash = hashlib.sha256(canonical_schema.encode("utf-8")).hexdigest()
    project_id = str(project.get("id") or "")
    published_version = int(project.get("published_version") or 0)
    site_id = str(settings.get("id") or "")
    publication_key = f"{site_id}:{site_identifier}:{project_id}:{published_version}:{schema_hash}"
    etag = f'"madar-{hashlib.sha256(publication_key.encode("utf-8")).hexdigest()}"'
    return {
        "site_id": site_id,
        "site_identifier": site_identifier,
        "project_id": project_id,
        "published_version": published_version,
        "published_at": project.get("last_published_at"),
        "schema_version": int(
            project.get("schema_version") or schema.get("schema_version") or 1
        ),
        "schema_hash": schema_hash,
        "publication_key": publication_key,
        "etag": etag,
    }


def apply_public_cache_headers(response: Response, metadata: dict, *, private: bool = False) -> None:
    response.headers["ETag"] = metadata["etag"]
    response.headers["Cache-Control"] = (
        "private, no-store" if private else "public, max-age=0, must-revalidate"
    )
    response.headers["Vary"] = "Host, X-Forwarded-Host, Origin"
    response.headers["CDN-Cache-Control"] = "no-store"


def request_etag_matches(request: Request, metadata: dict) -> bool:
    candidates = {
        value.strip()
        for value in str(request.headers.get("if-none-match") or "").split(",")
        if value.strip()
    }
    return metadata["etag"] in candidates or "*" in candidates


def get_form_sections(form: dict) -> list[dict]:
    sections = form.get("sections")
    return sections if isinstance(sections, list) else []


def get_form_fields(form: dict) -> list[dict]:
    fields = []

    for section in get_form_sections(form):
        section_fields = section.get("fields")
        if isinstance(section_fields, list):
            fields.extend(field for field in section_fields if isinstance(field, dict))

    return fields


def find_form_in_schema(schema: dict, form_id: str) -> dict:
    forms = schema.get("forms")

    if not isinstance(forms, list):
        raise HTTPException(status_code=404, detail="Form not found")

    matches = [
        form
        for form in forms
        if isinstance(form, dict) and str(form.get("id") or "") == form_id
    ]
    if not matches:
        raise HTTPException(status_code=404, detail="Form not found")
    if len(matches) != 1:
        raise api_error(409, "publication_form_ambiguous", "The published form is ambiguous.")
    return matches[0]


def get_published_form_for_site(settings: dict, form_id: str):
    """Resolve a published form without requiring its project to be the live website.

    Standalone form links belong to the tenant site, not necessarily to the project
    currently bound as the site's homepage. Require one unambiguous matching
    published snapshot across the bounded tenant lookup. Draft schemas are
    deliberately never considered here.
    """

    tenant_id = resolve_tenant_id(settings)
    bound_project_id = str(settings.get("published_project_id") or "").strip()

    bound_project_error = None
    bound_match = None
    if bound_project_id:
        try:
            project = get_bound_published_project(settings, require_pages=False)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            bound_project_error = exc
        else:
            published_schema = project.get("published_schema")
            if isinstance(published_schema, dict):
                try:
                    form = find_form_in_schema(published_schema, form_id)
                except HTTPException as exc:
                    if exc.status_code != 404:
                        raise
                else:
                    bound_match = (project, form, published_schema)

    projects_response = (
        service_supabase.table("builder_projects")
        .select(
            "id, tenant_id, name, slug, status, published_schema, "
            "published_version, published_revision, schema_version, "
            "last_published_at, updated_at"
        )
        .eq("tenant_id", tenant_id)
        .eq("status", "published")
        .not_.is_("published_schema", "null")
        .limit(101)
        .execute()
    )

    candidates = projects_response.data or []
    # A truncated search cannot establish globally unique form identity.
    if len(candidates) >= 101:
        raise api_error(409, "publication_form_ambiguous", "The published form lookup is incomplete.")
    matches = [bound_match[0]] if bound_match else []
    for candidate in candidates:
        if str(candidate.get("id") or "") == bound_project_id:
            continue
        schema = candidate.get("published_schema")
        forms = schema.get("forms") if isinstance(schema, dict) else None
        if not isinstance(forms, list):
            continue
        if any(
            isinstance(form, dict) and str(form.get("id") or "") == form_id
            for form in forms
        ):
            matches.append(candidate)

    if not matches:
        if bound_project_error is not None:
            raise bound_project_error
        raise HTTPException(status_code=404, detail="Form not found")
    if len(matches) != 1:
        raise api_error(409, "publication_form_ambiguous", "The published form is ambiguous.")

    project = matches[0]
    project_id = str(project.get("id") or "")
    published_schema = validate_published_snapshot(
        project,
        expected_tenant_id=tenant_id,
        expected_project_id=project_id,
        require_pages=False,
    )
    form = find_form_in_schema(published_schema, form_id)
    return project, form, published_schema

DEFAULT_PUBLIC_STORE_THEME = {
    "accent": "#852c21",
    "background": "#ffffff",
    "surface": "#f5f1eb",
    "text": "#162033",
    "muted": "#667085",
}
LEGACY_DEFAULT_PUBLIC_STORE_THEME = {
    "accent": "#2463eb",
    "background": "#ffffff",
    "surface": "#f7f8fa",
    "text": "#151821",
    "muted": "#697181",
}

def _public_store_growth(saved_theme: dict[str, Any]) -> dict[str, Any]:
    value = saved_theme.get("growth") if isinstance(saved_theme, dict) else None
    value = value if isinstance(value, dict) else {}
    text_fields = (
        "seo_title_en", "seo_title_ar", "seo_description_en", "seo_description_ar",
        "announcement_text_en", "announcement_text_ar", "announcement_link",
    )
    result = {key: str(value.get(key) or "").strip() for key in text_fields}
    result["announcement_enabled"] = bool(value.get("announcement_enabled"))
    for key, limit in (("featured_product_ids", 12), ("featured_category_ids", 6)):
        selected = value.get(key) if isinstance(value.get(key), list) else []
        result[key] = list(dict.fromkeys(str(item) for item in selected if item))[:limit]
    return result


def build_public_store_profile(settings: dict, subdomain: str) -> dict:
    """Build storefront identity without reading any page-builder project."""
    saved_theme = settings.get("ecommerce_theme") if isinstance(settings.get("ecommerce_theme"), dict) else {}
    if saved_theme == LEGACY_DEFAULT_PUBLIC_STORE_THEME:
        saved_theme = {}
    return {
        "subdomain": subdomain,
        "brand": settings.get("footer_store_name") or settings.get("brand"),
        "footer_store_name": settings.get("footer_store_name"),
        "logo_url": settings.get("logo_url"),
        "loading_image_url": settings.get("loading_image_url"),
        "contact_email": settings.get("contact_email"),
        "phone": settings.get("phone"),
        "description": settings.get("description"),
        "store_theme": {**DEFAULT_PUBLIC_STORE_THEME, **{key: value for key, value in saved_theme.items() if key != "growth"}},
        "growth": _public_store_growth(saved_theme),
    }

def build_public_site_profile(settings: dict, subdomain: str, project: dict) -> dict:
    schema = project.get("published_schema") if isinstance(project, dict) else None
    has_published_snapshot = isinstance(schema, dict)
    chrome = schema.get("siteChrome") if has_published_snapshot else {}
    chrome = chrome if isinstance(chrome, dict) else {}
    builder_theme = schema.get("theme") if has_published_snapshot else {}
    builder_theme = builder_theme if isinstance(builder_theme, dict) else {}
    fallback = settings if not has_published_snapshot else {}
    fallback_name = fallback.get("footer_store_name") or fallback.get("brand")
    inherited_store_theme = {
        "accent": builder_theme.get("primary") or builder_theme.get("accent"),
        "background": builder_theme.get("background"),
        "surface": builder_theme.get("softSurface") or builder_theme.get("surface"),
        "text": builder_theme.get("text"),
        "muted": builder_theme.get("muted"),
    }
    inherited_store_theme = {
        key: value for key, value in inherited_store_theme.items() if value
    }
    saved_store_theme = settings.get("ecommerce_theme")
    saved_store_theme = saved_store_theme if isinstance(saved_store_theme, dict) else {}
    return {
        "subdomain": subdomain,
        "brand": chrome.get("brand") or chrome.get("brandName") or fallback_name,
        "footer_store_name": chrome.get("footerStoreName") or fallback.get("footer_store_name"),
        "logo_url": chrome.get("logoUrl") or fallback.get("logo_url"),
        "loading_image_url": chrome.get("loadingImageUrl") or chrome.get("loading_image_url") or fallback.get("loading_image_url"),
        "contact_email": chrome.get("contactEmail") or fallback.get("contact_email"),
        "phone": chrome.get("phone") or fallback.get("phone"),
        "description": chrome.get("description") or fallback.get("description"),
        "store_theme": {
            **DEFAULT_PUBLIC_STORE_THEME,
            **inherited_store_theme,
            **saved_store_theme,
        },
    }

def build_public_form(form: dict) -> dict:
    return serialize_public_form(form)


def iter_section_elements(section: dict):
    for row in section.get("rows") or []:
        if not isinstance(row, dict):
            continue
        for column in row.get("columns") or []:
            if not isinstance(column, dict):
                continue
            for element in column.get("elements") or []:
                if isinstance(element, dict):
                    yield element

    for element in section.get("freeElements") or []:
        if isinstance(element, dict):
            yield element


def published_page_contains_form_block(published_schema: dict, form_id: str) -> bool:
    pages = published_schema.get("pages")

    if not isinstance(pages, list):
        return False

    for page in pages:
        if not isinstance(page, dict):
            continue
        for section in page.get("sections") or []:
            if not isinstance(section, dict):
                continue
            for element in iter_section_elements(section):
                if element.get("type") == "formBlock" and element.get("connectedFormId") == form_id:
                    return True

    return False


def find_published_block(
    published_schema: dict,
    block_id: Optional[str],
    block_type: str,
) -> Optional[dict]:
    pages = published_schema.get("pages")

    if not isinstance(pages, list):
        return None

    matches: list[dict] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        for section in page.get("sections") or []:
            if not isinstance(section, dict):
                continue
            for element in iter_section_elements(section):
                if element.get("type") != block_type:
                    continue
                if block_id and str(element.get("id") or "") != block_id:
                    continue
                matches.append(element)

    if not matches:
        return None
    if len(matches) != 1:
        raise api_error(409, "publication_block_ambiguous", "The published block is ambiguous.")
    return matches[0]


def normalize_public_block_type(value: str) -> str:
    block_type = (value or "").strip()

    if not block_type or not BLOCK_TYPE_PATTERN.match(block_type):
        raise HTTPException(status_code=400, detail="Invalid block type")

    return block_type


def normalize_public_event_type(value: Optional[str], block_type: str) -> str:
    event_type = (value or "").strip()

    if not event_type:
        return "builder.reservation_requested" if block_type == "reservationBlock" else f"builder.{block_type}.event"

    if not re.match(r"^[A-Za-z0-9_.:-]{1,120}$", event_type):
        raise HTTPException(status_code=400, detail="Invalid event type")

    return event_type


def normalize_answer_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [item for item in value if item is None or isinstance(item, (str, int, float, bool))]
    return value


def normalize_event_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [normalize_event_value(item) for item in value[:MAX_PUBLIC_BLOCK_EVENT_FIELDS]]
    if isinstance(value, dict):
        return {
            str(key)[:120]: normalize_event_value(item)
            for key, item in list(value.items())[:MAX_PUBLIC_BLOCK_EVENT_FIELDS]
        }
    return str(value)


def iter_answer_strings(value):
    if isinstance(value, str):
        yield value
        return

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                yield item


def iter_payload_strings(value):
    if isinstance(value, str):
        yield value
        return

    if isinstance(value, list):
        for item in value:
            yield from iter_payload_strings(item)
        return

    if isinstance(value, dict):
        for item in value.values():
            yield from iter_payload_strings(item)


def validate_public_answer_payload_limits(answers: dict[str, Any]):
    if len(answers) > MAX_PUBLIC_FORM_ANSWER_FIELDS:
        raise HTTPException(
            status_code=413,
            detail={
                "message": "Submission contains too many answer fields",
                "max_fields": MAX_PUBLIC_FORM_ANSWER_FIELDS,
            },
        )

    for field_id, value in answers.items():
        for answer_text in iter_answer_strings(value):
            if len(answer_text) > MAX_PUBLIC_FORM_ANSWER_STRING_LENGTH:
                raise HTTPException(
                    status_code=413,
                    detail={
                        "message": "Submission answer is too large",
                        "field_id": str(field_id),
                        "max_length": MAX_PUBLIC_FORM_ANSWER_STRING_LENGTH,
                    },
                )

    try:
        serialized = json.dumps(answers, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="answers must be JSON serializable")

    if len(serialized.encode("utf-8")) > MAX_PUBLIC_FORM_ANSWERS_JSON_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "message": "Submission answers payload is too large",
                "max_bytes": MAX_PUBLIC_FORM_ANSWERS_JSON_BYTES,
            },
        )


def validate_public_event_payload_limits(payload: dict[str, Any]):
    if len(payload) > MAX_PUBLIC_BLOCK_EVENT_FIELDS:
        raise HTTPException(
            status_code=413,
            detail={
                "message": "Event contains too many payload fields",
                "max_fields": MAX_PUBLIC_BLOCK_EVENT_FIELDS,
            },
        )

    for field_id, value in payload.items():
        for payload_text in iter_payload_strings(value):
            if len(payload_text) > MAX_PUBLIC_BLOCK_EVENT_STRING_LENGTH:
                raise HTTPException(
                    status_code=413,
                    detail={
                        "message": "Event payload field is too large",
                        "field_id": str(field_id),
                        "max_length": MAX_PUBLIC_BLOCK_EVENT_STRING_LENGTH,
                    },
                )

    try:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="payload must be JSON serializable")

    if len(serialized.encode("utf-8")) > MAX_PUBLIC_BLOCK_EVENT_JSON_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "message": "Event payload is too large",
                "max_bytes": MAX_PUBLIC_BLOCK_EVENT_JSON_BYTES,
            },
        )


def compact_public_text(value: Any, max_length: int = 500) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None

    text = str(value).strip()
    return text[:max_length] if text else None


def first_payload_text(payload: dict[str, Any], *keys: str, max_length: int = 500) -> str | None:
    for key in keys:
        value = compact_public_text(payload.get(key), max_length=max_length)
        if value:
            return value
    return None


def parse_public_datetime(value: Any) -> str | None:
    text = compact_public_text(value, max_length=120)
    if not text:
        return None

    candidate = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate).isoformat()
    except ValueError:
        return None


def reservation_datetime_from_payload(payload: dict[str, Any], *keys: str) -> str | None:
    direct_value = first_payload_text(payload, *keys, max_length=120)
    parsed = parse_public_datetime(direct_value)
    if parsed:
        return parsed

    date_value = first_payload_text(payload, "date", "reservation_date", "reservationDate", max_length=40)
    time_value = first_payload_text(payload, "time", "start_time", "startTime", max_length=40)

    if date_value and time_value:
        return parse_public_datetime(f"{date_value}T{time_value}")

    return None


def normalize_reservation_timing(payload: dict[str, Any]) -> dict[str, str | None]:
    timezone_name = first_payload_text(
        payload,
        "timezone",
        "time_zone",
        "timeZone",
        max_length=120,
    )
    timezone_value = None
    if timezone_name:
        try:
            timezone_value = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            raise api_error(
                400,
                "reservation_timezone_invalid",
                "Choose a valid timezone.",
            )

    starts_at = reservation_datetime_from_payload(
        payload,
        "starts_at",
        "startsAt",
        "start",
        "start_at",
        "startAt",
    )
    ends_at = parse_public_datetime(
        first_payload_text(
            payload,
            "ends_at",
            "endsAt",
            "end",
            "end_at",
            "endAt",
            max_length=120,
        )
    )
    start_was_supplied = any(
        compact_public_text(payload.get(key), max_length=120)
        for key in (
            "starts_at",
            "startsAt",
            "start",
            "start_at",
            "startAt",
            "date",
            "reservation_date",
            "reservationDate",
            "time",
            "start_time",
            "startTime",
        )
    )
    end_was_supplied = any(
        compact_public_text(payload.get(key), max_length=120)
        for key in ("ends_at", "endsAt", "end", "end_at", "endAt")
    )
    if start_was_supplied and not starts_at:
        raise api_error(
            400,
            "reservation_time_invalid",
            "Choose a valid reservation start time.",
        )
    if end_was_supplied and not ends_at:
        raise api_error(
            400,
            "reservation_time_invalid",
            "Choose a valid reservation end time.",
        )

    normalized: dict[str, str | None] = {
        "starts_at": None,
        "ends_at": None,
        "timezone": timezone_name,
    }
    parsed_values: list[datetime | None] = []
    for value in (starts_at, ends_at):
        if not value:
            parsed_values.append(None)
            continue
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            if timezone_value is None:
                raise api_error(
                    400,
                    "reservation_timezone_required",
                    "Choose a timezone for the reservation.",
                )
            parsed = parsed.replace(tzinfo=timezone_value)
        parsed_values.append(parsed)

    parsed_start, parsed_end = parsed_values
    if parsed_start and parsed_end is None:
        parsed_end = parsed_start + timedelta(minutes=DEFAULT_RESERVATION_DURATION_MINUTES)
    if parsed_start and parsed_end and parsed_start >= parsed_end:
        raise api_error(
            400,
            "reservation_time_invalid",
            "The reservation end time must be after its start time.",
        )
    normalized["starts_at"] = parsed_start.isoformat() if parsed_start else None
    normalized["ends_at"] = parsed_end.isoformat() if parsed_end else None
    return normalized


def reservation_block_is_exclusive(block: dict[str, Any]) -> bool:
    reservation = block.get("reservation")
    if not isinstance(reservation, dict):
        return False
    return str(reservation.get("bookingMode") or "restricted").strip().lower() != "flexible"


def validate_configured_reservation_slot(block: dict[str, Any], payload: dict[str, Any]) -> None:
    reservation = block.get("reservation")
    if not isinstance(reservation, dict):
        return
    if str(reservation.get("bookingMode") or "restricted").strip().lower() == "flexible":
        return

    slots_by_date = reservation.get("timeSlotsByDate")
    if not isinstance(slots_by_date, dict):
        return

    requested_date = str(payload.get("date") or "").strip()
    requested_time = str(payload.get("time") or "").strip()
    configured_times = slots_by_date.get(requested_date)
    valid_times = {
        str(value).strip()
        for value in configured_times
        if str(value).strip()
    } if isinstance(configured_times, list) else set()

    if not requested_date or not requested_time or requested_time not in valid_times:
        raise api_error(
            400,
            "reservation_slot_invalid",
            "Choose an available date and time.",
        )

RESERVATION_EMAIL_PATTERN = re.compile(
    r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$",
    re.IGNORECASE,
)
ISRAEL_RESERVATION_PHONE_PATTERN = re.compile(
    r"^(?:\+972(?:5\d{8}|7\d{8}|[23489]\d{7})|0(?:5\d{8}|7\d{8}|[23489]\d{7}))$"
)
PALESTINE_RESERVATION_PHONE_PATTERN = re.compile(
    r"^(?:\+970(?:5[69]\d{7}|[28]\d{7})|0(?:5[69]\d{7}|[28]\d{7}))$"
)


def is_valid_reservation_email(value: str) -> bool:
    email = value.strip()
    local = email.partition("@")[0]
    return (
        0 < len(email) <= 254
        and 0 < len(local) <= 64
        and not local.startswith(".")
        and not local.endswith(".")
        and ".." not in local
        and RESERVATION_EMAIL_PATTERN.fullmatch(email) is not None
    )


def normalize_reservation_phone(value: str) -> str:
    phone = re.sub(r"[\s().-]", "", value.strip())
    return f"+{phone[2:]}" if phone.startswith("00") else phone


def is_valid_reservation_phone(value: str) -> bool:
    phone = normalize_reservation_phone(value)
    return (
        ISRAEL_RESERVATION_PHONE_PATTERN.fullmatch(phone) is not None
        or PALESTINE_RESERVATION_PHONE_PATTERN.fullmatch(phone) is not None
    )

def validate_reservation_custom_answers(block: dict[str, Any], payload: dict[str, Any]) -> None:
    reservation = block.get("reservation")
    form_items = reservation.get("formItems") if isinstance(reservation, dict) else None
    answer_items = {
        str(item.get("id")): item
        for item in (form_items or [])
        if isinstance(item, dict) and item.get("type") in {"text", "email", "phone", "checkbox", "radio"} and item.get("id")
    }
    raw_answers = payload.get("customAnswers")

    if not answer_items:
        if raw_answers not in (None, {}):
            raise api_error(400, "reservation_answers_invalid", "This reservation does not accept custom answers.")
        payload.pop("customAnswers", None)
        return

    if raw_answers is None:
        raw_answers = {}
    if not isinstance(raw_answers, dict):
        raise api_error(400, "reservation_answers_invalid", "Custom reservation answers must be an object.")
    if any(str(item_id) not in answer_items for item_id in raw_answers):
        raise api_error(400, "reservation_answers_invalid", "A custom reservation answer does not match the published form.")

    cleaned_answers: dict[str, Any] = {}
    for item_id, item in answer_items.items():
        item_type = item.get("type")
        answer = raw_answers.get(item_id)
        options = item.get("options") if isinstance(item.get("options"), list) else []

        if item_type == "checkbox":
            if answer is None:
                answer = []
            if not isinstance(answer, list) or any(not isinstance(value, str) or value not in options for value in answer):
                raise api_error(400, "reservation_answers_invalid", "A checkbox answer contains an invalid choice.")
            answer = list(dict.fromkeys(answer))
            is_empty = len(answer) == 0
        else:
            if answer is None:
                answer = ""
            if not isinstance(answer, str):
                raise api_error(400, "reservation_answers_invalid", "A custom reservation answer has an invalid value.")
            answer = answer.strip()
            if item_type == "email" and answer and not is_valid_reservation_email(answer):
                raise api_error(400, "reservation_email_invalid", "Enter a valid email address.")
            if item_type == "phone" and answer:
                if not is_valid_reservation_phone(answer):
                    raise api_error(400, "reservation_phone_invalid", "Enter a valid Palestinian (+970) or Israeli (+972) phone number.")
                answer = normalize_reservation_phone(answer)
            if item_type == "radio" and answer and answer not in options:
                raise api_error(400, "reservation_answers_invalid", "A radio answer contains an invalid choice.")
            is_empty = not answer

        if item.get("required") is True and is_empty:
            raise api_error(400, "reservation_answer_required", f"{str(item.get('label') or 'A reservation question')[:120]} is required.")
        if not is_empty:
            cleaned_answers[item_id] = answer

    payload["customAnswers"] = cleaned_answers

def build_reservation_field_snapshot(block: dict, block_id: str | None, block_type: str) -> list[dict[str, Any]]:
    snapshot = {
        "block_id": block_id or block.get("id"),
        "block_type": block_type,
    }

    reservation = block.get("reservation")
    if isinstance(reservation, dict):
        snapshot["reservation"] = reservation

    return [snapshot]


def build_builder_reservation_payload(
    *,
    tenant_id: int,
    project: dict,
    subdomain: str,
    block: dict,
    block_id: str | None,
    block_type: str,
    title: str,
    payload: dict[str, Any],
    request: Request,
    timing: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    clean_timing = timing or normalize_reservation_timing(payload)
    return {
        "tenant_id": tenant_id,
        "project_id": project.get("id"),
        "site_subdomain": subdomain,
        "block_id": block_id or compact_public_text(block.get("id"), max_length=200),
        "block_type": block_type,
        "reservation_title": title,
        "customer_name": first_payload_text(payload, "customer_name", "customerName", "name", "full_name", "fullName"),
        "customer_email": first_payload_text(payload, "customer_email", "customerEmail", "email"),
        "customer_phone": first_payload_text(payload, "customer_phone", "customerPhone", "phone", "contact"),
        "starts_at": clean_timing.get("starts_at"),
        "ends_at": clean_timing.get("ends_at"),
        "timezone": clean_timing.get("timezone"),
        "status": "new",
        "payload": payload,
        "field_snapshot": build_reservation_field_snapshot(block, block_id, block_type),
        "submitter_ip": get_client_ip(request),
        "user_agent": request.headers.get("user-agent", "")[:1000],
    }


def _reservation_storage_error(error: Exception) -> HTTPException:
    text = str(error).lower()
    if "idempotency_conflict" in text:
        return api_error(
            409,
            "idempotency_conflict",
            "This idempotency key was already used for a different request.",
        )
    if "reservation_slot_unavailable" in text:
        return api_error(
            409,
            "reservation_slot_unavailable",
            "That reservation slot is no longer available.",
        )
    if "reservation_time" in text or "reservation_payload_invalid" in text:
        return api_error(
            400,
            "reservation_time_invalid",
            "The reservation time is invalid.",
        )
    return api_error(
        503,
        "dependency_unavailable",
        "The reservation could not be saved. Try again shortly.",
    )


def insert_builder_reservation(
    payload: dict[str, Any],
    *,
    idempotency_key_hash: str | None,
    request_hash: str,
    exclusive_slot: bool,
    notification: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    try:
        rpc = getattr(service_supabase, "rpc", None)
        if callable(rpc):
            insert_response = rpc(
                "create_builder_reservation_notified_safe",
                {
                    "p_reservation": payload,
                    "p_idempotency_key_hash": idempotency_key_hash,
                    "p_request_hash": request_hash,
                    "p_exclusive_slot": exclusive_slot,
                    "p_notification": notification,
                },
            ).execute()
            data = getattr(insert_response, "data", None)
            if isinstance(data, list):
                result = data[0] if data else None
            else:
                result = data
            if not isinstance(result, dict) or not isinstance(result.get("reservation"), dict):
                raise RuntimeError("reservation_rpc_empty_result")
            return result["reservation"], bool(result.get("duplicate"))

        # Lightweight in-memory clients used by unit tests do not implement RPC.
        # Production uses the Supabase RPC above so the overlap check is atomic.
        direct_payload = {
            **payload,
            "idempotency_key_hash": idempotency_key_hash,
            "request_hash": request_hash,
            "exclusive_slot": exclusive_slot,
        }
        insert_response = (
            service_supabase.table("builder_reservations")
            .insert(direct_payload)
            .execute()
        )
    except Exception as error:
        logger.warning(
            "public.builder_reservation_failed",
            extra={
                "tenant_id": payload.get("tenant_id"),
                "project_id": payload.get("project_id"),
                "block_id": payload.get("block_id"),
                "error_type": type(error).__name__,
            },
        )
        raise _reservation_storage_error(error)

    saved_reservation = first_row(insert_response)

    if not saved_reservation:
        raise api_error(
            503,
            "dependency_unavailable",
            "The reservation could not be saved. Try again shortly.",
        )

    return saved_reservation, False


def _form_answer_rejection_reason(field: dict[str, Any], value: Any) -> str | None:
    field_type = str(field.get("type") or "shortText").strip()
    if value is None:
        return None

    if field_type in {"shortText", "paragraph"}:
        return None if isinstance(value, str) else "text"

    if field_type == "email":
        text = str(value).strip() if isinstance(value, str) else ""
        return None if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", text) else "email"

    if field_type in {"url", "website"}:
        text = str(value).strip() if isinstance(value, str) else ""
        parsed = urlparse(text)
        return None if parsed.scheme in {"http", "https"} and bool(parsed.netloc) else "website"

    if field_type == "phone":
        text = str(value).strip() if isinstance(value, str) else ""
        digits = re.sub(r"\D", "", text)
        valid = bool(re.fullmatch(r"[+()\d\s.\-]+", text)) and 7 <= len(digits) <= 15
        return None if valid else "phone"

    if field_type in {"number", "money"}:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            return "amount" if field_type == "money" else "number"
        try:
            number = float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return "amount" if field_type == "money" else "number"
        return None if number not in {float("inf"), float("-inf")} and number == number else (
            "amount" if field_type == "money" else "number"
        )

    if field_type == "date":
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return None
        except (TypeError, ValueError):
            return "date"

    if field_type == "time":
        return None if isinstance(value, str) and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value) else "time"

    if field_type in {"dropdown", "status", "yesNo", "radio"}:
        return None if isinstance(value, (str, int, float, bool)) else "choice"

    if field_type == "checkboxes":
        valid = isinstance(value, list) and all(
            item is None or isinstance(item, (str, int, float, bool))
            for item in value
        )
        return None if valid else "choices"

    if field_type in {"linearScale", "rating"}:
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            return "scale"
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "scale"
        minimum = 1 if field_type == "rating" else int(field.get("scaleMin") or 1)
        maximum = int(field.get("maxRating") or 5) if field_type == "rating" else int(field.get("scaleMax") or 5)
        return None if number.is_integer() and minimum <= number <= maximum else "scale"

    if field_type == "file":
        valid = (
            isinstance(value, dict)
            and bool(str(value.get("name") or "").strip())
            and isinstance(value.get("size"), (int, float))
            and not isinstance(value.get("size"), bool)
            and value.get("size") >= 0
        )
        if not valid:
            return "file"
        max_size_mb = float(field.get("maxFileSizeMb") or 0)
        return "file_size" if max_size_mb > 0 and value["size"] > max_size_mb * 1024 * 1024 else None

    return None


def validate_form_answers(form: dict, answers: dict[str, Any]) -> dict[str, Any]:
    fields = get_form_fields(form)
    field_ids = {str(field.get("id") or "") for field in fields if field.get("id")}
    unknown_fields = sorted(set(answers.keys()) - field_ids)

    if unknown_fields:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Submission contains unknown fields",
                "fields": unknown_fields,
            },
        )

    cleaned_answers = {}

    for field in fields:
        field_id = str(field.get("id") or "")
        if not field_id:
            continue

        value = answers.get(field_id)

        if field.get("required") and (
            value is None
            or (isinstance(value, str) and not value.strip())
            or (isinstance(value, list) and len(value) == 0)
        ):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Required field is missing",
                    "field_id": field_id,
                    "field_label": field.get("label") or field_id,
                },
            )

        if field_id in answers:
            rejection_reason = _form_answer_rejection_reason(field, value)
            if rejection_reason:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Invalid field value",
                        "field_id": field_id,
                        "field_label": field.get("label") or field_id,
                        "field_type": field.get("type") or "shortText",
                        "reason": rejection_reason,
                    },
                )
            cleaned_answers[field_id] = normalize_answer_value(value)

    return cleaned_answers


def validate_form_draft_answers(form: dict, answers: dict[str, Any]) -> dict[str, Any]:
    fields = get_form_fields(form)
    field_ids = {str(field.get("id") or "") for field in fields if field.get("id")}
    unknown_fields = sorted(set(answers.keys()) - field_ids)
    if unknown_fields:
        raise HTTPException(
            status_code=400,
            detail={"message": "Submission contains unknown fields", "fields": unknown_fields},
        )
    return {
        field_id: normalize_answer_value(value)
        for field_id, value in answers.items()
    }


def format_public_form_draft(row: dict) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "formId": row.get("form_id"),
        "name": row.get("draft_name") or row.get("form_title") or "Incomplete form",
        "answers": row.get("answers") or {},
        "pageIndex": max(0, int(row.get("page_index") or 0)),
        "language": row.get("language") or "en",
        "savedAt": row.get("updated_at") or row.get("created_at"),
        "resumeToken": build_form_draft_token(str(row.get("id"))),
    }


def normalize_form_draft_name(value: str | None, fallback: str | None = None) -> str:
    normalized = " ".join(str(value or "").split()).strip()
    if not normalized:
        normalized = " ".join(str(fallback or "Incomplete form").split()).strip()
    return (normalized or "Incomplete form")[:120]


def require_form_draft_token(value: str | None) -> str:
    draft_id = parse_form_draft_token(value or "")
    if not draft_id:
        raise api_error(404, "form_draft_not_found", "This saved form could not be found.")
    return draft_id


def require_form_draft_owner(row: dict, identity) -> None:
    """Keep named-user drafts private while retaining anonymous bearer drafts."""
    owner_user_id = row.get("site_user_id")
    if owner_user_id is None:
        return
    identity_user = identity[0] if identity else {}
    if str(identity_user.get("id") or "") != str(owner_user_id):
        raise api_error(404, "form_draft_not_found", "This saved form could not be found.")


def schema_090_missing_draft_name(error: Exception) -> bool:
    raw = str(error).lower()
    missing_column = "draft_name" in raw and (
        "pgrst204" in raw or "schema cache" in raw or "does not exist" in raw
    )
    if not missing_column:
        return False
    try:
        state = first_row(
            service_supabase.table("application_schema_state")
            .select("schema_version")
            .eq("contract_key", "core")
            .limit(1)
            .execute()
        )
        return int((state or {}).get("schema_version", -1)) == 90
    except Exception:
        return False


def write_public_form_draft(payload: dict, *, draft_id: str | None, tenant_id: int):
    def execute(write_payload: dict):
        query = service_supabase.table("builder_form_drafts")
        if draft_id:
            return query.update(write_payload).eq("id", draft_id).eq("tenant_id", tenant_id).execute()
        return query.insert(write_payload).execute()

    try:
        return execute(payload)
    except Exception as error:
        if not schema_090_missing_draft_name(error):
            raise
        bridge_payload = dict(payload)
        bridge_payload.pop("draft_name", None)
        return execute(bridge_payload)


def format_submission(row: dict):
    return {
        "id": row.get("id"),
        "createdAt": row.get("submitted_at") or row.get("created_at"),
        "status": "New" if row.get("status") == "new" else row.get("status"),
        "answers": row.get("answers") or {},
        "quiz": row.get("quiz_result"),
    }


def normalize_subdomain(value: str) -> str:
    subdomain = normalize_hosted_address(value)

    if not subdomain or not SUBDOMAIN_PATTERN.match(subdomain):
        raise HTTPException(status_code=404, detail="Published site not found")

    return subdomain


def _request_uses_branded_address(request: Request, site_identifier: str) -> bool:
    public_domain = os.getenv("PUBLIC_SITE_DOMAIN", "madarportal.com").strip().lower()
    candidate_hosts = [
        str(request.headers.get("x-forwarded-host") or "").split(",", 1)[0],
        str(request.headers.get("host") or ""),
    ]
    origin = str(request.headers.get("origin") or "")
    if origin:
        candidate_hosts.append(urlparse(origin).hostname or "")
    expected = f"{site_identifier}.{public_domain}"
    return any(
        host.strip().lower().split(":", 1)[0] == expected
        for host in candidate_hosts
        if host
    )


def resolve_website_settings(site_identifier: str, *, request: Request):
    branded = _request_uses_branded_address(request, site_identifier)
    lookup_column = "subdomain" if branded else "standard_path_slug"
    settings_response = (
        service_supabase.table("website_settings")
        .select("*")
        .eq(lookup_column, site_identifier)
        .limit(2)
        .execute()
    )

    settings_rows = getattr(settings_response, "data", None) or []

    if not settings_rows and not branded:
        # Compatibility phase for pre-071 rows. Migration 071 backfills the
        # canonical path slug; retain old /site/:subdomain links meanwhile.
        settings_response = (
            service_supabase.table("website_settings")
            .select("*")
            .eq("subdomain", site_identifier)
            .limit(2)
            .execute()
        )
        settings_rows = getattr(settings_response, "data", None) or []

    settings = unique_public_row(
        settings_response,
        missing_detail="Published site not found",
        ambiguous_code="publication_hostname_ambiguous",
    )
    tenant_id = settings.get("tenant_id")
    if tenant_id is None or not tenant_is_active(
        tenant_id, client=service_supabase
    ):
        raise HTTPException(status_code=404, detail="Published site not found")
    if branded:
        require_branded_subdomain(settings, allow_legacy_routing=True)
    return settings


def resolve_tenant_id(settings: dict):
    tenant_id = settings.get("tenant_id")

    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Published site not found")

    return tenant_id


def resolve_public_store_settings(site_identifier: str, *, request: Request) -> dict:
    """Verify the current host binding and commercial access before any cache."""
    settings = resolve_website_settings(site_identifier, request=request)
    tenant_id = resolve_tenant_id(settings)
    state = require_entitlement(tenant_id, "ecommerce_publish")
    return {**settings, "_commercial_revision": state.get("entitlement_revision", "operator")}


def _localized_catalog_text(translations: Any, locale: str) -> dict[str, str]:
    values = translations if isinstance(translations, dict) else {}
    requested = str(locale or "en").strip()
    candidates = (requested, requested.split("-", 1)[0], "en")
    selected: dict[str, Any] = {}
    for candidate in candidates:
        value = values.get(candidate)
        if isinstance(value, dict):
            selected = value
            break
    if not selected:
        selected = next(
            (value for value in values.values() if isinstance(value, dict)),
            {},
        )
    return {
        "name": str(selected.get("name") or "").strip(),
        "description": str(selected.get("description") or "").strip(),
    }


def _public_catalog_item(row: dict[str, Any], locale: str) -> dict[str, Any]:
    localized = _localized_catalog_text(row.get("translations"), locale)
    return {
        "id": str(row.get("id") or ""),
        "slug": str(row.get("slug") or ""),
        "name": localized["name"],
        "description": localized["description"],
        "parent_id": str(row.get("parent_id") or "") or None,
        "sort_order": int(row.get("sort_order") or 0),
    }


def _public_catalog_product(
    row: dict[str, Any],
    *,
    locale: str,
    tag_ids: list[str],
) -> dict[str, Any]:
    localized = _localized_catalog_text(row.get("translations"), locale)
    track_inventory = bool(row.get("track_inventory"))
    inventory_quantity = int(row.get("inventory_quantity") or 0)
    allow_backorder = bool(row.get("allow_backorder"))
    seo_availability = "InStock" if (not track_inventory or inventory_quantity > 0) else "BackOrder" if allow_backorder else "OutOfStock"
    return {
        "id": str(row.get("id") or ""),
        "slug": str(row.get("slug") or ""),
        "sku": str(row.get("sku") or ""),
        "category_id": str(row.get("category_id") or "") or None,
        "tag_ids": tag_ids,
        "name": localized["name"],
        "description": localized["description"],
        "product_type": str(row.get("product_type") or "physical"),
        "brand": str(row.get("brand") or ""),
        "price": str(row.get("price") or "0"),
        "compare_at_price": (
            str(row.get("compare_at_price"))
            if row.get("compare_at_price") is not None
            else None
        ),
        "currency": str(row.get("currency") or "USD"),
        "in_stock": (not track_inventory) or inventory_quantity > 0 or allow_backorder,
        "allow_backorder": allow_backorder,
        "seo_availability": seo_availability,
        "images": [
            str(value)
            for value in (row.get("images") or [])
            if isinstance(value, str) and value.strip()
        ],
        "weight": str(row.get("weight")) if row.get("weight") is not None else None,
        "weight_unit": str(row.get("weight_unit") or "kg"),
        "requires_shipping": bool(row.get("requires_shipping")),
        "taxable": bool(row.get("taxable")),
        "seo_title": str(row.get("seo_title") or localized["name"]),
        "seo_description": str(row.get("seo_description") or localized["description"]),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _catalog_descendant_ids(
    categories: list[dict[str, Any]],
    root_id: str,
) -> set[str]:
    descendants = {root_id}
    changed = True
    while changed:
        changed = False
        for category in categories:
            category_id = str(category.get("id") or "")
            parent_id = str(category.get("parent_id") or "")
            if category_id and parent_id in descendants and category_id not in descendants:
                descendants.add(category_id)
                changed = True
    return descendants


def _read_public_catalog_rows(tenant_id: int) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    category_rows = rows(
        service_supabase.table("ecommerce_categories")
        .select("id,slug,parent_id,translations,sort_order,updated_at")
        .eq("tenant_id", tenant_id)
        .eq("status", "active")
        .order("sort_order")
        .order("created_at")
        .execute()
    )
    tag_rows = rows(
        service_supabase.table("ecommerce_tags")
        .select("id,slug,translations,updated_at")
        .eq("tenant_id", tenant_id)
        .eq("status", "active")
        .order("created_at", desc=True)
        .execute()
    )
    product_rows = rows(
        service_supabase.table("ecommerce_products")
        .select(
            "id,slug,sku,category_id,translations,product_type,brand,price,"
            "compare_at_price,currency,track_inventory,inventory_quantity,"
            "allow_backorder,images,weight,weight_unit,requires_shipping,"
            "taxable,seo_title,seo_description,created_at,updated_at"
        )
        .eq("tenant_id", tenant_id)
        .eq("status", "active")
        .order("created_at", desc=True)
        .execute()
    )
    link_rows = rows(
        service_supabase.table("ecommerce_product_tags")
        .select("product_id,tag_id")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    return category_rows, tag_rows, product_rows, link_rows


def _cached_public_catalog_rows(tenant_id: int) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    cache_key = ecommerce_cache_key(tenant_id, "public-catalog-source-v1")
    cached, _cache_hit = get_or_create_ecommerce_cache(
        cache_key,
        tenant_id,
        lambda: _read_public_catalog_rows(tenant_id),
    )
    return cached


def _filter_catalog_taxonomy(
    products: list[dict[str, Any]],
    *,
    category_rows: list[dict[str, Any]],
    tag_rows: list[dict[str, Any]],
    category: str,
    tag: str,
) -> list[dict[str, Any]]:
    clean_category = str(category or "").strip().lower()
    if clean_category:
        root = next(
            (
                item for item in category_rows
                if str(item.get("slug") or "").lower() == clean_category
            ),
            None,
        )
        allowed = (
            _catalog_descendant_ids(category_rows, str(root.get("id")))
            if root else set()
        )
        products = [
            item for item in products
            if str(item.get("category_id") or "") in allowed
        ]

    clean_tag = str(tag or "").strip().lower()
    if clean_tag:
        selected_tag = next(
            (
                item for item in tag_rows
                if str(item.get("slug") or "").lower() == clean_tag
            ),
            None,
        )
        tag_id = str(selected_tag.get("id") or "") if selected_tag else ""
        products = [
            item for item in products
            if tag_id and tag_id in item.get("tag_ids", [])
        ]
    return products


def _search_catalog(products: list[dict[str, Any]], search: str) -> list[dict[str, Any]]:
    clean_search = str(search or "").strip().casefold()
    if not clean_search:
        return products
    return [
        item for item in products
        if clean_search in " ".join((
            item.get("name", ""),
            item.get("description", ""),
            item.get("brand", ""),
            item.get("sku", ""),
        )).casefold()
    ]


def _sort_catalog(products: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    if sort == "price_low":
        products.sort(key=lambda item: float(item.get("price") or 0))
    elif sort == "price_high":
        products.sort(key=lambda item: float(item.get("price") or 0), reverse=True)
    elif sort == "name":
        products.sort(key=lambda item: str(item.get("name") or "").casefold())
    return products

def _optional_p1a_rows(query) -> list[dict[str, Any]] | None:
    try:
        return rows(query.execute())
    except Exception as error:
        message = str(error).lower()
        if "pgrst205" in message or "could not find the table" in message or "schema cache" in message:
            return None
        raise



def _catalog_payload(
    *,
    tenant_id: int,
    locale: str,
    search: str = "",
    category: str = "",
    tag: str = "",
    sort: Literal["latest", "price_low", "price_high", "name"] = "latest",
    page: int = 1,
    limit: int = 12,
    featured_product_ids: list[str] | None = None,
    featured_category_ids: list[str] | None = None,
) -> dict[str, Any]:
    category_rows, tag_rows, product_rows, link_rows = _cached_public_catalog_rows(tenant_id)
    tags_by_product: dict[str, list[str]] = {}
    for link in link_rows:
        tags_by_product.setdefault(
            str(link.get("product_id") or ""),
            [],
        ).append(str(link.get("tag_id") or ""))

    categories = [_public_catalog_item(row, locale) for row in category_rows]
    tags = [_public_catalog_item(row, locale) for row in tag_rows]
    products = [
        _public_catalog_product(
            row,
            locale=locale,
            tag_ids=tags_by_product.get(str(row.get("id") or ""), []),
        )
        for row in product_rows
    ]
    products = _filter_catalog_taxonomy(
        products,
        category_rows=category_rows,
        tag_rows=tag_rows,
        category=category,
        tag=tag,
    )
    variant_products = _optional_p1a_rows(service_supabase.table("ecommerce_product_options").select("product_id").eq("tenant_id", tenant_id))
    if variant_products is not None:
        variant_product_ids = {str(item.get("product_id")) for item in variant_products}
        for product in products:
            product["has_variants"] = str(product.get("id")) in variant_product_ids
    products = _sort_catalog(_search_catalog(products, search), sort)
    products_by_id = {str(item.get("id")): item for item in products}
    categories_by_id = {str(item.get("id")): item for item in categories}
    selected_products = [products_by_id[item] for item in (featured_product_ids or []) if item in products_by_id]
    selected_categories = [categories_by_id[item] for item in (featured_category_ids or []) if item in categories_by_id]

    total = len(products)
    safe_page = max(1, page)
    safe_limit = max(1, min(limit, 48))
    start = (safe_page - 1) * safe_limit
    return {
        "categories": categories,
        "tags": tags,
        "products": products[start:start + safe_limit],
        "featured_products": selected_products,
        "featured_categories": selected_categories,
        "pagination": {
            "page": safe_page,
            "limit": safe_limit,
            "total": total,
            "pages": max(1, (total + safe_limit - 1) // safe_limit),
        },
    }


def _catalog_product_payload(
    *,
    tenant_id: int,
    product_slug: str,
    locale: str,
) -> dict[str, Any]:
    category_rows, tag_rows, product_rows, link_rows = _cached_public_catalog_rows(tenant_id)
    row = next(
        (
            item for item in product_rows
            if str(item.get("slug") or "").lower() == product_slug
        ),
        None,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    product_id = str(row.get("id") or "")
    product_tag_ids = [
        str(link.get("tag_id") or "")
        for link in link_rows
        if str(link.get("product_id") or "") == product_id
    ]
    product = _public_catalog_product(
        row,
        locale=locale,
        tag_ids=product_tag_ids,
    )
    category = next(
        (
            _public_catalog_item(item, locale)
            for item in category_rows
            if str(item.get("id") or "") == str(product.get("category_id") or "")
        ),
        None,
    )
    tags = [
        _public_catalog_item(item, locale)
        for item in tag_rows
        if str(item.get("id") or "") in product_tag_ids
    ]
    attribute_rows = _optional_p1a_rows(service_supabase.table("ecommerce_product_attributes").select("id,name_translations,value_translations,sort_order").eq("tenant_id", tenant_id).eq("product_id", product_id).order("sort_order"))
    if attribute_rows is None:
        return {"product": product, "category": category, "tags": tags, "attributes": [], "options": [], "variants": []}
    option_rows = rows(service_supabase.table("ecommerce_product_options").select("id,code,name_translations,required,sort_order").eq("tenant_id", tenant_id).eq("product_id", product_id).order("sort_order").execute())
    option_ids = [str(item["id"]) for item in option_rows]
    value_rows = [] if not option_ids else rows(service_supabase.table("ecommerce_product_option_values").select("id,option_id,code,value_translations,sort_order").eq("tenant_id", tenant_id).eq("product_id", product_id).eq("active", True).in_("option_id", option_ids).order("sort_order").execute())
    variant_rows = rows(service_supabase.table("ecommerce_product_variants").select("id,sku,price_override,compare_at_price_override,track_inventory,inventory_quantity,allow_backorder,images").eq("tenant_id", tenant_id).eq("product_id", product_id).eq("active", True).execute())
    variant_ids = [str(item["id"]) for item in variant_rows]
    links = [] if not variant_ids else rows(service_supabase.table("ecommerce_variant_option_values").select("variant_id,option_id,option_value_id").eq("tenant_id", tenant_id).in_("variant_id", variant_ids).execute())
    for option in option_rows:
        names = option.pop("name_translations") or {}
        option["name"] = names.get(locale) or names.get("en") or next(iter(names.values()), "")
        option["values"] = []
        for source in value_rows:
            if str(source.get("option_id")) == str(option["id"]):
                value = dict(source); labels = value.pop("value_translations") or {}
                value["value"] = labels.get(locale) or labels.get("en") or next(iter(labels.values()), "")
                option["values"].append(value)
    for variant in variant_rows:
        variant["option_value_ids"] = [str(link["option_value_id"]) for link in links if str(link["variant_id"]) == str(variant["id"])]
        variant["price"] = str(variant.get("price_override") if variant.get("price_override") is not None else product["price"])
        variant["compare_at_price"] = variant.get("compare_at_price_override") if variant.get("compare_at_price_override") is not None else product.get("compare_at_price")
        variant["in_stock"] = not variant.get("track_inventory") or bool(variant.get("allow_backorder")) or int(variant.get("inventory_quantity") or 0) > 0
        variant["seo_availability"] = "InStock" if (not variant.get("track_inventory") or int(variant.get("inventory_quantity") or 0) > 0) else "BackOrder" if variant.get("allow_backorder") else "OutOfStock"
        variant["images"] = variant.get("images") or product.get("images") or []
    attributes = []
    for attribute in attribute_rows:
        names, values = attribute.pop("name_translations") or {}, attribute.pop("value_translations") or {}
        attribute["name"] = names.get(locale) or names.get("en") or next(iter(names.values()), "")
        attribute["value"] = values.get(locale) or values.get("en") or next(iter(values.values()), "")
        attributes.append(attribute)
    product["has_variants"] = bool(option_rows)
    product["in_stock"] = any(item["in_stock"] for item in variant_rows) if option_rows else product["in_stock"]
    return {"product": product, "category": category, "tags": tags, "attributes": attributes, "options": option_rows, "variants": variant_rows}


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def get_local_user_by_auth_id(auth_id: str):
    return first_row(
        service_supabase.table("users")
        .select("*")
        .eq("auth_id", str(auth_id))
        .limit(1)
        .execute()
    )


def get_active_tenant_membership(tenant_id: int, user_id: int):
    return first_row(
        service_supabase.table("tenant_site_memberships")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("user_id", user_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )


def get_tenant_staff_membership(tenant_id: int, user_id: int):
    return first_row(
        service_supabase.table("tenant_memberships")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("user_id", user_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )


def get_tenant_site_access(settings: dict, user_row: dict):
    tenant_id = resolve_tenant_id(settings)
    user_id = user_row.get("id")
    site_membership = get_active_tenant_membership(tenant_id, user_id)
    if site_membership:
        return {**site_membership, "_access_kind": "site"}

    staff_membership = get_tenant_staff_membership(tenant_id, user_id)
    if staff_membership:
        return {**staff_membership, "_access_kind": "staff"}

    if (
        str(settings.get("user_id") or "") == str(user_id or "")
        or str(user_row.get("tenant_id") or "") == str(tenant_id)
    ):
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role": "owner",
            "status": "active",
            "_access_kind": "staff",
        }

    return None


def require_tenant_visitor(subdomain: str, request: Request, response: Response):
    settings = resolve_website_settings(normalize_subdomain(subdomain), request=request)
    _, user_row = get_authenticated_user_row(request, response)
    membership = get_tenant_site_access(settings, user_row)

    if not membership:
        raise HTTPException(status_code=403, detail="This account does not belong to this website")

    return user_row, membership


def get_optional_tenant_visitor(subdomain: str, request: Request, response: Response):
    try:
        return require_tenant_visitor(subdomain, request, response)
    except HTTPException as error:
        if error.status_code in {401, 403}:
            return None
        raise


def authorize_site_resource(
    *,
    subdomain: str,
    request: Request,
    response: Response,
    project: dict,
    capability: str,
    resource_type: str,
    resource_id: str,
    always_require_member: bool = False,
):
    restricted = always_require_member or resource_is_role_restricted(
        project=project,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    identity = (
        require_tenant_visitor(subdomain, request, response)
        if always_require_member
        else get_optional_tenant_visitor(subdomain, request, response)
    )
    if not restricted:
        return identity
    if not identity:
        raise HTTPException(status_code=401, detail="Log in to access this resource")
    _, membership = identity
    if not has_project_permission(
        membership=membership,
        project_id=str(project.get("id") or ""),
        capability=capability,
        client=service_supabase,
        project=project,
        resource_type=resource_type,
        resource_id=resource_id,
    ):
        raise HTTPException(status_code=403, detail="Your role cannot access this resource")
    return identity


def site_record_owner_fields(identity) -> dict[str, Any]:
    if not identity:
        return {"site_user_id": None, "site_membership_id": None}
    user_row, membership = identity
    access_kind = str(membership.get("_access_kind") or "").strip().lower()
    user_id = user_row.get("id")
    if user_id is None or access_kind not in {"site", "staff"}:
        raise RuntimeError("site_record_identity_invalid")
    membership_id = membership.get("id") if access_kind == "site" else None
    if access_kind == "site" and membership_id is None:
        raise RuntimeError("site_record_identity_invalid")
    return {
        "site_user_id": user_id,
        "site_membership_id": membership_id,
    }


def attach_site_record_owner(table_name: str, row: dict, identity):
    if not identity or not row:
        return row

    update = site_record_owner_fields(identity)
    if all(row.get(field) == value for field, value in update.items()):
        return row

    response = (
        service_supabase.table(table_name)
        .update(update)
        .eq("id", row.get("id"))
        .eq("tenant_id", row.get("tenant_id"))
        .eq("project_id", row.get("project_id"))
        .execute()
    )
    return first_row(response) or {**row, **update}


def reconcile_site_record_owner_after_commit(table_name: str, row: dict, identity):
    """Bridge compatibility for schema 92 without returning a false failure.

    Schema 93 writes ownership inside the domain transaction and this becomes
    a no-op. While a schema-92 bridge is active, the compatibility update is a
    second durable operation. Its failure is observable, but cannot truthfully
    turn the already-committed customer record into a failed submission.
    """

    try:
        return attach_site_record_owner(table_name, row, identity)
    except Exception as error:
        logger.error(
            "public.site_record_owner_reconciliation_failed",
            extra={"error_type": type(error).__name__},
        )
        return row

@router.post("/sites/{subdomain}/auth/register")
def register_tenant_visitor(
    subdomain: str,
    payload: TenantRegisterRequest,
    request: Request,
):
    clean_subdomain = normalize_subdomain(subdomain)
    settings = resolve_website_settings(clean_subdomain, request=request)
    tenant_id = resolve_tenant_id(settings)
    project = get_bound_published_project(settings)
    clean_email = normalize_email(payload.email)
    name_parts = payload.full_name.strip().split(None, 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    auth_user_id = None
    local_user_id = None

    enforce_auth_rate_limit(request, "tenant_signup", f"{clean_subdomain}:{clean_email}")

    existing = service_supabase.table("users").select("id").eq("email", clean_email).limit(1).execute()
    if rows(existing):
        raise HTTPException(status_code=409, detail="Email is already registered")

    try:
        auth_response = supabase.auth.sign_up(
            {
                "email": clean_email,
                "password": payload.password,
                "options": {
                    "email_redirect_to": f"{FRONTEND_URL}/site/{clean_subdomain}",
                    "data": {"first_name": first_name, "last_name": last_name},
                },
            }
        )
        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Could not create account")

        auth_user_id = str(auth_response.user.id)
        user_result = service_supabase.table("users").insert(
            {
                "auth_id": auth_user_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": clean_email,
                "tenant_id": None,
                "account_kind": "site_visitor",
                "account_status": "pending_verification",
                "email_verified": False,
                "email_verified_at": None,
            }
        ).execute()
        local_user = first_row(user_result)
        if not local_user:
            raise HTTPException(status_code=400, detail="Could not create account")
        local_user_id = local_user["id"]

        membership_result = service_supabase.table("tenant_site_memberships").insert(
            {
                "tenant_id": tenant_id,
                "user_id": local_user["id"],
                "auth_id": auth_user_id,
                "role": "customer",
                "status": "active",
                "source": "registered",
            }
        ).execute()
        membership = first_row(membership_result)
        if not membership:
            raise HTTPException(status_code=400, detail="Could not create account")

        assign_project_role(
            membership_id=int(membership["id"]),
            tenant_id=tenant_id,
            project=project,
            role_key="customer",
            actor_user_id=None,
            client=service_supabase,
        )

        return {
            "message": "Account created. Check your email, then log in.",
            "requires_email_verification": True,
        }
    except HTTPException:
        if local_user_id:
            try:
                service_supabase.table("tenant_site_memberships").delete().eq("user_id", local_user_id).execute()
                service_supabase.table("users").delete().eq("id", local_user_id).execute()
            except Exception:
                pass
        if auth_user_id:
            try:
                service_supabase.auth.admin.delete_user(auth_user_id)
            except Exception:
                pass
        raise
    except Exception as error:
        logger.warning("public.tenant_signup_failed", extra={"tenant_id": tenant_id, "error_type": type(error).__name__})
        if local_user_id:
            try:
                service_supabase.table("tenant_site_memberships").delete().eq("user_id", local_user_id).execute()
                service_supabase.table("users").delete().eq("id", local_user_id).execute()
            except Exception:
                pass
        if auth_user_id:
            try:
                service_supabase.auth.admin.delete_user(auth_user_id)
            except Exception:
                pass
        raise HTTPException(status_code=400, detail="Could not create account") from error


@router.post("/sites/{subdomain}/auth/login")
def login_tenant_visitor(
    subdomain: str,
    payload: TenantLoginRequest,
    request: Request,
    response: Response,
):
    clean_subdomain = normalize_subdomain(subdomain)
    settings = resolve_website_settings(clean_subdomain, request=request)
    tenant_id = resolve_tenant_id(settings)
    clean_email = normalize_email(payload.email)
    enforce_auth_rate_limit(request, "tenant_login", f"{clean_subdomain}:{clean_email}")

    try:
        auth_response = supabase.auth.sign_in_with_password(
            {"email": clean_email, "password": payload.password}
        )
        if not auth_response.user or not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not auth_user_email_is_verified(auth_response.user):
            raise HTTPException(status_code=403, detail="Please verify your email before logging in")

        user_row = get_local_user_by_auth_id(str(auth_response.user.id))
        if not user_row or not get_tenant_site_access(settings, user_row):
            raise HTTPException(status_code=403, detail="This account does not belong to this website")

        user_row, _ = synchronize_verified_account(auth_response.user, user_row)
        csrf_token = set_auth_cookies(
            response,
            auth_response.session.access_token,
            auth_response.session.refresh_token,
        )
        return {"logged_in": True, "user": build_user_payload(user_row), "csrf_token": csrf_token}
    except HTTPException:
        raise
    except Exception as error:
        logger.warning("public.tenant_login_failed", extra={"tenant_id": tenant_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=401, detail="Invalid email or password") from error


@router.get("/sites/{subdomain}/auth/status")
def tenant_visitor_status(subdomain: str, request: Request, response: Response):
    try:
        user_row, membership = require_tenant_visitor(subdomain, request, response)
        return {"logged_in": True, "user": build_user_payload(user_row), "role": membership.get("role")}
    except HTTPException:
        return {"logged_in": False, "user": None}


@router.post("/sites/{subdomain}/screen-time/heartbeat")
def create_public_screen_time_heartbeat(
    subdomain: str,
    payload: PublicScreenTimeHeartbeat,
    request: Request,
    response: Response,
):
    user_row, membership = require_tenant_visitor(subdomain, request, response)
    enforce_public_rate_limit(
        request,
        "screen_time_heartbeat",
        str(user_row.get("id") or subdomain),
    )
    record_screen_time(
        tenant_id=int(membership.get("tenant_id")),
        user_id=int(user_row.get("id")),
        active_seconds=payload.active_seconds,
    )
    return {"success": True}


@router.post("/sites/{subdomain}/auth/logout")
def logout_tenant_visitor(subdomain: str, response: Response):
    normalize_subdomain(subdomain)
    delete_auth_cookies(response)
    return {"logged_in": False, "message": "Logged out"}

@router.get("/sites/{subdomain}/store-profile")
def get_public_store_profile(subdomain: str, request: Request, response: Response):
    clean_subdomain = normalize_subdomain(subdomain)
    enforce_public_rate_limit(request, "store_profile_lookup", clean_subdomain)
    settings = resolve_public_store_settings(clean_subdomain, request=request)
    site_profile = build_public_store_profile(settings, clean_subdomain)
    canonical = json.dumps(site_profile, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    metadata = {
        "etag": f'"store-profile-{hashlib.sha256(canonical.encode("utf-8")).hexdigest()}"'
    }
    apply_public_cache_headers(response, metadata)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["CDN-Cache-Control"] = "no-store"
    if request_etag_matches(request, metadata):
        return Response(
            status_code=304,
            headers={
                "ETag": metadata["etag"],
                "Cache-Control": "private, no-store",
                "CDN-Cache-Control": "no-store",
            },
        )
    return {"success": True, "site": site_profile}

def _canonical_storefront_base(settings: dict, site_identifier: str, request: Request) -> str:
    if _request_uses_branded_address(request, site_identifier):
        public_domain = os.getenv("PUBLIC_SITE_DOMAIN", "madarportal.com").strip().lower()
        return f"https://{site_identifier}.{public_domain}/shop"
    slug = str(settings.get("standard_path_slug") or site_identifier).strip().lower()
    return f"{FRONTEND_URL.rstrip('/')}/site/{quote(slug, safe='')}/shop"


def _storefront_sitemap_xml(settings: dict, site_identifier: str, request: Request) -> str:
    tenant_id = resolve_tenant_id(settings)
    categories, _tags, products, _links = _cached_public_catalog_rows(tenant_id)
    base = _canonical_storefront_base(settings, site_identifier, request)
    entries = [(base, settings.get("updated_at"))]
    entries.extend((f"{base}/catalog?category={quote(str(row.get('slug') or ''), safe='-')}", row.get("updated_at")) for row in categories if row.get("slug"))
    entries.extend((f"{base}/product/{quote(str(row.get('slug') or ''), safe='-')}", row.get("updated_at")) for row in products if row.get("slug"))
    urls = []
    for location, updated_at in entries:
        lastmod = str(updated_at or "")[:10]
        lastmod_xml = f"<lastmod>{xml_escape(lastmod)}</lastmod>" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", lastmod) else ""
        urls.append(f"<url><loc>{xml_escape(location)}</loc>{lastmod_xml}</url>")
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(urls) + "</urlset>"


@router.get("/sites/{subdomain}/sitemap.xml", name="get_public_storefront_sitemap")
def get_public_storefront_sitemap(subdomain: str, request: Request):
    clean_subdomain = normalize_subdomain(subdomain)
    enforce_public_rate_limit(request, "storefront_sitemap", clean_subdomain)
    settings = resolve_public_store_settings(clean_subdomain, request=request)
    return Response(content=_storefront_sitemap_xml(settings, clean_subdomain, request), media_type="application/xml", headers={"Cache-Control": "public, max-age=300, stale-while-revalidate=3600"})


@router.get("/sites/{subdomain}/robots.txt")
def get_public_storefront_robots(subdomain: str, request: Request):
    clean_subdomain = normalize_subdomain(subdomain)
    resolve_public_store_settings(clean_subdomain, request=request)
    sitemap = request.url_for("get_public_storefront_sitemap", subdomain=clean_subdomain)
    body = "User-agent: *\nDisallow: /checkout\nDisallow: /confirmation/\nDisallow: /account\nSitemap: " + str(sitemap) + "\n"
    return Response(content=body, media_type="text/plain", headers={"Cache-Control": "public, max-age=300"})

@router.get("/sites/{subdomain}/catalog")
def get_public_catalog(
    subdomain: str,
    request: Request,
    response: Response,
    search: str = "",
    category: str = "",
    tag: str = "",
    sort: Literal["latest", "price_low", "price_high", "name"] = "latest",
    locale: str = "en",
    page: int = 1,
    limit: int = 12,
):
    clean_subdomain = normalize_subdomain(subdomain)
    enforce_public_rate_limit(request, "catalog_lookup", clean_subdomain)
    settings = resolve_public_store_settings(clean_subdomain, request=request)
    tenant_id = resolve_tenant_id(settings)
    locale_value = str(locale or "en")[:16]
    search_value = str(search or "")[:200]
    category_value = str(category or "")[:160]
    tag_value = str(tag or "")[:160]
    page_value = max(1, page)
    limit_value = max(1, min(limit, 48))
    growth = _public_store_growth(settings.get("ecommerce_theme") if isinstance(settings.get("ecommerce_theme"), dict) else {})
    cache_key = ecommerce_cache_key(
        tenant_id,
        "catalog-v2",
        entitlement_revision=settings.get("_commercial_revision"),
        locale=locale_value,
        search=search_value,
        category=category_value,
        tag=tag_value,
        sort=sort,
        page=page_value,
        limit=limit_value,
    )
    try:
        payload, cache_hit = get_or_create_ecommerce_cache(
            cache_key,
            tenant_id,
            lambda: _catalog_payload(
                tenant_id=tenant_id,
                locale=locale_value,
                search=search_value,
                category=category_value,
                tag=tag_value,
                sort=sort,
                page=page_value,
                limit=limit_value,
                featured_product_ids=growth["featured_product_ids"],
                featured_category_ids=growth["featured_category_ids"],
            ),
        )
    except Exception as error:
        raw = str(error).lower()
        if "pgrst205" in raw or "could not find the table" in raw or "schema cache" in raw:
            raise HTTPException(
                status_code=503,
                detail="Ecommerce catalog is not available",
            ) from error
        raise

    site_profile = build_public_store_profile(settings, clean_subdomain)
    canonical = json.dumps(
        {"site": site_profile, "catalog": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    metadata = {
        "etag": f'"catalog-{hashlib.sha256(canonical.encode("utf-8")).hexdigest()}"'
    }
    apply_public_cache_headers(response, metadata)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["CDN-Cache-Control"] = "no-store"
    response.headers["X-Ecommerce-Cache"] = "HIT" if cache_hit else "MISS"
    if request_etag_matches(request, metadata):
        return Response(
            status_code=304,
            headers={
                "ETag": metadata["etag"],
                "Cache-Control": "private, no-store",
                "CDN-Cache-Control": "no-store",
                "X-Ecommerce-Cache": "HIT" if cache_hit else "MISS",
            },
        )
    return {
        "success": True,
        "site": site_profile,
        "catalog": payload,
    }


@router.get("/sites/{subdomain}/catalog/products/{product_slug}")
def get_public_catalog_product(
    subdomain: str,
    product_slug: str,
    request: Request,
    response: Response,
    locale: str = "en",
):
    clean_subdomain = normalize_subdomain(subdomain)
    clean_slug = str(product_slug or "").strip().lower()
    if not clean_slug or len(clean_slug) > 160:
        raise HTTPException(status_code=404, detail="Product not found")
    enforce_public_rate_limit(
        request,
        "catalog_product_lookup",
        f"{clean_subdomain}:{clean_slug}",
    )
    settings = resolve_public_store_settings(clean_subdomain, request=request)
    tenant_id = resolve_tenant_id(settings)
    locale_value = str(locale or "en")[:16]
    cache_key = ecommerce_cache_key(
        tenant_id,
        "product-v2",
        entitlement_revision=settings.get("_commercial_revision"),
        locale=locale_value,
        slug=clean_slug,
    )
    result, cache_hit = get_or_create_ecommerce_cache(
        cache_key,
        tenant_id,
        lambda: _catalog_product_payload(
            tenant_id=tenant_id,
            product_slug=clean_slug,
            locale=locale_value,
        ),
    )
    site_profile = build_public_store_profile(settings, clean_subdomain)
    canonical = json.dumps({"site": site_profile, **result}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    metadata = {
        "etag": f'"product-{hashlib.sha256(canonical.encode("utf-8")).hexdigest()}"'
    }
    apply_public_cache_headers(response, metadata)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["CDN-Cache-Control"] = "no-store"
    response.headers["X-Ecommerce-Cache"] = "HIT" if cache_hit else "MISS"
    if request_etag_matches(request, metadata):
        return Response(
            status_code=304,
            headers={
                "ETag": metadata["etag"],
                "Cache-Control": "private, no-store",
                "CDN-Cache-Control": "no-store",
                "X-Ecommerce-Cache": "HIT" if cache_hit else "MISS",
            },
        )
    return {
        "success": True,
        "site": site_profile,
        **result,
    }


def _ecommerce_order_storage_error(error: Exception) -> HTTPException:
    message = str(error).lower()
    mappings = (
        ("idempotency_conflict", 409, "idempotency_conflict", "This checkout key was already used for a different order."),
        ("ecommerce_inventory_insufficient", 409, "inventory_insufficient", "A product does not have enough stock."),
        ("ecommerce_variant_required", 409, "variant_required", "Choose all required product options."),
        ("ecommerce_variant_unavailable", 409, "variant_unavailable", "The selected product variant is unavailable."),
        ("ecommerce_variant_incomplete", 409, "variant_unavailable", "The selected product variant is incomplete."),
        ("ecommerce_variant_not_allowed", 409, "variant_invalid", "This simple product does not accept a variant."),
        ("ecommerce_product_unavailable", 409, "product_unavailable", "One or more products are no longer available."),
        ("ecommerce_delivery_area_unavailable", 409, "delivery_area_unavailable", "This store no longer delivers to the selected area."),
        ("ecommerce_delivery_street_required", 400, "delivery_street_required", "A street address is required."),
        ("ecommerce_currency_configuration_required", 409, "currency_configuration_required", "This store must configure one currency before accepting orders."),
        ("ecommerce_currency_product_mismatch", 409, "currency_mismatch", "The catalog contains a product in a different currency."),
        ("ecommerce_quantity_invalid", 400, "quantity_invalid", "Choose a quantity between 1 and 99."),
        ("ecommerce_order_items", 400, "order_items_invalid", "The order items are invalid."),
        ("ecommerce_order_payload_invalid", 400, "order_invalid", "The order is invalid."),
    )
    for marker, status, code, detail in mappings:
        if marker in message:
            return api_error(status, code, detail)
    if "pgrst202" in message or "create_ecommerce_order_safe" in message or "schema cache" in message:
        return api_error(503, "checkout_upgrade_required", "Checkout is temporarily unavailable while the store is upgraded.")
    return api_error(503, "dependency_unavailable", "The order could not be saved. Try again shortly.")


@router.get("/sites/{subdomain}/delivery-areas")
def get_public_store_delivery_areas(subdomain: str, request: Request):
    clean_subdomain = normalize_subdomain(subdomain)
    enforce_public_rate_limit(request, "store_delivery_areas", clean_subdomain)
    settings = resolve_public_store_settings(clean_subdomain, request=request)
    tenant_id = resolve_tenant_id(settings)
    mapping_rows = rows(
        service_supabase.table("ecommerce_tenant_service_areas")
        .select("service_area_id")
        .eq("tenant_id", tenant_id)
        .eq("enabled", True)
        .execute()
    )
    enabled_ids = [str(row.get("service_area_id")) for row in mapping_rows if row.get("service_area_id")]
    areas = [] if not enabled_ids else rows(
        service_supabase.table("ecommerce_service_areas").select("id,code,name_en,name_ar,sort_order")
        .in_("id", enabled_ids).eq("active", True).order("sort_order").execute()
    )
    return {"success": True, "areas": areas}


@router.post("/sites/{subdomain}/cart/reconcile")
def reconcile_public_store_cart(
    subdomain: str,
    payload: PublicStoreCartReconcile,
    request: Request,
):
    clean_subdomain = normalize_subdomain(subdomain)
    enforce_public_rate_limit(request, "store_cart_reconcile", clean_subdomain)
    settings = resolve_public_store_settings(clean_subdomain, request=request)
    tenant_id = resolve_tenant_id(settings)
    currency = str(settings.get("ecommerce_currency") or "").strip().upper()
    if not currency:
        raise api_error(409, "currency_configuration_required", "This store must configure one currency before checkout.")

    requested_product_ids = list(dict.fromkeys(str(item.product_id) for item in payload.items))
    product_rows = rows(
        service_supabase.table("ecommerce_products")
        .select("id,slug,translations,status,price,currency,track_inventory,inventory_quantity,allow_backorder,images")
        .eq("tenant_id", tenant_id)
        .eq("status", "active")
        .in_("id", requested_product_ids)
        .execute()
    )
    by_id = {str(product.get("id")): product for product in product_rows}
    optional_options = _optional_p1a_rows(service_supabase.table("ecommerce_product_options").select("product_id").eq("tenant_id", tenant_id).in_("product_id", requested_product_ids))
    option_rows = optional_options or []
    variant_product_ids = {str(item.get("product_id")) for item in option_rows}
    requested_variant_ids = list(dict.fromkeys(str(item.variant_id) for item in payload.items if item.variant_id))
    variant_rows = [] if optional_options is None or not requested_variant_ids else rows(
        service_supabase.table("ecommerce_product_variants")
        .select("id,product_id,sku,price_override,track_inventory,inventory_quantity,allow_backorder,images,active")
        .eq("tenant_id", tenant_id).in_("id", requested_variant_ids).execute()
    )
    variants_by_id = {str(variant.get("id")): variant for variant in variant_rows}
    reconciled = []
    for item in payload.items:
        product_id = str(item.product_id)
        variant_id = str(item.variant_id) if item.variant_id else None
        product = by_id.get(product_id)
        if not product:
            reconciled.append({"product_id": product_id, "variant_id": variant_id, "requested_quantity": item.quantity, "available": False, "reason": "unavailable"})
            continue
        product_currency = str(product.get("currency") or "").upper()
        variant = variants_by_id.get(variant_id) if variant_id else None
        has_variants = product_id in variant_product_ids
        reason = None
        if has_variants and not variant_id:
            reason = "variant_required"
        elif variant_id and (not variant or str(variant.get("product_id")) != product_id or not variant.get("active")):
            reason = "variant_unavailable"
        elif not has_variants and variant_id:
            reason = "variant_invalid"
        inventory_owner = variant if has_variants and variant else product
        tracked = bool(inventory_owner.get("track_inventory"))
        backorder = bool(inventory_owner.get("allow_backorder"))
        inventory = max(0, int(inventory_owner.get("inventory_quantity") or 0))
        maximum = 99 if not tracked or backorder else min(99, inventory)
        if product_currency != currency:
            reason = "currency_mismatch"
        elif reason is None and item.quantity > maximum:
            reason = "insufficient_inventory"
        price = variant.get("price_override") if variant and variant.get("price_override") is not None else product.get("price")
        images = variant.get("images") if variant and variant.get("images") else product.get("images")
        reconciled.append({
            "product_id": product_id,
            "variant_id": variant_id,
            "requested_quantity": item.quantity,
            "available": reason is None,
            "reason": reason,
            "max_quantity": maximum,
            "name": _localized_catalog_text(product.get("translations"), "en")["name"],
            "slug": str(product.get("slug") or ""),
            "images": images or [],
            "price": str(Decimal(str(price or "0")).quantize(Decimal("0.01"))),
            "sku": variant.get("sku") if variant else product.get("sku"),
            "currency": currency,
        })
    return {"success": True, "currency": currency, "valid": all(item["available"] for item in reconciled), "items": reconciled}


@router.post("/sites/{subdomain}/orders", status_code=201)
def create_public_store_order(
    subdomain: str,
    payload: PublicStoreOrderCreate,
    request: Request,
    response: Response,
):
    clean_subdomain = normalize_subdomain(subdomain)
    enforce_public_rate_limit(request, "store_order_create", clean_subdomain)
    settings = resolve_public_store_settings(clean_subdomain, request=request)
    tenant_id = resolve_tenant_id(settings)
    idempotency_key = normalize_idempotency_key(payload, request)
    if not idempotency_key:
        raise api_error(400, "idempotency_key_required", "An idempotency key is required for checkout.")
    confirmation_token = hash_public_identifier(f"ecommerce-confirmation:{tenant_id}:{idempotency_key}")
    customer_id = None
    if request.cookies.get("madar_access_token") or request.cookies.get("madar_refresh_token"):
        try:
            customer = get_authenticated_user_row(
                request, response,
                allow_admin_account_access=False,
                reject_admin_account_access=True,
            )
            customer_id = int(customer["id"])
        except HTTPException:
            customer_id = None
    order_payload = {
        "tenant_id": tenant_id,
        "verified_customer_id": customer_id,
        "customer_name": payload.customer_name.strip(),
        "email": str(payload.email).lower(),
        "phone": payload.phone.strip(),
        "address_line_1": payload.address_line_1.strip(),
        "address_line_2": payload.address_line_2.strip(),
        "city": payload.city.strip(),
        "postal_code": payload.postal_code.strip(),
        "country": payload.country.strip(),
        "notes": payload.notes.strip(),
        "service_area_id": str(payload.service_area_id),
        "street": payload.street.strip(),
        "building": payload.building.strip(),
        "floor_apartment": payload.floor_apartment.strip(),
        "address_description": payload.address_description.strip(),
        "delivery_notes": payload.delivery_notes.strip(),
        "payment_method": payload.payment_method,
        "items": [item.model_dump(mode="json") for item in payload.items],
    }
    try:
        rpc_params = {
            "p_order": order_payload,
            "p_idempotency_key_hash": hash_public_identifier(f"ecommerce-order:{tenant_id}:{idempotency_key}"),
            "p_request_hash": canonical_request_hash(order_payload),
            "p_confirmation_token_hash": hash_public_identifier(f"ecommerce-confirmation-token:{confirmation_token}"),
            "p_customer_id": customer_id,
        }
        try:
            rpc_response = service_supabase.rpc("create_ecommerce_order_safe", rpc_params).execute()
        except Exception as rpc_error:
            raw_error = str(rpc_error).lower()
            missing_identity_overload = "p_customer_id" in raw_error and (
                "pgrst202" in raw_error or "could not find" in raw_error or "schema cache" in raw_error
            )
            if not missing_identity_overload:
                raise
            legacy_params = {key: value for key, value in rpc_params.items() if key != "p_customer_id"}
            rpc_response = service_supabase.rpc("create_ecommerce_order_safe", legacy_params).execute()
        result = getattr(rpc_response, "data", None)
        if isinstance(result, list):
            result = result[0] if result else None
        if not isinstance(result, dict):
            raise RuntimeError("create_ecommerce_order_safe_empty_result")
    except HTTPException:
        raise
    except Exception as error:
        raise _ecommerce_order_storage_error(error) from error
    order = result.get("order")
    if not isinstance(order, dict):
        raise api_error(503, "dependency_unavailable", "The order could not be saved. Try again shortly.")

    return {
        "success": True,
        "confirmation_token": confirmation_token,
        "confirmation_path": f"/confirmation/{confirmation_token}",
        "idempotent_replay": bool(result.get("duplicate")),
        "order": {key: order.get(key) for key in (
            "id", "order_number", "status", "payment_status", "payment_method",
            "currency", "subtotal", "discount_total", "total",
        )},
    }


@router.get("/sites/{subdomain}/orders/confirmation/{confirmation_token}")
def get_public_order_confirmation(subdomain: str, confirmation_token: str, request: Request):
    clean_subdomain = normalize_subdomain(subdomain)
    enforce_public_rate_limit(request, "store_order_confirmation", clean_subdomain)
    if not re.fullmatch(r"[0-9a-f]{64}", str(confirmation_token or "")):
        raise HTTPException(status_code=404, detail="Order confirmation not found")
    settings = resolve_public_store_settings(clean_subdomain, request=request)
    tenant_id = resolve_tenant_id(settings)
    token_hash = hash_public_identifier(f"ecommerce-confirmation-token:{confirmation_token}")
    order_rows = rows(
        service_supabase.table("ecommerce_orders").select(
            "id,order_number,status,payment_status,payment_method,currency,subtotal,discount_total,total,created_at,customer_name,customer_email,customer_phone,service_area_code,service_area_name_en,service_area_name_ar,street,building,floor_apartment,address_description,delivery_notes"
        ).eq("tenant_id", tenant_id).eq("confirmation_token_hash", token_hash).limit(1).execute()
    )
    if not order_rows:
        raise HTTPException(status_code=404, detail="Order confirmation not found")
    order = order_rows[0]
    order_id = str(order.get("id"))
    item_rows = rows(
        service_supabase.table("ecommerce_order_items").select(
            # Loyalty attribution is response metadata introduced by schema
            # 097. Historical order truth at schema 096 lives in these fields.
            "id,sku,product_name,product_slug,product_snapshot,variant_snapshot,selected_options_snapshot,quantity,list_unit_price,discount_amount,discount_source,unit_price,line_total"
        ).eq("tenant_id", tenant_id).eq("order_id", order_id).order("created_at").execute()
    )
    history_rows = rows(
        service_supabase.table("ecommerce_order_status_history").select(
            "previous_status,new_status,note,created_at"
        ).eq("tenant_id", tenant_id).eq("order_id", order_id).order("created_at").execute()
    )
    return {"success": True, "site": build_public_store_profile(settings, clean_subdomain), "order": order, "items": item_rows, "status_history": history_rows}


@router.get("/sites/{subdomain}/loyalty/me")
def get_public_store_loyalty(subdomain: str, request: Request, response: Response):
    clean_subdomain = normalize_subdomain(subdomain)
    settings = resolve_public_store_settings(clean_subdomain, request=request)
    tenant_id = resolve_tenant_id(settings)
    customer = get_authenticated_user_row(
        request, response,
        allow_admin_account_access=False,
        reject_admin_account_access=True,
    )
    customer_id = int(customer["id"])
    try:
        service_supabase.rpc("expire_ecommerce_loyalty_entitlements_safe", {
            "p_tenant_id": tenant_id, "p_customer_id": customer_id,
        }).execute()
        account_rows = rows(service_supabase.table("ecommerce_loyalty_accounts").select("*").eq("tenant_id", tenant_id).eq("customer_id", customer_id).limit(1).execute())
        entitlement_rows = rows(service_supabase.table("ecommerce_loyalty_entitlements").select("*").eq("tenant_id", tenant_id).eq("customer_id", customer_id).order("created_at", desc=True).limit(20).execute())
        transaction_rows = rows(service_supabase.table("ecommerce_loyalty_transactions").select("id,transaction_type,points_delta,balance_after,order_id,rule_version,entitlement_id,metadata,created_at").eq("tenant_id", tenant_id).eq("customer_id", customer_id).order("created_at", desc=True).limit(50).execute())
        product_ids = list({str(item.get("reward_product_id")) for item in entitlement_rows if item.get("reward_product_id")})
        products = rows(service_supabase.table("ecommerce_products").select("id,slug,translations,images").eq("tenant_id", tenant_id).in_("id", product_ids).execute()) if product_ids else []
    except Exception as error:
        raise HTTPException(status_code=503, detail="Loyalty is temporarily unavailable") from error
    products_by_id = {str(product.get("id")): product for product in products}
    return {
        "account": account_rows[0] if account_rows else {
            "current_balance": 0, "lifetime_earned": 0, "lifetime_spent": 0,
        },
        "entitlements": [
            {**item, "reward_product": products_by_id.get(str(item.get("reward_product_id")))}
            for item in entitlement_rows
        ],
        "transactions": transaction_rows,
    }


@router.get("/sites/{subdomain}/bootstrap")
def get_public_site_bootstrap(subdomain: str, request: Request):
    clean_subdomain = normalize_subdomain(subdomain)
    enforce_public_rate_limit(request, "site_bootstrap_lookup", clean_subdomain)
    settings = resolve_website_settings(clean_subdomain, request=request)
    require_public_runtime_entitlement(settings, "website_publish")
    if not str(settings.get("published_project_id") or "").strip():
        raise HTTPException(status_code=404, detail="Published site not found")
    project = get_bound_published_project(settings, require_pages=False)
    return {
        "success": True,
        "site": build_public_site_profile(settings, clean_subdomain, project),
        "publication": {
            "project_id": str(project.get("id") or ""),
            "published_version": int(project.get("published_version") or 0),
            "published_at": project.get("last_published_at"),
        },
    }


@router.post("/sites/{subdomain}/visits", status_code=201)
def record_public_site_visit(
    subdomain: str,
    visit: PublicSiteVisitCreate,
    request: Request,
):
    clean_subdomain = normalize_subdomain(subdomain)
    enforce_public_rate_limit(
        request,
        "site_visit",
        f"{clean_subdomain}:{visit.surface}",
    )
    settings = resolve_website_settings(clean_subdomain, request=request)
    tenant_id = resolve_tenant_id(settings)
    try:
        service_supabase.rpc(
            "record_public_site_visit_safe",
            {
                "p_tenant_id": tenant_id,
                "p_surface": visit.surface,
            },
        ).execute()
    except Exception as error:
        raw = str(error).lower()
        if (
            "record_public_site_visit_safe" in raw
            or "site_visit_counters" in raw
            or "pgrst202" in raw
            or "schema cache" in raw
        ):
            raise api_error(
                503,
                "visit_tracking_upgrade_required",
                "Visit tracking is temporarily unavailable.",
            ) from error
        raise
    return {"success": True}


@router.get("/sites/{subdomain}")
def get_public_site(subdomain: str, request: Request, response: Response):
    clean_subdomain = normalize_subdomain(subdomain)
    enforce_public_rate_limit(request, "site_lookup", clean_subdomain)
    settings = resolve_website_settings(clean_subdomain, request=request)
    require_public_runtime_entitlement(settings, "website_publish")
    project = get_bound_published_project(settings)

    identity = get_optional_tenant_visitor(clean_subdomain, request, response)
    authorized_page_ids: set[str] = set()
    if identity:
        _, membership = identity
        for page in (project.get("published_schema") or {}).get("pages", []):
            page_id = str(page.get("id") or "") if isinstance(page, dict) else ""
            if page_id and has_project_permission(
                membership=membership,
                project_id=str(project.get("id") or ""),
                capability="view_protected_page",
                client=service_supabase,
                project=project,
                resource_type="page",
                resource_id=page_id,
            ):
                authorized_page_ids.add(page_id)

    public_schema = build_authorized_public_schema(
        project.get("published_schema") or {},
        authorized_page_ids=authorized_page_ids,
    )
    metadata = build_publication_metadata(
        project,
        public_schema,
        settings=settings,
        site_identifier=clean_subdomain,
    )
    apply_public_cache_headers(response, metadata, private=bool(identity))
    if not identity and request_etag_matches(request, metadata):
        return Response(
            status_code=304,
            headers={
                "ETag": metadata["etag"],
                "Cache-Control": "public, max-age=0, must-revalidate",
                "Vary": "Host, X-Forwarded-Host, Origin",
                "CDN-Cache-Control": "no-store",
            },
        )

    return {
        "success": True,
        "site": build_public_site_profile(settings, clean_subdomain, project),
        "project": {
            "published_schema": public_schema,
            **metadata,
        },
    }


@router.get("/sites/{subdomain}/pages/{page_reference:path}")
def get_member_site_page(
    subdomain: str,
    page_reference: str,
    request: Request,
    response: Response,
):
    clean_subdomain = normalize_subdomain(subdomain)
    clean_page_reference = str(page_reference or "").strip()
    if not clean_page_reference:
        raise HTTPException(status_code=404, detail="Page not found")

    enforce_public_rate_limit(
        request,
        "member_page_lookup",
        f"{clean_subdomain}:{clean_page_reference}",
    )
    settings = resolve_website_settings(clean_subdomain, request=request)
    require_public_runtime_entitlement(settings, "website_publish")
    project = get_bound_published_project(settings)
    schema, page, auth_destination_ids = find_published_page(project, clean_page_reference)
    if page_access_kind(page, auth_destination_ids) == "unsupported_role":
        raise HTTPException(status_code=403, detail="Page access is not configured")
    authorize_site_resource(
        subdomain=clean_subdomain,
        request=request,
        response=response,
        project=project,
        capability="view_protected_page",
        resource_type="page",
        resource_id=str(page.get("id") or ""),
        always_require_member=True,
    )

    authorized_schema = build_authorized_public_schema(
        schema,
        authorized_page_ids={str(page.get("id") or "")},
    )
    metadata = build_publication_metadata(
        project,
        authorized_schema,
        settings=settings,
        site_identifier=clean_subdomain,
    )
    apply_public_cache_headers(response, metadata, private=True)
    return {
        "success": True,
        "site": build_public_site_profile(settings, clean_subdomain, project),
        "project": {
            "published_schema": authorized_schema,
            **metadata,
        },
    }


@router.get("/sites/{subdomain}/forms/{form_id}")
def get_public_form(subdomain: str, form_id: str, request: Request, response: Response):
    clean_subdomain = normalize_subdomain(subdomain)
    clean_form_id = (form_id or "").strip()

    if not clean_form_id:
        raise HTTPException(status_code=404, detail="Form not found")

    enforce_public_rate_limit(
        request,
        "form_lookup",
        f"{clean_subdomain}:{clean_form_id}",
    )
    settings = resolve_website_settings(clean_subdomain, request=request)
    require_public_runtime_entitlement(settings, "public_form_links")
    project, form, published_schema = get_published_form_for_site(settings, clean_form_id)
    authorize_site_resource(
        subdomain=clean_subdomain,
        request=request,
        response=response,
        project=project,
        capability="submit_protected_form",
        resource_type="form",
        resource_id=clean_form_id,
    )

    return {
        "success": True,
        "site": build_public_site_profile(settings, clean_subdomain, project),
        "publication": {
            "project_id": str(project.get("id") or ""),
            "published_version": int(project.get("published_version") or 0),
            "published_at": project.get("last_published_at"),
        },
        "form": build_public_form(form),
        "theme": published_schema.get("theme") or {},
        "language": published_schema.get("language") or published_schema.get("lang") or "en",
    }


def _quiz_subject_hash(request: Request, subdomain: str, form_id: str) -> str:
    return hash_public_identifier(
        ":".join((
            "quiz-subject-v1",
            subdomain,
            form_id,
            get_client_ip(request),
            str(request.headers.get("user-agent") or "")[:300],
        ))
    )


def _rpc_object(response: Any) -> dict[str, Any]:
    data = getattr(response, "data", None)
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        raise api_error(503, "dependency_unavailable", "The quiz service is unavailable.")
    return data


@router.post("/sites/{subdomain}/forms/{form_id}/attempts")
def start_public_quiz_attempt(
    subdomain: str,
    form_id: str,
    payload: PublicQuizAttemptCreate,
    request: Request,
    response: Response,
):
    clean_subdomain = normalize_subdomain(subdomain)
    clean_form_id = str(form_id or "").strip()
    enforce_public_form_submission_rate_limit(request, "quiz_start", f"{clean_subdomain}:{clean_form_id}")
    reject_suspicious_public_submission(
        honeypot=payload.honeypot,
        submission_elapsed_ms=payload.submission_elapsed_ms,
        route_name="quiz_start",
    )
    settings = resolve_website_settings(clean_subdomain, request=request)
    require_public_runtime_entitlement(settings, "public_form_links")
    tenant_id = resolve_tenant_id(settings)
    project, form, _ = get_published_form_for_site(settings, clean_form_id)
    if not is_public_quiz(form):
        raise api_error(409, "quiz_mode_required", "This published form is not a quiz.")
    authorize_site_resource(
        subdomain=clean_subdomain,
        request=request,
        response=response,
        project=project,
        capability="submit_protected_form",
        resource_type="form",
        resource_id=clean_form_id,
    )
    attempt = build_attempt_payload(
        tenant_id=tenant_id,
        project=project,
        form=form,
        subject_hash=_quiz_subject_hash(request, clean_subdomain, clean_form_id),
    )
    quiz_settings = form.get("quiz") if isinstance(form.get("quiz"), dict) else {}
    max_attempts = 1
    if quiz_settings.get("allowRetakes"):
        max_retakes = max(0, min(int(quiz_settings.get("maxRetakes") or 0), 99))
        max_attempts = 100 if max_retakes == 0 else 1 + max_retakes
    try:
        created = _rpc_object(service_supabase.rpc(
            "start_public_quiz_attempt",
            {"p_attempt": attempt, "p_max_attempts": max_attempts},
        ).execute())
    except HTTPException:
        raise
    except Exception as error:
        raw = str(error).lower()
        if "quiz_attempt_limit_reached" in raw:
            raise api_error(409, "quiz_attempt_limit_reached", "No quiz attempts remain.") from error
        logger.warning("public.quiz_start_failed", extra={"tenant_id": tenant_id, "error_type": type(error).__name__})
        raise api_error(503, "dependency_unavailable", "The quiz could not be started.") from error
    return {
        "success": True,
        "attempt": {
            "id": created.get("id"),
            "state": created.get("state"),
            "started_at": created.get("started_at"),
            "deadline_at": created.get("deadline_at"),
            "publication_version": created.get("publication_version"),
            "question_order": created.get("question_order") or [],
            "form": build_public_form(form),
        },
    }


@router.post("/sites/{subdomain}/forms/{form_id}/attempts/{attempt_id}/finalize")
def finalize_public_quiz_attempt(
    subdomain: str,
    form_id: str,
    attempt_id: str,
    payload: PublicQuizFinalizeCreate,
    request: Request,
    response: Response,
):
    clean_subdomain = normalize_subdomain(subdomain)
    clean_form_id = str(form_id or "").strip()
    clean_attempt_id = str(attempt_id or "").strip()
    enforce_public_form_submission_rate_limit(request, "quiz_finalize", f"{clean_subdomain}:{clean_form_id}")
    validate_public_answer_payload_limits(payload.answers)
    settings = resolve_website_settings(clean_subdomain, request=request)
    require_public_runtime_entitlement(settings, "public_form_links")
    tenant_id = resolve_tenant_id(settings)
    project, form, _ = get_published_form_for_site(settings, clean_form_id)
    if not is_public_quiz(form):
        raise api_error(409, "quiz_mode_required", "This published form is not a quiz.")
    authorize_site_resource(
        subdomain=clean_subdomain,
        request=request,
        response=response,
        project=project,
        capability="submit_protected_form",
        resource_type="form",
        resource_id=clean_form_id,
    )
    try:
        rows = getattr(
            service_supabase.table("public_quiz_attempts")
            .select("*")
            .eq("id", clean_attempt_id)
            .eq("tenant_id", tenant_id)
            .eq("project_id", project.get("id"))
            .eq("form_id", clean_form_id)
            .limit(2)
            .execute(),
            "data",
            None,
        ) or []
    except Exception as error:
        raise api_error(503, "dependency_unavailable", "The quiz could not be finalized.") from error
    if len(rows) != 1:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    attempt = rows[0]
    if not hmac.compare_digest(
        str(attempt.get("subject_hash") or ""),
        _quiz_subject_hash(request, clean_subdomain, clean_form_id),
    ):
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    validate_submission_order(attempt, payload.answers)
    private_form = attempt.get("private_form_snapshot")
    if not isinstance(private_form, dict):
        raise api_error(409, "quiz_attempt_invalid", "The quiz attempt cannot be graded.")
    cleaned_answers = validate_form_answers(private_form, payload.answers)
    result = grade_public_quiz(private_form, cleaned_answers)
    submission = {
        "tenant_id": tenant_id,
        "project_id": project.get("id"),
        "form_id": clean_form_id,
        "form_title": private_form.get("title"),
        "form_version": attempt.get("publication_version"),
        "status": "new",
        "answers": cleaned_answers,
        "quiz_result": result,
        "field_snapshot": copy.deepcopy(get_form_fields(private_form)),
        "submitter_ip": get_client_ip(request),
        "user_agent": str(request.headers.get("user-agent") or "")[:1000],
    }
    try:
        finalized = _rpc_object(service_supabase.rpc(
            "finalize_public_quiz_attempt",
            {
                "p_attempt_id": clean_attempt_id,
                "p_tenant_id": tenant_id,
                "p_project_id": project.get("id"),
                "p_form_id": clean_form_id,
                "p_publication_version": int(attempt.get("publication_version") or 0),
                "p_answers": cleaned_answers,
                "p_result": result,
                "p_submission": submission,
                "p_request_hash": canonical_request_hash({
                    "attempt_id": clean_attempt_id,
                    "answers": cleaned_answers,
                }),
            },
        ).execute())
    except HTTPException:
        raise
    except Exception as error:
        raw = str(error).lower()
        code = "quiz_attempt_expired" if "quiz_attempt_expired" in raw else "quiz_attempt_conflict"
        status = 410 if code == "quiz_attempt_expired" else 409
        raise api_error(status, code, "The quiz attempt can no longer be finalized.") from error
    if finalized.get("error") == "quiz_attempt_expired":
        raise api_error(410, "quiz_attempt_expired", "The quiz attempt can no longer be finalized.")
    final_result = finalized.get("result") or result
    show_results = bool((private_form.get("quiz") or {}).get("showResults", True))
    return {
        "success": True,
        "duplicate": bool(finalized.get("duplicate")),
        "attempt": {"id": clean_attempt_id, "state": "completed"},
        "result": final_result if show_results else None,
    }


@router.get("/sites/{subdomain}/forms/{form_id}/drafts")
def list_public_builder_form_drafts(
    subdomain: str,
    form_id: str,
    request: Request,
    response: Response,
):
    clean_subdomain = normalize_subdomain(subdomain)
    clean_form_id = (form_id or "").strip()
    enforce_public_form_submission_rate_limit(
        request,
        "draft_list",
        f"{clean_subdomain}:{clean_form_id}",
    )
    settings = resolve_website_settings(clean_subdomain, request=request)
    require_public_runtime_entitlement(settings, "public_form_links")
    tenant_id = resolve_tenant_id(settings)
    project, _form, _ = get_published_form_for_site(settings, clean_form_id)
    identity = authorize_site_resource(
        subdomain=clean_subdomain,
        request=request,
        response=response,
        project=project,
        capability="submit_protected_form",
        resource_type="form",
        resource_id=clean_form_id,
    )
    if not identity:
        return {"success": True, "drafts": [], "items": []}

    identity_user, _identity_membership = identity
    site_user_id = identity_user.get("id")
    if not site_user_id:
        return {"success": True, "drafts": [], "items": []}

    drafts_response = (
        service_supabase.table("builder_form_drafts")
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("project_id", project.get("id"))
        .eq("form_id", clean_form_id)
        .eq("site_user_id", site_user_id)
        .order("updated_at", desc=True)
        .limit(25)
        .execute()
    )
    drafts = [
        format_public_form_draft(row)
        for row in (drafts_response.data or [])
    ]
    return {"success": True, "drafts": drafts, "items": drafts}


@router.get("/sites/{subdomain}/forms/{form_id}/drafts/{resume_token}")
def get_public_builder_form_draft(subdomain: str, form_id: str, resume_token: str, request: Request, response: Response):
    clean_subdomain = normalize_subdomain(subdomain)
    clean_form_id = (form_id or "").strip()
    draft_id = require_form_draft_token(resume_token)
    enforce_public_form_submission_rate_limit(request, "draft_read", f"{clean_subdomain}:{clean_form_id}")
    settings = resolve_website_settings(clean_subdomain, request=request)
    require_public_runtime_entitlement(settings, "public_form_links")
    tenant_id = resolve_tenant_id(settings)
    project, _form, _ = get_published_form_for_site(settings, clean_form_id)
    identity = authorize_site_resource(
        subdomain=clean_subdomain,
        request=request,
        response=response,
        project=project,
        capability="submit_protected_form",
        resource_type="form",
        resource_id=clean_form_id,
    )
    draft_response = (
        service_supabase.table("builder_form_drafts")
        .select("*")
        .eq("id", draft_id)
        .eq("tenant_id", tenant_id)
        .eq("project_id", project.get("id"))
        .eq("form_id", clean_form_id)
        .limit(1)
        .execute()
    )
    saved = first_row(draft_response)
    if not saved:
        raise api_error(404, "form_draft_not_found", "This saved form could not be found.")
    require_form_draft_owner(saved, identity)
    return {"success": True, "draft": format_public_form_draft(saved)}


@router.post("/sites/{subdomain}/forms/{form_id}/drafts")
def save_public_builder_form_draft(
    subdomain: str,
    form_id: str,
    draft: PublicFormDraftUpsert,
    request: Request,
    response: Response,
):
    clean_subdomain = normalize_subdomain(subdomain)
    clean_form_id = (form_id or "").strip()
    if not clean_form_id:
        raise HTTPException(status_code=404, detail="Form not found")
    enforce_public_form_submission_rate_limit(request, "draft_save", f"{clean_subdomain}:{clean_form_id}")
    reject_suspicious_public_submission(
        honeypot=draft.honeypot,
        submission_elapsed_ms=draft.submission_elapsed_ms,
        route_name="form_draft",
    )
    settings = resolve_website_settings(clean_subdomain, request=request)
    require_public_runtime_entitlement(settings, "public_form_links")
    tenant_id = resolve_tenant_id(settings)
    project, form, _ = get_published_form_for_site(settings, clean_form_id)
    identity = authorize_site_resource(
        subdomain=clean_subdomain,
        request=request,
        response=response,
        project=project,
        capability="submit_protected_form",
        resource_type="form",
        resource_id=clean_form_id,
    )
    answers = draft.answers or {}
    validate_public_answer_payload_limits(answers)
    cleaned_answers = validate_form_draft_answers(form, answers)
    owner_fields = site_record_owner_fields(identity)
    payload = {
        "tenant_id": tenant_id,
        "project_id": project.get("id"),
        "form_id": clean_form_id,
        "form_title": form.get("title"),
        "form_version": project.get("published_version"),
        "draft_name": normalize_form_draft_name(draft.draft_name, form.get("title")),
        "answers": cleaned_answers,
        "field_snapshot": copy.deepcopy(get_form_fields(form)),
        "form_element_id": draft.form_element_id,
        "page_index": draft.page_index,
        "language": draft.language,
        **owner_fields,
        "submitter_ip": get_client_ip(request),
        "user_agent": request.headers.get("user-agent", "")[:1000],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        if draft.resume_token:
            draft_id = require_form_draft_token(draft.resume_token)
            existing_response = (
                service_supabase.table("builder_form_drafts")
                .select("*")
                .eq("id", draft_id)
                .eq("tenant_id", tenant_id)
                .eq("project_id", project.get("id"))
                .eq("form_id", clean_form_id)
                .limit(1)
                .execute()
            )
            existing = first_row(existing_response)
            if not existing:
                raise api_error(404, "form_draft_not_found", "This saved form could not be found.")
            require_form_draft_owner(existing, identity)
            saved_response = write_public_form_draft(
                payload,
                draft_id=draft_id,
                tenant_id=tenant_id,
            )
        else:
            saved_response = write_public_form_draft(
                payload,
                draft_id=None,
                tenant_id=tenant_id,
            )
        saved = first_row(saved_response)
        if not saved:
            raise RuntimeError("form_draft_empty_result")
    except HTTPException:
        raise
    except Exception as error:
        logger.warning("public.form_draft_save_failed", extra={"error_type": type(error).__name__})
        raise api_error(503, "dependency_unavailable", "Your progress could not be saved right now.") from error
    return {"success": True, "draft": format_public_form_draft(saved)}


@router.post("/sites/{subdomain}/forms/{form_id}/submissions")
def submit_public_builder_form(
    subdomain: str,
    form_id: str,
    submission: PublicFormSubmissionCreate,
    request: Request,
    response: Response,
):
    clean_subdomain = normalize_subdomain(subdomain)
    clean_form_id = (form_id or "").strip()
    idempotency_key = normalize_idempotency_key(submission, request)
    resume_draft_id = (
        require_form_draft_token(submission.resume_token) if submission.resume_token else None
    )

    if not clean_form_id:
        raise HTTPException(status_code=404, detail="Form not found")

    enforce_public_form_submission_rate_limit(
        request,
        "create",
        f"{clean_subdomain}:{clean_form_id}",
    )
    reject_suspicious_public_submission(
        honeypot=submission.honeypot,
        submission_elapsed_ms=submission.submission_elapsed_ms,
        route_name="form",
    )

    settings = resolve_website_settings(clean_subdomain, request=request)
    require_public_runtime_entitlement(settings, "public_form_links")
    tenant_id = resolve_tenant_id(settings)
    project, form, _ = get_published_form_for_site(settings, clean_form_id)
    if is_public_quiz(form):
        raise api_error(
            409,
            "quiz_attempt_required",
            "Start and finalize a server-authoritative quiz attempt.",
        )
    identity = authorize_site_resource(
        subdomain=clean_subdomain,
        request=request,
        response=response,
        project=project,
        capability="submit_protected_form",
        resource_type="form",
        resource_id=clean_form_id,
    )

    owner_fields = site_record_owner_fields(identity)

    answers = submission.answers or {}
    validate_public_answer_payload_limits(answers)
    cleaned_answers = validate_form_answers(form, answers)
    fields = copy.deepcopy(get_form_fields(form))
    submitter_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")[:1000]

    payload = {
        "tenant_id": tenant_id,
        "project_id": project.get("id"),
        "form_id": clean_form_id,
        "form_title": form.get("title"),
        "form_version": project.get("published_version"),
        "status": "new",
        "answers": cleaned_answers,
        "quiz_result": None,
        "field_snapshot": fields,
        "submitter_ip": submitter_ip,
        "user_agent": user_agent,
        **owner_fields,
    }
    request_hash = canonical_request_hash({
        "tenant_id": tenant_id,
        "project_id": project.get("id"),
        "form_id": clean_form_id,
        "form_version": project.get("published_version"),
        "answers": cleaned_answers,
        **owner_fields,
    })
    idempotency_key_hash = (
        hash_public_identifier(f"form-idempotency:{idempotency_key}")
        if idempotency_key
        else None
    )
    saved_submission, duplicate = insert_builder_form_submission(
        payload,
        idempotency_key_hash=idempotency_key_hash,
        request_hash=request_hash,
        notification={
            "event_type": "builder.form_submitted",
            "source_type": "form",
            "title": "New form submission",
            "body": f"{form.get('title') or 'A published form'} received a new response.",
            "data": {
                "block_type": "form",
                "project_id": project.get("id"),
                "form_id": clean_form_id,
                "form_title": form.get("title"),
                "subdomain": clean_subdomain,
                "action": build_notification_action(
                    kind="form_submission", tenant_id=tenant_id
                ),
            },
        },
    )
    saved_submission = reconcile_site_record_owner_after_commit(
        "builder_form_submissions", saved_submission, identity
    )

    logger.info(
        "public.form_submission_created",
        extra={
            "tenant_id": tenant_id,
            "project_id": project.get("id"),
            "form_id": clean_form_id,
            "submission_id": saved_submission.get("id"),
            "idempotent_replay": duplicate,
        },
    )

    if not duplicate:
        increment_operational_usage(tenant_id, "form_submissions")
    if resume_draft_id:
        try:
            draft_response = (
                service_supabase.table("builder_form_drafts")
                .select("id,site_user_id")
                .eq("id", resume_draft_id)
                .eq("tenant_id", tenant_id)
                .eq("project_id", project.get("id"))
                .eq("form_id", clean_form_id)
                .limit(1)
                .execute()
            )
            saved_draft = first_row(draft_response)
            if saved_draft:
                require_form_draft_owner(saved_draft, identity)
                (
                    service_supabase.table("builder_form_drafts")
                    .delete()
                    .eq("id", resume_draft_id)
                    .eq("tenant_id", tenant_id)
                    .eq("project_id", project.get("id"))
                    .eq("form_id", clean_form_id)
                    .execute()
                )
        except HTTPException:
            # Submission succeeded; an unowned draft must remain untouched and
            # the response must not reveal that another user's draft exists.
            pass
        except Exception as error:
            logger.warning(
                "public.form_draft_cleanup_failed",
                extra={"draft_id": resume_draft_id, "error_type": type(error).__name__},
            )

    return format_submission(saved_submission)


@router.post("/sites/{subdomain}/events")
def submit_public_builder_block_event(
    subdomain: str,
    event: PublicBuilderBlockEventCreate,
    request: Request,
    response: Response,
):
    clean_subdomain = normalize_subdomain(subdomain)
    block_type = normalize_public_block_type(event.block_type)
    block_id = (event.block_id or "").strip() or None
    event_type = normalize_public_event_type(event.event_type, block_type)
    idempotency_key = normalize_idempotency_key(event, request)

    enforce_public_form_submission_rate_limit(
        request,
        "event",
        f"{clean_subdomain}:{block_type}:{block_id or 'unknown'}",
    )
    reject_suspicious_public_submission(
        honeypot=event.honeypot,
        submission_elapsed_ms=event.submission_elapsed_ms,
        route_name="event",
    )

    settings = resolve_website_settings(clean_subdomain, request=request)
    tenant_id = resolve_tenant_id(settings)
    project = get_bound_published_project(settings)

    if project.get("status") != "published":
        raise HTTPException(status_code=404, detail="Published site not found")

    published_schema = project.get("published_schema") or {}

    if not isinstance(published_schema, dict):
        raise HTTPException(status_code=404, detail="Published site not found")

    block = find_published_block(published_schema, block_id, block_type)

    if not block:
        raise HTTPException(status_code=404, detail="Block not found")

    if block_type == "reservationBlock":
        require_public_runtime_entitlement(settings, "reservations")

    resource_block_id = str(block_id or block.get("id") or "")
    identity = (
        authorize_site_resource(
            subdomain=clean_subdomain,
            request=request,
            response=response,
            project=project,
            capability="make_reservation",
            resource_type="reservation",
            resource_id=resource_block_id,
        )
        if block_type == "reservationBlock"
        else get_optional_tenant_visitor(clean_subdomain, request, response)
    )

    payload = event.payload or {}
    validate_public_event_payload_limits(payload)
    cleaned_payload = {
        str(key)[:120]: normalize_event_value(value)
        for key, value in payload.items()
    }
    if block_type == "reservationBlock":
        validate_reservation_custom_answers(block, cleaned_payload)
        validate_configured_reservation_slot(block, cleaned_payload)
    timing = normalize_reservation_timing(cleaned_payload)

    if block_type == "reservationBlock":
        reservation = block.get("reservation") or {}
        title = event.title or reservation.get("title") or "New reservation request"
        service = cleaned_payload.get("service")
        date = cleaned_payload.get("date")
        time = cleaned_payload.get("time")
        details = " ".join(str(item) for item in [service, date, time] if item)
        body = details or f"{reservation.get('title') or 'A reservation block'} received a new request."
    else:
        title = event.title or "New site event"
        body = f"{block_type} triggered an event on the published site."

    owner_fields = site_record_owner_fields(identity)

    reservation_payload = build_builder_reservation_payload(
        tenant_id=tenant_id,
        project=project,
        subdomain=clean_subdomain,
        block=block,
        block_id=block_id,
        block_type=block_type,
        title=title,
        payload=cleaned_payload,
        request=request,
        timing=timing,
    )
    reservation_payload.update(owner_fields)
    stable_request_payload = {
        key: value
        for key, value in reservation_payload.items()
        if key not in {"submitter_ip", "user_agent"}
    }
    request_hash = canonical_request_hash(stable_request_payload)
    idempotency_key_hash = (
        hash_public_identifier(f"reservation-idempotency:{idempotency_key}")
        if idempotency_key
        else None
    )
    cancellation_token = None
    if block_type == "reservationBlock":
        cancellation_token = build_cancellation_token(
            tenant_id=tenant_id,
            project_id=str(project.get("id") or ""),
            block_id=str(block_id or block.get("id") or block_type),
            idempotency_key_hash=idempotency_key_hash,
            request_hash=request_hash,
        )
        reservation_payload["cancellation_token_hash"] = hash_public_identifier(
            f"reservation-cancellation:{cancellation_token}"
        )
        reservation_payload["cancellation_expires_at"] = (
            datetime.now(timezone.utc) + timedelta(days=RESERVATION_CANCELLATION_TTL_DAYS)
        ).isoformat()
    saved_reservation, duplicate = insert_builder_reservation(
        reservation_payload,
        idempotency_key_hash=idempotency_key_hash,
        request_hash=request_hash,
        exclusive_slot=(
            block_type == "reservationBlock" and reservation_block_is_exclusive(block)
        ),
        notification={
            "event_type": event_type,
            "source_type": block_type,
            "title": title,
            "body": body,
            "data": {
                "project_id": project.get("id"),
                "block_id": block.get("id"),
                "block_type": block_type,
                "subdomain": clean_subdomain,
                "payload": cleaned_payload,
                "action": build_notification_action(
                    kind=(
                        "reservation"
                        if block_type == "reservationBlock"
                        else "notification_center"
                    ),
                    tenant_id=tenant_id,
                ),
            },
        },
    )
    saved_reservation = reconcile_site_record_owner_after_commit(
        "builder_reservations", saved_reservation, identity
    )
    reservation_id = str(saved_reservation.get("id") or "")

    if not duplicate:
        if block_type == "reservationBlock":
            increment_operational_usage(tenant_id, "reservation_requests")
            invalidate_calendar_workspace_cache(tenant_id)

    logger.info(
        "public.builder_block_event_created",
        extra={
            "tenant_id": tenant_id,
            "project_id": project.get("id"),
            "reservation_id": reservation_id,
            "block_id": block.get("id"),
            "block_type": block_type,
            "event_type": event_type,
            "idempotent_replay": duplicate,
        },
    )

    response_payload = {
        "success": True,
        "reservation_id": reservation_id,
        "idempotent_replay": duplicate,
        "message": "Reservation submitted successfully.",
    }
    if cancellation_token:
        response_payload["cancellation_token"] = cancellation_token
    return response_payload


@router.post("/reservations/{reservation_id}/cancel")
def cancel_public_builder_reservation(
    reservation_id: str,
    cancellation: PublicReservationCancellationRequest,
    request: Request,
):
    if not re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}",
        reservation_id,
    ):
        raise api_error(404, "reservation_cancellation_invalid", "Cancellation link is invalid.")

    enforce_public_form_submission_rate_limit(
        request,
        "reservation_cancel",
        reservation_id,
    )

    token_hash = hash_public_identifier(
        f"reservation-cancellation:{cancellation.token}"
    )
    try:
        response = service_supabase.rpc(
            "cancel_builder_reservation_notified_safe",
            {
                "p_reservation_id": reservation_id,
                "p_token_hash": token_hash,
                "p_cancelled_at": datetime.now(timezone.utc).isoformat(),
            },
        ).execute()
        data = getattr(response, "data", None)
        reservation = data[0] if isinstance(data, list) and data else data
        if not isinstance(reservation, dict):
            raise RuntimeError("reservation_cancellation_empty_result")
    except Exception as error:
        text = str(error).lower()
        if "reservation_cancellation_replayed" in text:
            raise api_error(
                409,
                "reservation_cancellation_replayed",
                "This reservation was already cancelled.",
            )
        if "reservation_cancellation_expired" in text:
            raise api_error(
                410,
                "reservation_cancellation_expired",
                "This cancellation link has expired.",
            )
        if "reservation_cancellation_unavailable" in text:
            raise api_error(
                409,
                "reservation_cancellation_unavailable",
                "This reservation can no longer be cancelled online.",
            )
        if "reservation_cancellation_invalid" in text:
            raise api_error(
                404,
                "reservation_cancellation_invalid",
                "Cancellation link is invalid.",
            )
        logger.warning(
            "public.builder_reservation_cancel_failed",
            extra={"error_type": type(error).__name__},
        )
        raise api_error(
            503,
            "dependency_unavailable",
            "The reservation could not be cancelled. Try again shortly.",
        )

    logger.info(
        "public.builder_reservation_cancelled",
        extra={"reservation_id": reservation_id},
    )
    return {
        "success": True,
        "reservation_id": reservation_id,
        "status": "cancelled",
    }

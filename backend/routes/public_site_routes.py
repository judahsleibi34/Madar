import logging
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator

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
from services.notification_service import create_builder_block_event_notification
from services.notification_outbox_service import enqueue_notification
from services.api_errors import api_error
from services.account_lifecycle_service import synchronize_verified_account

router = APIRouter(prefix="/public", tags=["Public Sites"])
logger = logging.getLogger(__name__)

SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
MAX_PUBLIC_FORM_ANSWER_FIELDS = 100
MAX_PUBLIC_FORM_ANSWER_STRING_LENGTH = 5000
MAX_PUBLIC_FORM_ANSWERS_JSON_BYTES = 64 * 1024
MAX_PUBLIC_BLOCK_EVENT_FIELDS = 100
MAX_PUBLIC_BLOCK_EVENT_STRING_LENGTH = 5000
MAX_PUBLIC_BLOCK_EVENT_JSON_BYTES = 64 * 1024
BLOCK_TYPE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,200}$")
MIN_PUBLIC_SUBMISSION_ELAPSED_MS = int(
    os.getenv("MIN_PUBLIC_SUBMISSION_ELAPSED_MS", "750")
)
RESERVATION_CANCELLATION_TTL_DAYS = int(
    os.getenv("RESERVATION_CANCELLATION_TTL_DAYS", "30")
)
FRONTEND_URL = resolve_frontend_url()


class PublicFormSubmissionCreate(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    form_element_id: Optional[str] = None
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


def rows(response):
    return getattr(response, "data", None) or []


def first_row(response):
    result_rows = rows(response)
    return result_rows[0] if result_rows else None


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


def normalize_idempotency_key(event: PublicBuilderBlockEventCreate, request: Request) -> str | None:
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


def get_latest_published_project_for_tenant(tenant_id: int):
    project_response = (
        service_supabase.table("builder_projects")
        .select(
            "id, tenant_id, name, slug, status, published_schema, "
            "published_version, last_published_at, updated_at"
        )
        .eq("tenant_id", tenant_id)
        .eq("status", "published")
        .not_.is_("published_schema", "null")
        .order("last_published_at", desc=True)
        .limit(1)
        .execute()
    )

    project = first_row(project_response)

    if not project:
        raise HTTPException(status_code=404, detail="Published site not found")

    return project


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


def find_published_form(published_schema: dict, form_id: str) -> dict:
    forms = published_schema.get("forms")

    if not isinstance(forms, list):
        raise HTTPException(status_code=404, detail="Form not found")

    for form in forms:
        if isinstance(form, dict) and str(form.get("id") or "") == form_id:
            return form

    raise HTTPException(status_code=404, detail="Form not found")


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
                return element

    return None


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
) -> tuple[dict[str, Any], bool]:
    try:
        rpc = getattr(service_supabase, "rpc", None)
        if callable(rpc):
            insert_response = rpc(
                "create_builder_reservation_safe",
                {
                    "p_reservation": payload,
                    "p_idempotency_key_hash": idempotency_key_hash,
                    "p_request_hash": request_hash,
                    "p_exclusive_slot": exclusive_slot,
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
            or value == ""
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
            cleaned_answers[field_id] = normalize_answer_value(value)

    return cleaned_answers


def format_submission(row: dict):
    return {
        "id": row.get("id"),
        "createdAt": row.get("submitted_at") or row.get("created_at"),
        "status": "New" if row.get("status") == "new" else row.get("status"),
        "answers": row.get("answers") or {},
        "quiz": row.get("quiz_result"),
    }


def normalize_subdomain(value: str) -> str:
    subdomain = (value or "").strip().lower()

    if not subdomain or not SUBDOMAIN_PATTERN.match(subdomain):
        raise HTTPException(status_code=404, detail="Published site not found")

    return subdomain


def resolve_website_settings(subdomain: str):
    settings_response = (
        service_supabase.table("website_settings")
        .select("*")
        .eq("subdomain", subdomain)
        .limit(1)
        .execute()
    )

    settings_rows = getattr(settings_response, "data", None) or []

    if not settings_rows:
        raise HTTPException(status_code=404, detail="Published site not found")

    return settings_rows[0]


def resolve_tenant_id(settings: dict):
    tenant_id = settings.get("tenant_id")

    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Published site not found")

    return tenant_id


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
        return site_membership

    staff_membership = get_tenant_staff_membership(tenant_id, user_id)
    if staff_membership:
        return staff_membership

    if (
        str(settings.get("user_id") or "") == str(user_id or "")
        or str(user_row.get("tenant_id") or "") == str(tenant_id)
    ):
        return {"tenant_id": tenant_id, "user_id": user_id, "role": "owner", "status": "active"}

    return None


def require_tenant_visitor(subdomain: str, request: Request, response: Response):
    settings = resolve_website_settings(normalize_subdomain(subdomain))
    _, user_row = get_authenticated_user_row(request, response)
    membership = get_tenant_site_access(settings, user_row)

    if not membership:
        raise HTTPException(status_code=403, detail="This account does not belong to this website")

    return user_row, membership


@router.post("/sites/{subdomain}/auth/register")
def register_tenant_visitor(
    subdomain: str,
    payload: TenantRegisterRequest,
    request: Request,
):
    clean_subdomain = normalize_subdomain(subdomain)
    settings = resolve_website_settings(clean_subdomain)
    tenant_id = resolve_tenant_id(settings)
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

        service_supabase.table("tenant_site_memberships").insert(
            {
                "tenant_id": tenant_id,
                "user_id": local_user["id"],
                "auth_id": auth_user_id,
                "role": "customer",
                "status": "active",
            }
        ).execute()

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
    settings = resolve_website_settings(clean_subdomain)
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


@router.post("/sites/{subdomain}/auth/logout")
def logout_tenant_visitor(subdomain: str, response: Response):
    normalize_subdomain(subdomain)
    delete_auth_cookies(response)
    return {"logged_in": False, "message": "Logged out"}

@router.get("/sites/{subdomain}")
def get_public_site(subdomain: str, request: Request):
    clean_subdomain = normalize_subdomain(subdomain)
    enforce_public_rate_limit(request, "site_lookup", clean_subdomain)
    settings = resolve_website_settings(clean_subdomain)
    tenant_id = resolve_tenant_id(settings)

    try:
        project = get_latest_published_project_for_tenant(tenant_id)
    except HTTPException as error:
        if error.status_code != 404:
            raise
        project = None

    return {
        "success": True,
        "site": {
            "subdomain": clean_subdomain,
            "brand": settings.get("brand"),
            "footer_store_name": settings.get("footer_store_name"),
            "logo_url": settings.get("logo_url"),
            "contact_email": settings.get("contact_email"),
            "phone": settings.get("phone"),
            "description": settings.get("description"),
        },
        "project": (
            {"published_schema": project.get("published_schema") or {}}
            if project
            else None
        ),
    }


@router.post("/sites/{subdomain}/forms/{form_id}/submissions")
def submit_public_builder_form(
    subdomain: str,
    form_id: str,
    submission: PublicFormSubmissionCreate,
    request: Request,
):
    clean_subdomain = normalize_subdomain(subdomain)
    clean_form_id = (form_id or "").strip()

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

    settings = resolve_website_settings(clean_subdomain)
    tenant_id = resolve_tenant_id(settings)
    project = get_latest_published_project_for_tenant(tenant_id)

    if project.get("status") != "published":
        raise HTTPException(status_code=404, detail="Published site not found")

    published_schema = project.get("published_schema") or {}

    if not isinstance(published_schema, dict):
        raise HTTPException(status_code=404, detail="Published site not found")

    form = find_published_form(published_schema, clean_form_id)

    if not published_page_contains_form_block(published_schema, clean_form_id):
        raise HTTPException(status_code=404, detail="Form not found")

    answers = submission.answers or {}
    validate_public_answer_payload_limits(answers)
    cleaned_answers = validate_form_answers(form, answers)
    fields = get_form_fields(form)
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
    }

    try:
        insert_response = service_supabase.table("builder_form_submissions").insert(payload).execute()
    except Exception as error:
        logger.warning("public.form_submission_failed", extra={"tenant_id": tenant_id, "project_id": project.get("id"), "form_id": clean_form_id, "error_type": type(error).__name__})
        raise HTTPException(status_code=500, detail="Could not submit form")

    saved_submission = first_row(insert_response)

    if not saved_submission:
        raise HTTPException(status_code=500, detail="Could not submit form")

    logger.info(
        "public.form_submission_created",
        extra={
            "tenant_id": tenant_id,
            "project_id": project.get("id"),
            "form_id": clean_form_id,
            "submission_id": saved_submission.get("id"),
        },
    )

    create_builder_block_event_notification(
        tenant_id=tenant_id,
        event_type="builder.form_submitted",
        block_type="form",
        source_id=str(saved_submission.get("id") or clean_form_id),
        title="New form submission",
        body=f"{form.get('title') or 'A published form'} received a new response.",
        data={
            "project_id": project.get("id"),
            "form_id": clean_form_id,
            "form_title": form.get("title"),
            "submission_id": saved_submission.get("id"),
            "subdomain": clean_subdomain,
        },
    )

    return format_submission(saved_submission)


@router.post("/sites/{subdomain}/events")
def submit_public_builder_block_event(
    subdomain: str,
    event: PublicBuilderBlockEventCreate,
    request: Request,
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

    settings = resolve_website_settings(clean_subdomain)
    tenant_id = resolve_tenant_id(settings)
    project = get_latest_published_project_for_tenant(tenant_id)

    if project.get("status") != "published":
        raise HTTPException(status_code=404, detail="Published site not found")

    published_schema = project.get("published_schema") or {}

    if not isinstance(published_schema, dict):
        raise HTTPException(status_code=404, detail="Published site not found")

    block = find_published_block(published_schema, block_id, block_type)

    if not block:
        raise HTTPException(status_code=404, detail="Block not found")

    payload = event.payload or {}
    validate_public_event_payload_limits(payload)
    cleaned_payload = {
        str(key)[:120]: normalize_event_value(value)
        for key, value in payload.items()
    }
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
    )
    reservation_id = str(saved_reservation.get("id") or "")

    if not duplicate:
        create_builder_block_event_notification(
            tenant_id=tenant_id,
            event_type=event_type,
            block_type=block_type,
            source_id=reservation_id or block_id or str(block.get("id") or block_type),
            title=title,
            body=body,
            data={
                "project_id": project.get("id"),
                "block_id": block.get("id"),
                "block_type": block_type,
                "reservation_id": reservation_id,
                "subdomain": clean_subdomain,
                "payload": cleaned_payload,
            },
        )
        customer_email = str(saved_reservation.get("customer_email") or "").strip().lower()
        if block_type == "reservationBlock" and customer_email:
            enqueue_notification(
                channel="email",
                template="reservation_confirmation",
                tenant_id=tenant_id,
                recipient_hash=hash_public_identifier(customer_email),
                recipient_reference=f"reservation:{reservation_id}",
                deduplication_key=hash_public_identifier(
                    f"reservation-confirmation:{reservation_id}"
                ),
                payload={
                    "reservation_id": reservation_id,
                    "status": str(saved_reservation.get("status") or "new"),
                    "site_subdomain": clean_subdomain,
                },
                client=service_supabase,
            )

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
            "cancel_builder_reservation_safe",
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
    customer_email = str(reservation.get("customer_email") or "").strip().lower()
    if customer_email:
        enqueue_notification(
            channel="email",
            template="reservation_status_changed",
            tenant_id=reservation.get("tenant_id"),
            recipient_hash=hash_public_identifier(customer_email),
            recipient_reference=f"reservation:{reservation_id}",
            deduplication_key=hash_public_identifier(
                f"reservation-cancelled:{reservation_id}"
            ),
            payload={"reservation_id": reservation_id, "status": "cancelled"},
            client=service_supabase,
        )
    return {
        "success": True,
        "reservation_id": reservation_id,
        "status": "cancelled",
    }

import json
import re
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from database import service_supabase
from services.rate_limit_service import (
    enforce_public_form_submission_rate_limit,
    enforce_public_rate_limit,
    get_client_ip,
)

router = APIRouter(prefix="/public", tags=["Public Sites"])
logger = logging.getLogger(__name__)

SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
MAX_PUBLIC_FORM_ANSWER_FIELDS = 100
MAX_PUBLIC_FORM_ANSWER_STRING_LENGTH = 5000
MAX_PUBLIC_FORM_ANSWERS_JSON_BYTES = 64 * 1024


class PublicFormSubmissionCreate(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    form_element_id: Optional[str] = None

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("answers must be a JSON object")
        return value


def rows(response):
    return getattr(response, "data", None) or []


def first_row(response):
    result_rows = rows(response)
    return result_rows[0] if result_rows else None


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


def normalize_answer_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [item for item in value if item is None or isinstance(item, (str, int, float, bool))]
    return value


def iter_answer_strings(value):
    if isinstance(value, str):
        yield value
        return

    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                yield item


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

@router.get("/sites/{subdomain}")
def get_public_site(subdomain: str, request: Request):
    clean_subdomain = normalize_subdomain(subdomain)
    enforce_public_rate_limit(request, "site_lookup", clean_subdomain)
    settings = resolve_website_settings(clean_subdomain)
    tenant_id = resolve_tenant_id(settings)

    project = get_latest_published_project_for_tenant(tenant_id)

    return {
        "success": True,
        "site": {
            "subdomain": clean_subdomain,
            "tenant_id": tenant_id,
            "brand": settings.get("brand"),
            "footer_store_name": settings.get("footer_store_name"),
            "logo_url": settings.get("logo_url"),
            "contact_email": settings.get("contact_email"),
            "phone": settings.get("phone"),
            "description": settings.get("description"),
        },
        "project": {
            "id": project.get("id"),
            "name": project.get("name"),
            "slug": project.get("slug"),
            "status": project.get("status"),
            "published_version": project.get("published_version"),
            "last_published_at": project.get("last_published_at"),
            "published_schema": project.get("published_schema") or {},
        },
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

    return format_submission(saved_submission)

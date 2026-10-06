"""Tenant-owned, extensible learning configuration; no learning runtime yet."""
from typing import Literal
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator
from email_validator import validate_email, EmailNotValidError

from database import service_supabase
from services.url_validation import validate_public_url
from services.asset_registry_service import ASSET_URL_PATTERN


def normalize_academy_email_domain(value):
    if not isinstance(value, str):
        raise ValueError("Enter an email domain or example email address")
    candidate = value.strip()
    # Accept a bare domain, @domain shorthand, or a validated example email.
    # Store only the canonical domain; example addresses are never persisted.
    if candidate.startswith("@") and candidate.count("@") == 1:
        candidate = candidate[1:]
    email = candidate if "@" in candidate else f"learner@{candidate}"
    try:
        return validate_email(email, check_deliverability=False).ascii_domain
    except EmailNotValidError as error:
        raise ValueError("Enter a valid domain or example email, such as jack@university.edu") from error


class ELearningSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    academy_registration: Literal["open", "invitation_only", "email_domain"] = "invitation_only"
    academy_email_domains: list[str] = Field(default_factory=list, max_length=20)
    academy_enabled: StrictBool = False
    academy_hero_title: str = Field(default="", max_length=160)
    academy_hero_description: str = Field(default="", max_length=1200)
    academy_hero_image: str = Field(default="", max_length=2048)
    academy_cta_text: str = Field(default="", max_length=80)
    academy_benefits: str = Field(default="", max_length=2000)
    academy_featured_courses: list[UUID] = Field(default_factory=list, max_length=24)

    enabled: StrictBool = False
    platform_name: str = Field(default="Learning Platform", min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    course_label: str = Field(default="Course", min_length=1, max_length=80)
    section_label: str = Field(default="Section", min_length=1, max_length=80)
    lesson_label: str = Field(default="Lesson", min_length=1, max_length=80)
    group_label: str = Field(default="Group", min_length=1, max_length=80)
    instructor_label: str = Field(default="Instructor", min_length=1, max_length=80)
    sequential_progression: StrictBool = False
    allow_locked_content: StrictBool = False
    track_learner_progress: StrictBool = True
    assessments_enabled: StrictBool = False
    default_passing_score: int = Field(default=70, ge=0, le=100, strict=True)
    certificates_enabled: StrictBool = False
    logo_url: str = Field(default="", max_length=2048)
    primary_display_name: str = Field(default="", max_length=120)

    @field_validator("academy_email_domains")
    @classmethod
    def validate_domains(cls, values):
        return list(dict.fromkeys(normalize_academy_email_domain(value) for value in values))

    @model_validator(mode="after")
    def require_email_domains(self):
        if self.academy_registration == "email_domain" and not self.academy_email_domains:
            raise ValueError("Email domain registration requires at least one domain")
        return self

    @field_validator("logo_url", "academy_hero_image")
    @classmethod
    def validate_logo(cls, value):
        if value.startswith("/uploads/"):
            match = ASSET_URL_PATTERN.fullmatch(value)
            if not match or not value.endswith((".png", ".jpg", ".webp")):
                raise ValueError("Platform image must be a managed image")
            return value
        return validate_public_url(value, field_name="Platform image URL")


def settings_available(minimum_schema=117):
    rows = (service_supabase.table("application_schema_state")
            .select("schema_version").eq("contract_key", "core").limit(1).execute()).data or []
    if not rows:
        raise HTTPException(status_code=503, detail="Schema state unavailable")
    return int(rows[0]["schema_version"]) >= minimum_schema


def get_settings(tenant_id):
    rows = (service_supabase.table("elearning_settings").select("settings")
            .eq("tenant_id", tenant_id).limit(1).execute()).data or []
    stored = rows[0]["settings"] if rows else {}
    # Preserve future keys in storage while exposing this version's typed fields.
    known = {key: value for key, value in stored.items() if key in ELearningSettings.model_fields}
    return ELearningSettings(**known).model_dump(mode="json")


def require_owned_image(tenant_id, image_url):
    if image_url.startswith("/uploads/"):
        match = ASSET_URL_PATTERN.fullmatch(image_url)
        if not match or int(match.group("tenant")) != int(tenant_id):
            raise HTTPException(status_code=400, detail="Image must belong to this tenant")
        assets = (service_supabase.table("builder_assets").select("id,status,mime_type")
                  .eq("tenant_id", tenant_id).eq("storage_key", match.group("key"))
                  .limit(1).execute()).data or []
        if not assets or assets[0].get("status") not in {"active", "unreferenced"} or assets[0].get("mime_type") not in {"image/png", "image/jpeg", "image/webp"}:
            raise HTTPException(status_code=400, detail="Image is unavailable")


def save_settings(tenant_id, settings):
    require_owned_image(tenant_id, settings.logo_url)
    require_owned_image(tenant_id, settings.academy_hero_image)
    if settings.academy_enabled and not settings_available(131):
        raise HTTPException(503, detail="Academy requires the database upgrade")
    if settings.academy_featured_courses:
        ids = [str(value) for value in settings.academy_featured_courses]
        rows = (service_supabase.table("elearning_courses").select("id").eq("tenant_id", tenant_id)
                .eq("status", "published").eq("catalog_visible", True).in_("access_type", ["free", "paid"])
                .in_("id", ids).execute()).data or []
        if len({row["id"] for row in rows}) != len(ids):
            raise HTTPException(400, detail="Featured courses must be published catalog courses in this tenant")
    # The RPC merges this version's keys atomically, preserving future settings.
    service_supabase.rpc("save_elearning_settings", {
        "p_tenant_id": tenant_id, "p_settings": settings.model_dump(mode="json"),
    }).execute()
    return settings.model_dump(mode="json")

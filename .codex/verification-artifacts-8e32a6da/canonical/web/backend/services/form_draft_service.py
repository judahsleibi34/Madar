from __future__ import annotations

import hashlib
import hmac
import os
from uuid import UUID


def _draft_secret() -> bytes:
    value = (
        os.getenv("FORM_DRAFT_TOKEN_SECRET")
        or os.getenv("RESERVATION_TOKEN_SECRET")
        or os.getenv("CSRF_SECRET")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SECRET_KEY")
        or "madar-development-form-draft-secret"
    )
    return value.encode("utf-8")


def build_form_draft_token(draft_id: str) -> str:
    normalized_id = str(UUID(str(draft_id)))
    signature = hmac.new(
        _draft_secret(),
        f"form-draft:{normalized_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{normalized_id}.{signature}"


def parse_form_draft_token(token: str) -> str | None:
    try:
        raw_id, supplied_signature = str(token or "").strip().split(".", 1)
        normalized_id = str(UUID(raw_id))
    except (TypeError, ValueError):
        return None

    expected = build_form_draft_token(normalized_id).rsplit(".", 1)[1]
    if not hmac.compare_digest(supplied_signature, expected):
        return None
    return normalized_id

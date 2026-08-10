from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import unquote, urlsplit


logger = logging.getLogger(__name__)

NOTIFICATION_CENTER_PATH = "/notifications"
ACTION_KINDS = {
    "notification_center",
    "reservation",
    "calendar_event",
    "calendar_task",
    "form_submission",
}
MAX_ACTION_PATH_LENGTH = 300
MAX_OBJECT_ID_LENGTH = 200
_OBJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,200}$")


def validate_notification_action_path(path: Any) -> str | None:
    if not isinstance(path, str) or not path or len(path) > MAX_ACTION_PATH_LENGTH:
        return None
    if "\\" in path or any(ord(character) < 32 for character in path):
        return None
    parsed = urlsplit(path)
    if (
        not path.startswith("/")
        or path.startswith("//")
        or parsed.scheme
        or parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.query
    ):
        return None
    decoded_path = unquote(parsed.path)
    if "\\" in decoded_path or decoded_path.startswith("//"):
        return None
    # Current object routes do not carry an authoritative tenant identity.
    # Keep actions in the tenant-scoped inbox until that routing contract exists.
    return NOTIFICATION_CENTER_PATH if decoded_path == NOTIFICATION_CENTER_PATH else None


def build_notification_action(
    *,
    kind: str = "notification_center",
    object_id: Any = None,
    path: str = NOTIFICATION_CENTER_PATH,
) -> dict[str, str]:
    safe_kind = kind if kind in ACTION_KINDS else "notification_center"
    safe_path = validate_notification_action_path(path) or NOTIFICATION_CENTER_PATH
    action = {"kind": safe_kind, "path": safe_path}
    candidate_id = str(object_id or "").strip()
    if candidate_id and _OBJECT_ID_PATTERN.fullmatch(candidate_id):
        action["object_id"] = candidate_id[:MAX_OBJECT_ID_LENGTH]
    return action


def normalize_notification_data(
    data: dict[str, Any] | None,
    *,
    default_kind: str = "notification_center",
    object_id: Any = None,
) -> dict[str, Any]:
    normalized = dict(data) if isinstance(data, dict) else {}
    candidate = normalized.get("action")
    if isinstance(candidate, dict):
        kind = candidate.get("kind")
        path = candidate.get("path")
        candidate_id = candidate.get("object_id", object_id)
        valid = kind in ACTION_KINDS and validate_notification_action_path(path)
        if valid:
            normalized["action"] = build_notification_action(
                kind=str(kind), object_id=candidate_id, path=str(path)
            )
            return normalized
        logger.warning(
            "notifications.action_fallback",
            extra={"action_kind": str(kind or "missing")[:80]},
        )
    normalized["action"] = build_notification_action(
        kind=default_kind,
        object_id=object_id,
    )
    return normalized


def action_kind_for_source(*, event_type: Any, source_type: Any) -> str:
    event_value = str(event_type or "").lower()
    source_value = str(source_type or "").lower()
    if "form" in event_value or source_value == "form":
        return "form_submission"
    if "reservation" in event_value or "reservation" in source_value:
        return "reservation"
    if source_value == "calendar_event" or event_value == "calendar_reminder":
        return "calendar_event"
    if source_value == "calendar_task" or event_value == "calendar_task_reminder":
        return "calendar_task"
    return "notification_center"

"""Private quiz snapshots, public redaction, and server-side grading primitives."""

from __future__ import annotations

import copy
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from services.api_errors import error_detail


FORBIDDEN_PUBLIC_KEYS = frozenset({
    "quizcorrectanswer", "correctanswer", "correct_answer", "answerkey",
    "answer_key", "expectedanswer", "expected_answer", "quizpoints",
    "answerweight", "answer_weight", "rubric", "gradingrubric",
    "grading_rubric", "privategrading", "private_grading",
})
SAFE_QUIZ_SETTINGS = frozenset({
    "lockScreen", "totalTimeLimitSec", "questionTimeLimitSec",
    "showQuestionTimer", "showTotalTimer", "showResults", "allowRetakes",
})
CORRECTABLE_TYPES = frozenset({
    "dropdown", "radio", "status", "yesNo", "linearScale", "rating",
    "checkboxes", "shortText", "paragraph", "email", "phone", "url",
    "number", "money",
})


def redact_public_value(value: Any) -> Any:
    """Deep-copy a publication payload while removing private grading data."""
    if isinstance(value, list):
        return [redact_public_value(item) for item in value]
    if not isinstance(value, dict):
        return copy.deepcopy(value)
    clean: dict[str, Any] = {}
    for key, item in value.items():
        if str(key).replace("-", "_").lower() in FORBIDDEN_PUBLIC_KEYS:
            continue
        if key == "quiz" and isinstance(item, dict):
            clean[key] = {
                safe_key: redact_public_value(safe_value)
                for safe_key, safe_value in item.items()
                if safe_key in SAFE_QUIZ_SETTINGS
            }
            continue
        clean[key] = redact_public_value(item)
    return clean


def public_form(form: dict[str, Any]) -> dict[str, Any]:
    clean = redact_public_value(form)
    clean.pop("responses", None)
    clean.pop("submissions", None)
    return clean


def form_fields(form: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for section in form.get("sections") or []:
        if isinstance(section, dict):
            result.extend(item for item in (section.get("fields") or []) if isinstance(item, dict))
    return result


def is_quiz(form: dict[str, Any]) -> bool:
    return str(form.get("mode") or "").strip().lower() == "quiz"


def normalize_answer(value: Any) -> str:
    return str(value if value is not None else "").strip().lower()


def answer_is_correct(field: dict[str, Any], answer: Any) -> bool | None:
    if field.get("type") not in CORRECTABLE_TYPES or "quizCorrectAnswer" not in field:
        return None
    expected = field.get("quizCorrectAnswer")
    if field.get("type") == "checkboxes":
        wanted = sorted(normalize_answer(item) for item in (expected or []) if normalize_answer(item))
        received = sorted(normalize_answer(item) for item in (answer or []) if normalize_answer(item)) if isinstance(answer, list) else []
        return wanted == received
    expected_values = expected if isinstance(expected, list) else str(expected or "").splitlines()
    return normalize_answer(answer) in {normalize_answer(item) for item in expected_values}


def grade(private_form: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    settings = private_form.get("quiz") if isinstance(private_form.get("quiz"), dict) else {}
    mode = str(settings.get("scoring") or "automatic")
    passing_score = max(0, min(int(settings.get("passingScore") or 0), 100))
    fields = form_fields(private_form)
    if mode == "completion":
        total = len(fields)
        correct = sum(1 for field in fields if answers.get(str(field.get("id") or "")) not in (None, "", []))
    elif mode == "manual":
        return {"mode": "manual", "correct": None, "total": None, "score": None, "passed": None, "passingScore": passing_score}
    else:
        graded = [answer_is_correct(field, answers.get(str(field.get("id") or ""))) for field in fields]
        keyed = [result for result in graded if result is not None]
        total = len(keyed)
        correct = sum(1 for result in keyed if result)
    score = round((correct / total) * 100) if total else None
    return {
        "mode": mode, "correct": correct, "total": total, "score": score,
        "passed": None if score is None else score >= passing_score,
        "passingScore": passing_score,
    }


def question_order(private_form: dict[str, Any]) -> list[str]:
    ids = [str(field.get("id") or "") for field in form_fields(private_form) if field.get("id")]
    order = list(ids)
    settings = private_form.get("quiz") if isinstance(private_form.get("quiz"), dict) else {}
    if settings.get("randomizeQuestions") or settings.get("randomizeQuestionOrder"):
        secrets.SystemRandom().shuffle(order)
    return order


def publication_hash(schema: dict[str, Any]) -> str:
    encoded = json.dumps(schema, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_attempt_payload(*, tenant_id: int, project: dict[str, Any], form: dict[str, Any], subject_hash: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    settings = form.get("quiz") if isinstance(form.get("quiz"), dict) else {}
    duration = max(0, min(int(settings.get("totalTimeLimitSec") or 0), 86400))
    deadline = now + timedelta(seconds=duration) if duration else now + timedelta(hours=24)
    order = question_order(form)
    return {
        "tenant_id": tenant_id,
        "project_id": project.get("id"),
        "form_id": str(form.get("id") or ""),
        "publication_version": int(project.get("published_version") or 0),
        "publication_hash": publication_hash(project.get("published_schema") or {}),
        "subject_hash": subject_hash,
        "state": "active",
        "started_at": now.isoformat(),
        "deadline_at": deadline.isoformat(),
        "question_order": order,
        "private_form_snapshot": copy.deepcopy(form),
    }


def validate_submission_order(attempt: dict[str, Any], answers: dict[str, Any]) -> None:
    allowed = set(attempt.get("question_order") or [])
    unknown = sorted(set(answers) - allowed)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=error_detail("quiz_answer_fields_invalid", "The quiz answer payload is invalid."),
        )

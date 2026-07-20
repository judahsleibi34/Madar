from __future__ import annotations

import json
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone
from typing import Any

from database import service_supabase


class DeliveryError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = True):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


def _rows(response) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return [data]
    return [row for row in (data or []) if isinstance(row, dict)]


def _deliver_internal(row: dict[str, Any]) -> None:
    tenant_id = row.get("tenant_id")
    payload = row.get("payload") or {}
    required = (tenant_id, payload.get("event_type"), payload.get("source_type"), payload.get("title"))
    if not all(required):
        raise DeliveryError("internal_payload_invalid", retryable=False)
    query = (
        service_supabase.table("notification_events")
        .select("*")
        .eq("tenant_id", int(tenant_id))
        .eq("event_type", str(payload["event_type"]))
        .eq("source_type", str(payload["source_type"]))
    )
    source_id = payload.get("source_id")
    query = query.eq("source_id", str(source_id)) if source_id else query.is_("source_id", "null")
    existing = _rows(query.limit(1).execute())
    if existing:
        event = existing[0]
    else:
        inserted = service_supabase.table("notification_events").insert({
            "tenant_id": int(tenant_id),
            "event_type": str(payload["event_type"])[:120],
            "source_type": str(payload["source_type"])[:120],
            "source_id": str(source_id)[:200] if source_id else None,
            "title": str(payload["title"])[:200],
            "body": str(payload.get("body") or "")[:1000],
            "data": payload.get("data") if isinstance(payload.get("data"), dict) else {},
        }).execute()
        rows = _rows(inserted)
        if not rows:
            raise DeliveryError("internal_event_insert_failed")
        event = rows[0]

    recipients = _rows(
        service_supabase.table("tenant_memberships")
        .select("user_id")
        .eq("tenant_id", int(tenant_id))
        .eq("status", "active")
        .execute()
    )
    for recipient in recipients:
        if recipient.get("user_id") is None:
            continue
        service_supabase.table("user_notifications").upsert({
            "event_id": event.get("id"),
            "tenant_id": int(tenant_id),
            "user_id": int(recipient["user_id"]),
            "event_type": str(payload["event_type"])[:120],
            "title": str(payload["title"])[:200],
            "body": str(payload.get("body") or "")[:1000],
            "data": payload.get("data") if isinstance(payload.get("data"), dict) else {},
        }, on_conflict="event_id,user_id").execute()


def _smtp_settings() -> tuple[str, int, str, str, str, bool]:
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        raise DeliveryError("smtp_not_configured")
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError as error:
        raise DeliveryError("smtp_configuration_invalid", retryable=False) from error
    username = os.getenv("SMTP_USERNAME", "").strip()
    sender = os.getenv("SMTP_FROM_EMAIL", username).strip()
    if not sender:
        raise DeliveryError("smtp_configuration_invalid", retryable=False)
    use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes", "on"}
    return host, port, username, os.getenv("SMTP_PASSWORD", ""), sender, use_tls


def _deliver_email(row: dict[str, Any]) -> None:
    reference = str(row.get("recipient_reference") or "")
    if not reference.startswith("reservation:"):
        raise DeliveryError("email_recipient_reference_unsupported", retryable=False)
    reservation_id = reference.removeprefix("reservation:")
    query = service_supabase.table("builder_reservations").select("*").eq("id", reservation_id)
    if row.get("tenant_id") is not None:
        query = query.eq("tenant_id", int(row["tenant_id"]))
    reservations = _rows(query.limit(1).execute())
    if not reservations:
        raise DeliveryError("email_recipient_not_found", retryable=False)
    recipient = str(reservations[0].get("customer_email") or "").strip()
    if not recipient:
        raise DeliveryError("email_recipient_not_found", retryable=False)
    host, port, username, password, sender, use_tls = _smtp_settings()
    template = str(row.get("template") or "")
    payload = row.get("payload") or {}
    if template == "reservation_confirmation":
        subject = "Madar reservation confirmation"
        body = "Your reservation was received."
    elif template == "reservation_status_changed":
        subject = "Madar reservation update"
        body = f"Your reservation status is now: {str(payload.get('status') or 'updated')[:80]}."
    else:
        raise DeliveryError("email_template_unsupported", retryable=False)
    message = EmailMessage()
    message["Subject"], message["From"], message["To"] = subject, sender, recipient
    message.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if use_tls:
                smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise DeliveryError("smtp_delivery_failed") from error


def _deliver_web_push(row: dict[str, Any]) -> None:
    public_key = os.getenv("WEB_PUSH_VAPID_PUBLIC_KEY", "").strip()
    private_key = os.getenv("WEB_PUSH_VAPID_PRIVATE_KEY", "").strip()
    subject = os.getenv("WEB_PUSH_VAPID_SUBJECT", "").strip()
    if not all((public_key, private_key, subject)):
        raise DeliveryError("web_push_not_configured")
    try:
        from pywebpush import WebPushException, webpush
    except ImportError as error:
        raise DeliveryError("web_push_dependency_missing") from error
    query = service_supabase.table("web_push_subscriptions").select("id,endpoint,p256dh,auth").is_("revoked_at", "null")
    if row.get("user_id") is not None:
        query = query.eq("user_id", int(row["user_id"]))
    elif row.get("tenant_id") is not None:
        query = query.eq("tenant_id", int(row["tenant_id"]))
    else:
        raise DeliveryError("web_push_recipient_missing", retryable=False)
    payload = row.get("payload") or {}
    data = json.dumps({
        "title": str(payload.get("title") or "Madar")[:200],
        "body": str(payload.get("body") or "")[:1000],
        "data": payload.get("data") if isinstance(payload.get("data"), dict) else {},
    }, separators=(",", ":"))
    for subscription in _rows(query.execute()):
        try:
            webpush(
                subscription_info={"endpoint": subscription.get("endpoint"), "keys": {"p256dh": subscription.get("p256dh"), "auth": subscription.get("auth")}},
                data=data,
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
            )
        except WebPushException as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            if status in {404, 410}:
                service_supabase.table("web_push_subscriptions").update(
                    {"revoked_at": datetime.now(timezone.utc).isoformat()}
                ).eq("id", subscription.get("id")).execute()
                continue
            raise DeliveryError("web_push_delivery_failed") from error


def deliver_notification(row: dict[str, Any]) -> None:
    channel = str(row.get("channel") or "").lower()
    if channel == "internal":
        _deliver_internal(row)
    elif channel == "email":
        _deliver_email(row)
    elif channel == "web_push":
        _deliver_web_push(row)
    else:
        raise DeliveryError("notification_channel_unsupported", retryable=False)

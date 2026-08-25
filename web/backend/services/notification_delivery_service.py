from __future__ import annotations

import json
import logging
import os
import smtplib
import socket
from email.message import EmailMessage
from datetime import datetime, timezone
from typing import Any

from database import service_supabase
from services.push_subscription_security import (
    UnsafePushEndpoint,
    create_no_redirect_session,
    validate_push_endpoint,
)
from services.notification_action_service import (
    action_kind_for_source,
    normalize_notification_data,
)
from services.notification_preference_service import (
    notification_category,
    preference_enabled,
)


logger = logging.getLogger(__name__)
MAX_WEB_PUSH_PAYLOAD_BYTES = 3500


class DeliveryError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool = True,
        terminal_outcome: str = "dead",
        retry_after_seconds: int | None = None,
    ):
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.terminal_outcome = terminal_outcome
        self.retry_after_seconds = retry_after_seconds


def _rows(response) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return [data]
    return [row for row in (data or []) if isinstance(row, dict)]


def _has_active_membership(tenant_id: int | str, user_id: int | str) -> bool:
    rows = _rows(
        service_supabase.table("tenant_memberships")
        .select("user_id")
        .eq("tenant_id", int(tenant_id))
        .eq("user_id", int(user_id))
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    return bool(rows)


def build_web_push_payload(row: dict[str, Any]) -> str:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    event_type = payload.get("event_type")
    source_type = payload.get("source_type")
    action_data = normalize_notification_data(
        payload.get("data") if isinstance(payload.get("data"), dict) else {},
        default_kind=action_kind_for_source(
            event_type=event_type, source_type=source_type
        ),
        object_id=payload.get("source_id"),
        tenant_id=row.get("tenant_id"),
    )
    kind = action_data["action"]["kind"]
    if kind == "form_submission":
        title, body = "New form submission", "A new form submission was received."
    elif kind == "reservation":
        title, body = "New reservation received", "A new reservation request was received."
    elif kind in {"calendar_event", "calendar_task"}:
        title, body = "Calendar reminder", "Open Madar to view reminder details."
    elif action_data.get("block_type") or str(source_type or "").lower() in {
        "reservationblock",
        "form",
    }:
        title, body = "New site activity", "New activity was received from a published site."
    else:
        title, body = "Madar notification", "Open Madar to view details."

    event_id = str(row.get("event_id") or payload.get("event_id") or "").strip()
    document = {
        "title": title,
        "body": body,
        "event_id": event_id,
        "data": {"action": action_data["action"]},
    }
    if event_id and len(event_id) <= 100:
        document["tag"] = f"madar-event:{event_id}"
    encoded = json.dumps(document, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_WEB_PUSH_PAYLOAD_BYTES:
        fallback = normalize_notification_data(None)
        encoded = json.dumps(
            {
                "title": "Madar notification",
                "body": "Open Madar to view details.",
                "data": {"action": fallback["action"]},
            },
            separators=(",", ":"),
        )
    return encoded


def _deliver_internal(row: dict[str, Any]) -> None:
    tenant_id = row.get("tenant_id")
    payload = row.get("payload") or {}
    required = (tenant_id, payload.get("event_type"), payload.get("source_type"), payload.get("title"))
    if not all(required):
        raise DeliveryError("internal_payload_invalid", retryable=False)
    source_id = payload.get("source_id")
    canonical_payload_data = normalize_notification_data(
        payload.get("data") if isinstance(payload.get("data"), dict) else {},
        default_kind=action_kind_for_source(
            event_type=payload.get("event_type"),
            source_type=payload.get("source_type"),
        ),
        object_id=source_id,
        tenant_id=tenant_id,
    )
    event_id = row.get("event_id") or payload.get("event_id")
    if event_id:
        existing = _rows(
            service_supabase.table("notification_events")
            .select("*")
            .eq("id", str(event_id))
            .eq("tenant_id", int(tenant_id))
            .limit(1)
            .execute()
        )
        if not existing:
            raise DeliveryError("internal_event_not_found", retryable=False)
        event = existing[0]
    else:
        deduplication_key = str(
            payload.get("event_deduplication_key")
            or row.get("deduplication_key")
            or f"outbox:{row.get('outbox_id') or row.get('id')}"
        )[:240]
        rpc = getattr(service_supabase, "rpc", None)
        if callable(rpc):
            response = rpc(
                "get_or_create_notification_event",
                {
                    "p_tenant_id": int(tenant_id),
                    "p_event_type": str(payload["event_type"])[:120],
                    "p_source_type": str(payload["source_type"])[:120],
                    "p_source_id": str(source_id)[:200] if source_id else None,
                    "p_title": str(payload["title"])[:200],
                    "p_body": str(payload.get("body") or "")[:1000],
                    "p_data": canonical_payload_data,
                    "p_deduplication_key": deduplication_key,
                },
            ).execute()
            rows = _rows(response)
            if not rows:
                raise DeliveryError("internal_event_insert_failed")
            event = rows[0]
        else:
            # Unit-test clients do not expose RPC. Production event creation is
            # protected by the database uniqueness constraint above.
            inserted = service_supabase.table("notification_events").insert({
                "tenant_id": int(tenant_id),
                "event_type": str(payload["event_type"])[:120],
                "source_type": str(payload["source_type"])[:120],
                "source_id": str(source_id)[:200] if source_id else None,
                "title": str(payload["title"])[:200],
                "body": str(payload.get("body") or "")[:1000],
                "data": canonical_payload_data,
                "deduplication_key": deduplication_key,
            }).execute()
            rows = _rows(inserted)
            if not rows:
                raise DeliveryError("internal_event_insert_failed")
            event = rows[0]

    recipient_query = (
        service_supabase.table("tenant_memberships")
        .select("user_id")
        .eq("tenant_id", int(tenant_id))
        .eq("status", "active")
    )
    if row.get("user_id") is not None:
        recipient_query = recipient_query.eq("user_id", int(row["user_id"]))
    recipients = _rows(recipient_query.execute())
    if row.get("user_id") is not None and not recipients:
        logger.warning(
            "notifications.delivery_skipped_inactive_member",
            extra={
                "tenant_id": tenant_id,
                "user_id": row.get("user_id"),
                "channel": "internal",
            },
        )
        raise DeliveryError("recipient_inactive", retryable=False)
    event_data = normalize_notification_data(
        event.get("data") if isinstance(event.get("data"), dict) else canonical_payload_data,
        default_kind=action_kind_for_source(
            event_type=event.get("event_type") or payload.get("event_type"),
            source_type=event.get("source_type") or payload.get("source_type"),
        ),
        object_id=event.get("source_id") or source_id,
        tenant_id=tenant_id,
    )
    for recipient in recipients:
        if recipient.get("user_id") is None:
            continue
        category = notification_category(
            event_type=event.get("event_type") or payload.get("event_type"),
            source_type=event.get("source_type") or payload.get("source_type"),
        )
        if not preference_enabled(
            tenant_id=tenant_id,
            user_id=recipient["user_id"],
            category=category,
            channel="in_app",
        ):
            logger.info(
                "notifications.delivery_skipped_preference",
                extra={"tenant_id": tenant_id, "user_id": recipient["user_id"], "channel": "internal", "category": category},
            )
            continue
        service_supabase.table("user_notifications").upsert({
            "event_id": event.get("id"),
            "tenant_id": int(tenant_id),
            "user_id": int(recipient["user_id"]),
            "event_type": str(event.get("event_type") or payload["event_type"])[:120],
            "title": str(event.get("title") or payload["title"])[:200],
            "body": str(event.get("body") or payload.get("body") or "")[:1000],
            "data": event_data,
        }, on_conflict="event_id,user_id").execute()


def _smtp_settings() -> tuple[str, int, str, str, str, bool]:
    enabled = os.getenv("EMAIL_CHANNEL_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        raise DeliveryError(
            "email_channel_disabled",
            retryable=False,
            terminal_outcome="revoked",
        )
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        raise DeliveryError("smtp_not_configured", retryable=False)
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
    if reference.startswith("reservation:"):
        reservation_id = reference.removeprefix("reservation:")
        query = service_supabase.table("builder_reservations").select("*").eq("id", reservation_id)
        if row.get("tenant_id") is not None:
            query = query.eq("tenant_id", int(row["tenant_id"]))
        reservations = _rows(query.limit(1).execute())
        recipient = str(reservations[0].get("customer_email") if reservations else "").strip()
    elif reference.startswith("user:"):
        user_id = reference.removeprefix("user:")
        if row.get("tenant_id") is not None and not _has_active_membership(
            row["tenant_id"], user_id
        ):
            logger.warning(
                "notifications.delivery_skipped_inactive_member",
                extra={"tenant_id": row.get("tenant_id"), "user_id": user_id, "channel": "email"},
            )
            raise DeliveryError("recipient_inactive", retryable=False)
        users = _rows(service_supabase.table("users").select("email").eq("id", user_id).limit(1).execute())
        recipient = str(users[0].get("email") if users else "").strip()
        payload = row.get("payload") or {}
        category = notification_category(
            event_type=payload.get("event_type"), source_type=payload.get("source_type")
        )
        if not preference_enabled(
            tenant_id=row.get("tenant_id"), user_id=user_id, category=category, channel="email"
        ):
            raise DeliveryError("email_preference_disabled", retryable=False, terminal_outcome="revoked")
    else:
        raise DeliveryError("email_recipient_reference_unsupported", retryable=False)
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
    elif template == "calendar_reminder":
        subject = str(payload.get("title") or "Madar calendar reminder")[:200]
        body = str(payload.get("body") or "An event is starting soon.")[:2000]
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
    except smtplib.SMTPRecipientsRefused as error:
        raise DeliveryError("smtp_recipient_rejected", retryable=False) from error
    except smtplib.SMTPResponseException as error:
        retryable = 400 <= int(error.smtp_code or 0) < 500
        raise DeliveryError("smtp_provider_rejected", retryable=retryable) from error
    except (OSError, socket.timeout, smtplib.SMTPException) as error:
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
    tenant_id = row.get("tenant_id")
    target_user_id = row.get("user_id")
    subscription_id = row.get("subscription_id")
    if target_user_id is None:
        raise DeliveryError("web_push_recipient_missing", retryable=False)
    if not subscription_id:
        raise DeliveryError("web_push_subscription_missing", retryable=False)
    if tenant_id is not None:
        recipient_ids = [int(target_user_id)] if _has_active_membership(
            tenant_id, target_user_id
        ) else []
        if not recipient_ids:
            logger.warning(
                "notifications.delivery_skipped_inactive_member",
                extra={"tenant_id": tenant_id, "user_id": target_user_id, "channel": "web_push"},
            )
            raise DeliveryError("recipient_inactive", retryable=False)
    else:
        recipient_ids = [int(target_user_id)]
    data = build_web_push_payload(row)
    recipient_id = recipient_ids[0]
    payload = row.get("payload") or {}
    category = notification_category(
        event_type=payload.get("event_type"), source_type=payload.get("source_type")
    )
    if not preference_enabled(
        tenant_id=tenant_id, user_id=recipient_id, category=category, channel="push"
    ):
        raise DeliveryError("web_push_preference_disabled", retryable=False, terminal_outcome="revoked")
    query = (
        service_supabase.table("web_push_subscriptions")
        .select("id,endpoint,p256dh,auth,app_installation_id")
        .eq("id", str(subscription_id))
        .eq("user_id", recipient_id)
        .is_("revoked_at", "null")
    )
    if tenant_id is not None:
        query = query.eq("tenant_id", int(tenant_id))
    subscriptions = _rows(query.limit(1).execute())
    if not subscriptions:
        raise DeliveryError(
            "web_push_subscription_revoked", retryable=False, terminal_outcome="revoked"
        )
    subscription = subscriptions[0]
    app_installation_id = subscription.get("app_installation_id")
    if app_installation_id:
        installations = _rows(
            service_supabase.table("app_installations")
            .select("id")
            .eq("id", str(app_installation_id))
            .eq("user_id", recipient_id)
            .eq("notifications_enabled", True)
            .eq("notification_permission", "granted")
            .is_("revoked_at", "null")
            .limit(1)
            .execute()
        )
        if not installations:
            logger.warning(
                "notifications.delivery_skipped_inactive_installation",
                extra={
                    "tenant_id": tenant_id,
                    "user_id": recipient_id,
                    "subscription_id": subscription.get("id"),
                },
            )
            raise DeliveryError(
                "web_push_installation_inactive",
                retryable=False,
                terminal_outcome="revoked",
            )
    try:
        safe_endpoint = validate_push_endpoint(str(subscription.get("endpoint") or ""))
    except UnsafePushEndpoint as error:
        service_supabase.table("web_push_subscriptions").update(
            {"revoked_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", subscription.get("id")).execute()
        logger.warning(
            "notifications.web_push_endpoint_rejected",
            extra={"subscription_id": subscription.get("id"), "error_code": str(error)},
        )
        raise DeliveryError(
            "web_push_endpoint_unsafe", retryable=False, terminal_outcome="revoked"
        ) from error
    if tenant_id is not None and not _has_active_membership(tenant_id, recipient_id):
        logger.warning(
            "notifications.delivery_skipped_inactive_member",
            extra={"tenant_id": tenant_id, "user_id": recipient_id, "channel": "web_push"},
        )
        raise DeliveryError("recipient_inactive", retryable=False)
    try:
        webpush(
            subscription_info={"endpoint": safe_endpoint, "keys": {"p256dh": subscription.get("p256dh"), "auth": subscription.get("auth")}},
            data=data,
            vapid_private_key=private_key,
            vapid_claims={"sub": subject},
            requests_session=create_no_redirect_session(),
        )
    except WebPushException as error:
        status = getattr(getattr(error, "response", None), "status_code", None)
        if status in {404, 410}:
            service_supabase.table("web_push_subscriptions").update(
                {"revoked_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", subscription.get("id")).execute()
            raise DeliveryError(
                "web_push_subscription_revoked",
                retryable=False,
                terminal_outcome="revoked",
            ) from error
        if status is not None and int(status) == 429:
            retry_after = getattr(getattr(error, "response", None), "headers", {}).get(
                "Retry-After"
            )
            try:
                retry_after_seconds = max(1, min(int(retry_after), 86400))
            except (TypeError, ValueError):
                retry_after_seconds = None
            raise DeliveryError(
                "web_push_rate_limited",
                retry_after_seconds=retry_after_seconds,
            ) from error
        if status is not None and 400 <= int(status) < 500:
            raise DeliveryError("web_push_provider_rejected", retryable=False) from error
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

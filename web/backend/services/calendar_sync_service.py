from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote, urlencode, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from cryptography.fernet import Fernet, InvalidToken

from database import service_supabase


class CalendarSyncError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


MAX_SYNC_PAGES = 20
MAX_SYNC_EVENTS = 5000
SYNC_OPERATION_BUDGET_SECONDS = 90


def _secret() -> bytes:
    value = os.getenv("CALENDAR_CREDENTIALS_SECRET", "").strip()
    if _environment_name() not in {"prod", "production"}:
        value = value or os.getenv("SECRET_KEY", "").strip() or os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if len(value) < 24:
        raise CalendarSyncError("calendar_secret_missing", "Calendar credential encryption is not configured.")
    return value.encode()


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(_secret()).digest()))


def encrypt_credentials(credentials: dict[str, Any]) -> str:
    return _fernet().encrypt(json.dumps(credentials, separators=(",", ":")).encode()).decode()


def decrypt_credentials(value: str) -> dict[str, Any]:
    try:
        decoded = json.loads(_fernet().decrypt(str(value).encode()).decode())
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError) as error:
        raise CalendarSyncError("calendar_credentials_invalid", "Calendar credentials must be reconnected.") from error
    if not isinstance(decoded, dict):
        raise CalendarSyncError("calendar_credentials_invalid", "Calendar credentials must be reconnected.")
    return decoded


def _encode_state(payload: dict[str, Any]) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(hmac.new(_secret(), body.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    return f"{body}.{signature}"


def decode_oauth_state(value: str) -> dict[str, Any]:
    try:
        if not value or len(value) > 8192:
            raise ValueError("length")
        body, supplied = value.split(".", 1)
        expected = base64.urlsafe_b64encode(hmac.new(_secret(), body.encode(), hashlib.sha256).digest()).decode().rstrip("=")
        if not hmac.compare_digest(supplied, expected):
            raise ValueError("signature")
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        now = int(time.time())
        if int(payload.get("exp") or 0) < now:
            raise ValueError("expired")
        if int(payload.get("iat") or 0) > now + 60:
            raise ValueError("issued_in_future")
        required = {"connection_id", "calendar_id", "tenant_id", "user_id", "provider", "destination", "nonce", "iat", "exp"}
        if not required.issubset(payload):
            raise ValueError("incomplete")
        if payload.get("destination") != "calendar":
            raise ValueError("destination")
        return payload
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise CalendarSyncError("oauth_state_invalid", "Calendar connection state is invalid or expired.") from error


def _environment_name() -> str:
    return (os.getenv("APP_ENV") or "development").strip().lower()


def _configured_base_url(name: str, development_default: str) -> str:
    value = os.getenv(name, "").strip() or development_default
    parsed = urlparse(value)
    production = _environment_name() in {"prod", "production"}
    if not parsed.scheme or not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise CalendarSyncError("oauth_url_invalid", f"{name} must be an exact origin.")
    if production and (parsed.scheme != "https" or parsed.hostname in {"localhost", "127.0.0.1", "::1"}):
        raise CalendarSyncError("oauth_url_invalid", f"{name} must be an HTTPS production origin.")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _redirect_uri(provider: str) -> str:
    public_api = _configured_base_url("PUBLIC_API_URL", "http://localhost:8000")
    return f"{public_api}/calendar/oauth/{provider}/callback"


def frontend_calendar_url(*, status: str) -> str:
    frontend = _configured_base_url("FRONTEND_PRIMARY_URL", "http://localhost:5173")
    safe_status = status if status in {"connected", "error", "disconnected"} else "error"
    return f"{frontend}/calendar?sync={safe_status}"


def _provider_settings(provider: str) -> tuple[str, str]:
    prefix = "GOOGLE_CALENDAR" if provider == "google" else "MICROSOFT_CALENDAR"
    client_id = os.getenv(f"{prefix}_CLIENT_ID", "").strip()
    client_secret = os.getenv(f"{prefix}_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise CalendarSyncError("provider_credentials_missing", f"{provider.title()} Calendar credentials are not configured.")
    return client_id, client_secret


def authorization_url(
    connection: dict[str, Any],
    *,
    client=None,
    now: int | None = None,
    direction_override: str | None = None,
) -> str:
    provider = str(connection.get("provider") or "")
    if provider not in {"google", "microsoft"}:
        raise CalendarSyncError("provider_oauth_unsupported", "This provider does not use OAuth authorization.")
    client_id, _ = _provider_settings(provider)
    issued_at = int(now if now is not None else time.time())
    nonce = secrets.token_urlsafe(32)
    direction = str(direction_override or connection.get("direction") or "read")
    if direction not in {"read", "two_way"}:
        raise CalendarSyncError("oauth_direction_invalid", "Calendar access mode is invalid.")
    state_payload = {
        "connection_id": connection["id"],
        "calendar_id": connection["local_calendar_id"],
        "tenant_id": connection["tenant_id"],
        "user_id": connection["user_id"],
        "provider": provider,
        "direction": direction,
        "destination": "calendar",
        "nonce": nonce,
        "iat": issued_at,
        "exp": issued_at + 600,
    }
    database_client = client or service_supabase
    database_client.table("calendar_oauth_states").insert({
        "nonce_hash": hashlib.sha256(nonce.encode()).hexdigest(),
        "connection_id": connection["id"],
        "tenant_id": connection["tenant_id"],
        "user_id": connection["user_id"],
        "calendar_id": connection["local_calendar_id"],
        "provider": provider,
        "expires_at": datetime.fromtimestamp(state_payload["exp"], tz=timezone.utc).isoformat(),
    }).execute()
    state = _encode_state(state_payload)
    if provider == "google":
        scope = "https://www.googleapis.com/auth/calendar.readonly" if direction == "read" else "https://www.googleapis.com/auth/calendar.events"
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
            "client_id": client_id, "redirect_uri": _redirect_uri(provider), "response_type": "code",
            "scope": scope, "access_type": "offline", "include_granted_scopes": "true",
            "prompt": "consent", "state": state,
        })
    scope = "Calendars.Read" if direction == "read" else "Calendars.ReadWrite"
    return "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?" + urlencode({
        "client_id": client_id, "redirect_uri": _redirect_uri(provider), "response_type": "code",
        "response_mode": "query", "scope": f"offline_access {scope}", "state": state,
    })


def consume_oauth_state(payload: dict[str, Any], *, client=None) -> None:
    database_client = client or service_supabase
    response = database_client.rpc("consume_calendar_oauth_state", {
        "target_nonce_hash": hashlib.sha256(str(payload["nonce"]).encode()).hexdigest(),
        "target_connection_id": payload["connection_id"],
        "target_tenant_id": int(payload["tenant_id"]),
        "target_user_id": int(payload["user_id"]),
        "target_calendar_id": payload["calendar_id"],
        "target_provider": payload["provider"],
    }).execute()
    if getattr(response, "data", None) is not True:
        raise CalendarSyncError("oauth_state_replayed", "Calendar connection state is invalid or already used.")


def _safe_credentials(credentials: dict[str, Any], previous: dict[str, Any] | None = None) -> dict[str, Any]:
    previous = previous or {}
    access_token = str(credentials.get("access_token") or "")
    if not access_token:
        raise CalendarSyncError("oauth_token_invalid", "The provider returned an invalid token response.")
    try:
        expires_in = max(60, min(int(credentials.get("expires_in") or 3600), 31_536_000))
    except (TypeError, ValueError) as error:
        raise CalendarSyncError("oauth_token_invalid", "The provider returned an invalid token response.") from error
    return {
        "access_token": access_token,
        "refresh_token": str(credentials.get("refresh_token") or previous.get("refresh_token") or ""),
        "token_type": str(credentials.get("token_type") or "Bearer")[:40],
        "scope": str(credentials.get("scope") or previous.get("scope") or "")[:2000],
        "expires_at": int(time.time()) + expires_in,
    }


def credentials_allow_direction(
    provider: str, credentials: dict[str, Any], direction: str
) -> bool:
    if direction == "read":
        return True
    scopes = {scope.lower() for scope in str(credentials.get("scope") or "").split()}
    if provider == "google":
        return bool(scopes & {
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/calendar.events",
        })
    if provider == "microsoft":
        return "calendars.readwrite" in scopes
    return False


def exchange_authorization_code(
    provider: str,
    code: str,
    *,
    http_client=None,
    previous_credentials: dict[str, Any] | None = None,
) -> dict[str, Any]:
    client_id, client_secret = _provider_settings(provider)
    endpoint = "https://oauth2.googleapis.com/token" if provider == "google" else "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    data = {
        "client_id": client_id, "client_secret": client_secret, "code": code,
        "redirect_uri": _redirect_uri(provider), "grant_type": "authorization_code",
    }
    client = http_client or httpx.Client(timeout=20)
    response = client.post(endpoint, data=data)
    if response.status_code >= 400:
        raise CalendarSyncError("oauth_exchange_failed", "The provider did not accept the authorization code.")
    try:
        credentials = response.json()
    except (ValueError, TypeError) as error:
        raise CalendarSyncError("oauth_token_invalid", "The provider returned an invalid token response.") from error
    return _safe_credentials(credentials, previous_credentials)


def _refresh(provider: str, credentials: dict[str, Any], client) -> dict[str, Any]:
    if int(credentials.get("expires_at") or 0) > int(time.time()) + 60:
        return credentials
    refresh_token = credentials.get("refresh_token")
    if not refresh_token:
        raise CalendarSyncError("refresh_token_missing", "Reconnect the calendar to continue syncing.")
    client_id, client_secret = _provider_settings(provider)
    endpoint = "https://oauth2.googleapis.com/token" if provider == "google" else "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    response = client.post(endpoint, data={"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"})
    if response.status_code >= 400:
        raise CalendarSyncError("token_refresh_failed", "The provider access token could not be refreshed.")
    try:
        refreshed = response.json()
    except (ValueError, TypeError) as error:
        raise CalendarSyncError("oauth_token_invalid", "The provider returned an invalid token response.") from error
    return _safe_credentials(refreshed, credentials)


def disconnect_connection(connection: dict[str, Any], *, http_client=None, client=None) -> bool:
    database_client = client or service_supabase
    provider = str(connection.get("provider") or "")
    revoked = False
    if provider == "google" and connection.get("encrypted_credentials"):
        try:
            credentials = decrypt_credentials(connection["encrypted_credentials"])
            token = credentials.get("refresh_token") or credentials.get("access_token")
            if token:
                provider_client = http_client or httpx.Client(timeout=10)
                response = provider_client.post(
                    "https://oauth2.googleapis.com/revoke",
                    data={"token": token},
                )
                revoked = response.status_code in {200, 204, 400}
        except (CalendarSyncError, httpx.HTTPError):
            revoked = False
    database_client.table("calendar_sync_connections").update({
        "status": "disconnected",
        "encrypted_credentials": None,
        "cursor_data": {},
        "last_error_code": None,
    }).eq("id", connection["id"]).eq("tenant_id", connection["tenant_id"]).execute()
    return revoked


def delete_provider_event(
    connection: dict[str, Any],
    event: dict[str, Any],
    *,
    http_client=None,
    client=None,
) -> None:
    provider = str(connection.get("provider") or "")
    if provider not in {"google", "microsoft"}:
        raise CalendarSyncError(
            "provider_sync_unsupported", "This provider does not support remote event deletion."
        )
    if connection.get("direction") != "two_way":
        raise CalendarSyncError(
            "calendar_write_access_required",
            "Reconnect this calendar with read/write access before deleting its provider event.",
        )
    if not connection.get("encrypted_credentials"):
        raise CalendarSyncError(
            "connection_setup_incomplete", "Finish provider authorization before syncing."
        )
    source_id = str(event.get("source_id") or "")
    prefix = f"{connection['id']}:"
    if str(event.get("source_type") or "") != provider or not source_id.startswith(prefix):
        raise CalendarSyncError(
            "provider_event_binding_invalid", "The synchronized provider event link is invalid."
        )
    remote_id = source_id[len(prefix):]
    if not remote_id:
        raise CalendarSyncError(
            "provider_event_binding_invalid", "The synchronized provider event link is invalid."
        )
    provider_client = http_client or httpx.Client(timeout=20)
    credentials = _refresh(
        provider, decrypt_credentials(connection["encrypted_credentials"]), provider_client
    )
    headers = {"Authorization": f"Bearer {credentials['access_token']}"}
    if provider == "google":
        provider_calendar_id = quote(
            str(connection.get("provider_calendar_id") or "primary"), safe=""
        )
        url = (
            "https://www.googleapis.com/calendar/v3/calendars/"
            f"{provider_calendar_id}/events/"
            f"{quote(remote_id, safe='')}"
        )
    else:
        url = f"https://graph.microsoft.com/v1.0/me/events/{quote(remote_id, safe='')}"
    result = provider_client.delete(url, headers=headers)
    if result.status_code not in {204, 404, 410}:
        raise CalendarSyncError(
            "provider_event_delete_failed", "The provider event could not be deleted."
        )
    database_client = client or service_supabase
    database_client.table("calendar_sync_connections").update({
        "encrypted_credentials": encrypt_credentials(credentials),
        "last_error_code": None,
    }).eq("id", connection["id"]).eq("tenant_id", connection["tenant_id"]).execute()


def _parse_provider_time(value: Any, timezone_name: str | None = None) -> datetime:
    if isinstance(value, dict):
        timezone_name = value.get("timeZone") or timezone_name
        value = value.get("dateTime") or value.get("date")
    raw = str(value or "")
    if len(raw) == 10:
        return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name or "UTC"))
        except ZoneInfoNotFoundError:
            parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _upsert_external_event(connection: dict[str, Any], remote: dict[str, Any], provider: str, client) -> str:
    if not isinstance(remote, dict):
        return "ignored"
    remote_id = str(remote.get("id") or "")
    if not remote_id:
        return "ignored"
    source_key = f"{connection['id']}:{remote_id}"
    existing_rows = getattr(
        service_supabase.table("calendar_events").select("*")
        .eq("tenant_id", connection["tenant_id"]).eq("source_type", provider).eq("source_id", source_key).limit(1).execute(),
        "data", None,
    ) or []
    existing = existing_rows[0] if existing_rows else None
    removed = bool(remote.get("@removed")) or remote.get("status") == "cancelled" or remote.get("isCancelled") is True
    if removed:
        if existing and not existing.get("deleted_at"):
            service_supabase.table("calendar_events").update({"deleted_at": datetime.now(timezone.utc).isoformat(), "last_synced_at": datetime.now(timezone.utc).isoformat(), "version": int(existing.get("version") or 1) + 1}).eq("id", existing["id"]).execute()
            return "deleted"
        return "ignored"
    start_value = remote.get("start")
    end_value = remote.get("end")
    try:
        start = _parse_provider_time(start_value, (start_value or {}).get("timeZone") if isinstance(start_value, dict) else None)
        end = _parse_provider_time(end_value, (end_value or {}).get("timeZone") if isinstance(end_value, dict) else None)
    except (TypeError, ValueError, OverflowError):
        return "ignored"
    if end <= start:
        return "ignored"
    etag = str(remote.get("etag") or remote.get("@odata.etag") or remote.get("changeKey") or "")
    last_synced = datetime.fromisoformat(str(existing.get("last_synced_at")).replace("Z", "+00:00")) if existing and existing.get("last_synced_at") else None
    updated_at = datetime.fromisoformat(str(existing.get("updated_at")).replace("Z", "+00:00")) if existing and existing.get("updated_at") else None
    if (
        existing
        and existing.get("external_etag") != etag
        and last_synced
        and updated_at
        and updated_at > last_synced + timedelta(seconds=1)
    ):
        service_supabase.table("calendar_sync_conflicts").insert({
            "tenant_id": connection["tenant_id"], "connection_id": connection["id"], "event_id": existing["id"],
            "external_event_id": remote_id,
            "local_data": {
                key: existing.get(key) for key in
                ("id", "calendar_id", "title", "description", "location", "starts_at", "ends_at", "timezone", "version")
            },
            "remote_data": {
                "id": remote_id,
                "summary": remote.get("summary"),
                "subject": remote.get("subject"),
                "description": str(remote.get("description") or "")[:20000],
                "start": remote.get("start"),
                "end": remote.get("end"),
                "location": remote.get("location"),
            },
            "status": "unresolved",
        }).execute()
        return "conflict"
    timezone_name = ((start_value or {}).get("timeZone") if isinstance(start_value, dict) else None) or "UTC"
    recurrence = remote.get("recurrence") or []
    recurrence_rule = next(
        (
            str(value)[6:]
            for value in recurrence
            if str(value).startswith("RRULE:")
        ),
        None,
    )
    all_day = bool(
        remote.get("allDay")
        or remote.get("isAllDay")
        or (
            isinstance(start_value, dict)
            and bool(start_value.get("date"))
            and not start_value.get("dateTime")
        )
    )
    values = {
        "tenant_id": connection["tenant_id"], "calendar_id": connection["local_calendar_id"], "created_by": connection["user_id"],
        "title": str(remote.get("summary") or remote.get("subject") or "Untitled event")[:240],
        "description": str(remote.get("description") or ((remote.get("body") or {}).get("content") if isinstance(remote.get("body"), dict) else ""))[:20000],
        "location": str(((remote.get("location") or {}).get("displayName") if isinstance(remote.get("location"), dict) else remote.get("location")) or "")[:500],
        "starts_at": start.isoformat(), "ends_at": end.isoformat(), "timezone": timezone_name,
        "all_day": all_day, "status": "confirmed",
        "visibility": "private" if remote.get("visibility") == "private" or remote.get("sensitivity") == "private" else "calendar_default",
        "transparency": "free" if remote.get("transparency") == "transparent" or remote.get("showAs") == "free" else "busy",
        "source_type": provider, "source_id": source_key, "external_etag": etag,
        "last_synced_at": datetime.now(timezone.utc).isoformat(), "deleted_at": None,
        "recurrence_rule": recurrence_rule,
    }
    if existing:
        values["version"] = int(existing.get("version") or 1) + 1
        service_supabase.table("calendar_events").update(values).eq("id", existing["id"]).execute()
        _sync_google_attendees(connection, existing["id"], remote)
        return "updated"
    created = getattr(
        service_supabase.table("calendar_events").insert(values).execute(),
        "data",
        None,
    ) or []
    if created:
        _sync_google_attendees(connection, created[0]["id"], remote)
    return "created"


def _sync_google_attendees(
    connection: dict[str, Any], event_id: str, remote: dict[str, Any]
) -> None:
    attendees = remote.get("attendees")
    if not isinstance(attendees, list):
        return
    service_supabase.table("calendar_event_attendees").delete().eq(
        "event_id", event_id
    ).eq("tenant_id", connection["tenant_id"]).execute()
    rows = []
    allowed_statuses = {
        "needsAction": "needs_action",
        "accepted": "accepted",
        "declined": "declined",
        "tentative": "tentative",
    }
    for attendee in attendees[:500]:
        if not isinstance(attendee, dict):
            continue
        email = str(attendee.get("email") or "").strip().lower()
        if not email or len(email) > 320:
            continue
        rows.append(
            {
                "event_id": event_id,
                "tenant_id": connection["tenant_id"],
                "email": email,
                "display_name": str(attendee.get("displayName") or "")[:240],
                "response_status": allowed_statuses.get(
                    str(attendee.get("responseStatus") or ""), "needs_action"
                ),
                "is_organizer": bool(attendee.get("organizer")),
                "is_external": True,
            }
        )
    if rows:
        service_supabase.table("calendar_event_attendees").insert(rows).execute()


def _google_sync(connection: dict[str, Any], credentials: dict[str, Any], client) -> tuple[dict[str, int], dict[str, Any]]:
    cursor = dict(connection.get("cursor_data") or {})
    params: dict[str, Any] = {"maxResults": 250, "singleEvents": "true", "showDeleted": "true"}
    if cursor.get("sync_token"):
        params["syncToken"] = cursor["sync_token"]
    else:
        params["timeMin"] = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    provider_calendar_id = quote(
        str(connection.get("provider_calendar_id") or "primary"), safe=""
    )
    url = (
        "https://www.googleapis.com/calendar/v3/calendars/"
        f"{provider_calendar_id}/events"
    )
    counts = {"created": 0, "updated": 0, "deleted": 0, "conflict": 0, "ignored": 0}
    pages = 0
    total_events = 0
    started = time.monotonic()
    while url:
        if time.monotonic() - started > SYNC_OPERATION_BUDGET_SECONDS:
            raise CalendarSyncError(
                "sync_time_budget_exceeded",
                "Calendar synchronization exceeded its time budget.",
            )
        pages += 1
        if pages > MAX_SYNC_PAGES:
            raise CalendarSyncError("sync_page_limit", "Calendar synchronization exceeded its page limit.")
        response = client.get(url, params=params, headers={"Authorization": f"Bearer {credentials['access_token']}"})
        if response.status_code == 410 and cursor.get("sync_token"):
            cursor.pop("sync_token", None)
            return _google_sync({**connection, "cursor_data": cursor}, credentials, client)
        if response.status_code == 429:
            raise CalendarSyncError(
                "provider_rate_limited", "Calendar provider is busy."
            )
        if response.status_code in {500, 502, 503, 504}:
            raise CalendarSyncError(
                "provider_unavailable", "Calendar provider is unavailable."
            )
        if response.status_code in {401, 403}:
            raise CalendarSyncError(
                "provider_authorization_failed",
                "Reconnect the calendar account before synchronizing.",
            )
        if response.status_code >= 400:
            raise CalendarSyncError("google_sync_failed", "Google Calendar synchronization failed.")
        data = response.json()
        items = data.get("items") or []
        total_events += len(items)
        if total_events > MAX_SYNC_EVENTS:
            raise CalendarSyncError(
                "sync_event_limit",
                "Calendar synchronization exceeded its event limit.",
            )
        for remote in items:
            counts[_upsert_external_event(connection, remote, "google", client)] += 1
        page_token = data.get("nextPageToken")
        if page_token:
            params["pageToken"] = page_token
        else:
            cursor["sync_token"] = data.get("nextSyncToken") or cursor.get("sync_token")
            url = ""
    return counts, cursor


def _microsoft_sync(connection: dict[str, Any], credentials: dict[str, Any], client) -> tuple[dict[str, int], dict[str, Any]]:
    cursor = dict(connection.get("cursor_data") or {})
    now = datetime.now(timezone.utc)
    url = cursor.get("delta_link") or ("https://graph.microsoft.com/v1.0/me/calendarView/delta?" + urlencode({"startDateTime": (now - timedelta(days=365)).isoformat(), "endDateTime": (now + timedelta(days=730)).isoformat()}))
    counts = {"created": 0, "updated": 0, "deleted": 0, "conflict": 0, "ignored": 0}
    pages = 0
    while url:
        pages += 1
        if pages > MAX_SYNC_PAGES:
            raise CalendarSyncError("sync_page_limit", "Calendar synchronization exceeded its page limit.")
        response = client.get(url, headers={"Authorization": f"Bearer {credentials['access_token']}", "Prefer": "odata.maxpagesize=500"})
        if response.status_code >= 400:
            raise CalendarSyncError("microsoft_sync_failed", "Outlook calendar synchronization failed.")
        data = response.json()
        for remote in data.get("value") or []:
            counts[_upsert_external_event(connection, remote, "microsoft", client)] += 1
        url = data.get("@odata.nextLink")
        if data.get("@odata.deltaLink"):
            cursor["delta_link"] = data["@odata.deltaLink"]
    return counts, cursor


def _outbound_payload(event: dict[str, Any], provider: str) -> dict[str, Any]:
    if provider == "google":
        payload = {
            "summary": event.get("title"), "description": event.get("description"), "location": event.get("location"),
            "start": {"dateTime": event.get("starts_at"), "timeZone": event.get("timezone") or "UTC"},
            "end": {"dateTime": event.get("ends_at"), "timeZone": event.get("timezone") or "UTC"},
            "visibility": "private" if event.get("visibility") == "private" else "default",
            "transparency": "transparent" if event.get("transparency") == "free" else "opaque",
        }
        if event.get("recurrence_rule"):
            payload["recurrence"] = [f"RRULE:{event['recurrence_rule']}"]
        return payload
    return {
        "subject": event.get("title"),
        "body": {"contentType": "text", "content": event.get("description") or ""},
        "location": {"displayName": event.get("location") or ""},
        "start": {"dateTime": event.get("starts_at"), "timeZone": event.get("timezone") or "UTC"},
        "end": {"dateTime": event.get("ends_at"), "timeZone": event.get("timezone") or "UTC"},
        "showAs": "free" if event.get("transparency") == "free" else "busy",
        "sensitivity": "private" if event.get("visibility") == "private" else "normal",
    }


def _push_local_changes(connection: dict[str, Any], credentials: dict[str, Any], provider: str, client) -> dict[str, int]:
    if connection.get("direction") != "two_way":
        return {"pushed": 0, "push_failed": 0}
    query = service_supabase.table("calendar_events").select("*").eq("tenant_id", connection["tenant_id"]).eq("calendar_id", connection["local_calendar_id"]).order("updated_at").limit(1000)
    if connection.get("last_success_at"):
        query = query.gt("updated_at", connection["last_success_at"])
    events = getattr(query.execute(), "data", None) or []
    counts = {"pushed": 0, "push_failed": 0}
    headers = {"Authorization": f"Bearer {credentials['access_token']}", "Content-Type": "application/json"}
    for event in events:
        source_type = str(event.get("source_type") or "madar")
        source_id = str(event.get("source_id") or "")
        if source_type not in {"madar", provider}:
            continue
        if source_type == provider and not source_id.startswith(f"{connection['id']}:"):
            continue
        remote_id = source_id.split(":", 1)[1] if source_type == provider and ":" in source_id else ""
        if provider == "google":
            provider_calendar_id = quote(
                str(connection.get("provider_calendar_id") or "primary"),
                safe="",
            )
            collection_url = (
                "https://www.googleapis.com/calendar/v3/calendars/"
                f"{provider_calendar_id}/events"
            )
            item_url = f"{collection_url}/{remote_id}" if remote_id else collection_url
        else:
            collection_url = "https://graph.microsoft.com/v1.0/me/events"
            item_url = f"{collection_url}/{remote_id}" if remote_id else collection_url
        if event.get("deleted_at"):
            if remote_id:
                result = client.delete(item_url, headers=headers)
                if result.status_code not in {204, 404, 410}:
                    counts["push_failed"] += 1
                    continue
            counts["pushed"] += 1
            continue
        payload = _outbound_payload(event, provider)
        result = client.patch(item_url, headers=headers, json=payload) if remote_id else client.post(collection_url, headers=headers, json=payload)
        if result.status_code >= 400:
            counts["push_failed"] += 1
            continue
        remote = result.json()
        saved_remote_id = str(remote.get("id") or remote_id)
        service_supabase.table("calendar_events").update({
            "source_type": provider, "source_id": f"{connection['id']}:{saved_remote_id}",
            "external_etag": str(remote.get("etag") or remote.get("@odata.etag") or remote.get("changeKey") or ""),
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", event["id"]).eq("tenant_id", connection["tenant_id"]).execute()
        counts["pushed"] += 1
    return counts


def _sync_connection_with_client(
    connection: dict[str, Any], client
) -> dict[str, Any]:
    provider = str(connection.get("provider") or "")
    if provider not in {"google", "microsoft"}:
        raise CalendarSyncError("provider_sync_unsupported", "Use ICS export or subscription for this provider.")
    if not connection.get("encrypted_credentials") or not connection.get("local_calendar_id"):
        raise CalendarSyncError("connection_setup_incomplete", "Finish provider authorization before syncing.")
    calendars = getattr(
        service_supabase.table("calendars").select("id,owner_user_id")
        .eq("id", connection["local_calendar_id"])
        .eq("tenant_id", connection["tenant_id"]).limit(1).execute(),
        "data", None,
    ) or []
    memberships = getattr(
        service_supabase.table("tenant_memberships").select("user_id")
        .eq("tenant_id", connection["tenant_id"])
        .eq("user_id", connection["user_id"])
        .eq("status", "active").limit(1).execute(),
        "data", None,
    ) or []
    calendar_memberships = []
    if calendars and int(calendars[0].get("owner_user_id") or -1) != int(connection["user_id"]):
        calendar_memberships = getattr(
            service_supabase.table("calendar_memberships").select("role")
            .eq("calendar_id", connection["local_calendar_id"])
            .eq("tenant_id", connection["tenant_id"])
            .eq("user_id", connection["user_id"])
            .eq("role", "owner").limit(1).execute(),
            "data", None,
        ) or []
    calendar_owner_valid = bool(calendars) and (
        int(calendars[0].get("owner_user_id") or -1) == int(connection["user_id"])
        or bool(calendar_memberships)
    )
    if not calendar_owner_valid or not memberships:
        raise CalendarSyncError("connection_binding_invalid", "Calendar connection ownership is no longer valid.")
    credentials = _refresh(provider, decrypt_credentials(connection["encrypted_credentials"]), client)
    if not credentials_allow_direction(
        provider, credentials, str(connection.get("direction") or "read")
    ):
        raise CalendarSyncError(
            "calendar_write_access_required",
            "Reconnect this calendar with the requested access before synchronizing.",
        )
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        push_counts = _push_local_changes(connection, credentials, provider, client)
        counts, cursor = (_google_sync if provider == "google" else _microsoft_sync)(connection, credentials, client)
    except CalendarSyncError as error:
        service_supabase.table("calendar_sync_connections").update({"status": "degraded", "last_attempt_at": started_at, "last_error_code": error.code, "failed_changes": int(connection.get("failed_changes") or 0) + 1}).eq("id", connection["id"]).execute()
        raise
    counts.update(push_counts)
    service_supabase.table("calendar_sync_connections").update({
        "status": "connected", "encrypted_credentials": encrypt_credentials(credentials), "cursor_data": cursor,
        "last_attempt_at": started_at, "last_success_at": datetime.now(timezone.utc).isoformat(), "last_error_code": None,
        "pending_changes": counts["push_failed"], "failed_changes": counts["conflict"] + counts["push_failed"],
    }).eq("id", connection["id"]).execute()
    return counts


def sync_connection(connection: dict[str, Any], *, http_client=None) -> dict[str, Any]:
    if http_client is not None:
        return _sync_connection_with_client(connection, http_client)
    timeout = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)
    with httpx.Client(timeout=timeout) as client:
        return _sync_connection_with_client(connection, client)

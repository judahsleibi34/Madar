import socket
import os
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from routes import auth_routes, notification_routes
from services import auth_service, notification_delivery_service, notification_service
from services.installation_service import PushSubscriptionBindingError
from services.push_subscription_security import UnsafePushEndpoint, validate_push_endpoint


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []
        self.null_filters = []
        self.values = None

    def select(self, *_args): return self
    def eq(self, field, value): self.filters.append((field, value)); return self
    def is_(self, field, value): self.null_filters.append((field, value)); return self
    def order(self, *_args, **_kwargs): return self
    def limit(self, *_args): return self
    def update(self, values): self.values = values; return self

    def execute(self):
        rows = [
            row for row in self.client.tables.get(self.table, [])
            if all(row.get(field) == value for field, value in self.filters)
            and all((row.get(field) is None) == (value == "null") for field, value in self.null_filters)
        ]
        if self.values is not None:
            for row in rows:
                row.update(self.values)
        return FakeResponse([dict(row) for row in rows])


class FakeClient:
    def __init__(self):
        self.tables = {
            "tenant_memberships": [],
            "user_notifications": [],
            "web_push_subscriptions": [],
            "app_installations": [],
            "users": [],
        }

    def table(self, name):
        return FakeQuery(self, name)


def resolved(address):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    destination = (address, 443, 0, 0) if family == socket.AF_INET6 else (address, 443)
    return [(family, socket.SOCK_STREAM, 6, "", destination)]


class NotificationInboxIsolationTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.client.tables["user_notifications"] = [
            {"id": "a", "tenant_id": 1, "user_id": 7, "read_at": None, "created_at": "2026-01-01", "title": "A"},
            {"id": "b", "tenant_id": 2, "user_id": 7, "read_at": None, "created_at": "2026-01-02", "title": "B"},
            {"id": "other", "tenant_id": 2, "user_id": 8, "read_at": None, "created_at": "2026-01-03", "title": "Other"},
        ]

    def test_list_and_unread_count_are_tenant_and_user_scoped(self):
        with patch.object(notification_service, "service_supabase", self.client):
            result = notification_service.list_user_notifications(tenant_id=2, user_id=7)
        self.assertEqual([item["id"] for item in result["items"]], ["b"])
        self.assertEqual(result["unread_count"], 1)

    def test_mark_one_cannot_cross_tenants_or_users(self):
        with patch.object(notification_service, "service_supabase", self.client):
            self.assertIsNone(notification_service.mark_notification_read(tenant_id=2, user_id=7, notification_id="a"))
            self.assertIsNone(notification_service.mark_notification_read(tenant_id=2, user_id=7, notification_id="other"))
        self.assertIsNone(self.client.tables["user_notifications"][0]["read_at"])
        self.assertIsNone(self.client.tables["user_notifications"][2]["read_at"])

    def test_mark_all_only_mutates_current_tenant_and_user(self):
        with patch.object(notification_service, "service_supabase", self.client):
            count = notification_service.mark_all_notifications_read(tenant_id=2, user_id=7)
        self.assertEqual(count, 1)
        self.assertIsNone(self.client.tables["user_notifications"][0]["read_at"])
        self.assertIsNotNone(self.client.tables["user_notifications"][1]["read_at"])
        self.assertIsNone(self.client.tables["user_notifications"][2]["read_at"])


class PushEndpointSecurityTests(unittest.TestCase):
    def setUp(self):
        self.push_environment = patch.dict(os.environ, {
            "WEB_PUSH_ENABLED": "true",
            "WEB_PUSH_VAPID_PUBLIC_KEY": "public",
            "WEB_PUSH_VAPID_PRIVATE_KEY": "private",
            "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.invalid",
        }, clear=False)
        self.push_environment.start()

    def tearDown(self):
        self.push_environment.stop()

    def test_rejects_unsafe_url_shapes_and_network_destinations(self):
        unsafe_without_dns = [
            "http://push.example.test/send",
            "https://user:password@push.example.test/send",
            "https://push.example.test/send#fragment",
            "not-a-url",
            "https://localhost/send",
        ]
        for endpoint in unsafe_without_dns:
            with self.subTest(endpoint=endpoint), self.assertRaises(UnsafePushEndpoint):
                validate_push_endpoint(endpoint)

        unsafe_addresses = ["127.0.0.1", "10.0.0.1", "169.254.1.1", "224.0.0.1", "0.0.0.0", "::1", "fc00::1", "fe80::1"]
        for address in unsafe_addresses:
            with self.subTest(address=address), patch("socket.getaddrinfo", return_value=resolved(address)), self.assertRaises(UnsafePushEndpoint):
                validate_push_endpoint("https://push.example.test/send")

    def test_rejects_dns_failure_and_accepts_public_https_destination(self):
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("not found")), self.assertRaises(UnsafePushEndpoint):
            validate_push_endpoint("https://missing.example.test/send")
        with patch("socket.getaddrinfo", return_value=resolved("8.8.8.8")):
            self.assertEqual(validate_push_endpoint("https://push.example.test/send"), "https://push.example.test/send")

    def test_subscription_fields_have_bounded_base64url_validation(self):
        valid = {"endpoint": "https://push.example.test/send", "keys": {"p256dh": "A" * 87, "auth": "B" * 22}}
        self.assertEqual(notification_routes.PushSubscriptionRequest(**valid).keys.auth, "B" * 22)
        invalid_payloads = [
            {**valid, "endpoint": "https://" + "a" * 2001},
            {**valid, "keys": {"p256dh": "short", "auth": "B" * 22}},
            {**valid, "keys": {"p256dh": "!" * 87, "auth": "B" * 22}},
            {**valid, "keys": {"p256dh": "A" * 87, "auth": "x" * 1000}},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                notification_routes.PushSubscriptionRequest(**payload)

    def test_registration_rejects_private_dns_and_records_authoritative_tenant(self):
        app = FastAPI()
        app.include_router(notification_routes.router)
        client = TestClient(app)
        context = SimpleNamespace(tenant_id=22, user_id=7)
        payload = {"endpoint": "https://push.example.test/send", "keys": {"p256dh": "A" * 87, "auth": "B" * 22}}
        with patch.object(notification_routes, "get_current_tenant_context", return_value=context), patch("socket.getaddrinfo", return_value=resolved("10.0.0.5")):
            rejected = client.post("/notifications/push-subscriptions", json=payload)
        self.assertEqual(rejected.status_code, 400)

        with patch.object(notification_routes, "get_current_tenant_context", return_value=context), patch("socket.getaddrinfo", return_value=resolved("8.8.8.8")), patch.object(notification_routes, "upsert_web_push_subscription", return_value={"id": "subscription", "endpoint": payload["endpoint"]}) as upsert:
            accepted = client.post("/notifications/push-subscriptions", json=payload)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(upsert.call_args.kwargs["tenant_id"], 22)
        self.assertEqual(upsert.call_args.kwargs["user_id"], 7)

    def test_registration_resolves_installation_under_authoritative_identity(self):
        app = FastAPI()
        app.include_router(notification_routes.router)
        client = TestClient(app)
        context = SimpleNamespace(tenant_id=22, user_id=7)
        payload = {
            "endpoint": "https://push.example.test/send",
            "keys": {"p256dh": "A" * 87, "auth": "B" * 22},
            "installation_id": "123e4567-e89b-42d3-a456-426614174000",
        }
        with patch.object(notification_routes, "get_current_tenant_context", return_value=context), patch("socket.getaddrinfo", return_value=resolved("8.8.8.8")), patch.object(notification_routes, "bind_push_subscription", return_value={"id": "subscription", "endpoint": payload["endpoint"]}) as bind, patch.object(notification_routes, "upsert_web_push_subscription") as legacy:
            accepted = client.post("/notifications/push-subscriptions", json=payload)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(bind.call_args.kwargs["user_id"], 7)
        self.assertEqual(bind.call_args.kwargs["tenant_id"], 22)
        self.assertEqual(bind.call_args.kwargs["installation_id"], payload["installation_id"])
        legacy.assert_not_called()

    def test_registration_maps_sanitized_installation_rpc_error(self):
        app = FastAPI()
        app.include_router(notification_routes.router)
        client = TestClient(app)
        context = SimpleNamespace(tenant_id=22, user_id=7)
        payload = {
            "endpoint": "https://push.example.test/send",
            "keys": {"p256dh": "A" * 87, "auth": "B" * 22},
            "installation_id": "123e4567-e89b-42d3-a456-426614174000",
        }
        failure = PushSubscriptionBindingError(
            status_code=409,
            code="installation_unavailable",
            message="The application installation is not available.",
        )
        with patch.object(
            notification_routes, "get_current_tenant_context", return_value=context
        ), patch("socket.getaddrinfo", return_value=resolved("8.8.8.8")), patch.object(
            notification_routes, "bind_push_subscription", side_effect=failure
        ):
            response = client.post("/notifications/push-subscriptions", json=payload)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "installation_unavailable")

    def test_registration_respects_disabled_and_misconfigured_channel(self):
        app = FastAPI()
        app.include_router(notification_routes.router)
        client = TestClient(app)
        context = SimpleNamespace(tenant_id=22, user_id=7)
        payload = {
            "endpoint": "https://push.example.test/send",
            "keys": {"p256dh": "A" * 87, "auth": "B" * 22},
        }
        for environment, status, code in (
            ({"WEB_PUSH_ENABLED": "false"}, 409, "push_channel_disabled"),
            ({"WEB_PUSH_ENABLED": "true"}, 503, "push_channel_misconfigured"),
        ):
            with self.subTest(code=code), patch.dict(
                os.environ, environment, clear=True
            ), patch.object(
                notification_routes,
                "get_current_tenant_context",
                return_value=context,
            ), patch.object(notification_routes, "upsert_web_push_subscription") as upsert:
                response = client.post("/notifications/push-subscriptions", json=payload)
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.json()["detail"]["code"], code)
            upsert.assert_not_called()

    def test_endpoint_revocation_is_authenticated_user_scoped(self):
        app = FastAPI()
        app.include_router(notification_routes.router)
        client = TestClient(app)
        context = SimpleNamespace(tenant_id=22, user_id=7)
        endpoint = "https://push.example.test/current-device"
        with patch.object(notification_routes, "get_current_tenant_context", return_value=context), patch.object(notification_routes, "revoke_web_push_subscription", return_value=1) as revoke:
            response = client.request(
                "DELETE",
                "/notifications/push-subscriptions",
                json={"endpoint": endpoint},
            )
        self.assertEqual(response.status_code, 200)
        revoke.assert_called_once_with(user_id=7, endpoint=endpoint)

    def test_inbox_route_fails_closed_without_active_tenant_context(self):
        app = FastAPI()
        app.include_router(notification_routes.router)
        client = TestClient(app)
        with patch.object(notification_routes, "get_current_tenant_context", side_effect=HTTPException(status_code=403, detail="Active tenant membership required")), patch.object(notification_routes, "list_user_notifications") as listing:
            response = client.get("/notifications")
        self.assertEqual(response.status_code, 403)
        listing.assert_not_called()


class ExternalDeliveryMembershipTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.client.tables["tenant_memberships"] = [
            {"tenant_id": 1, "user_id": 10, "status": "active"},
            {"tenant_id": 1, "user_id": 11, "status": "inactive"},
        ]
        self.client.tables["web_push_subscriptions"] = [
            {"id": "active", "tenant_id": 1, "user_id": 10, "endpoint": "https://push.test/active", "p256dh": "A", "auth": "B", "revoked_at": None},
            {"id": "inactive", "tenant_id": 1, "user_id": 11, "endpoint": "https://push.test/inactive", "p256dh": "A", "auth": "B", "revoked_at": None},
            {"id": "other-tenant", "tenant_id": 2, "user_id": 10, "endpoint": "https://push.test/other", "p256dh": "A", "auth": "B", "revoked_at": None},
        ]

    def test_worker_push_rejects_inactive_member_and_scopes_active_subscription(self):
        base_row = {"channel": "web_push", "tenant_id": 1, "payload": {"title": "Title", "body": "Body"}}
        environment = {"WEB_PUSH_ENABLED": "true", "WEB_PUSH_VAPID_PUBLIC_KEY": "public", "WEB_PUSH_VAPID_PRIVATE_KEY": "private", "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.com"}
        with patch.object(notification_delivery_service, "service_supabase", self.client), patch.dict("os.environ", environment, clear=False):
            with self.assertRaisesRegex(notification_delivery_service.DeliveryError, "recipient_inactive"):
                notification_delivery_service._deliver_web_push({**base_row, "user_id": 11, "subscription_id": "inactive"})
            with patch.object(notification_delivery_service, "validate_push_endpoint", side_effect=lambda value: value), patch("pywebpush.webpush") as send:
                notification_delivery_service._deliver_web_push({**base_row, "user_id": 10, "subscription_id": "active"})
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.kwargs["subscription_info"]["endpoint"], "https://push.test/active")
        self.assertEqual(send.call_args.kwargs["requests_session"].max_redirects, 0)

    def test_worker_rechecks_endpoint_safety_before_send_and_revokes_invalid_binding(self):
        row = {"channel": "web_push", "tenant_id": 1, "user_id": 10, "subscription_id": "active", "payload": {"title": "Title", "body": "Body"}}
        environment = {"WEB_PUSH_ENABLED": "true", "WEB_PUSH_VAPID_PUBLIC_KEY": "public", "WEB_PUSH_VAPID_PRIVATE_KEY": "private", "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.com"}
        with patch.object(notification_delivery_service, "service_supabase", self.client), patch.dict("os.environ", environment, clear=False), patch.object(notification_delivery_service, "validate_push_endpoint", side_effect=UnsafePushEndpoint("push_endpoint_unsafe")), patch("pywebpush.webpush") as send:
            with self.assertRaisesRegex(notification_delivery_service.DeliveryError, "web_push_endpoint_unsafe"):
                notification_delivery_service._deliver_web_push(row)
        send.assert_not_called()
        active = next(item for item in self.client.tables["web_push_subscriptions"] if item["id"] == "active")
        self.assertIsNotNone(active["revoked_at"])

    def test_worker_marks_gone_subscription_revoked_and_terminal(self):
        from pywebpush import WebPushException

        row = {"channel": "web_push", "tenant_id": 1, "user_id": 10, "subscription_id": "active", "payload": {"title": "Title"}}
        environment = {"WEB_PUSH_ENABLED": "true", "WEB_PUSH_VAPID_PUBLIC_KEY": "public", "WEB_PUSH_VAPID_PRIVATE_KEY": "private", "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.com"}
        gone = WebPushException("gone", response=SimpleNamespace(status_code=410))
        with patch.object(notification_delivery_service, "service_supabase", self.client), patch.dict("os.environ", environment, clear=False), patch.object(notification_delivery_service, "validate_push_endpoint", side_effect=lambda value: value), patch("pywebpush.webpush", side_effect=gone), self.assertRaises(notification_delivery_service.DeliveryError) as raised:
            notification_delivery_service._deliver_web_push(row)
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(raised.exception.terminal_outcome, "revoked")
        active = next(item for item in self.client.tables["web_push_subscriptions"] if item["id"] == "active")
        self.assertIsNotNone(active["revoked_at"])

    def test_worker_classifies_provider_failures_without_persisting_provider_content(self):
        from pywebpush import WebPushException

        row = {"channel": "web_push", "tenant_id": 1, "user_id": 10, "subscription_id": "active", "payload": {"title": "Title"}}
        environment = {"WEB_PUSH_ENABLED": "true", "WEB_PUSH_VAPID_PUBLIC_KEY": "public", "WEB_PUSH_VAPID_PRIVATE_KEY": "private", "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.com"}
        expectations = (
            (400, "web_push_request_invalid", False),
            (401, "web_push_provider_unauthorized", False),
            (403, "web_push_provider_forbidden", False),
            (500, "web_push_provider_unavailable", True),
            (503, "web_push_provider_unavailable", True),
        )
        for status, code, retryable in expectations:
            with self.subTest(status=status):
                failure = WebPushException(
                    "provider response must not be persisted",
                    response=SimpleNamespace(status_code=status, headers={}),
                )
                with patch.object(notification_delivery_service, "service_supabase", self.client), patch.dict("os.environ", environment, clear=False), patch.object(notification_delivery_service, "validate_push_endpoint", side_effect=lambda value: value), patch("pywebpush.webpush", side_effect=failure), self.assertRaises(notification_delivery_service.DeliveryError) as raised:
                    notification_delivery_service._deliver_web_push(row)
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(raised.exception.retryable, retryable)
                self.assertNotIn("provider response", raised.exception.code)

    def test_worker_honors_numeric_and_http_date_retry_after(self):
        from pywebpush import WebPushException

        row = {"channel": "web_push", "tenant_id": 1, "user_id": 10, "subscription_id": "active", "payload": {"title": "Title"}}
        environment = {"WEB_PUSH_ENABLED": "true", "WEB_PUSH_VAPID_PUBLIC_KEY": "public", "WEB_PUSH_VAPID_PRIVATE_KEY": "private", "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.com"}
        values = (
            ("120", 120),
            (format_datetime(datetime.now(timezone.utc) + timedelta(seconds=120)), 120),
        )
        for retry_after, expected in values:
            with self.subTest(retry_after=retry_after):
                failure = WebPushException(
                    "limited",
                    response=SimpleNamespace(
                        status_code=429,
                        headers={"Retry-After": retry_after},
                    ),
                )
                with patch.object(notification_delivery_service, "service_supabase", self.client), patch.dict("os.environ", environment, clear=False), patch.object(notification_delivery_service, "validate_push_endpoint", side_effect=lambda value: value), patch("pywebpush.webpush", side_effect=failure), self.assertRaises(notification_delivery_service.DeliveryError) as raised:
                    notification_delivery_service._deliver_web_push(row)
                self.assertEqual(raised.exception.code, "web_push_rate_limited")
                self.assertTrue(raised.exception.retryable)
                self.assertLessEqual(abs(raised.exception.retry_after_seconds - expected), 2)

    def test_invalid_global_vapid_key_does_not_revoke_subscription(self):
        row = {"channel": "web_push", "tenant_id": 1, "user_id": 10, "subscription_id": "active", "payload": {"title": "Title"}}
        environment = {"WEB_PUSH_ENABLED": "true", "WEB_PUSH_VAPID_PUBLIC_KEY": "public", "WEB_PUSH_VAPID_PRIVATE_KEY": "private", "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.com"}
        with patch.object(notification_delivery_service, "service_supabase", self.client), patch.dict("os.environ", environment, clear=False), patch.object(notification_delivery_service, "validate_push_endpoint", side_effect=lambda value: value), patch("pywebpush.webpush", side_effect=ValueError("invalid local key material")), self.assertRaises(notification_delivery_service.DeliveryError) as raised:
            notification_delivery_service._deliver_web_push(row)
        self.assertEqual(raised.exception.code, "web_push_provider_configuration_invalid")
        self.assertFalse(raised.exception.retryable)
        self.assertEqual(raised.exception.terminal_outcome, "dead")
        active = next(item for item in self.client.tables["web_push_subscriptions"] if item["id"] == "active")
        self.assertIsNone(active["revoked_at"])

    def test_global_vapid_failure_cannot_mass_revoke_recipients(self):
        self.client.tables["web_push_subscriptions"].append({
            **self.client.tables["web_push_subscriptions"][0],
            "id": "second", "user_id": 11,
        })
        self.client.tables["tenant_memberships"].append({
            "tenant_id": 1, "user_id": 11, "status": "active",
        })
        environment = {
            "WEB_PUSH_ENABLED": "true",
            "WEB_PUSH_VAPID_PUBLIC_KEY": "invalid-global-public",
            "WEB_PUSH_VAPID_PRIVATE_KEY": "invalid-global-private",
            "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.com",
        }
        for user_id, subscription_id in ((10, "active"), (11, "second")):
            row = {
                "channel": "web_push", "tenant_id": 1, "user_id": user_id,
                "subscription_id": subscription_id, "payload": {"title": "Title"},
            }
            with patch.object(notification_delivery_service, "service_supabase", self.client), patch.dict("os.environ", environment, clear=False), patch.object(notification_delivery_service, "validate_push_endpoint", side_effect=lambda value: value), patch("pywebpush.webpush", side_effect=ValueError("invalid global key")), self.assertRaises(notification_delivery_service.DeliveryError) as raised:
                notification_delivery_service._deliver_web_push(row)
            self.assertEqual(
                raised.exception.code, "web_push_provider_configuration_invalid"
            )
        self.assertTrue(all(
            item["revoked_at"] is None
            for item in self.client.tables["web_push_subscriptions"]
        ))

    def test_inactive_member_email_is_rejected_before_smtp(self):
        self.client.tables["users"] = [{"id": "11", "email": "former@example.com"}]
        with patch.object(notification_delivery_service, "service_supabase", self.client):
            with self.assertRaisesRegex(notification_delivery_service.DeliveryError, "recipient_inactive"):
                notification_delivery_service._deliver_email({"tenant_id": 1, "recipient_reference": "user:11", "template": "calendar_reminder", "payload": {}})


class LogoutPushRevocationTests(unittest.TestCase):
    def request(self):
        return Request({"type": "http", "method": "POST", "path": "/auth/log_out", "headers": []})

    def test_logout_revokes_all_server_bindings_for_authenticated_user(self):
        response = Response()
        with patch.object(auth_routes, "get_authenticated_user_row", return_value=(object(), {"id": 42})), patch.object(auth_routes, "revoke_all_web_push_subscriptions", return_value=2) as revoke:
            result = auth_routes.log_out(self.request(), response)
        self.assertEqual(result["message"], "Logged out successfully")
        revoke.assert_called_once_with(user_id=42)
        self.assertIn("madar_access_token", response.headers.get("set-cookie", ""))

    def test_logout_still_succeeds_when_push_revocation_fails(self):
        response = Response()
        with patch.object(auth_routes, "get_authenticated_user_row", return_value=(object(), {"id": 42})), patch.object(auth_routes, "revoke_all_web_push_subscriptions", side_effect=RuntimeError("database unavailable")):
            result = auth_routes.log_out(self.request(), response)
        self.assertEqual(result["message"], "Logged out successfully")

    def test_logout_revokes_only_the_request_verified_provider_session(self):
        request = self.request()
        request.state.verified_auth_session = {
            "access_token": "verified-access",
            "refresh_token": "verified-refresh",
            "auth_id": "verified-user",
        }
        provider_auth = Mock()
        provider = SimpleNamespace(auth=provider_auth)

        with patch.object(
            auth_service, "create_session_supabase_client", return_value=provider
        ):
            revoked = auth_service.revoke_verified_auth_session(request)

        self.assertTrue(revoked)
        provider_auth.set_session.assert_called_once_with(
            "verified-access", "verified-refresh"
        )
        provider_auth.sign_out.assert_called_once_with({"scope": "local"})
        self.assertIsNone(request.state.verified_auth_session)

    def test_logout_fails_closed_when_provider_session_cannot_be_revoked(self):
        response = Response()
        with patch.object(
            auth_routes,
            "get_authenticated_user_row",
            return_value=(object(), {"id": 42}),
        ), patch.object(
            auth_routes, "revoke_all_web_push_subscriptions", return_value=0
        ), patch.object(
            auth_routes,
            "revoke_verified_auth_session",
            side_effect=RuntimeError("provider unavailable"),
        ):
            result = auth_routes.log_out(self.request(), response)

        self.assertEqual(result.status_code, 503)
        self.assertIn("madar_access_token", result.headers.get("set-cookie", ""))
        self.assertNotIn("provider unavailable", result.body.decode())

    def test_identified_logout_revokes_only_current_installation(self):
        response = Response()
        logout = auth_routes.LogoutRequest(
            installation_id="123e4567-e89b-42d3-a456-426614174000"
        )
        with patch.object(auth_routes, "get_authenticated_user_row", return_value=(object(), {"id": 42})), patch.object(auth_routes, "revoke_installation_push_bindings", return_value=1) as scoped, patch.object(auth_routes, "revoke_all_web_push_subscriptions") as revoke_all:
            result = auth_routes.log_out(self.request(), response, logout)
        self.assertEqual(result["message"], "Logged out successfully")
        scoped.assert_called_once_with(
            user_id=42,
            installation_id="123e4567-e89b-42d3-a456-426614174000",
        )
        revoke_all.assert_not_called()

    def test_identified_logout_still_succeeds_when_scoped_cleanup_fails(self):
        response = Response()
        logout = auth_routes.LogoutRequest(
            installation_id="123e4567-e89b-42d3-a456-426614174000"
        )
        with patch.object(auth_routes, "get_authenticated_user_row", return_value=(object(), {"id": 42})), patch.object(auth_routes, "revoke_installation_push_bindings", side_effect=RuntimeError("database unavailable")):
            result = auth_routes.log_out(self.request(), response, logout)
        self.assertEqual(result["message"], "Logged out successfully")

    def test_logout_revokes_known_legacy_endpoint_without_other_devices(self):
        response = Response()
        logout = auth_routes.LogoutRequest(
            installation_id="123e4567-e89b-42d3-a456-426614174000",
            push_endpoint="https://push.test/device-a",
        )
        with patch.object(auth_routes, "get_authenticated_user_row", return_value=(object(), {"id": 42})), patch.object(auth_routes, "revoke_installation_push_bindings", return_value=0), patch.object(auth_routes, "revoke_web_push_subscription", return_value=1) as endpoint_revoke, patch.object(auth_routes, "revoke_all_web_push_subscriptions") as revoke_all:
            result = auth_routes.log_out(self.request(), response, logout)
        self.assertEqual(result["message"], "Logged out successfully")
        endpoint_revoke.assert_called_once_with(
            user_id=42, endpoint="https://push.test/device-a"
        )
        revoke_all.assert_not_called()

    def test_worker_rejects_subscription_bound_to_revoked_installation(self):
        client = FakeClient()
        client.tables["tenant_memberships"] = [{"tenant_id": 1, "user_id": 42, "status": "active"}]
        client.tables["web_push_subscriptions"] = [{"id": "binding", "tenant_id": 1, "user_id": 42, "app_installation_id": "installation", "endpoint": "https://push.test/send", "p256dh": "A", "auth": "B", "revoked_at": None}]
        client.tables["app_installations"] = [{"id": "installation", "user_id": 42, "notifications_enabled": True, "notification_permission": "granted", "revoked_at": "2026-01-01"}]
        environment = {"WEB_PUSH_ENABLED": "true", "WEB_PUSH_VAPID_PUBLIC_KEY": "public", "WEB_PUSH_VAPID_PRIVATE_KEY": "private", "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.com"}
        with patch.object(notification_delivery_service, "service_supabase", client), patch.dict("os.environ", environment, clear=False), self.assertRaisesRegex(notification_delivery_service.DeliveryError, "web_push_installation_inactive"):
            notification_delivery_service._deliver_web_push({"channel": "web_push", "tenant_id": 1, "user_id": 42, "subscription_id": "binding", "payload": {}})

    def test_worker_sends_for_active_enabled_installation(self):
        client = FakeClient()
        client.tables["tenant_memberships"] = [{"tenant_id": 1, "user_id": 42, "status": "active"}]
        client.tables["web_push_subscriptions"] = [{"id": "binding", "tenant_id": 1, "user_id": 42, "app_installation_id": "installation", "endpoint": "https://push.test/send", "p256dh": "A", "auth": "B", "revoked_at": None}]
        client.tables["app_installations"] = [{"id": "installation", "user_id": 42, "notifications_enabled": True, "notification_permission": "granted", "revoked_at": None}]
        environment = {"WEB_PUSH_ENABLED": "true", "WEB_PUSH_VAPID_PUBLIC_KEY": "public", "WEB_PUSH_VAPID_PRIVATE_KEY": "private", "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.com"}
        with patch.object(notification_delivery_service, "service_supabase", client), patch.dict("os.environ", environment, clear=False), patch.object(notification_delivery_service, "validate_push_endpoint", side_effect=lambda value: value), patch("pywebpush.webpush") as send:
            notification_delivery_service._deliver_web_push({"channel": "web_push", "tenant_id": 1, "user_id": 42, "subscription_id": "binding", "payload": {}})
        send.assert_called_once()

    def test_worker_rejects_permission_denied_installation_without_affecting_sibling(self):
        client = FakeClient()
        client.tables["tenant_memberships"] = [{"tenant_id": 1, "user_id": 42, "status": "active"}]
        client.tables["web_push_subscriptions"] = [
            {"id": "denied-binding", "tenant_id": 1, "user_id": 42, "app_installation_id": "denied-installation", "endpoint": "https://push.test/denied", "p256dh": "A", "auth": "B", "revoked_at": None},
            {"id": "active-binding", "tenant_id": 1, "user_id": 42, "app_installation_id": "active-installation", "endpoint": "https://push.test/active", "p256dh": "A", "auth": "B", "revoked_at": None},
        ]
        client.tables["app_installations"] = [
            {"id": "denied-installation", "user_id": 42, "notifications_enabled": False, "notification_permission": "denied", "revoked_at": None},
            {"id": "active-installation", "user_id": 42, "notifications_enabled": True, "notification_permission": "granted", "revoked_at": None},
        ]
        environment = {"WEB_PUSH_ENABLED": "true", "WEB_PUSH_VAPID_PUBLIC_KEY": "public", "WEB_PUSH_VAPID_PRIVATE_KEY": "private", "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.com"}
        with patch.object(notification_delivery_service, "service_supabase", client), patch.dict("os.environ", environment, clear=False), self.assertRaisesRegex(notification_delivery_service.DeliveryError, "web_push_installation_inactive"):
            notification_delivery_service._deliver_web_push({"channel": "web_push", "tenant_id": 1, "user_id": 42, "subscription_id": "denied-binding", "payload": {}})
        with patch.object(notification_delivery_service, "service_supabase", client), patch.dict("os.environ", environment, clear=False), patch.object(notification_delivery_service, "validate_push_endpoint", side_effect=lambda value: value), patch("pywebpush.webpush") as send:
            notification_delivery_service._deliver_web_push({"channel": "web_push", "tenant_id": 1, "user_id": 42, "subscription_id": "active-binding", "payload": {}})
        send.assert_called_once()

    def test_revoked_binding_is_not_selected_for_later_tenant_push(self):
        client = FakeClient()
        client.tables["tenant_memberships"] = [{"tenant_id": 1, "user_id": 42, "status": "active"}]
        client.tables["web_push_subscriptions"] = [{"id": "binding", "tenant_id": 1, "user_id": 42, "endpoint": "https://push.test/send", "p256dh": "A", "auth": "B", "revoked_at": None}]
        with patch.object(notification_service, "service_supabase", client):
            self.assertEqual(notification_service.revoke_all_web_push_subscriptions(user_id=42), 1)
        environment = {"WEB_PUSH_ENABLED": "true", "WEB_PUSH_VAPID_PUBLIC_KEY": "public", "WEB_PUSH_VAPID_PRIVATE_KEY": "private", "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.com"}
        with patch.object(notification_delivery_service, "service_supabase", client), patch.dict("os.environ", environment, clear=False), self.assertRaisesRegex(notification_delivery_service.DeliveryError, "web_push_subscription_revoked"):
            notification_delivery_service._deliver_web_push({"channel": "web_push", "tenant_id": 1, "user_id": 42, "subscription_id": "binding", "payload": {}})


if __name__ == "__main__":
    unittest.main()

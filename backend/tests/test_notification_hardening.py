import socket
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from routes import auth_routes, notification_routes
from services import notification_delivery_service, notification_service
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

    def test_direct_tenant_push_selects_only_active_member_bindings(self):
        with patch.object(notification_service, "service_supabase", self.client), patch.object(notification_service, "_web_push_enabled", return_value=True), patch.object(notification_service, "_send_web_push") as send:
            notification_service._send_tenant_push_notifications(tenant_id=1, title="Title", body="Body", data={})
        self.assertEqual([call.kwargs["subscription"]["id"] for call in send.call_args_list], ["active"])

    def test_worker_push_rejects_inactive_member_and_scopes_active_subscription(self):
        base_row = {"channel": "web_push", "tenant_id": 1, "payload": {"title": "Title", "body": "Body"}}
        environment = {"WEB_PUSH_VAPID_PUBLIC_KEY": "public", "WEB_PUSH_VAPID_PRIVATE_KEY": "private", "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.com"}
        with patch.object(notification_delivery_service, "service_supabase", self.client), patch.dict("os.environ", environment, clear=False):
            with self.assertRaisesRegex(notification_delivery_service.DeliveryError, "recipient_inactive"):
                notification_delivery_service._deliver_web_push({**base_row, "user_id": 11})
            with patch.object(notification_delivery_service, "validate_push_endpoint", side_effect=lambda value: value), patch("pywebpush.webpush") as send:
                notification_delivery_service._deliver_web_push({**base_row, "user_id": 10})
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.kwargs["subscription_info"]["endpoint"], "https://push.test/active")
        self.assertEqual(send.call_args.kwargs["requests_session"].max_redirects, 0)

    def test_worker_rechecks_endpoint_safety_before_send_and_revokes_invalid_binding(self):
        row = {"channel": "web_push", "tenant_id": 1, "user_id": 10, "payload": {"title": "Title", "body": "Body"}}
        environment = {"WEB_PUSH_VAPID_PUBLIC_KEY": "public", "WEB_PUSH_VAPID_PRIVATE_KEY": "private", "WEB_PUSH_VAPID_SUBJECT": "mailto:test@example.com"}
        with patch.object(notification_delivery_service, "service_supabase", self.client), patch.dict("os.environ", environment, clear=False), patch.object(notification_delivery_service, "validate_push_endpoint", side_effect=UnsafePushEndpoint("push_endpoint_unsafe")), patch("pywebpush.webpush") as send:
            notification_delivery_service._deliver_web_push(row)
        send.assert_not_called()
        active = next(item for item in self.client.tables["web_push_subscriptions"] if item["id"] == "active")
        self.assertIsNotNone(active["revoked_at"])

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

    def test_revoked_binding_is_not_selected_for_later_tenant_push(self):
        client = FakeClient()
        client.tables["tenant_memberships"] = [{"tenant_id": 1, "user_id": 42, "status": "active"}]
        client.tables["web_push_subscriptions"] = [{"id": "binding", "tenant_id": 1, "user_id": 42, "endpoint": "https://push.test/send", "p256dh": "A", "auth": "B", "revoked_at": None}]
        with patch.object(notification_service, "service_supabase", client):
            self.assertEqual(notification_service.revoke_all_web_push_subscriptions(user_id=42), 1)
            with patch.object(notification_service, "_web_push_enabled", return_value=True), patch.object(notification_service, "_send_web_push") as send:
                notification_service._send_tenant_push_notifications(tenant_id=1, title="Title", body="Body", data={})
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()

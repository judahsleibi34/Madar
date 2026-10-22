import json
import gzip
import os
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from services.data_source_api_provider import (
    ProviderErrorCategory,
    ProviderFetchError,
    fetch_bounded_records,
    get_provider,
)
from services.provider_credentials import (
    AuthorizedSource, CredentialError, TestCredentialStore, test_credential_store,
)
from services.provider_http_transport import (
    SecretValue,
    TransportError,
    build_target,
    validate_destination,
)
from services.provider_registry import public_provider_capabilities


TOKEN = "fixture-token-not-a-real-credential"
PROJECT = "11111111-1111-4111-8111-111111111111"
SOURCE = "33333333-3333-4333-8333-333333333333"
AUTHORIZED_SOURCE = AuthorizedSource(1, PROJECT, SOURCE, "http_fixture")


class ProviderCapabilityTests(unittest.TestCase):
    def test_public_catalogue_is_empty_in_production_and_redacted_in_tests(self):
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=False):
            self.assertEqual(public_provider_capabilities(), [])
        with patch.dict(os.environ, {
            "APP_ENV": "test",
            "MADAR_TEST_HTTP_PROVIDER_URL": "http://127.0.0.1:8765",
        }, clear=False):
            catalogue = public_provider_capabilities()
        self.assertEqual(catalogue[0]["key"], "http_fixture")
        self.assertEqual(catalogue[0]["resources"], [{"key": "records", "label": "Records"}])
        self.assertNotIn("127.0.0.1", repr(catalogue))
        self.assertNotIn("/v1/records", repr(catalogue))


def fixture_provider(*, credential=TOKEN, **options):
    test_credential_store().put(AUTHORIZED_SOURCE, credential)
    return get_provider("http_fixture", source_scope=AUTHORIZED_SOURCE, **options)


class FixtureHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    mode = "records"
    requests = []

    def log_message(self, _format, *_args):
        return

    def _send(self, status, payload, **headers):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", headers.pop("content_type", "application/json"))
        self.send_header("Content-Length", str(len(body)))
        for name, value in headers.items():
            self.send_header(name.replace("_", "-"), str(value))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # Expected when the bounded client closes an oversized response early.
            pass

    def do_GET(self):
        type(self).requests.append({"path": self.path, "authorization": self.headers.get("Authorization")})
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self._send(401, {"error": "credential rejected"})
            return
        mode = type(self).mode
        if mode == "redirect":
            self._send(302, b"", Location="http://127.0.0.1/private")
            return
        if mode == "malformed":
            self._send(200, b"{not-json")
            return
        if mode == "timeout":
            time.sleep(0.1)
            self._send(200, {"records": [], "cursor": "late"})
            return
        if mode == "oversized":
            self._send(200, b"x" * (1024 * 1024 + 1))
            return
        if mode == "decompression_bomb":
            self._send(200, gzip.compress(b"x" * (4 * 1024 * 1024 + 1)), Content_Encoding="gzip")
            return
        if mode == "forbidden":
            self._send(403, {"error": "scope rejected"})
            return
        if mode == "rate_limited":
            self._send(429, {"error": "slow"}, Retry_After="0")
            return
        if mode == "unavailable":
            self._send(503, {"error": "down"})
            return
        if mode == "loop":
            self._send(200, {
                "records": [{"id": "A", "version": 1, "data": {"name": "A"}}],
                "next_page_token": "same",
            })
            return
        if mode == "early_cursor":
            self._send(200, {
                "records": [{"id": "A", "version": 1, "data": {"name": "A"}}],
                "next_page_token": "page-2", "sync_cursor": "unsafe-early-cursor",
            })
            return

        query = parse_qs(urlsplit(self.path).query)
        continuation = query.get("page_token", [None])[0]
        cursor = query.get("since", [None])[0]
        if cursor == "cursor-1":
            self._send(200, {
                "records": [
                    {"id": "B", "version": 2, "event_id": "event-B-2", "data": {"name": "B", "value": 25}},
                    {"id": "D", "version": 1, "event_id": "event-D-1", "data": {"name": "D", "value": 40}},
                    {"id": "A", "deleted": True, "version": 2, "event_id": "event-A-2"},
                ],
                "sync_cursor": "cursor-2",
            })
        elif continuation == "page-2":
            self._send(200, {
                "records": [{"id": "C", "version": 1, "event_id": "event-C-1", "data": {"name": "C", "value": 30}}],
                "sync_cursor": "cursor-1",
            })
        else:
            self._send(200, {
                "records": [
                    {"id": "A", "version": 1, "event_id": "event-A-1", "data": {"name": "A", "value": 10}},
                    {"id": "B", "version": 1, "event_id": "event-B-1", "data": {"name": "B", "value": 20}},
                ],
                "next_page_token": "page-2",
            })


class LocalFixture:
    def __enter__(self):
        FixtureHandler.mode = "records"
        FixtureHandler.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class ProviderHttpSecurityTests(unittest.TestCase):
    def test_https_resolution_rejects_private_mixed_and_nonstandard_destinations(self):
        def resolution(*addresses):
            return lambda *_args, **_kwargs: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))
                for address in addresses
            ]

        destination = validate_destination(
            "https://api.example.test/v1", resolver=resolution("93.184.216.34"),
        )
        self.assertEqual(destination.address, "93.184.216.34")
        for url, resolver in (
            ("https://api.example.test", resolution("127.0.0.1")),
            ("https://api.example.test", resolution("93.184.216.34", "10.0.0.2")),
            ("https://169.254.169.254", resolution("169.254.169.254")),
            ("https://api.example.test:8443", resolution("93.184.216.34")),
            ("http://api.example.test", resolution("93.184.216.34")),
        ):
            with self.subTest(url=url), self.assertRaises(TransportError):
                validate_destination(url, resolver=resolver)

    def test_loopback_requires_exact_test_environment_and_target_is_registry_bounded(self):
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=False):
            with self.assertRaises(TransportError):
                validate_destination("http://127.0.0.1:8080", test_loopback=True)
        with patch.dict(os.environ, {"APP_ENV": "test"}, clear=False):
            destination = validate_destination("http://localhost:8080/base", test_loopback=True)
        self.assertEqual(destination.address, "127.0.0.1")
        self.assertEqual(build_target(destination, "/records", {"cursor": "one"}), "/base/records?cursor=one")
        for path in ("http://evil.test", "/../private", "//evil.test/path"):
            with self.assertRaises(TransportError):
                build_target(destination, path, {})

    def test_secret_never_renders_or_serializes(self):
        secret = SecretValue(TOKEN)
        for rendered in (repr(secret), str(secret), f"{secret}"):
            self.assertNotIn(TOKEN, rendered)
            self.assertIn("redacted", rendered.lower())
        with self.assertRaises(TypeError):
            json.dumps({"credential": secret})

    def test_actual_http_fixture_paginates_and_normalizes_incremental_changes(self):
        audit = []
        with LocalFixture() as fixture, patch.dict(os.environ, {
            "APP_ENV": "test",
            "MADAR_TEST_HTTP_PROVIDER_URL": fixture.base_url,
        }, clear=False):
            first_provider = fixture_provider(audit=audit.append)
            first = fetch_bounded_records(first_provider, resource_type="records")
            first_provider.close()
            second_provider = fixture_provider(audit=audit.append)
            second = fetch_bounded_records(
                second_provider, resource_type="records", sync_cursor=first.next_cursor,
            )
            second_provider.close()
        self.assertEqual((first.page_count, first.record_count, first.next_cursor), (2, 3, "cursor-1"))
        self.assertEqual(second.next_cursor, "cursor-2")
        self.assertEqual([change["operation"] for change in second.changes], ["upsert", "upsert", "delete"])
        self.assertEqual(FixtureHandler.requests[0]["authorization"], f"Bearer {TOKEN}")
        self.assertNotIn(TOKEN, json.dumps(audit))
        self.assertTrue(all("path" not in event for event in audit))

    def test_http_failures_are_classified_and_pagination_cannot_commit_incomplete(self):
        cases = {
            "redirect": ProviderErrorCategory.UNAVAILABLE,
            "malformed": ProviderErrorCategory.INVALID_RESPONSE,
            "oversized": ProviderErrorCategory.PAYLOAD_TOO_LARGE,
            "decompression_bomb": ProviderErrorCategory.PAYLOAD_TOO_LARGE,
            "forbidden": ProviderErrorCategory.UNAUTHORIZED,
            "rate_limited": ProviderErrorCategory.RATE_LIMITED,
            "unavailable": ProviderErrorCategory.UNAVAILABLE,
            "loop": ProviderErrorCategory.INVALID_RESPONSE,
            "early_cursor": ProviderErrorCategory.INVALID_RESPONSE,
        }
        with LocalFixture() as fixture, patch.dict(os.environ, {
            "APP_ENV": "test",
            "MADAR_TEST_HTTP_PROVIDER_URL": fixture.base_url,
        }, clear=False):
            for mode, category in cases.items():
                with self.subTest(mode=mode):
                    FixtureHandler.mode = mode
                    provider = fixture_provider()
                    try:
                        with self.assertRaises(ProviderFetchError) as caught:
                            fetch_bounded_records(provider, resource_type="records")
                        self.assertEqual(caught.exception.category, category)
                    finally:
                        provider.close()

    def test_invalid_revoked_credential_and_cancellation_fail_closed(self):
        with LocalFixture() as fixture, patch.dict(os.environ, {
            "APP_ENV": "test",
            "MADAR_TEST_HTTP_PROVIDER_URL": fixture.base_url,
        }, clear=False):
            provider = fixture_provider(credential="revoked-token")
            with self.assertRaises(ProviderFetchError) as unauthorized:
                fetch_bounded_records(provider, resource_type="records")
            self.assertEqual(unauthorized.exception.category, ProviderErrorCategory.UNAUTHORIZED)
            provider.close()
            test_credential_store().revoke(AUTHORIZED_SOURCE)
            with self.assertRaises(ProviderFetchError) as revoked:
                get_provider("http_fixture", source_scope=AUTHORIZED_SOURCE)
            self.assertEqual(revoked.exception.category, ProviderErrorCategory.UNAUTHORIZED)

    def test_actual_http_timeout_is_bounded_and_redacted(self):
        with LocalFixture() as fixture, patch.dict(os.environ, {
            "APP_ENV": "test",
            "MADAR_TEST_HTTP_PROVIDER_URL": fixture.base_url,
        }, clear=False), patch(
            "services.provider_http_transport.REQUEST_TIMEOUT_SECONDS", 0.02,
        ):
            FixtureHandler.mode = "timeout"
            provider = fixture_provider()
            with self.assertRaises(ProviderFetchError) as caught:
                fetch_bounded_records(
                    provider, resource_type="records", timeout_seconds=0.2,
                )
            provider.close()
        self.assertEqual(caught.exception.category, ProviderErrorCategory.TIMEOUT)
        self.assertNotIn(TOKEN, str(caught.exception))

    def test_cancellation_stops_before_network_request(self):
        with LocalFixture() as fixture, patch.dict(os.environ, {
            "APP_ENV": "test",
            "MADAR_TEST_HTTP_PROVIDER_URL": fixture.base_url,
        }, clear=False):
            provider = fixture_provider(cancelled=lambda: True)
            with self.assertRaises(ProviderFetchError) as cancelled:
                fetch_bounded_records(provider, resource_type="records", cancelled=lambda: True)
            self.assertEqual(cancelled.exception.category, ProviderErrorCategory.CANCELLED)
            provider.close()

    def test_fixture_cannot_be_constructed_outside_tests(self):
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "MADAR_TEST_HTTP_PROVIDER_URL": "http://127.0.0.1:8080",
        }, clear=False):
            with self.assertRaises(ProviderFetchError) as caught:
                get_provider("http_fixture", source_scope=AUTHORIZED_SOURCE)
        self.assertEqual(caught.exception.category, ProviderErrorCategory.UNAVAILABLE)

    def test_fixture_credentials_are_source_scoped_rotatable_and_revocable(self):
        with patch.dict(os.environ, {"APP_ENV": "test"}, clear=False):
            store = TestCredentialStore()
            first = store.put(AUTHORIZED_SOURCE, TOKEN)
            second = store.rotate(AUTHORIZED_SOURCE, "rotated-fixture-token")
            self.assertEqual((first, second), (1, 2))
            self.assertNotIn("rotated-fixture-token", repr(store.resolve(AUTHORIZED_SOURCE)))
            foreign = AuthorizedSource(2, PROJECT, SOURCE, "http_fixture")
            with self.assertRaises(CredentialError):
                store.resolve(foreign)
            store.revoke(AUTHORIZED_SOURCE)
            with self.assertRaises(CredentialError) as revoked:
                store.resolve(AUTHORIZED_SOURCE)
            self.assertEqual(revoked.exception.code, "provider_credentials_revoked")


if __name__ == "__main__":
    unittest.main()

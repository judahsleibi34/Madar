"""Offline contracts for the public hosted-domain synthetic monitor."""

import importlib.util
import io
import json
import os
from pathlib import Path
import re
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest.mock import patch


WEB_ROOT = Path(
    os.getenv("MADAR_TEST_REPOSITORY_ROOT")
    or Path(__file__).resolve().parents[2]
).resolve()
SCRIPT = WEB_ROOT / "scripts/monitor_hosted_domains.py"
UNIT_ROOT = WEB_ROOT / "deployment/systemd"


def load_monitor():
    spec = importlib.util.spec_from_file_location("hosted_domain_monitor", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakePublicWeb:
    def __init__(self, *, release_sha="b" * 40):
        self.sha = release_sha
        self.changes = {}
        self.urls = []

    def __call__(self, url, *, read_version=False):
        self.urls.append(url)
        if url in self.changes:
            value = self.changes[url]
            if isinstance(value, BaseException):
                raise value
            return value
        if "/site/madar-demo/" in url:
            return response(308, location="https://madar-demo.madarportal.com/?probe=" + "a" * 32)
        if url.startswith("https://monitor-"):
            return response(404)
        if url.endswith("/health/version"):
            return response(200, body=(
                '{"release_sha":"' + self.sha + '","release_slot":"blue"}'
            ).encode())
        return response(200)


def response(code, *, body=b"", location=None, hsts="max-age=31536000"):
    headers = {"Strict-Transport-Security": hsts}
    if location is not None:
        headers["Location"] = location
    return {"code": code, "headers": headers, "body": body}


class HostedDomainMonitorTests(unittest.TestCase):
    def setUp(self):
        self.monitor = load_monitor()
        self.web = FakePublicWeb()

    def run_check(self):
        return self.monitor.run_monitor(
            requester=self.web, token_factory=lambda: "a" * 32
        )

    def assert_failed(self, name, error=None):
        result = self.run_check()
        self.assertEqual(result["status"], "unhealthy")
        self.assertEqual(result["probes"][name]["status"], "failed")
        if error:
            self.assertEqual(result["probes"][name]["error"], error)

    def test_expected_canonical_deep_api_isolation_and_redirect_pass(self):
        result = self.run_check()
        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["observed_release_sha"], "b" * 40)
        self.assertEqual(result["observed_release_slot"], "blue")
        self.assertTrue(all(p["status"] == "passed" for p in result["probes"].values()))
        self.assertEqual(result["probes"]["wrong_host"]["http_status"], 404)
        self.assertEqual(result["probes"]["unknown_tenant"]["http_status"], 404)
        self.assertEqual(result["probes"]["legacy_redirect"]["http_status"], 308)
        self.assertEqual(len(self.web.urls), 9)

    def test_deep_route_failure(self):
        self.web.changes["https://madar-demo.madarportal.com/shop"] = response(404)
        self.assert_failed("shop", "unexpected_http_status")

    def test_same_origin_api_http_failure(self):
        self.web.changes["https://madar-demo.madarportal.com/api/health/version"] = response(502)
        self.assert_failed("tenant_api_version", "unexpected_http_status")

    def test_release_identity_mismatch(self):
        self.web.changes["https://api.madarportal.com/health/version"] = response(
            200, body=b'{"release_sha":"' + b"c" * 40 + b'","release_slot":"blue"}'
        )
        self.assert_failed("release_identity", "release_identity_mismatch")

    def test_same_sha_with_opposite_slot_fails(self):
        self.web.changes["https://api.madarportal.com/health/version"] = response(
            200, body=b'{"release_sha":"' + b"b" * 40 + b'","release_slot":"green"}'
        )
        self.assert_failed("release_identity", "release_identity_mismatch")

    def test_wrong_host_returning_200_is_an_isolation_failure(self):
        self.web.changes[
            "https://monitor-" + "a" * 32 + ".madarportal.com/api/public/sites/madar-demo/bootstrap"
        ] = response(200)
        self.assert_failed("wrong_host", "unexpected_http_status")

    def test_wrong_host_and_unknown_tenant_404_pass(self):
        result = self.run_check()
        for name in ("wrong_host", "unknown_tenant"):
            self.assertEqual(result["probes"][name]["status"], "passed")

    def test_unknown_tenant_returning_200_fails(self):
        self.web.changes[
            "https://monitor-" + "a" * 32 + ".madarportal.com/api/public/sites/missing-" + "a" * 32 + "/bootstrap"
        ] = response(200)
        self.assert_failed("unknown_tenant", "unexpected_http_status")

    def test_legacy_must_be_308(self):
        self.web.changes[
            "https://madarportal.com/site/madar-demo/?probe=" + "a" * 32
        ] = response(301)
        self.assert_failed("legacy_redirect", "unexpected_http_status")

    def test_legacy_location_must_be_exact(self):
        self.web.changes[
            "https://madarportal.com/site/madar-demo/?probe=" + "a" * 32
        ] = response(308, location="https://other.madarportal.com/?probe=" + "a" * 32)
        self.assert_failed("legacy_redirect", "legacy_location_mismatch")

    def test_hsts_include_subdomains_fails(self):
        self.web.changes["https://madar-demo.madarportal.com/"] = response(
            200, hsts="max-age=31536000; includeSubDomains"
        )
        self.assert_failed("hsts", "include_subdomains_forbidden")

    def test_hsts_include_subdomains_on_api_also_fails(self):
        self.web.changes["https://api.madarportal.com/health/version"] = response(
            200,
            body=b'{"release_sha":"' + b"b" * 40 + b'","release_slot":"blue"}',
            hsts="max-age=31536000; includeSubDomains",
        )
        self.assert_failed("hsts", "include_subdomains_forbidden")

    def test_missing_hsts_fails(self):
        self.web.changes["https://madar-demo.madarportal.com/"] = response(200, hsts="")
        self.assert_failed("hsts", "hsts_max_age_missing")

    def test_bootstrap_http_failure(self):
        self.web.changes[
            "https://madar-demo.madarportal.com/api/public/sites/madar-demo/bootstrap"
        ] = response(503)
        self.assert_failed("bootstrap", "unexpected_http_status")

    def test_timeout_and_network_failure_are_reported_without_exception_text(self):
        self.web.changes["https://madar-demo.madarportal.com/about"] = TimeoutError("private detail")
        self.assert_failed("about", "network_error")
        result = self.run_check()
        self.assertNotIn("private detail", str(result))

    def test_malformed_version_json_fails(self):
        self.web.changes["https://api.madarportal.com/health/version"] = response(200, body=b"not json")
        self.assert_failed("explicit_api_version", "version_json_invalid")

    def test_missing_release_slot_fails(self):
        self.web.changes["https://api.madarportal.com/health/version"] = response(
            200, body=b'{"release_sha":"' + b"b" * 40 + b'"}'
        )
        self.assert_failed("explicit_api_version", "release_slot_invalid")

    def test_no_redirect_handler_blocks_redirect_following(self):
        self.assertIsNone(self.monitor.NoRedirect().redirect_request(None, None, 308, "", {}, "https://example.invalid"))

    def test_duplicate_hsts_headers_cannot_hide_include_subdomains(self):
        headers = self.monitor._response_headers([
            ("Strict-Transport-Security", "max-age=31536000"),
            ("Strict-Transport-Security", "includeSubDomains"),
        ])
        self.web.changes["https://madar-demo.madarportal.com/"] = {
            "code": 200, "headers": headers, "body": b"",
        }
        self.assert_failed("hsts", "include_subdomains_forbidden")

    def test_cli_emits_one_json_document_and_fails_nonzero(self):
        for status, expected_exit in (("healthy", 0), ("unhealthy", 1)):
            with self.subTest(status=status):
                output = io.StringIO()
                with patch.object(self.monitor, "run_monitor", return_value={"status": status}), redirect_stdout(output):
                    self.assertEqual(self.monitor.main(), expected_exit)
                self.assertEqual(json.loads(output.getvalue()), {"status": status})

    def test_systemd_and_installer_contract(self):
        service = (UNIT_ROOT / "madar-hosted-domain-monitor.service").read_text()
        timer = (UNIT_ROOT / "madar-hosted-domain-monitor.timer").read_text()
        installer = (WEB_ROOT / "deployment/bin/madar-install-control-plane").read_text()
        guard = (WEB_ROOT / "deployment/bin/madar-control-plane-guard").read_text()
        self.assertIn("Type=oneshot", service)
        self.assertIn("User=madar", service)
        self.assertIn("NoNewPrivileges=true", service)
        self.assertIn("ProtectSystem=strict", service)
        self.assertIn("OnFailure=madar-ops-alert@%n.service", service)
        self.assertIn("/usr/local/lib/madar/monitor_hosted_domains.py", service)
        self.assertIn("OnCalendar=*:0/5", timer)
        self.assertIn("madar-hosted-domain-monitor.service", installer)
        self.assertIn("madar-hosted-domain-monitor.timer", installer)
        self.assertIn("monitor_hosted_domains.py", installer)
        self.assertIn("web/scripts/monitor_hosted_domains.py", guard)
        self.assertNotIn("systemctl enable madar-hosted-domain-monitor", installer)

    def test_monitor_contains_no_mutation_or_embedded_credential(self):
        source = SCRIPT.read_text()
        self.assertIsNone(re.search(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])", source))
        self.assertIn("urllib.request.ProxyHandler({})", source)
        for forbidden in ("subprocess", "os.system", "Authorization", "Cookie", "POST", "PUT", "PATCH", "DELETE", "SUPABASE_SERVICE_KEY"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()

import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import httpx
from unittest.mock import patch

from fastapi.testclient import TestClient
import app as app_module
from services import business_write_authority as authority
from services import provider_recovery as recovery


class BusinessWriteAuthorityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "authority.json"
        self.data = {"version": 1, "schema": 115, "release_sha": "b" * 40,
                     "contract_digest": "a" * 64, "mode": "READ_ONLY"}
        self.write()
        patches = [patch.object(authority, "AUTHORITY_PATH", self.path),
            patch.dict(os.environ, {"MADAR_BUSINESS_WRITE_AUTHORITY": str(self.path),
                "MADAR_BUSINESS_WRITE_CONTRACT": "a" * 64, "MADAR_RELEASE_SHA": "b" * 40,
                "MADAR_RECOVERY_PROFILE": ""}),
            patch.object(Path, "lstat", return_value=SimpleNamespace(st_uid=0, st_mode=0o100644)),
            patch.object(Path, "is_symlink", return_value=False)]
        # Unit coverage only; acceptance exercises actual root-owned mounts.
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.client = TestClient(app_module.app)

    def write(self):
        self.path.write_text(json.dumps(self.data))

    def test_read_only_authority_uses_existing_request_and_provider_fences(self):
        self.assertTrue(authority.restricted() and recovery.restricted())
        response = self.client.post("/auth/signup", json={})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "provider_recovery_read_only")
        self.assertEqual(self.client.get("/health/recovery").json(),
                         {"restricted": True, "business_writes_enabled": False})

    def test_root_authority_transition_is_visible_without_process_restart(self):
        self.assertTrue(authority.restricted())
        self.data["mode"] = "NORMAL"
        self.write()
        self.assertFalse(authority.restricted())
        self.assertFalse(recovery.restricted())

    def test_modified_binding_denies_every_request(self):
        for field, value in [("mode", "ALLOW"), ("schema", 116), ("release_sha", "c" * 40),
                             ("contract_digest", "d" * 64), ("version", 2)]:
            with self.subTest(field=field):
                original = dict(self.data)
                self.data[field] = value
                self.write()
                with self.assertRaises(RuntimeError):
                    authority.read_authority()
                self.assertEqual(self.client.post("/auth/login", json={}).status_code, 503)
                self.data = original
                self.write()

    def test_missing_authority_is_fail_closed(self):
        self.path.unlink()
        self.assertEqual(self.client.post("/auth/login", json={}).status_code, 503)

    def test_untrusted_permissions_are_rejected(self):
        with patch.object(Path, "lstat", return_value=SimpleNamespace(st_uid=0, st_mode=0o100666)):
            with self.assertRaisesRegex(RuntimeError, "untrusted"):
                authority.read_authority()

    def test_recovery_profile_cannot_be_overridden_by_normal_authority(self):
        self.data["mode"] = "NORMAL"
        self.write()
        with patch.dict(os.environ, {"MADAR_RECOVERY_PROFILE": recovery.PROFILE}):
            self.assertTrue(recovery.restricted())
            with self.assertRaisesRegex(RuntimeError, "consumers_prohibited"):
                recovery.prohibit_worker_start()

    def test_ordinary_runtime_policy_is_unchanged(self):
        with patch.dict(os.environ, {"MADAR_BUSINESS_WRITE_AUTHORITY": "",
                "MADAR_BUSINESS_WRITE_CONTRACT": "", "MADAR_RECOVERY_PROFILE": ""}):
            self.assertIsNone(authority.read_authority())
            self.assertFalse(recovery.restricted())

    def test_only_reviewed_business_reads_are_admitted_during_transition(self):
        for path in ("/notifications", "/calendar/bootstrap", "/builder/reservations",
                     "/builder/projects/fixture/form-submissions", "/ecommerce/catalog", "/ecommerce/orders"):
            self.assertTrue(recovery.request_allowed("GET", path), path)
            self.assertFalse(recovery.request_allowed("POST", path), path)
            with patch.dict(os.environ, {"MADAR_RECOVERY_PROFILE": recovery.PROFILE}):
                self.assertFalse(recovery.request_allowed("GET", path), path)
        for path in ("/calendar/oauth/google/callback", "/notifications/preferences", "/screen-time/heartbeat", "/public/contact"):
            self.assertFalse(recovery.request_allowed("GET", path), path)

    def test_read_only_commercial_rpc_has_no_general_rpc_exemption(self):
        marker = recovery.REQUEST_OPERATION.set(("GET", "/ecommerce/catalog"))
        self.addCleanup(recovery.REQUEST_OPERATION.reset, marker)
        request = httpx.Request("POST", "http://madar-supabase:8000/rest/v1/rpc/resolve_commercial_access",
                                json={"p_tenant_id": 1})
        self.assertTrue(recovery.provider_request_allowed(request))
        with patch.dict(os.environ, {"MADAR_RECOVERY_PROFILE": recovery.PROFILE}):
            self.assertFalse(recovery.provider_request_allowed(request))
        for payload in ({"p_tenant_id": True}, {"p_tenant_id": 1, "command": {}}, {"p_tenant_id": -1}):
            self.assertFalse(recovery.provider_request_allowed(httpx.Request("POST", str(request.url), json=payload)))
        self.assertFalse(recovery.provider_request_allowed(httpx.Request(
            "POST", "http://madar-supabase:8000/rest/v1/rpc/apply_commercial_access_command", json={})))

    def test_calendar_read_does_not_create_default_calendar(self):
        from datetime import datetime, timezone
        from routes import calendar_routes
        # Stop after the calendar lookup; this tests the actual read handler's
        # first boundary without fabricating downstream tenant/customer data.
        with patch.object(calendar_routes, "ensure_default_calendar") as create, patch.object(
                calendar_routes, "list_accessible_calendars", side_effect=RuntimeError("lookup boundary")):
            with self.assertRaisesRegex(RuntimeError, "lookup boundary"):
                calendar_routes._calendar_workspace_payload(SimpleNamespace(),
                    datetime.now(timezone.utc), datetime.now(timezone.utc))
            create.assert_not_called()

    def test_worker_consumption_follows_root_authority_without_restart(self):
        self.assertFalse(recovery.worker_consumption_allowed())
        self.data["mode"] = "NORMAL"
        self.write()
        self.assertTrue(recovery.worker_consumption_allowed())
        self.path.unlink()
        self.assertFalse(recovery.worker_consumption_allowed())

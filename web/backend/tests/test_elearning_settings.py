import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from routes import elearning_routes as routes
from services import elearning_settings_service as service


class ELearningSettingsTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(routes.router)
        self.client = TestClient(app)
        self.context = SimpleNamespace(tenant_id=17, user_id=3, role="owner")
        self.auth = patch.object(routes, "require_active_tenant_member", return_value=self.context)
        self.auth_mock = self.auth.start()
        self.addCleanup(self.auth.stop)
        management = patch.object(routes, "management_profile", return_value=None)
        self.management_mock = management.start()
        self.addCleanup(management.stop)
        self.availability = patch.object(service, "settings_available", return_value=True)
        self.availability.start()
        self.addCleanup(self.availability.stop)

    def test_reads_and_writes_use_session_tenant(self):
        values = service.ELearningSettings(platform_name="Shared Learning", course_label="Workshop").model_dump(mode="json")
        with patch.object(service, "get_settings", return_value=values) as read:
            result = self.client.get("/elearning/settings")
        self.assertEqual(result.json()["settings"]["course_label"], "Workshop")
        read.assert_called_once_with(17)
        with patch.object(service, "save_settings", return_value=values) as save, patch.object(routes, "record_audit_event"):
            result = self.client.put("/elearning/settings", json=values)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(save.call_args.args[0], 17)
        self.assertFalse(self.auth_mock.call_args.kwargs["allow_admin_account_access"])

    def test_member_and_viewer_cannot_read_or_save(self):
        for role in ["member", "viewer", ""]:
            self.context.role = role
            for method in ["get", "put"]:
                with self.subTest(role=role, method=method), patch.object(service, "get_settings") as read, patch.object(service, "save_settings") as save:
                    response = getattr(self.client, method)("/elearning/settings", **({"json": {}} if method == "put" else {}))
                    self.assertEqual(response.status_code, 403)
                    read.assert_not_called()
                    save.assert_not_called()
                    self.management_mock.assert_not_called()

    def test_management_metadata_uses_authenticated_tenant_without_initializing_builder(self):
        self.management_mock.return_value = {"subdomain": "testing", "landing_project": None}
        with patch.object(service, "get_settings", return_value={}):
            response = self.client.get("/elearning/settings")
        self.assertEqual(response.json()["academy_management"]["subdomain"], "testing")
        self.management_mock.assert_called_once_with(17)

    def test_admin_can_save(self):
        self.context.role = "admin"
        with patch.object(service, "save_settings", return_value={}), patch.object(routes, "record_audit_event"):
            self.assertEqual(self.client.put("/elearning/settings", json={}).status_code, 200)

    def test_email_domain_mode_normalizes_and_saves_for_session_tenant(self):
        payload = {"academy_registration": "email_domain", "academy_email_domains": [" @University.EDU ", "university.edu", "Jack@UNIVERSITY.edu", "COLLEGE.edu", "bücher.de", "jack@bücher.de"]}
        with patch.object(service, "save_settings", return_value={}) as save, patch.object(routes, "record_audit_event"):
            response = self.client.put("/elearning/settings", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(save.call_args.args[0], 17)
        self.assertEqual(save.call_args.args[1].academy_email_domains, ["university.edu", "college.edu", "xn--bcher-kva.de"])

    def test_email_domain_mode_rejects_empty_invalid_and_excessive_domains(self):
        for domains in [[], [""], ["jack@@university.edu"], ["Jack <jack@university.edu>"], ["jack@university.edu/path"], ["https://university.edu"], ["*.university.edu"], ["localhost"], ["university.edu/path"], [f"school{i}.edu" for i in range(21)]]:
            with self.subTest(domains=domains), patch.object(service, "save_settings") as save:
                response = self.client.put("/elearning/settings", json={"academy_registration": "email_domain", "academy_email_domains": domains})
                self.assertEqual(response.status_code, 422)
                save.assert_not_called()

    def test_unauthenticated_request_fails(self):
        self.auth_mock.side_effect = HTTPException(status_code=401, detail="Authentication required")
        self.assertEqual(self.client.get("/elearning/settings").status_code, 401)

    def test_validation_rejects_invalid_values_and_tenant_override(self):
        for payload in [{"tenant_id": 99}, {"default_passing_score": -1}, {"default_passing_score": 101}, {"default_passing_score": 70.5}, {"default_passing_score": True}, {"enabled": "true"}, {"course_label": "  "}, {"platform_name": "x" * 121}, {"description": "x" * 2001}, {"logo_url": "javascript:alert(1)"}]:
            with self.subTest(payload=payload), patch.object(service, "save_settings") as save:
                self.assertIn(self.client.put("/elearning/settings", json=payload).status_code, [400, 422])
                save.assert_not_called()

    def test_bridge_defaults_and_fail_closed_save(self):
        with patch.object(service, "settings_available", return_value=False), patch.object(service, "get_settings") as read, patch.object(service, "save_settings") as save:
            response = self.client.get("/elearning/settings")
            self.assertFalse(response.json()["available"])
            self.assertFalse(response.json()["settings"]["enabled"])
            read.assert_not_called()
            self.assertEqual(self.client.put("/elearning/settings", json={}).status_code, 503)
            save.assert_not_called()

    def test_database_read_is_tenant_scoped_and_future_keys_survive_save(self):
        client = MagicMock()
        query = client.table.return_value
        query.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"settings": {"course_label": "Workshop", "future_setting": True}}]
        with patch.object(service, "service_supabase", client):
            self.assertEqual(service.get_settings(17)["course_label"], "Workshop")
            query.select.return_value.eq.assert_called_once_with("tenant_id", 17)
            service.save_settings(17, service.ELearningSettings())
            client.rpc.assert_called_once_with("save_elearning_settings", {"p_tenant_id": 17, "p_settings": service.ELearningSettings().model_dump(mode="json")})

    def test_database_failure_returns_safe_error(self):
        with patch.object(service, "get_settings", side_effect=RuntimeError("internal SQL secret")):
            response = self.client.get("/elearning/settings")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret", response.text)


    def test_managed_logo_requires_registered_image_owned_by_the_tenant(self):
        own_url = "/uploads/tenant_17/builder_assets/" + "a" * 32 + ".png"
        client = MagicMock()
        query = client.table.return_value
        query.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"id": "asset", "status": "unreferenced", "mime_type": "image/png"}]
        with patch.object(service, "service_supabase", client):
            values = service.ELearningSettings(logo_url=own_url)
            self.assertEqual(service.save_settings(17, values)["logo_url"], own_url)
            client.rpc.assert_called_once()
            client.rpc.reset_mock()
            with self.assertRaises(HTTPException):
                service.save_settings(18, values)
            client.rpc.assert_not_called()
            query.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"id": "asset", "status": "soft_deleted", "mime_type": "image/png"}]
            with self.assertRaises(HTTPException):
                service.save_settings(17, values)
            client.rpc.assert_not_called()

    def test_unmanaged_relative_logo_and_nonimage_asset_are_rejected(self):
        for url in ["/uploads/logo.png", "/other/logo.png", "/uploads/tenant_17/builder_assets/" + "a" * 32 + ".pdf"]:
            with self.subTest(url=url), self.assertRaises((ValueError, HTTPException)):
                service.ELearningSettings(logo_url=url)

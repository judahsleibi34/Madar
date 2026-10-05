import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from routes import elearning_directory_routes as routes
from services import elearning_directory_service as service, elearning_access_service as access
from tests.test_elearning_courses import Client


class ELearningDirectoryTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI(); app.include_router(routes.router)
        self.http = TestClient(app)
        self.db = Client()
        self.context = SimpleNamespace(tenant_id=17, user_id=3, role="owner")
        for item in (patch.object(access, "require_active_tenant_member", return_value=self.context), patch.object(service, "service_supabase", self.db), patch.object(service, "directory_available", return_value=True), patch.object(service, "settings_available", return_value=True), patch.object(routes, "record_audit_event")):
            item.start(); self.addCleanup(item.stop)

    def create(self, kind):
        payload = {"name": "Local record", "description": "Details"}
        if kind == "instructors": payload["email"] = "teacher@example.com"
        result = self.http.post(f"/elearning/{kind}", json=payload)
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()["item"]

    def test_both_directories_create_read_update_archive_and_restore(self):
        for kind in ("groups", "instructors"):
            with self.subTest(kind=kind):
                row = self.create(kind)
                base = f"/elearning/{kind}"
                self.assertEqual((row["tenant_id"], row["created_by"], row["status"]), (17, 3, "active"))
                self.assertTrue(self.http.get(base).json()["available"])
                self.assertEqual(self.http.get(f"{base}/{row['id']}").json()["item"], row)
                response = self.http.put(f"{base}/{row['id']}", json={"name": "Updated", "expected_revision": 1})
                self.assertEqual(response.json()["item"]["revision"], 2)
                response = self.http.post(f"{base}/{row['id']}/archive", json={"expected_revision": 2})
                self.assertEqual(response.json()["item"]["status"], "archived")
                response = self.http.put(f"{base}/{row['id']}", json={"name": "Restored", "status": "active", "expected_revision": 3})
                self.assertEqual(response.json()["item"]["status"], "active")
                self.assertEqual(self.http.delete(f"{base}/{row['id']}").status_code, 422)

    def test_group_delete_context_confirmation_and_bridge(self):
        row = self.create("groups")
        url = f"/elearning/groups/{row['id']}"
        with patch.object(service, "delete_group", return_value=row) as delete:
            self.assertEqual(self.http.request("DELETE", url, json={"expected_revision": 1, "confirmed": True}).status_code, 200)
            self.assertEqual(delete.call_args.args[:3], (17, 3, __import__('uuid').UUID(row['id'])))
            self.context.role = "member"
            self.assertEqual(self.http.request("DELETE", url, json={"expected_revision": 1, "confirmed": True}).status_code, 403)
            self.context.role = "owner"
            self.assertEqual(self.http.request("DELETE", url, json={"expected_revision": 1, "confirmed": "yes"}).status_code, 422)
        with patch.object(service, "settings_available", return_value=False):
            self.assertEqual(self.http.request("DELETE", url, json={"expected_revision": 1, "confirmed": True}).status_code, 503)
            self.assertEqual(self.http.post('/elearning/groups', json={"name": "New"}).status_code, 503)

    def test_duplicate_database_error_is_safe_and_distinct(self):
        from postgrest.exceptions import APIError
        with patch.object(service, "table", side_effect=APIError({"code": "23505", "message": "elearning_group_name_exists", "details": "private", "hint": "private"})):
            response = self.http.post('/elearning/groups', json={"name": "Duplicate"})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['detail']['code'], 'elearning_group_name_exists')
            self.assertNotIn('private', response.text)

    def test_instructor_delete_authorization_and_bridge(self):
        row = self.create('instructors')
        url = f"/elearning/instructors/{row['id']}"
        command = {"expected_revision": 1, "confirmed": True}
        with patch.object(service, 'delete_instructor', return_value=row) as delete:
            self.assertEqual(self.http.request('DELETE', url, json=command).status_code, 200)
            self.assertEqual(delete.call_args.args[:2], (17, 3))
            self.context.role = 'member'
            self.assertEqual(self.http.request('DELETE', url, json=command).status_code, 403)
            self.context.role = 'owner'
            self.assertEqual(self.http.request('DELETE', url, json={**command, 'confirmed': 'yes'}).status_code, 422)
        with patch.object(service, 'settings_available', return_value=False):
            self.assertEqual(self.http.request('DELETE', url, json=command).status_code, 503)

    def test_tenant_isolation_and_stale_revisions(self):
        for kind in ("groups", "instructors"):
            self.context.tenant_id = 17
            row = self.create(kind); base = f"/elearning/{kind}"
            self.http.post(f"{base}/{row['id']}/archive", json={"expected_revision": 1})
            self.assertEqual(self.http.put(f"{base}/{row['id']}", json={"name": "Stale", "expected_revision": 1}).status_code, 409)
            self.assertEqual(self.http.post(f"{base}/{row['id']}/archive", json={"expected_revision": 1}).status_code, 409)
            self.context.tenant_id = 18
            self.assertEqual(self.http.get(base).json()["items"], [])
            self.assertEqual(self.http.get(f"{base}/{row['id']}").status_code, 404)
            self.assertEqual(self.http.put(f"{base}/{row['id']}", json={"name": "Stolen", "expected_revision": 2}).status_code, 404)
            self.assertEqual(self.http.post(f"{base}/{row['id']}/archive", json={"expected_revision": 2}).status_code, 404)

    def test_bridge_never_queries_missing_tables(self):
        with patch.object(service, "directory_available", return_value=False), patch.object(service, "table") as table:
            for kind in ("groups", "instructors"):
                base = f"/elearning/{kind}"; item = "00000000-0000-0000-0000-000000000001"
                self.assertEqual(self.http.get(base).json(), {"available": False, "items": [], "has_more": False})
                for response in (self.http.post(base, json={"name": "New"}), self.http.get(f"{base}/{item}"), self.http.put(f"{base}/{item}", json={"name": "Edit", "expected_revision": 1}), self.http.post(f"{base}/{item}/archive", json={"expected_revision": 1})):
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response.json()["detail"]["code"], "elearning_directory_upgrade_required")
            table.assert_not_called()

    def test_role_auth_and_payload_validation(self):
        for kind in ("groups", "instructors"):
            base = f"/elearning/{kind}"
            for role in ("member", "viewer", "instructor"):
                self.context.role = role
                self.assertEqual(self.http.get(base).status_code, 403)
                self.assertEqual(self.http.post(base, json={"name": "New"}).status_code, 403)
            self.context.role = "admin"
            for payload in ({"name": " "}, {"name": "New", "tenant_id": 18}, {"name": "New", "created_by": 9}, {"name": "New", "status": "invalid"}):
                self.assertEqual(self.http.post(base, json=payload).status_code, 422)
            archived = self.http.post(base, json={"name": "Archive", "status": "archived"})
            self.assertEqual(archived.status_code, 200)
            self.assertEqual(archived.json()["item"]["status"], "archived")
            self.assertEqual(self.http.get(base+'?limit=101').status_code, 422)
        self.assertEqual(self.http.post('/elearning/instructors', json={"name": "Invalid", "email": "bad"}).status_code, 422)
        with patch.object(access, "require_active_tenant_member", side_effect=HTTPException(401, "Authentication required")):
            self.assertEqual(self.http.get('/elearning/groups').status_code, 401)

    def test_database_errors_are_redacted(self):
        with patch.object(service, "list_items", side_effect=RuntimeError("SQL secret")):
            response = self.http.get('/elearning/groups')
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("secret", response.text)

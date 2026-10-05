import unittest
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from services import elearning_structure_service as service, elearning_access_service as access
from routes import elearning_structure_routes as routes


class ELearningStructureTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI(); app.include_router(routes.router)
        self.http = TestClient(app)
        self.course, self.item = str(uuid4()), str(uuid4())
        self.base = f"/elearning/courses/{self.course}"
        self.member = SimpleNamespace(tenant_id=17, user_id=3, role="owner")
        self.db = MagicMock()
        self.snapshot = {"available": True, "revision": 2, "sections": [], "section_count": 0, "lesson_count": 0}
        self.db.rpc.return_value.execute.return_value.data = self.snapshot
        for item in (patch.object(access, "require_active_tenant_member", return_value=self.member), patch.object(service, "service_supabase", self.db), patch.object(service, "structure_available", return_value=True), patch.object(routes, "record_audit_event")):
            item.start(); self.addCleanup(item.stop)

    def command(self, action="create_section", **values):
        return self.http.post(self.base + "/structure/commands", json={"action": action, "expected_revision": 1, "payload": {"name": "Level 1"}, **values})

    def test_commands_supply_session_identity_and_return_atomic_snapshot(self):
        self.assertEqual(self.command().json(), self.snapshot)
        args = self.db.rpc.call_args.args
        self.assertEqual(args[0], "manage_elearning_structure")
        self.assertEqual(args[1], {"p_tenant_id": 17, "p_course_id": self.course, "p_user_id": 3, "p_expected_revision": 1, "p_action": "create_section", "p_entity_id": None, "p_payload": {"name": "Level 1", "description": "", "status": "draft"}})

    def test_reads_and_all_roles_are_scoped(self):
        self.http.get(self.base + "/structure")
        self.db.rpc.assert_called_with("get_elearning_structure", {"p_tenant_id": 17, "p_course_id": self.course})
        for role in ("member", "viewer", "instructor"):
            self.member.role = role
            self.assertEqual(self.http.get(self.base + "/structure").status_code, 403)
            self.assertEqual(self.command().status_code, 403)
        self.member.role = "admin"
        self.assertEqual(self.command().status_code, 200)
        with patch.object(access, "require_active_tenant_member", side_effect=HTTPException(401, "Authentication required")):
            self.assertEqual(self.command().status_code, 401)

    def test_rejects_untrusted_positions_tenant_ids_and_invalid_commands(self):
        cases = [{"tenant_id": 2}, {"expected_revision": True}, {"expected_revision": 0}, {"entity_id": self.item}, {"payload": {"name": " ", "position": 8}}, {"payload": {"name": "New", "tenant_id": 2}}, {"payload": {"name": "New", "status": "archived"}}, {"action": "delete_section", "entity_id": self.item, "payload": {"confirmed": False}}, {"action": "delete_section", "entity_id": self.item, "payload": {"confirmed": 1}}, {"action": "move_lesson", "entity_id": self.item, "payload": {"section_id": "invalid"}}, {"action": "reorder_section", "entity_id": self.item, "payload": {"direction": "sideways"}}]
        for values in cases:
            with self.subTest(values=values): self.assertEqual(self.command(**values).status_code, 422)
        self.db.rpc.assert_not_called()

    def test_schema_bridge_queries_no_new_rpc(self):
        with patch.object(service, "structure_available", return_value=False), patch.object(service, "settings_available", return_value=True):
            self.db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"id": self.course}]
            self.assertFalse(self.http.get(self.base + "/structure").json()["available"])
            self.assertEqual(self.command().status_code, 503)
            self.assertEqual(self.http.get(self.base + f"/lessons/{self.item}").status_code, 503)
            self.db.rpc.assert_not_called()

    def test_pre117_read_fails_closed_without_querying_course_table(self):
        with patch.object(service, "structure_available", return_value=False), patch.object(service, "settings_available", return_value=False):
            self.assertEqual(self.http.get(self.base + "/structure").status_code, 503)
            self.db.table.assert_not_called()
            self.db.rpc.assert_not_called()

    def test_sql_errors_map_to_conflict_not_found_and_redacted_errors(self):
        for code,message,status in (("P0001", "elearning_structure_conflict", 409), ("P0001", "elearning_section_not_empty", 409), ("P0002", "missing", 404), ("42501", "denied", 403), ("23514", "invalid", 400), ("XX000", "internal SQL secret", 503)):
            self.db.rpc.return_value.execute.side_effect = APIError({"code":code,"message":message,"details":None,"hint":None})
            result = self.command()
            self.assertEqual(result.status_code,status)
            self.assertNotIn("internal SQL secret",result.text)

    def test_generic_lesson_placeholder_requires_owned_structure(self):
        self.snapshot["sections"] = [{"id": "section", "name": "Section", "lessons": [{"id": self.item, "name": "Generic lesson"}]}]
        result = self.http.get(self.base + f"/lessons/{self.item}")
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()["lesson"]["name"], "Generic lesson")
        self.assertEqual(self.http.get(self.base + f"/lessons/{uuid4()}").status_code,404)

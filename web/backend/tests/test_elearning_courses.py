import unittest
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from routes import elearning_courses_routes as routes
from services import elearning_courses_service as service, elearning_access_service as access, elearning_settings_service as settings


class Query:
    def __init__(self, client, table):
        self.client, self.table = client, table
        self.filters, self.payload, self.kind, self.bounds = [], None, "select", None
    def select(self, *_args): return self
    def eq(self, key, value): self.filters.append((key, value)); return self
    def order(self, *_args, **_kwargs): return self
    def range(self, start, end): self.bounds = (start, end + 1); return self
    def limit(self, limit): self.bounds = (0, limit); return self
    def insert(self, payload): self.kind, self.payload = "insert", payload; return self
    def update(self, payload): self.kind, self.payload = "update", payload; return self
    def execute(self):
        self.client.queries.append((self.table, self.kind, self.filters))
        rows = self.client.rows.setdefault(self.table, [])
        if self.kind == "insert":
            now = datetime.now(timezone.utc).isoformat()
            row = {"id": str(uuid4()), "revision": 1, "created_at": now, "updated_at": now, **self.payload}
            rows.insert(0, row)
            return SimpleNamespace(data=[deepcopy(row)])
        selected = [row for row in rows if all(row.get(key) == value for key, value in self.filters)]
        if self.bounds: selected = selected[self.bounds[0]:self.bounds[1]]
        if self.kind == "update":
            for row in selected: row.update(self.payload)
        return SimpleNamespace(data=deepcopy(selected))


class Client:
    def __init__(self): self.rows, self.queries = {}, []
    def table(self, name): return Query(self, name)


class ELearningCourseTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI(); app.include_router(routes.router)
        self.http = TestClient(app)
        self.db = Client()
        self.context = SimpleNamespace(tenant_id=17, user_id=3, role="owner")
        self.auth = patch.object(access, "require_active_tenant_member", return_value=self.context)
        self.auth_mock = self.auth.start(); self.addCleanup(self.auth.stop)
        for item in [patch.object(service, "service_supabase", self.db), patch.object(settings, "service_supabase", self.db), patch.object(service, "courses_available", return_value=True), patch.object(service, "settings_available", return_value=True), patch.object(service, "structure_available", return_value=False), patch.object(service, "participation_available", return_value=False), patch.object(routes, "record_audit_event")]:
            item.start(); self.addCleanup(item.stop)

    def create(self, **extra):
        response = self.http.post("/elearning/courses", json={"name": "English Course", **extra})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["course"]

    def test_create_list_update_duplicate_archive_are_tenant_owned(self):
        course = self.create()
        self.assertEqual(course["tenant_id"], 17)
        self.assertTrue(course["deletion_available"])
        self.assertEqual(course["created_by"], 3)
        self.assertEqual(course["access_type"], "private")
        self.assertEqual(course["status"], "draft")
        self.assertEqual(course["section_count"], 0)
        result = self.http.get("/elearning/courses").json()
        self.assertEqual(result["courses"][0]["id"], course["id"])
        self.assertTrue(result["available"])
        edited = self.http.put(f"/elearning/courses/{course['id']}", json={"name": "English Program", "status": "published", "access_type": "paid", "expected_revision": 1})
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["course"]["revision"], 2)
        self.assertTrue(edited.json()["course"]["deletion_available"])
        duplicate = self.http.post(f"/elearning/courses/{course['id']}/duplicate", json={"expected_revision": 2})
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json()["course"]["status"], "draft")
        self.assertEqual(duplicate.json()["course"]["name"], "Copy of English Program")
        archived = self.http.post(f"/elearning/courses/{course['id']}/archive", json={"expected_revision": 2})
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(archived.json()["course"]["status"], "archived")
        self.assertTrue(archived.json()["course"]["deletion_available"])
        self.assertEqual(len(self.db.rows["elearning_courses"]), 2)
        self.assertEqual(self.http.delete(f"/elearning/courses/{course['id']}").status_code, 422)
        self.assertFalse(self.auth_mock.call_args.kwargs["allow_admin_account_access"])

    def test_other_tenant_cannot_list_read_edit_archive_or_duplicate(self):
        course = self.create()
        self.context.tenant_id = 18
        self.assertEqual(self.http.get("/elearning/courses").json()["courses"], [])
        self.assertEqual(self.http.get(f"/elearning/courses/{course['id']}").status_code, 404)
        self.assertEqual(self.http.put(f"/elearning/courses/{course['id']}", json={"name": "Stolen", "expected_revision": 1}).status_code, 404)
        for action in ["archive", "duplicate"]:
            self.assertEqual(self.http.post(f"/elearning/courses/{course['id']}/{action}", json={"expected_revision": 1}).status_code, 404)
        self.assertEqual(self.db.rows["elearning_courses"][0]["name"], "English Course")

    def test_stale_revision_rejects_mutations(self):
        course = self.create()
        self.http.post(f"/elearning/courses/{course['id']}/archive", json={"expected_revision": 1})
        for action in ["archive", "duplicate"]:
            self.assertEqual(self.http.post(f"/elearning/courses/{course['id']}/{action}", json={"expected_revision": 1}).status_code, 409)
        self.assertEqual(self.http.put(f"/elearning/courses/{course['id']}", json={"name": "Stale", "expected_revision": 1}).status_code, 409)
        self.assertEqual(self.db.rows["elearning_courses"][0]["status"], "archived")

    def test_pre117_list_is_empty_and_all_writes_fail_without_querying_course_table(self):
        with patch.object(service, "courses_available", return_value=False):
            self.assertEqual(self.http.get("/elearning/courses").json(), {"available": False, "courses": [], "has_more": False})
            self.assertEqual(self.http.post("/elearning/courses", json={"name": "Bridge"}).status_code, 503)
            course_id = str(uuid4())
            self.assertEqual(self.http.get(f"/elearning/courses/{course_id}").status_code, 503)
            self.assertEqual(self.http.put(f"/elearning/courses/{course_id}", json={"name": "Bridge", "expected_revision": 1}).status_code, 503)
            for action in ["archive", "duplicate"]:
                self.assertEqual(self.http.post(f"/elearning/courses/{course_id}/{action}", json={"expected_revision": 1}).status_code, 503)
        self.assertEqual(self.db.queries, [])

    def test_role_and_unauthenticated_permissions_fail_closed(self):
        for role in ["member", "viewer", ""]:
            self.context.role = role
            self.assertEqual(self.http.get("/elearning/courses").status_code, 403)
            self.assertEqual(self.http.post("/elearning/courses", json={"name": "Denied"}).status_code, 403)
        self.auth_mock.side_effect = HTTPException(status_code=401, detail="Authentication required")
        self.assertEqual(self.http.get("/elearning/courses").status_code, 401)
        self.assertEqual(self.db.queries, [])

    def test_validation_and_tenant_override(self):
        for payload in [{"name": ""}, {"name": "  "}, {"name": "x" * 121}, {"name": "Valid", "tenant_id": 18}, {"name": "Valid", "status": "unknown"}, {"name": "Valid", "access_type": "public"}, {"name": "Valid", "cover_asset": "https://example.com/cover.png"}]:
            self.assertEqual(self.http.post("/elearning/courses", json=payload).status_code, 422)
        self.assertEqual(self.http.post("/elearning/courses", json={"name": "Valid", "status": "archived"}).status_code, 400)

    def test_covers_require_existing_tenant_owned_image_registry_entry(self):
        own_url = "/uploads/tenant_17/builder_assets/" + "a" * 32 + ".png"
        self.assertEqual(self.http.post("/elearning/courses", json={"name": "Image", "cover_asset": own_url}).status_code, 400)
        self.db.rows["builder_assets"] = [{"id": "asset", "tenant_id": 17, "storage_key": own_url.removeprefix("/uploads/"), "mime_type": "image/png", "status": "unreferenced"}]
        course = self.create(cover_asset=own_url)
        self.assertEqual(course["cover_asset"], own_url)
        self.context.tenant_id = 18
        self.assertEqual(self.http.post("/elearning/courses", json={"name": "Image", "cover_asset": own_url}).status_code, 400)

    def test_pagination_and_database_failure_do_not_expose_details(self):
        for index in range(3): self.create(name=f"Course {index}")
        result = self.http.get("/elearning/courses?limit=2").json()
        self.assertEqual(len(result["courses"]), 2); self.assertTrue(result["has_more"])
        self.assertEqual(len(self.http.get("/elearning/courses?limit=2&offset=2").json()["courses"]), 1)
        with patch.object(service, "list_courses", side_effect=RuntimeError("internal SQL secret")):
            result = self.http.get("/elearning/courses")
        self.assertEqual(result.status_code, 503); self.assertNotIn("secret", result.text)

    def test_structure_counts_are_batched_scoped_and_retained_on_metadata_edit(self):
        first, second = self.create(), self.create(name="Second")
        rpc = MagicMock()
        rpc.return_value.execute.return_value.data = {first["id"]: {"section_count": 2, "lesson_count": 5}, second["id"]: {"section_count": 1, "lesson_count": 3}}
        with patch.object(service, "structure_available", return_value=True), patch.object(self.db, "rpc", rpc, create=True):
            result = self.http.get("/elearning/courses").json()["courses"]
            self.assertEqual({row["id"]: row["lesson_count"] for row in result}, {first["id"]: 5, second["id"]: 3})
            rpc.assert_called_once_with("get_elearning_course_counts", {"p_tenant_id": 17, "p_course_ids": [second["id"], first["id"]]})
            edited = self.http.put(f"/elearning/courses/{first['id']}", json={"name": "Changed", "expected_revision": 1}).json()["course"]
            self.assertEqual(edited["section_count"], 2)
            self.assertEqual(edited["lesson_count"], 5)


class ELearningCourseSchemaGateTests(unittest.TestCase):
    def test_settings_are_available_on_116_but_courses_require_117(self):
        database = Client()
        with patch.object(settings, "service_supabase", database):
            for schema_version, course_available in [(114, False), (115, False), (116, False), (117, True)]:
                database.rows["application_schema_state"] = [{"contract_key": "core", "schema_version": schema_version}]
                self.assertEqual(service.courses_available(), course_available)
                self.assertEqual(settings.settings_available(), schema_version >= 116)

class CourseDeletionAPITests(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.include_router(routes.router);self.http=TestClient(app)
        self.course=str(uuid4());self.db=MagicMock();self.member=SimpleNamespace(tenant_id=17,user_id=3,role='owner')
        self.payload={'expected_revision':1,'expected_structure_revision':2,'confirmation_name':'English','confirmed':True}
        self.db.rpc.return_value.execute.return_value.data={'id':self.course,'deleted':True}
        for item in (patch.object(access,'require_active_tenant_member',return_value=self.member),patch.object(service,'service_supabase',self.db),patch.object(service,'settings_available',return_value=True),patch.object(routes,'record_audit_event')):
            item.start();self.addCleanup(item.stop)

    def test_delete_supplies_session_identity_and_requires_confirmation(self):
        response=self.http.request('DELETE',f'/elearning/courses/{self.course}',json=self.payload)
        self.assertEqual(response.status_code,200)
        self.db.rpc.assert_called_once_with('delete_elearning_course',{'p_tenant_id':17,'p_course_id':self.course,'p_user_id':3,'p_expected_revision':1,'p_expected_structure_revision':2,'p_confirmation_name':'English','p_confirmed':True})
        self.db.rpc.reset_mock()
        for extra in ({'confirmed':False},{'confirmed':1},{'tenant_id':18},{'expected_revision':True},{'confirmation_name':''}):
            response=self.http.request('DELETE',f'/elearning/courses/{self.course}',json={**self.payload,**extra})
            self.assertIn(response.status_code,(400,422))
        self.db.rpc.assert_not_called()

    def test_pre121_and_members_fail_closed(self):
        with patch.object(service,'settings_available',return_value=False):
            self.assertEqual(self.http.request('DELETE',f'/elearning/courses/{self.course}',json=self.payload).status_code,503)
        self.member.role='member'
        self.assertEqual(self.http.request('DELETE',f'/elearning/courses/{self.course}',json=self.payload).status_code,403)
        self.db.rpc.assert_not_called()

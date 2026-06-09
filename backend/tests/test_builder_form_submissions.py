import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes import builder_routes, public_site_routes
from services.tenant_service import TenantContext


FORM_ID = "form_contact"
PROJECT_ID = "11111111-1111-4111-8111-111111111111"
SUBMISSION_ID = "22222222-2222-4222-8222-222222222222"


PUBLISHED_SCHEMA = {
    "forms": [
        {
            "id": FORM_ID,
            "title": "Contact form",
            "sections": [
                {
                    "id": "section_1",
                    "title": "Section 1",
                    "fields": [
                        {
                            "id": "field_name",
                            "label": "Full name",
                            "type": "shortText",
                            "required": True,
                        },
                        {
                            "id": "field_email",
                            "label": "Email",
                            "type": "email",
                            "required": False,
                        },
                    ],
                }
            ],
            "responses": [
                {
                    "id": "sample",
                    "status": "Sample",
                    "answers": {"field_name": "Sample"},
                }
            ],
        }
    ],
    "pages": [
        {
            "id": "page_home",
            "sections": [
                {
                    "id": "section_page",
                    "rows": [
                        {
                            "columns": [
                                {
                                    "elements": [
                                        {
                                            "id": "element_form",
                                            "type": "formBlock",
                                            "connectedFormId": FORM_ID,
                                        }
                                    ]
                                }
                            ]
                        }
                    ],
                }
            ],
        }
    ],
}


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, supabase, table_name):
        self.supabase = supabase
        self.table_name = table_name
        self.filters = []
        self.neq_filters = []
        self.not_null_columns = set()
        self.insert_payload = None
        self.update_payload = None
        self.limit_count = None
        self.order_column = None
        self.order_desc = False
        self.range_start = None
        self.range_end = None

    def select(self, *_args):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def neq(self, column, value):
        self.neq_filters.append((column, value))
        return self

    @property
    def not_(self):
        return self

    def is_(self, column, value):
        if value == "null":
            self.not_null_columns.add(column)
        return self

    def order(self, column, desc=False):
        self.order_column = column
        self.order_desc = desc
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def update(self, payload):
        self.update_payload = payload
        return self

    def execute(self):
        if self.insert_payload is not None:
            row = {
                "id": SUBMISSION_ID,
                "submitted_at": "2026-06-03T14:00:00+00:00",
                "created_at": "2026-06-03T14:00:00+00:00",
                **self.insert_payload,
            }
            self.supabase.tables.setdefault(self.table_name, []).append(row)
            return FakeResponse([row])

        rows = list(self.supabase.tables.get(self.table_name, []))

        for column, value in self.filters:
            rows = [row for row in rows if row.get(column) == value]

        for column, value in self.neq_filters:
            rows = [row for row in rows if row.get(column) != value]

        for column in self.not_null_columns:
            rows = [row for row in rows if row.get(column) is not None]

        if self.update_payload is not None:
            table_rows = self.supabase.tables.get(self.table_name, [])
            updated_rows = []
            for row in table_rows:
                if row in rows:
                    row.update(self.update_payload)
                    updated_rows.append(row)
            return FakeResponse(updated_rows)

        if self.order_column:
            rows = sorted(
                rows,
                key=lambda row: row.get(self.order_column) or "",
                reverse=self.order_desc,
            )

        if self.range_start is not None and self.range_end is not None:
            rows = rows[self.range_start : self.range_end + 1]

        if self.limit_count is not None:
            rows = rows[: self.limit_count]

        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "website_settings": [
                {"id": 1, "tenant_id": 1, "user_id": 2, "subdomain": "tenant-site"}
            ],
            "builder_projects": [
                {
                    "id": PROJECT_ID,
                    "tenant_id": 1,
                    "name": "Published site",
                    "slug": "published-site",
                    "status": "published",
                    "published_schema": PUBLISHED_SCHEMA,
                    "published_version": 4,
                    "last_published_at": "2026-06-03T13:00:00+00:00",
                    "updated_at": "2026-06-03T13:00:00+00:00",
                }
            ],
            "builder_form_submissions": [
                {
                    "id": SUBMISSION_ID,
                    "tenant_id": 1,
                    "project_id": PROJECT_ID,
                    "form_id": FORM_ID,
                    "form_title": "Contact form",
                    "form_version": 4,
                    "status": "new",
                    "answers": {"field_name": "Existing"},
                    "quiz_result": None,
                    "field_snapshot": PUBLISHED_SCHEMA["forms"][0]["sections"][0]["fields"],
                    "submitted_at": "2026-06-03T14:00:00+00:00",
                    "created_at": "2026-06-03T14:00:00+00:00",
                }
            ],
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)


def fake_context(tenant_id=1, role="member"):
    return TenantContext(
        tenant_id=tenant_id,
        user_id=2,
        auth_id="auth-1",
        role=role,
        membership_status="active",
        user={},
        membership={"role": role},
    )


def build_public_client(fake_supabase):
    app = FastAPI()
    app.include_router(public_site_routes.router)
    app.state.fake_supabase = fake_supabase
    return TestClient(app)


def build_builder_client(fake_supabase):
    app = FastAPI()
    app.include_router(builder_routes.router)
    app.state.fake_supabase = fake_supabase
    return TestClient(app)


class BuilderFormSubmissionTests(unittest.TestCase):
    def test_public_submission_succeeds_for_published_form(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Ada", "field_email": "ada@example.com"}},
                headers={"User-Agent": "test-agent"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], SUBMISSION_ID)
        self.assertEqual(body["status"], "New")
        self.assertEqual(body["answers"], {"field_name": "Ada", "field_email": "ada@example.com"})

        saved = fake_supabase.tables["builder_form_submissions"][-1]
        self.assertEqual(saved["tenant_id"], 1)
        self.assertEqual(saved["project_id"], PROJECT_ID)
        self.assertEqual(saved["form_id"], FORM_ID)
        self.assertEqual(saved["form_title"], "Contact form")
        self.assertEqual(saved["form_version"], 4)
        self.assertEqual(saved["user_agent"], "test-agent")
        self.assertEqual(len(saved["field_snapshot"]), 2)

    def test_missing_required_field_fails(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_email": "ada@example.com"}},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["message"], "Required field is missing")

    def test_unknown_form_id_fails(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                "/public/sites/tenant-site/forms/missing-form/submissions",
                json={"answers": {"field_name": "Ada"}},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Form not found")

    def test_unknown_field_fails(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Ada", "field_other": "Nope"}},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["message"], "Submission contains unknown fields")

    def test_public_submission_rate_limit_is_applied(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(
                 public_site_routes,
                 "enforce_public_form_submission_rate_limit",
                 side_effect=HTTPException(status_code=429, detail="Too many requests. Please try again later."),
             ):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Ada"}},
            )

        self.assertEqual(response.status_code, 429)

    def test_authenticated_project_submissions_list_works(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.get(f"/users/2/builder/projects/{PROJECT_ID}/form-submissions?form_id={FORM_ID}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["project_id"], PROJECT_ID)
        self.assertEqual(len(body["submissions"]), 1)
        self.assertEqual(body["items"], body["submissions"])
        self.assertEqual(body["pagination"]["limit"], 20)
        self.assertEqual(body["pagination"]["offset"], 0)
        self.assertFalse(body["pagination"]["has_more"])
        self.assertEqual(body["submissions"][0]["answers"], {"field_name": "Existing"})

    def test_builder_project_list_default_pagination(self):
        fake_supabase = FakeSupabase()
        for index in range(25):
            fake_supabase.tables["builder_projects"].append(
                {
                    "id": f"project-{index}",
                    "tenant_id": 1,
                    "name": f"Project {index}",
                    "slug": f"project-{index}",
                    "status": "draft",
                    "updated_at": f"2026-06-03T12:{index:02d}:00+00:00",
                }
            )
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.get("/users/2/builder/projects")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["projects"]), 20)
        self.assertEqual(body["items"], body["projects"])
        self.assertEqual(body["pagination"]["limit"], 20)
        self.assertEqual(body["pagination"]["offset"], 0)
        self.assertEqual(body["pagination"]["count"], 20)
        self.assertTrue(body["pagination"]["has_more"])

    def test_builder_project_list_custom_limit_offset_and_tenant_scope(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"].extend(
            [
                {
                    "id": "tenant-1-project",
                    "tenant_id": 1,
                    "name": "Tenant 1 project",
                    "slug": "tenant-1-project",
                    "status": "draft",
                    "updated_at": "2026-06-03T15:00:00+00:00",
                },
                {
                    "id": "tenant-2-project",
                    "tenant_id": 2,
                    "name": "Tenant 2 project",
                    "slug": "tenant-2-project",
                    "status": "draft",
                    "updated_at": "2026-06-03T16:00:00+00:00",
                },
                {
                    "id": "tenant-1-project-2",
                    "tenant_id": 1,
                    "name": "Tenant 1 project 2",
                    "slug": "tenant-1-project-2",
                    "status": "draft",
                    "updated_at": "2026-06-03T14:00:00+00:00",
                },
            ]
        )
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.get("/users/2/builder/projects?limit=1&offset=1")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["projects"]), 1)
        self.assertTrue(all(project["tenant_id"] == 1 for project in body["projects"]))
        self.assertEqual(body["pagination"]["limit"], 1)
        self.assertEqual(body["pagination"]["offset"], 1)
        self.assertTrue(body["pagination"]["has_more"])

    def test_builder_project_list_rejects_invalid_pagination(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            over_limit = client.get("/users/2/builder/projects?limit=101")
            negative_offset = client.get("/users/2/builder/projects?offset=-1")

        self.assertEqual(over_limit.status_code, 422)
        self.assertEqual(negative_offset.status_code, 422)

    def test_form_submissions_custom_pagination(self):
        fake_supabase = FakeSupabase()
        for index in range(3):
            fake_supabase.tables["builder_form_submissions"].append(
                {
                    "id": f"submission-{index}",
                    "tenant_id": 1,
                    "project_id": PROJECT_ID,
                    "form_id": FORM_ID,
                    "form_title": "Contact form",
                    "form_version": 4,
                    "status": "new",
                    "answers": {"field_name": f"Person {index}"},
                    "quiz_result": None,
                    "field_snapshot": [],
                    "submitted_at": f"2026-06-03T15:0{index}:00+00:00",
                    "created_at": f"2026-06-03T15:0{index}:00+00:00",
                }
            )
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.get(
                f"/users/2/builder/projects/{PROJECT_ID}/form-submissions?limit=2&offset=1"
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["submissions"]), 2)
        self.assertEqual(body["items"], body["submissions"])
        self.assertEqual(body["pagination"]["limit"], 2)
        self.assertEqual(body["pagination"]["offset"], 1)
        self.assertTrue(body["pagination"]["has_more"])

    def test_form_submissions_rejects_invalid_pagination(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            over_limit = client.get(
                f"/users/2/builder/projects/{PROJECT_ID}/form-submissions?limit=101"
            )
            negative_offset = client.get(
                f"/users/2/builder/projects/{PROJECT_ID}/form-submissions?offset=-1"
            )

        self.assertEqual(over_limit.status_code, 422)
        self.assertEqual(negative_offset.status_code, 422)

    def test_authenticated_submission_read_works(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.get(
                f"/users/2/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["submission"]["id"], SUBMISSION_ID)

    def test_authenticated_submission_read_returns_status_label(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_form_submissions"][0]["status"] = "contacted"
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.get(
                f"/users/2/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["submission"]["status"], "Contacted")

    def test_authenticated_submission_list_returns_status_labels(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_form_submissions"][0]["status"] = "closed"
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.get(
                f"/users/2/builder/projects/{PROJECT_ID}/form-submissions?form_id={FORM_ID}"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["submissions"][0]["status"], "Closed")


    def test_authenticated_submission_status_update_works(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.put(
                f"/users/2/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}",
                json={"status": "Contacted"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["submission"]["id"], SUBMISSION_ID)
        self.assertEqual(body["submission"]["status"], "Contacted")
        self.assertEqual(fake_supabase.tables["builder_form_submissions"][0]["status"], "contacted")

    def test_authenticated_submission_status_update_closed_works(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.put(
                f"/users/2/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}",
                json={"status": "Closed"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["submission"]["id"], SUBMISSION_ID)
        self.assertEqual(body["submission"]["status"], "Closed")
        self.assertEqual(fake_supabase.tables["builder_form_submissions"][0]["status"], "closed")

    def test_authenticated_submission_status_update_rejects_invalid_status(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.put(
                f"/users/2/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}",
                json={"status": "Maybe"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid submission status")

    def test_authenticated_submission_status_update_unknown_submission_fails(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.put(
                f"/users/2/builder/projects/{PROJECT_ID}/form-submissions/missing-submission",
                json={"status": "Closed"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Form submission not found")

    def test_authenticated_submission_status_update_requires_auth(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase):
            response = client.put(
                f"/users/2/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}",
                json={"status": "Contacted"},
            )

        self.assertEqual(response.status_code, 401)

    def test_cross_tenant_submission_status_update_is_blocked(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context(tenant_id=2)):
            response = client.put(
                f"/users/2/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}",
                json={"status": "Contacted"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Builder project not found")

    def test_cross_tenant_project_access_is_blocked(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context(tenant_id=2)):
            response = client.get(f"/users/2/builder/projects/{PROJECT_ID}/form-submissions")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Builder project not found")


if __name__ == "__main__":
    unittest.main()

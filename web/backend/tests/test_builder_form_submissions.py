import copy
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes import builder_routes, public_site_routes
from services.tenant_service import TenantContext
from tests.entitlement_test_support import installed_business_fixture


_entitlement_fixture = installed_business_fixture(1, 2)


def setUpModule():
    _entitlement_fixture.__enter__()


def tearDownModule():
    _entitlement_fixture.__exit__(None, None, None)


FORM_ID = "form_contact"
RESERVATION_BLOCK_ID = "reservation_request"
PROJECT_ID = "11111111-1111-4111-8111-111111111111"
SUBMISSION_ID = "22222222-2222-4222-8222-222222222222"


PUBLISHED_SCHEMA = {
    "defaultPageId": "page_home",
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
            "name": "Home",
            "slug": "/",
            "isDefault": True,
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
        self.delete_requested = False
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

    def in_(self, column, values):
        self.filters.append((column, set(values)))
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

    def delete(self):
        self.delete_requested = True
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
            if isinstance(value, set):
                rows = [row for row in rows if row.get(column) in value]
            else:
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

        if self.delete_requested:
            table_rows = self.supabase.tables.get(self.table_name, [])
            deleted = [row for row in table_rows if row in rows]
            self.supabase.tables[self.table_name] = [row for row in table_rows if row not in rows]
            return FakeResponse(deleted)

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
                {
                    "id": 1,
                    "tenant_id": 1,
                    "user_id": 2,
                    "subdomain": "tenant-site",
                    "published_project_id": PROJECT_ID,
                }
            ],
            "builder_projects": [
                {
                    "id": PROJECT_ID,
                    "tenant_id": 1,
                    "name": "Published site",
                    "slug": "published-site",
                    "status": "published",
                    "draft_schema": copy.deepcopy(PUBLISHED_SCHEMA),
                    "draft_revision": 5,
                    "published_schema": copy.deepcopy(PUBLISHED_SCHEMA),
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
            "builder_form_drafts": [],
            "users": [],
            "tenant_site_memberships": [],
            "tenant_site_project_role_assignments": [],
            "tenant_site_project_roles": [],
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
    def test_role_restricted_form_requires_login(self):
        fake_supabase = FakeSupabase()
        restricted_schema = copy.deepcopy(fake_supabase.tables["builder_projects"][0]["published_schema"])
        fake_supabase.tables["builder_projects"][0]["published_schema"] = restricted_schema
        restricted_schema["roles"] = [{
            "id": "customer",
            "permissions": {"submitForms": True},
            "resourceAccess": {"formIds": [FORM_ID]},
        }]
        client = build_public_client(fake_supabase)
        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"), \
             patch.object(public_site_routes, "get_optional_tenant_visitor", return_value=None):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Ada"}},
            )
        self.assertEqual(response.status_code, 401)

    def test_logged_in_form_submission_records_member_ownership(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)
        identity = ({"id": 31}, {"id": 41, "status": "active"})
        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"), \
             patch.object(public_site_routes, "authorize_site_resource", return_value=identity):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Ada"}},
            )
        self.assertEqual(response.status_code, 200)
        saved = fake_supabase.tables["builder_form_submissions"][-1]
        self.assertEqual(saved["site_user_id"], 31)
        self.assertEqual(saved["site_membership_id"], 41)

    def test_member_submissions_endpoint_is_not_exposed(self):
        client = build_public_client(FakeSupabase())
        response = client.get("/public/sites/tenant-site/me/submissions")
        self.assertEqual(response.status_code, 404)
    def test_public_submission_replay_returns_original_and_notifies_once(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)
        initial_count = len(fake_supabase.tables["builder_form_submissions"])
        body = {
            "answers": {"field_name": "Ada"},
            "idempotency_key": "madar-form-replay-0001",
        }

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            first = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json=body,
                headers={"Idempotency-Key": body["idempotency_key"]},
            )
            replay = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json=body,
                headers={"Idempotency-Key": body["idempotency_key"]},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(first.json()["id"], replay.json()["id"])
        self.assertEqual(len(fake_supabase.tables["builder_form_submissions"]), initial_count + 1)
        saved = fake_supabase.tables["builder_form_submissions"][-1]
        self.assertRegex(saved["idempotency_key_hash"], r"^[0-9a-f]{64}$")
        self.assertNotIn(body["idempotency_key"], str(saved))

    def test_public_submission_same_key_different_payload_conflicts(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)
        key = "madar-form-conflict-0001"
        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            first = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Ada"}, "idempotency_key": key},
            )
            conflict = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Grace"}, "idempotency_key": key},
            )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["detail"]["code"], "idempotency_conflict")

    def test_public_submission_rejects_invalid_or_mismatched_key(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)
        with patch.object(public_site_routes, "service_supabase", fake_supabase):
            invalid = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Ada"}, "idempotency_key": "bad key!"},
            )
            mismatch = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Ada"}, "idempotency_key": "madar-form-body-0001"},
                headers={"Idempotency-Key": "madar-form-header-0001"},
            )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["detail"]["code"], "idempotency_key_invalid")
        self.assertEqual(mismatch.status_code, 409)
        self.assertEqual(mismatch.json()["detail"]["code"], "idempotency_conflict")

    def test_form_idempotency_scope_includes_form_and_project(self):
        fake_supabase = FakeSupabase()
        key_hash = "a" * 64
        base = {
            "tenant_id": 1,
            "project_id": PROJECT_ID,
            "form_id": FORM_ID,
            "status": "new",
            "answers": {},
            "field_snapshot": [],
        }
        with patch.object(public_site_routes, "service_supabase", fake_supabase):
            first, _ = public_site_routes.insert_builder_form_submission(
                base,
                idempotency_key_hash=key_hash,
                request_hash="b" * 64,
                notification={"event_type": "test"},
            )
            other_form, duplicate = public_site_routes.insert_builder_form_submission(
                {**base, "form_id": "another-form"},
                idempotency_key_hash=key_hash,
                request_hash="c" * 64,
                notification={"event_type": "test"},
            )
        self.assertFalse(duplicate)
        self.assertNotEqual(first["form_id"], other_form["form_id"])

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

    def test_invalid_email_is_rejected_with_safe_field_context(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Ada", "field_email": "not-an-email"}},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            {
                "message": "Invalid field value",
                "field_id": "field_email",
                "field_label": "Email",
                "field_type": "email",
                "reason": "email",
            },
        )

    def test_server_type_validation_covers_scale_choices_and_whitespace(self):
        fields = [
            {"id": "name", "label": "Name", "type": "shortText", "required": True},
            {"id": "scale", "label": "Score", "type": "linearScale", "scaleMin": 1, "scaleMax": 5},
            {"id": "choices", "label": "Choices", "type": "checkboxes"},
        ]
        form = {"sections": [{"fields": fields}]}

        for answers, field_id in [
            ({"name": "   "}, "name"),
            ({"name": "Ada", "scale": 6}, "scale"),
            ({"name": "Ada", "choices": "One"}, "choices"),
        ]:
            with self.subTest(field_id=field_id), self.assertRaises(HTTPException) as raised:
                public_site_routes.validate_form_answers(form, answers)
            self.assertEqual(raised.exception.detail["field_id"], field_id)

    def test_public_submission_honeypot_is_rejected_without_insert(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)
        initial_count = len(fake_supabase.tables["builder_form_submissions"])

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={
                    "answers": {"field_name": "Bot"},
                    "honeypot": "filled",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "submission_rejected")
        self.assertEqual(
            len(fake_supabase.tables["builder_form_submissions"]),
            initial_count,
        )

    def test_public_submission_rejects_too_many_answer_fields(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)
        answers = {
            f"field_{index}": "x"
            for index in range(public_site_routes.MAX_PUBLIC_FORM_ANSWER_FIELDS + 1)
        }

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": answers},
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(
            response.json()["detail"]["message"],
            "Submission contains too many answer fields",
        )
        self.assertEqual(
            response.json()["detail"]["max_fields"],
            public_site_routes.MAX_PUBLIC_FORM_ANSWER_FIELDS,
        )

    def test_public_submission_rejects_too_large_individual_answer(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)
        oversized_answer = "a" * (public_site_routes.MAX_PUBLIC_FORM_ANSWER_STRING_LENGTH + 1)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": oversized_answer}},
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["detail"]["message"], "Submission answer is too large")
        self.assertEqual(response.json()["detail"]["field_id"], "field_name")
        self.assertEqual(
            response.json()["detail"]["max_length"],
            public_site_routes.MAX_PUBLIC_FORM_ANSWER_STRING_LENGTH,
        )

    def test_public_submission_rejects_too_large_answers_object(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)
        answers = {
            "field_name": "Ada",
            "field_email": [
                "a" * public_site_routes.MAX_PUBLIC_FORM_ANSWER_STRING_LENGTH
                for _ in range(14)
            ],
        }

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": answers},
            )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(
            response.json()["detail"]["message"],
            "Submission answers payload is too large",
        )
        self.assertEqual(
            response.json()["detail"]["max_bytes"],
            public_site_routes.MAX_PUBLIC_FORM_ANSWERS_JSON_BYTES,
        )


    def test_public_submission_rejects_form_missing_from_bound_publication(self):
        fake_supabase = FakeSupabase()
        project = fake_supabase.tables["builder_projects"][0]
        project["draft_schema"] = copy.deepcopy(PUBLISHED_SCHEMA)
        project["draft_schema"]["forms"][0]["title"] = "Draft-only contact form"
        project["published_schema"] = {
            "forms": [],
            "pages": [],
        }
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Ada"}},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(len(fake_supabase.tables["builder_form_submissions"]), 1)

    def test_public_submission_accepts_form_without_builder_placement(self):
        fake_supabase = FakeSupabase()
        project = fake_supabase.tables["builder_projects"][0]
        project["published_schema"] = copy.deepcopy(PUBLISHED_SCHEMA)
        project["published_schema"]["pages"] = []
        project["draft_schema"]["pages"] = []
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Ada"}},
            )

        self.assertEqual(response.status_code, 200)

    def test_public_submission_rejects_archived_project(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"][0]["status"] = "archived"
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase),              patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Ada"}},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Published site not found")

    def test_public_submission_rejects_invalid_answers_shape(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase),              patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": ["not", "an", "object"]},
            )

        self.assertEqual(response.status_code, 422)

    def test_public_submission_field_snapshot_is_based_on_published_form(self):
        fake_supabase = FakeSupabase()
        project = fake_supabase.tables["builder_projects"][0]
        project["draft_schema"] = copy.deepcopy(PUBLISHED_SCHEMA)
        project["draft_schema"]["forms"][0]["sections"][0]["fields"][0]["label"] = "Draft full name"
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Ada", "field_email": "ada@example.com"}},
            )

        self.assertEqual(response.status_code, 200)
        saved = fake_supabase.tables["builder_form_submissions"][-1]
        expected_snapshot = copy.deepcopy(project["published_schema"]["forms"][0]["sections"][0]["fields"])
        self.assertEqual(saved["field_snapshot"], expected_snapshot)

        project["draft_schema"]["forms"][0]["sections"][0]["fields"][0]["label"] = "Changed in draft"
        self.assertEqual(saved["field_snapshot"], expected_snapshot)
        self.assertEqual(saved["field_snapshot"][0]["label"], "Full name")
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
            response = client.get(f"/builder/projects/{PROJECT_ID}/form-submissions?form_id={FORM_ID}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["project_id"], PROJECT_ID)
        self.assertEqual(len(body["submissions"]), 1)
        self.assertEqual(body["items"], body["submissions"])
        self.assertEqual(body["pagination"]["limit"], 20)
        self.assertEqual(body["pagination"]["offset"], 0)
        self.assertFalse(body["pagination"]["has_more"])
        self.assertEqual(body["submissions"][0]["answers"], {"field_name": "Existing"})
        self.assertEqual(body["submissions"][0]["submitted_by"]["name"], "Guest")

    def test_submission_submitter_hydration_includes_user_and_role(self):
        fake_supabase = FakeSupabase()
        submission = fake_supabase.tables["builder_form_submissions"][0]
        submission.update({"site_user_id": 31, "site_membership_id": 41})
        fake_supabase.tables["users"].append(
            {"id": 31, "first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com"}
        )
        fake_supabase.tables["tenant_site_memberships"].append(
            {"id": 41, "tenant_id": 1, "user_id": 31, "role": "customer"}
        )
        fake_supabase.tables["tenant_site_project_role_assignments"].append(
            {"membership_id": 41, "project_id": PROJECT_ID, "role_id": "role-vip"}
        )
        fake_supabase.tables["tenant_site_project_roles"].append(
            {"id": "role-vip", "project_id": PROJECT_ID, "role_key": "vip", "deleted_at": None}
        )
        with patch.object(builder_routes, "service_supabase", fake_supabase):
            submitter = builder_routes.get_form_submission_submitters([submission], 1, PROJECT_ID)[SUBMISSION_ID]
        self.assertEqual(submitter, {
            "user_id": 31, "membership_id": 41, "name": "Ada Lovelace",
            "email": "ada@example.com", "role": "vip", "authenticated": True,
        })


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
            response = client.get("/builder/projects")

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
            response = client.get("/builder/projects?limit=1&offset=1")

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
            over_limit = client.get("/builder/projects?limit=101")
            negative_offset = client.get("/builder/projects?offset=-1")

        self.assertEqual(over_limit.status_code, 422)
        self.assertEqual(negative_offset.status_code, 422)


    def test_project_form_submissions_list_requires_auth(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase):
            response = client.get(f"/builder/projects/{PROJECT_ID}/form-submissions?form_id={FORM_ID}")

        self.assertEqual(response.status_code, 401)
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
                f"/builder/projects/{PROJECT_ID}/form-submissions?limit=2&offset=1"
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
                f"/builder/projects/{PROJECT_ID}/form-submissions?limit=101"
            )
            negative_offset = client.get(
                f"/builder/projects/{PROJECT_ID}/form-submissions?offset=-1"
            )

        self.assertEqual(over_limit.status_code, 422)
        self.assertEqual(negative_offset.status_code, 422)

    def test_authenticated_submission_read_works(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.get(
                f"/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}"
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
                f"/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}"
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
                f"/builder/projects/{PROJECT_ID}/form-submissions?form_id={FORM_ID}"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["submissions"][0]["status"], "Closed")


    def test_authenticated_submission_status_update_works(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()), \
             patch.object(builder_routes, "record_audit_event"):
            response = client.put(
                f"/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}",
                json={"status": "Contacted"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["submission"]["id"], SUBMISSION_ID)
        self.assertEqual(body["submission"]["status"], "Contacted")
        self.assertEqual(fake_supabase.tables["builder_form_submissions"][0]["status"], "contacted")


    def test_authenticated_submission_status_update_records_audit(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()), \
             patch.object(builder_routes, "record_audit_event") as record_audit:
            response = client.put(
                f"/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}",
                json={"status": "Contacted"},
            )

        self.assertEqual(response.status_code, 200)
        record_audit.assert_called_once()
        audit_kwargs = record_audit.call_args.kwargs
        self.assertEqual(audit_kwargs["tenant_id"], 1)
        self.assertEqual(audit_kwargs["actor_user_id"], 2)
        self.assertEqual(audit_kwargs["action"], "builder.form_submission_status_updated")
        self.assertEqual(audit_kwargs["target_type"], "builder_form_submission")
        self.assertEqual(audit_kwargs["target_id"], SUBMISSION_ID)
        self.assertEqual(
            audit_kwargs["metadata"],
            {
                "project_id": PROJECT_ID,
                "form_id": FORM_ID,
                "old_status": "New",
                "new_status": "Contacted",
            },
        )
        self.assertNotIn("answers", audit_kwargs["metadata"])
        self.assertNotIn("field_snapshot", audit_kwargs["metadata"])

    def test_authenticated_submission_status_update_closed_works(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()), \
             patch.object(builder_routes, "record_audit_event"):
            response = client.put(
                f"/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}",
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
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()), \
             patch.object(builder_routes, "record_audit_event") as record_audit:
            response = client.put(
                f"/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}",
                json={"status": "Maybe"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid submission status")
        record_audit.assert_not_called()

    def test_authenticated_submission_status_update_unknown_submission_fails(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.put(
                f"/builder/projects/{PROJECT_ID}/form-submissions/missing-submission",
                json={"status": "Closed"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Form submission not found")

    def test_authenticated_submission_status_update_requires_auth(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase):
            response = client.put(
                f"/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}",
                json={"status": "Contacted"},
            )

        self.assertEqual(response.status_code, 401)

    def test_cross_tenant_submission_status_update_is_blocked(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context(tenant_id=2)), \
             patch.object(builder_routes, "record_audit_event") as record_audit:
            response = client.put(
                f"/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}",
                json={"status": "Contacted"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Builder project not found")
        record_audit.assert_not_called()

    def test_cross_tenant_project_access_is_blocked(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context(tenant_id=2)):
            response = client.get(f"/builder/projects/{PROJECT_ID}/form-submissions")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Builder project not found")

    def test_canonical_builder_project_list_requires_auth(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase):
            response = client.get("/builder/projects")

        self.assertEqual(response.status_code, 401)

    def test_cross_tenant_project_read_is_blocked(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context(tenant_id=2)):
            response = client.get(f"/builder/projects/{PROJECT_ID}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Builder project not found")

    def test_cross_tenant_project_update_is_blocked(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_write_access", return_value=fake_context(tenant_id=2)):
            response = client.put(
                f"/builder/projects/{PROJECT_ID}",
                json={"name": "Other tenant update"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Builder project not found")

    def test_cross_tenant_project_archive_is_blocked(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_builder_admin_access", return_value=fake_context(tenant_id=2, role="owner")):
            response = client.delete(f"/builder/projects/{PROJECT_ID}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Builder project not found")

    def test_cross_tenant_submission_read_is_blocked(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context(tenant_id=2)):
            response = client.get(
                f"/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}"
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Builder project not found")

    def test_compatibility_submission_status_update_rejects_wrong_user_id(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()):
            response = client.put(
                f"/users/3/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}",
                json={"status": "Contacted"},
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "User id does not match session")

    def test_public_site_response_exposes_only_render_safe_fields(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"][0]["draft_schema"] = {"secret": True}
        fake_supabase.tables["builder_projects"][0]["owner_user_id"] = 77
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"):
            response = client.get("/public/sites/tenant-site")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body["site"],
            {
                "subdomain": "tenant-site",
                "brand": None,
                "footer_store_name": None,
                "logo_url": None,
                "loading_image_url": None,
                "contact_email": None,
                "phone": None,
                "description": None,
            },
        )
        self.assertEqual(
            body["project"]["published_schema"],
            public_site_routes.build_authorized_public_schema(PUBLISHED_SCHEMA),
        )
        self.assertEqual(body["project"]["project_id"], PROJECT_ID)
        self.assertEqual(body["project"]["published_version"], 4)
        self.assertEqual(body["project"]["published_at"], "2026-06-03T13:00:00+00:00")
        self.assertEqual(body["project"]["schema_version"], 1)
        self.assertEqual(len(body["project"]["schema_hash"]), 64)
        self.assertEqual(response.headers["etag"], body["project"]["etag"])
        self.assertNotIn("tenant_id", body["site"])
        self.assertNotIn("id", body["project"])
        self.assertNotIn("owner_user_id", body["project"])
        self.assertNotIn("draft_schema", body["project"])
        self.assertNotIn("status", body["project"])
        self.assertNotIn("published_revision", body["project"])
        self.assertNotIn("last_published_at", body["project"])
        self.assertNotIn("draft_schema", str(body))

    def test_public_site_etag_supports_conditional_get(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"):
            first = client.get("/public/sites/tenant-site")
            second = client.get(
                "/public/sites/tenant-site",
                headers={"If-None-Match": first.headers["etag"]},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 304)
        self.assertEqual(second.headers["etag"], first.headers["etag"])
        self.assertEqual(second.content, b"")

    def test_public_site_etag_changes_with_published_version(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"):
            first = client.get("/public/sites/tenant-site")
            fake_supabase.tables["builder_projects"][0]["published_version"] = 5
            second = client.get("/public/sites/tenant-site")

        self.assertNotEqual(first.headers["etag"], second.headers["etag"])

    def test_public_site_uses_bound_project_when_another_project_is_published_later(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"].append(
            {
                "id": "later-project",
                "tenant_id": 1,
                "name": "Later project",
                "slug": "later-project",
                "status": "published",
                "published_schema": {"pages": [{"id": "later-page"}], "forms": []},
                "published_version": 1,
                "last_published_at": "2026-07-17T12:00:00+00:00",
            }
        )
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"):
            response = client.get("/public/sites/tenant-site")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["project"]["published_schema"],
            public_site_routes.build_authorized_public_schema(PUBLISHED_SCHEMA),
        )
        self.assertNotIn("later-page", str(response.json()))

    def test_anonymous_site_response_excludes_protected_page_content(self):
        fake_supabase = FakeSupabase()
        schema = fake_supabase.tables["builder_projects"][0]["published_schema"]
        schema["pages"].append(
            {
                "id": "member-page",
                "name": "Member vault",
                "slug": "/members",
                "visibility": "members",
                "sections": [{"secret": "literal-private-page-content"}],
            }
        )
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"):
            response = client.get("/public/sites/tenant-site")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertNotIn("literal-private-page-content", str(body))
        self.assertNotIn("Member vault", str(body))
        self.assertEqual(
            [page["id"] for page in body["project"]["published_schema"]["pages"]],
            ["page_home"],
        )

    def test_authenticated_admin_receives_protected_pages_from_site_root(self):
        fake_supabase = FakeSupabase()
        schema = fake_supabase.tables["builder_projects"][0]["published_schema"]
        schema["roles"] = [{
            "id": "customer",
            "permissions": {"viewProtectedPages": True},
            "resourceAccess": {"pageIds": ["member-page"]},
        }]
        schema["pages"].append(
            {
                "id": "member-page",
                "name": "Member vault",
                "slug": "/members",
                "visibility": "public",
                "sections": [{"content": "authorized-content"}],
            }
        )
        client = build_public_client(fake_supabase)
        staff_identity = (
            {"id": 77},
            {"status": "active", "_access_kind": "staff"},
        )

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"), \
             patch.object(public_site_routes, "get_optional_tenant_visitor", return_value=staff_identity):
            response = client.get("/public/sites/tenant-site")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("authorized-content", str(body))
        self.assertEqual(
            {page["id"] for page in body["project"]["published_schema"]["pages"]},
            {"page_home", "member-page"},
        )
        self.assertEqual(response.headers["cache-control"], "private, no-store")
    def test_active_site_member_can_fetch_bound_protected_page(self):
        fake_supabase = FakeSupabase()
        schema = fake_supabase.tables["builder_projects"][0]["published_schema"]
        schema["pages"].append(
            {
                "id": "member-page",
                "name": "Member vault",
                "slug": "/members",
                "visibility": "members",
                "sections": [{"secret": "literal-private-page-content"}],
            }
        )
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"), \
             patch.object(public_site_routes, "has_project_permission", return_value=True), \
             patch.object(
                 public_site_routes,
                 "require_tenant_visitor",
                 return_value=({}, {"status": "active"}),
             ):
            response = client.get("/public/sites/tenant-site/pages/member-page")

        self.assertEqual(response.status_code, 200)
        self.assertIn("literal-private-page-content", str(response.json()))

    def test_site_member_without_project_permission_cannot_fetch_protected_page(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"][0]["published_schema"]["pages"].append(
            {"id": "member-page", "slug": "/members", "visibility": "members", "sections": []}
        )
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"), \
             patch.object(public_site_routes, "has_project_permission", return_value=False), \
             patch.object(
                 public_site_routes,
                 "require_tenant_visitor",
                 return_value=({}, {"id": 19, "status": "active", "_access_kind": "site"}),
             ):
            response = client.get("/public/sites/tenant-site/pages/member-page")

        self.assertEqual(response.status_code, 403)

    def test_disabled_site_member_cannot_fetch_protected_page(self):
        fake_supabase = FakeSupabase()
        schema = fake_supabase.tables["builder_projects"][0]["published_schema"]
        schema["pages"].append(
            {"id": "member-page", "slug": "/members", "visibility": "members", "sections": []}
        )
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"), \
             patch.object(
                 public_site_routes,
                 "require_tenant_visitor",
                 side_effect=HTTPException(
                     status_code=403,
                     detail="This account does not belong to this website",
                 ),
             ):
            response = client.get("/public/sites/tenant-site/pages/member-page")

        self.assertEqual(response.status_code, 403)

    def test_unknown_role_restricted_page_fails_closed(self):
        fake_supabase = FakeSupabase()
        schema = fake_supabase.tables["builder_projects"][0]["published_schema"]
        schema["pages"].append(
            {
                "id": "role-page",
                "slug": "/role-page",
                "visibility": "vip",
                "sections": [{"secret": "restricted-content"}],
            }
        )
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"), \
             patch.object(
                 public_site_routes,
                 "require_tenant_visitor",
                 return_value=({}, {"status": "active"}),
             ):
            response = client.get("/public/sites/tenant-site/pages/role-page")

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("restricted-content", str(response.json()))

    def test_site_binding_requires_published_same_tenant_project(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"].append(
            {
                "id": "cross-tenant-project",
                "tenant_id": 2,
                "status": "published",
                "published_schema": {"pages": []},
            }
        )
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(
                 builder_routes,
                 "require_builder_admin_access",
                 return_value=fake_context(role="admin"),
             ):
            response = client.put(
                "/builder/site-binding",
                headers={"X-Madar-Builder-Contract": "cloud-draft-v1"},
                json={"project_id": "cross-tenant-project"},
            )

        self.assertEqual(response.status_code, 404)

    def test_site_binding_can_select_published_tenant_project(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"].append(
            {
                "id": "second-project",
                "tenant_id": 1,
                "name": "Second",
                "slug": "second",
                "status": "published",
                "published_schema": {"pages": []},
                "published_version": 1,
            }
        )
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(
                 builder_routes,
                 "require_builder_admin_access",
                 return_value=fake_context(role="admin"),
             ), patch.object(builder_routes, "record_audit_event") as audit:
            response = client.put(
                "/builder/site-binding",
                headers={"X-Madar-Builder-Contract": "cloud-draft-v1"},
                json={"project_id": "second-project"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["binding"]["project_id"], "second-project")
        self.assertEqual(
            fake_supabase.tables["website_settings"][0]["published_project_id"],
            "second-project",
        )
        audit.assert_called_once()

    def test_bound_project_cannot_be_archived(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(
                 builder_routes,
                 "require_builder_admin_access",
                 return_value=fake_context(role="admin"),
             ):
            response = client.delete(
                f"/builder/projects/{PROJECT_ID}",
                headers={"X-Madar-Builder-Contract": "cloud-draft-v1"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["code"], "public_project_bound")

    def test_public_form_returns_saved_form_without_other_forms_or_responses(self):
        fake_supabase = FakeSupabase()
        project = fake_supabase.tables["builder_projects"][0]
        project["draft_schema"]["forms"].append(
            {"id": "another-form", "title": "Private sibling form", "sections": []}
        )
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"):
            response = client.get(f"/public/sites/tenant-site/forms/{FORM_ID}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["form"]["id"], FORM_ID)
        self.assertEqual(body["publication"]["project_id"], PROJECT_ID)
        self.assertEqual(body["publication"]["published_version"], 4)
        self.assertEqual(body["publication"]["published_at"], "2026-06-03T13:00:00+00:00")
        self.assertNotIn("responses", body["form"])
        self.assertNotIn("project", body)
        self.assertNotIn("pages", body)
        self.assertNotIn("another-form", str(body))
        self.assertNotIn("sample", str(body))

    def test_standalone_published_form_opens_without_a_live_website_project(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["website_settings"][0]["published_project_id"] = None
        standalone_project_id = "standalone-project"
        fake_supabase.tables["builder_projects"].append(
            {
                "id": standalone_project_id,
                "tenant_id": 1,
                "name": "Standalone published form",
                "slug": "standalone-form",
                "status": "published",
                "published_schema": copy.deepcopy(PUBLISHED_SCHEMA),
                "published_version": 1,
                "last_published_at": "2026-06-03T15:00:00+00:00",
                "updated_at": "2026-06-03T15:00:00+00:00",
            }
        )
        fake_supabase.tables["builder_projects"][0]["status"] = "archived"
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_rate_limit"):
            response = client.get(f"/public/sites/tenant-site/forms/{FORM_ID}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["form"]["id"], FORM_ID)
        self.assertEqual(response.json()["publication"]["project_id"], standalone_project_id)
    def test_public_submission_rejects_bound_draft_project(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_projects"][0]["status"] = "draft"
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                f"/public/sites/tenant-site/forms/{FORM_ID}/submissions",
                json={"answers": {"field_name": "Ada"}},
            )

        self.assertEqual(response.status_code, 404)

    def test_public_reservation_event_creates_notification(self):
        fake_supabase = FakeSupabase()
        published_schema = copy.deepcopy(PUBLISHED_SCHEMA)
        published_schema["pages"][0]["sections"][0]["rows"][0]["columns"][0]["elements"].append(
            {
                "id": RESERVATION_BLOCK_ID,
                "type": "reservationBlock",
                "reservation": {"title": "Book a table"},
            }
        )
        fake_supabase.tables["builder_projects"][0]["published_schema"] = published_schema
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                "/public/sites/tenant-site/events",
                json={
                    "block_type": "reservationBlock",
                    "block_id": RESERVATION_BLOCK_ID,
                    "event_type": "builder.reservation_requested",
                    "payload": {
                        "name": "Ada",
                        "contact": "ada@example.com",
                        "service": "Dinner",
                        "date": "2026-07-10",
                        "time": "19:00",
                        "timezone": "Asia/Jerusalem",
                        "guests": 2,
                    },
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["reservation_id"], SUBMISSION_ID)
        self.assertEqual(body["message"], "Reservation submitted successfully.")
        saved = fake_supabase.tables["builder_reservations"][-1]
        self.assertEqual(saved["tenant_id"], 1)
        self.assertEqual(saved["project_id"], PROJECT_ID)
        self.assertEqual(saved["customer_name"], "Ada")

    def test_public_event_rejects_missing_published_block(self):
        fake_supabase = FakeSupabase()
        client = build_public_client(fake_supabase)

        with patch.object(public_site_routes, "service_supabase", fake_supabase), \
             patch.object(public_site_routes, "enforce_public_form_submission_rate_limit"):
            response = client.post(
                "/public/sites/tenant-site/events",
                json={
                    "block_type": "reservationBlock",
                    "block_id": "not-on-page",
                    "payload": {"name": "Ada"},
                },
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Block not found")



class PublicSiteTenantResolutionTests(unittest.TestCase):
    def test_authenticated_submission_answers_can_be_edited(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()), \
             patch.object(builder_routes, "record_audit_event") as record_audit:
            response = client.patch(
                f"/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}",
                json={"answers": {"field_name": "Edited"}},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["record"]["answers"], {"field_name": "Edited"})
        self.assertEqual(fake_supabase.tables["builder_form_submissions"][0]["answers"], {"field_name": "Edited"})
        self.assertEqual(record_audit.call_args.kwargs["action"], "builder.form_submission_updated")

    def test_authenticated_submission_can_be_deleted(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()), \
             patch.object(builder_routes, "record_audit_event"):
            response = client.delete(
                f"/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted_id"], SUBMISSION_ID)
        self.assertEqual(fake_supabase.tables["builder_form_submissions"], [])

    def test_authenticated_draft_can_be_edited_and_deleted(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["builder_form_drafts"] = [{
            "id": SUBMISSION_ID, "tenant_id": 1, "project_id": PROJECT_ID,
            "form_id": FORM_ID, "form_title": "Contact form", "form_version": 4,
            "answers": {"field_name": "Partial"}, "field_snapshot": [],
            "page_index": 0, "language": "en",
            "created_at": "2026-06-03T14:00:00+00:00",
            "updated_at": "2026-06-03T14:00:00+00:00",
        }]
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase), \
             patch.object(builder_routes, "require_active_tenant_member", return_value=fake_context()), \
             patch.object(builder_routes, "record_audit_event"):
            update_response = client.patch(
                f"/builder/projects/{PROJECT_ID}/form-drafts/{SUBMISSION_ID}",
                json={"answers": {"field_name": "Edited partial"}},
            )
            delete_response = client.delete(
                f"/builder/projects/{PROJECT_ID}/form-drafts/{SUBMISSION_ID}"
            )

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["record"]["answers"], {"field_name": "Edited partial"})
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(fake_supabase.tables["builder_form_drafts"], [])

    def test_record_mutations_require_authentication(self):
        fake_supabase = FakeSupabase()
        client = build_builder_client(fake_supabase)

        with patch.object(builder_routes, "service_supabase", fake_supabase):
            update_response = client.patch(
                f"/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}",
                json={"answers": {"field_name": "Blocked"}},
            )
            delete_response = client.delete(
                f"/builder/projects/{PROJECT_ID}/form-submissions/{SUBMISSION_ID}"
            )

        self.assertEqual(update_response.status_code, 401)
        self.assertEqual(delete_response.status_code, 401)
        self.assertEqual(fake_supabase.tables["builder_form_submissions"][0]["answers"], {"field_name": "Existing"})

    def test_public_resolve_tenant_id_prefers_website_settings_tenant_id(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["website_settings"] = [
            {"id": 1, "tenant_id": 11, "user_id": 2, "subdomain": "tenant-site"}
        ]
        fake_supabase.tables["users"] = [{"id": 2, "tenant_id": 22}]

        with patch.object(public_site_routes, "service_supabase", fake_supabase):
            tenant_id = public_site_routes.resolve_tenant_id(fake_supabase.tables["website_settings"][0])

        self.assertEqual(tenant_id, 11)

    def test_public_resolve_tenant_id_rejects_missing_tenant_even_with_legacy_user_mapping(self):
        fake_supabase = FakeSupabase()
        fake_supabase.tables["website_settings"] = [
            {"id": 1, "tenant_id": None, "user_id": 2, "subdomain": "legacy-site"}
        ]
        fake_supabase.tables["users"] = [{"id": 2, "tenant_id": 22}]

        with patch.object(public_site_routes, "service_supabase", fake_supabase):
            with self.assertRaises(HTTPException) as exc:
                public_site_routes.resolve_tenant_id(fake_supabase.tables["website_settings"][0])

        self.assertEqual(exc.exception.status_code, 404)
        self.assertEqual(exc.exception.detail, "Published site not found")

    def test_public_resolve_tenant_id_rejects_missing_tenant_and_user(self):
        fake_supabase = FakeSupabase()
        settings = {"id": 1, "tenant_id": None, "subdomain": "broken-site"}

        with patch.object(public_site_routes, "service_supabase", fake_supabase):
            with self.assertRaises(HTTPException) as exc:
                public_site_routes.resolve_tenant_id(settings)

        self.assertEqual(exc.exception.status_code, 404)
        self.assertEqual(exc.exception.detail, "Published site not found")

    def test_public_resolve_tenant_id_rejects_user_without_tenant(self):
        fake_supabase = FakeSupabase()
        settings = {"id": 1, "tenant_id": None, "user_id": 99, "subdomain": "broken-site"}
        fake_supabase.tables["users"] = [{"id": 99, "tenant_id": None}]

        with patch.object(public_site_routes, "service_supabase", fake_supabase):
            with self.assertRaises(HTTPException) as exc:
                public_site_routes.resolve_tenant_id(settings)

        self.assertEqual(exc.exception.status_code, 404)
        self.assertEqual(exc.exception.detail, "Published site not found")

    def test_public_resolve_tenant_id_prefers_tenant_id_over_disagreeing_user_fallback(self):
        fake_supabase = FakeSupabase()
        settings = {"id": 1, "tenant_id": 11, "user_id": 2, "subdomain": "tenant-site"}
        fake_supabase.tables["users"] = [{"id": 2, "tenant_id": 22}]

        with patch.object(public_site_routes, "service_supabase", fake_supabase):
            tenant_id = public_site_routes.resolve_tenant_id(settings)

        self.assertEqual(tenant_id, 11)

if __name__ == "__main__":
    unittest.main()

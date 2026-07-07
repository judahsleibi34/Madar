import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import auth_routes


ONBOARDING_PATH = "/auth/signup/onboard"


def build_client():
    app = FastAPI()
    app.include_router(auth_routes.router)
    return TestClient(app)


def onboarding_payload(**overrides):
    payload = {
        "business_name": "Madar Demo Cafe",
        "business_type": "restaurant",
        "subdomain": "Madar-Demo",
        "first_name": "Madar",
        "last_name": "Owner",
        "email": "Owner@Example.COM",
        "owner_name": "Madar Owner",
        "owner_email": "Owner@Example.COM",
        "password": "super-secret-password",
        "selected_base_plan": {
            "subscription_type": "full_platform",
            "plan": "starter",
        },
        "selected_features": [
            {
                "subscription_type": "individual_builder",
                "plan": "basic",
                "builder_type": "website",
            }
        ],
    }
    payload.update(overrides)
    return payload


class FakeAuthAdmin:
    def __init__(self):
        self.created_users = []
        self.deleted_users = []

    def create_user(self, payload):
        self.created_users.append(payload)
        return SimpleNamespace(user=SimpleNamespace(id=f"auth-user-{len(self.created_users)}"))

    def delete_user(self, user_id):
        self.deleted_users.append(user_id)
        return SimpleNamespace()


class FakeAuth:
    def __init__(self):
        self.admin = FakeAuthAdmin()


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, supabase, table_name):
        self.supabase = supabase
        self.table_name = table_name
        self.operation = "select"
        self.payload = None
        self.filters = []
        self.limit_count = None

    def select(self, *_args):
        self.operation = "select"
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def execute(self):
        if self.operation == "insert":
            return self.supabase.insert_row(self.table_name, self.payload)

        if self.operation == "delete":
            return self.supabase.delete_rows(self.table_name, self.filters)

        rows = list(self.supabase.tables.get(self.table_name, []))
        for column, value in self.filters:
            rows = [row for row in rows if row.get(column) == value]
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return FakeResult(rows)


class FakeSupabase:
    def __init__(self, *, existing_subdomains=None, fail_insert_table=None):
        self.auth = FakeAuth()
        self.fail_insert_table = fail_insert_table
        self.tables = {
            "tenants": [],
            "users": [],
            "tenant_memberships": [],
            "website_settings": [],
            "builder_projects": [],
            "features": [],
        }
        for index, subdomain in enumerate(existing_subdomains or [], start=1):
            self.tables["website_settings"].append(
                {
                    "id": index,
                    "tenant_id": 100 + index,
                    "user_id": 200 + index,
                    "subdomain": subdomain,
                }
            )
        self.deleted_rows = []

    def table(self, table_name):
        return FakeQuery(self, table_name)

    def insert_row(self, table_name, payload):
        if table_name == self.fail_insert_table:
            raise RuntimeError(f"forced {table_name} insert failure")

        row = dict(payload)
        if table_name == "tenants":
            row.setdefault("tenant_id", len(self.tables[table_name]) + 1)
        elif table_name == "users":
            row.setdefault("id", len(self.tables[table_name]) + 1)
        elif table_name in {"website_settings", "features"}:
            row.setdefault("id", len(self.tables[table_name]) + 1)
        elif table_name == "builder_projects":
            row.setdefault("id", f"project-{len(self.tables[table_name]) + 1}")

        self.tables.setdefault(table_name, []).append(row)
        return FakeResult([row])

    def delete_rows(self, table_name, filters):
        old_rows = list(self.tables.get(table_name, []))
        kept_rows = []
        deleted = []
        for row in old_rows:
            should_delete = all(row.get(column) == value for column, value in filters)
            if should_delete:
                deleted.append(row)
            else:
                kept_rows.append(row)
        self.tables[table_name] = kept_rows
        self.deleted_rows.append((table_name, filters, deleted))
        return FakeResult(deleted)


class OnboardingRoutesTests(unittest.TestCase):
    def test_successful_onboarding_creates_tenant_user_membership_settings_project_and_pending_features(self):
        client = build_client()
        fake_supabase = FakeSupabase()

        with patch.object(auth_routes, "service_supabase", fake_supabase), patch.object(
            auth_routes,
            "enforce_auth_rate_limit",
        ):
            response = client.post(ONBOARDING_PATH, json=onboarding_payload())

        self.assertIn(response.status_code, (200, 201))

        tenants = fake_supabase.tables["tenants"]
        self.assertEqual(len(tenants), 1)
        self.assertEqual(tenants[0]["brand_name"], "Madar Demo Cafe")
        self.assertEqual(tenants[0]["business_type"], "restaurant")

        users = fake_supabase.tables["users"]
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["email"], "owner@example.com")
        self.assertEqual(users[0]["tenant_id"], tenants[0]["tenant_id"])

        memberships = fake_supabase.tables["tenant_memberships"]
        self.assertEqual(len(memberships), 1)
        self.assertEqual(memberships[0]["tenant_id"], tenants[0]["tenant_id"])
        self.assertEqual(memberships[0]["user_id"], users[0]["id"])
        self.assertEqual(memberships[0]["role"], "owner")
        self.assertEqual(memberships[0]["status"], "active")

        settings = fake_supabase.tables["website_settings"]
        self.assertEqual(len(settings), 1)
        self.assertEqual(settings[0]["tenant_id"], tenants[0]["tenant_id"])
        self.assertEqual(settings[0]["user_id"], users[0]["id"])
        self.assertEqual(settings[0]["subdomain"], "madar-demo")

        projects = fake_supabase.tables["builder_projects"]
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["tenant_id"], tenants[0]["tenant_id"])
        self.assertEqual(projects[0]["owner_user_id"], users[0]["id"])
        self.assertEqual(projects[0]["status"], "draft")
        self.assertFalse(projects[0].get("published_schema"))
        self.assertEqual(projects[0].get("published_version"), 0)

        draft_schema = projects[0]["draft_schema"]
        self.assertEqual(draft_schema["status"], "draft")
        self.assertEqual(draft_schema["activePageId"], "home")
        page = draft_schema["pages"][0]
        self.assertEqual(page["id"], "home")
        self.assertEqual(page["slug"], "/")
        section = page["sections"][0]
        self.assertEqual(section["mode"], "auto")
        self.assertIn("width", section["layout"])
        self.assertIn("paddingY", section["layout"])
        self.assertIn("background", section["layout"])
        row = section["rows"][0]
        self.assertIn("columns", row["layout"])
        self.assertIn("align", row["layout"])
        self.assertIn("gap", row["layout"])
        column = row["columns"][0]
        self.assertIn("align", column["layout"])
        element = column["elements"][0]
        self.assertEqual(element["type"], "heading")
        self.assertEqual(element["content"], "Madar Demo Cafe")
        self.assertIn("styles", element)
        self.assertIn("width", element["position"]["desktop"])

        features = fake_supabase.tables["features"]
        self.assertGreaterEqual(len(features), 1)
        for feature in features:
            self.assertEqual(feature["tenant_id"], tenants[0]["tenant_id"])
            self.assertEqual(feature["payment_status"], "pending")

    def test_onboarding_allows_optional_business_details_and_subdomain(self):
        client = build_client()
        fake_supabase = FakeSupabase()

        with patch.object(auth_routes, "service_supabase", fake_supabase), patch.object(
            auth_routes,
            "enforce_auth_rate_limit",
        ):
            response = client.post(
                ONBOARDING_PATH,
                json=onboarding_payload(
                    business_name="",
                    business_type="",
                    subdomain="",
                ),
            )

        self.assertIn(response.status_code, (200, 201))
        body = response.json()
        self.assertIsNone(body["subdomain"])

        tenants = fake_supabase.tables["tenants"]
        self.assertEqual(tenants[0]["brand_name"], "Madar Owner")
        self.assertEqual(tenants[0]["business_type"], "")

        settings = fake_supabase.tables["website_settings"]
        self.assertIsNone(settings[0]["subdomain"])
        self.assertEqual(settings[0]["brand"], "Madar Owner")

        projects = fake_supabase.tables["builder_projects"]
        self.assertEqual(projects[0]["name"], "Madar Owner Website")
        self.assertEqual(projects[0]["slug"], "site-1")

    def test_onboarding_rejects_numeric_names_and_business_text(self):
        client = build_client()
        invalid_cases = [
            {"first_name": "123"},
            {"last_name": "456"},
            {"business_name": "Cafe 123"},
            {"business_type": "123"},
        ]

        for payload_overrides in invalid_cases:
            with self.subTest(payload_overrides=payload_overrides):
                fake_supabase = FakeSupabase()
                with patch.object(auth_routes, "service_supabase", fake_supabase), patch.object(
                    auth_routes,
                    "enforce_auth_rate_limit",
                ):
                    response = client.post(
                        ONBOARDING_PATH,
                        json=onboarding_payload(**payload_overrides),
                    )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(fake_supabase.auth.admin.created_users, [])
                self.assertEqual(fake_supabase.tables["tenants"], [])

    def test_onboarding_response_is_safe_and_requires_login(self):
        client = build_client()
        fake_supabase = FakeSupabase()

        with patch.object(auth_routes, "service_supabase", fake_supabase), patch.object(
            auth_routes,
            "enforce_auth_rate_limit",
        ):
            response = client.post(ONBOARDING_PATH, json=onboarding_payload())

        self.assertIn(response.status_code, (200, 201))
        body = response.json()
        self.assertTrue(body["requires_login"])
        self.assertIn("user_id", body)
        self.assertIn("tenant_id", body)
        self.assertEqual(body["subdomain"], "madar-demo")
        self.assertNotIn("access_token", body)
        self.assertNotIn("refresh_token", body)
        self.assertNotIn("password", body)

    def test_onboarding_rejects_invalid_reserved_and_duplicate_subdomains(self):
        client = build_client()
        invalid_cases = {
            "spaces": "bad subdomain",
            "too_short": "ab",
            "reserved": "admin",
        }

        for label, subdomain in invalid_cases.items():
            with self.subTest(label=label):
                fake_supabase = FakeSupabase()
                with patch.object(auth_routes, "service_supabase", fake_supabase), patch.object(
                    auth_routes,
                    "enforce_auth_rate_limit",
                ):
                    response = client.post(
                        ONBOARDING_PATH,
                        json=onboarding_payload(subdomain=subdomain),
                    )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(fake_supabase.auth.admin.created_users, [])

        duplicate_supabase = FakeSupabase(existing_subdomains=["madar-demo"])
        with patch.object(auth_routes, "service_supabase", duplicate_supabase), patch.object(
            auth_routes,
            "enforce_auth_rate_limit",
        ):
            response = client.post(
                ONBOARDING_PATH,
                json=onboarding_payload(subdomain="MADAR-DEMO"),
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(duplicate_supabase.auth.admin.created_users, [])

    def test_onboarding_ignores_or_rejects_protected_fields_and_keeps_billing_pending(self):
        client = build_client()
        fake_supabase = FakeSupabase()

        with patch.object(auth_routes, "service_supabase", fake_supabase), patch.object(
            auth_routes,
            "enforce_auth_rate_limit",
        ):
            response = client.post(
                ONBOARDING_PATH,
                json=onboarding_payload(
                    tenant_id=999,
                    user_type="admin",
                    billing_status="active",
                    payment_status="active",
                    selected_features=[
                        {
                            "subscription_type": "individual_builder",
                            "plan": "premium",
                            "builder_type": "forms",
                            "payment_status": "active",
                            "tenant_id": 999,
                        }
                    ],
                ),
            )

        self.assertIn(response.status_code, (200, 201))
        self.assertEqual(fake_supabase.tables["users"][0]["tenant_id"], 1)
        self.assertNotEqual(fake_supabase.tables["users"][0].get("user_type"), "admin")
        for feature in fake_supabase.tables["features"]:
            self.assertEqual(feature["tenant_id"], 1)
            self.assertEqual(feature["payment_status"], "pending")

    def test_onboarding_failure_after_auth_creation_cleans_up_partial_rows(self):
        client = build_client()
        fake_supabase = FakeSupabase(fail_insert_table="builder_projects")

        with patch.object(auth_routes, "service_supabase", fake_supabase), patch.object(
            auth_routes,
            "enforce_auth_rate_limit",
        ):
            response = client.post(ONBOARDING_PATH, json=onboarding_payload())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(fake_supabase.tables["users"], [])
        self.assertEqual(fake_supabase.tables["tenants"], [])
        self.assertEqual(fake_supabase.tables["tenant_memberships"], [])
        self.assertEqual(fake_supabase.tables["website_settings"], [])
        self.assertIn("auth-user-1", fake_supabase.auth.admin.deleted_users)

    def test_existing_signup_route_remains_unchanged(self):
        client = build_client()
        fake_supabase = FakeSupabase()

        with patch.object(auth_routes, "service_supabase", fake_supabase), patch.object(
            auth_routes,
            "enforce_auth_rate_limit",
        ):
            response = client.post(
                "/auth/signup",
                json={
                    "first_name": "Existing",
                    "last_name": "Signup",
                    "email": "Existing@Example.COM",
                    "password": "super-secret-password",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["message"], "Signup request sent successfully")
        self.assertEqual(body["user"]["email"], "existing@example.com")
        self.assertEqual(len(fake_supabase.tables["tenants"]), 1)
        self.assertEqual(fake_supabase.tables["tenants"][0]["brand_name"], "")
        self.assertEqual(fake_supabase.tables["website_settings"], [])
        self.assertEqual(fake_supabase.tables["builder_projects"], [])

    def test_existing_signup_rejects_numeric_names(self):
        client = build_client()

        for payload_overrides in ({"first_name": "123"}, {"last_name": "456"}):
            with self.subTest(payload_overrides=payload_overrides):
                fake_supabase = FakeSupabase()
                payload = {
                    "first_name": "Existing",
                    "last_name": "Signup",
                    "email": "Existing@Example.COM",
                    "password": "super-secret-password",
                }
                payload.update(payload_overrides)

                with patch.object(auth_routes, "service_supabase", fake_supabase), patch.object(
                    auth_routes,
                    "enforce_auth_rate_limit",
                ):
                    response = client.post("/auth/signup", json=payload)

                self.assertEqual(response.status_code, 400)
                self.assertEqual(fake_supabase.auth.admin.created_users, [])
                self.assertEqual(fake_supabase.tables["tenants"], [])


if __name__ == "__main__":
    unittest.main()

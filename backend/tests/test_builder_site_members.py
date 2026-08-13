import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes import builder_routes, public_site_routes
from services.tenant_service import TenantContext


def tenant_context(tenant_id=7, user_id=3):
    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        auth_id="admin-auth",
        role="owner",
        membership_status="active",
        user={"id": user_id},
        membership={"role": "owner"},
    )


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.filters = []
        self.in_filters = []
        self.limit_count = None
        self.operation = "select"
        self.payload = None
        self.order_field = None
        self.order_desc = False

    def select(self, *_args):
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def in_(self, field, values):
        self.in_filters.append((field, set(values)))
        return self

    def is_(self, field, value):
        self.filters.append((field, None if value == "null" else value))
        return self

    def limit(self, value):
        self.limit_count = value
        return self

    def order(self, field, desc=False):
        self.order_field = field
        self.order_desc = desc
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = dict(payload)
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = dict(payload)
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def _matches(self, row):
        return all(row.get(field) == value for field, value in self.filters) and all(
            row.get(field) in values for field, values in self.in_filters
        )

    def execute(self):
        rows = self.client.tables.setdefault(self.table_name, [])
        if self.operation == "insert":
            row = dict(self.payload)
            if row.get("id") is None:
                row["id"] = self.client.next_id(self.table_name)
            rows.append(row)
            return SimpleNamespace(data=[dict(row)])

        matched = [row for row in rows if self._matches(row)]
        if self.operation == "update":
            for row in matched:
                row.update(self.payload)
            return SimpleNamespace(data=[dict(row) for row in matched])
        if self.operation == "delete":
            self.client.tables[self.table_name] = [row for row in rows if not self._matches(row)]
            return SimpleNamespace(data=[dict(row) for row in matched])

        if self.order_field:
            matched.sort(key=lambda row: row.get(self.order_field) or "", reverse=self.order_desc)
        if self.limit_count is not None:
            matched = matched[: self.limit_count]
        return SimpleNamespace(data=[dict(row) for row in matched])


class FakeAuthAdmin:
    def __init__(self):
        self.created = []
        self.deleted = []

    def create_user(self, payload):
        self.created.append(dict(payload))
        return SimpleNamespace(user=SimpleNamespace(id=f"auth-{len(self.created)}"))

    def delete_user(self, auth_id):
        self.deleted.append(auth_id)


class FakeAuth:
    def __init__(self):
        self.admin = FakeAuthAdmin()
        self.signed_up = []

    def sign_up(self, payload):
        self.signed_up.append(dict(payload))
        return SimpleNamespace(user=SimpleNamespace(id=f"signup-auth-{len(self.signed_up)}"))


class FakeSupabase:
    def __init__(self, tables=None):
        self.tables = {name: [dict(row) for row in rows] for name, rows in (tables or {}).items()}
        self.auth = FakeAuth()

    def table(self, name):
        return FakeQuery(self, name)

    def rpc(self, name, payload):
        if name != "assign_tenant_site_project_role":
            raise AssertionError(f"Unexpected RPC: {name}")
        roles = self.tables.setdefault("tenant_site_project_roles", [])
        role = next((row for row in roles if row.get("project_id") == payload["target_project_id"] and row.get("role_key") == payload["target_role_key"]), None)
        if role is None:
            role = {
                "id": f"role-{len(roles) + 1}",
                "tenant_id": payload["target_tenant_id"],
                "project_id": payload["target_project_id"],
                "role_key": payload["target_role_key"],
                "capabilities": ["view_protected_page", "submit_protected_form", "make_reservation"],
                "deleted_at": None,
            }
            roles.append(role)
        assignments = self.tables.setdefault("tenant_site_project_role_assignments", [])
        assignment = next((row for row in assignments if row.get("membership_id") == payload["target_membership_id"] and row.get("project_id") == payload["target_project_id"]), None)
        value = {"membership_id": payload["target_membership_id"], "project_id": payload["target_project_id"], "role_id": role["id"]}
        if assignment is None:
            assignments.append(value)
        else:
            assignment.update(value)
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=role["id"]))

    def next_id(self, table_name):
        ids = [row.get("id") for row in self.tables.get(table_name, [])]
        numeric_ids = [value for value in ids if isinstance(value, int)]
        return max(numeric_ids, default=0) + 1


def build_client():
    app = FastAPI()
    app.include_router(builder_routes.router)
    app.include_router(public_site_routes.router)
    return TestClient(app)


class BuilderSiteMemberTests(unittest.TestCase):
    def setUp(self):
        self.client = build_client()
        self.project = {
            "id": "project-1",
            "tenant_id": 7,
            "status": "draft",
            "draft_schema": {"roles": [{"id": "customer"}, {"id": "vip"}]},
        }
        self.supabase = FakeSupabase(
            {
                "users": [
                    {
                        "id": 11,
                        "auth_id": "registered-auth",
                        "first_name": "Registered",
                        "last_name": "Person",
                        "email": "registered@example.com",
                    }
                ],
                "tenant_site_memberships": [
                    {
                        "id": 21,
                        "tenant_id": 7,
                        "user_id": 11,
                        "auth_id": "registered-auth",
                        "role": "customer",
                        "status": "active",
                        "source": "registered",
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ],
                "tenant_site_project_roles": [
                    {"id": "role-customer", "tenant_id": 7, "project_id": "project-1", "role_key": "customer", "capabilities": ["view_protected_page", "submit_protected_form", "make_reservation"], "deleted_at": None},
                    {"id": "role-vip", "tenant_id": 7, "project_id": "project-1", "role_key": "vip", "capabilities": ["view_protected_page", "submit_protected_form", "make_reservation"], "deleted_at": None},
                ],
                "tenant_site_project_role_assignments": [
                    {"membership_id": 21, "project_id": "project-1", "role_id": "role-customer"}
                ],
            }
        )
        self.patches = [
            patch.object(builder_routes, "service_supabase", self.supabase),
            patch.object(builder_routes, "require_builder_admin_access", return_value=tenant_context()),
            patch.object(builder_routes, "get_project_for_tenant", return_value=self.project),
            patch.object(builder_routes, "record_audit_event"),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def test_registered_subdomain_users_are_listed(self):
        response = self.client.get("/builder/projects/project-1/site-members")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["members"], [
            {
                "id": "21",
                "userId": 11,
                "authId": "registered-auth",
                "name": "Registered Person",
                "email": "registered@example.com",
                "roleId": "customer",
                "status": "Active",
                "source": "registered",
                "createdAt": "2026-01-01T00:00:00Z",
                "updatedAt": None,
            }
        ])

    def test_self_registered_user_is_assigned_and_listed_for_the_project(self):
        with patch.object(public_site_routes, "service_supabase", self.supabase), \
             patch.object(public_site_routes, "supabase", self.supabase), \
             patch.object(public_site_routes, "resolve_website_settings", return_value={"tenant_id": 7, "published_project_id": "project-1"}), \
             patch.object(public_site_routes, "get_bound_published_project", return_value=self.project), \
             patch.object(public_site_routes, "enforce_auth_rate_limit"):
            register_response = self.client.post(
                "/public/sites/tenant-site/auth/register",
                json={
                    "full_name": "New Member",
                    "email": "new-member@example.com",
                    "password": "safe-password-123",
                },
            )

        self.assertEqual(register_response.status_code, 200)
        membership = self.supabase.tables["tenant_site_memberships"][-1]
        self.assertEqual(membership["source"], "registered")
        self.assertIn(
            {
                "membership_id": membership["id"],
                "project_id": "project-1",
                "role_id": "role-customer",
            },
            self.supabase.tables["tenant_site_project_role_assignments"],
        )

        list_response = self.client.get("/builder/projects/project-1/site-members")
        self.assertEqual(list_response.status_code, 200)
        listed_emails = {member["email"] for member in list_response.json()["members"]}
        self.assertIn("new-member@example.com", listed_emails)
    def test_admin_created_user_is_saved_to_auth_users_and_memberships(self):
        response = self.client.post(
            "/builder/projects/project-1/site-members",
            json={
                "full_name": "Admin Created",
                "email": "created@example.com",
                "password": "safe-password-123",
                "role_id": "vip",
                "status": "active",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["member"]["source"], "admin")
        self.assertEqual(response.json()["member"]["roleId"], "vip")
        self.assertEqual(self.supabase.auth.admin.created[0]["email_confirm"], True)
        self.assertEqual(self.supabase.tables["users"][-1]["email"], "created@example.com")
        self.assertEqual(self.supabase.tables["tenant_site_memberships"][-1]["source"], "admin")

    def test_role_status_updates_and_removal_are_tenant_scoped(self):
        update_response = self.client.patch(
            "/builder/projects/project-1/site-members/21",
            json={"role_id": "vip", "status": "disabled"},
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["member"]["roleId"], "vip")
        self.assertEqual(update_response.json()["member"]["status"], "Disabled")

        delete_response = self.client.delete("/builder/projects/project-1/site-members/21")
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(len(self.supabase.tables["tenant_site_memberships"]), 1)
        self.assertEqual(self.supabase.tables["tenant_site_project_role_assignments"], [])
        self.assertEqual(len(self.supabase.tables["users"]), 1)

    def test_role_is_scoped_to_the_selected_project(self):
        self.supabase.tables["tenant_site_project_roles"].append(
            {"id": "role-other", "tenant_id": 7, "project_id": "project-2", "role_key": "customer", "capabilities": ["view_protected_page"], "deleted_at": None}
        )
        self.supabase.tables["tenant_site_project_role_assignments"].append(
            {"membership_id": 21, "project_id": "project-2", "role_id": "role-other"}
        )
        response = self.client.delete("/builder/projects/project-1/site-members/21")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.supabase.tables["tenant_site_project_role_assignments"], [
            {"membership_id": 21, "project_id": "project-2", "role_id": "role-other"}
        ])

    def test_non_admin_cannot_list_site_members(self):
        with patch.object(
            builder_routes,
            "require_builder_admin_access",
            side_effect=HTTPException(status_code=403, detail="Builder admin access required"),
        ):
            response = self.client.get("/builder/projects/project-1/site-members")
        self.assertEqual(response.status_code, 403)

    def test_unknown_project_role_is_rejected(self):
        response = self.client.patch(
            "/builder/projects/project-1/site-members/21",
            json={"role_id": "invented-role"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Selected role is invalid")


if __name__ == "__main__":
    unittest.main()

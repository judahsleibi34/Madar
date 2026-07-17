import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes import builder_routes
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


class FakeSupabase:
    def __init__(self, tables=None):
        self.tables = {name: [dict(row) for row in rows] for name, rows in (tables or {}).items()}
        self.auth = SimpleNamespace(admin=FakeAuthAdmin())

    def table(self, name):
        return FakeQuery(self, name)

    def next_id(self, table_name):
        ids = [row.get("id") for row in self.tables.get(table_name, [])]
        numeric_ids = [value for value in ids if isinstance(value, int)]
        return max(numeric_ids, default=0) + 1


def build_client():
    app = FastAPI()
    app.include_router(builder_routes.router)
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
        self.assertEqual(self.supabase.tables["tenant_site_memberships"], [])
        self.assertEqual(len(self.supabase.tables["users"]), 1)

    def test_non_admin_cannot_list_site_members(self):
        with patch.object(
            builder_routes,
            "require_builder_admin_access",
            side_effect=HTTPException(status_code=403, detail="Builder admin access required"),
        ):
            response = self.client.get("/builder/projects/project-1/site-members")
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()

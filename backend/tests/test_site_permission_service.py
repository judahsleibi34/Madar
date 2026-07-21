import unittest
from types import SimpleNamespace

from services.site_permission_service import has_project_permission


class Query:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args): return self
    def eq(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) == value]
        return self
    def is_(self, field, value):
        expected = None if value == "null" else value
        self.rows = [row for row in self.rows if row.get(field) == expected]
        return self
    def limit(self, count):
        self.rows = self.rows[:count]
        return self
    def execute(self): return SimpleNamespace(data=self.rows)


class Client:
    def __init__(self):
        self.tables = {
            "tenant_site_project_role_assignments": [
                {"membership_id": 9, "project_id": "project-a", "role_id": "role-a"},
                {"membership_id": 9, "project_id": "project-b", "role_id": "role-b"},
            ],
            "tenant_site_project_roles": [
                {"id": "role-a", "project_id": "project-a", "role_key": "customer", "capabilities": ["view_protected_page", "submit_protected_form", "make_reservation"], "deleted_at": None},
                {"id": "role-b", "project_id": "project-b", "capabilities": [], "deleted_at": None},
                {"id": "deleted", "project_id": "project-a", "capabilities": ["view_protected_page"], "deleted_at": "2026-01-01T00:00:00Z"},
            ],
        }

    def table(self, name): return Query([dict(row) for row in self.tables.get(name, [])])


class SitePermissionTests(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.membership = {"id": 9, "status": "active", "_access_kind": "site"}

    def test_permissions_are_project_scoped(self):
        self.assertTrue(has_project_permission(membership=self.membership, project_id="project-a", capability="view_protected_page", client=self.client))
        self.assertFalse(has_project_permission(membership=self.membership, project_id="project-b", capability="view_protected_page", client=self.client))

    def test_resource_allowlists_are_role_scoped(self):
        project = {
            "id": "project-a",
            "published_schema": {
                "roles": [
                    {
                        "id": "customer",
                        "permissions": {"viewProtectedPages": True},
                        "resourceAccess": {"pageIds": ["page-a"]},
                    },
                    {
                        "id": "other",
                        "permissions": {"viewProtectedPages": True},
                        "resourceAccess": {"pageIds": ["page-b"]},
                    },
                ]
            },
        }
        self.assertTrue(has_project_permission(
            membership=self.membership,
            project_id="project-a",
            capability="view_protected_page",
            project=project,
            resource_type="page",
            resource_id="page-a",
            client=self.client,
        ))
        self.assertFalse(has_project_permission(
            membership=self.membership,
            project_id="project-a",
            capability="view_protected_page",
            project=project,
            resource_type="page",
            resource_id="page-b",
            client=self.client,
        ))

    def test_explicit_capability_switch_can_deny_database_default(self):
        project = {
            "id": "project-a",
            "published_schema": {
                "roles": [{
                    "id": "customer",
                    "permissions": {"submitForms": False},
                    "resourceAccess": {"formIds": ["private-form"]},
                }]
            },
        }
        self.assertFalse(has_project_permission(
            membership=self.membership,
            project_id="project-a",
            capability="submit_protected_form",
            project=project,
            resource_type="form",
            resource_id="private-form",
            client=self.client,
        ))
    def test_disabled_membership_overrides_assignment(self):
        membership = {**self.membership, "status": "disabled"}
        self.assertFalse(has_project_permission(membership=membership, project_id="project-a", capability="view_protected_page", client=self.client))

    def test_unknown_capability_fails_closed(self):
        self.assertFalse(has_project_permission(membership=self.membership, project_id="project-a", capability="unknown", client=self.client))

    def test_staff_access_is_explicit(self):
        membership = {"status": "active", "_access_kind": "staff"}
        self.assertTrue(has_project_permission(membership=membership, project_id="project-a", capability="view_protected_page", client=self.client))


if __name__ == "__main__":
    unittest.main()

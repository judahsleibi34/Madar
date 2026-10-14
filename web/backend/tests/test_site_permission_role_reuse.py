import unittest
from types import SimpleNamespace

from services.site_permission_service import get_project_role, has_project_permission


class CountingClient:
    def __init__(self):
        self.reads = []
        self.tables = {
            "tenant_site_project_role_assignments": [{"membership_id": 11, "project_id": "project-1", "role_id": "role-1"}],
            "tenant_site_project_roles": [{"id": "role-1", "project_id": "project-1", "role_key": "members", "capabilities": ["view_protected_page"], "deleted_at": None}],
        }

    def table(self, name):
        client = self

        class Query:
            filters = []

            def select(self, *_args):
                self.filters = []
                return self

            def eq(self, field, value):
                self.filters.append((field, value))
                return self

            def is_(self, field, _value):
                self.filters.append((field, None))
                return self

            def limit(self, _size):
                return self

            def execute(self):
                client.reads.append(name)
                return SimpleNamespace(data=[row for row in client.tables[name] if all(row.get(f) == v for f, v in self.filters)])

        return Query()


PROJECT = {
    "id": "project-1",
    "published_schema": {
        "roles": [{"id": "members", "resourceAccess": {"pageIds": ["members-only", "home"]}}],
        "pages": [{"id": page_id} for page_id in ("home", "about", "members-only", "staff-only", "pricing", "contact")],
    },
}
MEMBERSHIPS = {
    "member": {"id": 11, "status": "active"},
    "staff": {"id": 12, "status": "active", "_access_kind": "staff"},
    "unassigned": {"id": 99, "status": "active"},
    "inactive": {"id": 11, "status": "suspended"},
}


class ProjectRoleReuseTests(unittest.TestCase):
    def page_access(self, membership, client, *, reuse):
        role = get_project_role(membership=membership, project_id="project-1", client=client) if reuse else None
        extra = {"role": role} if reuse else {}
        return {
            page["id"]: has_project_permission(
                membership=membership, project_id="project-1", capability="view_protected_page",
                client=client, project=PROJECT, resource_type="page", resource_id=page["id"], **extra,
            )
            for page in PROJECT["published_schema"]["pages"]
        }

    def test_one_role_lookup_gives_the_same_page_access_as_per_page_lookups(self):
        for kind, membership in MEMBERSHIPS.items():
            per_page, shared = CountingClient(), CountingClient()
            expected = self.page_access(membership, per_page, reuse=False)
            assert self.page_access(membership, shared, reuse=True) == expected, kind
            assert len(shared.reads) <= 2, (kind, shared.reads)
            if kind == "member":
                # Measured: two queries per page before, two per response now.
                assert len(per_page.reads) == 2 * len(PROJECT["published_schema"]["pages"]) == 12
                assert expected == {"home": True, "about": False, "members-only": True, "staff-only": False, "pricing": False, "contact": False}


if __name__ == "__main__":
    unittest.main()

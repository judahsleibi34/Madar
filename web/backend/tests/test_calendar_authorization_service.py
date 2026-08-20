import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from services.calendar_authorization_service import (
    availability_event,
    list_accessible_calendars,
    require_calendar_access,
    resolve_calendar_access,
)


class Query:
    def __init__(self, rows): self.rows = [dict(row) for row in rows]
    def select(self, *_args): return self
    def eq(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) == value]
        return self
    def limit(self, count): self.rows = self.rows[:count]; return self
    def or_(self, *_args): return self
    def order(self, *_args, **_kwargs): return self
    def execute(self): return SimpleNamespace(data=self.rows)


class Client:
    def __init__(self, role=None):
        self.tables = {
            "calendars": [{"id": "calendar-1", "tenant_id": 7, "owner_user_id": 10, "visibility": "private"}],
            "calendar_memberships": ([{"calendar_id": "calendar-1", "tenant_id": 7, "user_id": 20, "role": role}] if role else []),
        }
    def table(self, name): return Query(self.tables[name])


def context(user_id=20, role="member", status="active", tenant_id=7):
    return SimpleNamespace(
        user_id=user_id, tenant_id=tenant_id, role=role,
        membership_status=status,
    )


class CalendarAuthorizationTests(unittest.TestCase):
    def test_role_matrix_fails_closed(self):
        expectations = {
            "availability": {"view_availability"},
            "viewer": {"view_availability", "view_details"},
            "editor": {"view_details", "create_event", "manage_tasks", "view_conflicts", "view_sync_state"},
            "owner": {"view_details", "create_event", "manage_members", "manage_oauth_connection"},
        }
        for role, allowed in expectations.items():
            with self.subTest(role=role):
                access = resolve_calendar_access(context(), "calendar-1", client=Client(role))
                for capability in allowed:
                    self.assertTrue(access.allows(capability))
                if role != "owner":
                    self.assertFalse(access.allows("manage_members"))

    def test_tenant_admin_override_is_explicit(self):
        access = resolve_calendar_access(context(role="admin"), "calendar-1", client=Client())
        self.assertTrue(access.tenant_admin_override)
        self.assertTrue(access.allows("manage_oauth_connection"))

    def test_calendar_owner_has_full_control(self):
        access = resolve_calendar_access(context(user_id=10), "calendar-1", client=Client())
        self.assertEqual(access.role, "owner")
        self.assertTrue(access.allows("manage_members"))

    def test_unrelated_private_calendar_member_is_hidden(self):
        with self.assertRaises(HTTPException) as raised:
            resolve_calendar_access(context(), "calendar-1", client=Client())
        self.assertEqual(raised.exception.status_code, 404)

    def test_disabled_and_cross_tenant_contexts_fail_closed(self):
        with self.assertRaises(HTTPException):
            resolve_calendar_access(context(status="disabled"), "calendar-1", client=Client("owner"))
        with self.assertRaises(HTTPException):
            resolve_calendar_access(context(tenant_id=8), "calendar-1", client=Client("owner"))

    def test_viewer_cannot_write_and_editor_cannot_manage_members(self):
        for role, capability in (("viewer", "create_event"), ("editor", "manage_members"), ("availability", "view_details")):
            with self.subTest(role=role), self.assertRaises(HTTPException) as raised:
                require_calendar_access(context(), "calendar-1", capability, client=Client(role))
            self.assertEqual(raised.exception.status_code, 403)

    def test_availability_projection_contains_no_private_fields(self):
        projected = availability_event({
            "id": "event-1", "calendar_id": "calendar-1",
            "title": "Private title", "description": "Private description",
            "starts_at": "2026-07-22T09:00:00Z", "ends_at": "2026-07-22T10:00:00Z",
            "attendees": ["private@example.test"], "transparency": "busy",
        })
        self.assertEqual(projected["transparency"], "busy")
        self.assertNotIn("title", projected)
        self.assertNotIn("description", projected)
        self.assertNotIn("event-1", projected["id"])
        self.assertNotIn("attendees", projected)

    def test_accessible_calendar_listing_excludes_unrelated_private_calendars(self):
        client = Client("viewer")
        client.tables["calendars"].extend([
            {"id": "private-unrelated", "tenant_id": 7, "owner_user_id": 99, "visibility": "private"},
            {"id": "organization-shared", "tenant_id": 7, "owner_user_id": 99, "visibility": "organization"},
            {"id": "cross-tenant", "tenant_id": 8, "owner_user_id": 20, "visibility": "public"},
        ])
        accesses = list_accessible_calendars(context(), client=client)
        ids = {access.calendar["id"] for access in accesses}
        self.assertEqual(ids, {"calendar-1", "organization-shared"})


if __name__ == "__main__":
    unittest.main()

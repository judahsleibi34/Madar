import unittest
from unittest.mock import patch

from services import website_settings_service


class FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class RecordingQuery:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.filters = []
        self.payload = None

    def select(self, _columns):
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def limit(self, _value):
        return self

    def execute(self):
        return FakeResponse(self.rows)


class RecordingSupabase:
    def __init__(self, rows=None):
        self.query = RecordingQuery(rows)

    def table(self, name):
        if name != "website_settings":
            raise AssertionError(f"Unexpected table: {name}")
        return self.query


class WebsiteSettingsTenantIsolationTests(unittest.TestCase):
    def test_read_is_scoped_to_authenticated_tenant(self):
        fake = RecordingSupabase([{"id": 4, "tenant_id": 17}])

        with patch.object(website_settings_service, "service_supabase", fake):
            result = website_settings_service.get_settings_for_tenant(17, 3)

        self.assertEqual(result["tenant_id"], 17)
        self.assertIn(("tenant_id", 17), fake.query.filters)

    def test_update_reasserts_tenant_ownership_in_write_filter(self):
        fake = RecordingSupabase([{"id": 4, "tenant_id": 17, "brand": "Mine"}])

        with patch.object(website_settings_service, "service_supabase", fake), patch.object(
            website_settings_service,
            "get_settings_for_tenant",
            return_value={"id": 4, "tenant_id": 17},
        ):
            website_settings_service.save_settings_for_tenant(17, 3, {"brand": "Mine"})

        self.assertIn(("id", 4), fake.query.filters)
        self.assertIn(("tenant_id", 17), fake.query.filters)
        self.assertEqual(fake.query.payload["tenant_id"], 17)


if __name__ == "__main__":
    unittest.main()

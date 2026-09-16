from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from pydantic import ValidationError

WEB_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = WEB_ROOT / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from routes import builder_routes, public_site_routes


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTableQuery:
    def __init__(self, data):
        self.data = data
        self.tenant_id = None

    def select(self, *_args):
        return self

    def eq(self, column, value):
        if column == "tenant_id":
            self.tenant_id = value
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        return FakeResult(self.data)


class FakeSupabase:
    def __init__(self, metrics=None):
        self.metrics = metrics or []
        self.rpc_name = None
        self.rpc_payload = None
        self.query = None

    def table(self, name):
        if name != "site_visit_counters":
            raise AssertionError(f"unexpected table: {name}")
        self.query = FakeTableQuery(self.metrics)
        return self.query

    def rpc(self, name, payload):
        self.rpc_name = name
        self.rpc_payload = payload
        return FakeTableQuery([])


class SiteVisitMetricsTests(unittest.TestCase):
    def test_public_visit_uses_atomic_tenant_rpc(self):
        client = FakeSupabase()
        visit = public_site_routes.PublicSiteVisitCreate(surface="store")
        with (
            patch.object(public_site_routes, "service_supabase", client),
            patch.object(public_site_routes, "normalize_subdomain", return_value="olive-house"),
            patch.object(public_site_routes, "enforce_public_rate_limit"),
            patch.object(
                public_site_routes,
                "resolve_website_settings",
                return_value={"tenant_id": 7},
            ),
        ):
            result = public_site_routes.record_public_site_visit(
                "olive-house",
                visit,
                object(),
            )

        self.assertEqual(result, {"success": True})
        self.assertEqual(client.rpc_name, "record_public_site_visit_safe")
        self.assertEqual(
            client.rpc_payload,
            {"p_tenant_id": 7, "p_surface": "store"},
        )

    def test_visit_surface_is_allowlisted(self):
        with self.assertRaises(ValidationError):
            public_site_routes.PublicSiteVisitCreate(surface="admin")

    def test_authenticated_metrics_are_tenant_scoped(self):
        client = FakeSupabase([
            {"website_visits": 42, "store_visits": 17},
        ])
        with (
            patch.object(builder_routes, "service_supabase", client),
            patch.object(
                builder_routes,
                "require_builder_context",
                return_value=SimpleNamespace(tenant_id=7),
            ),
        ):
            result = builder_routes.read_site_visit_metrics(object(), object())

        self.assertEqual(client.query.tenant_id, 7)
        self.assertEqual(result["website_visits"], 42)
        self.assertEqual(result["store_visits"], 17)
        self.assertTrue(result["available"])

    def test_schema_098_is_mirrored_and_contains_no_visitor_identity(self):
        database = WEB_ROOT / "database/migrations/098_create_site_visit_counters.sql"
        supabase = WEB_ROOT / "supabase/migrations/098_create_site_visit_counters.sql"
        self.assertEqual(database.read_bytes(), supabase.read_bytes())
        sql = database.read_text(encoding="utf-8").lower()
        self.assertIn("record_public_site_visit_safe", sql)
        self.assertIn("on conflict (tenant_id)", sql)
        self.assertIn("tenant.lifecycle_state = 'active'", sql)
        self.assertIn("p_surface is null", sql)
        self.assertIn("schema_version = 98", sql)
        self.assertNotIn("visitor_id", sql)
        self.assertNotIn("ip_address", sql)
        self.assertNotIn("user_agent", sql)


if __name__ == "__main__":
    unittest.main()

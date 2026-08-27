import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services import tenant_lifecycle_service


class Query:
    def __init__(self, rows): self.rows = rows; self.filters = []
    def select(self, *_args): return self
    def eq(self, key, value): self.filters.append((key, value)); return self
    def limit(self, *_args): return self
    def execute(self):
        return SimpleNamespace(data=[row for row in self.rows if all(row.get(k) == v for k, v in self.filters)])


class TenantLifecycleGateTests(unittest.TestCase):
    def test_production_gate_fails_closed_for_pending_and_missing_tenant(self):
        client = SimpleNamespace(table=lambda _name: Query([
            {"tenant_id": 1, "lifecycle_state": "active"},
            {"tenant_id": 2, "lifecycle_state": "deletion_pending"},
        ]))
        with patch.dict(os.environ, {"APP_ENV": "production"}):
            self.assertTrue(tenant_lifecycle_service.tenant_is_active(1, client=client))
            self.assertFalse(tenant_lifecycle_service.tenant_is_active(2, client=client))
            self.assertFalse(tenant_lifecycle_service.tenant_is_active(3, client=client))

    def test_offline_suite_must_explicitly_opt_into_database_lookup(self):
        unavailable = SimpleNamespace(table=lambda _name: (_ for _ in ()).throw(AssertionError("unexpected lookup")))
        with patch.dict(os.environ, {"APP_ENV": "test", "MADAR_TEST_TENANT_LIFECYCLE_LOOKUPS": ""}):
            self.assertTrue(tenant_lifecycle_service.tenant_is_active(1, client=unavailable))

    def test_schema_82_missing_column_is_an_explicit_bridge_not_generic_fail_open(self):
        class BridgeClient:
            def table(self, name):
                if name == "tenants":
                    return BrokenQuery("column tenants.lifecycle_state does not exist")
                return Query([{"contract_key": "core", "schema_version": 82}])

        class BrokenQuery(Query):
            def __init__(self, message): self.message = message
            def select(self, *_args): return self
            def eq(self, *_args): return self
            def limit(self, *_args): return self
            def execute(self): raise RuntimeError(self.message)

        with patch.dict(os.environ, {"APP_ENV": "production"}):
            self.assertTrue(tenant_lifecycle_service.tenant_is_active(1, client=BridgeClient()))
            self.assertFalse(
                tenant_lifecycle_service.tenant_is_active(
                    1,
                    client=SimpleNamespace(table=lambda _name: BrokenQuery("database timeout")),
                )
            )


if __name__ == "__main__":
    unittest.main()

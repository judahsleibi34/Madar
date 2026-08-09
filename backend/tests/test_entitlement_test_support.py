import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.entitlement_service import require_entitlement
from tests.entitlement_test_support import EntitlementTestState


class EntitlementTestBoundaryTests(unittest.TestCase):
    @staticmethod
    def client():
        app = FastAPI()

        @app.get("/tenant/{tenant_id}/data")
        def protected(tenant_id: str):
            require_entitlement(tenant_id, "data_import")
            return {"allowed": True}

        return TestClient(app)

    def test_explicit_allowance_reaches_route_and_denial_is_controlled(self):
        state = EntitlementTestState().allow_capability("tenant-a", "data_import")
        state.deny_capability("tenant-b", "data_import")
        with state.installed():
            allowed = self.client().get("/tenant/tenant-a/data")
            denied = self.client().get("/tenant/tenant-b/data")
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(denied.status_code, 402)
        self.assertEqual(denied.json()["detail"]["code"], "entitlement_required")

    def test_unconfigured_tenant_remains_fail_closed(self):
        with EntitlementTestState().installed():
            response = self.client().get("/tenant/missing/data")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"]["code"],
            "entitlement_dependency_unavailable",
        )


if __name__ == "__main__":
    unittest.main()

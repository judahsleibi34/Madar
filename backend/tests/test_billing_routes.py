import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import billing_routes
from services import billing_service


def build_client():
    app = FastAPI()
    app.include_router(billing_routes.router)
    return TestClient(app)


class BillingRoutesTests(unittest.TestCase):
    def test_canonical_checkout_requires_auth(self):
        client = build_client()

        response = client.post(
            "/billing/checkout",
            json={
                "subscription_type": "full_platform",
                "plan": "pro",
                "builder_type": None,
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Not logged in")

    def test_canonical_checkout_persists_pending_feature(self):
        client = build_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}
        feature = {
            "id": 11,
            "tenant_id": 7,
            "subscription_type": "individual_builder",
            "plan": "basic",
            "builder_type": "website",
            "payment_status": "pending",
        }

        with patch.object(
            billing_routes,
            "require_regular_user",
            return_value=(object(), user_data),
        ), patch.object(
            billing_routes,
            "apply_pending_checkout_selection",
            return_value=feature,
        ) as apply_update:
            response = client.post(
                "/billing/checkout",
                json={
                    "subscription_type": "individual_builder",
                    "plan": "basic",
                    "builder_type": "website",
                },
            )

        self.assertEqual(response.status_code, 200)
        apply_update.assert_called_once_with(
            tenant_id=7,
            subscription_type="individual_builder",
            plan="basic",
            builder_type="website",
            updated_by_user_id=3,
        )
        body = response.json()
        self.assertTrue(body["success"])
        self.assertTrue(body["requires_payment"])
        self.assertIn("saved", body["message"].lower())
        self.assertEqual(body["data"], feature)
        self.assertEqual(
            body["checkout"],
            {
                "tenant_id": 7,
                "subscription_type": "individual_builder",
                "plan": "basic",
                "builder_type": "website",
                "payment_status": "pending",
            },
        )

    def test_canonical_checkout_full_platform_stores_null_builder_type(self):
        client = build_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}
        feature = {
            "id": 12,
            "tenant_id": 7,
            "subscription_type": "full_platform",
            "plan": "pro",
            "builder_type": None,
            "payment_status": "pending",
        }

        with patch.object(
            billing_routes,
            "require_regular_user",
            return_value=(object(), user_data),
        ), patch.object(
            billing_routes,
            "apply_pending_checkout_selection",
            return_value=feature,
        ) as apply_update:
            response = client.post(
                "/billing/checkout",
                json={
                    "subscription_type": "full_platform",
                    "plan": "pro",
                    "builder_type": None,
                },
            )

        self.assertEqual(response.status_code, 200)
        apply_update.assert_called_once_with(
            tenant_id=7,
            subscription_type="full_platform",
            plan="pro",
            builder_type=None,
            updated_by_user_id=3,
        )
        self.assertIsNone(response.json()["checkout"]["builder_type"])
        self.assertEqual(response.json()["checkout"]["payment_status"], "pending")

    def test_user_scoped_checkout_still_persists_pending_feature(self):
        client = build_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}
        feature = {
            "id": 13,
            "tenant_id": 7,
            "subscription_type": "full_platform",
            "plan": "starter",
            "builder_type": None,
            "payment_status": "pending",
        }

        with patch.object(
            billing_routes,
            "require_regular_user_id",
            return_value=(object(), user_data),
        ) as require_user_id, patch.object(
            billing_routes,
            "apply_pending_checkout_selection",
            return_value=feature,
        ) as apply_update:
            response = client.post(
                "/users/3/billing/checkout",
                json={
                    "subscription_type": "full_platform",
                    "plan": "starter",
                    "builder_type": None,
                },
            )

        self.assertEqual(response.status_code, 200)
        require_user_id.assert_called_once()
        self.assertEqual(require_user_id.call_args.args[0], 3)
        apply_update.assert_called_once_with(
            tenant_id=7,
            subscription_type="full_platform",
            plan="starter",
            builder_type=None,
            updated_by_user_id=3,
        )
        self.assertEqual(response.json()["checkout"]["tenant_id"], 7)

    def test_user_scoped_checkout_rejects_mismatched_user_id(self):
        client = build_client()

        with patch.object(
            billing_routes,
            "require_regular_user_id",
            side_effect=billing_routes.HTTPException(
                status_code=403,
                detail="User id does not match session",
            ),
        ), patch.object(
            billing_routes,
            "apply_pending_checkout_selection",
        ) as apply_update:
            response = client.post(
                "/users/4/billing/checkout",
                json={
                    "subscription_type": "full_platform",
                    "plan": "starter",
                    "builder_type": None,
                },
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "User id does not match session")
        apply_update.assert_not_called()

    def test_feature_type_route_is_not_restored(self):
        client = build_client()

        response = client.post(
            "/feature-type",
            json={
                "subscription_type": "full_platform",
                "plan": "pro",
                "builder_type": None,
            },
        )

        self.assertEqual(response.status_code, 404)


class FakeBillingExecuteResult:
    def __init__(self, data):
        self.data = data


class FakeBillingMutation:
    def __init__(self, table):
        self.table = table
        self.filters = []

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def execute(self):
        if self.table.operation == "insert":
            return FakeBillingExecuteResult([self.table.payload])

        return FakeBillingExecuteResult([self.table.payload])


class FakeBillingTable:
    def __init__(self):
        self.operation = None
        self.payload = None
        self.mutation = None

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        self.mutation = FakeBillingMutation(self)
        return self.mutation

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        self.mutation = FakeBillingMutation(self)
        return self.mutation


class FakeBillingSupabase:
    def __init__(self):
        self.tables = []

    def table(self, name):
        self.tables.append((name, FakeBillingTable()))
        return self.tables[-1][1]


class BillingServiceTests(unittest.TestCase):
    def test_apply_pending_checkout_inserts_new_feature(self):
        fake_supabase = FakeBillingSupabase()

        with patch.object(
            billing_service,
            "get_existing_feature_for_tenant",
            return_value=None,
        ), patch.object(
            billing_service,
            "service_supabase",
            fake_supabase,
        ):
            feature = billing_service.apply_pending_checkout_selection(
                tenant_id=7,
                subscription_type="full_platform",
                plan="pro",
                builder_type=None,
                updated_by_user_id=3,
            )

        table_name, table = fake_supabase.tables[0]
        self.assertEqual(table_name, "features")
        self.assertEqual(table.operation, "insert")
        self.assertEqual(feature["tenant_id"], 7)
        self.assertEqual(feature["subscription_type"], "full_platform")
        self.assertEqual(feature["plan"], "pro")
        self.assertIsNone(feature["builder_type"])
        self.assertEqual(feature["payment_status"], "pending")

    def test_apply_pending_checkout_updates_existing_feature(self):
        fake_supabase = FakeBillingSupabase()

        with patch.object(
            billing_service,
            "get_existing_feature_for_tenant",
            return_value={"id": 44, "tenant_id": 7},
        ), patch.object(
            billing_service,
            "service_supabase",
            fake_supabase,
        ):
            feature = billing_service.apply_pending_checkout_selection(
                tenant_id=7,
                subscription_type="individual_builder",
                plan="premium",
                builder_type="forms",
                updated_by_user_id=3,
            )

        table_name, table = fake_supabase.tables[0]
        self.assertEqual(table_name, "features")
        self.assertEqual(table.operation, "update")
        self.assertIn(("id", 44), table.mutation.filters)
        self.assertIn(("tenant_id", 7), table.mutation.filters)
        self.assertEqual(feature["subscription_type"], "individual_builder")
        self.assertEqual(feature["plan"], "premium")
        self.assertEqual(feature["builder_type"], "forms")
        self.assertEqual(feature["payment_status"], "pending")

    def test_verified_billing_update_can_mark_feature_active(self):
        fake_supabase = FakeBillingSupabase()

        with patch.object(
            billing_service,
            "get_existing_feature_for_tenant",
            return_value={"id": 45, "tenant_id": 7},
        ), patch.object(
            billing_service,
            "service_supabase",
            fake_supabase,
        ):
            feature = billing_service.apply_verified_billing_update(
                tenant_id=7,
                subscription_type="full_platform",
                plan="business",
                builder_type=None,
                payment_status="active",
                source="admin",
                updated_by_user_id=1,
            )

        table_name, table = fake_supabase.tables[0]
        self.assertEqual(table_name, "features")
        self.assertEqual(table.operation, "update")
        self.assertEqual(feature["subscription_type"], "full_platform")
        self.assertEqual(feature["plan"], "business")
        self.assertIsNone(feature["builder_type"])
        self.assertEqual(feature["payment_status"], "active")

    def test_individual_builder_checkout_requires_builder_type(self):
        with self.assertRaises(billing_service.HTTPException) as context:
            billing_service.apply_pending_checkout_selection(
                tenant_id=7,
                subscription_type="individual_builder",
                plan="basic",
                builder_type=None,
                updated_by_user_id=3,
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("builder_type is required", context.exception.detail)


if __name__ == "__main__":
    unittest.main()

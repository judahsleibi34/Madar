import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes import admin_billing_routes, billing_routes
from services import billing_service


def build_client():
    app = FastAPI()
    app.include_router(billing_routes.router)
    return TestClient(app)


def fake_tenant_context(tenant_id=7, user_id=3):
    return SimpleNamespace(tenant_id=tenant_id, user_id=user_id)


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
            "require_active_tenant_member",
            return_value=fake_tenant_context(
                tenant_id=user_data.get("tenant_id"),
                user_id=user_data.get("id"),
            ),
        ), patch.object(
            billing_routes,
            "apply_pending_checkout_selection",
            return_value=feature,
        ) as apply_update, patch.object(
            billing_routes,
            "record_audit_event",
        ):
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
        self.assertFalse(body["requires_payment"])
        self.assertFalse(body["checkout_available"])
        self.assertEqual(body["code"], "billing_not_configured")
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
            "require_active_tenant_member",
            return_value=fake_tenant_context(
                tenant_id=user_data.get("tenant_id"),
                user_id=user_data.get("id"),
            ),
        ), patch.object(
            billing_routes,
            "apply_pending_checkout_selection",
            return_value=feature,
        ) as apply_update, patch.object(
            billing_routes,
            "record_audit_event",
        ):
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

    def test_canonical_checkout_rejects_membership_mismatch_before_persisting(self):
        client = build_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}

        with patch.object(
            billing_routes,
            "require_active_tenant_member",
            side_effect=billing_routes.HTTPException(
                status_code=403,
                detail="Active tenant membership required",
            ),
        ), patch.object(
            billing_routes,
            "apply_pending_checkout_selection",
        ) as apply_update, patch.object(
            billing_routes,
            "record_audit_event",
        ) as record_audit:
            response = client.post(
                "/billing/checkout",
                json={
                    "subscription_type": "individual_builder",
                    "plan": "basic",
                    "builder_type": "website",
                },
            )

        self.assertEqual(response.status_code, 403)
        apply_update.assert_not_called()
        record_audit.assert_not_called()

    def test_canonical_checkout_rejects_inactive_membership_before_persisting(self):
        client = build_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}

        with patch.object(
            billing_routes,
            "require_active_tenant_member",
            side_effect=billing_routes.HTTPException(
                status_code=403,
                detail="Active tenant membership required",
            ),
        ), patch.object(
            billing_routes,
            "apply_pending_checkout_selection",
        ) as apply_update, patch.object(
            billing_routes,
            "record_audit_event",
        ) as record_audit:
            response = client.post(
                "/billing/checkout",
                json={
                    "subscription_type": "full_platform",
                    "plan": "pro",
                    "builder_type": None,
                },
            )

        self.assertEqual(response.status_code, 403)
        apply_update.assert_not_called()
        record_audit.assert_not_called()

    def test_canonical_checkout_ignores_client_supplied_protected_fields(self):
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
            "require_active_tenant_member",
            return_value=fake_tenant_context(
                tenant_id=user_data.get("tenant_id"),
                user_id=user_data.get("id"),
            ),
        ), patch.object(
            billing_routes,
            "apply_pending_checkout_selection",
            return_value=feature,
        ) as apply_update, patch.object(
            billing_routes,
            "record_audit_event",
        ):
            response = client.post(
                "/billing/checkout",
                json={
                    "tenant_id": 99,
                    "payment_status": "active",
                    "billing_status": "active",
                    "user_type": "admin",
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
            "require_active_tenant_member",
            return_value=fake_tenant_context(
                tenant_id=user_data.get("tenant_id"),
                user_id=user_data.get("id"),
            ),
        ) as require_user_id, patch.object(
            billing_routes,
            "apply_pending_checkout_selection",
            return_value=feature,
        ) as apply_update, patch.object(
            billing_routes,
            "record_audit_event",
        ):
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
            "require_active_tenant_member",
            return_value=fake_tenant_context(tenant_id=7, user_id=3),
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


    def test_successful_checkout_records_pending_audit(self):
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
            "require_active_tenant_member",
            return_value=fake_tenant_context(
                tenant_id=user_data.get("tenant_id"),
                user_id=user_data.get("id"),
            ),
        ), patch.object(
            billing_routes,
            "apply_pending_checkout_selection",
            return_value=feature,
        ), patch.object(billing_routes, "record_audit_event") as record_audit:
            response = client.post(
                "/billing/checkout",
                json={
                    "subscription_type": "individual_builder",
                    "plan": "basic",
                    "builder_type": "website",
                    "token": "not-accepted-by-schema",
                },
            )

        self.assertEqual(response.status_code, 200)
        record_audit.assert_called_once()
        audit_kwargs = record_audit.call_args.kwargs
        self.assertEqual(audit_kwargs["tenant_id"], 7)
        self.assertEqual(audit_kwargs["actor_user_id"], 3)
        self.assertEqual(audit_kwargs["action"], "billing.checkout_selected")
        self.assertEqual(audit_kwargs["target_type"], "billing_selection")
        self.assertEqual(audit_kwargs["target_id"], 11)
        self.assertEqual(
            audit_kwargs["metadata"],
            {
                "plan_type": "individual_builder",
                "subscription_type": "individual_builder",
                "plan": "basic",
                "builder_type": "website",
                "selected_features": ["website"],
                "payment_status": "pending",
                "source": "checkout",
            },
        )
        self.assertNotIn("active", audit_kwargs["metadata"].values())
        self.assertNotIn("token", str(audit_kwargs["metadata"]).lower())
        self.assertNotIn("cookie", str(audit_kwargs["metadata"]).lower())
        self.assertNotIn("raw_body", str(audit_kwargs["metadata"]).lower())

    def test_failed_checkout_does_not_record_audit(self):
        client = build_client()

        with patch.object(
            billing_routes,
            "require_active_tenant_member",
            side_effect=billing_routes.HTTPException(status_code=401, detail="Not logged in"),
        ), patch.object(billing_routes, "record_audit_event") as record_audit:
            response = client.post(
                "/billing/checkout",
                json={
                    "subscription_type": "full_platform",
                    "plan": "pro",
                    "builder_type": None,
                },
            )

        self.assertEqual(response.status_code, 401)
        record_audit.assert_not_called()

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


def build_admin_billing_client():
    app = FastAPI()
    app.include_router(admin_billing_routes.router)
    return TestClient(app)


class AdminBillingRoutesTests(unittest.TestCase):
    def test_successful_admin_billing_update_records_audit(self):
        client = build_admin_billing_client()
        admin_user = {"id": 1, "tenant_id": 99, "user_type": "admin"}
        feature = {
            "id": 45,
            "tenant_id": 7,
            "subscription_type": "full_platform",
            "plan": "business",
            "builder_type": None,
            "payment_status": "active",
        }

        with patch.object(
            admin_billing_routes,
            "require_system_admin",
            return_value=(object(), admin_user),
        ), patch.object(
            admin_billing_routes,
            "apply_verified_billing_update",
            return_value=feature,
        ) as apply_update, patch.object(admin_billing_routes, "record_audit_event") as record_audit:
            response = client.post(
                "/admin/billing/features",
                json={
                    "tenant_id": 7,
                    "subscription_type": "full_platform",
                    "plan": "business",
                    "builder_type": None,
                    "payment_status": "active",
                },
            )

        self.assertEqual(response.status_code, 200)
        apply_update.assert_called_once_with(
            tenant_id=7,
            subscription_type="full_platform",
            plan="business",
            builder_type=None,
            payment_status="active",
            source="admin",
            updated_by_user_id=1,
        )
        record_audit.assert_called_once()
        audit_kwargs = record_audit.call_args.kwargs
        self.assertEqual(audit_kwargs["tenant_id"], 7)
        self.assertEqual(audit_kwargs["actor_user_id"], 1)
        self.assertEqual(audit_kwargs["action"], "admin.billing_feature_updated")
        self.assertEqual(audit_kwargs["target_type"], "billing_feature")
        self.assertEqual(audit_kwargs["target_id"], 45)
        self.assertEqual(
            audit_kwargs["metadata"],
            {
                "plan_type": "full_platform",
                "subscription_type": "full_platform",
                "plan": "business",
                "builder_type": None,
                "payment_status": "active",
                "source": "admin",
            },
        )
        self.assertNotIn("token", str(audit_kwargs["metadata"]).lower())
        self.assertNotIn("cookie", str(audit_kwargs["metadata"]).lower())
        self.assertNotIn("raw_body", str(audit_kwargs["metadata"]).lower())
        self.assertNotIn("secret", str(audit_kwargs["metadata"]).lower())

    def test_unauthorized_admin_billing_update_does_not_record_audit(self):
        client = build_admin_billing_client()

        with patch.object(
            admin_billing_routes,
            "require_system_admin",
            side_effect=HTTPException(status_code=403, detail="Admin access required"),
        ), patch.object(admin_billing_routes, "record_audit_event") as record_audit:
            response = client.post(
                "/admin/billing/features",
                json={
                    "tenant_id": 7,
                    "subscription_type": "full_platform",
                    "plan": "business",
                    "builder_type": None,
                    "payment_status": "active",
                },
            )

        self.assertEqual(response.status_code, 403)
        record_audit.assert_not_called()


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

    def test_placeholder_checkout_never_downgrades_active_feature(self):
        fake_supabase = FakeBillingSupabase()
        active_feature = {
            "id": 46,
            "tenant_id": 7,
            "subscription_type": "full_platform",
            "plan": "pro",
            "builder_type": None,
            "payment_status": "active",
        }

        with patch.object(
            billing_service,
            "get_existing_feature_for_tenant",
            return_value=active_feature,
        ), patch.object(
            billing_service,
            "service_supabase",
            fake_supabase,
        ):
            feature = billing_service.apply_pending_checkout_selection(
                tenant_id=7,
                subscription_type="full_platform",
                plan="business",
                builder_type=None,
                updated_by_user_id=3,
            )

        self.assertEqual(feature, active_feature)
        self.assertEqual(feature["payment_status"], "active")
        self.assertEqual(fake_supabase.tables, [])

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

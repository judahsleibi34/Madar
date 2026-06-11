import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import billing_routes


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

    def test_canonical_checkout_returns_placeholder_intent(self):
        client = build_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}

        with patch.object(
            billing_routes,
            "require_regular_user",
            return_value=(object(), user_data),
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
        body = response.json()
        self.assertTrue(body["success"])
        self.assertTrue(body["requires_payment"])
        self.assertEqual(
            body["checkout"],
            {
                "tenant_id": 7,
                "subscription_type": "individual_builder",
                "plan": "basic",
                "builder_type": "website",
            },
        )

    def test_user_scoped_checkout_still_works(self):
        client = build_client()
        user_data = {"id": 3, "tenant_id": 7, "user_type": "user"}

        with patch.object(
            billing_routes,
            "require_regular_user_id",
            return_value=(object(), user_data),
        ) as require_user_id:
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
        ):
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


if __name__ == "__main__":
    unittest.main()

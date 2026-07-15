import unittest
from unittest.mock import patch

from fastapi import HTTPException, FastAPI
from fastapi.testclient import TestClient

from routes import public_contact_routes
from services import error_codes


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self):
        self.insert_payload = None

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def execute(self):
        return FakeResponse([{**self.insert_payload, "id": 1}])


class FakeSupabase:
    def __init__(self):
        self.queries = []

    def table(self, table_name):
        query = FakeQuery()
        query.table_name = table_name
        self.queries.append(query)
        return query


def build_client():
    app = FastAPI()
    app.include_router(public_contact_routes.router)
    return TestClient(app)


class PublicContactRouteTests(unittest.TestCase):
    def test_public_contact_succeeds_with_valid_payload(self):
        fake_supabase = FakeSupabase()
        client = build_client()

        with patch.object(public_contact_routes, "service_supabase", fake_supabase), \
             patch.object(public_contact_routes, "enforce_public_contact_rate_limit"):
            response = client.post(
                "/public/contact",
                json={
                    "name": "  Ada Lovelace  ",
                    "phone": "  +972599203857  ",
                    "message": "  Hello Madar  ",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "success": True,
                "code": error_codes.CONTACT_RECEIVED,
                "message": "Contact message received",
            },
        )
        self.assertEqual(fake_supabase.queries[0].table_name, "contacts")
        self.assertEqual(
            fake_supabase.queries[0].insert_payload,
            {
                "name": "Ada Lovelace",
                "phone": "+972599203857",
                "message": "Hello Madar",
            },
        )

    def test_public_contact_succeeds_without_phone(self):
        fake_supabase = FakeSupabase()
        client = build_client()

        with patch.object(public_contact_routes, "service_supabase", fake_supabase), \
             patch.object(public_contact_routes, "enforce_public_contact_rate_limit"):
            response = client.post(
                "/public/contact",
                json={"name": "Ada", "message": "Hello"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(fake_supabase.queries[0].insert_payload["phone"])

    def test_empty_name_is_rejected(self):
        client = build_client()

        with patch.object(public_contact_routes, "enforce_public_contact_rate_limit"):
            response = client.post(
                "/public/contact",
                json={"name": "   ", "message": "Hello"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], error_codes.CONTACT_NAME_REQUIRED)
        self.assertEqual(response.json()["detail"]["message"], "Name is required")

    def test_empty_message_is_rejected(self):
        client = build_client()

        with patch.object(public_contact_routes, "enforce_public_contact_rate_limit"):
            response = client.post(
                "/public/contact",
                json={"name": "Ada", "message": "   "},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], error_codes.CONTACT_MESSAGE_REQUIRED)
        self.assertEqual(response.json()["detail"]["message"], "Message is required")

    def test_overlong_message_is_rejected_by_schema(self):
        client = build_client()

        response = client.post(
            "/public/contact",
            json={"name": "Ada", "message": "x" * 5001},
        )

        self.assertEqual(response.status_code, 422)

    def test_rate_limited_request_returns_429(self):
        client = build_client()

        with patch.object(
            public_contact_routes,
            "enforce_public_contact_rate_limit",
            side_effect=HTTPException(status_code=429, detail="Too many requests. Please try again later."),
        ):
            response = client.post(
                "/public/contact",
                json={"name": "Ada", "message": "Hello"},
            )

        self.assertEqual(response.status_code, 429)

    def test_endpoint_does_not_require_auth(self):
        fake_supabase = FakeSupabase()
        client = build_client()

        with patch.object(public_contact_routes, "service_supabase", fake_supabase), \
             patch.object(public_contact_routes, "enforce_public_contact_rate_limit"):
            response = client.post(
                "/public/contact",
                json={"name": "Ada", "message": "Hello"},
            )

        self.assertEqual(response.status_code, 200)

    def test_public_contact_router_does_not_define_auth_routes(self):
        paths = {route.path for route in public_contact_routes.router.routes}

        self.assertIn("/public/contact", paths)
        self.assertNotIn("/auth/login", paths)
        self.assertNotIn("/auth/signup", paths)
        self.assertNotIn("/auth/user_status", paths)


if __name__ == "__main__":
    unittest.main()

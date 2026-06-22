import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import user_routes


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeUsersQuery:
    def __init__(self):
        self.payload = None

    def update(self, payload):
        self.payload = payload
        return self

    def eq(self, *_args):
        return self

    def execute(self):
        return FakeResponse(
            [
                {
                    "id": 3,
                    "auth_id": "auth-1",
                    "tenant_id": 7,
                    "first_name": "Madar",
                    "last_name": "User",
                    "email": "madar@example.com",
                    "avatar": self.payload.get("avatar", "") if self.payload else "",
                    "user_type": "user",
                }
            ]
        )


class FakeSupabase:
    def __init__(self):
        self.users_query = FakeUsersQuery()

    def table(self, table_name):
        if table_name != "users":
            raise AssertionError(f"Unexpected table {table_name}")

        return self.users_query


def build_client():
    app = FastAPI()
    app.include_router(user_routes.router)
    return TestClient(app)


def fake_user():
    return {
        "id": 3,
        "auth_id": "auth-1",
        "tenant_id": 7,
        "first_name": "Madar",
        "last_name": "User",
        "email": "madar@example.com",
        "avatar": "",
        "user_type": "user",
    }


class UserProfileUrlValidationTests(unittest.TestCase):
    def test_profile_avatar_allows_uploaded_relative_path(self):
        client = build_client()
        fake_supabase = FakeSupabase()

        with patch.object(user_routes, "service_supabase", fake_supabase), \
             patch.object(user_routes, "require_regular_user_id", return_value=(object(), fake_user())):
            response = client.put(
                "/users/3/profile",
                json={"avatar": "/avatar_uploads/users/auth-1/photo.jpg"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            fake_supabase.users_query.payload["avatar"],
            "/avatar_uploads/users/auth-1/photo.jpg",
        )
        self.assertEqual(response.json()["user"]["avatar"], "/avatar_uploads/users/auth-1/photo.jpg")

    def test_profile_avatar_rejects_unsafe_url_string(self):
        client = build_client()
        fake_supabase = FakeSupabase()

        unsafe_values = [
            "javascript:alert(1)",
            "data:image/svg+xml;base64,PHN2Zy8+",
            "//evil.example/avatar.png",
        ]

        for unsafe_value in unsafe_values:
            with self.subTest(unsafe_value=unsafe_value), patch.object(
                user_routes,
                "service_supabase",
                fake_supabase,
            ), patch.object(user_routes, "require_regular_user_id", return_value=(object(), fake_user())):
                response = client.put(
                    "/users/3/profile",
                    json={"avatar": unsafe_value},
                )

            self.assertEqual(response.status_code, 400)

    def test_profile_update_ignores_client_supplied_user_type_and_tenant_id(self):
        client = build_client()
        fake_supabase = FakeSupabase()

        with patch.object(user_routes, "service_supabase", fake_supabase), \
             patch.object(user_routes, "require_regular_user_id", return_value=(object(), fake_user())):
            response = client.put(
                "/users/3/profile",
                json={
                    "first_name": "Updated",
                    "tenant_id": 99,
                    "user_type": "admin",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_supabase.users_query.payload, {"first_name": "Updated"})
        self.assertEqual(response.json()["user"]["tenant_id"], 7)
        self.assertEqual(response.json()["user"]["user_type"], "user")


if __name__ == "__main__":
    unittest.main()

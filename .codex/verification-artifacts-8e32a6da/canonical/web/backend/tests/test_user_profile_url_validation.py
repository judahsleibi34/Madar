import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from routes import admin_profile_routes, user_routes


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


def build_profile_client():
    app = FastAPI()
    app.include_router(user_routes.router)
    app.include_router(admin_profile_routes.router)
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


def fake_admin():
    return {
        "id": 9,
        "auth_id": "admin-auth-1",
        "tenant_id": 7,
        "first_name": "Madar",
        "last_name": "Admin",
        "email": "admin@example.com",
        "avatar": "",
        "user_type": "admin",
    }


class UserProfileUrlValidationTests(unittest.TestCase):
    def test_profile_updates_first_and_last_name_together(self):
        client = build_client()
        fake_supabase = FakeSupabase()

        with patch.object(user_routes, "service_supabase", fake_supabase), patch.object(
            user_routes,
            "require_regular_user_id",
            return_value=(object(), fake_user()),
        ):
            response = client.put(
                "/users/3/profile",
                json={"first_name": "Updated", "last_name": "Owner"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            fake_supabase.users_query.payload,
            {"first_name": "Updated", "last_name": "Owner"},
        )

    def test_user_info_read_supports_get_without_mutation(self):
        client = build_client()
        with patch.object(
            user_routes,
            "require_regular_user_id",
            return_value=(object(), fake_user()),
        ), patch.object(
            user_routes,
            "get_billing_summary_for_tenant",
            return_value={},
        ):
            response = client.get("/users/3/info")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["first_name"], "Madar")

    def test_profile_same_email_is_unchanged_while_other_fields_update(self):
        client = build_client()
        fake_supabase = FakeSupabase()

        with patch.object(user_routes, "service_supabase", fake_supabase), patch.object(
            user_routes,
            "require_regular_user_id",
            return_value=(object(), fake_user()),
        ):
            response = client.put(
                "/users/3/profile",
                json={"email": "Madar@Example.COM", "first_name": "Updated"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_supabase.users_query.payload, {"first_name": "Updated"})

    def test_profile_changed_email_rejects_entire_update_atomically(self):
        client = build_client()
        fake_supabase = FakeSupabase()

        with patch.object(user_routes, "service_supabase", fake_supabase), patch.object(
            user_routes,
            "require_regular_user_id",
            return_value=(object(), fake_user()),
        ):
            response = client.put(
                "/users/3/profile",
                json={"email": "new@example.com", "first_name": "Must Not Change"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"]["code"],
            "email_change_requires_verification_flow",
        )
        self.assertIsNone(fake_supabase.users_query.payload)

    def test_admin_profile_changed_email_rejects_entire_update_atomically(self):
        client = build_profile_client()
        fake_supabase = FakeSupabase()
        provider_admin = type(
            "AuthUser",
            (),
            {"id": "admin-auth-1", "email": "admin@example.com"},
        )()

        with patch.object(
            admin_profile_routes,
            "service_supabase",
            fake_supabase,
        ), patch.object(
            admin_profile_routes,
            "require_system_admin",
            return_value=(provider_admin, fake_admin()),
        ), patch.object(admin_profile_routes, "record_security_event"):
            response = client.put(
                "/admin/profile/profile",
                json={"email": "new@example.com", "first_name": "Must Not Change"},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"]["code"],
            "email_change_requires_verification_flow",
        )
        self.assertIsNone(fake_supabase.users_query.payload)

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

    def test_user_avatar_upload_rate_limit_is_applied(self):
        client = build_profile_client()

        with patch.object(user_routes, "require_regular_user_id", return_value=(object(), fake_user())), \
             patch.object(
                 user_routes,
                 "enforce_avatar_upload_rate_limit",
                 side_effect=HTTPException(status_code=429, detail="Too many avatar uploads"),
             ) as enforce_limit:
            response = client.post(
                "/users/3/avatar",
                files={"file": ("avatar.png", b"\x89PNG\r\n\x1a\nabc", "image/png")},
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], "Too many avatar uploads")
        enforce_limit.assert_called_once()
        self.assertEqual(enforce_limit.call_args.args[1:], (3, 7))

    def test_admin_avatar_upload_rate_limit_is_applied(self):
        client = build_profile_client()

        with patch.object(admin_profile_routes, "require_system_admin", return_value=(object(), fake_admin())), \
             patch.object(
                 admin_profile_routes,
                 "enforce_avatar_upload_rate_limit",
                 side_effect=HTTPException(status_code=429, detail="Too many avatar uploads"),
             ) as enforce_limit:
            response = client.post(
                "/admin/profile/avatar",
                files={"file": ("avatar.png", b"\x89PNG\r\n\x1a\nabc", "image/png")},
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], "Too many avatar uploads")
        enforce_limit.assert_called_once()
        self.assertEqual(enforce_limit.call_args.args[1:], (9, 7))


if __name__ == "__main__":
    unittest.main()

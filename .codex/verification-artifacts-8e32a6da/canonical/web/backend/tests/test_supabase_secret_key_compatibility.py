import unittest

from services.supabase_api_key import (
    create_api_key_compatible_client,
    supabase_api_headers,
)


OPAQUE_SECRET_FIXTURE = "sb_secret_synthetic_fixture_not_a_credential"
LEGACY_JWT_FIXTURE = "synthetic-legacy-service-role-jwt"


def _lower_header_names(headers) -> set[str]:
    return {str(name).lower() for name in headers.keys()}


class SupabaseSecretKeyCompatibilityTests(unittest.TestCase):
    def test_opaque_secret_uses_apikey_without_bearer(self):
        headers = supabase_api_headers(OPAQUE_SECRET_FIXTURE)
        self.assertEqual(_lower_header_names(headers), {"apikey"})

    def test_legacy_service_role_retains_dual_headers(self):
        headers = supabase_api_headers(LEGACY_JWT_FIXTURE)
        self.assertEqual(_lower_header_names(headers), {"apikey", "authorization"})
        self.assertTrue(headers["Authorization"].startswith("Bearer "))

    def test_explicit_user_authorization_is_preserved_with_opaque_api_key(self):
        headers = supabase_api_headers(
            OPAQUE_SECRET_FIXTURE,
            authorization="Bearer synthetic-user-session-jwt",
        )
        self.assertEqual(_lower_header_names(headers), {"apikey", "authorization"})
        self.assertEqual(headers["Authorization"], "Bearer synthetic-user-session-jwt")

    def test_official_client_components_do_not_copy_opaque_secret_to_authorization(self):
        client = create_api_key_compatible_client(
            "https://example.supabase.co",
            OPAQUE_SECRET_FIXTURE,
        )
        component_headers = {
            "options": client.options.headers,
            "auth": client.auth._headers,
            "auth_admin": client.auth.admin._headers,
            "postgrest": client.postgrest.headers,
            "storage": client.storage._headers,
            "functions": client.functions.headers,
        }
        for component, headers in component_headers.items():
            with self.subTest(component=component):
                names = _lower_header_names(headers)
                self.assertIn("apikey", names)
                self.assertNotIn("authorization", names)

    def test_official_client_retains_legacy_service_role_behavior(self):
        client = create_api_key_compatible_client(
            "https://example.supabase.co",
            LEGACY_JWT_FIXTURE,
        )
        for headers in (
            client.options.headers,
            client.auth._headers,
            client.auth.admin._headers,
            client.postgrest.headers,
            client.storage._headers,
        ):
            self.assertIn("authorization", _lower_header_names(headers))


if __name__ == "__main__":
    unittest.main()

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from routes import google_sheets_routes
from services.google_sheets_connector import SCOPE


TRANSACTION = {
    "tenant_id": 7, "project_id": "11111111-1111-4111-8111-111111111111",
    "source_id": "22222222-2222-4222-8222-222222222222", "actor_user_id": 9,
}


class GoogleSheetsCallbackTests(unittest.TestCase):
    def callback_patches(self, *, tenant_id=7):
        return (
            patch.object(google_sheets_routes, "consume_oauth_transaction", return_value=TRANSACTION),
            patch.object(google_sheets_routes, "require_active_tenant_user_id",
                         return_value=SimpleNamespace(tenant_id=tenant_id, user_id=9)),
            patch.object(google_sheets_routes.project_data_source_service,
                         "get_project_data_source", return_value={"provider_key": "google_sheets"}),
        )

    def test_callback_exchanges_only_after_bound_session_and_stores_reduced_refresh_credential(self):
        first, second, third = self.callback_patches()
        resolved = SimpleNamespace(secret=SimpleNamespace(reveal_for_request=lambda: "pkce-verifier"))
        with first, second, third, patch.object(
            google_sheets_routes.data_source_credential_service,
            "resolve_persistent_credential", return_value=resolved,
        ), patch.object(
            google_sheets_routes, "exchange_authorization_code",
            return_value={"access_token": "short", "refresh_token": "durable", "scope": SCOPE},
        ) as exchange, patch.object(
            google_sheets_routes.data_source_credential_service, "provision_credential",
        ) as provision, patch.object(google_sheets_routes, "google_sheets_config", return_value=object()):
            response = google_sheets_routes.google_sheets_oauth_callback(
                object(), object(), state="opaque-state", code="authorization-code", error=None,
            )
        self.assertEqual(response.status_code, 303)
        self.assertIn(f"/data-sources/projects/{TRANSACTION['project_id']}/data", response.headers["location"])
        exchange.assert_called_once_with(unittest.mock.ANY, "authorization-code", "pkce-verifier")
        stored = provision.call_args.kwargs["secret"]
        self.assertIn("durable", stored)
        self.assertNotIn("short", stored)
        self.assertEqual(provision.call_args.kwargs["credential_type"], "oauth_refresh")

    def test_cross_tenant_callback_never_exchanges_or_stores_tokens(self):
        first, second, third = self.callback_patches(tenant_id=8)
        with first, second, third, patch.object(
            google_sheets_routes, "exchange_authorization_code",
        ) as exchange, patch.object(
            google_sheets_routes.data_source_credential_service, "provision_credential",
        ) as provision:
            response = google_sheets_routes.google_sheets_oauth_callback(
                object(), object(), state="opaque-state", code="private-code", error=None,
            )
        self.assertEqual(response.status_code, 303)
        exchange.assert_not_called()
        provision.assert_not_called()
        self.assertNotIn("private-code", response.headers["location"])

    def test_denial_consumes_state_but_does_not_resolve_or_exchange(self):
        first, second, third = self.callback_patches()
        with first as consume, second, third, patch.object(
            google_sheets_routes.data_source_credential_service,
            "resolve_persistent_credential",
        ) as resolve, patch.object(google_sheets_routes, "exchange_authorization_code") as exchange:
            response = google_sheets_routes.google_sheets_oauth_callback(
                object(), object(), state="opaque-state", error="access_denied",
            )
        self.assertEqual(response.status_code, 303)
        consume.assert_called_once()
        resolve.assert_not_called()
        exchange.assert_not_called()


if __name__ == "__main__":
    unittest.main()

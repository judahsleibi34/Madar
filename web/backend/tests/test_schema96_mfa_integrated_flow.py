"""Request-level recovery evidence for login, MFA, AAL2 and logout."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from routes import auth_routes, mfa_routes
from services import auth_service


ADMIN = {
    "id": 99001, "auth_id": "schema96-admin-auth", "tenant_id": 99001,
    "email": "schema96-admin@example.com", "user_type": "admin",
    "account_status": "active", "email_verified_at": "2026-09-14T00:00:00Z",
}


class _UserQuery:
    def select(self, *_args): return self
    def eq(self, *_args): return self
    def single(self): return self
    def execute(self): return SimpleNamespace(data=dict(ADMIN))


class _ServiceClient:
    def table(self, name):
        if name != "users": raise AssertionError(name)
        return _UserQuery()


class _MfaProvider:
    def __init__(self):
        self.challenge_calls = 0
        self.verify_calls = 0
        self.auth = SimpleNamespace(
            mfa=SimpleNamespace(
                list_factors=self.list_factors,
                challenge=self.challenge,
                verify=self.verify,
                get_authenticator_assurance_level=lambda: SimpleNamespace(
                    data=SimpleNamespace(current_level="aal2")
                ),
            ),
            get_session=lambda: SimpleNamespace(session=SimpleNamespace(
                access_token="schema96-aal2-access",
                refresh_token="schema96-aal2-refresh",
            )),
        )

    @staticmethod
    def list_factors():
        return SimpleNamespace(data=SimpleNamespace(totp=[{
            "id": "schema96-factor", "factor_type": "totp", "status": "verified",
        }]))

    def challenge(self, payload):
        assert payload == {"factor_id": "schema96-factor"}
        self.challenge_calls += 1
        return SimpleNamespace(data=SimpleNamespace(id="schema96-challenge"))

    def verify(self, payload):
        assert payload == {
            "factor_id": "schema96-factor", "challenge_id": "schema96-challenge",
            "code": "123456",
        }
        self.verify_calls += 1
        return SimpleNamespace(data=SimpleNamespace(session=SimpleNamespace(
            access_token="schema96-aal2-access",
            refresh_token="schema96-aal2-refresh",
        )))


class Schema96MfaIntegratedFlowTests(unittest.TestCase):
    def test_existing_factor_login_aal2_privileged_flow_and_logout(self):
        app = FastAPI()
        app.include_router(auth_routes.router)
        app.include_router(mfa_routes.router)

        @app.get("/schema96-privileged")
        def privileged(request: Request, response: Response):
            _auth_user, user = auth_service.require_system_admin(
                request, response, require_aal2=True
            )
            return {"user_id": user["id"], "aal": "aal2"}

        client = TestClient(app, base_url="https://testserver")
        provider = _MfaProvider()
        password_session = SimpleNamespace(
            user=SimpleNamespace(
                id=ADMIN["auth_id"], email=ADMIN["email"],
                email_confirmed_at="2026-09-14T00:00:00Z",
            ),
            session=SimpleNamespace(
                access_token="schema96-aal1-access",
                refresh_token="schema96-aal1-refresh",
            ),
        )
        common_login = (
            patch.object(auth_routes, "enforce_auth_rate_limit"),
            patch.object(auth_routes.supabase.auth, "sign_in_with_password", return_value=password_session),
            patch.object(auth_routes, "get_local_user_by_auth_id", return_value=dict(ADMIN)),
            patch.object(auth_routes, "mark_local_email_verified", return_value=dict(ADMIN)),
            patch.object(auth_routes, "is_admin_mfa_login_enforcement_enabled", return_value=True),
            patch.object(auth_routes, "get_user_security_settings", return_value={"mfa_required": True}),
            patch.object(auth_routes, "create_pending_mfa_client", return_value=provider),
            patch.object(auth_routes, "record_security_event"),
        )
        with common_login[0], common_login[1], common_login[2], common_login[3], common_login[4], common_login[5], common_login[6], common_login[7]:
            login = client.post("/auth/login", json={
                "email": ADMIN["email"], "password": "synthetic-password",
            })
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()["mfa_required"])
        self.assertNotIn("madar_access_token", client.cookies)
        self.assertIn("madar_mfa_pending", client.cookies)

        with patch.object(mfa_routes, "create_pending_mfa_client", return_value=provider), patch.object(mfa_routes, "record_mfa_event"):
            challenge = client.post(
                "/auth/mfa/login/challenge", json={"factor_id": "schema96-factor"}
            )
        self.assertEqual(challenge.json(), {"challenge_id": "schema96-challenge"})

        with patch.object(mfa_routes, "create_pending_mfa_client", return_value=provider), patch.object(mfa_routes, "get_local_user_for_pending_mfa", return_value=dict(ADMIN)), patch.object(mfa_routes, "mark_aal2_verified"), patch.object(mfa_routes, "record_security_event"), patch.object(mfa_routes, "record_mfa_event"):
            verified = client.post("/auth/mfa/login/verify", json={
                "factor_id": "schema96-factor", "challenge_id": "schema96-challenge",
                "code": "123456",
            })
        self.assertEqual(verified.status_code, 200)
        self.assertIn("madar_access_token", client.cookies)
        self.assertNotIn("madar_mfa_pending", client.cookies)
        self.assertEqual(provider.challenge_calls, 1)
        self.assertEqual(provider.verify_calls, 1)

        with patch.object(auth_service.supabase.auth, "get_user", return_value=SimpleNamespace(user=SimpleNamespace(id=ADMIN["auth_id"], email_confirmed_at="2026-09-14T00:00:00Z"))), patch.object(auth_service, "service_supabase", _ServiceClient()), patch.object(auth_service, "get_current_aal", return_value={"current_level": "aal2"}):
            allowed = client.get("/schema96-privileged")
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json(), {"user_id": ADMIN["id"], "aal": "aal2"})

        with patch.object(auth_routes, "get_authenticated_user_row", return_value=(SimpleNamespace(id=ADMIN["auth_id"]), dict(ADMIN))), patch.object(auth_routes, "revoke_all_web_push_subscriptions"):
            logout = client.post("/auth/log_out")
        self.assertEqual(logout.status_code, 200)
        self.assertNotIn("madar_access_token", client.cookies)
        denied = client.get("/schema96-privileged")
        self.assertEqual(denied.status_code, 401)


if __name__ == "__main__":
    unittest.main()

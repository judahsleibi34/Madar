"""Adversarial session-bound AAL2 regression: no live Auth calls."""
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from fastapi import Request, Response, HTTPException
from services import auth_service
from tests.test_admin_mfa_aal2_enforcement import ADMIN_USER, _FakeServiceSupabase


def token(aal, *, subject="auth-admin", expires=None):
    return jwt.encode({"sub": subject, "aal": aal, "exp": int(time.time()) + 300 if expires is None else expires},
                      "isolated-test-signing-material-32-bytes", algorithm="HS256")


def request_for(value):
    return Request({"type": "http", "headers": [(b"cookie", ("madar_access_token=" + value).encode())]})


class RequestSessionAssuranceTests(unittest.TestCase):
    def authorize(self, value):
        request = request_for(value)
        auth_service.require_system_admin(request, Response(), require_aal2=True)
        return request

    def setUp(self):
        self.patches = [
            patch.object(auth_service.supabase.auth, "get_user", return_value=SimpleNamespace(
                user=SimpleNamespace(id="auth-admin", email_confirmed_at="2026-01-01T00:00:00Z", factors=[]))),
            patch.object(auth_service, "service_supabase", _FakeServiceSupabase(ADMIN_USER)),
            patch.object(auth_service, "mark_local_email_verified", side_effect=lambda u: u),
            patch.object(auth_service, "is_session_activity_valid", return_value=True),
            patch.object(auth_service.supabase.auth.mfa, "get_authenticator_assurance_level",
                         side_effect=AssertionError("Shared session must not authorize this request")),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_aal1_cannot_borrow_another_sessions_aal2(self):
        with self.assertRaises(HTTPException) as caught:
            self.authorize(token("aal1"))
        self.assertEqual(caught.exception.detail["code"], "aal2_required")

    def test_verified_aal2_grants_only_this_request(self):
        request = self.authorize(token("aal2"))
        self.assertEqual(auth_service.get_current_aal(request)["current_level"], "aal2")
        self.assertEqual(auth_service.get_current_aal(request_for(token("aal2"))), {})
        self.assertEqual(auth_service.get_current_aal(), {})

    def test_concurrent_request_assurance_is_isolated(self):
        def check(aal):
            try:
                self.authorize(token(aal))
                return True
            except HTTPException:
                return False
        levels = ["aal1", "aal2"] * 16
        with ThreadPoolExecutor(max_workers=8) as executor:
            actual = list(executor.map(check, levels))
        self.assertEqual(actual, [aal == "aal2" for aal in levels])

    def test_malformed_expired_subject_mismatch_and_unknown_aal_deny(self):
        for value in ["invalid", token("aal2", expires=0), token("aal2", subject="someone-else"), token("future-aal")]:
            with self.subTest(case=value[:8]), self.assertRaises(HTTPException):
                self.authorize(value)

    def test_provider_rejection_cannot_set_assurance(self):
        request = request_for(token("aal2"))
        with patch.object(auth_service.supabase.auth, "get_user", side_effect=RuntimeError("unavailable")):
            with self.assertRaises(HTTPException):
                auth_service.get_authenticated_user_row(request, Response())
        self.assertEqual(auth_service.get_current_aal(request), {})

    def test_reattempt_clears_previous_assurance_before_failure(self):
        request = self.authorize(token("aal2"))
        with patch.object(auth_service.supabase.auth, "get_user", return_value=SimpleNamespace(user=None)):
            with self.assertRaises(HTTPException):
                auth_service.get_authenticated_user_row(request, Response())
        self.assertEqual(auth_service.get_current_aal(request), {})


class MfaClientIsolationTests(unittest.TestCase):
    def test_two_requests_cannot_share_mfa_session(self):
        from unittest.mock import MagicMock
        requests = [request_for(token("aal2")) for _ in range(2)]
        clients = [MagicMock() for _ in range(2)]
        for index, request in enumerate(requests):
            request.state.verified_auth_session = {"access_token": f"verified-{index}", "refresh_token": "", "auth_id": str(index)}
            clients[index].auth.get_session.return_value = SimpleNamespace(user=SimpleNamespace(id=str(index)), access_token=f"verified-{index}", refresh_token="")
        with patch.object(auth_service, "create_session_supabase_client", side_effect=clients) as factory:
            for index, request in enumerate(requests):
                actual = auth_service.get_request_mfa_client(request, Response())
                self.assertIs(actual, clients[index])
                self.assertIs(auth_service.get_request_mfa_client(request, Response()), actual)
            self.assertEqual(factory.call_count, 2)
        for index, client in enumerate(clients):
            client.auth.set_session.assert_called_once_with(f"verified-{index}", "")

    def test_unverified_request_never_initializes_client(self):
        with patch.object(auth_service, "create_session_supabase_client") as factory:
            with self.assertRaises(HTTPException):
                auth_service.get_request_mfa_client(request_for(token("aal2")), Response())
            factory.assert_not_called()

    def test_subject_mismatch_after_initialization_fails_closed(self):
        from unittest.mock import MagicMock
        request = request_for(token("aal2"))
        request.state.verified_auth_session = {"access_token": "verified", "refresh_token": "", "auth_id": "expected"}
        client = MagicMock()
        client.auth.get_session.return_value = SimpleNamespace(user=SimpleNamespace(id="other"))
        with patch.object(auth_service, "create_session_supabase_client", return_value=client):
            with self.assertRaises(HTTPException):
                auth_service.get_request_mfa_client(request, Response())
        self.assertIsNone(getattr(request.state, "mfa_client", None))

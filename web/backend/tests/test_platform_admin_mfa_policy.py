import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException, Response
from starlette.requests import Request
from routes import mfa_routes
from services import auth_service


class PlatformAdminPolicyTests(unittest.TestCase):
    def test_role_and_account_kind_are_both_required(self):
        for row, expected in [
            ({"user_type": "admin", "account_kind": "platform"}, True),
            ({"user_type": "user", "account_kind": "platform"}, False),
            ({"user_type": "admin", "account_kind": "site_visitor"}, False),
        ]:
            with self.subTest(row=row):
                self.assertEqual(auth_service.is_platform_admin(row), expected)

    def test_status_reports_mandatory_policy_but_verified_factor_is_not_aal2(self):
        request = Request({"type": "http", "headers": []})
        for role, expected in [("admin", True), ("user", False)]:
            user = {"id": 42, "account_kind": "platform", "user_type": role}
            with patch.object(mfa_routes, "get_authenticated_user_row", return_value=(None, user)), \
                 patch.object(mfa_routes, "get_user_security_settings", return_value={"mfa_required": False, "last_aal2_at": "yesterday"}), \
                 patch.object(mfa_routes.supabase.auth.mfa, "list_factors", return_value={"all": [{"id": "totp", "factor_type": "totp", "status": "verified"}]}), \
                 patch.object(mfa_routes, "get_authenticator_assurance_level", return_value={"current_level": "aal1", "next_level": "aal2"}):
                status = mfa_routes.mfa_status(request, Response())
            self.assertEqual(status["mfa_required"], expected)
            self.assertEqual(status["aal"]["current_level"], "aal1")

    def test_provider_assurance_is_the_security_boundary(self):
        for level, allowed in [("aal1", False), (None, False), ("aal2", True)]:
            provider = SimpleNamespace(auth=SimpleNamespace(mfa=SimpleNamespace(
                get_authenticator_assurance_level=lambda: {"current_level": level, "next_level": "aal2"})))
            with patch.object(auth_service, "supabase", provider):
                if allowed:
                    self.assertEqual(auth_service.require_current_session_aal2()["current_level"], "aal2")
                else:
                    with self.assertRaises(HTTPException) as denied:
                        auth_service.require_current_session_aal2()
                    self.assertEqual(denied.exception.detail["code"], "aal2_required")

    def test_tenant_admin_cannot_gain_platform_privilege_at_aal2(self):
        request = Request({"type": "http", "headers": []})
        with patch.object(auth_service, "get_authenticated_user_row", return_value=(None, {"account_kind": "site_visitor", "user_type": "admin"})), \
             patch.object(auth_service, "get_current_aal", return_value={"current_level": "aal2"}):
            with self.assertRaises(HTTPException) as denied:
                auth_service.require_system_admin(request, require_aal2=True)
            self.assertEqual(denied.exception.status_code, 403)

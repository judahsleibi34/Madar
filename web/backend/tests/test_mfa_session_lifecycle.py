import unittest
from fastapi.testclient import TestClient
from services import auth_service
from mfa_sdk_lifecycle_fixture import sdk_cookie_fixture


class MfaSessionLifecycleTests(unittest.TestCase):
    def setUp(self):
        app, self.provider, self.store, self.shared, stack = sdk_cookie_fixture()
        self.addCleanup(stack.close)
        self.client = TestClient(app, base_url="https://testserver")
        self.addCleanup(self.client.close)

    def post(self, path, data):
        headers = {"Origin": "https://testserver"}
        csrf = self.client.cookies.get("madar_csrf_token")
        if csrf: headers["X-CSRF-Token"] = csrf
        return self.client.post(path, json=data, headers=headers)

    def login(self):
        primary = self.post("/auth/login", {"email": "synthetic@example.com", "password": "synthetic-password"})
        self.assertEqual(primary.status_code, 200, primary.text)
        self.assertTrue(primary.json()["mfa_required"])
        self.assertNotIn("madar_access_token", self.client.cookies)
        challenge = self.post("/auth/mfa/login/challenge", {"factor_id": "synthetic-factor"})
        self.assertEqual(challenge.status_code, 200, challenge.text)
        verified = self.post("/auth/mfa/login/verify", {"factor_id": "synthetic-factor", "challenge_id": challenge.json()["challenge_id"], "code": "123456"})
        self.assertEqual(verified.status_code, 200, verified.text)
        self.assertNotIn("madar_mfa_pending", self.client.cookies)
        return self.pair()

    def pair(self):
        return self.client.cookies.get("madar_access_token"), self.client.cookies.get("madar_refresh_token")

    def status(self, level="aal2"):
        result = self.client.get("/auth/mfa/status")
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()
        self.assertEqual(data["aal"]["current_level"], level)
        self.assertEqual(data["aal"]["next_level"], "aal2")
        self.assertEqual(data["factors"][0]["status"], "verified")
        return data

    def test_one_code_login_installs_provider_post_mfa_pair_and_status(self):
        access, refresh = self.login()
        self.assertEqual(self.provider.tokens[access][0], "aal2")
        self.assertEqual(self.provider.refresh[refresh], "aal2")
        # Shared SDK state still describes a different AAL1 session. It is not authority.
        self.assertEqual(self.shared.auth.mfa.get_authenticator_assurance_level().current_level, "aal1")
        self.status()
        self.assertEqual(self.provider.verify_count, 1)

    def test_direct_protected_admin_routes_need_no_second_code(self):
        self.login()
        for path in ["/lifecycle/protected", "/admin/users"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.provider.verify_count, 1)

    def test_expiry_refreshes_both_cookies_without_browser_refresh_endpoint(self):
        before = self.login()
        self.status()
        self.provider.now += 901
        self.status()
        after = self.pair()
        self.assertNotEqual(before[0], after[0])
        self.assertNotEqual(before[1], after[1])
        self.assertEqual(self.provider.refresh_count, 1)
        self.assertEqual(self.client.get("/auth/user_status").json()["logged_in"], True)
        self.assertEqual(self.provider.verify_count, 1)

    def test_multiple_rotations_never_restore_pre_mfa_credentials(self):
        previous = self.login()
        for _ in range(5):
            self.provider.now += 901
            result = self.client.get("/lifecycle/protected")
            self.assertEqual(result.status_code, 200, result.text)
            self.status()
            current = self.pair()
            self.assertNotEqual(current[0], previous[0])
            self.assertNotEqual(current[1], previous[1])
            self.assertEqual(self.provider.tokens[current[0]][0], "aal2")
            self.assertEqual(self.provider.refresh[current[1]], "aal2")
            previous = current
        self.assertEqual(self.provider.refresh_count, 5)
        self.assertEqual(self.provider.verify_count, 1)

    def test_provider_downgrade_keeps_factor_and_step_up_rotates_both_tokens(self):
        self.login()
        self.provider.downgrade = True
        self.provider.now += 901
        self.status("aal1")
        old_pair = self.pair()
        denied = self.client.get("/lifecycle/protected")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["detail"]["code"], "aal2_required")
        verified = self.post("/auth/mfa/enroll/verify", {"factor_id": "synthetic-factor", "code": "123456"})
        self.assertEqual(verified.status_code, 200, verified.text)
        self.assertNotEqual(old_pair[0], self.pair()[0])
        self.assertNotEqual(old_pair[1], self.pair()[1])
        self.provider.downgrade = False
        for _ in range(3):
            self.provider.now += 901
            self.status()
        self.assertFalse(any(method == "POST" and path == "factors" for method, path in self.provider.calls))

    def test_shared_client_empty_factor_state_cannot_collapse_cookie_session(self):
        self.login()
        self.shared.auth._in_memory_session.user.factors = []
        self.assertEqual(self.shared.auth.mfa.get_authenticator_assurance_level().next_level, "aal1")
        self.provider.now += 901
        self.status()
        self.assertTrue(self.client.get("/auth/user_status").json()["logged_in"])

    def test_another_shared_aal2_session_cannot_authorize_aal1_cookies(self):
        current = self.provider.issue("aal1")
        elevated = self.provider.issue("aal2")
        self.shared.auth.set_session(elevated["access_token"], elevated["refresh_token"])
        self.client.cookies.set("madar_access_token", current["access_token"])
        self.client.cookies.set("madar_refresh_token", current["refresh_token"])
        response = self.client.get("/lifecycle/protected")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "aal2_required")
        self.status("aal1")

    def test_auth_clients_have_no_background_refresh_or_shared_session_storage(self):
        self.login()
        client = auth_service.create_supabase_auth_client()
        self.assertFalse(client.auth._auto_refresh_token)
        self.assertFalse(client.auth._persist_session)
        self.assertIsNone(client.auth.get_session())
        self.assertIs(client.options.httpx_client, self.shared.options.httpx_client)

    def test_exact_live_collapse_from_other_worker_session_cannot_affect_admin(self):
        self.login()
        self.status()
        self.provider.now += 931
        other = self.provider.issue("aal1", "different-unenrolled-account")
        self.shared.auth.set_session(other["access_token"], other["refresh_token"])
        stale = self.shared.auth.mfa.get_authenticator_assurance_level()
        self.assertEqual((stale.current_level, stale.next_level), ("aal1", "aal1"))
        self.assertEqual(self.shared.auth.mfa.list_factors().all, [])
        # /user_status still authenticates the cookie's admin, while old MFA
        # status read the unrelated shared session. New status must stay coherent.
        self.status()
        restored = self.client.get("/auth/user_status").json()
        self.assertTrue(restored["logged_in"])
        self.assertEqual(restored["user"]["auth_id"], "synthetic-auth")

    def test_unchanged_read_cannot_reinstall_stale_pre_mfa_pair(self):
        old = self.provider.issue("aal1")
        self.login()
        with TestClient(self.client.app, base_url="https://testserver") as delayed:
            delayed.cookies.set("madar_access_token", old["access_token"])
            delayed.cookies.set("madar_refresh_token", old["refresh_token"])
            response = delayed.get("/auth/user_status")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["logged_in"])
        headers = response.headers.get_list("set-cookie")
        self.assertFalse(any(header.startswith("madar_access_token=") or header.startswith("madar_refresh_token=") for header in headers))
        self.status()

    def test_other_provider_account_cannot_use_admin_profile(self):
        other = self.provider.issue("aal2", "different-account")
        self.client.cookies.set("madar_access_token", other["access_token"])
        self.client.cookies.set("madar_refresh_token", other["refresh_token"])
        self.assertEqual(self.client.get("/lifecycle/protected").status_code, 404)

import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from local_dev_auth import LocalTestLoginMiddleware
from routes import auth_routes


class LocalTestLoginTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "APP_ENV": "development", "SUPABASE_DB_URL": "postgresql://127.0.0.1/postgres",
            "MADAR_TEST_EMAIL": "testing@example.com", "MADAR_TEST_PASSWORD": "test-password",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.database = patch("database.SUPABASE_URL", "http://127.0.0.1:54321")
        self.database.start()
        self.addCleanup(self.database.stop)
        app = FastAPI()
        app.add_middleware(LocalTestLoginMiddleware)
        self.client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 50000))

    def test_signs_in_normally_and_preserves_session_cookies(self):
        def login(user, response, request):
            self.assertEqual(user.email, "testing@example.com")
            response.set_cookie("madar_access_token", "local-session", httponly=True)
            return {"user": {"email": user.email}, "csrf_token": "local-csrf"}
        with patch.object(auth_routes, "user_status", return_value={"logged_in": False}), patch.object(auth_routes, "login", side_effect=login) as sign_in:
            response = self.client.get("/auth/user_status")
        self.assertTrue(response.json()["logged_in"])
        self.assertEqual(response.cookies["madar_access_token"], "local-session")
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertNotIn("test-password", response.text)
        sign_in.assert_called_once()

    def test_existing_session_does_not_sign_in_again(self):
        with patch.object(auth_routes, "user_status", return_value={"logged_in": True, "user": {"id": 7}}), patch.object(auth_routes, "login") as login:
            self.assertEqual(self.client.get("/auth/user_status").json()["user"], {"id": 7})
            login.assert_not_called()

    def test_cross_site_and_nonlocal_hosts_cannot_sign_in(self):
        with patch.object(auth_routes, "login") as login:
            for headers in ({"origin": "https://example.com"}, {"host": "example.com"}, {"sec-fetch-site": "cross-site"}):
                self.assertEqual(self.client.get("/auth/user_status", headers=headers).status_code, 403)
            login.assert_not_called()

    def test_normal_login_failure_is_not_bypassed(self):
        with patch.object(auth_routes, "user_status", return_value={"logged_in": False}), patch.object(auth_routes, "login", side_effect=HTTPException(401, "Invalid email or password")):
            self.assertEqual(self.client.get("/auth/user_status").status_code, 401)

    def test_production_or_hosted_database_is_rejected(self):
        for values in ({"APP_ENV": "production"}, {"SUPABASE_DB_URL": "postgresql://shared.example/postgres"}):
            with patch.dict(os.environ, values), self.assertRaisesRegex(RuntimeError, "isolated local"):
                LocalTestLoginMiddleware(FastAPI())
        with patch("database.SUPABASE_URL", "https://shared.example"), self.assertRaisesRegex(RuntimeError, "isolated local"):
            LocalTestLoginMiddleware(FastAPI())

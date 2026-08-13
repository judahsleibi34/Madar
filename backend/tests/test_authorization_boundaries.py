import unittest
from unittest.mock import patch

from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from services import auth_service


def build_client():
    app = FastAPI()

    @app.get("/users/{user_id}/probe")
    def user_probe(user_id: int, request: Request, response: Response):
        _auth_user, user_data = auth_service.require_regular_user_id(
            user_id,
            request,
            response,
        )
        return {"ok": True, "user_id": user_data["id"]}

    @app.get("/admin/probe")
    def admin_probe(request: Request, response: Response):
        _auth_user, user_data = auth_service.require_system_admin(request, response)
        return {"ok": True, "user_id": user_data["id"]}

    @app.get("/public/probe")
    def public_probe():
        return {"ok": True}

    return TestClient(app)


def fake_auth_result(user_data):
    return object(), user_data


class AuthorizationBoundaryTests(unittest.TestCase):
    def test_regular_user_cannot_access_another_user_id(self):
        client = build_client()

        with patch.object(
            auth_service,
            "get_authenticated_user_row",
            return_value=fake_auth_result({"id": 2, "tenant_id": 10, "user_type": "user"}),
        ):
            response = client.get("/users/3/probe")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "User id does not match session")

    def test_admin_cannot_access_user_workspace_route(self):
        client = build_client()

        with patch.object(
            auth_service,
            "get_authenticated_user_row",
            return_value=fake_auth_result({"id": 1, "user_type": "admin"}),
        ):
            response = client.get("/users/1/probe")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "User access is required")

    def test_regular_user_cannot_access_admin_route(self):
        client = build_client()

        with patch.object(
            auth_service,
            "get_authenticated_user_row",
            return_value=fake_auth_result({"id": 2, "tenant_id": 10, "user_type": "user"}),
        ):
            response = client.get("/admin/probe")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Admin access is required")

    def test_unauthenticated_user_cannot_access_user_workspace_route(self):
        client = build_client()

        response = client.get("/users/2/probe")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Not logged in")

    def test_site_only_customer_cannot_access_product_user_api(self):
        client = build_client()

        with patch.object(
            auth_service,
            "get_authenticated_user_row",
            return_value=fake_auth_result(
                {"id": 2, "tenant_id": None, "user_type": "site_user"}
            ),
        ):
            response = client.get("/users/2/probe")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "User access is required")

    def test_public_route_still_works_without_auth(self):
        client = build_client()

        response = client.get("/public/probe")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})


if __name__ == "__main__":
    unittest.main()

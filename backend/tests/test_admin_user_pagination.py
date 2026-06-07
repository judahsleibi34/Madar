import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes import admin_user_routes


def build_client():
    app = FastAPI()
    app.include_router(admin_user_routes.router)
    return TestClient(app)


class AdminUserPaginationTests(unittest.TestCase):
    def test_admin_users_accepts_limit_offset_pagination(self):
        client = build_client()
        result = {
            "items": [{"id": 2, "email": "user@example.com"}],
            "users": [{"id": 2, "email": "user@example.com"}],
            "pagination": {
                "limit": 20,
                "offset": 40,
                "count": 1,
                "has_more": False,
                "page": 3,
                "page_size": 20,
                "total_count": 41,
                "has_next_page": False,
                "has_previous_page": True,
            },
        }

        with patch.object(admin_user_routes, "require_system_admin"), \
             patch.object(admin_user_routes, "list_users_with_features", return_value=result) as list_users:
            response = client.get("/admin/users?limit=20&offset=40")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], result["items"])
        self.assertEqual(response.json()["pagination"]["offset"], 40)
        list_users.assert_called_once()
        self.assertEqual(list_users.call_args.kwargs["limit"], 20)
        self.assertEqual(list_users.call_args.kwargs["offset"], 40)

    def test_admin_users_rejects_invalid_pagination(self):
        client = build_client()

        with patch.object(admin_user_routes, "require_system_admin"):
            over_limit = client.get("/admin/users?limit=101")
            negative_offset = client.get("/admin/users?offset=-1")

        self.assertEqual(over_limit.status_code, 422)
        self.assertEqual(negative_offset.status_code, 422)


if __name__ == "__main__":
    unittest.main()

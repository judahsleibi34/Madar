import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
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

    def test_successful_user_type_update_records_audit(self):
        client = build_client()
        admin_user = {"id": 1, "user_type": "admin"}
        updated_user = {
            "id": 4,
            "tenant_id": 7,
            "email": "user@example.com",
            "user_type": "admin",
            "old_user_type": "user",
        }

        with patch.object(
            admin_user_routes,
            "require_system_admin",
            return_value=(object(), admin_user),
        ), patch.object(
            admin_user_routes,
            "update_user_type",
            return_value=updated_user,
        ) as update_user_type, patch.object(admin_user_routes, "record_audit_event") as record_audit:
            response = client.patch(
                "/admin/users/4/user-type",
                json={"user_type": "admin", "token": "ignored"},
            )

        self.assertEqual(response.status_code, 200)
        update_user_type.assert_called_once_with(user_id=4, user_type="admin")
        record_audit.assert_called_once()
        audit_kwargs = record_audit.call_args.kwargs
        self.assertEqual(audit_kwargs["tenant_id"], 7)
        self.assertEqual(audit_kwargs["actor_user_id"], 1)
        self.assertEqual(audit_kwargs["action"], "admin.user_type_updated")
        self.assertEqual(audit_kwargs["target_type"], "user")
        self.assertEqual(audit_kwargs["target_id"], 4)
        self.assertEqual(
            audit_kwargs["metadata"],
            {
                "new_user_type": "admin",
                "affected_user_id": 4,
                "source": "admin",
                "old_user_type": "user",
                "affected_user_email": "user@example.com",
            },
        )
        self.assertNotIn("token", str(audit_kwargs["metadata"]).lower())
        self.assertNotIn("cookie", str(audit_kwargs["metadata"]).lower())
        self.assertNotIn("raw_body", str(audit_kwargs["metadata"]).lower())

    def test_unauthorized_user_type_update_does_not_record_audit(self):
        client = build_client()

        with patch.object(
            admin_user_routes,
            "require_system_admin",
            side_effect=HTTPException(status_code=403, detail="Admin access required"),
        ), patch.object(admin_user_routes, "record_audit_event") as record_audit:
            response = client.patch("/admin/users/4/user-type", json={"user_type": "admin"})

        self.assertEqual(response.status_code, 403)
        record_audit.assert_not_called()

    def test_failed_user_type_update_does_not_record_audit(self):
        client = build_client()

        with patch.object(
            admin_user_routes,
            "require_system_admin",
            return_value=(object(), {"id": 1, "user_type": "admin"}),
        ), patch.object(
            admin_user_routes,
            "update_user_type",
            side_effect=HTTPException(status_code=400, detail="Invalid user type."),
        ), patch.object(admin_user_routes, "record_audit_event") as record_audit:
            response = client.patch("/admin/users/4/user-type", json={"user_type": "user"})

        self.assertEqual(response.status_code, 400)
        record_audit.assert_not_called()

    def test_successful_user_delete_records_audit(self):
        client = build_client()
        admin_user = {"id": 1, "user_type": "admin"}
        deleted_user = {
            "id": 4,
            "tenant_id": 7,
            "email": "user@example.com",
            "user_type": "user",
            "auth_id": "auth-secret",
            "tenant_deleted": False,
        }

        with patch.object(
            admin_user_routes,
            "require_system_admin",
            return_value=(object(), admin_user),
        ), patch.object(
            admin_user_routes,
            "delete_user_account",
            return_value=deleted_user,
        ) as delete_user_account, patch.object(admin_user_routes, "record_audit_event") as record_audit:
            response = client.delete("/admin/users/4")

        self.assertEqual(response.status_code, 200)
        delete_user_account.assert_called_once_with(user_id=4, requesting_user_id=1)
        record_audit.assert_called_once()
        audit_kwargs = record_audit.call_args.kwargs
        self.assertEqual(audit_kwargs["tenant_id"], 7)
        self.assertEqual(audit_kwargs["actor_user_id"], 1)
        self.assertEqual(audit_kwargs["action"], "admin.user_deleted")
        self.assertEqual(audit_kwargs["target_type"], "user")
        self.assertEqual(audit_kwargs["target_id"], 4)
        self.assertEqual(
            audit_kwargs["metadata"],
            {
                "deleted_user_id": 4,
                "source": "admin",
                "deleted_user_email": "user@example.com",
                "deleted_user_type": "user",
            },
        )
        self.assertNotIn("auth-secret", str(audit_kwargs["metadata"]))
        self.assertNotIn("auth_id", str(audit_kwargs["metadata"]).lower())
        self.assertNotIn("token", str(audit_kwargs["metadata"]).lower())
        self.assertNotIn("cookie", str(audit_kwargs["metadata"]).lower())
        self.assertNotIn("raw_body", str(audit_kwargs["metadata"]).lower())

    def test_unauthorized_user_delete_does_not_record_audit(self):
        client = build_client()

        with patch.object(
            admin_user_routes,
            "require_system_admin",
            side_effect=HTTPException(status_code=403, detail="Admin access required"),
        ), patch.object(admin_user_routes, "record_audit_event") as record_audit:
            response = client.delete("/admin/users/4")

        self.assertEqual(response.status_code, 403)
        record_audit.assert_not_called()

    def test_not_found_user_delete_does_not_record_audit(self):
        client = build_client()

        with patch.object(
            admin_user_routes,
            "require_system_admin",
            return_value=(object(), {"id": 1, "user_type": "admin"}),
        ), patch.object(
            admin_user_routes,
            "delete_user_account",
            side_effect=HTTPException(status_code=404, detail="User was not found."),
        ), patch.object(admin_user_routes, "record_audit_event") as record_audit:
            response = client.delete("/admin/users/4")

        self.assertEqual(response.status_code, 404)
        record_audit.assert_not_called()


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from services import tenant_service


def tenant_context(*, user_id=7, tenant_id=11):
    return tenant_service.TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        auth_id=f"auth-{user_id}",
        role="member",
        membership_status="active",
        user={"id": user_id, "tenant_id": tenant_id, "user_type": "user"},
        membership={"role": "member", "status": "active"},
    )


class TenantUserAuthorizationTests(unittest.TestCase):
    def test_matching_path_user_receives_active_tenant_context(self):
        expected = tenant_context()
        with patch.object(
            tenant_service,
            "require_active_tenant_member",
            return_value=expected,
        ):
            result = tenant_service.require_active_tenant_user_id(
                7,
                object(),
            )

        self.assertIs(result, expected)

    def test_cross_user_path_is_rejected_after_membership_check(self):
        with patch.object(
            tenant_service,
            "require_active_tenant_member",
            return_value=tenant_context(user_id=7),
        ):
            with self.assertRaises(HTTPException) as raised:
                tenant_service.require_active_tenant_user_id(8, object())

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, "User id does not match session")

    def test_inactive_membership_rejection_is_preserved(self):
        denied = HTTPException(
            status_code=403,
            detail="Active tenant membership required",
        )
        with patch.object(
            tenant_service,
            "require_active_tenant_member",
            side_effect=denied,
        ):
            with self.assertRaises(HTTPException) as raised:
                tenant_service.require_active_tenant_user_id(7, object())

        self.assertIs(raised.exception, denied)


if __name__ == "__main__":
    unittest.main()

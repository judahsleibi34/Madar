import unittest
from unittest.mock import patch

from services.email_service import send_permission_code_email


class EmailServiceTests(unittest.TestCase):
    def test_missing_smtp_in_production_never_logs_permission_code_even_if_enabled(self):
        with patch.dict(
            "os.environ",
            {
                "APP_ENV": "production",
                "SMTP_HOST": "",
                "ADMIN_ACCOUNT_ACCESS_ALLOW_DEV_EMAIL_LOG": "true",
            },
            clear=False,
        ), patch("services.email_service.logger.warning") as warning:
            with self.assertRaises(RuntimeError):
                send_permission_code_email(
                    recipient_email="user@example.com",
                    code="A2b!x9",
                    expires_minutes=10,
                )

        warning.assert_not_called()

    def test_missing_smtp_in_local_development_can_log_permission_code(self):
        with patch.dict(
            "os.environ",
            {
                "APP_ENV": "development",
                "SMTP_HOST": "",
                "ADMIN_ACCOUNT_ACCESS_ALLOW_DEV_EMAIL_LOG": "true",
            },
            clear=False,
        ), patch("services.email_service.logger.warning") as warning:
            delivery = send_permission_code_email(
                recipient_email="user@example.com",
                code="A2b!x9",
                expires_minutes=10,
            )

        self.assertEqual(delivery, "development_log")
        warning.assert_called_once()
        self.assertEqual(
            warning.call_args.kwargs["extra"]["development_permission_code"],
            "A2b!x9",
        )

    def test_missing_smtp_in_staging_never_logs_permission_code(self):
        with patch.dict(
            "os.environ",
            {
                "APP_ENV": "staging",
                "SMTP_HOST": "",
                "ADMIN_ACCOUNT_ACCESS_ALLOW_DEV_EMAIL_LOG": "true",
            },
            clear=False,
        ), patch("services.email_service.logger.warning") as warning:
            with self.assertRaises(RuntimeError):
                send_permission_code_email(
                    recipient_email="user@example.com",
                    code="A2b!x9",
                    expires_minutes=10,
                )

        warning.assert_not_called()


if __name__ == "__main__":
    unittest.main()

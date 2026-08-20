from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _app_env() -> str:
    return (
        os.getenv("APP_ENV")
        or os.getenv("ENV")
        or os.getenv("FASTAPI_ENV")
        or "development"
    ).strip().lower()


def _is_local_development_env() -> bool:
    return _app_env() in {"dev", "development", "local", "test", "testing"}


def send_permission_code_email(*, recipient_email: str, code: str, expires_minutes: int) -> str:
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM_EMAIL", smtp_username or "no-reply@madar.local").strip()
    smtp_tls = _env_bool("SMTP_USE_TLS", True)

    if not smtp_host:
        allow_dev_delivery = _is_local_development_env() and _env_bool(
            "ADMIN_ACCOUNT_ACCESS_ALLOW_DEV_EMAIL_LOG",
            True,
        )

        if allow_dev_delivery:
            logger.warning(
                "admin.account_access.email_dev_delivery",
                extra={
                    "recipient_email": recipient_email,
                    "expires_minutes": expires_minutes,
                    "development_permission_code": code,
                },
            )
            return "development_log"

        raise RuntimeError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = "Your Madar permission code"
    message["From"] = smtp_from
    message["To"] = recipient_email
    message.set_content(
        "\n".join(
            [
                "A Madar administrator requested temporary access to your account.",
                "",
                f"Your permission code is: {code}",
                f"This code expires in {expires_minutes} minutes and can be used once.",
                "",
                "Share this code only if you approve the access request.",
            ]
        )
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
        if smtp_tls:
            smtp.starttls()

        if smtp_username:
            smtp.login(smtp_username, smtp_password)

        smtp.send_message(message)

    return "smtp"

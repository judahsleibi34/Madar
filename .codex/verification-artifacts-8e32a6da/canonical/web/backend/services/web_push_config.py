"""Canonical, redaction-safe Web Push runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _administratively_enabled() -> bool:
    raw = os.getenv("WEB_PUSH_ENABLED")
    if raw is None:
        return False
    normalized = raw.strip().lower()
    if normalized not in _TRUE_VALUES | _FALSE_VALUES:
        raise RuntimeError("configuration value is invalid: WEB_PUSH_ENABLED")
    return normalized in _TRUE_VALUES


@dataclass(frozen=True)
class WebPushConfiguration:
    administratively_enabled: bool
    public_key: str
    private_key: str
    subject: str

    @property
    def missing_fields(self) -> tuple[str, ...]:
        values = {
            "WEB_PUSH_VAPID_PUBLIC_KEY": self.public_key,
            "WEB_PUSH_VAPID_PRIVATE_KEY": self.private_key,
            "WEB_PUSH_VAPID_SUBJECT": self.subject,
        }
        return tuple(name for name, value in values.items() if not value)

    @property
    def configured(self) -> bool:
        return not self.missing_fields

    @property
    def operational(self) -> bool:
        return self.administratively_enabled and self.configured

    @property
    def status(self) -> str:
        if not self.administratively_enabled:
            return "disabled"
        return "configured" if self.configured else "misconfigured"

    def public_config(self) -> dict[str, str | bool]:
        return {
            "enabled": self.operational,
            "status": self.status,
            "public_key": self.public_key if self.operational else "",
        }


def get_web_push_configuration() -> WebPushConfiguration:
    """Load the single Web Push operator/configuration contract.

    Secret values stay inside the returned object and must never be serialized
    or logged. The deprecated ``VAPID_PRIVATE_KEY`` is deliberately ignored.
    """

    return WebPushConfiguration(
        administratively_enabled=_administratively_enabled(),
        public_key=os.getenv("WEB_PUSH_VAPID_PUBLIC_KEY", "").strip(),
        private_key=os.getenv("WEB_PUSH_VAPID_PRIVATE_KEY", "").strip(),
        subject=os.getenv("WEB_PUSH_VAPID_SUBJECT", "").strip(),
    )

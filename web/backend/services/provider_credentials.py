"""Credential boundary for API providers (C2).

When candidate schema 155 and the separately operated Transit service are available,
production resolution uses the tenant/project/source-scoped encrypted credential
vault. Before that candidate is selected, resolution fails closed without changing
the legacy upload path.

``TestCredentialStore`` exists only when ``APP_ENV`` is exactly ``test``: in-memory,
  keyed by (tenant, project, source, provider), with rotation and revocation, so the
  transport, authorization and failure paths can be verified end to end.

Credentials are resolved server side only, after the source has been authorized for
the caller's tenant, and are carried as ``SecretValue`` (never rendered, logged or
serialized).
"""

from __future__ import annotations

import os
import threading
import uuid
from dataclasses import dataclass

from services.provider_http_transport import SecretValue


class CredentialError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AuthorizedSource:
    """Built only from a data source row already fetched under tenant scope."""

    tenant_id: int
    project_id: str
    source_id: str
    provider_key: str
    user_id: int | None = None


@dataclass
class CredentialLease:
    secret: SecretValue | None
    credential_id: str | None
    credential_version: int | None
    source_revision: int | None
    _validate: object = lambda: None

    def validate(self) -> None:
        self._validate()

    def reference_metadata(self) -> dict[str, object] | None:
        if self.credential_id is None:
            return None
        return {
            "credential_id": self.credential_id,
            "credential_version": self.credential_version,
            "source_revision": self.source_revision,
        }


class TestCredentialStore:
    """In-memory credentials for the local fixture. Refuses to exist outside tests."""

    def __init__(self):
        if os.environ.get("APP_ENV") != "test":
            raise CredentialError("provider_credentials_unavailable")
        self._lock = threading.Lock()
        self._secrets: dict[tuple, tuple[int, str, SecretValue | None]] = {}

    @staticmethod
    def _key(source: AuthorizedSource) -> tuple:
        return (int(source.tenant_id), str(source.project_id), str(source.source_id),
                source.provider_key)

    def put(self, source: AuthorizedSource, secret: str) -> int:
        with self._lock:
            version = self._secrets.get(self._key(source), (0, "", None))[0] + 1
            self._secrets[self._key(source)] = (
                version, str(uuid.uuid4()), SecretValue(secret),
            )
            return version

    rotate = put

    def revoke(self, source: AuthorizedSource) -> None:
        with self._lock:
            version = self._secrets.get(self._key(source), (0, "", None))[0] + 1
            self._secrets[self._key(source)] = (version, str(uuid.uuid4()), None)

    def resolve(self, source: AuthorizedSource) -> CredentialLease:
        with self._lock:
            entry = self._secrets.get(self._key(source))
        if entry is None:
            raise CredentialError("provider_credentials_unavailable")
        if entry[2] is None:
            raise CredentialError("provider_credentials_revoked")
        version, credential_id, secret = entry

        def validate() -> None:
            with self._lock:
                current = self._secrets.get(self._key(source))
            if current is None or current[2] is None or current[:2] != (version, credential_id):
                raise CredentialError("provider_credentials_revoked")

        return CredentialLease(secret, credential_id, version, version, validate)


_TEST_STORE: TestCredentialStore | None = None
_TEST_STORE_LOCK = threading.Lock()


def test_credential_store() -> TestCredentialStore:
    global _TEST_STORE
    with _TEST_STORE_LOCK:
        if _TEST_STORE is None:
            _TEST_STORE = TestCredentialStore()
        return _TEST_STORE


def resolve_credential(source: AuthorizedSource, *, auth: str) -> CredentialLease:
    if not isinstance(source, AuthorizedSource):
        raise CredentialError("provider_credentials_unavailable")
    if auth == "none":
        return CredentialLease(None, None, None, None)
    if os.environ.get("APP_ENV") == "test" and not os.getenv("DATA_SOURCE_VAULT_ADDR", "").strip():
        return test_credential_store().resolve(source)
    if source.user_id is None:
        raise CredentialError("provider_credentials_unavailable")
    try:
        from services.data_source_credential_service import (
            DataSourceCredentialError,
            resolve_persistent_credential,
        )
        resolved = resolve_persistent_credential(
            tenant_id=source.tenant_id, project_id=source.project_id,
            source_id=source.source_id, user_id=source.user_id,
            provider_key=source.provider_key, credential_type=auth,
        )
        return CredentialLease(
            resolved.secret, resolved.reference.credential_id,
            resolved.reference.credential_version, resolved.reference.source_revision,
            resolved.validate,
        )
    except DataSourceCredentialError as error:
        raise CredentialError(error.code) from error

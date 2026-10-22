"""Persistent tenant/source credential lifecycle backed by Vault Transit."""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
from dataclasses import dataclass
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException

from database import service_supabase
from services.provider_http_transport import SecretValue
from services.vault_transit import VaultTransitClient, VaultTransitConfig, VaultTransitError


CREDENTIAL_VAULT_SCHEMA = 155
AAD_VERSION = 1
_TYPE = re.compile(r"^[a-z][a-z0-9_]{1,79}$")


class DataSourceCredentialError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class CredentialScope:
    environment: str
    tenant_id: int
    project_id: str
    source_id: str
    provider_key: str
    credential_type: str
    credential_id: str
    credential_version: int


@dataclass(frozen=True)
class CredentialReference:
    credential_id: str
    credential_version: int
    source_revision: int

    def as_metadata(self) -> dict[str, object]:
        return {
            "credential_id": self.credential_id,
            "credential_version": self.credential_version,
            "source_revision": self.source_revision,
        }


@dataclass
class ResolvedCredential:
    secret: SecretValue
    reference: CredentialReference
    revalidator: object

    def validate(self) -> None:
        self.revalidator()


def _rows(response) -> list[dict]:
    return list(getattr(response, "data", None) or [])


def _rpc(database, name: str, params: dict, *, code: str = "provider_credentials_unavailable"):
    try:
        return database.rpc(name, params).execute()
    except DataSourceCredentialError:
        raise
    except Exception as error:
        raise DataSourceCredentialError(code) from error


def _uuid(value: object) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as error:
        raise DataSourceCredentialError("provider_credentials_scope_invalid") from error


def _environment_binding() -> str:
    value = (os.getenv("DATA_SOURCE_CREDENTIAL_ENVIRONMENT") or os.getenv("APP_ENV") or "development").strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", value):
        raise DataSourceCredentialError("provider_credentials_configuration_invalid")
    return value


def canonical_context(scope: CredentialScope) -> bytes:
    body = {
        "credential_id": _uuid(scope.credential_id),
        "credential_type": scope.credential_type,
        "credential_version": int(scope.credential_version),
        "environment": scope.environment,
        "project_id": _uuid(scope.project_id),
        "provider_key": scope.provider_key,
        "source_id": _uuid(scope.source_id),
        "tenant_id": int(scope.tenant_id),
        "version": AAD_VERSION,
    }
    if not _TYPE.fullmatch(scope.provider_key) or not _TYPE.fullmatch(scope.credential_type):
        raise DataSourceCredentialError("provider_credentials_scope_invalid")
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _vault(client=None) -> VaultTransitClient:
    return client or VaultTransitClient(VaultTransitConfig.from_environment())


def _translate_vault(error: VaultTransitError) -> DataSourceCredentialError:
    mapping = {
        "vault_authentication_failed": "provider_credentials_key_service_unauthorized",
        "vault_key_unavailable": "provider_credentials_key_unavailable",
        "vault_decryption_failed": "provider_credentials_invalid",
        "vault_wrapped_key_invalid": "provider_credentials_invalid",
    }
    return DataSourceCredentialError(mapping.get(error.code, "provider_credentials_key_service_unavailable"))


def _schema_version(*, client=None) -> int:
    try:
        rows = _rows((client or service_supabase).table("application_schema_state").select(
            "schema_version"
        ).eq("contract_key", "core").limit(1).execute())
    except Exception as error:
        raise DataSourceCredentialError("provider_credentials_unavailable") from error
    try:
        return int(rows[0]["schema_version"]) if rows else 0
    except (KeyError, TypeError, ValueError):
        return 0


def credential_vault_available(*, client=None) -> bool:
    return _schema_version(client=client) >= CREDENTIAL_VAULT_SCHEMA


def _scope_from_row(row: dict) -> CredentialScope:
    return CredentialScope(
        environment=str(row.get("environment_binding") or ""),
        tenant_id=int(row["tenant_id"]),
        project_id=str(row["project_id"]),
        source_id=str(row["source_id"]),
        provider_key=str(row["provider_key"]),
        credential_type=str(row["credential_type"]),
        credential_id=str(row["credential_id"]),
        credential_version=int(row["credential_version"]),
    )


def provision_credential(
    *, tenant_id: int, project_id: str, source_id: str, user_id: int,
    provider_key: str, credential_type: str, secret: str,
    expires_at: str | None = None, client=None, vault_client=None,
) -> dict:
    database = client or service_supabase
    try:
        SecretValue(secret)
    except ValueError as error:
        raise DataSourceCredentialError("provider_credentials_invalid") from error
    if not credential_vault_available(client=database):
        raise HTTPException(status_code=503, detail={"code": "credential_vault_upgrade_required"})
    prepared = _rows(_rpc(database, "prepare_data_source_credential155", {
        "p_tenant_id": int(tenant_id), "p_project_id": _uuid(project_id),
        "p_source_id": _uuid(source_id), "p_actor_user_id": int(user_id),
        "p_provider_key": provider_key, "p_credential_type": credential_type,
    }))
    if not prepared:
        raise DataSourceCredentialError("provider_credentials_not_authorized")
    item = prepared[0]
    scope = CredentialScope(
        _environment_binding(), int(tenant_id), _uuid(project_id), _uuid(source_id),
        provider_key, credential_type, _uuid(item["credential_id"]),
        int(item["credential_version"]),
    )
    context = canonical_context(scope)
    nonce = secrets.token_bytes(12)
    vault = _vault(vault_client)
    key = None
    try:
        key, wrapped, key_version = vault.generate_data_key(context=context)
        ciphertext = AESGCM(bytes(key)).encrypt(nonce, secret.encode("utf-8"), context)
    except VaultTransitError as error:
        raise _translate_vault(error) from error
    finally:
        if key is not None:
            for index in range(len(key)):
                key[index] = 0
        if vault_client is None:
            vault.close()
    activated = _rows(_rpc(database, "activate_data_source_credential155", {
        "p_tenant_id": int(tenant_id), "p_project_id": _uuid(project_id),
        "p_source_id": _uuid(source_id), "p_actor_user_id": int(user_id),
        "p_provider_key": provider_key, "p_credential_type": credential_type,
        "p_credential_id": scope.credential_id,
        "p_credential_version": scope.credential_version,
        "p_expected_source_revision": int(item["source_revision"]),
        "p_environment_binding": scope.environment,
        "p_ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "p_nonce": base64.b64encode(nonce).decode("ascii"),
        "p_wrapped_data_key": wrapped, "p_key_name": vault.config.key_name,
        "p_key_version": key_version, "p_aad_version": AAD_VERSION,
        "p_expires_at": expires_at,
    }, code="provider_credentials_write_conflict"))
    if not activated:
        raise DataSourceCredentialError("provider_credentials_write_conflict")
    return activated[0]


def resolve_persistent_credential(
    *, tenant_id: int, project_id: str, source_id: str, user_id: int,
    provider_key: str, credential_type: str = "bearer", client=None,
    vault_client=None,
) -> ResolvedCredential:
    database = client or service_supabase
    rows = _rows(_rpc(database, "resolve_data_source_credential155", {
        "p_tenant_id": int(tenant_id), "p_project_id": _uuid(project_id),
        "p_source_id": _uuid(source_id), "p_actor_user_id": int(user_id),
        "p_provider_key": provider_key, "p_credential_type": credential_type,
    }))
    if not rows:
        raise DataSourceCredentialError("provider_credentials_unavailable")
    row = rows[0]
    scope = _scope_from_row(row)
    if scope.environment != _environment_binding() or int(row.get("aad_version") or 0) != AAD_VERSION:
        raise DataSourceCredentialError("provider_credentials_invalid")
    context = canonical_context(scope)
    try:
        nonce = base64.b64decode(str(row["nonce"]), validate=True)
        ciphertext = base64.b64decode(str(row["ciphertext"]), validate=True)
    except (ValueError, TypeError, KeyError) as error:
        raise DataSourceCredentialError("provider_credentials_invalid") from error
    if len(nonce) != 12:
        raise DataSourceCredentialError("provider_credentials_invalid")
    vault = _vault(vault_client)
    key = None
    try:
        if str(row.get("key_name")) != vault.config.key_name:
            raise DataSourceCredentialError("provider_credentials_key_unavailable")
        if vault.key_version(str(row.get("wrapped_data_key"))) != int(row.get("key_version") or 0):
            raise DataSourceCredentialError("provider_credentials_invalid")
        key = vault.unwrap_data_key(str(row["wrapped_data_key"]), context=context)
        plaintext = AESGCM(bytes(key)).decrypt(nonce, ciphertext, context).decode("utf-8")
    except VaultTransitError as error:
        raise _translate_vault(error) from error
    except (InvalidTag, UnicodeError, ValueError) as error:
        raise DataSourceCredentialError("provider_credentials_invalid") from error
    finally:
        if key is not None:
            for index in range(len(key)):
                key[index] = 0
        if vault_client is None:
            vault.close()
    reference = CredentialReference(
        scope.credential_id, scope.credential_version, int(row["source_revision"]),
    )

    def revalidate() -> None:
        try:
            valid = database.rpc("assert_data_source_credential155", {
                "p_tenant_id": int(tenant_id), "p_project_id": _uuid(project_id),
                "p_source_id": _uuid(source_id), "p_actor_user_id": int(user_id),
                "p_provider_key": provider_key, "p_credential_id": reference.credential_id,
                "p_credential_version": reference.credential_version,
                "p_source_revision": reference.source_revision,
            }).execute()
        except Exception as error:
            raise DataSourceCredentialError("provider_credentials_unavailable") from error
        if getattr(valid, "data", None) is not True:
            raise DataSourceCredentialError("provider_credentials_revoked")

    revalidate()
    marked = _rpc(database, "mark_data_source_credential_used155", {
        "p_tenant_id": int(tenant_id), "p_project_id": _uuid(project_id),
        "p_source_id": _uuid(source_id), "p_actor_user_id": int(user_id),
        "p_provider_key": provider_key, "p_credential_id": reference.credential_id,
        "p_credential_version": reference.credential_version,
        "p_source_revision": reference.source_revision,
    })
    if getattr(marked, "data", None) is not True:
        raise DataSourceCredentialError("provider_credentials_revoked")
    return ResolvedCredential(SecretValue(plaintext), reference, revalidate)


def revoke_credential(
    *, tenant_id: int, project_id: str, source_id: str, user_id: int,
    provider_key: str, expected_revision: int, client=None,
) -> dict:
    database = client or service_supabase
    rows = _rows(_rpc(database, "revoke_data_source_credential155", {
        "p_tenant_id": int(tenant_id), "p_project_id": _uuid(project_id),
        "p_source_id": _uuid(source_id), "p_actor_user_id": int(user_id),
        "p_provider_key": provider_key,
        "p_expected_source_revision": int(expected_revision),
    }, code="provider_credentials_write_conflict"))
    if not rows:
        raise DataSourceCredentialError("provider_credentials_write_conflict")
    return rows[0]


def rewrap_credential(
    *, tenant_id: int, project_id: str, source_id: str, user_id: int,
    provider_key: str, credential_id: str, client=None, vault_client=None,
) -> dict:
    """Rewrap one immutable credential DEK without decrypting its payload."""
    database = client or service_supabase
    rows = _rows(_rpc(database, "prepare_data_source_credential_rewrap155", {
        "p_tenant_id": int(tenant_id), "p_project_id": _uuid(project_id),
        "p_source_id": _uuid(source_id), "p_actor_user_id": int(user_id),
        "p_provider_key": provider_key, "p_credential_id": _uuid(credential_id),
    }))
    if not rows:
        raise DataSourceCredentialError("provider_credentials_not_authorized")
    row = rows[0]
    scope = _scope_from_row(row)
    if scope.environment != _environment_binding() or int(row.get("aad_version") or 0) != AAD_VERSION:
        raise DataSourceCredentialError("provider_credentials_invalid")
    vault = _vault(vault_client)
    try:
        if str(row.get("key_name")) != vault.config.key_name:
            raise DataSourceCredentialError("provider_credentials_key_unavailable")
        old_wrapped = str(row["wrapped_data_key"])
        old_key_version = int(row["key_version"])
        if vault.key_version(old_wrapped) != old_key_version:
            raise DataSourceCredentialError("provider_credentials_invalid")
        wrapped, key_version = vault.rewrap_data_key(
            old_wrapped, context=canonical_context(scope),
        )
    except VaultTransitError as error:
        raise _translate_vault(error) from error
    finally:
        if vault_client is None:
            vault.close()
    updated = _rows(_rpc(database, "complete_data_source_credential_rewrap155", {
        "p_tenant_id": int(tenant_id), "p_project_id": _uuid(project_id),
        "p_source_id": _uuid(source_id), "p_actor_user_id": int(user_id),
        "p_provider_key": provider_key, "p_credential_id": scope.credential_id,
        "p_expected_wrapped_data_key": old_wrapped,
        "p_expected_key_version": old_key_version,
        "p_wrapped_data_key": wrapped, "p_key_version": key_version,
    }, code="provider_credentials_write_conflict"))
    if not updated:
        raise DataSourceCredentialError("provider_credentials_write_conflict")
    return updated[0]


def list_credential_metadata(
    *, tenant_id: int, project_id: str, source_id: str, user_id: int,
    provider_key: str, client=None,
) -> list[dict]:
    database = client or service_supabase
    return _rows(_rpc(database, "list_data_source_credentials155", {
        "p_tenant_id": int(tenant_id), "p_project_id": _uuid(project_id),
        "p_source_id": _uuid(source_id), "p_actor_user_id": int(user_id),
        "p_provider_key": provider_key,
    }))

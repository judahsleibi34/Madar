import base64
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.data_source_credential_service import (
    DataSourceCredentialError,
    canonical_context,
    CredentialScope,
    provision_credential,
    rewrap_credential,
    resolve_persistent_credential,
)
from services.vault_transit import (
    VaultTransitClient,
    VaultTransitConfig,
    VaultTransitError,
)


PROJECT = "11111111-1111-4111-8111-111111111111"
SOURCE = "33333333-3333-4333-8333-333333333333"
CREDENTIAL = "55555555-5555-4555-8555-555555555555"


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args): return self
    def eq(self, *_args): return self
    def limit(self, *_args): return self
    def execute(self): return Result(self.rows)


class FakeDatabase:
    def __init__(self):
        self.activated = None
        self.calls = []
        self.allow = True

    def table(self, name):
        assert name == "application_schema_state"
        return Query([{"schema_version": 155}])

    def rpc(self, name, params):
        self.calls.append((name, dict(params)))
        database = self

        class Rpc:
            def execute(self):
                if name == "prepare_data_source_credential155":
                    return Result([{
                        "credential_id": CREDENTIAL,
                        "credential_version": 1,
                        "source_revision": 0,
                    }])
                if name == "activate_data_source_credential155":
                    database.activated = dict(params)
                    return Result([{
                        "credential_id": CREDENTIAL,
                        "credential_version": 1,
                        "source_revision": 1,
                        "status": "active",
                        "expires_at": None,
                        "key_name": "madar-data-sources",
                        "key_version": 1,
                        "created_at": "2026-01-01T00:00:00Z",
                    }])
                if name == "resolve_data_source_credential155":
                    if not database.allow or database.activated is None:
                        return Result([])
                    value = database.activated
                    return Result([{
                        "credential_id": CREDENTIAL,
                        "tenant_id": 1,
                        "project_id": PROJECT,
                        "source_id": SOURCE,
                        "provider_key": "http_fixture",
                        "credential_type": "bearer",
                        "credential_version": 1,
                        "source_revision": 1,
                        "environment_binding": value["p_environment_binding"],
                        "ciphertext": value["p_ciphertext"],
                        "nonce": value["p_nonce"],
                        "wrapped_data_key": value["p_wrapped_data_key"],
                        "key_name": value["p_key_name"],
                        "key_version": value["p_key_version"],
                        "aad_version": value["p_aad_version"],
                        "expires_at": None,
                    }])
                if name == "prepare_data_source_credential_rewrap155":
                    value = database.activated
                    return Result([{
                        "credential_id": CREDENTIAL,
                        "tenant_id": 1,
                        "project_id": PROJECT,
                        "source_id": SOURCE,
                        "provider_key": "http_fixture",
                        "credential_type": "bearer",
                        "credential_version": 1,
                        "source_revision": 1,
                        "environment_binding": value["p_environment_binding"],
                        "wrapped_data_key": value["p_wrapped_data_key"],
                        "key_name": value["p_key_name"],
                        "key_version": value["p_key_version"],
                        "aad_version": value["p_aad_version"],
                    }])
                if name == "complete_data_source_credential_rewrap155":
                    if params["p_expected_wrapped_data_key"] != database.activated["p_wrapped_data_key"]:
                        return Result([])
                    database.activated["p_wrapped_data_key"] = params["p_wrapped_data_key"]
                    database.activated["p_key_version"] = params["p_key_version"]
                    return Result([{
                        "credential_id": CREDENTIAL,
                        "credential_version": 1,
                        "status": "active",
                        "key_name": "madar-data-sources",
                        "key_version": params["p_key_version"],
                        "rewrapped_at": "2026-01-01T00:00:00Z",
                    }])
                if name in {
                    "assert_data_source_credential155",
                    "mark_data_source_credential_used155",
                }:
                    return Result(database.allow)
                raise AssertionError(name)
        return Rpc()


class FakeVault:
    def __init__(self):
        self.config = SimpleNamespace(key_name="madar-data-sources")
        self.key = b"k" * 32
        self.available = True

    def generate_data_key(self, *, context):
        if not self.available:
            raise VaultTransitError("vault_unavailable")
        return bytearray(self.key), "vault:v1:" + base64.b64encode(b"wrapped").decode(), 1

    def unwrap_data_key(self, wrapped_key, *, context):
        if not self.available:
            raise VaultTransitError("vault_unavailable")
        return bytearray(self.key)

    def rewrap_data_key(self, wrapped_key, *, context):
        if not self.available:
            raise VaultTransitError("vault_unavailable")
        return "vault:v2:" + base64.b64encode(b"rewrapped").decode(), 2

    @staticmethod
    def key_version(wrapped): return int(wrapped.split(":", 2)[1][1:])


class CredentialEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.database = FakeDatabase()
        self.vault = FakeVault()
        self.environment = patch.dict(os.environ, {
            "APP_ENV": "test",
            "DATA_SOURCE_CREDENTIAL_ENVIRONMENT": "test",
        }, clear=False)
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    def provision(self, secret="synthetic-token-not-real"):
        return provision_credential(
            tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
            provider_key="http_fixture", credential_type="bearer", secret=secret,
            client=self.database, vault_client=self.vault,
        )

    def test_encrypts_persists_metadata_and_resolves_without_returning_ciphertext(self):
        result = self.provision()
        self.assertNotIn("ciphertext", result)
        self.assertNotIn("wrapped_data_key", result)
        self.assertNotIn("synthetic-token-not-real", repr(self.database.activated))
        resolved = resolve_persistent_credential(
            tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
            provider_key="http_fixture", client=self.database,
            vault_client=self.vault,
        )
        self.assertEqual(resolved.secret.reveal_for_request(), "synthetic-token-not-real")
        self.assertNotIn("synthetic-token-not-real", repr(resolved.secret))
        self.assertEqual(resolved.reference.source_revision, 1)
        self.assertIn("mark_data_source_credential_used155", [call[0] for call in self.database.calls])

    def test_ciphertext_and_authenticated_context_tampering_fail_closed(self):
        self.provision()
        original = self.database.activated["p_ciphertext"]
        tampered = bytearray(base64.b64decode(original))
        tampered[-1] ^= 1
        self.database.activated["p_ciphertext"] = base64.b64encode(tampered).decode()
        with self.assertRaises(DataSourceCredentialError) as caught:
            resolve_persistent_credential(
                tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
                provider_key="http_fixture", client=self.database,
                vault_client=self.vault,
            )
        self.assertEqual(caught.exception.code, "provider_credentials_invalid")

        self.database.activated["p_ciphertext"] = original
        self.database.activated["p_environment_binding"] = "other"
        with patch.dict(os.environ, {"DATA_SOURCE_CREDENTIAL_ENVIRONMENT": "other"}, clear=False):
            with self.assertRaises(DataSourceCredentialError):
                resolve_persistent_credential(
                    tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
                    provider_key="http_fixture", client=self.database,
                    vault_client=self.vault,
                )

    def test_revocation_and_vault_unavailability_fail_closed(self):
        self.provision()
        resolved = resolve_persistent_credential(
            tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
            provider_key="http_fixture", client=self.database,
            vault_client=self.vault,
        )
        self.database.allow = False
        with self.assertRaises(DataSourceCredentialError) as revoked:
            resolved.validate()
        self.assertEqual(revoked.exception.code, "provider_credentials_revoked")
        self.database.allow = True
        self.vault.available = False
        with self.assertRaises(DataSourceCredentialError) as unavailable:
            resolve_persistent_credential(
                tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
                provider_key="http_fixture", client=self.database,
                vault_client=self.vault,
            )
        self.assertEqual(unavailable.exception.code, "provider_credentials_key_service_unavailable")

    def test_canonical_context_binds_every_scope_dimension(self):
        scope = CredentialScope("test", 1, PROJECT, SOURCE, "http_fixture", "bearer", CREDENTIAL, 1)
        baseline = canonical_context(scope)
        changed = CredentialScope("test", 2, PROJECT, SOURCE, "http_fixture", "bearer", CREDENTIAL, 1)
        self.assertNotEqual(baseline, canonical_context(changed))

    def test_rewrap_changes_only_wrapped_key_metadata_and_remains_decryptable(self):
        self.provision()
        original_ciphertext = self.database.activated["p_ciphertext"]
        result = rewrap_credential(
            tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
            provider_key="http_fixture", credential_id=CREDENTIAL,
            client=self.database, vault_client=self.vault,
        )
        self.assertEqual(result["key_version"], 2)
        self.assertEqual(self.database.activated["p_ciphertext"], original_ciphertext)
        resolved = resolve_persistent_credential(
            tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
            provider_key="http_fixture", client=self.database,
            vault_client=self.vault,
        )
        self.assertEqual(resolved.secret.reveal_for_request(), "synthetic-token-not-real")


class Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self): return self._payload


class HttpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, path, **kwargs):
        self.requests.append((path, kwargs))
        return self.responses.pop(0)

    def close(self): pass


class VaultTransitClientTests(unittest.TestCase):
    def test_private_token_file_and_transit_operations(self):
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "token"
            token.write_text("synthetic-vault-token", encoding="utf-8")
            token.chmod(0o400)
            context = b"credential-context"
            wrapped = "vault:v1:" + base64.b64encode(b"wrapped").decode()
            http = HttpClient([
                Response(200, {"data": {
                    "plaintext": base64.b64encode(b"k" * 32).decode(),
                    "ciphertext": wrapped,
                }}),
                Response(200, {"data": {
                    "plaintext": base64.b64encode(b"k" * 32).decode(),
                }}),
                Response(200, {"data": {"ciphertext": wrapped}}),
            ])
            vault = VaultTransitClient(VaultTransitConfig(
                "http://127.0.0.1:8200", token, "madar-data-sources",
            ), client=http)
            key, value, version = vault.generate_data_key(context=context)
            self.assertEqual((bytes(key), value, version), (b"k" * 32, wrapped, 1))
            self.assertEqual(bytes(vault.unwrap_data_key(value, context=context)), b"k" * 32)
            self.assertEqual(vault.rewrap_data_key(value, context=context), (wrapped, 1))
            self.assertTrue(all(request[1]["headers"]["X-Vault-Token"] == "synthetic-vault-token" for request in http.requests))
            self.assertNotIn("synthetic-vault-token", repr(http.requests[0][0]))

    def test_unsafe_token_permissions_and_auth_errors_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            token = Path(directory) / "token"
            token.write_text("synthetic-vault-token", encoding="utf-8")
            token.chmod(0o644)
            vault = VaultTransitClient(VaultTransitConfig(
                "http://127.0.0.1:8200", token, "madar-data-sources",
            ), client=HttpClient([]))
            with self.assertRaises(VaultTransitError) as unsafe:
                vault.generate_data_key(context=b"context")
            self.assertEqual(unsafe.exception.code, "vault_token_file_unsafe")
            token.chmod(0o400)
            denied = VaultTransitClient(VaultTransitConfig(
                "http://127.0.0.1:8200", token, "madar-data-sources",
            ), client=HttpClient([Response(403, {"errors": ["do not leak this"]})]))
            with self.assertRaises(VaultTransitError) as caught:
                denied.generate_data_key(context=b"context")
            self.assertEqual(caught.exception.code, "vault_authentication_failed")
            self.assertNotIn("do not leak", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

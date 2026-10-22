"""Disposable real-Vault proof for the candidate credential boundary."""

import os
from pathlib import Path

import httpx

from services.data_source_api_provider import fetch_bounded_records
from services.data_source_credential_service import (
    DataSourceCredentialError,
    provision_credential,
    rewrap_credential,
    resolve_persistent_credential,
)
from services.http_provider_adapter import HttpApiProviderAdapter
from services.provider_http_transport import ProviderHttpSession, validate_destination
from services.provider_registry import get_provider_spec
from tests.test_data_source_credential_vault import CREDENTIAL, FakeDatabase, PROJECT, SOURCE
from tests.test_provider_http_transport import LocalFixture, TOKEN


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    database = FakeDatabase()
    provisioned = provision_credential(
        tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
        provider_key="http_fixture", credential_type="bearer", secret=TOKEN,
        client=database,
    )
    check("ciphertext" not in provisioned, "secret material escaped provisioning")
    first = resolve_persistent_credential(
        tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
        provider_key="http_fixture", client=database,
    )
    second = resolve_persistent_credential(
        tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
        provider_key="http_fixture", client=database,
    )
    check(first.secret.reveal_for_request() == TOKEN, "first decrypt failed")
    check(second.secret.reveal_for_request() == TOKEN, "worker restart decrypt failed")
    check(TOKEN not in repr(first.secret), "secret repr was not redacted")

    with LocalFixture() as fixture:
        os.environ["MADAR_TEST_HTTP_PROVIDER_URL"] = fixture.base_url
        spec = get_provider_spec("http_fixture")
        check(spec is not None, "test provider registry did not accept loopback fixture")
        session = ProviderHttpSession(
            provider_key=spec.key,
            destination=validate_destination(fixture.base_url, test_loopback=True),
            credential=first.secret, credential_validator=first.validate,
            credential_reference=first.reference.as_metadata(), auth_scheme=spec.auth,
            min_interval=0, cancelled=lambda: False,
        )
        adapter = HttpApiProviderAdapter(spec, session)
        batch = fetch_bounded_records(adapter, resource_type="records")
        adapter.close()
        check(batch.next_cursor == "cursor-1" and batch.page_count == 2,
              "real paginated provider fetch failed")

    admin_token = Path(os.environ["MADAR_TEST_VAULT_ADMIN_TOKEN_FILE"]).read_text().strip()
    vault_address = os.environ["DATA_SOURCE_VAULT_ADDR"]
    admin = httpx.Client(base_url=vault_address, trust_env=False)
    rotated = admin.post(
        "/v1/transit/keys/madar-data-sources/rotate",
        headers={"X-Vault-Token": admin_token},
    )
    check(200 <= rotated.status_code < 300, "operator key rotation failed")
    ciphertext = database.activated["p_ciphertext"]
    rewrapped = rewrap_credential(
        tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
        provider_key="http_fixture", credential_id=CREDENTIAL, client=database,
    )
    check(rewrapped["key_version"] == 2, "Transit rotation did not advance key version")
    check(database.activated["p_ciphertext"] == ciphertext, "rewrap changed ciphertext")
    resolved = resolve_persistent_credential(
        tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
        provider_key="http_fixture", client=database,
    )
    check(resolved.secret.reveal_for_request() == TOKEN, "rewrapped key did not decrypt")

    database.allow = False
    try:
        resolved.validate()
    except DataSourceCredentialError as error:
        check(error.code == "provider_credentials_revoked", "unexpected revoke failure")
    else:
        raise AssertionError("revoked credential remained valid")
    database.allow = True

    sealed = admin.put("/v1/sys/seal", headers={"X-Vault-Token": admin_token})
    check(200 <= sealed.status_code < 300, "operator seal failed")
    admin.close()
    try:
        resolve_persistent_credential(
            tenant_id=1, project_id=PROJECT, source_id=SOURCE, user_id=7,
            provider_key="http_fixture", client=database,
        )
    except DataSourceCredentialError as error:
        check(error.code == "provider_credentials_key_service_unavailable",
              "sealed Vault did not produce bounded unavailable error")
    else:
        raise AssertionError("sealed Vault did not fail closed")
    print("vault_transit_disposable_integration_passed")


if __name__ == "__main__":
    main()

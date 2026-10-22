"""Minimal, fail-closed HashiCorp Vault Transit client for Data Sources.

The application reads a short-lived token from a private file populated by a
separately managed Vault Agent.  Root tokens, unseal keys and AppRole SecretIDs
are deliberately outside this process and outside ordinary Compose environment
variables.  Disposable tests may write a dev token to an isolated temporary file.
"""

from __future__ import annotations

import base64
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx


_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_VAULT_CIPHERTEXT = re.compile(r"^vault:v(?P<version>[1-9][0-9]*):[A-Za-z0-9+/=]+$")


class VaultTransitError(RuntimeError):
    """A bounded error code; Vault response bodies and tokens are never retained."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class VaultTransitConfig:
    address: str
    token_file: Path
    key_name: str
    mount: str = "transit"
    namespace: str | None = None
    ca_cert: Path | None = None
    timeout_seconds: float = 5.0

    @classmethod
    def from_environment(cls) -> "VaultTransitConfig":
        address = os.getenv("DATA_SOURCE_VAULT_ADDR", "").strip().rstrip("/")
        token_file = os.getenv("DATA_SOURCE_VAULT_TOKEN_FILE", "").strip()
        key_name = os.getenv("DATA_SOURCE_VAULT_TRANSIT_KEY", "").strip()
        mount = os.getenv("DATA_SOURCE_VAULT_TRANSIT_MOUNT", "transit").strip()
        namespace = os.getenv("DATA_SOURCE_VAULT_NAMESPACE", "").strip() or None
        ca_value = os.getenv("DATA_SOURCE_VAULT_CA_CERT", "").strip()
        if not address or not token_file or not key_name:
            raise VaultTransitError("vault_configuration_missing")
        if not _NAME.fullmatch(key_name) or not _NAME.fullmatch(mount):
            raise VaultTransitError("vault_configuration_invalid")
        try:
            timeout = float(os.getenv("DATA_SOURCE_VAULT_TIMEOUT_SECONDS", "5"))
        except ValueError as error:
            raise VaultTransitError("vault_configuration_invalid") from error
        if not 0.25 <= timeout <= 30:
            raise VaultTransitError("vault_configuration_invalid")
        parsed = urlsplit(address)
        test_loopback = (
            os.environ.get("APP_ENV") == "test"
            and parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        )
        if (parsed.scheme != "https" and not test_loopback) or not parsed.hostname \
                or parsed.username or parsed.password or parsed.query or parsed.fragment \
                or parsed.path not in {"", "/"}:
            raise VaultTransitError("vault_configuration_invalid")
        ca_cert = Path(ca_value).resolve() if ca_value else None
        if parsed.scheme == "https" and ca_cert is None:
            raise VaultTransitError("vault_ca_missing")
        if ca_cert is not None and not ca_cert.is_file():
            raise VaultTransitError("vault_ca_invalid")
        return cls(
            address=address,
            token_file=Path(token_file).resolve(),
            key_name=key_name,
            mount=mount,
            namespace=namespace,
            ca_cert=ca_cert,
            timeout_seconds=timeout,
        )


def _read_private_token(path: Path) -> str:
    try:
        details = path.lstat()
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
            raise VaultTransitError("vault_token_file_unsafe")
        if details.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise VaultTransitError("vault_token_file_unsafe")
        if details.st_size <= 0 or details.st_size > 8192:
            raise VaultTransitError("vault_token_file_invalid")
        token = path.read_text(encoding="utf-8").strip()
    except VaultTransitError:
        raise
    except (OSError, UnicodeError) as error:
        raise VaultTransitError("vault_token_unavailable") from error
    if not token or any(ord(character) < 33 or ord(character) == 127 for character in token):
        raise VaultTransitError("vault_token_file_invalid")
    return token


class VaultTransitClient:
    def __init__(self, config: VaultTransitConfig, *, client: httpx.Client | None = None):
        self.config = config
        verify: bool | str = str(config.ca_cert) if config.ca_cert else True
        self._client = client or httpx.Client(
            base_url=config.address,
            timeout=config.timeout_seconds,
            verify=verify,
            trust_env=False,
            follow_redirects=False,
        )

    def close(self) -> None:
        self._client.close()

    def _request(self, operation: str, payload: dict[str, object]) -> dict:
        token = _read_private_token(self.config.token_file)
        headers = {"X-Vault-Token": token}
        if self.config.namespace:
            headers["X-Vault-Namespace"] = self.config.namespace
        path = f"/v1/{quote(self.config.mount, safe='')}/{operation}/{quote(self.config.key_name, safe='')}"
        try:
            response = self._client.post(path, headers=headers, json=payload)
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise VaultTransitError("vault_unavailable") from error
        except httpx.HTTPError as error:
            raise VaultTransitError("vault_request_failed") from error
        if response.status_code in {401, 403}:
            raise VaultTransitError("vault_authentication_failed")
        if response.status_code == 404:
            raise VaultTransitError("vault_key_unavailable")
        if response.status_code >= 400:
            raise VaultTransitError("vault_request_failed")
        try:
            result = response.json()
        except ValueError as error:
            raise VaultTransitError("vault_response_invalid") from error
        data = result.get("data") if isinstance(result, dict) else None
        if not isinstance(data, dict):
            raise VaultTransitError("vault_response_invalid")
        return data

    @staticmethod
    def key_version(wrapped_key: str) -> int:
        match = _VAULT_CIPHERTEXT.fullmatch(str(wrapped_key or ""))
        if not match:
            raise VaultTransitError("vault_wrapped_key_invalid")
        return int(match.group("version"))

    def generate_data_key(self, *, context: bytes) -> tuple[bytearray, str, int]:
        data = self._request("datakey/plaintext", {
            "bits": 256,
            "context": base64.b64encode(context).decode("ascii"),
        })
        wrapped = str(data.get("ciphertext") or "")
        plaintext = data.get("plaintext")
        try:
            key = bytearray(base64.b64decode(str(plaintext), validate=True))
        except (ValueError, TypeError) as error:
            raise VaultTransitError("vault_response_invalid") from error
        if len(key) != 32:
            for index in range(len(key)):
                key[index] = 0
            raise VaultTransitError("vault_response_invalid")
        return key, wrapped, self.key_version(wrapped)

    def unwrap_data_key(self, wrapped_key: str, *, context: bytes) -> bytearray:
        self.key_version(wrapped_key)
        data = self._request("decrypt", {
            "ciphertext": wrapped_key,
            "context": base64.b64encode(context).decode("ascii"),
        })
        try:
            key = bytearray(base64.b64decode(str(data.get("plaintext")), validate=True))
        except (ValueError, TypeError) as error:
            raise VaultTransitError("vault_decryption_failed") from error
        if len(key) != 32:
            for index in range(len(key)):
                key[index] = 0
            raise VaultTransitError("vault_decryption_failed")
        return key

    def rewrap_data_key(self, wrapped_key: str, *, context: bytes) -> tuple[str, int]:
        self.key_version(wrapped_key)
        data = self._request("rewrap", {
            "ciphertext": wrapped_key,
            "context": base64.b64encode(context).decode("ascii"),
        })
        rewrapped = str(data.get("ciphertext") or "")
        return rewrapped, self.key_version(rewrapped)

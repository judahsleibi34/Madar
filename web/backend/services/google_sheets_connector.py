"""Secure Google Sheets OAuth, mapping, and read-only adapter boundary."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urlsplit

from services.data_source_api_provider import (
    ProviderErrorCategory, ProviderFetchError, ProviderFetchRequest, ProviderPage,
    ProviderRecord,
)
from services.provider_credentials import AuthorizedSource
from services.provider_http_transport import (
    ProviderHttpSession, SecretValue, TransportError, validate_destination,
)


PROVIDER_KEY = "google_sheets"
RESOURCE_TYPE = "sheet"
SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com"
SHEETS_ENDPOINT = "https://sheets.googleapis.com"
SPREADSHEET_ID = re.compile(r"^[A-Za-z0-9_-]{20,200}$")
STATE_NONCE = re.compile(r"^[A-Za-z0-9_-]{43}$")
MAX_PREVIEW_ROWS = 20
MAX_ROWS = 10_000
MAX_COLUMNS = 128
PAGE_ROWS = 1_000


class GoogleSheetsError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class GoogleSheetsConfig:
    client_id: str
    client_secret: SecretValue
    redirect_uri: str
    state_key: bytes
    authorization_endpoint: str = AUTHORIZATION_ENDPOINT
    token_base_url: str = TOKEN_ENDPOINT
    sheets_base_url: str = SHEETS_ENDPOINT
    test_loopback: bool = False


def _urlsafe(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode_key(value: str) -> bytes:
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError) as error:
        raise GoogleSheetsError("google_sheets_configuration_invalid") from error
    if len(decoded) < 32:
        raise GoogleSheetsError("google_sheets_configuration_invalid")
    return decoded


def _approved_endpoint(value: str, expected: str, *, test_name: str) -> tuple[str, bool]:
    value = value.strip() or expected
    if value == expected:
        return value, False
    parsed = urlsplit(value)
    if os.getenv("APP_ENV") != "test" or os.getenv(test_name) != value:
        raise GoogleSheetsError("google_sheets_configuration_invalid")
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"} \
            or parsed.port is None or parsed.query or parsed.fragment:
        raise GoogleSheetsError("google_sheets_configuration_invalid")
    return value.rstrip("/"), True


def google_sheets_config() -> GoogleSheetsConfig:
    if os.getenv("GOOGLE_SHEETS_PROVIDER_ENABLED", "").strip().lower() != "true":
        raise GoogleSheetsError("google_sheets_provider_disabled")
    client_id = os.getenv("GOOGLE_SHEETS_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_SHEETS_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("GOOGLE_SHEETS_REDIRECT_URI", "").strip()
    state_key = os.getenv("GOOGLE_SHEETS_STATE_KEY", "").strip()
    if not client_id or len(client_id) > 512 or not client_secret or not state_key:
        raise GoogleSheetsError("google_sheets_configuration_invalid")
    redirect = urlsplit(redirect_uri)
    loopback_redirect = os.getenv("APP_ENV") == "test" and redirect.hostname in {"127.0.0.1", "localhost"}
    if (redirect.scheme != "https" and not (loopback_redirect and redirect.scheme == "http")) \
            or redirect.query or redirect.fragment or redirect.username or redirect.password:
        raise GoogleSheetsError("google_sheets_configuration_invalid")
    authorization, auth_loopback = _approved_endpoint(
        os.getenv("GOOGLE_SHEETS_AUTHORIZATION_ENDPOINT", ""), AUTHORIZATION_ENDPOINT,
        test_name="GOOGLE_SHEETS_AUTHORIZATION_ENDPOINT",
    )
    token, token_loopback = _approved_endpoint(
        os.getenv("GOOGLE_SHEETS_TOKEN_ENDPOINT", ""), TOKEN_ENDPOINT,
        test_name="GOOGLE_SHEETS_TOKEN_ENDPOINT",
    )
    sheets, sheets_loopback = _approved_endpoint(
        os.getenv("GOOGLE_SHEETS_API_ENDPOINT", ""), SHEETS_ENDPOINT,
        test_name="GOOGLE_SHEETS_API_ENDPOINT",
    )
    return GoogleSheetsConfig(
        client_id, SecretValue(client_secret), redirect_uri, _decode_key(state_key),
        authorization, token, sheets,
        auth_loopback or token_loopback or sheets_loopback,
    )


def google_sheets_configured() -> bool:
    try:
        google_sheets_config()
        return True
    except (GoogleSheetsError, ValueError):
        return False


def parse_spreadsheet_url(value: str) -> tuple[str, int | None]:
    """Extract identifiers from a canonical Google Sheets URL without fetching it."""
    try:
        parsed = urlsplit(str(value or "").strip())
    except ValueError as error:
        raise GoogleSheetsError("google_sheets_url_invalid") from error
    if parsed.scheme != "https" or parsed.hostname != "docs.google.com" \
            or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise GoogleSheetsError("google_sheets_url_invalid")
    match = re.fullmatch(r"/spreadsheets/d/([A-Za-z0-9_-]{20,200})(?:/[^?#]*)?", parsed.path)
    if not match or not SPREADSHEET_ID.fullmatch(match.group(1)):
        raise GoogleSheetsError("google_sheets_url_invalid")
    fragment = parse_qs(parsed.fragment, keep_blank_values=True)
    gid_values = fragment.get("gid", [])
    if len(gid_values) > 1 or (gid_values and not gid_values[0].isdigit()):
        raise GoogleSheetsError("google_sheets_url_invalid")
    return match.group(1), int(gid_values[0]) if gid_values else None


def resource_key(spreadsheet_id: str, sheet_id: int) -> str:
    return "gs_" + hashlib.sha256(f"{spreadsheet_id}:{int(sheet_id)}".encode()).hexdigest()[:48]


def create_state(config: GoogleSheetsConfig) -> tuple[str, str, str]:
    nonce = _urlsafe(secrets.token_bytes(32))
    verifier = _urlsafe(secrets.token_bytes(48))
    mac = _urlsafe(hmac.digest(config.state_key, f"v1.{nonce}".encode(), "sha256"))
    challenge = _urlsafe(hashlib.sha256(verifier.encode("ascii")).digest())
    return f"v1.{nonce}.{mac}", verifier, challenge


def validate_state_shape(state: str, config: GoogleSheetsConfig) -> str:
    parts = str(state or "").split(".")
    if len(parts) != 3 or parts[0] != "v1" or not STATE_NONCE.fullmatch(parts[1]):
        raise GoogleSheetsError("google_sheets_oauth_state_invalid")
    expected = _urlsafe(hmac.digest(config.state_key, f"v1.{parts[1]}".encode(), "sha256"))
    if not hmac.compare_digest(expected, parts[2]):
        raise GoogleSheetsError("google_sheets_oauth_state_invalid")
    return hashlib.sha256(state.encode("ascii")).hexdigest()


def authorization_url(config: GoogleSheetsConfig, state: str, challenge: str) -> str:
    return config.authorization_endpoint + "?" + urlencode({
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "false",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })


def _token_session(config: GoogleSheetsConfig) -> ProviderHttpSession:
    return ProviderHttpSession(
        provider_key=PROVIDER_KEY,
        destination=validate_destination(config.token_base_url, test_loopback=config.test_loopback),
        max_response_bytes=64 * 1024,
    )


def _token_request(config: GoogleSheetsConfig, fields: dict[str, str]) -> dict:
    session = _token_session(config)
    try:
        result = session.post_form_json(
            "/token", fields, deadline=time.monotonic() + 20,
            allowed_fields=frozenset(fields),
        )
    except TransportError as error:
        code = "google_sheets_authorization_invalid" if error.code == "unauthorized" \
            else "google_sheets_provider_unavailable"
        raise GoogleSheetsError(code) from error
    finally:
        session.close()
    if not isinstance(result, dict):
        raise GoogleSheetsError("google_sheets_authorization_invalid")
    return result


def exchange_authorization_code(config: GoogleSheetsConfig, code: str, verifier: str) -> dict:
    if not code or len(code) > 4096 or not verifier or len(verifier) > 128:
        raise GoogleSheetsError("google_sheets_authorization_invalid")
    result = _token_request(config, {
        "client_id": config.client_id,
        "client_secret": config.client_secret.reveal_for_request(),
        "code": code,
        "code_verifier": verifier,
        "grant_type": "authorization_code",
        "redirect_uri": config.redirect_uri,
    })
    scopes = set(str(result.get("scope") or "").split())
    if SCOPE not in scopes or not isinstance(result.get("refresh_token"), str):
        raise GoogleSheetsError("google_sheets_scope_insufficient")
    access_token = result.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise GoogleSheetsError("google_sheets_authorization_invalid")
    return {
        "access_token": access_token,
        "refresh_token": result["refresh_token"],
        "scope": SCOPE,
        "expires_in": min(max(int(result.get("expires_in") or 3600), 1), 86400),
    }


def refresh_access_token(config: GoogleSheetsConfig, credential_json: str) -> str:
    try:
        stored = json.loads(credential_json)
    except (TypeError, ValueError) as error:
        raise GoogleSheetsError("google_sheets_authorization_invalid") from error
    if not isinstance(stored, dict) or stored.get("scope") != SCOPE \
            or not isinstance(stored.get("refresh_token"), str):
        raise GoogleSheetsError("google_sheets_authorization_invalid")
    result = _token_request(config, {
        "client_id": config.client_id,
        "client_secret": config.client_secret.reveal_for_request(),
        "grant_type": "refresh_token",
        "refresh_token": stored["refresh_token"],
    })
    token = result.get("access_token")
    returned_scope = str(result.get("scope") or SCOPE).split()
    if not isinstance(token, str) or not token or SCOPE not in returned_scope:
        raise GoogleSheetsError("google_sheets_authorization_invalid")
    return token


def credential_payload(token: dict) -> str:
    value = json.dumps(
        {"refresh_token": token["refresh_token"], "scope": SCOPE},
        sort_keys=True, separators=(",", ":"),
    )
    if len(value) > 4096:
        raise GoogleSheetsError("google_sheets_authorization_invalid")
    return value


def begin_oauth(
    source: AuthorizedSource, *, client, vault_client=None,
) -> dict:
    from services import data_source_credential_service
    config = google_sheets_config()
    state, verifier, challenge = create_state(config)
    expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    client.rpc("begin_data_source_oauth161", {
        "p_tenant_id": source.tenant_id, "p_project_id": source.project_id,
        "p_source_id": source.source_id, "p_actor_user_id": source.user_id,
        "p_provider_key": PROVIDER_KEY,
        "p_state_hash": hashlib.sha256(state.encode("ascii")).hexdigest(),
        "p_redirect_uri": config.redirect_uri, "p_expires_at": expires.isoformat(),
    }).execute()
    try:
        data_source_credential_service.provision_credential(
            tenant_id=source.tenant_id, project_id=source.project_id,
            source_id=source.source_id, user_id=int(source.user_id or 0),
            provider_key=PROVIDER_KEY, credential_type="oauth_pkce",
            secret=verifier, expires_at=expires.isoformat(), client=client,
            vault_client=vault_client,
        )
    except Exception:
        # The unreturned state remains unusable and expires quickly.
        raise
    return {"authorization_url": authorization_url(config, state, challenge),
            "expires_at": expires.isoformat(), "scope": SCOPE}


def _response_rows(response) -> list[dict]:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return [data]
    return list(data or [])


def consume_oauth_transaction(state: str, *, client) -> dict:
    config = google_sheets_config()
    state_hash = validate_state_shape(state, config)
    response = client.rpc("consume_data_source_oauth161", {
        "p_state_hash": state_hash, "p_provider_key": PROVIDER_KEY,
        "p_redirect_uri": config.redirect_uri,
    }).execute()
    rows = _response_rows(response)
    if not rows:
        raise GoogleSheetsError("google_sheets_oauth_state_invalid")
    return rows[0]


def get_mapping(source: AuthorizedSource, *, client) -> dict:
    rows = list(getattr(
        client.table("google_sheets_source_mappings").select("*")
        .eq("tenant_id", source.tenant_id).eq("project_id", source.project_id)
        .eq("source_id", source.source_id).limit(1).execute(), "data", None,
    ) or [])
    if not rows:
        raise GoogleSheetsError("google_sheets_mapping_missing")
    return rows[0]


def save_mapping(source: AuthorizedSource, mapping: dict, *, client) -> dict:
    response = client.rpc("save_google_sheets_mapping161", {
        "p_tenant_id": source.tenant_id, "p_project_id": source.project_id,
        "p_source_id": source.source_id, "p_actor_user_id": source.user_id,
        "p_spreadsheet_id": mapping["spreadsheet_id"],
        "p_spreadsheet_title": mapping.get("spreadsheet_title", ""),
        "p_sheet_id": int(mapping["sheet_id"]), "p_sheet_title": mapping["sheet_title"],
        "p_header_row": int(mapping["header_row"]),
        "p_selected_columns": mapping["selected_columns"],
        "p_record_id_column": mapping["record_id_column"],
        "p_resource_key": resource_key(mapping["spreadsheet_id"], int(mapping["sheet_id"])),
        "p_expected_revision": mapping.get("expected_revision"),
    }).execute()
    rows = _response_rows(response)
    if not rows:
        raise GoogleSheetsError("google_sheets_mapping_not_saved")
    return rows[0]


def _a1_title(title: str) -> str:
    if not title or len(title) > 255 or any(ord(char) < 32 for char in title):
        raise GoogleSheetsError("google_sheets_response_invalid")
    return "'" + title.replace("'", "''") + "'"


def _headers(values: list) -> list[str]:
    headers = [str(value).strip() for value in values]
    if not headers or any(not value for value in headers) or len(set(headers)) != len(headers):
        raise GoogleSheetsError("google_sheets_headers_invalid")
    return headers


class GoogleSheetsClient:
    def __init__(self, config: GoogleSheetsConfig, access_token: str):
        self.session = ProviderHttpSession(
            provider_key=PROVIDER_KEY,
            destination=validate_destination(config.sheets_base_url, test_loopback=config.test_loopback),
            credential=SecretValue(access_token), auth_scheme="bearer", min_interval=1.0,
            max_response_bytes=4 * 1024 * 1024,
        )

    def close(self):
        self.session.close()

    def metadata(self, spreadsheet_id: str, *, deadline: float | None = None) -> dict:
        if not SPREADSHEET_ID.fullmatch(spreadsheet_id):
            raise GoogleSheetsError("google_sheets_url_invalid")
        try:
            body = self.session.get_json(
                f"/v4/spreadsheets/{spreadsheet_id}",
                {"fields": "spreadsheetId,properties.title,sheets.properties(sheetId,title,index,gridProperties)"},
                deadline=deadline if deadline is not None else time.monotonic() + 20,
            )
        except TransportError as error:
            raise _google_transport_error(error) from error
        if not isinstance(body, dict) or body.get("spreadsheetId") != spreadsheet_id \
                or not isinstance(body.get("sheets"), list):
            raise GoogleSheetsError("google_sheets_response_invalid")
        tabs = []
        for item in body["sheets"]:
            props = item.get("properties") if isinstance(item, dict) else None
            if not isinstance(props, dict) or not isinstance(props.get("sheetId"), int) \
                    or not isinstance(props.get("title"), str):
                raise GoogleSheetsError("google_sheets_response_invalid")
            grid = props.get("gridProperties") or {}
            tabs.append({"sheet_id": props["sheetId"], "title": props["title"],
                         "index": int(props.get("index") or 0),
                         "row_count": min(int(grid.get("rowCount") or 0), MAX_ROWS + 1000),
                         "column_count": min(int(grid.get("columnCount") or 0), MAX_COLUMNS + 1)})
        return {"spreadsheet_id": spreadsheet_id,
                "title": str((body.get("properties") or {}).get("title") or "")[:255],
                "tabs": tabs}

    def values(
        self, spreadsheet_id: str, range_value: str, *, deadline: float | None = None,
    ) -> list[list]:
        try:
            body = self.session.get_json(
                f"/v4/spreadsheets/{spreadsheet_id}/values:batchGet",
                {"ranges": range_value, "majorDimension": "ROWS",
                 "valueRenderOption": "UNFORMATTED_VALUE",
                 "dateTimeRenderOption": "FORMATTED_STRING"},
                deadline=deadline if deadline is not None else time.monotonic() + 20,
            )
        except TransportError as error:
            raise _google_transport_error(error) from error
        ranges = body.get("valueRanges") if isinstance(body, dict) else None
        values = ranges[0].get("values", []) if isinstance(ranges, list) and len(ranges) == 1 \
            and isinstance(ranges[0], dict) else None
        if not isinstance(values, list) or any(not isinstance(row, list) for row in values):
            raise GoogleSheetsError("google_sheets_response_invalid")
        return values


def _google_transport_error(error: TransportError) -> GoogleSheetsError:
    mapping = {"unauthorized": "google_sheets_authorization_invalid",
               "rate_limited": "google_sheets_rate_limited",
               "timeout": "google_sheets_timeout",
               "payload_too_large": "google_sheets_response_too_large"}
    return GoogleSheetsError(mapping.get(error.code, "google_sheets_provider_unavailable"))


def preview_mapping(
    client: GoogleSheetsClient, spreadsheet_id: str, sheet_id: int,
    *, header_row: int = 1,
) -> dict:
    metadata = client.metadata(spreadsheet_id)
    tab = next((item for item in metadata["tabs"] if item["sheet_id"] == int(sheet_id)), None)
    if tab is None:
        raise GoogleSheetsError("google_sheets_tab_missing")
    end = min(header_row + MAX_PREVIEW_ROWS, MAX_ROWS)
    values = client.values(spreadsheet_id, f"{_a1_title(tab['title'])}!{header_row}:{end}")
    if not values:
        raise GoogleSheetsError("google_sheets_headers_invalid")
    headers = _headers(values[0])
    if len(headers) > MAX_COLUMNS:
        raise GoogleSheetsError("google_sheets_too_many_columns")
    rows = []
    for raw in values[1:MAX_PREVIEW_ROWS + 1]:
        padded = list(raw[:len(headers)]) + [None] * max(0, len(headers) - len(raw))
        if any(value not in (None, "") for value in padded):
            rows.append(dict(zip(headers, padded)))
    return {"spreadsheet_id": spreadsheet_id, "spreadsheet_title": metadata["title"],
            "sheet_id": int(sheet_id), "sheet_title": tab["title"],
            "header_row": header_row, "headers": headers, "rows": rows}


class GoogleSheetsAdapter:
    provider_key = PROVIDER_KEY
    supported_resources = frozenset({RESOURCE_TYPE})

    def __init__(self, source: AuthorizedSource, mapping: dict, client: GoogleSheetsClient,
                 credential_lease, *, current_hashes: dict[str, str] | None = None,
                 next_order: int = 1):
        self.source = source
        self.mapping = mapping
        self.client = client
        self.credential_lease = credential_lease
        self.supported_resources = frozenset({RESOURCE_TYPE, str(mapping["resource_key"])})
        self._metadata = None
        self._headers = None
        self._completed = False
        self._fingerprint = None
        self._snapshot_hash = hashlib.sha256()
        self._current_hashes = current_hashes or {}
        self._next_order = max(1, int(next_order))
        self._emitted = False
        self._seen_ids: set[str] = set()
        self.no_changes = False

    def _prepare(self, deadline: float):
        if self._headers is not None:
            return
        metadata = self.client.metadata(
            str(self.mapping["spreadsheet_id"]), deadline=deadline,
        )
        tab = next((value for value in metadata["tabs"]
                    if value["sheet_id"] == int(self.mapping["sheet_id"])), None)
        if tab is None:
            raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
        header_values = self.client.values(
            str(self.mapping["spreadsheet_id"]),
            f"{_a1_title(tab['title'])}!{int(self.mapping['header_row'])}:{int(self.mapping['header_row'])}",
            deadline=deadline,
        )
        try:
            headers = _headers(header_values[0] if header_values else [])
        except GoogleSheetsError as error:
            raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE) from error
        selected = list(self.mapping["selected_columns"])
        record_id = str(self.mapping["record_id_column"])
        if record_id not in selected or any(value not in headers for value in selected):
            raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
        self._metadata, self._headers = tab, headers

    def fetch_page(self, request: ProviderFetchRequest) -> ProviderPage:
        try:
            self._prepare(request.deadline)
            start = int(request.continuation or (int(self.mapping["header_row"]) + 1))
            max_row = min(int(self.mapping.get("max_rows") or MAX_ROWS),
                          int(self._metadata.get("row_count") or MAX_ROWS))
            end = min(start + PAGE_ROWS - 1, max_row)
            values = self.client.values(
                str(self.mapping["spreadsheet_id"]),
                f"{_a1_title(self._metadata['title'])}!{start}:{end}",
                deadline=request.deadline,
            )
            selected = list(self.mapping["selected_columns"])
            id_column = str(self.mapping["record_id_column"])
            indexes = {name: self._headers.index(name) for name in selected}
            records = []
            for raw in values:
                if not any(value not in (None, "") for value in raw):
                    continue
                data = {name: raw[index] if index < len(raw) else None
                        for name, index in indexes.items()}
                identifier = str(data.get(id_column) or "").strip()
                if not identifier or len(identifier) > 255 or identifier in self._seen_ids:
                    raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
                self._seen_ids.add(identifier)
                self._snapshot_hash.update(json.dumps(
                    [identifier, data], sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False,
                ).encode())
                self._snapshot_hash.update(b"\n")
                content_hash = hashlib.sha256(json.dumps({
                    "operation": "upsert", "source_record_id": identifier, "payload": data,
                }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                if self._current_hashes.get(identifier) != content_hash:
                    records.append(ProviderRecord(
                        identifier, data, "upsert", source_order=self._next_order,
                    ))
                    self._emitted = True
            continuation = str(end + 1) if end < max_row and values else None
            if continuation is None:
                self._completed = True
                self.no_changes = not self._emitted and bool(self._current_hashes)
            if continuation is None:
                self._fingerprint = self._snapshot_hash.hexdigest()
            return ProviderPage(records, continuation)
        except ProviderFetchError:
            raise
        except GoogleSheetsError as error:
            mapping = {"google_sheets_authorization_invalid": ProviderErrorCategory.UNAUTHORIZED,
                       "google_sheets_rate_limited": ProviderErrorCategory.RATE_LIMITED,
                       "google_sheets_timeout": ProviderErrorCategory.TIMEOUT,
                       "google_sheets_response_too_large": ProviderErrorCategory.PAYLOAD_TOO_LARGE}
            raise ProviderFetchError(mapping.get(error.code, ProviderErrorCategory.INVALID_RESPONSE)) from error

    def next_cursor(self, _resource_type: str, _current: str | None) -> str:
        if not self._completed or not self._fingerprint:
            raise ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)
        return "snapshot:" + self._fingerprint

    def revalidate_credential(self):
        self.credential_lease.validate()

    def credential_reference(self):
        return self.credential_lease.reference_metadata()

    def close(self):
        self.client.close()


def build_adapter(source: AuthorizedSource, *, database) -> GoogleSheetsAdapter:
    from services.data_source_credential_service import resolve_persistent_credential
    config = google_sheets_config()
    mapping = get_mapping(source, client=database)
    resolved = resolve_persistent_credential(
        tenant_id=source.tenant_id, project_id=source.project_id,
        source_id=source.source_id, user_id=int(source.user_id or 0),
        provider_key=PROVIDER_KEY, credential_type="oauth_refresh", client=database,
    )
    token = refresh_access_token(config, resolved.secret.reveal_for_request())

    class Lease:
        def validate(self): resolved.validate()
        def reference_metadata(self): return resolved.reference.as_metadata()

    resources = list(getattr(
        database.table("data_source_resources").select("dataset_id,committed_revision")
        .eq("tenant_id", source.tenant_id).eq("project_id", source.project_id)
        .eq("source_id", source.source_id).eq("resource_key", mapping["resource_key"])
        .limit(1).execute(), "data", None,
    ) or [])
    current_hashes: dict[str, str] = {}
    next_order = 1
    if resources and resources[0].get("dataset_id"):
        next_order = int(resources[0].get("committed_revision") or 0) + 1
        offset = 0
        while offset < MAX_ROWS:
            rows = list(getattr(
                database.table("data_dataset_current_records")
                .select("source_record_id,content_hash")
                .eq("tenant_id", source.tenant_id)
                .eq("dataset_id", resources[0]["dataset_id"])
                .eq("is_deleted", False).order("source_record_id")
                .range(offset, min(offset + 499, MAX_ROWS - 1)).execute(),
                "data", None,
            ) or [])
            for row in rows:
                current_hashes[str(row["source_record_id"])] = str(row["content_hash"])
            if len(rows) < 500:
                break
            offset += 500
    return GoogleSheetsAdapter(
        source, mapping, GoogleSheetsClient(config, token), Lease(),
        current_hashes=current_hashes, next_order=next_order,
    )


__all__ = [
    "GoogleSheetsAdapter", "GoogleSheetsClient", "GoogleSheetsConfig", "GoogleSheetsError",
    "PROVIDER_KEY", "RESOURCE_TYPE", "SCOPE", "authorization_url", "begin_oauth",
    "build_adapter", "consume_oauth_transaction", "create_state", "credential_payload",
    "exchange_authorization_code", "get_mapping", "google_sheets_config",
    "google_sheets_configured", "parse_spreadsheet_url", "preview_mapping",
    "refresh_access_token", "resource_key", "save_mapping", "validate_state_shape",
]

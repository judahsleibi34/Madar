import base64
import hashlib
import json
import os
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, unquote, urlsplit

from services.data_source_api_provider import (
    ProviderErrorCategory, ProviderFetchError, ProviderNoChanges, fetch_bounded_records,
)
from services.google_sheets_connector import (
    GoogleSheetsAdapter, GoogleSheetsClient, GoogleSheetsConfig, GoogleSheetsError, SCOPE,
    create_state, credential_payload, exchange_authorization_code,
    consume_oauth_transaction, parse_spreadsheet_url, preview_mapping,
    refresh_access_token, resource_key, save_mapping,
    validate_state_shape,
)
from services.provider_credentials import AuthorizedSource
from services.provider_http_transport import SecretValue


SPREADSHEET = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
SOURCE = AuthorizedSource(
    7, "11111111-1111-4111-8111-111111111111",
    "22222222-2222-4222-8222-222222222222", "google_sheets", 9,
)


def config():
    return GoogleSheetsConfig(
        "client", SecretValue("client-secret"),
        "https://api.example.test/data/oauth/google-sheets/callback", b"s" * 32,
    )


class FakeSheetsClient:
    def __init__(self, *, headers=None, rows=None, tabs=None):
        self.headers = headers or ["id", "name", "amount"]
        self.rows = rows or [["A", "Alpha", 10], ["B", "Beta", 20]]
        self.tabs = tabs or [{"sheet_id": 5, "title": "Orders", "index": 0,
                              "row_count": 3, "column_count": 3}]
        self.closed = False

    def metadata(self, spreadsheet_id, *, deadline=None):
        return {"spreadsheet_id": spreadsheet_id, "title": "Business workbook",
                "tabs": self.tabs}

    def values(self, _spreadsheet_id, range_value, *, deadline=None):
        if range_value.endswith("!1:1"):
            return [self.headers]
        if range_value.endswith("!1:21"):
            return [self.headers, *self.rows]
        return self.rows

    def close(self):
        self.closed = True


class Lease:
    def __init__(self): self.validated = False
    def validate(self): self.validated = True
    def reference_metadata(self):
        return {"credential_id": "id", "credential_version": 2, "source_revision": 3}


class GoogleFixtureHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    mode = "normal"
    requests = []

    def log_message(self, _format, *_args):
        return

    def _send(self, status, payload):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if status == 429:
            self.send_header("Retry-After", "0")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode())
        type(self).requests.append(("POST", self.path, form))
        if self.path != "/token":
            self._send(404, {"error": "not_found"})
        elif form.get("refresh_token") == ["revoked"]:
            self._send(401, {"error": "invalid_grant"})
        elif form.get("grant_type") == ["authorization_code"]:
            self._send(200, {"access_token": "access-one", "refresh_token": "refresh-one",
                             "scope": SCOPE, "expires_in": 3600})
        elif form.get("grant_type") == ["refresh_token"]:
            self._send(200, {"access_token": "access-two", "scope": SCOPE, "expires_in": 3600})
        else:
            self._send(400, {"error": "invalid_request"})

    def do_GET(self):
        type(self).requests.append(("GET", self.path, self.headers.get("Authorization")))
        if self.headers.get("Authorization") != "Bearer access-two":
            self._send(401, {"error": "invalid_token"})
            return
        mode = type(self).mode
        if mode == "permission_denied":
            self._send(403, {"error": "forbidden"})
            return
        if mode == "missing":
            self._send(404, {"error": "not_found"})
            return
        if mode == "rate_limited":
            self._send(429, {"error": "rate_limited"})
            return
        if mode == "timeout":
            time.sleep(0.05)
        if mode == "oversized":
            self._send(200, b"x" * (4 * 1024 * 1024 + 1))
            return
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        requested_range = parse_qs(parsed.query).get("ranges", [""])[0]
        if path == f"/v4/spreadsheets/{SPREADSHEET}":
            active_title = "Q4 / Orders" if mode == "renamed_tab" else "Orders"
            self._send(200, {
                "spreadsheetId": SPREADSHEET, "properties": {"title": "Business workbook"},
                "sheets": [
                    {"properties": {"sheetId": 5, "title": active_title, "index": 0,
                                    "gridProperties": {"rowCount": 4, "columnCount": 3}}},
                    {"properties": {"sheetId": 9, "title": "Archive", "index": 1,
                                    "gridProperties": {"rowCount": 2, "columnCount": 3}}},
                ],
            })
        elif path == f"/v4/spreadsheets/{SPREADSHEET}/values:batchGet":
            if mode == "header_changed":
                self._send(200, {"valueRanges": [{"values": [["different", "name", "amount"]]}]})
            elif mode == "duplicate_ids":
                self._send(200, {"valueRanges": [{"values": [["A", "Alpha", 10], ["A", "Again", 20]]}]})
            elif mode == "partial_failure" and "2:4" in requested_range:
                self._send(503, {"error": "incomplete"})
            elif "1:1" in requested_range:
                self._send(200, {"valueRanges": [{"values": [["id", "name", "amount"]]}]})
            elif "1:21" in requested_range:
                self._send(200, {"valueRanges": [{"values": [["id", "name", "amount"],
                                              ["A", "Alpha", 10], ["B", "Beta", 20]]}]})
            else:
                self._send(200, {"valueRanges": [{"values": [["A", "Alpha", 10], ["B", "Beta", 20]]}]})
        else:
            self._send(404, {"error": "not_found"})


class GoogleFixture:
    def __enter__(self):
        GoogleFixtureHandler.mode = "normal"
        GoogleFixtureHandler.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), GoogleFixtureHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def config(self):
        return GoogleSheetsConfig(
            "client", SecretValue("client-secret"),
            "http://127.0.0.1:5173/data/oauth/google-sheets/callback", b"s" * 32,
            authorization_endpoint=self.base_url + "/authorize",
            token_base_url=self.base_url, sheets_base_url=self.base_url, test_loopback=True,
        )


class GoogleSheetsSecurityTests(unittest.TestCase):
    def test_url_parser_accepts_only_canonical_google_sheet_links(self):
        value, gid = parse_spreadsheet_url(
            f"https://docs.google.com/spreadsheets/d/{SPREADSHEET}/edit#gid=42"
        )
        self.assertEqual((value, gid), (SPREADSHEET, 42))
        for invalid in (
            f"http://docs.google.com/spreadsheets/d/{SPREADSHEET}/edit",
            f"https://evil.example/spreadsheets/d/{SPREADSHEET}/edit",
            "https://docs.google.com/spreadsheets/d/short/edit",
            f"https://docs.google.com.evil.test/spreadsheets/d/{SPREADSHEET}/edit",
            f"https://docs.google.com/spreadsheets/d/{SPREADSHEET}/edit#gid=bad",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(GoogleSheetsError):
                parse_spreadsheet_url(invalid)

    def test_state_is_authenticated_pkce_s256_and_tampering_fails(self):
        state, verifier, challenge = create_state(config())
        self.assertEqual(validate_state_shape(state, config()), hashlib.sha256(state.encode()).hexdigest())
        self.assertEqual(challenge, base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode())
        with self.assertRaises(GoogleSheetsError):
            validate_state_shape(state[:-1] + ("A" if state[-1] != "A" else "B"), config())
        self.assertNotIn(verifier, state)

    def test_token_contract_requires_read_only_scope_and_reduces_storage(self):
        with patch("services.google_sheets_connector._token_request", return_value={
            "access_token": "short-lived", "refresh_token": "durable",
            "scope": SCOPE, "expires_in": 3600, "id_token": "must-not-store",
        }):
            token = exchange_authorization_code(config(), "code", "verifier")
        stored = credential_payload(token)
        self.assertEqual(json.loads(stored), {"refresh_token": "durable", "scope": SCOPE})
        self.assertNotIn("short-lived", stored)
        with patch("services.google_sheets_connector._token_request", return_value={
            "access_token": "access", "scope": "openid",
        }), self.assertRaises(GoogleSheetsError):
            refresh_access_token(config(), stored)

    def test_preview_rejects_duplicate_headers_and_preserves_scalar_values(self):
        preview = preview_mapping(FakeSheetsClient(), SPREADSHEET, 5)
        self.assertEqual(preview["headers"], ["id", "name", "amount"])
        self.assertEqual(preview["rows"][0]["amount"], 10)
        with self.assertRaises(GoogleSheetsError):
            preview_mapping(FakeSheetsClient(headers=["id", "id"]), SPREADSHEET, 5)

    def test_resource_identity_uses_spreadsheet_and_numeric_tab(self):
        one = resource_key(SPREADSHEET, 5)
        self.assertRegex(one, r"^gs_[0-9a-f]{48}$")
        self.assertNotEqual(one, resource_key(SPREADSHEET, 6))

    def test_composite_rpc_objects_are_normalized_without_losing_scope_fields(self):
        transaction = {"tenant_id": 7, "actor_user_id": 9, "project_id": SOURCE.project_id,
                       "source_id": SOURCE.source_id}
        mapping = {"spreadsheet_id": SPREADSHEET, "sheet_id": 5, "sheet_title": "Orders",
                   "header_row": 1, "selected_columns": ["id"],
                   "record_id_column": "id", "mapping_revision": 1}
        client = Mock()
        transaction_call = Mock()
        transaction_call.execute.return_value = SimpleNamespace(data=transaction)
        mapping_call = Mock()
        mapping_call.execute.return_value = SimpleNamespace(data=mapping)
        client.rpc.side_effect = [transaction_call, mapping_call]
        state, _, _ = create_state(config())
        with patch("services.google_sheets_connector.google_sheets_config", return_value=config()):
            self.assertEqual(consume_oauth_transaction(state, client=client), transaction)
        self.assertEqual(save_mapping(SOURCE, mapping, client=client), mapping)


class GoogleSheetsHttpFixtureTests(unittest.TestCase):
    def test_oauth_refresh_metadata_tabs_and_bounded_preview_use_real_transport(self):
        with GoogleFixture() as fixture, patch.dict(os.environ, {"APP_ENV": "test"}, clear=False):
            token = exchange_authorization_code(fixture.config(), "authorization-code", "verifier")
            self.assertEqual(token["refresh_token"], "refresh-one")
            access = refresh_access_token(fixture.config(), credential_payload(token))
            client = GoogleSheetsClient(fixture.config(), access)
            try:
                metadata = client.metadata(SPREADSHEET)
                preview = preview_mapping(client, SPREADSHEET, 5)
                GoogleFixtureHandler.mode = "renamed_tab"
                renamed = preview_mapping(client, SPREADSHEET, 5)
            finally:
                client.close()
        self.assertEqual([tab["sheet_id"] for tab in metadata["tabs"]], [5, 9])
        self.assertEqual(preview["headers"], ["id", "name", "amount"])
        self.assertEqual(preview["rows"][1]["amount"], 20)
        self.assertEqual(renamed["sheet_id"], 5)
        self.assertEqual(renamed["sheet_title"], "Q4 / Orders")
        self.assertTrue(any(request[0] == "POST" and request[1] == "/token"
                            for request in GoogleFixtureHandler.requests))
        self.assertTrue(any(request[0] == "GET" and "/v4/spreadsheets/" in request[1]
                            for request in GoogleFixtureHandler.requests))

    def test_fixture_revocation_permission_missing_and_rate_limit_fail_closed(self):
        with GoogleFixture() as fixture, patch.dict(os.environ, {"APP_ENV": "test"}, clear=False):
            with self.assertRaises(GoogleSheetsError) as revoked:
                refresh_access_token(fixture.config(), json.dumps({
                    "refresh_token": "revoked", "scope": SCOPE,
                }))
            self.assertEqual(revoked.exception.code, "google_sheets_authorization_invalid")
            for mode, expected in (
                ("permission_denied", "google_sheets_authorization_invalid"),
                ("missing", "google_sheets_provider_unavailable"),
                ("rate_limited", "google_sheets_rate_limited"),
            ):
                GoogleFixtureHandler.mode = mode
                client = GoogleSheetsClient(fixture.config(), "access-two")
                try:
                    with self.subTest(mode=mode), self.assertRaises(GoogleSheetsError) as failure:
                        client.metadata(SPREADSHEET)
                    self.assertEqual(failure.exception.code, expected)
                finally:
                    client.close()

    def test_fixture_header_change_partial_failure_timeout_and_size_bounds(self):
        with GoogleFixture() as fixture, patch.dict(os.environ, {"APP_ENV": "test"}, clear=False):
            mapping = {"spreadsheet_id": SPREADSHEET, "sheet_id": 5, "sheet_title": "Orders",
                       "header_row": 1, "selected_columns": ["id", "name", "amount"],
                       "record_id_column": "id", "resource_key": resource_key(SPREADSHEET, 5),
                       "max_rows": 4, "max_columns": 3}
            for mode, category in (
                ("header_changed", ProviderErrorCategory.INVALID_RESPONSE),
                ("partial_failure", ProviderErrorCategory.INVALID_RESPONSE),
                ("oversized", ProviderErrorCategory.PAYLOAD_TOO_LARGE),
            ):
                GoogleFixtureHandler.mode = mode
                adapter = GoogleSheetsAdapter(
                    SOURCE, mapping, GoogleSheetsClient(fixture.config(), "access-two"), Lease(),
                )
                try:
                    with self.subTest(mode=mode), self.assertRaises(ProviderFetchError) as failure:
                        fetch_bounded_records(adapter, resource_type="sheet")
                    self.assertEqual(failure.exception.category, category)
                finally:
                    adapter.close()
            GoogleFixtureHandler.mode = "timeout"
            client = GoogleSheetsClient(fixture.config(), "access-two")
            try:
                with patch("services.provider_http_transport.REQUEST_TIMEOUT_SECONDS", 0.01), \
                        self.assertRaises(GoogleSheetsError) as timed_out:
                    client.metadata(SPREADSHEET)
                self.assertEqual(timed_out.exception.code, "google_sheets_timeout")
            finally:
                client.close()


class GoogleSheetsAdapterTests(unittest.TestCase):
    def mapping(self):
        return {"spreadsheet_id": SPREADSHEET, "sheet_id": 5, "sheet_title": "Orders",
                "header_row": 1, "selected_columns": ["id", "name", "amount"],
                "record_id_column": "id", "resource_key": resource_key(SPREADSHEET, 5),
                "max_rows": 3, "max_columns": 3}

    def test_adapter_emits_stable_ids_snapshot_fingerprint_and_no_deletes(self):
        lease = Lease()
        adapter = GoogleSheetsAdapter(SOURCE, self.mapping(), FakeSheetsClient(), lease)
        batch = fetch_bounded_records(adapter, resource_type="sheet")
        self.assertEqual(batch.record_count, 2)
        self.assertTrue(batch.next_cursor.startswith("snapshot:"))
        self.assertTrue(all(change["operation"] == "upsert" for change in batch.changes))
        self.assertEqual([change["source_record_id"] for change in batch.changes], ["A", "B"])
        adapter.revalidate_credential()
        self.assertTrue(lease.validated)

    def test_adapter_propagates_the_bounded_run_deadline_to_every_sheet_read(self):
        class DeadlineClient(FakeSheetsClient):
            def __init__(self):
                super().__init__()
                self.deadlines = []

            def metadata(self, spreadsheet_id, *, deadline=None):
                self.deadlines.append(deadline)
                return super().metadata(spreadsheet_id, deadline=deadline)

            def values(self, spreadsheet_id, range_value, *, deadline=None):
                self.deadlines.append(deadline)
                return super().values(spreadsheet_id, range_value, deadline=deadline)

        client = DeadlineClient()
        adapter = GoogleSheetsAdapter(SOURCE, self.mapping(), client, Lease())
        with patch("services.data_source_api_provider.time.monotonic", return_value=100.0):
            fetch_bounded_records(adapter, resource_type="sheet", timeout_seconds=15)
        self.assertEqual(client.deadlines, [115.0, 115.0, 115.0])

    def test_blank_and_duplicate_business_ids_fail_closed(self):
        for rows in ([["", "No ID", 1]], [["A", "One", 1], ["A", "Again", 2]]):
            adapter = GoogleSheetsAdapter(
                SOURCE, self.mapping(), FakeSheetsClient(rows=rows), Lease(),
            )
            with self.subTest(rows=rows), self.assertRaises(ProviderFetchError):
                fetch_bounded_records(adapter, resource_type="sheet")

    def test_duplicate_business_ids_across_pages_fail_closed(self):
        class PagedClient(FakeSheetsClient):
            def __init__(self):
                super().__init__(tabs=[{"sheet_id": 5, "title": "Orders", "index": 0,
                                      "row_count": 1002, "column_count": 3}])

            def values(self, _spreadsheet_id, range_value, *, deadline=None):
                if range_value.endswith("!1:1"):
                    return [self.headers]
                if range_value.endswith("!2:1001"):
                    return [["A", "Alpha", 10]]
                return [["A", "Duplicate", 20]]

        mapping = {**self.mapping(), "max_rows": 1002}
        adapter = GoogleSheetsAdapter(SOURCE, mapping, PagedClient(), Lease())
        with self.assertRaises(ProviderFetchError):
            fetch_bounded_records(adapter, resource_type="sheet")

    def test_reordered_rows_keep_business_identifiers(self):
        adapter = GoogleSheetsAdapter(
            SOURCE, self.mapping(),
            FakeSheetsClient(rows=[["B", "Beta", 20], ["A", "Alpha", 10]]), Lease(),
        )
        batch = fetch_bounded_records(adapter, resource_type=self.mapping()["resource_key"])
        self.assertEqual([change["source_record_id"] for change in batch.changes], ["B", "A"])

    def test_unchanged_complete_snapshot_uses_noop_instead_of_new_changes(self):
        rows = [["A", "Alpha", 10], ["B", "Beta", 20]]
        hashes = {}
        for identifier, name, amount in rows:
            hashes[identifier] = hashlib.sha256(json.dumps({
                "operation": "upsert", "source_record_id": identifier,
                "payload": {"id": identifier, "name": name, "amount": amount},
            }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        adapter = GoogleSheetsAdapter(
            SOURCE, self.mapping(), FakeSheetsClient(rows=rows), Lease(),
            current_hashes=hashes, next_order=4,
        )
        with self.assertRaises(ProviderNoChanges) as outcome:
            fetch_bounded_records(adapter, resource_type="sheet")
        self.assertTrue(outcome.exception.next_cursor.startswith("snapshot:"))

    def test_snapshot_emits_insert_and_update_but_never_deletes_missing_records(self):
        def content_hash(identifier, name, amount):
            return hashlib.sha256(json.dumps({
                "operation": "upsert", "source_record_id": identifier,
                "payload": {"id": identifier, "name": name, "amount": amount},
            }, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

        adapter = GoogleSheetsAdapter(
            SOURCE, self.mapping(),
            FakeSheetsClient(rows=[["B", "Beta", 25], ["C", "New", 30]]), Lease(),
            current_hashes={"A": content_hash("A", "Alpha", 10),
                            "B": content_hash("B", "Beta", 20)},
            next_order=4,
        )
        batch = fetch_bounded_records(adapter, resource_type="sheet")
        self.assertEqual(
            [(change["source_record_id"], change["operation"])
             for change in batch.changes],
            [("B", "upsert"), ("C", "upsert")],
        )
        self.assertNotIn("A", [change["source_record_id"] for change in batch.changes])


if __name__ == "__main__":
    unittest.main()

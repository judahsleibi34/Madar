"""Loopback-only provider, object storage, and worker control for C3 browser E2E.

This process is deliberately test-only. It requires ``APP_ENV=test``, binds only
to loopback, accepts one synthetic provider credential, and invokes the real
automatic-sync/checkpoint services through a private random control token.
"""

from __future__ import annotations

import hmac
import json
import os
import signal
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlencode, urlsplit


if os.environ.get("APP_ENV") != "test":
    raise RuntimeError("The Data Sources browser fixture requires APP_ENV=test")

TENANT_ID = int(os.environ["MADAR_E2E_TENANT_ID"])
PROJECT_ID = os.environ["MADAR_E2E_PROJECT_ID"]
PROVIDER_TOKEN = os.environ["MADAR_E2E_PROVIDER_TOKEN"]
CONTROL_TOKEN = os.environ["MADAR_E2E_CONTROL_TOKEN"]
PROVIDER_PORT = int(os.environ["MADAR_E2E_PROVIDER_PORT"])
OBJECT_PORT = int(os.environ["MADAR_E2E_OBJECT_PORT"])
CONTROL_PORT = int(os.environ["MADAR_E2E_CONTROL_PORT"])


class JsonHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:
        return

    def json_response(self, status: int, payload: object) -> None:
        content = json.dumps(payload, separators=(",", ":"), default=str).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(content)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def body(self) -> dict:
        size = int(self.headers.get("content-length", "0"))
        if not size:
            return {}
        value = json.loads(self.rfile.read(size))
        return value if isinstance(value, dict) else {}


class ProviderHandler(JsonHandler):
    requests: list[dict] = []
    google_version = 1
    google_revoked = False

    def do_POST(self) -> None:
        if self.path != "/google/token":
            self.json_response(404, {"error": "not_found"})
            return
        size = int(self.headers.get("content-length", "0"))
        form = parse_qs(self.rfile.read(size).decode())
        type(self).requests.append({"path": self.path, "oauth_grant": form.get("grant_type", [""])[0]})
        if type(self).google_revoked and form.get("grant_type") == ["refresh_token"]:
            self.json_response(401, {"error": "invalid_grant"})
        elif form.get("grant_type") == ["authorization_code"]:
            self.json_response(200, {
                "access_token": "fixture-google-access", "refresh_token": "fixture-google-refresh",
                "scope": "https://www.googleapis.com/auth/spreadsheets.readonly", "expires_in": 3600,
            })
        elif form.get("grant_type") == ["refresh_token"]:
            self.json_response(200, {
                "access_token": "fixture-google-access",
                "scope": "https://www.googleapis.com/auth/spreadsheets.readonly", "expires_in": 3600,
            })
        else:
            self.json_response(400, {"error": "invalid_request"})

    def do_GET(self) -> None:
        if self.path == "/health":
            self.json_response(200, {"ready": True})
            return
        parsed = urlsplit(self.path)
        request_path = unquote(parsed.path)
        if request_path == "/google/authorize":
            query = parse_qs(parsed.query)
            location = query.get("redirect_uri", [""])[0]
            state = query.get("state", [""])[0]
            separator = "&" if "?" in location else "?"
            self.send_response(302)
            self.send_header("location", location + separator + urlencode({
                "state": state, "code": "fixture-authorization-code",
            }))
            self.send_header("content-length", "0")
            self.end_headers()
            return
        if request_path.startswith("/google/v4/"):
            type(self).requests.append({
                "path": request_path,
                "authorized": self.headers.get("authorization") == "Bearer fixture-google-access",
            })
            if self.headers.get("authorization") != "Bearer fixture-google-access":
                self.json_response(401, {"error": "invalid_token"})
                return
            spreadsheet = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
            if request_path == f"/google/v4/spreadsheets/{spreadsheet}":
                self.json_response(200, {
                    "spreadsheetId": spreadsheet, "properties": {"title": "Fixture business"},
                    "sheets": [{"properties": {"sheetId": 5, "title": "Orders", "index": 0,
                                "gridProperties": {"rowCount": 3, "columnCount": 3}}}],
                })
                return
            if request_path == f"/google/v4/spreadsheets/{spreadsheet}/values:batchGet":
                requested = parse_qs(parsed.query).get("ranges", [""])[0]
                if "1:1" in requested:
                    values = [["id", "name", "amount"]]
                elif "1:21" in requested:
                    values = [["id", "name", "amount"], ["A", "Alpha", 10], ["B", "Beta", 20]]
                elif type(self).google_version == 1:
                    values = [["A", "Alpha", 10], ["B", "Beta", 20]]
                else:
                    values = [["B", "Beta", 25], ["C", "New", 30]]
                self.json_response(200, {"valueRanges": [{"values": values}]})
                return
            self.json_response(404, {"error": "not_found"})
            return
        type(self).requests.append({
            "path": self.path,
            "authorized": self.headers.get("authorization") == f"Bearer {PROVIDER_TOKEN}",
        })
        if self.headers.get("authorization") != f"Bearer {PROVIDER_TOKEN}":
            self.json_response(401, {"error": "credential rejected"})
            return
        query = parse_qs(urlsplit(self.path).query)
        cursor = query.get("since", [None])[0]
        continuation = query.get("page_token", [None])[0]
        if cursor == "cursor-2":
            self.json_response(200, {
                "records": [
                    {"id": "C", "version": 2, "event_id": "event-C-2", "data": {"name": "C", "value": 35}},
                    {"id": "E", "version": 1, "event_id": "event-E-1", "data": {"name": "E", "value": 50}},
                    {"id": "D", "deleted": True, "version": 2, "event_id": "event-D-2"},
                ],
                "sync_cursor": "cursor-3",
            })
        elif cursor == "cursor-1":
            self.json_response(200, {
                "records": [
                    {"id": "B", "version": 2, "event_id": "event-B-2", "data": {"name": "B", "value": 25}},
                    {"id": "D", "version": 1, "event_id": "event-D-1", "data": {"name": "D", "value": 40}},
                    {"id": "A", "deleted": True, "version": 2, "event_id": "event-A-2"},
                ],
                "sync_cursor": "cursor-2",
            })
        elif cursor is None and continuation == "page-2":
            self.json_response(200, {
                "records": [{"id": "C", "version": 1, "event_id": "event-C-1", "data": {"name": "C", "value": 30}}],
                "sync_cursor": "cursor-1",
            })
        elif cursor is None:
            self.json_response(200, {
                "records": [
                    {"id": "A", "version": 1, "event_id": "event-A-1", "data": {"name": "A", "value": 10}},
                    {"id": "B", "version": 1, "event_id": "event-B-1", "data": {"name": "B", "value": 20}},
                ],
                "next_page_token": "page-2",
            })
        else:
            self.json_response(400, {"error": "unsupported fixture cursor"})


class ObjectHandler(BaseHTTPRequestHandler):
    objects: dict[str, bytes] = {}

    def log_message(self, *_args) -> None:
        return

    def reply(self, status: int, content: bytes = b"") -> None:
        self.send_response(status)
        self.send_header("content-length", str(len(content)))
        self.end_headers()
        if content and self.command != "HEAD":
            self.wfile.write(content)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.reply(200, b"ready")
            return
        content = type(self).objects.get(self.path)
        self.reply(404 if content is None else 200, content or b"")

    def do_PUT(self) -> None:
        if self.path in type(self).objects:
            self.reply(412)
            return
        size = int(self.headers.get("content-length", "0"))
        type(self).objects[self.path] = self.rfile.read(size)
        self.reply(201)

    def do_DELETE(self) -> None:
        type(self).objects.pop(self.path, None)
        self.reply(204)


def rows(response) -> list[dict]:
    data = getattr(response, "data", None)
    if isinstance(data, dict):
        return [data]
    return list(data or [])


class ControlHandler(JsonHandler):
    crashed_webhook_claims: dict[str, dict] = {}

    def authorized(self) -> bool:
        supplied = self.headers.get("x-madar-e2e-control", "")
        return bool(supplied) and hmac.compare_digest(supplied, CONTROL_TOKEN)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.json_response(200, {"ready": True})
            return
        if not self.authorized():
            self.json_response(404, {"detail": "Not Found"})
            return
        if self.path.startswith("/control/evidence"):
            self.json_response(200, self.evidence())
            return
        self.json_response(404, {"detail": "Not Found"})

    def do_POST(self) -> None:
        if not self.authorized():
            self.json_response(404, {"detail": "Not Found"})
            return
        payload = self.body()
        try:
            if self.path == "/control/sync":
                result = self.run_sync(payload)
            elif self.path == "/control/checkpoints":
                result = self.run_checkpoints()
            elif self.path == "/control/webhook-worker":
                result = self.run_worker_process("run_webhook_ingestion_worker.py", payload)
            elif self.path == "/control/checkpoint-worker":
                result = self.run_worker_process("run_dataset_checkpoint_worker.py", payload)
            elif self.path == "/control/report-worker":
                result = self.run_worker_process("run_bi_report_worker.py", payload)
            elif self.path == "/control/report-scheduler":
                result = self.run_report_scheduler(payload)
            elif self.path == "/control/crash-webhook-worker":
                result = self.crash_webhook_worker()
            elif self.path == "/control/expire-webhook-leases":
                result = self.expire_webhook_leases()
            elif self.path == "/control/recover-webhook-leases":
                result = self.recover_webhook_leases()
            elif self.path == "/control/stale-webhook-complete":
                result = self.stale_webhook_complete(payload)
            elif self.path == "/control/reconstruct-revision":
                result = self.reconstruct_revision(payload)
            elif self.path == "/control/schema-version":
                result = self.set_schema_version(payload)
            elif self.path == "/control/google-sheet":
                result = self.set_google_sheet(payload)
            else:
                self.json_response(404, {"detail": "Not Found"})
                return
            if PROVIDER_TOKEN in repr(result):
                raise RuntimeError("control response contained provider credential")
            self.json_response(200, result)
        except Exception as error:
            self.json_response(500, {"error": type(error).__name__})

    @staticmethod
    def source_id(payload: dict) -> str:
        value = str(payload.get("source_id") or "")
        if not value:
            raise ValueError("source_id is required")
        return value

    def run_sync(self, payload: dict) -> dict:
        from database import service_supabase as database

        source_id = self.source_id(payload)
        source = rows(database.table("data_sources").select("id").eq(
            "tenant_id", TENANT_ID
        ).eq("project_id", PROJECT_ID).eq("id", source_id).limit(1).execute())
        if not source:
            raise ValueError("source is outside the fixture scope")
        if payload.get("force_due"):
            database.table("data_source_sync_schedules").update({
                "next_due_at": "2000-01-01T00:00:00Z",
            }).eq("tenant_id", TENANT_ID).eq("project_id", PROJECT_ID).eq(
                "source_id", source_id
            ).execute()
        # Pandas/Arrow ingestion is not thread-safe in this image when invoked from
        # ThreadingHTTPServer. Run the repository's real bounded worker in its own
        # process, which also matches the deployed execution boundary.
        worker = self.run_worker_process("run_automatic_source_sync.py", {"limit": 5})
        outcomes = worker.get("results", [])
        return {
            "process": worker["process"],
            "claimed": int(worker.get("claimed", 0)),
            "outcomes": [{
                key: value for key, value in outcome.items()
                if key in {"outcome", "dataset_id", "version_id", "committed_revision",
                           "credential_attention", "failure_code", "error_category", "no_changes"}
            } for outcome in outcomes],
        }

    def run_checkpoints(self) -> dict:
        worker = self.run_worker_process("run_dataset_checkpoint_worker.py", {"limit": 20})
        outcomes = worker.get("results", [])
        return {
            "process": worker["process"],
            "claimed": int(worker.get("claimed", 0)),
            "outcomes": [{key: value for key, value in item.items() if key in {"outcome", "target_revision", "version_id"}}
                         for item in outcomes],
        }

    def run_report_scheduler(self, payload: dict) -> dict:
        from database import service_supabase as database

        if payload.get("force_due"):
            database.table("bi_report_schedules").update({
                "next_run_at": "2000-01-01T00:00:00Z",
            }).eq("tenant_id", TENANT_ID).eq("project_id", PROJECT_ID).execute()
        return self.run_worker_process("run_bi_report_scheduler.py", payload)

    @staticmethod
    def run_worker_process(script: str, payload: dict) -> dict:
        limit = max(1, min(int(payload.get("limit", 20)), 50))
        command = [sys.executable, f"/app/scripts/{script}", "--limit", str(limit)]
        completed = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=180,
            env=dict(os.environ),
        )
        if completed.returncode != 0:
            raise RuntimeError(f"worker_process_failed:{script}:{completed.returncode}")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError(f"worker_process_empty:{script}")
        result = json.loads(lines[-1])
        if not isinstance(result, dict):
            raise RuntimeError(f"worker_process_invalid:{script}")
        outcomes = result.get("results")
        if isinstance(outcomes, list) and any(item.get("outcome") == "failed" or item.get("status") in {"failed", "retry_pending"} for item in outcomes if isinstance(item, dict)):
            diagnostic = [{key: item.get(key) for key in ("outcome", "status", "failure_code", "error_category", "error_code", "exception_type", "test_diagnostic")}
                          for item in outcomes if isinstance(item, dict)]
            print(f"e2e_worker_failure:{script}:{json.dumps(diagnostic, sort_keys=True)}", file=sys.stderr, flush=True)
        return {"process": script, **result}

    @classmethod
    def crash_webhook_worker(cls) -> dict:
        """Claim in a real child process, then let that process exit without committing."""
        program = (
            "import json; "
            "from services.webhook_ingestion_service import claim_events; "
            "items=claim_events(worker_id='browser-e2e-crash',limit=1,lease_seconds=60); "
            "print(json.dumps(items[0] if items else {},default=str))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", program], check=False, capture_output=True,
            text=True, timeout=60, env=dict(os.environ),
        )
        if completed.returncode != 0:
            raise RuntimeError(f"crash_worker_failed:{completed.returncode}")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        claim = json.loads(lines[-1]) if lines else {}
        if not claim:
            return {"claimed": 0, "child_exited": True}
        cls.crashed_webhook_claims[str(claim["id"])] = claim
        return {
            "claimed": 1, "event_id": claim["id"],
            "lease_fence": int(claim["lease_fence"]), "child_exited": True,
        }

    @staticmethod
    def expire_webhook_leases() -> dict:
        from database import service_supabase as database

        response = database.table("data_source_webhook_events").update({
            "lease_expires_at": "2000-01-01T00:00:00Z",
        }).eq("tenant_id", TENANT_ID).eq("status", "leased").execute()
        return {"expired": len(rows(response))}

    @staticmethod
    def recover_webhook_leases() -> dict:
        from database import service_supabase as database
        from services import webhook_ingestion_service

        expired = ControlHandler.expire_webhook_leases()["expired"]
        reconciled = webhook_ingestion_service.reconcile_expired(limit=100, client=database)
        due = database.table("data_source_webhook_events").update({
            "next_attempt_at": "2000-01-01T00:00:00Z",
        }).eq("tenant_id", TENANT_ID).eq("status", "retry").execute()
        return {"expired": expired, "reconciled": reconciled, "retry_due": len(rows(due))}

    @classmethod
    def stale_webhook_complete(cls, payload: dict) -> dict:
        from database import service_supabase as database

        event_id = str(payload.get("event_id") or "")
        claim = cls.crashed_webhook_claims.get(event_id)
        if not claim:
            raise ValueError("unknown crashed webhook claim")
        result = database.rpc("complete_data_source_webhook_event162", {
            "p_event_id": claim["id"], "p_lease_token": claim["lease_token"],
            "p_lease_fence": int(claim["lease_fence"]), "p_result_revision": 999999,
        }).execute()
        return {"event_id": event_id, "completed": getattr(result, "data", None) is True}

    @staticmethod
    def reconstruct_revision(payload: dict) -> dict:
        from database import service_supabase as database
        from services import project_dataset_checkpoint_service as checkpoints

        source_id = ControlHandler.source_id(payload)
        sources = rows(database.table("data_sources").select("creator_user_id").eq(
            "tenant_id", TENANT_ID
        ).eq("project_id", PROJECT_ID).eq("id", source_id).limit(1).execute())
        resources = rows(database.table("data_source_resources").select(
            "id,dataset_id"
        ).eq("tenant_id", TENANT_ID).eq("project_id", PROJECT_ID).eq(
            "source_id", source_id
        ).limit(1).execute())
        if not sources or not resources or not resources[0].get("dataset_id"):
            raise ValueError("source dataset is unavailable")
        item = resources[0]
        reconstruction = checkpoints.reconstruct_dataset_revision(
            tenant_id=TENANT_ID, project_id=PROJECT_ID, source_id=source_id,
            resource_id=item["id"], dataset_id=item["dataset_id"],
            user_id=int(sources[0]["creator_user_id"]),
            target_revision=int(payload.get("target_revision")), client=database,
        )
        try:
            return {
                "target_revision": int(payload.get("target_revision")),
                "record_count": int(reconstruction["record_count"]),
                "change_count": int(reconstruction["change_count"]),
                "state_hash": reconstruction["state_hash"],
                "immutable_bytes_read": int(reconstruction["immutable_bytes_read"]),
            }
        finally:
            reconstruction.cleanup()

    @staticmethod
    def set_schema_version(payload: dict) -> dict:
        from database import service_supabase as database

        version = int(payload.get("schema_version"))
        if version not in {141, 161, 162}:
            raise ValueError("unsupported compatibility fixture schema")
        database.table("application_schema_state").update({
            "schema_version": version,
        }).eq("contract_key", "core").execute()
        return {"schema_version": version}

    @staticmethod
    def set_google_sheet(payload: dict) -> dict:
        ProviderHandler.google_version = int(payload.get("version", ProviderHandler.google_version))
        ProviderHandler.google_revoked = bool(payload.get("revoked", False))
        if ProviderHandler.google_version not in {1, 2}:
            raise ValueError("unsupported Google fixture version")
        return {"version": ProviderHandler.google_version, "revoked": ProviderHandler.google_revoked}

    @staticmethod
    def evidence() -> dict:
        from database import service_supabase as database

        schema_version = int(database.table("application_schema_state").select(
            "schema_version"
        ).eq("contract_key", "core").single().execute().data.get("schema_version", 0))
        sources = rows(database.table("data_sources").select(
            "id,provider_key,resource_type,credential_revision,status"
        ).eq("tenant_id", TENANT_ID).eq("project_id", PROJECT_ID).execute())
        source_ids = [item["id"] for item in sources]
        resource_columns = (
            "id,source_id,resource_key,dataset_id,committed_revision,committed_cursor,"
            "latest_checkpoint_version_id"
        )
        if schema_version >= 162:
            resource_columns += ",reconciliation_requested_at,reconciliation_reason"
        resources = rows(database.table("data_source_resources").select(
            resource_columns
        ).eq("tenant_id", TENANT_ID).eq("project_id", PROJECT_ID).execute())
        dataset_ids = [item["dataset_id"] for item in resources if item.get("dataset_id")]
        versions = []
        current_records = []
        checkpoints = []
        for dataset_id in dataset_ids:
            versions.extend(rows(database.table("data_dataset_versions").select(
                "id,dataset_id,version_number,version_kind,provenance,created_at"
            ).eq("tenant_id", TENANT_ID).eq("dataset_id", dataset_id).order("version_number").execute()))
            current_records.extend(rows(database.table("data_dataset_current_records").select(
                "dataset_id,source_record_id,is_deleted,payload,source_order,last_committed_revision"
            ).eq("tenant_id", TENANT_ID).eq("dataset_id", dataset_id).order("source_record_id").execute()))
            checkpoints.extend(rows(database.table("data_dataset_checkpoints").select(
                "dataset_id,target_revision,status,failure_code,version_id"
            ).eq("tenant_id", TENANT_ID).eq("dataset_id", dataset_id).order("target_revision").execute()))
        schedules = []
        attempts = []
        for source_id in source_ids:
            schedules.extend(rows(database.table("data_source_sync_schedules").select(
                "source_id,source_resource_id,enabled,interval_seconds,status,last_success_at,next_due_at,retry_count,last_error_category,fence"
            ).eq("tenant_id", TENANT_ID).eq("project_id", PROJECT_ID).eq("source_id", source_id).execute()))
            attempts.extend(rows(database.table("data_source_sync_attempts").select(
                "source_id,source_resource_id,fence,status,error_category,credential_revision"
            ).eq("tenant_id", TENANT_ID).eq("project_id", PROJECT_ID).eq("source_id", source_id).order("fence").execute()))
        result = {
            "sources": sources,
            "resources": resources,
            "versions": versions,
            "current_records": current_records,
            "checkpoints": checkpoints,
            "schedules": schedules,
            "attempts": attempts,
            "provider_requests": list(ProviderHandler.requests),
            "google_mappings": rows(database.table("google_sheets_source_mappings").select(
                "source_id,spreadsheet_id,sheet_id,sheet_title,record_id_column,resource_key,mapping_revision"
            ).eq("tenant_id", TENANT_ID).eq("project_id", PROJECT_ID).execute()),
            "object_count": len(ObjectHandler.objects),
        }
        if schema_version >= 162:
            result["webhook_endpoints"] = rows(database.table(
                "data_source_webhook_endpoints"
            ).select(
                "id,source_id,source_resource_id,status,fence,last_received_at,last_processed_at"
            ).eq("tenant_id", TENANT_ID).eq("project_id", PROJECT_ID).execute())
            result["webhook_events"] = rows(database.table(
                "data_source_webhook_events"
            ).select(
                "id,source_id,source_resource_id,provider_event_id,event_type,delivery_kind,status,attempts,error_category,result_revision,ingestion_run_id"
            ).eq("tenant_id", TENANT_ID).eq("project_id", PROJECT_ID).order(
                "received_at"
            ).execute())
        if PROVIDER_TOKEN in repr(result):
            raise RuntimeError("evidence contained provider credential")
        return result


def serve(server: ThreadingHTTPServer) -> None:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()


def main() -> None:
    servers = [
        ThreadingHTTPServer(("127.0.0.1", PROVIDER_PORT), ProviderHandler),
        ThreadingHTTPServer(("127.0.0.1", OBJECT_PORT), ObjectHandler),
        ThreadingHTTPServer(("127.0.0.1", CONTROL_PORT), ControlHandler),
    ]
    for server in servers:
        serve(server)
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_args: stopped.set())
    signal.signal(signal.SIGINT, lambda *_args: stopped.set())
    stopped.wait()
    for server in servers:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()

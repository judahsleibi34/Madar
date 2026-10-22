"""Loopback-only provider, object storage, and worker control for C3 browser E2E.

This process is deliberately test-only. It requires ``APP_ENV=test``, binds only
to loopback, accepts one synthetic provider credential, and invokes the real
automatic-sync/checkpoint services through a private random control token.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


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

    def do_GET(self) -> None:
        if self.path == "/health":
            self.json_response(200, {"ready": True})
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
            elif self.path == "/control/schema-version":
                result = self.set_schema_version(payload)
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
        from services import automatic_source_sync_service as scheduler

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
        claims = scheduler.claim_due_syncs(worker_id="browser-e2e", limit=5, client=database)
        outcomes = [asyncio.run(scheduler.execute_claim(claim, client=database)) for claim in claims]
        return {
            "claimed": len(claims),
            "outcomes": [{
                key: value for key, value in outcome.items()
                if key in {"outcome", "dataset_id", "version_id", "committed_revision", "credential_attention", "failure_code"}
            } for outcome in outcomes],
        }

    def run_checkpoints(self) -> dict:
        from database import service_supabase as database
        from services import project_dataset_checkpoint_service as checkpoints

        claimed = checkpoints.claim_dataset_checkpoints(
            worker_id="browser-e2e-checkpoint", limit=20, client=database,
        )
        outcomes = [
            asyncio.run(checkpoints.materialize_claimed_checkpoint(item, client=database))
            for item in claimed
        ]
        return {
            "claimed": len(claimed),
            "outcomes": [{key: value for key, value in item.items() if key in {"outcome", "target_revision", "version_id"}}
                         for item in outcomes],
        }

    @staticmethod
    def set_schema_version(payload: dict) -> dict:
        from database import service_supabase as database

        version = int(payload.get("schema_version"))
        if version not in {141, 156}:
            raise ValueError("unsupported compatibility fixture schema")
        database.table("application_schema_state").update({
            "schema_version": version,
        }).eq("contract_key", "core").execute()
        return {"schema_version": version}

    @staticmethod
    def evidence() -> dict:
        from database import service_supabase as database

        sources = rows(database.table("data_sources").select(
            "id,provider_key,resource_type,credential_revision,status"
        ).eq("tenant_id", TENANT_ID).eq("project_id", PROJECT_ID).execute())
        source_ids = [item["id"] for item in sources]
        resources = rows(database.table("data_source_resources").select(
            "id,source_id,resource_key,dataset_id,committed_revision,committed_cursor,latest_checkpoint_version_id"
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
                "dataset_id,source_record_id,is_deleted,payload,last_committed_revision"
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
            "object_count": len(ObjectHandler.objects),
        }
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

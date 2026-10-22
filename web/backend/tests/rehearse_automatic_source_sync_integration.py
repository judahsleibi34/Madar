"""Combined disposable Vault/PostgREST/HTTP/incremental-sync proof for C3."""

from __future__ import annotations

import asyncio
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from services import automatic_source_sync_service as scheduler
from services import project_dataset_checkpoint_service as checkpoints
from services import project_source_ingestion_service as source_ingestions
from services.data_source_credential_service import (
    DataSourceCredentialError, provision_credential, revoke_credential,
    resolve_persistent_credential,
)
from test_provider_http_transport import LocalFixture, TOKEN


TENANT = 7001
USER = 7001
PROJECT = "70000000-0000-4000-8000-000000000002"
SOURCE = "70000000-0000-4000-8000-000000000003"
RESOURCE = "70000000-0000-4000-8000-000000000004"


def check(value, message):
    if not value:
        raise AssertionError(message)


class ObjectHandler(BaseHTTPRequestHandler):
    objects: dict[str, bytes] = {}

    def log_message(self, *_args):
        return

    def _reply(self, status: int, content: bytes = b"") -> None:
        self.send_response(status)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        if content:
            self.wfile.write(content)

    def do_PUT(self):
        if self.path in type(self).objects:
            self._reply(412)
            return
        size = int(self.headers.get("Content-Length", "0"))
        type(self).objects[self.path] = self.rfile.read(size)
        self._reply(201)

    def do_GET(self):
        content = type(self).objects.get(self.path)
        self._reply(404 if content is None else 200, content or b"")

    def do_DELETE(self):
        type(self).objects.pop(self.path, None)
        self._reply(204)


class LocalObjectFixture:
    def __enter__(self):
        ObjectHandler.objects = {}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ObjectHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def due(database):
    database.table("data_source_sync_schedules").update({
        "next_due_at": "2000-01-01T00:00:00Z",
    }).eq("source_resource_id", RESOURCE).execute()


def main():
    from database import service_supabase as database

    provisioned = provision_credential(
        tenant_id=TENANT, project_id=PROJECT, source_id=SOURCE, user_id=USER,
        provider_key="http_fixture", credential_type="bearer", secret=TOKEN,
        client=database,
    )
    check("ciphertext" not in provisioned, "credential response leaked ciphertext")
    schedule = scheduler.configure_schedule(
        tenant_id=TENANT, project_id=PROJECT, source_id=SOURCE, resource_id=RESOURCE,
        user_id=USER, enabled=True, interval_seconds=900, client=database,
    )
    check(schedule["enabled"], "schedule was not enabled")

    with LocalFixture() as fixture, LocalObjectFixture() as object_fixture:
        os.environ["MADAR_TEST_HTTP_PROVIDER_URL"] = fixture.base_url
        os.environ["DATA_IMMUTABLE_STORAGE_BACKEND"] = "test_http"
        os.environ["DATA_IMMUTABLE_TEST_URL"] = object_fixture.base_url
        first_claim = scheduler.claim_due_syncs(
            worker_id="combined:first", limit=1, client=database,
        )[0]
        first = asyncio.run(scheduler.execute_claim(first_claim, client=database))
        check(first["outcome"] == "succeeded" and first["committed_revision"] == 1,
              f"first automatic synchronization did not commit: {first!r}")
        first_cursor = database.table("data_source_resources").select(
            "committed_cursor"
        ).eq("id", RESOURCE).single().execute().data["committed_cursor"]
        check(first_cursor == "cursor-1", "first cursor did not advance")
        due(database)
        second_claim = scheduler.claim_due_syncs(
            worker_id="combined:second", limit=1, client=database,
        )[0]
        second = asyncio.run(scheduler.execute_claim(second_claim, client=database))
        check(second["outcome"] == "succeeded" and second["committed_revision"] == 2,
              f"second automatic synchronization did not commit: {second!r}")
        check(first["dataset_id"] == second["dataset_id"],
              "logical dataset identity changed")
        second_cursor = database.table("data_source_resources").select(
            "committed_cursor"
        ).eq("id", RESOURCE).single().execute().data["committed_cursor"]
        check(second_cursor == "cursor-2", "second cursor did not advance")

        claimed = checkpoints.claim_dataset_checkpoints(
            worker_id="combined:checkpoint", limit=5, client=database,
        )
        check(len(claimed) == 2, "scheduled commits did not create checkpoints")
        checkpoint_results = [
            asyncio.run(checkpoints.materialize_claimed_checkpoint(item, client=database))
            for item in claimed
        ]
        check(all(item["outcome"] == "ready" for item in checkpoint_results),
              "checkpoint materialization did not complete")

        overview = source_ingestions.list_source_resource_statuses(
            tenant_id=TENANT, project_id=PROJECT, source_id=SOURCE,
            user_id=USER, client=database,
        )
        check(overview["available"] and overview["provider_registered"],
              "source management capabilities were not projected")
        check(len(overview["items"]) == 1, "source management resource was not isolated")
        managed_resource = overview["items"][0]
        check(managed_resource["committed_revision"] == 2,
              "source management committed revision is stale")
        check(managed_resource["latest_checkpoint"]["status"] == "ready"
              and managed_resource["latest_checkpoint"]["target_revision"] == 2,
              "source management checkpoint freshness is stale")

        current = database.table("data_dataset_current_records").select(
            "source_record_id,is_deleted,payload,last_committed_revision"
        ).eq("tenant_id", TENANT).eq(
            "dataset_id", second["dataset_id"]
        ).order("source_record_id").execute().data
        states = {item["source_record_id"]: item for item in current}
        check(states["A"]["is_deleted"] and states["B"]["payload"]["value"] == 25
              and states["D"]["payload"]["value"] == 40,
              "insert/update/delete projection is incorrect")

        revoked = revoke_credential(
            tenant_id=TENANT, project_id=PROJECT, source_id=SOURCE, user_id=USER,
            provider_key="http_fixture", expected_revision=1, client=database,
        )
        check(revoked["status"] == "revoked", "credential was not revoked")
        due(database)
        revoked_claim = scheduler.claim_due_syncs(
            worker_id="combined:revoked", limit=1, client=database,
        )[0]
        result = __import__("asyncio").run(scheduler.execute_claim(
            revoked_claim, client=database,
        ))
        check(result["credential_attention"] and result["outcome"] == "failed",
              f"revoked credential did not fail closed: {result!r}")
        try:
            resolve_persistent_credential(
                tenant_id=TENANT, project_id=PROJECT, source_id=SOURCE, user_id=USER,
                provider_key="http_fixture", client=database,
            )
        except DataSourceCredentialError:
            pass
        else:
            raise AssertionError("revoked credential resolved")

    schedule_row = database.table("data_source_sync_schedules").select(
        "status,last_success_at,retry_count,last_error_category,diagnostic_metadata"
    ).eq("source_resource_id", RESOURCE).single().execute().data
    check(schedule_row["status"] == "credential_attention",
          "credential-attention schedule state missing")
    check(TOKEN not in repr(schedule_row), "schedule state leaked credential")
    print("automatic_source_sync_combined_integration_passed")


if __name__ == "__main__":
    main()

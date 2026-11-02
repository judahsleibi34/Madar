"""Opt-in real-socket HTTP verification for C5 Step 10 Phase 3B."""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI, HTTPException, Request
import httpx
import psutil
import uvicorn

from data_analysis import services as data_services
from data_analysis.routes import data_routes
from services import (
    bi_dashboard_service,
    bi_report_export_service,
    bi_reporting_service,
    project_dataset_service,
    request_body_limits,
    versioned_analytics_service,
)
from services.request_body_limits import RequestBodyLimitMiddleware
from services.storage_quota_service import StorageSafetyError


PROJECT = "71111111-1111-4111-8111-111111111111"
CROSS_PROJECT = "71111111-1111-4111-8111-111111111112"
DATASET = "72222222-2222-4222-8222-222222222222"
VERSION = "73333333-3333-4333-8333-333333333333"
DASHBOARD = "74444444-4444-4444-8444-444444444444"
WIDGET = "75555555-5555-4555-8555-555555555555"
RUN = "76666666-6666-4666-8666-666666666666"
OWNER_TOKEN = "phase3-owner-token"
CROSS_TOKEN = "phase3-cross-token"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _tree_bytes(root: Path) -> int:
    total = 0
    for item in root.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            # Upload cancellation can remove a partial between discovery and stat.
            continue
    return total


class SlowFile:
    def __init__(self, path: Path, started: threading.Event):
        self._file = path.open("rb")
        self._started = started

    def read(self, size=-1):
        self._started.set()
        time.sleep(0.025)
        return self._file.read(size)

    def seek(self, *args):
        return self._file.seek(*args)

    def tell(self):
        return self._file.tell()

    def close(self):
        self._file.close()


@unittest.skipUnless(
    os.getenv("MADAR_RUN_250MB_HTTP_INTEGRATION") == "1",
    "Set MADAR_RUN_250MB_HTTP_INTEGRATION=1 and MADAR_PHASE3_DATASET_PATH.",
)
class Phase3HttpIntegrationTests(unittest.TestCase):
    def test_real_authenticated_http_upload_and_failure_boundaries(self):
        source = Path(os.environ["MADAR_PHASE3_DATASET_PATH"]).resolve()
        self.assertGreater(source.stat().st_size, 240_000_000)
        self.assertLessEqual(source.stat().st_size, 250_000_000)
        expected_hash = data_services.sha256_file(source)
        state = {
            "artifact": None, "disk_fail": False, "reservations": 0,
            "storage_objects": 0, "report": None,
        }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            uploads = root / "private"
            exports = root / "exports"
            uploads.mkdir()
            port = _free_port()

            def auth_context(request: Request) -> tuple[int, int]:
                token = request.headers.get("authorization", "").removeprefix("Bearer ")
                if token == OWNER_TOKEN:
                    return 3, 7
                if token == CROSS_TOKEN:
                    return 4, 8
                raise HTTPException(status_code=401, detail="Not authenticated")

            async def authenticated(request: Request):
                auth_context(request)

            def storage_scope(request, _response, user_id):
                tenant_id, scoped_user_id = auth_context(request)
                if int(user_id) != scoped_user_id:
                    raise HTTPException(status_code=403, detail="User scope mismatch")
                return str(tenant_id), str(scoped_user_id)

            def require_project(project_id, *, tenant_id, **_kwargs):
                if project_id != PROJECT or int(tenant_id) != 3:
                    raise HTTPException(status_code=404, detail="Data project was not found.")
                return {"id": PROJECT, "tenant_id": 3}

            def ensure_disk(path, *, incoming_bytes=0):
                if state["disk_fail"]:
                    state["disk_fail"] = False
                    raise StorageSafetyError("storage_disk_floor_breached")
                return shutil.disk_usage(path).free

            def reserve_storage(**_kwargs):
                state["reservations"] += 1
                return f"reservation-{state['reservations']}"

            def finish_storage(**_kwargs):
                state["storage_objects"] += 1
                return f"object-{state['storage_objects']}"

            def persist(artifact):
                state["artifact"] = dict(artifact)
                return {
                    "persistent_dataset_id": DATASET,
                    "dataset_version_id": VERSION,
                    "dataset_version_number": 1,
                    "content_hash": artifact["sha256"],
                    "project_id": PROJECT,
                }

            def resolve_version(*, tenant_id, project_id, user_id, dataset_id, version_id, **_kwargs):
                if (int(tenant_id), project_id, int(user_id), dataset_id, version_id) != (
                    3, PROJECT, 7, DATASET, VERSION,
                ) or not state["artifact"]:
                    raise HTTPException(status_code=404, detail="Dataset version was not found.")
                artifact = state["artifact"]
                response = artifact["response"]
                return {
                    "storage_identifier": artifact["storage_key"].split("/", 2)[-1],
                    "dataset": {"id": DATASET, "project_id": PROJECT,
                                "display_name": "HTTP boundary.csv"},
                    "version": {
                        "id": VERSION, "version_number": 1, "version_kind": "source",
                        "content_hash": artifact["sha256"], "size_bytes": artifact["file_size"],
                        "file_metadata": response,
                    },
                }

            dashboard = {
                "id": DASHBOARD, "revision": 1, "creator_user_id": 7,
                "access": {"can_edit": True},
                "widgets": [{
                    "id": WIDGET, "widget_type": "kpi", "title": "Rows",
                    "dataset_id": DATASET, "dataset_version_id": VERSION,
                    "version_policy": "pinned", "analysis_spec": {"operation": "count"},
                    "layout_config": {}, "display_options": {},
                }],
            }

            def get_dashboard(**kwargs):
                if int(kwargs["tenant_id"]) != 3 or int(kwargs["user_id"]) != 7 \
                        or kwargs["project_id"] != PROJECT or kwargs["dashboard_id"] != DASHBOARD:
                    raise HTTPException(status_code=404, detail="Dashboard was not found.")
                return dashboard

            def enqueue_report(**_kwargs):
                run = {
                    "id": RUN, "tenant_id": 3, "project_id": PROJECT,
                    "creator_user_id": 7,
                    "definition_snapshot": {
                        "dashboard": {"name": "HTTP boundary"}, "report_policy": {},
                        "widgets": [{"id": WIDGET, "title": "Rows",
                                     "analysis_spec": {"operation": "count"}}],
                    },
                    "version_vector": [{
                        "widget_id": WIDGET, "dataset_id": DATASET,
                        "dataset_version_id": VERSION, "version_number": 1,
                        "content_hash": expected_hash, "version_policy": "pinned",
                    }],
                }
                status, snapshot, warnings, artifact = bi_reporting_service.execute_run(
                    run, client=object(),
                )
                state["report"] = {
                    **run, "status": status, "completed_at": "2026-10-28T12:00:00Z",
                    "warnings": warnings, "result_snapshot": snapshot,
                    "artifact": artifact,
                }
                return {"id": RUN, "status": status}

            def get_report(**kwargs):
                if int(kwargs["tenant_id"]) != 3 or int(kwargs["user_id"]) != 7 \
                        or kwargs["project_id"] != PROJECT or kwargs["report_id"] != RUN \
                        or state["report"] is None:
                    raise HTTPException(status_code=404, detail="Report was not found.")
                return state["report"]

            def export_report(**kwargs):
                report = get_report(**{key: kwargs[key] for key in (
                    "tenant_id", "project_id", "user_id", "report_id",
                )})
                return bi_report_export_service.write_export(
                    report=report, tenant_id=3, root=exports,
                    export_format=kwargs["export_format"], language=kwargs["language"],
                )

            app = FastAPI()
            app.add_middleware(RequestBodyLimitMiddleware)
            app.include_router(data_routes.router, dependencies=[Depends(authenticated)])

            @app.get("/__phase3/health")
            def health():
                return {"ok": True}

            server = uvicorn.Server(uvicorn.Config(
                app, host="127.0.0.1", port=port, log_level="error", access_log=False,
            ))
            thread = threading.Thread(target=server.run, daemon=True)

            patches = ExitStack()
            patches.enter_context(patch.dict(os.environ, {
                "DATA_UPLOAD_DIR": str(uploads),
                "PARSER_ISOLATED_WORKER_ENABLED": "false",
                "MAX_CONCURRENT_DATASET_UPLOADS": "2",
            }, clear=False))
            patches.enter_context(patch.object(data_routes, "get_storage_scope", storage_scope))
            patches.enter_context(patch.object(data_routes, "enforce_data_workspace_rate_limit"))
            patches.enter_context(patch.object(data_routes, "require_entitlement"))
            patches.enter_context(patch.object(project_dataset_service, "require_project_datasets_schema"))
            patches.enter_context(patch.object(project_dataset_service, "require_data_project", side_effect=require_project))
            patches.enter_context(patch.object(project_dataset_service, "create_initial_dataset_version", side_effect=lambda **kwargs: persist(kwargs["artifact"])))
            patches.enter_context(patch.object(project_dataset_service, "resolve_project_dataset_version", side_effect=resolve_version))
            patches.enter_context(patch.object(project_dataset_service, "get_project_dataset_freshness", return_value={"available": True, "resource": {}, "checkpoint": None}))
            patches.enter_context(patch.object(data_services, "ensure_disk_capacity", side_effect=ensure_disk))
            patches.enter_context(patch.object(request_body_limits, "ensure_disk_capacity", side_effect=ensure_disk))
            patches.enter_context(patch.object(data_services, "reserve_storage", side_effect=reserve_storage))
            patches.enter_context(patch.object(data_services, "finish_storage", side_effect=finish_storage))
            patches.enter_context(patch.object(bi_dashboard_service, "get_dashboard", side_effect=get_dashboard))
            patches.enter_context(patch.object(bi_reporting_service, "enqueue_report", side_effect=enqueue_report))
            patches.enter_context(patch.object(bi_reporting_service, "get_report", side_effect=get_report))
            patches.enter_context(patch.object(bi_reporting_service, "report_export_artifact", side_effect=export_report))
            patches.enter_context(patch.object(bi_reporting_service, "_write_csv_artifact", return_value={"storage_key": "snapshot.csv", "filename": "snapshot.csv"}))

            process = psutil.Process()
            monitor_stop = threading.Event()
            initial_tmp_free = shutil.disk_usage(tempfile.gettempdir()).free
            measurements = {
                "peak_rss": process.memory_info().rss,
                "minimum_tmp_free": initial_tmp_free,
                "peak_private_bytes": 0,
            }

            def monitor():
                while not monitor_stop.wait(0.02):
                    measurements["peak_rss"] = max(
                        measurements["peak_rss"], process.memory_info().rss,
                    )
                    measurements["minimum_tmp_free"] = min(
                        measurements["minimum_tmp_free"],
                        shutil.disk_usage(tempfile.gettempdir()).free,
                    )
                    measurements["peak_private_bytes"] = max(
                        measurements["peak_private_bytes"], _tree_bytes(uploads),
                    )

            monitor_thread = threading.Thread(target=monitor, daemon=True)
            try:
                thread.start()
                deadline = time.monotonic() + 10
                base = f"http://127.0.0.1:{port}"
                while time.monotonic() < deadline:
                    try:
                        if httpx.get(f"{base}/__phase3/health", timeout=0.25).status_code == 200:
                            break
                    except httpx.HTTPError:
                        time.sleep(0.05)
                else:
                    self.fail("Uvicorn did not become ready")
                monitor_thread.start()
                headers = {"Authorization": f"Bearer {OWNER_TOKEN}"}
                upload_url = f"{base}/users/7/data/projects/{PROJECT}/datasets/upload"

                started = time.monotonic()
                with source.open("rb") as payload, httpx.Client(timeout=None) as client:
                    response = client.post(
                        upload_url, headers=headers,
                        files={"file": ("boundary.csv", payload, "text/csv")},
                    )
                upload_seconds = time.monotonic() - started
                self.assertEqual(response.status_code, 201, response.text[:500])
                body = response.json()
                self.assertEqual(body["persistent_dataset_id"], DATASET)
                self.assertEqual(body["dataset_version_id"], VERSION)
                self.assertEqual(body["rows"], 5_300_000)
                self.assertEqual(state["artifact"]["sha256"], expected_hash)
                stored = uploads / "tenant_3" / "user_7" / body["dataset_id"]
                self.assertEqual(stored.stat().st_size, source.stat().st_size)
                self.assertEqual(data_services.sha256_file(stored), expected_hash)

                cross = httpx.post(
                    f"{base}/users/8/data/projects/{PROJECT}/datasets/upload",
                    headers={"Authorization": f"Bearer {CROSS_TOKEN}"},
                    files={"file": ("cross.csv", b"a,b\n1,2\n", "text/csv")}, timeout=10,
                )
                self.assertEqual(cross.status_code, 404)

                explore = httpx.post(
                    f"{base}/users/7/data/projects/{PROJECT}/datasets/{DATASET}/versions/{VERSION}/explore",
                    headers=headers, json={
                        "columns": ["row_id", "group_key", "amount"],
                        "filters": [{"field": "group_key", "operator": "eq", "value": "g099"}],
                        "sort": [{"field": "amount", "direction": "desc"}],
                        "limit": 100, "offset": 0,
                    }, timeout=20,
                )
                self.assertEqual(explore.status_code, 200, explore.text[:500])
                self.assertEqual(explore.json()["pagination"]["total"], 53_000)
                parquet_artifacts = list((uploads / ".parquet_cache").rglob("*.parquet"))
                self.assertEqual(len(parquet_artifacts), 1)
                parquet_manifest = json.loads(
                    parquet_artifacts[0].with_suffix(".json").read_text(encoding="utf-8")
                )
                self.assertEqual(parquet_manifest["source_sha256"], expected_hash)
                self.assertEqual(parquet_manifest["dataset_version_id"], VERSION)

                dashboard_response = httpx.post(
                    f"{base}/users/7/data/projects/{PROJECT}/dashboards/{DASHBOARD}/widgets/{WIDGET}/execute",
                    headers=headers, json={"refresh_latest": False, "language": "en"}, timeout=20,
                )
                self.assertEqual(dashboard_response.status_code, 200, dashboard_response.text[:500])
                self.assertEqual(dashboard_response.json()["result"]["kpis"][0]["value"], 5_300_000)

                report_response = httpx.post(
                    f"{base}/users/7/data/projects/{PROJECT}/reports", headers=headers,
                    json={"dashboard_id": DASHBOARD, "idempotency_key": "phase3-http-integration"},
                    timeout=20,
                )
                self.assertEqual(report_response.status_code, 202, report_response.text[:500])
                self.assertEqual(state["report"]["result_snapshot"]["version_vector"][0]["dataset_version_id"], VERSION)
                for suffix, signature in (("pdf", b"%PDF-"), ("xlsx", b"PK")):
                    exported = httpx.get(
                        f"{base}/users/7/data/projects/{PROJECT}/reports/{RUN}/export.{suffix}",
                        headers=headers, timeout=20,
                    )
                    self.assertEqual(exported.status_code, 200, exported.text[:500])
                    self.assertTrue(exported.content.startswith(signature))

                before_failure_files = {item.name for item in (uploads / "tenant_3" / "user_7").iterdir()}
                oversize = root / "oversize.csv"
                with oversize.open("wb") as payload:
                    payload.write(b"a,b\n")
                    payload.truncate(250_000_001)
                with oversize.open("rb") as payload, httpx.Client(timeout=None) as client:
                    rejected = client.post(
                        upload_url, headers=headers,
                        files={"file": ("oversize.csv", payload, "text/csv")},
                    )
                self.assertEqual(rejected.status_code, 413)
                self.assertEqual(
                    {item.name for item in (uploads / "tenant_3" / "user_7").iterdir()},
                    before_failure_files,
                )

                state["disk_fail"] = True
                disk_denied = httpx.post(
                    upload_url, headers=headers,
                    files={"file": ("disk.csv", b"a,b\n1,2\n", "text/csv")}, timeout=10,
                )
                self.assertEqual(disk_denied.status_code, 507)

                boundary = "phase3-interrupted"
                request_head = (
                    f"POST /users/7/data/projects/{PROJECT}/datasets/upload HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{port}\r\nAuthorization: Bearer {OWNER_TOKEN}\r\n"
                    f"Content-Type: multipart/form-data; boundary={boundary}\r\n"
                    "Content-Length: 10000000\r\nConnection: close\r\n\r\n"
                    f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"cut.csv\"\r\n"
                    "Content-Type: text/csv\r\n\r\n"
                ).encode("ascii")
                with socket.create_connection(("127.0.0.1", port), timeout=2) as interrupted:
                    interrupted.sendall(request_head + b"a,b\n" + b"1,2\n" * 100_000)
                time.sleep(0.5)
                self.assertFalse(list(uploads.rglob("*.uploading")))

                slow = root / "slow.csv"
                with slow.open("wb") as output:
                    output.write(b"a,b\n")
                    output.write(b"1,2\n" * 1_000_000)
                slow_results = []
                active = [threading.Event(), threading.Event()]

                def slow_upload(index):
                    payload = SlowFile(slow, active[index])
                    try:
                        result = httpx.post(
                            f"{base}/users/7/data/upload", headers=headers,
                            files={"file": (f"slow-{index}.csv", payload, "text/csv")},
                            timeout=30,
                        )
                        slow_results.append(result.status_code)
                    finally:
                        payload.close()

                workers = [threading.Thread(target=slow_upload, args=(index,)) for index in range(2)]
                for worker in workers:
                    worker.start()
                self.assertTrue(all(event.wait(5) for event in active))
                busy = httpx.post(
                    f"{base}/users/7/data/upload", headers=headers,
                    files={"file": ("third.csv", b"a,b\n1,2\n", "text/csv")}, timeout=10,
                )
                for worker in workers:
                    worker.join(30)
                self.assertEqual(sorted(slow_results), [200, 200])
                self.assertEqual(busy.status_code, 429)
                self.assertEqual(busy.json()["detail"]["code"], "dataset_upload_busy")

                print({
                    "http_upload_seconds": round(upload_seconds, 4),
                    "peak_rss_bytes": measurements["peak_rss"],
                    "peak_private_bytes": measurements["peak_private_bytes"],
                    "tmp_free_delta_bytes": max(
                        0, initial_tmp_free - measurements["minimum_tmp_free"],
                    ),
                    "stored_bytes": stored.stat().st_size,
                    "rows": body["rows"],
                    "oversize_status": rejected.status_code,
                    "disk_status": disk_denied.status_code,
                    "busy_status": busy.status_code,
                })
            finally:
                monitor_stop.set()
                if monitor_thread.is_alive():
                    monitor_thread.join(2)
                server.should_exit = True
                if thread.is_alive():
                    thread.join(5)
                patches.close()


if __name__ == "__main__":
    unittest.main()

import asyncio
import hashlib
from io import BytesIO
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from data_analysis import services as data_services
from services import (
    adaptive_analytics_service,
    bi_dashboard_service,
    bi_report_export_service,
    bi_reporting_service,
    versioned_analytics_service,
)
from services.request_body_limits import (
    DEFAULT_MAX_DATASET_REQUEST_BODY_BYTES,
    RequestBodyLimitConfig,
    RequestBodyLimitMiddleware,
    select_request_body_limit,
)
from workers import parser_worker


PROJECT = "11111111-1111-4111-8111-111111111111"
DATASET = "22222222-2222-4222-8222-222222222222"
VERSION = "33333333-3333-4333-8333-333333333333"
DASHBOARD = "44444444-4444-4444-8444-444444444444"
WIDGET = "55555555-5555-4555-8555-555555555555"
RUN = "66666666-6666-4666-8666-666666666666"


class StreamingUpload:
    def __init__(self, file, *, filename: str, content_type: str = "text/csv"):
        self.file = file
        self.filename = filename
        self.content_type = content_type

    async def read(self, size: int):
        return self.file.read(size)


class Phase3DatasetSupportTests(unittest.TestCase):
    def test_streaming_writer_hashes_atomically_and_cleans_cancelled_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "atomic.csv"
            content = b"name,value\nAlpha,1\n"
            upload = StreamingUpload(file=BytesIO(content), filename="atomic.csv")
            size, digest = asyncio.run(data_services.stream_upload_to_private_file(upload, target))
            self.assertEqual(size, len(content))
            self.assertEqual(digest, hashlib.sha256(content).hexdigest())
            self.assertEqual(target.read_bytes(), content)
            self.assertFalse((root / ".atomic.csv.uploading").exists())

            class CancelledUpload:
                calls = 0

                async def read(self, _size):
                    self.calls += 1
                    if self.calls == 1:
                        return b"partial"
                    raise asyncio.CancelledError

            cancelled_target = root / "cancelled.csv"
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(data_services.stream_upload_to_private_file(
                    CancelledUpload(), cancelled_target,
                ))
            self.assertFalse(cancelled_target.exists())
            self.assertFalse((root / ".cancelled.csv.uploading").exists())

    def test_only_expired_madar_partial_files_are_reclaimed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expired = root / ".abc.csv.uploading"
            active = root / ".def.csv.uploading"
            unrelated = root / "owner.csv"
            expired.write_bytes(b"old")
            active.write_bytes(b"active")
            unrelated.write_bytes(b"owner")
            now = time.time()
            os.utime(expired, (now - data_services.STALE_UPLOAD_PART_SECONDS - 1,) * 2)
            self.assertEqual(data_services.cleanup_stale_upload_parts(root, now=now), 1)
            self.assertFalse(expired.exists())
            self.assertTrue(active.exists())
            self.assertTrue(unrelated.exists())

    def test_chunked_metadata_rejects_excessive_width(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "wide.csv"
            columns = [f"column_{index}" for index in range(501)]
            source.write_text(
                ",".join(columns) + "\n" + ",".join("1" for _ in columns) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(HTTPException) as denied:
                data_services.extract_csv_metadata(source)
            self.assertEqual(denied.exception.status_code, 413)

    def test_250mb_policy_is_operation_and_row_aware(self):
        common = {
            "file_format": "csv", "size_bytes": 249_100_040,
            "row_count": 5_300_000,
        }
        self.assertEqual(adaptive_analytics_service.select_engine(
            workload="explore", **common,
        ).engine, "duckdb")
        self.assertEqual(adaptive_analytics_service.select_engine(
            workload="metric", operation="sum", polars_available=True, **common,
        ).engine, "polars")
        date = adaptive_analytics_service.select_engine(
            workload="metric", operation="date_aggregate", polars_available=True, **common,
        )
        self.assertEqual(date.engine, "unsupported")
        self.assertEqual(date.reason, "large_date_metric_limit_exceeded")
        self.assertEqual(adaptive_analytics_service.select_engine(
            workload="explore", file_format="csv", size_bytes=250_000_001,
            row_count=5_300_000,
        ).reason, "scalable_csv_limit_exceeded")
        self.assertEqual(adaptive_analytics_service.select_engine(
            workload="metric", file_format="csv", size_bytes=200_000_000,
            row_count=6_000_001, operation="count", polars_available=True,
        ).reason, "scalable_csv_limit_exceeded")

    def test_actual_source_size_enforces_the_smaller_date_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "dates.csv"
            with source.open("wb") as output:
                output.write(b"event_date,amount\n")
                output.truncate(adaptive_analytics_service.SCALABLE_DATE_MAX_BYTES + 1)
            with self.assertRaises(HTTPException) as denied:
                adaptive_analytics_service.run_large_metric(
                    authorized_path=str(source),
                    metric={
                        "operation": "date_aggregate", "date_column": "event_date",
                        "value_column": "amount", "aggregation": "sum", "period": "month",
                        "timezone": "UTC",
                    },
                    language="en", symbols={}, declared_rows=None,
                )
            self.assertEqual(denied.exception.status_code, 413)
            self.assertEqual(denied.exception.detail["code"],
                             "large_date_metric_limit_exceeded")

    def test_isolated_parser_worker_supports_chunked_csv_metadata(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"DATA_UPLOAD_DIR": directory, "PARSER_WORKER_PROCESS": "true"},
            clear=False,
        ):
            source = Path(directory) / "tenant_3" / "user_7" / "source.csv"
            source.parent.mkdir(parents=True)
            source.write_text("name,value\nA,1\nB,2\n", encoding="utf-8")
            result = parser_worker.parse_dataset({
                "operation": "csv_metadata", "input_path": str(source),
                "original_filename": "source.csv", "tenant_id": "3", "user_id": "7",
            })
            self.assertEqual(result["rows"], 2)
            self.assertEqual(result["columns"], ["name", "value"])
            self.assertEqual(result["storage"], "private")

    def test_backend_requests_the_bounded_worker_metadata_operation(self):
        payload = b'{"format":"csv","rows":2,"columns":["name","value"]}'
        response = MagicMock(status_code=200, headers={"Content-Length": str(len(payload))})
        response.raw.read.return_value = payload
        with patch.object(data_services.requests, "post", return_value=response) as post:
            result = data_services.extract_csv_metadata_via_worker(
                Path("/private/tenant_3/user_7/source.csv"),
                original_filename="source.csv", tenant_id="3", user_id="7",
            )
        self.assertEqual(result["rows"], 2)
        self.assertEqual(post.call_args.kwargs["json"]["operation"], "csv_metadata")
        self.assertTrue(post.call_args.kwargs["stream"])
        response.close.assert_called_once()
    def test_dataset_routes_have_a_narrow_multipart_envelope(self):
        config = RequestBodyLimitConfig(
            max_request_body_bytes=1024,
            max_builder_asset_request_body_bytes=2048,
            max_dataset_request_body_bytes=DEFAULT_MAX_DATASET_REQUEST_BODY_BYTES,
            max_json_body_bytes=512,
            max_small_json_body_bytes=256,
            max_data_json_body_bytes=128,
        )
        for path in (
            "/users/7/data/upload",
            f"/users/7/data/projects/{PROJECT}/datasets/upload",
            f"/users/7/data/projects/{PROJECT}/sources/source-1/ingestions/upload",
        ):
            self.assertEqual(select_request_body_limit(
                method="POST", path=path, content_type="multipart/form-data", config=config,
            ), DEFAULT_MAX_DATASET_REQUEST_BODY_BYTES)
        self.assertEqual(select_request_body_limit(
            method="POST", path="/unrelated/upload", content_type="multipart/form-data",
            config=config,
        ), 1024)

    def test_dataset_upload_admission_limit_rejects_before_body_spooling(self):
        reached = []

        async def app(scope, receive, send):
            reached.append(scope["path"])

        middleware = RequestBodyLimitMiddleware(app)
        self.assertTrue(middleware._dataset_upload_slots.acquire(blocking=False))
        self.assertTrue(middleware._dataset_upload_slots.acquire(blocking=False))
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        try:
            asyncio.run(middleware({
                "type": "http", "method": "POST", "path": "/users/7/data/upload",
                "headers": [(b"content-type", b"multipart/form-data; boundary=x")],
            }, receive, send))
        finally:
            middleware._dataset_upload_slots.release()
            middleware._dataset_upload_slots.release()
        self.assertEqual(reached, [])
        self.assertEqual(sent[0]["status"], 429)
        self.assertEqual(dict(sent[0]["headers"])[b"retry-after"], b"1")


@unittest.skipUnless(
    os.getenv("MADAR_RUN_250MB_INTEGRATION") == "1",
    "Set MADAR_RUN_250MB_INTEGRATION=1 with MADAR_PHASE3_DATASET_PATH.",
)
class Phase3DisposableIntegrationTests(unittest.TestCase):
    def test_upload_explore_dashboard_report_and_exports(self):
        source = Path(os.environ["MADAR_PHASE3_DATASET_PATH"]).resolve()
        self.assertGreater(source.stat().st_size, 150_000_000)
        self.assertLessEqual(source.stat().st_size, 250_000_000)
        timings = {}
        stage = time.monotonic()
        expected_hash = data_services.sha256_file(source)
        timings["source_hash_seconds"] = time.monotonic() - stage
        captured = {}

        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {
                "DATA_UPLOAD_DIR": str(Path(directory) / "private"),
                "PARSER_ISOLATED_WORKER_ENABLED": "true",
                "PARSER_WORKER_PROCESS": "true",
            }, clear=False,
        ), patch.object(data_services, "ensure_disk_capacity", return_value=10**12), \
                patch.object(data_services, "reserve_storage", return_value="reservation-1"), \
                patch.object(data_services, "finish_storage", return_value="object-1"), \
                patch.object(
                    data_services, "extract_csv_metadata_via_worker",
                    side_effect=lambda path, original_filename, tenant_id, user_id: (
                        parser_worker.parse_dataset_with_timeout({
                            "operation": "csv_metadata", "input_path": str(path),
                            "original_filename": original_filename,
                            "tenant_id": tenant_id, "user_id": user_id,
                        }, timeout_seconds=55)
                    ),
                ):
            def persist(artifact):
                captured.update(artifact)
                return {
                    "persistent_dataset_id": DATASET,
                    "dataset_version_id": VERSION,
                    "dataset_version_number": 1,
                    "content_hash": artifact["sha256"],
                }

            with source.open("rb") as payload:
                stage = time.monotonic()
                uploaded = asyncio.run(data_services.process_upload(
                    StreamingUpload(payload, filename="boundary.csv"),
                    tenant_id="3", user_id="7", metadata_persister=persist,
                ))
                timings["upload_metadata_seconds"] = time.monotonic() - stage
            self.assertEqual(captured["sha256"], expected_hash)
            self.assertGreater(uploaded["rows"], 2_000_000)
            stored = Path(directory) / "private" / "tenant_3" / "user_7" / uploaded["dataset_id"]
            self.assertTrue(stored.is_file())

            with self.assertRaises(HTTPException) as cross_tenant:
                data_services.authorize_dataset_input_path(
                    str(stored), tenant_id="4", user_id="7",
                )
            self.assertEqual(cross_tenant.exception.status_code, 403)

            with patch.object(
                versioned_analytics_service.data_services,
                "authorize_dataset_input_path", return_value=str(stored),
            ):
                stage = time.monotonic()
                first = versioned_analytics_service._explore_scalable_csv(
                    storage_identifier=uploaded["dataset_id"], tenant_id=3, user_id=7,
                    columns=["row_id", "group_key", "amount"],
                    filters=[{"field": "group_key", "operator": "eq", "value": "g099"}],
                    sort=[{"field": "amount", "direction": "desc"}], limit=100, offset=0,
                    started=time.monotonic(),
                )
                timings["exploration_first_seconds"] = time.monotonic() - stage
                stage = time.monotonic()
                second = versioned_analytics_service._explore_scalable_csv(
                    storage_identifier=uploaded["dataset_id"], tenant_id=3, user_id=7,
                    columns=["row_id", "group_key", "amount"],
                    filters=[{"field": "group_key", "operator": "eq", "value": "g099"}],
                    sort=[{"field": "amount", "direction": "desc"}], limit=100, offset=0,
                    started=time.monotonic(),
                )
                timings["exploration_repeat_seconds"] = time.monotonic() - stage
            self.assertEqual(first, second)

            version = {
                "id": VERSION, "version_number": 1, "version_kind": "source",
                "content_hash": expected_hash, "size_bytes": stored.stat().st_size,
                "file_metadata": {"rows": uploaded["rows"]},
            }
            persistent = {"storage_identifier": uploaded["dataset_id"], "version": version}
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
            with patch.object(bi_dashboard_service, "get_dashboard", return_value=dashboard), \
                    patch.object(
                        bi_dashboard_service.project_dataset_service,
                        "resolve_project_dataset_version", return_value=persistent,
                    ), patch.object(
                        data_services, "authorize_dataset_input_path", return_value=str(stored),
                    ):
                stage = time.monotonic()
                widget = bi_dashboard_service.execute_widget(
                    tenant_id=3, project_id=PROJECT, user_id=7, dashboard_id=DASHBOARD,
                    widget_id=WIDGET, refresh_latest=False, language="en", client=object(),
                )
                timings["dashboard_seconds"] = time.monotonic() - stage
            self.assertEqual(widget["status"], "ready")
            self.assertEqual(widget["result"]["kpis"][0]["value"], uploaded["rows"])

            run = {
                "id": RUN, "tenant_id": 3, "project_id": PROJECT, "creator_user_id": 7,
                "definition_snapshot": {
                    "dashboard": {"name": "Boundary dataset"}, "report_policy": {},
                    "widgets": [{"id": WIDGET, "title": "Rows",
                                 "analysis_spec": {"operation": "count"}}],
                },
                "version_vector": [{
                    "widget_id": WIDGET, "dataset_id": DATASET,
                    "dataset_version_id": VERSION, "version_number": 1,
                    "content_hash": expected_hash, "version_policy": "pinned",
                }],
            }
            with patch.object(
                bi_reporting_service.project_dataset_service, "get_project_dataset_freshness",
                return_value={"available": True, "resource": {}, "checkpoint": None},
            ), patch.object(
                bi_reporting_service.project_dataset_service,
                "resolve_project_dataset_version", return_value=persistent,
            ), patch.object(
                data_services, "authorize_dataset_input_path", return_value=str(stored),
            ), patch.object(
                bi_reporting_service, "_write_csv_artifact",
                return_value={"storage_key": "snapshot.csv", "filename": "snapshot.csv"},
            ):
                stage = time.monotonic()
                status, snapshot, warnings, artifact = bi_reporting_service.execute_run(
                    run, client=object(),
                )
                timings["report_seconds"] = time.monotonic() - stage
            self.assertEqual(status, "completed")
            self.assertEqual(warnings, [])
            self.assertEqual(snapshot["version_vector"][0]["dataset_version_id"], VERSION)
            self.assertEqual(snapshot["widgets"][0]["result"]["kpis"][0]["value"], uploaded["rows"])
            self.assertIsNotNone(artifact)

            completed_report = {
                **run, "status": "completed", "completed_at": "2026-10-28T12:00:00Z",
                "warnings": warnings, "result_snapshot": snapshot,
            }
            export_root = Path(directory) / "exports"
            stage = time.monotonic()
            pdf = bi_report_export_service.write_export(
                report=completed_report, tenant_id=3, root=export_root,
                export_format="pdf", language="en",
            )[0]
            xlsx = bi_report_export_service.write_export(
                report=completed_report, tenant_id=3, root=export_root,
                export_format="xlsx", language="en",
            )[0]
            timings["pdf_xlsx_seconds"] = time.monotonic() - stage
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"))
            self.assertTrue(xlsx.read_bytes().startswith(b"PK"))
            print({
                "phase3_metrics": {key: round(value, 4) for key, value in timings.items()},
                "bytes": source.stat().st_size, "rows": uploaded["rows"],
                "pdf_bytes": pdf.stat().st_size, "xlsx_bytes": xlsx.stat().st_size,
            })


if __name__ == "__main__":
    unittest.main()

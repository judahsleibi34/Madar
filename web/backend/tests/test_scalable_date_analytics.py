"""Correctness and opt-in resource measurements for Phase 5 date analytics."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import polars as pl
from fastapi import HTTPException

from services import adaptive_analytics_service as service
from services import adaptive_analytics_worker as worker
from services import bi_dashboard_service, bi_reporting_service
from services import parquet_cache_service
from data_analysis import services as data_services


DATES = (
    "2026-03-08T04:30:00Z", "2026-03-08T05:30:00Z",
    "2026-03-08T07:30:00Z", "2026-11-01T05:30:00Z",
    "2026-11-01T06:30:00Z", "2026-03-08 02:30:00",
    "2026-11-01 01:30:00", "2026-03-09 12:00:00", "bad", None,
)


class ScalableDateTests(unittest.TestCase):
    def test_timestamp_cache_eviction_preserves_results(self):
        dates = [
            (datetime(2026, 3, 8, tzinfo=timezone.utc) + timedelta(seconds=i)).isoformat()
            for i in range(6000)
        ]
        frame = pl.DataFrame({"date": dates, "amount": list(range(6000))})
        metric = {"date_column": "date", "value_column": "amount",
                  "aggregation": "sum", "period": "day", "timezone": "America/New_York"}
        with patch.object(worker, "DATE_PARSE_CACHE_ENTRIES", 0):
            expected = worker.date_metric(frame.lazy(), dict(frame.schema), metric, 500, 10000)
        self.assertEqual(worker.date_metric(frame.lazy(), dict(frame.schema), metric, 500, 10000), expected)

    def test_cached_and_uncached_results_match_for_all_aggregations_and_periods(self):
        frame = pl.DataFrame({
            "date": list(DATES) * 100,
            "amount": [0.1, 1e12, -1e12, None, 2.5, 4.0, 7.0, -3.0, 99.0, 99.0] * 100,
        })
        for zone in ("America/New_York", "Asia/Hebron", "UTC"):
            for period in ("day", "week", "month"):
                for aggregation in ("count", "sum", "mean", "min", "max"):
                    metric = {
                        "date_column": "date", "value_column": "amount",
                        "aggregation": aggregation, "period": period,
                        "timezone": zone, "start_date": "2026-03-08",
                        "end_date": "2026-11-01",
                    }
                    with self.subTest(zone=zone, period=period, aggregation=aggregation):
                        with patch.object(worker, "DATE_PARSE_CACHE_ENTRIES", 0):
                            expected = worker.date_metric(
                                frame.lazy(), dict(frame.schema), metric, 500, 2000,
                            )
                        actual = worker.date_metric(
                            frame.lazy(), dict(frame.schema), metric, 500, 2000,
                        )
                        self.assertEqual(actual, expected)

    def test_unique_timestamps_and_group_limit_remain_bounded(self):
        dates = [
            (datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)).isoformat()
            for i in range(6000)
        ]
        frame = pl.DataFrame({"date": dates})
        metric = {"date_column": "date", "aggregation": "count", "period": "day"}
        with self.assertRaisesRegex(worker.WorkerError, "analytics_group_cardinality_exceeded"):
            worker.date_metric(frame.lazy(), dict(frame.schema), metric, 500, 10000)

    def test_parquet_date_reuse_requires_exact_types_and_expansion_stays_disabled(self):
        self.assertEqual(service.SCALABLE_DATE_MAX_BYTES, 100 * 1024 * 1024)
        self.assertEqual(service.SCALABLE_DATE_MAX_ROWS, 2_000_000)
        decision = service.select_engine(
            workload="metric", file_format="csv", size_bytes=150_000_000,
            row_count=3_000_000, operation="date_aggregate", polars_available=True,
        )
        self.assertEqual(decision.reason, "large_date_metric_limit_exceeded")
        artifact = parquet_cache_service.ParquetArtifact(
            Path("unused.parquet"), "a" * 64, 100, 1, True,
            ("date", "amount"), ("amount",),
        )
        self.assertTrue(parquet_cache_service.is_metric_compatible(artifact, {
            "operation": "date_aggregate", "date_column": "date",
            "value_column": "amount", "aggregation": "sum",
        }))
        self.assertFalse(parquet_cache_service.is_metric_compatible(artifact, {
            "operation": "date_aggregate", "date_column": "converted_date",
            "value_column": "amount", "aggregation": "sum",
        }))
        self.assertFalse(parquet_cache_service.is_metric_compatible(artifact, {
            "operation": "date_aggregate", "date_column": "date",
            "value_column": "padded_numeric", "aggregation": "sum",
        }))


@unittest.skipUnless(os.getenv("MADAR_RUN_DATE_BENCHMARK") == "1", "Opt-in large date benchmark")
class DateBenchmark(unittest.TestCase):
    def test_high_cardinality_timestamp_resource_boundary(self):
        metric = {"operation": "date_aggregate", "date_column": "date",
                  "aggregation": "count", "period": "day", "timezone": "America/New_York"}
        with tempfile.TemporaryDirectory(prefix="madar-unique-date-") as directory:
            source = Path(directory) / "unique.csv"
            start_date = datetime(2026, 3, 8, tzinfo=timezone.utc)
            block = ''.join(
                (start_date + timedelta(seconds=i)).isoformat() + ',1,' + 'x' * 30 + '\n'
                for i in range(20000)
            ).encode()
            blocks = 100_000_000 // len(block)
            with source.open("wb") as output:
                output.write(b"date,amount,padding\n")
                for _ in range(blocks):
                    output.write(block)
            started = time.monotonic()
            try:
                result = service.run_large_metric(
                    authorized_path=str(source), metric=metric, language="en", symbols={},
                    declared_rows=blocks * 20000,
                )
                outcome = {"status": "ok", "peak_rss": result["metadata"]["worker_peak_rss_bytes"],
                           "scratch": result["metadata"]["scratch_bytes"]}
            except HTTPException as error:
                outcome = {"status": "refused", "code": error.detail["code"]}
            print("UNIQUE_DATE_BENCHMARK " + json.dumps({
                "bytes": source.stat().st_size, "rows": blocks * 20000,
                "unique_timestamps": 20000, "seconds": round(time.monotonic() - started, 4),
                **outcome,
            }), flush=True)

    def test_large_dates_under_unchanged_worker_budgets(self):
        # Temporarily widen admission only inside this experiment. Shipping
        # policy changes require successful measurements and remain independent.
        metric = {
            "operation": "date_aggregate", "date_column": "date",
            "value_column": "amount", "aggregation": "sum", "period": "month",
            "timezone": "America/New_York", "start_date": "2026-03-08",
            "end_date": "2026-11-01",
        }
        measurements = []
        with tempfile.TemporaryDirectory(prefix="madar-date-bench-") as directory:
            for target in (100_000_000, 150_000_000, 249_000_000):
                source = Path(directory) / f"dates-{target}.csv"
                records = [
                    f'{str(value or "")},{index % 7},' + 'x' * 25 + '\n'
                    for index, value in enumerate(DATES)
                ]
                block = ''.join(records).encode() * 1000
                with source.open("wb") as output:
                    output.write(b"date,amount,padding\n")
                    blocks = (target - 19) // len(block)
                    for _ in range(blocks):
                        output.write(block)
                rows = blocks * 10000
                csv_result = None
                for attempt in range(2):
                    started = time.monotonic()
                    observations = {"peak_rss": 0, "peak_virtual": 0}
                    original_resident = service._resident_bytes

                    def resident(pid):
                        value = original_resident(pid)
                        observations["peak_rss"] = max(observations["peak_rss"], value)
                        try:
                            for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                                if line.startswith("VmSize:"):
                                    observations["peak_virtual"] = max(
                                        observations["peak_virtual"], int(line.split()[1]) * 1024,
                                    )
                        except OSError:
                            pass
                        return value

                    with patch.object(service, "SCALABLE_DATE_MAX_BYTES", 250_000_000), \
                            patch.object(service, "SCALABLE_DATE_MAX_ROWS", 6_000_000), \
                            patch.object(service, "_resident_bytes", side_effect=resident):
                        try:
                            result = service.run_large_metric(
                                authorized_path=str(source), metric=metric, language="en",
                                symbols={}, declared_rows=rows,
                            )
                            self.assertEqual(result["result"]["tables"][0]["rows"], [
                                {"period": "2026-03", "value": 3 * rows // 10},
                                {"period": "2026-11", "value": 7 * rows // 10},
                            ])
                            mappings = result["result"]["metadata"]["mappings_used"]
                            self.assertEqual(mappings["missing_date_count"], rows // 10)
                            self.assertEqual(mappings["invalid_date_count"], 3 * rows // 10)
                            csv_result = result["result"]
                            outcome = {"status": "ok", "rows_used": result["rows_used"],
                                       "scratch": result["metadata"]["scratch_bytes"],
                                       "result": result["result"]["tables"][0]["rows"]}
                        except HTTPException as error:
                            outcome = {"status": "refused", "code": error.detail["code"]}
                    measurements.append({
                        "bytes": source.stat().st_size, "rows": rows, "attempt": attempt + 1,
                        "seconds": round(time.monotonic() - started, 4),
                        **observations, **outcome,
                    })
                parquet = source.with_suffix(".parquet")
                started = time.monotonic()
                try:
                    size, _, compatible, numeric, rss, scratch = parquet_cache_service._convert(
                        source, parquet, declared_rows=rows,
                    )
                    measurements.append({"bytes": source.stat().st_size,
                        "operation": "convert", "seconds": round(time.monotonic() - started, 4),
                        "artifact_bytes": size, "peak_rss": rss, "scratch": scratch,
                        "compatible": "date" in compatible and "amount" in numeric})
                    for attempt in range(2):
                        started = time.monotonic()
                        observations = {"peak_rss": 0, "peak_virtual": 0}
                        try:
                            with patch.object(service, "SCALABLE_DATE_MAX_BYTES", 250_000_000), \
                                    patch.object(service, "SCALABLE_DATE_MAX_ROWS", 6_000_000), \
                                    patch.object(service, "_resident_bytes", side_effect=resident):
                                result = service.run_large_metric(
                                    authorized_path=str(parquet), metric=metric, language="en",
                                    symbols={}, declared_rows=rows, source_format="parquet",
                                    source_size_bytes=source.stat().st_size,
                                )
                            self.assertEqual(result["result"]["tables"][0]["rows"], [
                                {"period": "2026-03", "value": 3 * rows // 10},
                                {"period": "2026-11", "value": 7 * rows // 10},
                            ])
                            mappings = result["result"]["metadata"]["mappings_used"]
                            self.assertEqual(mappings["missing_date_count"], rows // 10)
                            self.assertEqual(mappings["invalid_date_count"], 3 * rows // 10)
                            if csv_result is not None:
                                self.assertEqual(result["result"], csv_result)
                            outcome = {"status": "ok", "peak_rss": result["metadata"]["worker_peak_rss_bytes"],
                                       "scratch": result["metadata"]["scratch_bytes"]}
                        except HTTPException as error:
                            outcome = {"status": "refused", "code": error.detail["code"]}
                        measurements.append({"bytes": source.stat().st_size,
                            "operation": "parquet_query", "attempt": attempt + 1,
                            "seconds": round(time.monotonic() - started, 4), **observations, **outcome})
                except (OSError, RuntimeError, TimeoutError, ValueError) as error:
                    measurements.append({"bytes": source.stat().st_size,
                        "operation": "convert", "status": "refused", "error_type": type(error).__name__})
                parquet.unlink(missing_ok=True)
                source.unlink()
        print("DATE_BENCHMARK " + json.dumps(measurements, sort_keys=True), flush=True)

    def test_large_date_dashboard_and_immutable_report(self):
        project = "11111111-1111-4111-8111-111111111111"
        dataset = "22222222-2222-4222-8222-222222222222"
        version_id = "33333333-3333-4333-8333-333333333333"
        dashboard_id = "44444444-4444-4444-8444-444444444444"
        widget_id = "55555555-5555-4555-8555-555555555555"
        metric = {"operation": "date_aggregate", "date_column": "date",
                  "value_column": "amount", "aggregation": "sum", "period": "month",
                  "timezone": "America/New_York", "start_date": "2026-03-08",
                  "end_date": "2026-11-01"}
        with tempfile.TemporaryDirectory(prefix="madar-date-flow-") as directory:
            source = Path(directory) / "tenant_3" / "user_7" / "dates.csv"
            source.parent.mkdir(parents=True)
            block = ''.join(
                f'{str(value or "")},{index % 7},' + 'x' * 25 + '\n'
                for index, value in enumerate(DATES)
            ).encode() * 1000
            with source.open("wb") as output:
                output.write(b"date,amount,padding\n")
                for _ in range(int(os.getenv("MADAR_DATE_FLOW_BLOCKS", "180"))):
                    output.write(block)
            rows = int(os.getenv("MADAR_DATE_FLOW_BLOCKS", "180")) * 10000
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            version = {"id": version_id, "version_number": 1, "version_kind": "original",
                       "size_bytes": source.stat().st_size, "content_hash": digest,
                       "file_metadata": {"rows": rows}}
            persistent = {"storage_identifier": source.name, "version": version}
            widget = {"id": widget_id, "widget_type": "table", "title": "Dates",
                      "dataset_id": dataset, "dataset_version_id": version_id,
                      "version_policy": "pinned", "analysis_spec": metric,
                      "layout_config": {}, "display_options": {}}
            dashboard = {"id": dashboard_id, "revision": 1, "creator_user_id": 7,
                         "access": {"can_edit": True}, "widgets": [widget]}
            run = {"id": "66666666-6666-4666-8666-666666666666", "tenant_id": 3,
                   "project_id": project, "creator_user_id": 7,
                   "definition_snapshot": {"dashboard": {"name": "Dates"},
                                           "report_policy": {}, "widgets": [widget]},
                   "version_vector": [{"widget_id": widget_id, "dataset_id": dataset,
                                       "dataset_version_id": version_id, "version_number": 1,
                                       "content_hash": digest, "version_policy": "pinned"}]}
            with patch.object(data_services, "authorize_dataset_input_path", return_value=str(source)), \
                    patch.object(bi_dashboard_service, "get_dashboard", return_value=dashboard), \
                    patch.object(bi_dashboard_service.project_dataset_service,
                                 "resolve_project_dataset_version", return_value=persistent), \
                    patch.object(bi_reporting_service.project_dataset_service,
                                 "get_project_dataset_freshness", return_value={"available": False}), \
                    patch.dict(os.environ, {"PRIVATE_CHARTS_DIR": directory,
                        "DATA_UPLOAD_DIR": directory, "PARQUET_CACHE_ENABLED": "true"}, clear=False), \
                    patch.object(service, "_run_polars_worker", wraps=service._run_polars_worker) as query_worker:
                start = time.monotonic()
                baseline = bi_dashboard_service.execute_widget(
                    tenant_id=3, project_id=project, user_id=7, dashboard_id=dashboard_id,
                    widget_id=widget_id, refresh_latest=False, language="en", client=object(),
                )
                cached = parquet_cache_service.get_or_create(
                    source_path=str(source), tenant_id=3, user_id=7, project_id=project,
                    dataset_id=dataset, version_id=version_id, source_hash=digest,
                    source_size=source.stat().st_size, declared_rows=rows,
                )
                self.assertIsNotNone(cached)
                self.assertTrue(parquet_cache_service.is_metric_compatible(cached, metric))
                executed = bi_dashboard_service.execute_widget(
                    tenant_id=3, project_id=project, user_id=7, dashboard_id=dashboard_id,
                    widget_id=widget_id, refresh_latest=False, language="en", client=object(),
                )
                self.assertEqual(executed["status"], "ready")
                self.assertEqual(executed["result"], baseline["result"])
                status, snapshot, warnings, artifact = bi_reporting_service.execute_run(run, client=object())
                self.assertEqual([
                    call.kwargs["request"]["source_format"] for call in query_worker.call_args_list
                ], ["csv", "parquet", "parquet"])
            self.assertEqual(status, "completed")
            self.assertEqual(snapshot["widgets"][0]["result"], executed["result"])
            self.assertEqual(snapshot["version_vector"][0]["content_hash"], digest)
            self.assertEqual(executed["provenance"]["dataset_version_id"], version_id)
            self.assertTrue(artifact)
            self.assertTrue(warnings)
            print("DATE_FLOW " + json.dumps({"bytes": source.stat().st_size, "rows": rows,
                  "seconds": round(time.monotonic() - start, 4), "status": status,
                  "warnings": warnings}), flush=True)


if __name__ == "__main__":
    unittest.main()

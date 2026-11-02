"""Phase 5B parser equivalence and streaming-reader regressions."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import polars as pl

from services import adaptive_analytics_worker as worker
from services import adaptive_analytics_service as service
from services import parquet_cache_service


class LargeDateStreamingTests(unittest.TestCase):
    def test_specialized_aware_iso_parser_matches_pandas_exactly(self):
        dates = []
        for instant in (datetime(2026, 3, 8, 6, tzinfo=timezone.utc),
                        datetime(2026, 11, 1, 5, tzinfo=timezone.utc)):
            for index in range(180):
                value = instant + timedelta(minutes=index, microseconds=index)
                for offset in (-720, -210, 0, 330, 840):
                    dates.append(value.astimezone(timezone(timedelta(minutes=offset))).isoformat())
        dates += ["2026-03-08T07:30:00Z", "2026-11-01T06:30:00Z",
                  "2026-03-08 02:30:00", "2026-11-01 01:30:00",
                  "2026-02-30T00:00:00Z", "2026-03-08T24:00:00Z", "bad", None,
                  "2026-03-08T07:30:00.123456789Z", "2026-03-08T07:30:00+25:00"]
        frame = pl.DataFrame({"date": dates, "amount": [0.1, 1e10, -1e10, None] * (len(dates) // 4)
                              + [0.1] * (len(dates) % 4)})
        for zone in ("America/New_York", "Asia/Hebron", "Asia/Kolkata", "UTC"):
            for period in ("day", "week", "month"):
                for aggregation in ("count", "sum", "mean", "min", "max"):
                    metric = {"date_column": "date", "value_column": "amount",
                              "aggregation": aggregation, "period": period, "timezone": zone,
                              "start_date": "2026-03-08", "end_date": "2026-11-01"}
                    with self.subTest(zone=zone, period=period, aggregation=aggregation):
                        with patch.object(worker, "DATE_ISO_FAST_PATH", False):
                            expected = worker.date_metric(frame.lazy(), dict(frame.schema), metric, 500, 10000)
                        self.assertEqual(worker.date_metric(
                            frame.lazy(), dict(frame.schema), metric, 500, 10000,
                        ), expected)

    def test_pull_csv_reader_matches_lazy_reader_for_csv_edge_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dates.csv"
            path.write_bytes(
                b'\xef\xbb\xbfdate,amount,note\r\n'
                b'2026-03-08T07:30:00Z,0.1,"embedded\r\nnewline"\r\n'
                b'2026-11-01T06:30:00+00:00,1.0,"escaped ""quote"""\r\n'
                b',,""\r\n'
                b'bad,-2.0,last\r\n'
            )
            frame = pl.scan_csv(path, infer_schema_length=10000, try_parse_dates=False, low_memory=True)
            schema = dict(frame.collect_schema())
            metric = {"date_column": "date", "value_column": "amount", "aggregation": "sum",
                      "period": "month", "timezone": "America/New_York"}
            with patch.object(worker, "DATE_ISO_FAST_PATH", False):
                expected = worker.date_metric(frame, schema, metric, 500, 100)
            with patch.object(worker, "DATE_CSV_BATCH_BYTES", 32):
                actual = worker.date_metric(frame, schema, metric, 500, 100,
                    batches=worker.date_csv_batches(str(path), schema, ["date", "amount"]))
            self.assertEqual(actual, expected)

    def test_oversized_record_is_bounded_and_reader_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "long.csv"
            path.write_text('date,amount\n"' + 'x' * 300 + '\n' + 'y' * 300 + '",1\n')
            with patch.object(worker, "DATE_CSV_RECORD_BYTES", 256):
                with self.assertRaisesRegex(worker.WorkerError, "analytics_csv_record_limit_exceeded"):
                    list(worker.date_csv_batches(str(path), {"date": pl.String, "amount": pl.Int64},
                                                 ["date", "amount"]))

    def test_leading_blank_lines_do_not_drop_rows_between_batches(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blank.csv"
            path.write_bytes(b'\n\r\ndate,amount\n2026-03-08T07:30:00Z,1\n2026-03-09T07:30:00Z,2\n')
            frame = pl.scan_csv(path)
            with patch.object(worker, "DATE_CSV_BATCH_BYTES", 1):
                actual = [row for batch in worker.date_csv_batches(
                    str(path), dict(frame.collect_schema()), ["date", "amount"],
                ) for row in batch.to_dicts()]
            self.assertEqual(actual, frame.collect().to_dicts())

    def test_late_numeric_drift_is_not_silently_coerced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "drift.csv"
            path.write_text("date,amount\n" + "2026-03-08T07:30:00Z,1\n" * 11000
                            + "2026-03-08T07:30:00Z,bad\n", encoding="utf-8")
            frame = pl.scan_csv(path, infer_schema_length=10000, try_parse_dates=False)
            schema = dict(frame.collect_schema())
            with self.assertRaises(pl.exceptions.PolarsError):
                list(worker.date_csv_batches(str(path), schema, ["date", "amount"]))


@unittest.skipUnless(os.getenv("MADAR_RUN_DATE_STREAMING_BENCHMARK") == "1",
                     "Opt-in Phase 5B streaming measurements")
class DateStreamingBenchmark(unittest.TestCase):
    def test_experimental_247mb_dashboard_and_report(self):
        from tests.test_scalable_date_analytics import DateBenchmark
        # Experimental admission only; no shipping constant is expanded.
        with patch.dict(os.environ, {"MADAR_DATE_FLOW_BLOCKS": "550"}), \
                patch.object(service, "SCALABLE_DATE_MAX_BYTES", 250_000_000), \
                patch.object(service, "SCALABLE_DATE_MAX_ROWS", 6_000_000):
            DateBenchmark("test_large_date_dashboard_and_immutable_report").test_large_date_dashboard_and_immutable_report()

    def test_high_cardinality_and_wide_csv_and_parquet(self):
        measurements = []
        metric = {"operation": "date_aggregate", "date_column": "date",
                  "value_column": "amount", "aggregation": "sum", "period": "day",
                  "timezone": "America/New_York", "start_date": "2026-03-07",
                  "end_date": "2026-11-02"}
        with tempfile.TemporaryDirectory(prefix="madar-date-stream-bench-") as directory:
            for wide in (False, True):
                header = b"date,amount," + (
                    ','.join(f'c{i}' for i in range(63)).encode() if wide else b"padding"
                ) + b"\n"
                records = []
                for index in range(20000):
                    base = datetime(2026, 3, 8 if index < 10000 else 9, tzinfo=timezone.utc)
                    stamp = (base + timedelta(seconds=index)).isoformat()
                    if index % 97 == 0:
                        stamp = "bad"
                    elif index % 89 == 0:
                        stamp = ""
                    elif index % 79 == 0:
                        stamp = "2026-03-08 02:30:00"
                    padding = ','.join(str((index + j) % 7) for j in range(63)) if wide else 'x' * 25
                    records.append(f"{stamp},{index % 7},{padding}\n")
                block = ''.join(records).encode()
                reference_path = Path(directory) / "reference.csv"
                reference_path.write_bytes(header + block)
                frame = pl.scan_csv(reference_path, infer_schema_length=10000, try_parse_dates=False)
                with patch.object(worker, "DATE_ISO_FAST_PATH", False):
                    reference = worker.date_metric(frame, dict(frame.collect_schema()), metric, 500, 20000)
                for target in (100_000_000, 150_000_000, 249_000_000):
                    source = Path(directory) / f"source-{wide}-{target}.csv"
                    blocks = (target - len(header)) // len(block)
                    with source.open("wb") as output:
                        output.write(header)
                        for _ in range(blocks):
                            output.write(block)
                    rows = blocks * 20000
                    expected_rows = [{**item, "value": item["value"] * blocks} for item in reference[0]]
                    csv_result = None
                    parquet = source.with_suffix(".parquet")
                    for source_format in ("csv", "parquet"):
                        if source_format == "parquet":
                            started = time.monotonic()
                            try:
                                size, _, _, _, rss, scratch = parquet_cache_service._convert(
                                    source, parquet, declared_rows=rows,
                                )
                                measurements.append({"wide": wide, "source_bytes": source.stat().st_size,
                                    "operation": "convert", "seconds": round(time.monotonic() - started, 4),
                                    "parquet_bytes": size, "peak_rss": rss, "scratch": scratch})
                            except (RuntimeError, OSError, ValueError, TimeoutError):
                                measurements.append({"wide": wide, "source_bytes": source.stat().st_size,
                                    "operation": "convert", "status": "refused"})
                                continue
                        for attempt in range(2):
                            observations = {"peak_rss": 0, "peak_virtual": 0}
                            original_resident = service._resident_bytes

                            def resident(pid):
                                rss = original_resident(pid)
                                observations["peak_rss"] = max(observations["peak_rss"], rss)
                                try:
                                    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                                        if line.startswith("VmSize:"):
                                            observations["peak_virtual"] = max(
                                                observations["peak_virtual"], int(line.split()[1]) * 1024)
                                except OSError:
                                    pass
                                return rss

                            started = time.monotonic()
                            with patch.object(service, "SCALABLE_DATE_MAX_BYTES", 250_000_000), \
                                    patch.object(service, "SCALABLE_DATE_MAX_ROWS", 6_000_000), \
                                    patch.object(service, "_resident_bytes", side_effect=resident):
                                try:
                                    result = service.run_large_metric(
                                        authorized_path=str(source if source_format == "csv" else parquet),
                                        metric=metric, language="en", symbols={}, declared_rows=rows,
                                        source_format=source_format, source_size_bytes=source.stat().st_size,
                                    )
                                    self.assertEqual(result["result"]["tables"][0]["rows"], expected_rows)
                                    mappings = result["result"]["metadata"]["mappings_used"]
                                    for name in ("missing_date_count", "invalid_date_count", "selected_row_count",
                                                 "outside_period_count", "total_row_count"):
                                        self.assertEqual(mappings[name], reference[1][name] * blocks)
                                    if source_format == "csv":
                                        csv_result = result["result"]
                                    elif csv_result is not None:
                                        self.assertEqual(result["result"], csv_result)
                                    outcome = {"status": "ok", "scratch": result["metadata"]["scratch_bytes"]}
                                except service.HTTPException as error:
                                    outcome = {"status": "refused", "code": error.detail["code"]}
                            measurements.append({"wide": wide, "source_bytes": source.stat().st_size,
                                "rows": rows, "format": source_format, "attempt": attempt + 1,
                                "seconds": round(time.monotonic() - started, 4), **observations, **outcome})
                    source.unlink()
                    parquet.unlink(missing_ok=True)
        print("DATE_STREAM_BENCHMARK " + json.dumps(measurements, sort_keys=True), flush=True)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

import duckdb
import pandas as pd
from fastapi import HTTPException

from services import versioned_analytics_service


PROJECT = "11111111-1111-4111-8111-111111111111"
DATASET = "22222222-2222-4222-8222-222222222222"
VERSION = "33333333-3333-4333-8333-333333333333"


def resolved(*, size=100, rows=4):
    return {
        "dataset": {"id": DATASET, "project_id": PROJECT},
        "version": {
            "id": VERSION, "version_number": 3, "version_kind": "derived",
            "size_bytes": size, "content_hash": "a" * 64,
            "file_metadata": {"rows": rows},
        },
        "storage_identifier": "version-3.csv",
    }


class VersionedAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({
            "name": ["C", "A", "B", "D"],
            "amount": [30, 10, 20, None],
            "observed_at": ["2026-03-03", "2026-03-01", "2026-03-02", None],
        })

    def explore(self, **overrides):
        values = {
            "tenant_id": 1, "project_id": PROJECT, "user_id": 7,
            "dataset_id": DATASET, "version_id": VERSION, "columns": [],
            "filters": [], "sort": [], "limit": 100, "offset": 0,
        }
        values.update(overrides)
        with patch.object(versioned_analytics_service.project_dataset_service,
                          "resolve_project_dataset_version", return_value=resolved()) as resolve, \
             patch.object(versioned_analytics_service.data_services,
                          "read_dataset", return_value=self.frame.copy()) as read:
            result = versioned_analytics_service.explore_dataset_version(**values)
        resolve.assert_called_once_with(
            tenant_id=1, project_id=PROJECT, user_id=7,
            dataset_id=DATASET, version_id=VERSION, client=None,
        )
        read.assert_called_once_with("version-3.csv", tenant_id="1", user_id="7")
        return result

    def test_exact_version_filter_sort_and_paging(self):
        result = self.explore(
            columns=["name", "amount"],
            filters=[{"field": "amount", "operator": "gte", "value": "15"}],
            sort=[{"field": "amount", "direction": "desc"}], limit=1, offset=1,
        )
        self.assertEqual(result["rows"], [{"name": "B", "amount": 20.0}])
        self.assertEqual(result["pagination"], {
            "limit": 1, "offset": 1, "returned": 1, "total": 2, "has_more": False,
        })
        self.assertEqual(result["provenance"]["dataset_version_id"], VERSION)

    def test_date_and_missing_filters_are_typed(self):
        result = self.explore(filters=[
            {"field": "observed_at", "operator": "gte", "value": "2026-03-02"},
            {"field": "amount", "operator": "not_missing"},
        ])
        self.assertEqual([row["name"] for row in result["rows"]], ["C", "B"])

    def test_unknown_fields_and_text_ranges_fail_closed(self):
        for filters in (
            [{"field": "private", "operator": "eq", "value": "x"}],
            [{"field": "name", "operator": "gte", "value": "A"}],
        ):
            with self.subTest(filters=filters), self.assertRaises(HTTPException) as denied:
                self.explore(filters=filters)
            self.assertEqual(denied.exception.status_code, 422)

    def test_query_bounds_are_enforced_before_storage_read(self):
        with self.assertRaises(HTTPException) as denied:
            self.explore(limit=101)
        self.assertEqual(denied.exception.status_code, 422)

        with patch.object(versioned_analytics_service.project_dataset_service,
                          "resolve_project_dataset_version",
                          return_value=resolved(size=versioned_analytics_service.MAX_SCALABLE_CSV_SOURCE_BYTES + 1)), \
             patch.object(versioned_analytics_service.data_services,
                          "authorize_dataset_input_path") as authorize:
            with self.assertRaises(HTTPException) as too_large:
                versioned_analytics_service.explore_dataset_version(
                    tenant_id=1, project_id=PROJECT, user_id=7, dataset_id=DATASET,
                    version_id=VERSION, columns=[], filters=[], sort=[], limit=10, offset=0,
                )
        self.assertEqual(too_large.exception.status_code, 413)
        self.assertEqual(too_large.exception.detail["code"],
                         "dataset_exploration_scalable_source_limit_exceeded")
        authorize.assert_not_called()

    def test_large_csv_projection_filter_sort_pagination_count_and_repeatability(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.csv"
            payload = "x" * 104
            with path.open("w", encoding="utf-8", newline="") as output:
                output.write("record_id,group_name,amount,observed_at,payload\n")
                for index in range(100_005):
                    group = "even" if index % 2 == 0 else "odd"
                    output.write(
                        f"{index},{group},{index % 100},2026-01-{index % 28 + 1:02d},{payload}\n"
                    )
            self.assertGreater(path.stat().st_size,
                               versioned_analytics_service.MAX_EXPLORATION_SOURCE_BYTES)

            persistent = resolved(size=path.stat().st_size, rows=100_005)
            query = {
                "tenant_id": 1, "project_id": PROJECT, "user_id": 7,
                "dataset_id": DATASET, "version_id": VERSION,
                "columns": ["record_id", "amount"],
                "filters": [
                    {"field": "group_name", "operator": "eq", "value": "even"},
                    {"field": "amount", "operator": "gte", "value": "90"},
                ],
                "sort": [
                    {"field": "amount", "direction": "desc"},
                    {"field": "record_id", "direction": "asc"},
                ],
                "limit": 5, "offset": 3,
            }
            with patch.object(
                versioned_analytics_service.project_dataset_service,
                "resolve_project_dataset_version", return_value=persistent,
            ) as resolve, patch.object(
                versioned_analytics_service.data_services,
                "authorize_dataset_input_path", return_value=str(path),
            ) as authorize:
                first = versioned_analytics_service.explore_dataset_version(**query)
                second = versioned_analytics_service.explore_dataset_version(**query)

            self.assertEqual(first, second)
            self.assertEqual(first["pagination"], {
                "limit": 5, "offset": 3, "returned": 5, "total": 5000, "has_more": True,
            })
            self.assertEqual([row["record_id"] for row in first["rows"]],
                             [398, 498, 598, 698, 798])
            self.assertEqual(first["provenance"]["dataset_version_id"], VERSION)
            self.assertEqual(first["provenance"]["content_hash"], "a" * 64)
            self.assertEqual(first["limits"]["max_rows"],
                             versioned_analytics_service.MAX_SCALABLE_CSV_ROWS)
            self.assertEqual(resolve.call_count, 2)
            authorize.assert_called_with(
                "version-3.csv", tenant_id="1", user_id="7", require_small=False,
                operation="bounded scalable dataset exploration",
            )

    def test_large_non_csv_remains_on_the_safe_unsupported_path(self):
        persistent = resolved(size=11 * 1024 * 1024, rows=100_001)
        persistent["storage_identifier"] = "version-3.xlsx"
        with patch.object(
            versioned_analytics_service.project_dataset_service,
            "resolve_project_dataset_version", return_value=persistent,
        ), patch.object(versioned_analytics_service.data_services, "read_dataset") as read:
            with self.assertRaises(HTTPException) as denied:
                versioned_analytics_service.explore_dataset_version(
                    tenant_id=1, project_id=PROJECT, user_id=7, dataset_id=DATASET,
                    version_id=VERSION, columns=[], filters=[], sort=[], limit=10, offset=0,
                )
        self.assertEqual(denied.exception.status_code, 413)
        self.assertEqual(denied.exception.detail["code"],
                         "dataset_exploration_scalable_format_unsupported")
        read.assert_not_called()

    def test_large_csv_authorization_failure_precedes_duckdb_access(self):
        with patch.object(
            versioned_analytics_service.project_dataset_service,
            "resolve_project_dataset_version", return_value=resolved(size=11 * 1024 * 1024),
        ), patch.object(
            versioned_analytics_service.data_services, "authorize_dataset_input_path",
            side_effect=HTTPException(status_code=403, detail="Dataset access is not allowed."),
        ) as authorize, patch.object(versioned_analytics_service.duckdb, "connect") as connect:
            with self.assertRaises(HTTPException) as denied:
                versioned_analytics_service.explore_dataset_version(
                    tenant_id=1, project_id=PROJECT, user_id=7, dataset_id=DATASET,
                    version_id=VERSION, columns=[], filters=[], sort=[], limit=10, offset=0,
                )
        self.assertEqual(denied.exception.status_code, 403)
        authorize.assert_called_once()
        connect.assert_not_called()

    def test_quoted_identifiers_and_bound_values_are_not_sql(self):
        dangerous_column = 'value" FROM read_csv_auto(\'/etc/passwd\') --'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quoted.csv"
            path.write_text(f'"{dangerous_column.replace(chr(34), chr(34) * 2)}"\n'
                            '"x\' OR true --"\n"other"\n', encoding="utf-8")
            with patch.object(
                versioned_analytics_service.project_dataset_service,
                "resolve_project_dataset_version", return_value=resolved(size=11 * 1024 * 1024),
            ), patch.object(
                versioned_analytics_service.data_services,
                "authorize_dataset_input_path", return_value=str(path),
            ):
                result = versioned_analytics_service.explore_dataset_version(
                    tenant_id=1, project_id=PROJECT, user_id=7, dataset_id=DATASET,
                    version_id=VERSION, columns=[dangerous_column],
                    filters=[{"field": dangerous_column, "operator": "eq",
                              "value": "x' OR true --"}],
                    sort=[{"field": dangerous_column, "direction": "asc"}], limit=10, offset=0,
                )
        self.assertEqual(result["rows"], [{dangerous_column: "x' OR true --"}])
        self.assertEqual(result["pagination"]["total"], 1)

    def test_duckdb_connection_is_locked_to_source_and_private_scratch(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.csv"
            other = Path(directory) / "other.csv"
            scratch = Path(directory) / "scratch"
            source.write_text("value\n1\n", encoding="utf-8")
            other.write_text("value\n2\n", encoding="utf-8")
            scratch.mkdir()
            connection = duckdb.connect(":memory:")
            try:
                versioned_analytics_service._configure_duckdb(
                    connection, source_path=str(source), scratch_path=str(scratch),
                )
                self.assertEqual(connection.execute(
                    "SELECT value FROM read_csv_auto(?)", [str(source)],
                ).fetchone()[0], 1)
                with self.assertRaises(duckdb.PermissionException):
                    connection.execute("SELECT * FROM read_csv_auto(?)", [str(other)])
                settings = dict(connection.execute(
                    "SELECT name, value FROM duckdb_settings() WHERE name IN "
                    "('enable_external_access', 'autoinstall_known_extensions', "
                    "'autoload_known_extensions', 'allow_community_extensions', "
                    "'lock_configuration', 'threads', 'memory_limit', "
                    "'max_temp_directory_size')"
                ).fetchall())
                self.assertEqual(settings, {
                    "allow_community_extensions": "false",
                    "autoinstall_known_extensions": "false",
                    "autoload_known_extensions": "false",
                    "enable_external_access": "false",
                    "lock_configuration": "true",
                    "max_temp_directory_size": "256.0 MiB",
                    "memory_limit": "128.0 MiB",
                    "threads": "1",
                })
            finally:
                connection.close()

    def test_scalable_concurrency_and_deadline_fail_closed(self):
        slots = versioned_analytics_service._scalable_exploration_slots
        self.assertTrue(slots.acquire(blocking=False))
        self.assertTrue(slots.acquire(blocking=False))
        try:
            with self.assertRaises(HTTPException) as busy:
                versioned_analytics_service._explore_scalable_csv(
                    storage_identifier="large.csv", tenant_id=1, user_id=7,
                    columns=[], filters=[], sort=[], limit=10, offset=0,
                    started=time.monotonic(),
                )
            self.assertEqual(busy.exception.status_code, 429)
        finally:
            slots.release()
            slots.release()

        with self.assertRaises(HTTPException) as expired:
            versioned_analytics_service._execute_duckdb(
                object(), "SELECT 1", [],
                started=time.monotonic()
                - versioned_analytics_service.SCALABLE_EXPLORATION_DEADLINE_SECONDS - 1,
            )
        self.assertEqual(expired.exception.status_code, 408)

        connection = duckdb.connect(":memory:")
        try:
            with patch.object(
                versioned_analytics_service,
                "SCALABLE_EXPLORATION_DEADLINE_SECONDS", 0.01,
            ), self.assertRaises(HTTPException) as interrupted:
                versioned_analytics_service._execute_duckdb(
                    connection, "SELECT sum(value) FROM range(1000000000) AS items(value)", [],
                    started=time.monotonic(),
                )
            self.assertEqual(interrupted.exception.status_code, 408)
        finally:
            connection.close()

    def test_scalable_memory_and_actual_row_limits_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "limits.csv"
            path.write_text(
                "record_id,payload\n"
                + "".join(f"{index},{'x' * 100}\n" for index in range(20_000)),
                encoding="utf-8",
            )
            common = {
                "storage_identifier": path.name, "tenant_id": 1, "user_id": 7,
                "columns": ["record_id"], "filters": [],
                "sort": [{"field": "payload", "direction": "asc"}],
                "limit": 10, "offset": 0,
            }
            with patch.object(
                versioned_analytics_service.data_services,
                "authorize_dataset_input_path", return_value=str(path),
            ), patch.object(
                versioned_analytics_service, "SCALABLE_EXPLORATION_MEMORY_LIMIT", "1MiB",
            ), self.assertRaises(HTTPException) as memory_limited:
                versioned_analytics_service._explore_scalable_csv(
                    **common, started=time.monotonic(),
                )
            self.assertEqual(memory_limited.exception.status_code, 413)
            self.assertEqual(memory_limited.exception.detail["code"],
                             "dataset_exploration_resource_limit_exceeded")

            with patch.object(
                versioned_analytics_service.data_services,
                "authorize_dataset_input_path", return_value=str(path),
            ), patch.object(
                versioned_analytics_service, "MAX_SCALABLE_CSV_ROWS", 2,
            ), self.assertRaises(HTTPException) as row_limited:
                versioned_analytics_service._explore_scalable_csv(
                    **common, started=time.monotonic(),
                )
            self.assertEqual(row_limited.exception.status_code, 413)
            self.assertEqual(row_limited.exception.detail["code"],
                             "dataset_exploration_scalable_row_limit_exceeded")

    def test_scalable_csv_types_nulls_dates_and_quoted_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "edge.csv"
            path.write_text(
                'record_id,amount,observed_at,note\n'
                '1,10,2026-01-01,"a,b"\n'
                '2,,2026-01-02,\n'
                '3,30,2026-01-03,""\n',
                encoding="utf-8",
            )
            with patch.object(
                versioned_analytics_service.project_dataset_service,
                "resolve_project_dataset_version", return_value=resolved(size=11 * 1024 * 1024),
            ), patch.object(
                versioned_analytics_service.data_services,
                "authorize_dataset_input_path", return_value=str(path),
            ):
                result = versioned_analytics_service.explore_dataset_version(
                    tenant_id=1, project_id=PROJECT, user_id=7, dataset_id=DATASET,
                    version_id=VERSION, columns=["record_id", "amount", "observed_at", "note"],
                    filters=[
                        {"field": "amount", "operator": "not_missing", "value": None},
                        {"field": "observed_at", "operator": "gte", "value": "2026-01-02"},
                    ],
                    sort=[{"field": "record_id", "direction": "asc"}], limit=10, offset=0,
                )
        self.assertEqual(result["rows"], [{
            "record_id": 3, "amount": 30, "observed_at": "2026-01-03", "note": None,
        }])
        self.assertEqual(
            {item["name"]: item["technical_type"] for item in result["columns"]},
            {"record_id": "number", "amount": "number", "observed_at": "datetime", "note": "text"},
        )


if __name__ == "__main__":
    unittest.main()

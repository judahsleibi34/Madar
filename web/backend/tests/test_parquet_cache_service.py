from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import duckdb

from data_analysis import services as data_services
from services import (
    adaptive_analytics_service,
    parquet_cache_service,
    versioned_analytics_service,
)


PROJECT = "71111111-1111-4111-8111-111111111111"
DATASET = "72222222-2222-4222-8222-222222222222"
VERSION = "73333333-3333-4333-8333-333333333333"


def _write_csv(path: Path, rows: int = 20_000) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with path.open("wb") as output:
        header = b"row_id,group_key,amount,nullable,text\n"
        output.write(header)
        digest.update(header)
        for index in range(rows):
            nullable = "" if index % 13 == 0 else str(index % 17)
            row = (
                f"{index},g{index % 100:03d},{index % 10000}.{index % 10},"
                f"{nullable},sample-{index % 7}\n"
            ).encode()
            output.write(row)
            digest.update(row)
    return digest.hexdigest()


class ParquetCacheServiceTests(unittest.TestCase):
    def setUp(self):
        from tests.account_schema_fixture import install_legacy_schema
        install_legacy_schema(self)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "tenant_3" / "user_7" / "source.csv"
        self.digest = _write_csv(self.source)
        self.environment = patch.dict(os.environ, {
            "DATA_UPLOAD_DIR": str(self.root), "PARQUET_CACHE_ENABLED": "true",
        }, clear=False)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def args(self, **updates):
        values = {
            "source_path": str(self.source), "tenant_id": 3, "user_id": 7,
            "project_id": PROJECT, "dataset_id": DATASET, "version_id": VERSION,
            "source_hash": self.digest, "source_size": self.source.stat().st_size,
            "declared_rows": 20_000,
        }
        values.update(updates)
        return values

    def test_atomic_artifact_is_private_version_bound_and_reused(self):
        original = self.source.read_bytes()
        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1):
            self.assertIsNone(parquet_cache_service.get_existing(**self.args()))
            first = parquet_cache_service.get_or_create(**self.args())
            second = parquet_cache_service.get_existing(**self.args())
        self.assertIsNotNone(first)
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(first.path, second.path)
        self.assertEqual(first.path.stat().st_mode & 0o777, 0o600)
        manifest = json.loads(first.path.with_suffix(".json").read_text())
        self.assertEqual(manifest["tenant_id"], 3)
        self.assertEqual(manifest["project_id"], PROJECT)
        self.assertEqual(manifest["dataset_id"], DATASET)
        self.assertEqual(manifest["dataset_version_id"], VERSION)
        self.assertEqual(manifest["source_sha256"], self.digest)
        self.assertEqual(manifest["config_sha256"], parquet_cache_service.CONFIG_HASH)
        self.assertTrue(parquet_cache_service.is_metric_compatible(
            first, {"operation": "count", "group_column": "group_key"},
        ))
        self.assertFalse(list(self.root.rglob("*.building")))

    def test_wrong_scope_hash_and_path_are_never_reused(self):
        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1):
            self.assertIsNone(parquet_cache_service.get_or_create(
                **self.args(tenant_id=4),
            ))
            self.assertIsNone(parquet_cache_service.get_or_create(
                **self.args(source_hash="0" * 64),
            ))
            outside = self.root / "outside.csv"
            outside.write_bytes(self.source.read_bytes())
            self.assertIsNone(parquet_cache_service.get_or_create(
                **self.args(source_path=str(outside)),
            ))

    def test_manifest_artifact_and_lock_symlinks_are_refused(self):
        directory = parquet_cache_service._identity_dir(
            tenant_id=3, user_id=7, project_id=PROJECT,
            dataset_id=DATASET, version_id=VERSION,
        )
        artifact, manifest, lock = parquet_cache_service._paths(directory, self.digest)
        outside = self.root / "outside-sensitive"
        outside.write_text('{"secret":true}', encoding="utf-8")
        manifest.symlink_to(outside)
        self.assertIsNone(parquet_cache_service._read_manifest(manifest))
        manifest.unlink()
        artifact.symlink_to(outside)
        data = {
            "format_version": parquet_cache_service.CACHE_FORMAT_VERSION,
            "tenant_id": 3, "user_id": 7, "project_id": PROJECT,
            "dataset_id": DATASET, "dataset_version_id": VERSION,
            "source_filename": self.source.name, "source_sha256": self.digest,
            "source_size_bytes": self.source.stat().st_size,
            "config_sha256": parquet_cache_service.CONFIG_HASH,
            "parquet_size_bytes": outside.stat().st_size, "row_count": 20_000,
            "parquet_sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
            "polars_compatible_columns": [], "polars_numeric_columns": [],
        }
        self.assertIsNone(parquet_cache_service._manifest_matches(
            data, artifact=artifact, tenant_id=3, user_id=7, project_id=PROJECT,
            dataset_id=DATASET, version_id=VERSION, source_name=self.source.name,
            source_hash=self.digest, source_size=self.source.stat().st_size,
            declared_rows=20_000,
        ))
        artifact.unlink()
        lock.symlink_to(outside)
        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1):
            self.assertIsNone(parquet_cache_service.get_or_create(**self.args()))
        self.assertEqual(outside.read_text(encoding="utf-8"), '{"secret":true}')

    def test_integrity_failure_rebuilds_instead_of_accepting_stale_cache(self):
        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1):
            first = parquet_cache_service.get_or_create(**self.args())
            first.path.write_bytes(b"tampered")
            rebuilt = parquet_cache_service.get_or_create(**self.args())
        self.assertIsNotNone(rebuilt)
        self.assertFalse(rebuilt.cache_hit)
        self.assertNotEqual(rebuilt.path.read_bytes(), b"tampered")
        self.assertEqual(rebuilt.sha256, parquet_cache_service._sha256(rebuilt.path))

    def test_failed_conversion_leaves_no_partial_or_manifest(self):
        def fail(_source, target, **_kwargs):
            target.write_bytes(b"partial")
            raise TimeoutError("synthetic cancellation")

        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1), \
                patch.object(parquet_cache_service, "_convert", side_effect=fail):
            self.assertIsNone(parquet_cache_service.get_or_create(**self.args()))
        self.assertFalse(list(self.root.rglob("*.building")))
        self.assertFalse(list(self.root.rglob("*.parquet")))
        self.assertFalse(list(self.root.rglob("*.json")))

    def test_isolated_conversion_rss_limit_kills_without_publication(self):
        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1), \
                patch.object(
                    parquet_cache_service, "_resident_bytes",
                    return_value=parquet_cache_service.CONVERSION_RSS_BYTES + 1,
                ):
            self.assertIsNone(parquet_cache_service.get_or_create(**self.args()))
        self.assertFalse(list(self.root.rglob("*.building")))
        self.assertFalse(list(self.root.rglob("*.parquet")))
        self.assertFalse(list(self.root.rglob("*.json")))

    def test_ttl_cleanup_and_source_lifecycle_remove_artifacts(self):
        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1):
            artifact = parquet_cache_service.get_or_create(**self.args())
        manifest = artifact.path.with_suffix(".json")
        old = time.time() - parquet_cache_service.CACHE_TTL_SECONDS - 1
        os.utime(manifest, (old, old))
        result = parquet_cache_service.cleanup_cache()
        self.assertGreaterEqual(result["removed"], 1)
        self.assertFalse(artifact.path.exists())

        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1):
            artifact = parquet_cache_service.get_or_create(**self.args())
        self.assertEqual(parquet_cache_service.remove_for_source(self.source), 1)
        self.assertFalse(artifact.path.exists())

    def test_cross_process_lock_prevents_mutation_before_admission(self):
        directory = parquet_cache_service._identity_dir(
            tenant_id=3, user_id=7, project_id=PROJECT, dataset_id=DATASET, version_id=VERSION,
        )
        artifact, manifest, lock = parquet_cache_service._paths(directory, self.digest)
        artifact.write_bytes(b'owned repair pending')
        manifest.write_text('{}')
        child = subprocess.Popen([
            sys.executable, '-c',
            'import fcntl,sys; f=open(sys.argv[1],"a+b"); '
            'fcntl.flock(f,fcntl.LOCK_EX); print("ready",flush=True); sys.stdin.read(1)',
            str(lock),
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        try:
            self.assertEqual(child.stdout.readline().strip(), b'ready')
            with patch.object(parquet_cache_service, 'MIN_SOURCE_BYTES', 1):
                self.assertIsNone(parquet_cache_service.get_or_create(**self.args()))
            self.assertTrue(artifact.exists(), 'another process must not mutate a held conversion')
            self.assertEqual(artifact.read_bytes(), b'owned repair pending')
        finally:
            child.communicate(b'x', timeout=5)

    def test_cache_tenant_quota_evicts_owned_artifact(self):
        with patch.object(parquet_cache_service, 'MIN_SOURCE_BYTES', 1):
            artifact = parquet_cache_service.get_or_create(**self.args())
        with patch.object(parquet_cache_service, 'MAX_TENANT_CACHE_BYTES', artifact.size_bytes - 1):
            result = parquet_cache_service.cleanup_cache()
        self.assertEqual(result['bytes'], 0)
        self.assertFalse(artifact.path.exists())

    def test_cross_tenant_cache_directory_symlink_is_refused(self):
        root = parquet_cache_service._cache_root()
        foreign = root / 'tenant_4'
        foreign.mkdir()
        (root / 'tenant_3').symlink_to(foreign, target_is_directory=True)
        with self.assertRaises(PermissionError):
            parquet_cache_service._identity_dir(
                tenant_id=3, user_id=7, project_id=PROJECT,
                dataset_id=DATASET, version_id=VERSION,
            )

    def test_fenced_host_unlink_also_removes_derived_files(self):
        from services import data_deletion_service
        with patch.object(parquet_cache_service, 'MIN_SOURCE_BYTES', 1):
            artifact = parquet_cache_service.get_or_create(**self.args())
        with patch.dict(data_deletion_service.HOST_RESOURCE_ROOTS, {'host_dataset': lambda: self.root}):
            data_deletion_service._unlink_host_resource({
                'resource_kind': 'host_dataset', 'resource_key': 'tenant_3/user_7/source.csv',
            })
        self.assertFalse(self.source.exists())
        self.assertFalse(artifact.path.exists())

    def test_exploration_csv_and_parquet_results_match(self):
        query = dict(
            storage_identifier=self.source.name, tenant_id=3, user_id=7,
            columns=["row_id", "group_key", "amount", "nullable"],
            filters=[{"field": "group_key", "operator": "eq", "value": "g099"}],
            sort=[{"field": "amount", "direction": "desc"}], limit=100, offset=7,
        )
        with patch.object(
            versioned_analytics_service.data_services, "authorize_dataset_input_path",
            return_value=str(self.source),
        ), patch.object(parquet_cache_service, "get_or_create", return_value=None):
            csv_result = versioned_analytics_service._explore_scalable_csv(
                **query, started=time.monotonic(),
            )
        with patch.object(
            versioned_analytics_service.data_services, "authorize_dataset_input_path",
            return_value=str(self.source),
        ), patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1):
            parquet_result = versioned_analytics_service._explore_scalable_csv(
                **query, started=time.monotonic(), project_id=PROJECT,
                dataset_id=DATASET, version_id=VERSION, content_hash=self.digest,
                declared_rows=20_000,
            )
        self.assertEqual(parquet_result, csv_result)

    def test_conversion_schema_preserves_nulls_and_decimal_values(self):
        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1):
            artifact = parquet_cache_service.get_or_create(**self.args())
        connection = duckdb.connect(":memory:")
        try:
            csv = connection.execute(
                "select count(*), count(nullable), sum(amount), avg(amount), min(amount), max(amount) "
                "from read_csv_auto(?, header=true, sample_size=-1, strict_mode=true)",
                [str(self.source)],
            ).fetchone()
            parquet = connection.execute(
                "select count(*), count(nullable), sum(amount), avg(amount), min(amount), max(amount) "
                "from read_parquet(?)", [str(artifact.path)],
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(parquet, csv)

    def test_polars_scalar_and_grouped_metrics_match_csv(self):
        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1):
            artifact = parquet_cache_service.get_or_create(**self.args())
        metrics = [{"operation": "count", "label": "Count"}]
        for operation in ("count", "sum", "mean", "min", "max"):
            metrics.append({
                "operation": operation, "label": operation,
                "value_column": "amount", "group_column": "group_key",
            })
        for metric in metrics:
            with self.subTest(metric=metric):
                csv = adaptive_analytics_service.run_large_metric(
                    authorized_path=str(self.source), metric=metric, language="en",
                    symbols={}, declared_rows=20_000,
                    source_size_bytes=self.source.stat().st_size, source_format="csv",
                )
                parquet = adaptive_analytics_service.run_large_metric(
                    authorized_path=str(artifact.path), metric=metric, language="en",
                    symbols={}, declared_rows=20_000,
                    source_size_bytes=self.source.stat().st_size, source_format="parquet",
                )
                self.assertEqual(parquet["rows_used"], csv["rows_used"])
                self.assertEqual(parquet["result"], csv["result"])

    def test_metric_selection_requires_matching_polars_types(self):
        padded = self.source.with_name("padded.csv")
        padded.write_text(
            "group_key,amount\n" + "".join(
                f"g{index % 5},{index % 100:08d}\n" for index in range(20_000)
            ), encoding="utf-8",
        )
        padded_hash = hashlib.sha256(padded.read_bytes()).hexdigest()
        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1):
            padded_artifact = parquet_cache_service.get_or_create(**self.args(
                source_path=str(padded), source_hash=padded_hash,
                source_size=padded.stat().st_size, declared_rows=20_000,
            ))
        self.assertFalse(parquet_cache_service.is_metric_compatible(
            padded_artifact, {"operation": "sum", "value_column": "amount"},
        ))

        source = self.source.with_name("integers.csv")
        source.write_text(
            "group_key,amount\n" + "".join(
                f"g{index % 5},{index % 100}\n" for index in range(20_000)
            ), encoding="utf-8",
        )
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1):
            integer_artifact = parquet_cache_service.get_or_create(**self.args(
                source_path=str(source), source_hash=digest,
                source_size=source.stat().st_size, declared_rows=20_000,
                version_id="73333333-3333-4333-8333-333333333334",
            ))
        self.assertTrue(parquet_cache_service.is_metric_compatible(
            integer_artifact,
            {"operation": "sum", "value_column": "amount", "group_column": "group_key"},
        ))

    def test_adaptive_metric_reuses_only_compatible_existing_artifact(self):
        version = {
            "id": VERSION, "size_bytes": 11 * 1024 * 1024,
            "content_hash": self.digest, "file_metadata": {"rows": 20_000},
        }
        identity = {"project_id": PROJECT, "dataset_id": DATASET, "version_id": VERSION}
        metric = {"operation": "count", "label": "Count"}
        with patch.object(
            data_services, "authorize_dataset_input_path", return_value=str(self.source),
        ), patch.object(
            parquet_cache_service, "get_existing", return_value=None,
        ), patch.object(
            adaptive_analytics_service, "run_large_metric", return_value={"ok": True},
        ) as execute:
            data_services.run_assisted_analysis(
                input_path=self.source.name, cleaning_actions=[], question=None,
                metric=metric, language="en", symbols={}, tenant_id="3", user_id="7",
                dataset_version=version, dataset_identity=identity,
            )
        self.assertEqual(execute.call_args.kwargs["authorized_path"], str(self.source))
        self.assertEqual(execute.call_args.kwargs["source_format"], "csv")

        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1):
            artifact = parquet_cache_service.get_or_create(**self.args())
        with patch.object(
            data_services, "authorize_dataset_input_path", return_value=str(self.source),
        ), patch.object(
            parquet_cache_service, "get_existing", return_value=artifact,
        ), patch.object(
            adaptive_analytics_service, "run_large_metric", return_value={"ok": True},
        ) as execute:
            data_services.run_assisted_analysis(
                input_path=self.source.name, cleaning_actions=[], question=None,
                metric=metric, language="en", symbols={}, tenant_id="3", user_id="7",
                dataset_version=version, dataset_identity=identity,
            )
        self.assertEqual(execute.call_args.kwargs["authorized_path"], str(artifact.path))
        self.assertEqual(execute.call_args.kwargs["source_format"], "parquet")

    def test_date_timezone_dst_and_disclosures_match_but_cache_is_not_selected(self):
        source = self.source.with_name("dates.csv")
        source.write_text(
            "event_date,amount\n"
            "2026-03-08T06:30:00Z,10\n2026-03-08T07:30:00Z,20\n"
            ",30\ninvalid,40\n2026-03-09T03:30:00Z,50\n",
            encoding="utf-8",
        )
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1):
            artifact = parquet_cache_service.get_or_create(**self.args(
                source_path=str(source), source_hash=digest,
                source_size=source.stat().st_size, declared_rows=5,
            ))
        metric = {
            "operation": "date_aggregate", "label": "DST",
            "date_column": "event_date", "value_column": "amount",
            "aggregation": "sum", "period": "day", "timezone": "America/New_York",
            "start_date": "2026-03-08", "end_date": "2026-03-09",
        }
        csv = adaptive_analytics_service.run_large_metric(
            authorized_path=str(source), metric=metric, language="en", symbols={},
            declared_rows=5, source_size_bytes=source.stat().st_size, source_format="csv",
        )
        parquet = adaptive_analytics_service.run_large_metric(
            authorized_path=str(artifact.path), metric=metric, language="en", symbols={},
            declared_rows=5, source_size_bytes=source.stat().st_size,
            source_format="parquet",
        )
        self.assertEqual(parquet["result"], csv["result"])
        mappings = parquet["result"]["metadata"]["mappings_used"]
        self.assertEqual(mappings["invalid_date_count"], 1)
        self.assertEqual(mappings["missing_date_count"], 1)
        self.assertIn("-05:00", mappings["start_inclusive"])
        self.assertIn("-04:00", mappings["end_exclusive"])

    def test_concurrent_conversion_has_one_publisher_and_bounded_fallback(self):
        original_convert = parquet_cache_service._convert
        entered = threading.Event()
        release = threading.Event()
        outcomes = []

        def slow_convert(*args, **kwargs):
            entered.set()
            release.wait(5)
            return original_convert(*args, **kwargs)

        def convert():
            outcomes.append(parquet_cache_service.get_or_create(**self.args()))

        with patch.object(parquet_cache_service, "MIN_SOURCE_BYTES", 1), \
                patch.object(parquet_cache_service, "_convert", side_effect=slow_convert):
            first = threading.Thread(target=convert)
            first.start()
            self.assertTrue(entered.wait(2))
            second = threading.Thread(target=convert)
            second.start()
            second.join(2)
            release.set()
            first.join(5)
        self.assertEqual(sum(item is not None for item in outcomes), 1)
        self.assertEqual(len(list(self.root.rglob("*.parquet"))), 1)
        self.assertFalse(list(self.root.rglob("*.building")))


if __name__ == "__main__":
    unittest.main()

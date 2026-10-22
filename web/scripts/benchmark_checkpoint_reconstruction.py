#!/usr/bin/env python3
"""Measured bounded reconstruction benchmark; not a production claim."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import resource
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from services import project_dataset_checkpoint_service as checkpoints
from services.checkpoint_streaming import workspace_bytes


class Query:
    def __init__(self, rows):
        self.rows, self.window, self.maximum, self.orders = list(rows), None, None, []
    def select(self, *_args): return self
    def eq(self, key, value): self.rows = [row for row in self.rows if row.get(key) == value]; return self
    def lte(self, key, value): self.rows = [row for row in self.rows if row.get(key) <= value]; return self
    def order(self, key, desc=False): self.orders.append((key, desc)); return self
    def range(self, start, end): self.window = (start, end); return self
    def limit(self, value): self.maximum = value; return self
    def execute(self):
        rows = self.rows
        for key, desc in reversed(self.orders): rows.sort(key=lambda row: row.get(key), reverse=desc)
        if self.window is not None: rows = rows[self.window[0]:self.window[1] + 1]
        if self.maximum is not None: rows = rows[:self.maximum]
        return SimpleNamespace(data=rows)


class SyntheticHistoryQuery:
    """Generate only the requested REST page so fixture memory does not dominate."""
    def __init__(self, count): self.count, self.window = count, (0, count - 1)
    def select(self, *_args): return self
    def eq(self, *_args): return self
    def lte(self, *_args): return self
    def order(self, *_args, **_kwargs): return self
    def range(self, start, end): self.window = (start, min(end, self.count - 1)); return self
    def execute(self):
        start, end = self.window
        rows = []
        if start <= end:
            for index in range(start + 1, end + 2):
                payload = {"amount": index, "label": f"Order {index}"}
                body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                rows.append({
                    "tenant_id": 1, "project_id": "project", "source_id": "source",
                    "source_resource_id": "resource", "dataset_id": "dataset",
                    "storage_object_id": "object", "row_ordinal": index,
                    "source_record_id": f"record-{index:06d}", "operation": "upsert",
                    "outcome": "inserted", "content_hash": hashlib.sha256(body.encode()).hexdigest(),
                    "committed_revision": 1,
                })
        return SimpleNamespace(data=rows)


class Client:
    def __init__(self, *, count, tables): self.count, self.tables = count, tables
    def table(self, name):
        if name == "data_dataset_record_changes":
            return SyntheticHistoryQuery(self.count)
        return Query(self.tables.get(name, []))


def benchmark(count: int) -> dict:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        chunk = root / "checkpoint-benchmark.csv"
        with chunk.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "_source_record_id", "_change_operation", "_content_hash", "_payload_json"
            ], lineterminator="\n")
            writer.writeheader()
            for ordinal in range(1, count + 1):
                record_id = f"record-{ordinal:06d}"
                payload = {"amount": ordinal, "label": f"Order {ordinal}"}
                content = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                writer.writerow({"_source_record_id": record_id, "_change_operation": "upsert",
                                 "_content_hash": hashlib.sha256(content.encode()).hexdigest(),
                                 "_payload_json": content})
        client = Client(count=count, tables={
            "data_source_resources": [{
                "id": "resource", "tenant_id": 1, "project_id": "project",
                "source_id": "source", "dataset_id": "dataset",
                "committed_revision": 1, "resource_key": "orders",
            }],
            "storage_objects": [{
                "id": "object", "tenant_id": 1, "user_id": 7, "category": "dataset",
                "status": "active", "storage_key": "tenant_1/user_7/checkpoint-benchmark.csv",
            }],
        })
        tracemalloc.start()
        started = time.perf_counter()
        with (
            patch.object(checkpoints.project_data_source_service, "get_project_data_source",
                         return_value={"id": "source"}),
            patch.object(checkpoints.data_services, "get_user_upload_dir", return_value=root),
        ):
            artifact = checkpoints.reconstruct_dataset_revision(
                tenant_id=1, project_id="project", source_id="source", resource_id="resource",
                dataset_id="dataset", user_id=7, target_revision=1, client=client,
            )
        elapsed = time.perf_counter() - started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        verification_started = time.perf_counter()
        verification_hash = hashlib.sha256()
        with artifact.csv_path.open("rb") as checkpoint_file:
            while block := checkpoint_file.read(64 * 1024):
                verification_hash.update(block)
        hash_verification_seconds = time.perf_counter() - verification_started
        if verification_hash.hexdigest() != artifact.checkpoint_sha256:
            raise RuntimeError("checkpoint_hash_verification_failed")
        try:
            return {
                "records": count, "events": artifact.change_count,
                "elapsed_seconds": round(elapsed, 6),
                "records_per_second": round(count / elapsed, 2),
                "peak_python_bytes": peak,
                "peak_resident_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                "temporary_disk_bytes": workspace_bytes(artifact.workspace),
                "history_chunk_bytes": chunk.stat().st_size,
                "immutable_bytes_read": artifact.immutable_bytes_read,
                "checkpoint_csv_bytes": artifact.checkpoint_size_bytes,
                "database_reads": artifact.database_reads,
                "database_writes": artifact.database_writes,
                "hash_verification_seconds": round(hash_verification_seconds, 6),
                "checkpoint_sha256": artifact.checkpoint_sha256,
                "state_hash": artifact.state_hash,
            }
        finally:
            artifact.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=int)
    args = parser.parse_args()
    if args.records is not None:
        print(json.dumps(benchmark(args.records), sort_keys=True))
        return
    results = []
    for count in (10_000, 50_000, 100_000):
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--records", str(count)],
            check=True, capture_output=True, text=True,
        )
        results.append(json.loads(completed.stdout.strip().splitlines()[-1]))
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    main()

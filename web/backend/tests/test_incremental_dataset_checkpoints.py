import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services import project_dataset_checkpoint_service
from services.data_source_api_provider import SyntheticOrdersProvider, fetch_bounded_records


class FakeQuery:
    def __init__(self, rows):
        self.rows = [dict(row) for row in rows]
        self.window = None
        self.maximum = None
        self.orders = []

    def select(self, *_args): return self
    def eq(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) == value]
        return self
    def lte(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) <= value]
        return self
    def order(self, field, desc=False):
        self.orders.append((field, desc))
        return self
    def range(self, start, end): self.window = (start, end); return self
    def limit(self, value): self.maximum = value; return self
    def execute(self):
        rows = self.rows
        for field, desc in reversed(self.orders):
            rows.sort(key=lambda row: row.get(field), reverse=desc)
        if self.window is not None:
            rows = rows[self.window[0]:self.window[1] + 1]
        if self.maximum is not None:
            rows = rows[:self.maximum]
        return SimpleNamespace(data=rows)


class FakeClient:
    def __init__(self, tables): self.tables = tables
    def table(self, name): return FakeQuery(self.tables.get(name, []))


class IncrementalCheckpointTests(unittest.TestCase):
    def test_exact_revision_reconstruction_ignores_concurrent_later_commit(self):
        batches = [
            fetch_bounded_records(SyntheticOrdersProvider(number), resource_type="orders")
            for number in (1, 2, 3)
        ]
        outcomes = [
            ["inserted", "inserted", "inserted"],
            ["updated", "inserted"],
            ["duplicate", "deleted", "stale_ignored"],
        ]
        storage = []
        history = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for revision, (batch, batch_outcomes) in enumerate(zip(batches, outcomes), 1):
                object_id = f"object-{revision}"
                filename = f"chunk{revision}.csv"
                (root / filename).write_bytes(batch.csv_bytes)
                storage.append({
                    "id": object_id, "tenant_id": 1, "user_id": 7,
                    "category": "dataset", "status": "active",
                    "storage_key": f"tenant_1/user_7/{filename}",
                })
                for change, outcome in zip(batch.changes, batch_outcomes):
                    history.append({
                        "tenant_id": 1, "project_id": "project", "source_id": "source",
                        "source_resource_id": "resource", "dataset_id": "dataset",
                        "storage_object_id": object_id, "row_ordinal": change["ordinal"],
                        "source_record_id": change["source_record_id"],
                        "operation": change["operation"], "outcome": outcome,
                        "content_hash": change["content_hash"],
                        "committed_revision": revision,
                    })

            later = fetch_bounded_records(SyntheticOrdersProvider(1), resource_type="customers")
            (root / "chunk4.csv").write_bytes(later.csv_bytes)
            storage.append({
                "id": "object-4", "tenant_id": 1, "user_id": 7,
                "category": "dataset", "status": "active",
                "storage_key": "tenant_1/user_7/chunk4.csv",
            })
            change = later.changes[0]
            history.append({
                "tenant_id": 1, "project_id": "project", "source_id": "source",
                "source_resource_id": "resource", "dataset_id": "dataset",
                "storage_object_id": "object-4", "row_ordinal": 1,
                "source_record_id": change["source_record_id"],
                "operation": change["operation"], "outcome": "inserted",
                "content_hash": change["content_hash"], "committed_revision": 4,
            })
            client = FakeClient({
                "data_source_resources": [{
                    "id": "resource", "dataset_id": "dataset",
                    "committed_revision": 4, "resource_key": "orders",
                    "tenant_id": 1, "project_id": "project", "source_id": "source",
                }],
                "data_dataset_record_changes": history,
                "storage_objects": storage,
            })
            with (
                patch.object(
                    project_dataset_checkpoint_service.project_data_source_service,
                    "get_project_data_source", return_value={"id": "source"},
                ),
                patch.object(
                    project_dataset_checkpoint_service.data_services,
                    "get_user_upload_dir", return_value=root,
                ),
            ):
                artifacts = [
                    project_dataset_checkpoint_service.reconstruct_dataset_revision(
                        tenant_id=1, project_id="project", source_id="source",
                        resource_id="resource", dataset_id="dataset", user_id=7,
                        target_revision=revision, client=client,
                    )
                    for revision in (1, 2, 3)
                ]
                try:
                    rows = []
                    for artifact in artifacts:
                        with artifact.csv_path.open(
                            "r", encoding="utf-8", newline="",
                        ) as checkpoint_file:
                            rows.append(list(csv.DictReader(checkpoint_file)))
                    hashes = [artifact.state_hash for artifact in artifacts]
                finally:
                    for artifact in artifacts:
                        artifact.cleanup()

        self.assertEqual([row["_source_record_id"] for row in rows[0]], ["A", "B", "C"])
        revision_two = {row["_source_record_id"]: row for row in rows[1]}
        self.assertEqual(set(revision_two), {"A", "B", "C", "D"})
        self.assertEqual(revision_two["B"]["amount"], "25")
        self.assertEqual([row["_source_record_id"] for row in rows[2]], ["B", "C", "D"])
        self.assertFalse(any(row["_source_record_id"] == "customer-A" for row in rows[2]))
        self.assertEqual(len(set(hashes)), 3)
        expected_revision_three = {
            "B": {"name": "Order B", "amount": 25},
            "C": {"name": "Order C", "amount": 30},
            "D": {"name": "Order D", "amount": 40},
        }
        expected_hash = hashlib.sha256(json.dumps(
            expected_revision_three, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        self.assertEqual(hashes[2], expected_hash)


if __name__ == "__main__":
    unittest.main()

import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from services import asset_registry_service


class Response:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, db, table):
        self.db, self.table = db, table
        self.filters, self.payload, self.operation, self.limit_value = [], None, "select", None

    def select(self, *_args): return self
    def eq(self, key, value): self.filters.append(("eq", key, value)); return self
    def lte(self, key, value): self.filters.append(("lte", key, value)); return self
    def limit(self, value): self.limit_value = value; return self
    def insert(self, payload): self.operation, self.payload = "insert", payload; return self
    def update(self, payload): self.operation, self.payload = "update", payload; return self
    def delete(self): self.operation = "delete"; return self

    def execute(self):
        table = self.db.setdefault(self.table, [])
        rows = [row for row in table if all(
            row.get(key) == value if kind == "eq" else str(row.get(key) or "") <= str(value)
            for kind, key, value in self.filters
        )]
        if self.limit_value is not None: rows = rows[:self.limit_value]
        if self.operation == "insert":
            payloads = self.payload if isinstance(self.payload, list) else [self.payload]
            inserted = []
            for payload in payloads:
                row = {"id": payload.get("id", f"{self.table}-{len(table) + 1}"), **payload}
                table.append(row); inserted.append(dict(row))
            return Response(inserted)
        if self.operation == "update":
            for row in rows: row.update(self.payload)
            return Response([dict(row) for row in rows])
        if self.operation == "delete":
            for row in rows: table.remove(row)
            return Response([dict(row) for row in rows])
        return Response([dict(row) for row in rows])


class Client:
    def __init__(self): self.data = {}
    def setdefault(self, *args): return self.data.setdefault(*args)
    def table(self, name): return Query(self, name)


class AssetRegistryTests(unittest.TestCase):
    def test_register_hashes_content_and_never_uses_original_path(self):
        client = Client()
        row = asset_registry_service.register_builder_asset(
            tenant_id=7,
            uploader_user_id=3,
            storage_key="tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png",
            original_filename="../../logo.png",
            managed_filename="0123456789abcdef0123456789abcdef.png",
            mime_type="image/png",
            content=b"image",
            client=client,
        )
        self.assertEqual(row["sha256"], hashlib.sha256(b"image").hexdigest())
        self.assertEqual(row["original_filename"], "logo.png")
        self.assertNotIn("..", row["storage_key"])

    def test_reference_extraction_is_tenant_scoped(self):
        schema = {"logo": "/uploads/tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png", "other": "/uploads/tenant_8/builder_assets/abcdefabcdefabcdefabcdefabcdefab.webp"}
        refs = asset_registry_service.extract_builder_asset_references(schema, tenant_id=7)
        self.assertEqual(list(refs), ["tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"])

    def test_cross_tenant_managed_document_reference_is_rejected(self):
        schema = {
            "document": "/uploads/tenant_8/builder_assets/abcdefabcdefabcdefabcdefabcdefab.pdf",
        }
        with self.assertRaisesRegex(ValueError, "builder_asset_tenant_mismatch"):
            asset_registry_service.require_builder_asset_tenant_ownership(
                schema,
                tenant_id=7,
            )

    def test_reconcile_activates_then_unreferences_with_grace(self):
        client = Client()
        key = "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"
        client.data["builder_assets"] = [{"id": "asset-1", "tenant_id": 7, "storage_key": key, "status": "unreferenced"}]
        first = asset_registry_service.reconcile_project_asset_references(
            project_id="project-1", tenant_id=7, schema={"image": f"/uploads/{key}"}, client=client
        )
        self.assertEqual(first["referenced"], 1)
        self.assertEqual(client.data["builder_assets"][0]["status"], "active")
        asset_registry_service.reconcile_project_asset_references(
            project_id="project-1", tenant_id=7, schema={}, client=client
        )
        self.assertEqual(client.data["builder_assets"][0]["status"], "unreferenced")
        self.assertIsNotNone(client.data["builder_assets"][0]["retention_until"])

    def test_cleanup_is_dry_run_by_default_and_rechecks_checksum(self):
        client = Client()
        with tempfile.TemporaryDirectory() as root:
            storage = Path(root)
            key = "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"
            path = storage / key
            path.parent.mkdir(parents=True)
            path.write_bytes(b"image")
            client.data["builder_assets"] = [{
                "id": "asset-1", "tenant_id": 7, "storage_key": key, "status": "unreferenced",
                "retention_until": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                "sha256": hashlib.sha256(b"image").hexdigest(),
            }]
            dry = asset_registry_service.cleanup_expired_builder_assets(storage_root=storage, client=client)
            self.assertEqual(dry["deleted"], 0)
            self.assertTrue(path.exists())
            with patch.object(asset_registry_service, "release_storage", return_value=True):
                applied = asset_registry_service.cleanup_expired_builder_assets(storage_root=storage, client=client, dry_run=False)
            self.assertEqual(applied["deleted"], 1)
            self.assertFalse(path.exists())

    def test_cleanup_refuses_hash_mismatch(self):
        client = Client()
        with tempfile.TemporaryDirectory() as root:
            storage = Path(root)
            key = "tenant_7/builder_assets/abcdefabcdefabcdefabcdefabcdefab.webp"
            path = storage / key
            path.parent.mkdir(parents=True)
            path.write_bytes(b"tampered")
            client.data["builder_assets"] = [{
                "id": "asset-2", "tenant_id": 7, "storage_key": key, "status": "unreferenced",
                "retention_until": "2020-01-01T00:00:00+00:00",
                "sha256": hashlib.sha256(b"original").hexdigest(),
            }]
            result = asset_registry_service.cleanup_expired_builder_assets(
                storage_root=storage, client=client, dry_run=False
            )
            self.assertEqual(result["skipped"], 1)
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()

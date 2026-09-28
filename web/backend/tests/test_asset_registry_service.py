import hashlib
import json
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
    def filter(self, key, operator, value):
        assert operator == "cs"
        self.filters.append(("contains", key, json.loads(value)))
        return self
    def lte(self, key, value): self.filters.append(("lte", key, value)); return self
    def limit(self, value): self.limit_value = value; return self
    def insert(self, payload): self.operation, self.payload = "insert", payload; return self
    def update(self, payload): self.operation, self.payload = "update", payload; return self
    def delete(self): self.operation = "delete"; return self

    def execute(self):
        self.db.queries.append(self.table)
        table = self.db.setdefault(self.table, [])
        rows = [row for row in table if all(
            row.get(key) == value if kind == "eq" else (
                set(value) <= set(row.get(key) or []) if kind == "contains"
                else str(row.get(key) or "") <= str(value)
            )
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
    def __init__(self): self.data, self.queries = {}, []
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

    def test_failed_upload_registration_rollback_is_tenant_scoped(self):
        client = Client()
        client.data["builder_assets"] = [
            {"id": "asset-1", "tenant_id": 7},
            {"id": "asset-1", "tenant_id": 8},
        ]

        asset_registry_service.delete_builder_asset_registration(
            asset_id="asset-1",
            tenant_id=7,
            client=client,
        )

        self.assertEqual(
            client.data["builder_assets"],
            [{"id": "asset-1", "tenant_id": 8}],
        )

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

    def test_store_logo_replacement_recounts_both_assets(self):
        client = Client()
        old = "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"
        new = "tenant_7/builder_assets/abcdefabcdefabcdefabcdefabcdefab.webp"
        client.data["builder_assets"] = [
            {"id": "old", "tenant_id": 7, "storage_key": old, "status": "active"},
            {"id": "new", "tenant_id": 7, "storage_key": new, "status": "unreferenced"},
        ]
        client.data["website_settings"] = [{"tenant_id": 7, "subdomain": "olive", "logo_url": f"/uploads/{old}"}]
        for key in (old, new):
            asset_registry_service.refresh_builder_asset_reference_state(tenant_id=7, storage_key=key, client=client)
        self.assertEqual([row["reference_count"] for row in client.data["builder_assets"]], [1, 0])
        client.data["website_settings"][0]["logo_url"] = f"/uploads/{new}"
        for key in (old, new):
            asset_registry_service.refresh_builder_asset_reference_state(tenant_id=7, storage_key=key, client=client)
        self.assertEqual([row["status"] for row in client.data["builder_assets"]], ["unreferenced", "active"])
        self.assertIsNotNone(client.data["builder_assets"][0]["retention_until"])
        client.data["website_settings"][0]["logo_url"] = ""
        asset_registry_service.refresh_builder_asset_reference_state(tenant_id=7, storage_key=new, client=client)
        self.assertEqual(client.data["builder_assets"][1]["status"], "unreferenced")

    def test_catalog_and_builder_references_keep_replaced_logo_available(self):
        client = Client()
        key = "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"
        client.data["builder_assets"] = [{"id": "asset-1", "tenant_id": 7, "storage_key": key, "status": "active"}]
        client.data["website_settings"] = [{"tenant_id": 7, "subdomain": "olive", "logo_url": f"/uploads/{key}"}]
        client.data["ecommerce_products"] = [{"id": "product-1", "tenant_id": 7, "status": "active", "images": [f"/uploads/{key}"]}]
        client.data["ecommerce_product_variants"] = [{
            "tenant_id": 7, "product_id": "product-1", "active": True, "images": [f"/uploads/{key}"],
        }]
        client.data["builder_asset_references"] = [{"asset_id": "asset-1", "project_id": "project-1"}]
        asset_registry_service.refresh_builder_asset_reference_state(tenant_id=7, storage_key=key, client=client)
        self.assertEqual(client.data["builder_assets"][0]["reference_count"], 4)
        client.data["website_settings"][0]["logo_url"] = ""
        asset_registry_service.refresh_builder_asset_reference_state(tenant_id=7, storage_key=key, client=client)
        self.assertEqual(client.data["builder_assets"][0]["status"], "active")
        self.assertEqual(client.data["builder_assets"][0]["reference_count"], 3)

    def test_draft_catalog_asset_stays_registered_for_retention(self):
        client = Client()
        key = "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"
        client.data["builder_assets"] = [{"id": "asset-1", "tenant_id": 7, "storage_key": key, "status": "unreferenced"}]
        client.data["ecommerce_products"] = [{"tenant_id": 7, "status": "draft", "images": [f"/uploads/{key}"]}]
        asset_registry_service.refresh_builder_asset_reference_state(tenant_id=7, storage_key=key, client=client)
        self.assertEqual(client.data["builder_assets"][0]["status"], "active")
        self.assertEqual(client.data["builder_assets"][0]["reference_count"], 1)
        self.assertEqual(asset_registry_service.nonproject_asset_reference_count(
            tenant_id=7, storage_key=key, public_only=True, client=client,
        ), 0)

    def test_landing_slide_replacement_recounts_and_preserves_other_references(self):
        client = Client()
        old = "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"
        new = "tenant_7/builder_assets/abcdefabcdefabcdefabcdefabcdefab.webp"
        client.data["builder_assets"] = [
            {"id": "old", "tenant_id": 7, "storage_key": old, "status": "unreferenced"},
            {"id": "new", "tenant_id": 7, "storage_key": new, "status": "unreferenced"},
        ]
        settings = {"tenant_id": 7, "subdomain": "olive", "ecommerce_theme": {
            "landing_page": {"slides": [{"image_url": f"/uploads/{old}"}]},
        }}
        client.data["website_settings"] = [settings]
        client.data["ecommerce_products"] = [{
            "id": "product-1", "tenant_id": 7, "status": "active", "images": [f"/uploads/{old}"],
        }]
        asset_registry_service.refresh_builder_asset_reference_state(tenant_id=7, storage_key=old, client=client)
        self.assertEqual(client.data["builder_assets"][0]["reference_count"], 2)
        self.assertEqual(asset_registry_service.nonproject_asset_reference_count(
            tenant_id=7, storage_key=old, public_only=True, client=client,
        ), 1)
        settings["ecommerce_theme"]["landing_page"]["slides"] = [{"image_url": f"/uploads/{new}"}]
        for key in (old, new):
            asset_registry_service.refresh_builder_asset_reference_state(tenant_id=7, storage_key=key, client=client)
        self.assertEqual([row["reference_count"] for row in client.data["builder_assets"]], [1, 1])
        self.assertEqual([row["status"] for row in client.data["builder_assets"]], ["active", "active"])
        client.data["ecommerce_products"].clear()
        asset_registry_service.refresh_builder_asset_reference_state(tenant_id=7, storage_key=old, client=client)
        self.assertEqual(client.data["builder_assets"][0]["status"], "unreferenced")

    def test_public_catalog_usage_hint_prioritizes_exact_database_lookup(self):
        client = Client()
        key = "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"
        client.data["ecommerce_products"] = [{
            "tenant_id": 7, "status": "active", "images": [f"/uploads/{key}"],
        }]
        count = asset_registry_service.nonproject_asset_reference_count(
            tenant_id=7, storage_key=key, public_only=True,
            usage_hint="ecommerce_product", client=client,
        )
        self.assertEqual(count, 1)
        self.assertEqual(client.queries, ["ecommerce_products"])
        client.queries.clear()
        client.data["ecommerce_products"][0]["status"] = "draft"
        self.assertEqual(asset_registry_service.nonproject_asset_reference_count(
            tenant_id=7, storage_key=key, public_only=True,
            usage_hint="ecommerce_product", client=client,
        ), 0)
        self.assertEqual(len(client.queries), 5)

    def test_stale_usage_hint_falls_back_to_live_reference(self):
        client = Client()
        key = "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"
        client.data["website_settings"] = [{
            "tenant_id": 7, "subdomain": "olive", "logo_url": f"/uploads/{key}",
        }]
        self.assertEqual(asset_registry_service.nonproject_asset_reference_count(
            tenant_id=7, storage_key=key, public_only=True,
            usage_hint="ecommerce_product", client=client,
        ), 1)
        self.assertEqual(client.queries, ["ecommerce_products", "website_settings"])

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

    def test_cleanup_preserves_persisted_store_logo_despite_stale_registry_state(self):
        client = Client()
        with tempfile.TemporaryDirectory() as root:
            key = "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"
            path = Path(root) / key
            path.parent.mkdir(parents=True)
            path.write_bytes(b"image")
            client.data["builder_assets"] = [{
                "id": "asset-1", "tenant_id": 7, "storage_key": key,
                "status": "unreferenced", "reference_count": 0,
                "retention_until": "2020-01-01T00:00:00+00:00",
                "sha256": hashlib.sha256(b"image").hexdigest(),
            }]
            client.data["website_settings"] = [{
                "tenant_id": 7, "subdomain": "olive", "logo_url": f"/uploads/{key}",
            }]
            with patch.object(asset_registry_service, "release_storage") as release:
                result = asset_registry_service.cleanup_expired_builder_assets(
                    storage_root=Path(root), client=client, dry_run=False,
                )
            self.assertEqual(result["referenced"], 1)
            self.assertTrue(path.exists())
            release.assert_not_called()


if __name__ == "__main__":
    unittest.main()

import hashlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from services import asset_registry_service
from scripts import reconcile_builder_project_assets


class Response:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, db, table):
        self.db, self.table = db, table
        self.filters, self.payload, self.operation, self.limit_value = [], None, "select", None

    def select(self, *_args): return self
    def eq(self, key, value): self.filters.append(("eq", key, value)); return self
    def in_(self, key, values): self.filters.append(("in", key, set(values))); return self
    def filter(self, key, operator, value):
        assert operator == "cs"
        self.filters.append(("contains", key, json.loads(value)))
        return self
    def lte(self, key, value): self.filters.append(("lte", key, value)); return self
    def limit(self, value): self.limit_value = value; return self
    def order(self, key): self.order_key = key; return self
    def range(self, start, end): self.range_value = (start, end); return self
    def insert(self, payload): self.operation, self.payload = "insert", payload; return self
    def update(self, payload): self.operation, self.payload = "update", payload; return self
    def delete(self): self.operation = "delete"; return self

    def execute(self):
        self.db.queries.append(self.table)
        table = self.db.setdefault(self.table, [])
        def matches(row, kind, key, value):
            if kind == "eq": return row.get(key) == value
            if kind == "in": return row.get(key) in value
            if kind == "contains": return set(value) <= set(row.get(key) or [])
            return str(row.get(key) or "") <= str(value)
        rows = [row for row in table if all(
            matches(row, kind, key, value)
            for kind, key, value in self.filters
        )]
        if hasattr(self, "order_key"): rows = sorted(rows, key=lambda row: row.get(self.order_key) or "")
        if hasattr(self, "range_value"):
            start, end = self.range_value
            rows = rows[start:end + 1]
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

    def test_published_snapshot_survives_draft_replacement_and_republish(self):
        client = Client()
        old = "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"
        new = "tenant_7/builder_assets/abcdefabcdefabcdefabcdefabcdefab.webp"
        client.data["builder_assets"] = [
            {"id": "old", "tenant_id": 7, "storage_key": old, "status": "unreferenced"},
            {"id": "new", "tenant_id": 7, "storage_key": new, "status": "unreferenced"},
        ]
        old_schema = {"siteChrome": {"logoUrl": f"/uploads/{old}"}}
        new_schema = {"siteChrome": {"logoUrl": f"/uploads/{new}"}}
        result = asset_registry_service.reconcile_project_asset_references(
            project_id="project-1", tenant_id=7, schema=new_schema,
            published_schema=old_schema, status="published", client=client,
        )
        self.assertEqual(result, {"referenced": 2, "unknown": 0})
        self.assertEqual({row["asset_id"] for row in client.data["builder_asset_references"]}, {"old", "new"})
        self.assertEqual([row["status"] for row in client.data["builder_assets"]], ["active", "active"])
        before = [dict(row) for row in client.data["builder_asset_references"]]
        asset_registry_service.reconcile_project_asset_references(
            project_id="project-1", tenant_id=7, schema=new_schema,
            published_schema=old_schema, status="published", client=client,
        )
        self.assertEqual(client.data["builder_asset_references"], before)
        asset_registry_service.reconcile_project_asset_references(
            project_id="project-1", tenant_id=7, schema=new_schema,
            published_schema=new_schema, status="published", client=client,
        )
        self.assertEqual({row["asset_id"] for row in client.data["builder_asset_references"]}, {"new"})
        self.assertEqual(client.data["builder_assets"][0]["status"], "unreferenced")
        self.assertIsNotNone(client.data["builder_assets"][0]["retention_until"])
        asset_registry_service.reconcile_project_asset_references(
            project_id="project-1", tenant_id=7, schema=new_schema,
            published_schema=old_schema, status="draft", client=client,
        )
        self.assertEqual({row["asset_id"] for row in client.data["builder_asset_references"]}, {"new"})
        asset_registry_service.reconcile_project_asset_references(
            project_id="project-1", tenant_id=7, schema={}, status="archived", client=client,
        )
        self.assertEqual(client.data["builder_asset_references"], [])

    def test_cleanup_guards_published_and_draft_schemas_when_registry_rows_are_missing(self):
        client = Client()
        key = "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"
        client.data["builder_assets"] = [{
            "id": "asset-1", "tenant_id": 7, "storage_key": key,
            "status": "unreferenced", "reference_count": 0,
            "retention_until": "2020-01-01T00:00:00+00:00",
            "sha256": hashlib.sha256(b"image").hexdigest(),
        }]
        project = {
            "id": "project-1", "tenant_id": 7, "status": "published",
            "draft_schema": {}, "published_schema": {"siteChrome": {"logoUrl": f"/uploads/{key}"}},
        }
        client.data["builder_projects"] = [project]
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / key
            path.parent.mkdir(parents=True)
            path.write_bytes(b"image")
            with patch.object(asset_registry_service, "release_storage") as release:
                published = asset_registry_service.cleanup_expired_builder_assets(
                    storage_root=Path(root), client=client, dry_run=False,
                )
                self.assertEqual(published["referenced"], 1)
                project["status"] = "draft"
                project["draft_schema"] = {"pages": [{"image": f"/uploads/{key}"}]}
                draft = asset_registry_service.cleanup_expired_builder_assets(
                    storage_root=Path(root), client=client, dry_run=False,
                )
                self.assertEqual(draft["referenced"], 1)
                release.assert_not_called()
            self.assertTrue(path.exists())

    def test_published_page_body_and_footer_survive_a_newer_empty_draft(self):
        client = Client()
        body = "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"
        footer = "tenant_7/builder_assets/abcdefabcdefabcdefabcdefabcdefab.webp"
        client.data["builder_assets"] = [
            {"id": "body", "tenant_id": 7, "storage_key": body, "status": "unreferenced"},
            {"id": "footer", "tenant_id": 7, "storage_key": footer, "status": "unreferenced"},
        ]
        result = asset_registry_service.reconcile_project_asset_references(
            project_id="project-1", tenant_id=7, schema={"pages": []},
            published_schema={
                "pages": [{"elements": [{"content": f"/uploads/{body}"}]}],
                "siteChrome": {"footerImageUrl": f"/uploads/{footer}"},
            },
            status="published", client=client,
        )
        self.assertEqual(result["referenced"], 2)
        self.assertEqual({row["asset_id"] for row in client.data["builder_asset_references"]}, {"body", "footer"})
        self.assertTrue(all(row["status"] == "active" for row in client.data["builder_assets"]))

    def test_tenant_scoped_repair_command_dry_run_apply_and_rerun(self):
        client = Client()
        key = "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"
        client.data["builder_assets"] = [{
            "id": "asset-1", "tenant_id": 7, "storage_key": key,
            "status": "unreferenced", "reference_count": 0,
        }]
        client.data["builder_projects"] = [{
            "id": "project-1", "tenant_id": 7, "status": "published",
            "draft_schema": {}, "published_schema": {"siteChrome": {"logoUrl": f"/uploads/{key}"}},
        }, {
            "id": "foreign", "tenant_id": 8, "status": "published",
            "draft_schema": {}, "published_schema": {"siteChrome": {"logoUrl": f"/uploads/{key}"}},
        }]
        with patch.object(reconcile_builder_project_assets, "service_supabase", client):
            with patch.object(sys, "argv", ["reconcile_builder_project_assets", "--tenant-id", "7"]), patch(
                "sys.stdout", new_callable=io.StringIO,
            ) as output:
                self.assertEqual(reconcile_builder_project_assets.main(), 0)
                self.assertEqual(json.loads(output.getvalue())["projects_scanned"], 1)
            self.assertEqual(client.data.get("builder_asset_references", []), [])
            with patch.object(sys, "argv", ["reconcile_builder_project_assets", "--tenant-id", "7", "--apply"]):
                with patch("sys.stdout", new_callable=io.StringIO):
                    self.assertEqual(reconcile_builder_project_assets.main(), 0)
                    first = [dict(row) for row in client.data["builder_asset_references"]]
                    self.assertEqual(reconcile_builder_project_assets.main(), 0)
                    self.assertEqual(client.data["builder_asset_references"], first)
        self.assertEqual(first[0]["asset_id"], "asset-1")
        self.assertEqual(client.data["builder_assets"][0]["status"], "active")

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

    def test_shared_variant_image_checks_parent_products_in_one_query(self):
        client = Client()
        key = "tenant_7/builder_assets/0123456789abcdef0123456789abcdef.png"
        url = f"/uploads/{key}"
        client.data["ecommerce_product_variants"] = [
            {"tenant_id": 7, "active": True, "product_id": "draft", "images": [url]},
            {"tenant_id": 7, "active": True, "product_id": "published", "images": [url]},
        ]
        client.data["ecommerce_products"] = [
            {"id": "draft", "tenant_id": 7, "status": "draft"},
            {"id": "published", "tenant_id": 7, "status": "active"},
        ]
        self.assertEqual(asset_registry_service.nonproject_asset_reference_count(
            tenant_id=7, storage_key=key, public_only=True, client=client,
        ), 1)
        self.assertEqual(client.queries, [
            "website_settings", "ecommerce_categories", "ecommerce_brands",
            "ecommerce_products", "ecommerce_product_variants", "ecommerce_products",
        ])

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

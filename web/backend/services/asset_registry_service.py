from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from database import service_supabase
from services.upload_config import assert_path_within_root
from services.storage_quota_service import release_storage, sha256_file

ASSET_URL_PATTERN = re.compile(r"^/uploads/(?P<key>tenant_(?P<tenant>[1-9][0-9]*)/builder_assets/[a-f0-9]{32}\.(?:png|jpg|webp|mp4|webm|pdf|doc|docx))$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _retained_project_references(*, tenant_id: int, draft_schema: Any, published_schema: Any, status: str) -> dict[str, str]:
    """Retain draft assets and the current published snapshot, without granting visibility."""
    if status == "archived":
        return {}
    references = extract_builder_asset_references(draft_schema or {}, tenant_id=tenant_id)
    if status == "published":
        for key, path in extract_builder_asset_references(published_schema or {}, tenant_id=tenant_id).items():
            references.setdefault(key, f"published:{path}"[:500])
    return references


def register_builder_asset(*, tenant_id: int, uploader_user_id: int | None, storage_key: str, original_filename: str, managed_filename: str, mime_type: str, content: bytes | None = None, size_bytes: int | None = None, sha256_hex: str | None = None, client=None) -> dict[str, Any]:
    match = ASSET_URL_PATTERN.fullmatch(f"/uploads/{storage_key}")
    if not match or int(match.group("tenant")) != int(tenant_id):
        raise ValueError("asset_storage_key_invalid")
    row = {
        "tenant_id": int(tenant_id), "uploader_user_id": int(uploader_user_id) if uploader_user_id is not None else None,
        "storage_key": storage_key, "original_filename": Path(original_filename or "asset").name[:255],
        "managed_filename": managed_filename, "mime_type": mime_type,
        "size_bytes": int(size_bytes if size_bytes is not None else len(content or b"")),
        "sha256": sha256_hex or hashlib.sha256(content or b"").hexdigest(), "status": "unreferenced", "reference_count": 0,
        "retention_until": (_now() + timedelta(days=7)).isoformat(), "metadata": {},
    }
    response = (client or service_supabase).table("builder_assets").insert(row).execute()
    data = getattr(response, "data", None) or []
    if not data:
        raise RuntimeError("asset_registry_insert_failed")
    return data[0]


def delete_builder_asset_registration(*, asset_id: str, tenant_id: int, client=None) -> None:
    """Remove a registry row when its upload transaction cannot finish."""
    (
        (client or service_supabase)
        .table("builder_assets")
        .delete()
        .eq("id", asset_id)
        .eq("tenant_id", int(tenant_id))
        .execute()
    )


def extract_builder_asset_references(schema: Any, *, tenant_id: int) -> dict[str, str]:
    found: dict[str, str] = {}
    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, nested in value.items(): visit(nested, f"{path}/{key}")
        elif isinstance(value, list):
            for index, nested in enumerate(value): visit(nested, f"{path}/{index}")
        elif isinstance(value, str):
            match = ASSET_URL_PATTERN.fullmatch(value.strip())
            if match and int(match.group("tenant")) == int(tenant_id): found[match.group("key")] = path[:500]
    visit(schema, "$")
    return found


def nonproject_asset_reference_count(
    *, tenant_id: int, storage_key: str, public_only: bool = False,
    usage_hint: str | None = None, settings_row: dict | None = None, client=None,
) -> int:
    """Count tenant-owned site/store references, optionally only public ones.

    Catalog rows are queried by their exact managed URL. A registered file is
    not public merely because it exists or has an ``active`` registry status.
    """
    if not ASSET_URL_PATTERN.fullmatch(f"/uploads/{storage_key}") or not storage_key.startswith(f"tenant_{tenant_id}/"):
        return 0
    database_client = client or service_supabase
    url = f"/uploads/{storage_key}"
    def site_count() -> int:
        settings = [settings_row] if settings_row is not None else []
        if settings_row is None:
            settings = getattr(
                database_client.table("website_settings")
                .select("*")
                .eq("tenant_id", int(tenant_id)).limit(1).execute(), "data", None,
            ) or []
        if not settings or (public_only and not (settings[0].get("subdomain") or settings[0].get("standard_path_slug"))):
            return 0
        result = sum(settings[0].get(field) == url for field in ("logo_url", "loading_image_url"))
        theme = settings[0].get("ecommerce_theme")
        landing_page = theme.get("landing_page") if isinstance(theme, dict) else None
        slides = landing_page.get("slides") if isinstance(landing_page, dict) else None
        if isinstance(slides, list):
            result += sum(isinstance(slide, dict) and slide.get("image_url") == url for slide in slides)
        return result

    def taxonomy_count(table: str) -> int:
        try:
            query = database_client.table(table).select("id").eq("tenant_id", int(tenant_id))
            if public_only:
                query = query.eq("status", "active")
            rows = getattr(query.eq("image_url", url).limit(1).execute(), "data", None) or []
        except Exception as error:
            # Brands were introduced after the original catalog schema. The
            # release bridge still supports databases without that table.
            message = str(error).lower()
            if table != "ecommerce_brands" or not any(token in message for token in ("pgrst205", "could not find the table", "schema cache")):
                raise
            rows = []
        return int(bool(rows))

    def product_count() -> int:
        query = database_client.table("ecommerce_products").select("id").eq("tenant_id", int(tenant_id))
        if public_only:
            query = query.eq("status", "active")
        rows = getattr(query.filter("images", "cs", json.dumps([url])).limit(1).execute(), "data", None) or []
        return int(bool(rows))

    def variant_count() -> int:
        query = database_client.table("ecommerce_product_variants").select("product_id").eq("tenant_id", int(tenant_id))
        if public_only:
            query = query.eq("active", True)
        variants = getattr(query.filter("images", "cs", json.dumps([url])).execute(), "data", None) or []
        product_ids = {row.get("product_id") for row in variants if row.get("product_id")}
        if not product_ids:
            return 0
        parent_query = database_client.table("ecommerce_products").select("id").eq("tenant_id", int(tenant_id)).in_("id", list(product_ids))
        if public_only:
            parent_query = parent_query.eq("status", "active")
        return int(bool(getattr(parent_query.limit(1).execute(), "data", None)))

    def history_count() -> int:
        if public_only:
            return 0  # Historical order media must never grant public visibility.
        for snapshot in ("product_snapshot", "variant_snapshot"):
            result = database_client.table("ecommerce_order_items").select("id").eq("tenant_id", int(tenant_id)).filter(snapshot + "->images", "cs", json.dumps([url])).limit(1).execute()
            if getattr(result, "data", None):
                return 1
        return 0

    lookups = {
        "site": site_count,
        "category": lambda: taxonomy_count("ecommerce_categories"),
        "brand": lambda: taxonomy_count("ecommerce_brands"),
        "product": product_count,
        "variant": variant_count,
        "history": history_count,
    }
    preferred = {
        "ecommerce_landing_slide": "site",
        "ecommerce_category": "category",
        "ecommerce_brand": "brand",
        "ecommerce_product": "product",
    }.get(usage_hint) if public_only else None
    order = ([preferred] if preferred else []) + [name for name in lookups if name != preferred]
    count = 0
    for name in order:
        count += lookups[name]()
        if public_only and count:
            return count
    return count


def require_builder_asset_tenant_ownership(schema: Any, *, tenant_id: int) -> None:
    """Reject managed asset references whose path names another tenant."""
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)
        elif isinstance(value, str):
            match = ASSET_URL_PATTERN.fullmatch(value.strip())
            if match and int(match.group("tenant")) != int(tenant_id):
                raise ValueError("builder_asset_tenant_mismatch")

    visit(schema)


def refresh_builder_asset_reference_state(*, tenant_id: int, storage_key: str, client=None) -> None:
    """Recount project and public site/store usage after a persisted change."""
    database_client = client or service_supabase
    assets = getattr(
        database_client.table("builder_assets").select("id,status,reference_count,retention_until")
        .eq("tenant_id", int(tenant_id)).eq("storage_key", storage_key).limit(2).execute(), "data", None,
    ) or []
    if len(assets) != 1 or assets[0].get("status") == "soft_deleted":
        return
    asset_id = assets[0]["id"]
    project_refs = getattr(
        database_client.table("builder_asset_references").select("asset_id")
        .eq("asset_id", asset_id).execute(), "data", None,
    ) or []
    count = len(project_refs) + nonproject_asset_reference_count(
        tenant_id=tenant_id, storage_key=storage_key, client=database_client,
    )
    current = assets[0]
    if (
        current.get("status") == ("active" if count else "unreferenced")
        and int(current.get("reference_count") or 0) == count
        and (
            (count > 0 and current.get("retention_until") is None)
            or (count == 0 and current.get("retention_until") is not None)
        )
    ):
        return
    now = _now()
    database_client.table("builder_assets").update({
        "status": "active" if count else "unreferenced",
        "reference_count": count,
        "last_referenced_at": now.isoformat() if count else None,
        "retention_until": None if count else (now + timedelta(days=7)).isoformat(),
        "deleted_at": None,
    }).eq("id", asset_id).eq("tenant_id", int(tenant_id)).execute()


def reconcile_project_asset_references(
    *, project_id: str, tenant_id: int, schema: dict[str, Any],
    published_schema: dict[str, Any] | None = None, status: str = "draft", client=None,
) -> dict[str, int]:
    database_client = client or service_supabase
    desired = _retained_project_references(
        tenant_id=tenant_id, draft_schema=schema, published_schema=published_schema, status=status,
    )
    assets = {}
    for offset in range(0, len(desired), 100):
        keys = list(desired)[offset:offset + 100]
        response = (
            database_client.table("builder_assets").select("id,storage_key,status")
            .eq("tenant_id", int(tenant_id)).in_("storage_key", keys).execute()
        )
        assets.update({
            row["storage_key"]: row for row in (getattr(response, "data", None) or [])
            if row.get("storage_key") in desired and row.get("status") != "soft_deleted"
        })
    previous_response = (
        database_client.table("builder_asset_references")
        .select("asset_id,reference_path").eq("project_id", project_id).execute()
    )
    previous_rows = getattr(previous_response, "data", None) or []
    previous_ids = {row["asset_id"] for row in previous_rows}
    references = [{"asset_id": asset["id"], "project_id": project_id, "reference_path": desired[key]} for key, asset in assets.items()]
    previous_pairs = {(row["asset_id"], row.get("reference_path")) for row in previous_rows}
    current_pairs = {(row["asset_id"], row["reference_path"]) for row in references}
    if previous_pairs != current_pairs:
        database_client.table("builder_asset_references").delete().eq("project_id", project_id).execute()
        if references:
            database_client.table("builder_asset_references").insert(references).execute()
    current_ids = {asset["id"] for asset in assets.values()}
    for asset_id in previous_ids | current_ids:
        asset = next((row for row in assets.values() if row["id"] == asset_id), None)
        if asset is None:
            old = getattr(database_client.table("builder_assets").select("storage_key")
                .eq("id", asset_id).eq("tenant_id", int(tenant_id)).limit(1).execute(), "data", None) or []
            asset = old[0] if old else None
        if asset:
            refresh_builder_asset_reference_state(
                tenant_id=tenant_id, storage_key=asset["storage_key"], client=database_client,
            )
            if previous_pairs != current_pairs:
                database_client.table("builder_assets").update({
                    "project_id": project_id if asset_id in current_ids else None,
                }).eq("id", asset_id).eq("tenant_id", int(tenant_id)).execute()
    return {"referenced": len(references), "unknown": len(desired) - len(assets)}


def project_asset_is_persisted(*, tenant_id: int, storage_key: str, client=None) -> bool:
    """Cleanup-only guard for legacy rows whose project reference was lost."""
    database_client = client or service_supabase
    projects = getattr(
        database_client.table("builder_projects")
        .select("status,draft_schema,published_schema")
        .eq("tenant_id", int(tenant_id)).limit(1000).execute(), "data", None,
    ) or []
    # A truncated project scan must fail closed rather than delete an asset.
    if len(projects) == 1000:
        return True
    return any(
        storage_key in _retained_project_references(
            tenant_id=tenant_id, draft_schema=project.get("draft_schema"),
            published_schema=project.get("published_schema"),
            status=project.get("status") or "draft",
        )
        for project in projects
    )


def cleanup_expired_builder_assets(*, storage_root: Path, limit: int = 100, dry_run: bool = True, client=None) -> dict[str, int]:
    database_client = client or service_supabase
    response = database_client.table("builder_assets").select("id,tenant_id,storage_key,sha256").eq("status", "unreferenced").lte("retention_until", _now().isoformat()).limit(max(1, min(int(limit), 500))).execute()
    eligible = deleted = skipped = missing_files = hash_mismatches = referenced = 0
    for row in getattr(response, "data", None) or []:
        eligible += 1
        refs = database_client.table("builder_asset_references").select("asset_id").eq("asset_id", row["id"]).limit(1).execute()
        if getattr(refs, "data", None) or project_asset_is_persisted(
            tenant_id=int(row["tenant_id"]), storage_key=row["storage_key"], client=database_client,
        ) or nonproject_asset_reference_count(
            tenant_id=int(row["tenant_id"]), storage_key=row["storage_key"], client=database_client,
        ):
            skipped += 1; referenced += 1; continue
        path = assert_path_within_root(storage_root / row["storage_key"], storage_root)
        if path.exists() and not path.is_file():
            skipped += 1; continue
        if path.is_file() and sha256_file(path) != row["sha256"]:
            skipped += 1; hash_mismatches += 1; continue
        if not path.exists():
            missing_files += 1
        if not dry_run:
            # Recheck immediately before the irreversible file operation. The
            # publication path creates a reference before marking an asset
            # active, so a concurrent publish makes this item ineligible.
            current = database_client.table("builder_assets").select("status,reference_count").eq("id", row["id"]).eq("tenant_id", int(row["tenant_id"])).limit(1).execute()
            current_rows = getattr(current, "data", None) or []
            if len(current_rows) != 1 or current_rows[0].get("status") != "unreferenced" or int(current_rows[0].get("reference_count") or 0) != 0:
                skipped += 1; referenced += 1; continue
            if project_asset_is_persisted(
                tenant_id=int(row["tenant_id"]), storage_key=row["storage_key"], client=database_client,
            ) or nonproject_asset_reference_count(
                tenant_id=int(row["tenant_id"]), storage_key=row["storage_key"], client=database_client,
            ):
                skipped += 1; referenced += 1; continue
            if path.is_file(): path.unlink()
            release_storage(
                tenant_id=int(row["tenant_id"]),
                category="builder_asset",
                storage_key=row["storage_key"],
                client=database_client,
            )
            database_client.table("builder_assets").update({"status": "soft_deleted", "deleted_at": _now().isoformat(), "reference_count": 0}).eq("id", row["id"]).execute()
            deleted += 1
    return {
        "eligible": eligible, "deleted": deleted, "skipped": skipped,
        "referenced": referenced, "missing_files": missing_files,
        "hash_mismatches": hash_mismatches,
    }

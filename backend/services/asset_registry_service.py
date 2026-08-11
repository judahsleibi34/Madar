from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from database import service_supabase
from services.upload_config import assert_path_within_root
from services.storage_quota_service import release_storage

ASSET_URL_PATTERN = re.compile(r"^/uploads/(?P<key>tenant_(?P<tenant>[1-9][0-9]*)/builder_assets/[a-f0-9]{32}\.(?:png|jpg|webp|mp4|webm|pdf|doc|docx))$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


def reconcile_project_asset_references(*, project_id: str, tenant_id: int, schema: dict[str, Any], client=None) -> dict[str, int]:
    database_client = client or service_supabase
    desired = extract_builder_asset_references(schema, tenant_id=tenant_id)
    response = database_client.table("builder_assets").select("id,storage_key").eq("tenant_id", int(tenant_id)).execute()
    assets = {row["storage_key"]: row for row in (getattr(response, "data", None) or []) if row.get("storage_key") in desired}
    previous_response = database_client.table("builder_asset_references").select("asset_id").eq("project_id", project_id).execute()
    previous_ids = {row["asset_id"] for row in (getattr(previous_response, "data", None) or [])}
    database_client.table("builder_asset_references").delete().eq("project_id", project_id).execute()
    references = [{"asset_id": asset["id"], "project_id": project_id, "reference_path": desired[key]} for key, asset in assets.items()]
    if references: database_client.table("builder_asset_references").insert(references).execute()
    now = _now().isoformat()
    current_ids = {asset["id"] for asset in assets.values()}
    for asset_id in previous_ids | current_ids:
        count_response = database_client.table("builder_asset_references").select("asset_id").eq("asset_id", asset_id).execute()
        reference_count = len(getattr(count_response, "data", None) or [])
        update = {
            "project_id": project_id if asset_id in current_ids else None,
            "status": "active" if reference_count else "unreferenced",
            "reference_count": reference_count,
            "last_referenced_at": now if reference_count else None,
            "retention_until": None if reference_count else (_now() + timedelta(days=7)).isoformat(),
            "deleted_at": None,
        }
        database_client.table("builder_assets").update(update).eq("id", asset_id).eq("tenant_id", int(tenant_id)).execute()
    return {"referenced": len(references), "unknown": len(desired) - len(assets)}


def cleanup_expired_builder_assets(*, storage_root: Path, limit: int = 100, dry_run: bool = True, client=None) -> dict[str, int]:
    database_client = client or service_supabase
    response = database_client.table("builder_assets").select("id,tenant_id,storage_key,sha256").eq("status", "unreferenced").lte("retention_until", _now().isoformat()).limit(max(1, min(int(limit), 500))).execute()
    eligible = deleted = skipped = 0
    for row in getattr(response, "data", None) or []:
        eligible += 1
        refs = database_client.table("builder_asset_references").select("asset_id").eq("asset_id", row["id"]).limit(1).execute()
        if getattr(refs, "data", None): skipped += 1; continue
        path = assert_path_within_root(storage_root / row["storage_key"], storage_root)
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]: skipped += 1; continue
        if not dry_run:
            if path.is_file(): path.unlink()
            release_storage(
                tenant_id=int(row["tenant_id"]),
                category="builder_asset",
                storage_key=row["storage_key"],
                client=database_client,
            )
            database_client.table("builder_assets").update({"status": "soft_deleted", "deleted_at": _now().isoformat(), "reference_count": 0}).eq("id", row["id"]).execute()
            deleted += 1
    return {"eligible": eligible, "deleted": deleted, "skipped": skipped}

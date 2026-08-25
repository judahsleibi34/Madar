#!/usr/bin/env python3
"""Inventory and explicitly backfill legacy avatar storage accounting.

Dry-run is the default. Output contains only platform IDs, byte counts, hashes,
and a hash of the storage key; avatar content and URLs are never emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from database import service_supabase
from services.storage_quota_service import finish_storage, reserve_storage


MARKER = "/storage/v1/object/public/avatars/"
AUTH_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def avatar_storage_key(avatar_url: str, auth_id: str) -> str | None:
    if MARKER not in avatar_url or not AUTH_ID.fullmatch(auth_id):
        return None
    key = avatar_url.split(MARKER, 1)[1].split("?", 1)[0]
    if not key.startswith(f"users/{auth_id}/") or ".." in key.split("/"):
        return None
    return key if re.fullmatch(r"users/[0-9a-f-]{36}/[A-Za-z0-9_.-]+", key) else None


def _rows(client) -> list[dict[str, Any]]:
    response = client.table("users").select("id,auth_id,tenant_id,avatar").not_.is_("avatar", "null").limit(10000).execute()
    return list(getattr(response, "data", None) or [])


def inventory(*, client=service_supabase) -> list[dict[str, Any]]:
    candidates: list[tuple[dict[str, Any], str]] = []
    for user in _rows(client):
        key = avatar_storage_key(str(user.get("avatar") or ""), str(user.get("auth_id") or ""))
        if key:
            candidates.append((user, key))
    duplicate_keys = {key for key, amount in Counter(key for _, key in candidates).items() if amount > 1}
    results = []
    for user, key in candidates:
        safe = {
            "tenant_id": int(user["tenant_id"]), "user_id": int(user["id"]),
            "storage_key_sha256": hashlib.sha256(key.encode()).hexdigest(),
        }
        if key in duplicate_keys:
            results.append({**safe, "status": "duplicate_avatar_key"})
            continue
        existing = client.table("storage_objects").select("id,status,size_bytes,sha256,user_id").eq(
            "tenant_id", int(user["tenant_id"])
        ).eq("category", "avatar").eq("storage_key", key).limit(1).execute()
        rows = list(getattr(existing, "data", None) or [])
        if rows:
            row = rows[0]
            status = "already_accounted" if row.get("status") == "active" and row.get("user_id") == user["id"] else "accounting_conflict"
            results.append({**safe, "status": status, "size_bytes": int(row.get("size_bytes") or 0)})
            continue
        try:
            content = client.storage.from_("avatars").download(key)
        except Exception:
            results.append({**safe, "status": "avatar_object_missing"})
            continue
        if not isinstance(content, bytes) or not content:
            results.append({**safe, "status": "avatar_object_missing"})
            continue
        results.append({
            **safe, "status": "ready", "storage_key": key,
            "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
        })
    return results


def apply_inventory(rows: list[dict[str, Any]], *, client=service_supabase, storage_root: Path) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        safe = {key: row[key] for key in ("tenant_id", "user_id", "storage_key_sha256", "size_bytes") if key in row}
        if row["status"] != "ready":
            output.append({**safe, "status": row["status"]})
            continue
        reservation = reserve_storage(
            tenant_id=row["tenant_id"], user_id=row["user_id"], category="avatar",
            size_bytes=row["size_bytes"], storage_root=storage_root, client=client,
        )
        try:
            finish_storage(
                reservation_id=reservation, succeeded=True, storage_key=row["storage_key"],
                sha256_hex=row["sha256"], client=client,
            )
        except Exception:
            try:
                finish_storage(reservation_id=reservation, succeeded=False, client=client)
            except Exception:
                pass
            raise
        output.append({**safe, "status": "accounted"})
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory legacy avatar storage accounting")
    parser.add_argument("--apply", action="store_true", help="write accounting rows; default is read-only")
    parser.add_argument("--storage-root", type=Path, default=Path("avatar_uploads"))
    args = parser.parse_args()
    rows = inventory()
    output = apply_inventory(rows, storage_root=args.storage_root) if args.apply else [
        {key: value for key, value in row.items() if key != "storage_key"} for row in rows
    ]
    counts = Counter(row["status"] for row in output)
    print(json.dumps({"dry_run": not args.apply, "counts": dict(sorted(counts.items())), "rows": output}, sort_keys=True))
    return 2 if any(row["status"] in {"duplicate_avatar_key", "accounting_conflict"} for row in output) else 0


if __name__ == "__main__":
    raise SystemExit(main())

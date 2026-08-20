from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

from database import service_supabase
from services.entitlement_service import get_storage_quota_bytes

DEFAULT_TENANT_QUOTA_BYTES = 5 * 1024 * 1024 * 1024
DEFAULT_USER_QUOTA_BYTES = 1024 * 1024 * 1024
DEFAULT_DISK_FREE_FLOOR_BYTES = 2 * 1024 * 1024 * 1024


class StorageSafetyError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _env_bytes(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise StorageSafetyError("storage_configuration_invalid") from error
    if value <= 0:
        raise StorageSafetyError("storage_configuration_invalid")
    return value


def ensure_disk_capacity(path: Path, *, incoming_bytes: int = 0) -> int:
    path.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(path).free
    floor = _env_bytes("STORAGE_DISK_FREE_FLOOR_BYTES", DEFAULT_DISK_FREE_FLOOR_BYTES)
    if free - max(0, int(incoming_bytes)) < floor:
        raise StorageSafetyError("storage_disk_floor_breached")
    return free


def reserve_storage(*, tenant_id: int, user_id: int | None, category: str, size_bytes: int, storage_root: Path, client=None) -> str:
    if size_bytes <= 0:
        raise StorageSafetyError("storage_reservation_invalid")
    ensure_disk_capacity(storage_root, incoming_bytes=size_bytes)
    database_client = client or service_supabase
    tenant_quota = get_storage_quota_bytes(tenant_id)
    try:
        response = database_client.rpc("reserve_storage_bytes", {
            "p_tenant_id": int(tenant_id),
            "p_user_id": int(user_id) if user_id is not None else None,
            "p_category": category,
            "p_bytes": int(size_bytes),
            "p_tenant_quota": tenant_quota,
            # Commercial allowance belongs only to the workspace scope. The
            # user row remains an independent 1 GiB abuse/safety ceiling.
            "p_user_quota": DEFAULT_USER_QUOTA_BYTES if user_id is not None else None,
        }).execute()
    except Exception as error:
        text = str(error).lower()
        if "tenant_storage_quota_exceeded" in text:
            raise StorageSafetyError("tenant_storage_quota_exceeded") from error
        if "user_storage_quota_exceeded" in text:
            raise StorageSafetyError("user_storage_quota_exceeded") from error
        raise StorageSafetyError("storage_accounting_unavailable") from error
    data = getattr(response, "data", None)
    reservation_id = data[0] if isinstance(data, list) and data else data
    if not reservation_id:
        raise StorageSafetyError("storage_accounting_unavailable")
    return str(reservation_id)


def finish_storage(*, reservation_id: str, succeeded: bool, storage_key: str | None = None, content: bytes | None = None, sha256_hex: str | None = None, retention_until: str | None = None, client=None) -> str | None:
    response = (client or service_supabase).rpc("finish_storage_reservation", {
        "p_reservation_id": reservation_id,
        "p_succeeded": bool(succeeded),
        "p_storage_key": storage_key if succeeded else None,
        "p_sha256": sha256_hex or (hashlib.sha256(content).hexdigest() if succeeded and content is not None else None),
        "p_retention_until": retention_until,
    }).execute()
    data = getattr(response, "data", None)
    result = data[0] if isinstance(data, list) and data else data
    return str(result) if result else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_storage(*, tenant_id: int, category: str, storage_key: str, client=None) -> bool:
    response = (client or service_supabase).rpc("release_storage_object", {
        "p_tenant_id": int(tenant_id),
        "p_category": category,
        "p_storage_key": storage_key,
    }).execute()
    data = getattr(response, "data", None)
    return bool(data[0] if isinstance(data, list) and data else data)


def get_tenant_storage_usage(tenant_id: int, *, client=None) -> dict[str, Any]:
    response = (client or service_supabase).table("storage_accounts").select(
        "used_bytes,reserved_bytes,quota_bytes"
    ).eq("tenant_id", int(tenant_id)).eq("scope_key", "tenant").is_("user_id", "null").limit(1).execute()
    rows = getattr(response, "data", None) or []
    entitlement_quota = get_storage_quota_bytes(tenant_id)
    if not rows:
        return {
            "used_bytes": 0,
            "reserved_bytes": 0,
            "quota_bytes": entitlement_quota,
        }
    row = rows[0]
    total = int(row.get("used_bytes") or 0) + int(row.get("reserved_bytes") or 0)
    # The current entitlement is authoritative after upgrades/downgrades. The
    # next atomic reservation updates storage_accounts.quota_bytes. Existing
    # objects remain readable when usage is above the new quota.
    quota = entitlement_quota
    return {
        **row,
        "quota_bytes": quota,
        "over_capacity": total > quota,
        "near_capacity": total >= int(quota * 0.9),
    }


def sync_tenant_storage_quota(tenant_id: int, *, client=None) -> dict[str, Any] | None:
    """Persist the current commercial allowance on the authoritative tenant row.

    The existing atomic reservation RPC remains authoritative for used/reserved
    byte changes. Plan changes update only ``quota_bytes`` and never touch user
    safety scopes or create a second physical-usage accounting row.
    """

    quota_bytes = get_storage_quota_bytes(tenant_id)
    response = (
        (client or service_supabase)
        .table("storage_accounts")
        .update({"quota_bytes": quota_bytes})
        .eq("tenant_id", int(tenant_id))
        .eq("scope_key", "tenant")
        .is_("user_id", "null")
        .execute()
    )
    rows = getattr(response, "data", None) or []
    return rows[0] if rows else None

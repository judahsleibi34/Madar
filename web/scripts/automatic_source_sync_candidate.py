"""Validate the exact unselected 155→156 automatic synchronization candidate."""
import hashlib
import json
import re
from pathlib import Path


MANIFEST_SHA256 = "ad5f177dee47bd98489a556278b468fe42e587bde04098bc9fcbc8691c0d883d"
BRIDGE_SHA256 = "4ed571660b1b86a6d60e6a0550cf82c08a7af0154c961aa4c67a5b47d733fba3"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-155-156-automatic-source-sync.json"
    bridge = release / "schema-155-156-automatic-source-sync-bridge.json"
    if (hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
            or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256):
        raise ValueError("automatic-source-sync candidate metadata changed")
    entries = json.loads(manifest.read_text())['migrations']
    expected = {
        "number": 156, "from_schema": 155, "to_schema": 156,
        "compatibility": "expand-only",
        "path": "web/database/migrations/156_add_automatic_source_synchronization.sql",
    }
    if len(entries) != 1 or {key: entries[0].get(key) for key in expected} != expected:
        raise ValueError("automatic-source-sync candidate transition invalid")
    original = root / entries[0]['path']
    mirror = root / "web/supabase/migrations/156_add_automatic_source_synchronization.sql"
    if (original.read_bytes() != mirror.read_bytes()
            or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]['sha256']):
        raise ValueError("automatic-source-sync SQL mirror or checksum invalid")
    sql = re.sub(r"--[^\n]*|/\*.*?\*/", "", original.read_text(), flags=re.S).lower()
    required = (
        "create table public.data_source_sync_schedules",
        "create table public.data_source_sync_attempts",
        "create function public.claim_due_data_source_syncs156",
        "for update of q skip locked",
        "pg_advisory_xact_lock",
        "create function public.complete_source_sync156",
        "create function public.fail_source_sync156",
        "interval_seconds between 900 and 604800",
        "enabled boolean not null default false",
        "revoke all on public.data_source_sync_schedules,public.data_source_sync_attempts",
    )
    if any(value not in sql for value in required):
        raise ValueError("automatic-source-sync safety contract invalid")
    if sql.index("for update;") > sql.index("create unique index"):
        raise ValueError("schema-state lock must precede DDL")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 155, "compatible_max": 156, "target": 156,
        "migration_class": "expand-only", "rollback_compatible_min": 155,
        "rollback_compatible_max": 155,
    }
    if (value['schema'] != expected_schema
            or value['migration_manifest'] != manifest.name
            or value['deployment_profile'] != "automatic-source-sync155-156"):
        raise ValueError("automatic-source-sync compatibility invalid")
    return entries


if __name__ == "__main__":
    validated_entries(Path(__file__).resolve().parents[2])

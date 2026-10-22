"""Validate the exact unselected 149→150 ingestion-recovery candidate."""
import hashlib
import json
from pathlib import Path


MANIFEST_SHA256 = "74e099dfb45fd1e0492a90cea2fa8c25246e4ec555c94213c82499e06756e7b5"
BRIDGE_SHA256 = "be9fc32ecd11c26e103624b51ab8e38c6c0ace18b412bf050103109af4e7b869"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-149-150-source-ingestion-recovery.json"
    bridge = release / "schema-149-150-source-ingestion-recovery-bridge.json"
    if (
        hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
        or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256
    ):
        raise ValueError("Source-ingestion recovery candidate metadata changed")
    entries = json.loads(manifest.read_text())["migrations"]
    expected = {
        "number": 150,
        "from_schema": 149,
        "to_schema": 150,
        "compatibility": "expand-only",
        "path": "web/database/migrations/150_add_source_ingestion_recovery.sql",
    }
    if len(entries) != 1 or {key: entries[0].get(key) for key in expected} != expected:
        raise ValueError("Source-ingestion recovery candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/150_add_source_ingestion_recovery.sql"
    if (
        original.read_bytes() != mirror.read_bytes()
        or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]
    ):
        raise ValueError("Source-ingestion recovery SQL mirror or checksum invalid")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 149,
        "compatible_max": 150,
        "target": 150,
        "migration_class": "expand-only",
        "rollback_compatible_min": 149,
        "rollback_compatible_max": 149,
    }
    if (
        value["schema"] != expected_schema
        or value["migration_manifest"] != manifest.name
        or value["deployment_profile"] != "source-ingestion-recovery149-150"
    ):
        raise ValueError("Source-ingestion recovery compatibility invalid")
    return entries

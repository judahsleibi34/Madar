"""Validate the exact unselected 151→152 incremental-ingestion candidate."""
import hashlib
import json
from pathlib import Path


MANIFEST_SHA256 = "9cfb3f72fb8369c8f64bed75bac983abe6fbb5a0fcddaa262b44ac3c346277d7"
BRIDGE_SHA256 = "ea1d12762a29a253767a52a1c855fb3b43833017ea1eed5a649f810d54bc0397"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-151-152-incremental-ingestion.json"
    bridge = release / "schema-151-152-incremental-ingestion-bridge.json"
    if (
        hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
        or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256
    ):
        raise ValueError("incremental-ingestion candidate metadata changed")
    entries = json.loads(manifest.read_text())["migrations"]
    expected = {
        "number": 152,
        "from_schema": 151,
        "to_schema": 152,
        "compatibility": "expand-only",
        "path": "web/database/migrations/152_add_incremental_source_ingestion.sql",
    }
    if len(entries) != 1 or {key: entries[0].get(key) for key in expected} != expected:
        raise ValueError("incremental-ingestion candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/152_add_incremental_source_ingestion.sql"
    if (
        original.read_bytes() != mirror.read_bytes()
        or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]
    ):
        raise ValueError("incremental-ingestion SQL mirror or checksum invalid")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 151,
        "compatible_max": 152,
        "target": 152,
        "migration_class": "expand-only",
        "rollback_compatible_min": 151,
        "rollback_compatible_max": 151,
    }
    if (
        value["schema"] != expected_schema
        or value["migration_manifest"] != manifest.name
        or value["deployment_profile"] != "incremental-ingestion151-152"
    ):
        raise ValueError("incremental-ingestion compatibility invalid")
    return entries

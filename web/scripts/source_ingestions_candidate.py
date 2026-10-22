"""Validate the exact unselected 148→149 source-ingestion candidate."""
import hashlib
import json
from pathlib import Path


MANIFEST_SHA256 = "39992b612fd97c5501610b6a024394ae1340b6cd45767fe80801600f7624e364"
BRIDGE_SHA256 = "e6dca38334fb4ccfc3e6d0e665b83db159ec11ccebcb970cf7703a4732a2ae8d"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-148-149-source-ingestions.json"
    bridge = release / "schema-148-149-source-ingestions-bridge.json"
    if (
        hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
        or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256
    ):
        raise ValueError("Source-ingestion candidate metadata changed")
    raw = json.loads(manifest.read_text())
    entries = raw["migrations"]
    expected = {
        "number": 149,
        "from_schema": 148,
        "to_schema": 149,
        "compatibility": "expand-only",
        "path": "web/database/migrations/149_add_source_ingestion_runs.sql",
    }
    if len(entries) != 1 or {key: entries[0].get(key) for key in expected} != expected:
        raise ValueError("Source-ingestion candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/149_add_source_ingestion_runs.sql"
    if (
        original.read_bytes() != mirror.read_bytes()
        or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]
    ):
        raise ValueError("Source-ingestion SQL mirror or checksum invalid")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 148,
        "compatible_max": 149,
        "target": 149,
        "migration_class": "expand-only",
        "rollback_compatible_min": 148,
        "rollback_compatible_max": 148,
    }
    if (
        value["schema"] != expected_schema
        or value["migration_manifest"] != manifest.name
        or value["deployment_profile"] != "source-ingestions148-149"
    ):
        raise ValueError("Source-ingestion branch compatibility invalid")
    return entries

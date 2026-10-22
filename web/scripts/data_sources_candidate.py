"""Validate the exact unselected 147→148 project data-sources candidate."""
import hashlib
import json
from pathlib import Path


MANIFEST_SHA256 = "9d932ecd0daacfc39dd03621b2d68a47ebc4145ed4a1aa6704fa64a29eee0c20"
BRIDGE_SHA256 = "05706a61e2b12671f66a16e35ff836fbffbf0551e20647847317d6c294b33fac"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-147-148-data-sources.json"
    bridge = release / "schema-147-148-data-sources-bridge.json"
    if (
        hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
        or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256
    ):
        raise ValueError("Project data-sources candidate metadata changed")
    raw = json.loads(manifest.read_text())
    entries = raw["migrations"]
    expected = {
        "number": 148,
        "from_schema": 147,
        "to_schema": 148,
        "compatibility": "expand-only",
        "path": "web/database/migrations/148_add_project_data_sources.sql",
    }
    if len(entries) != 1 or {
        key: entries[0].get(key) for key in expected
    } != expected:
        raise ValueError("Project data-sources candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/148_add_project_data_sources.sql"
    if (
        original.read_bytes() != mirror.read_bytes()
        or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]
    ):
        raise ValueError("Project data-sources SQL mirror or checksum invalid")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 147,
        "compatible_max": 148,
        "target": 148,
        "migration_class": "expand-only",
        "rollback_compatible_min": 147,
        "rollback_compatible_max": 147,
    }
    if (
        value["schema"] != expected_schema
        or value["migration_manifest"] != manifest.name
        or value["deployment_profile"] != "project-data-sources147-148"
    ):
        raise ValueError("Project data-sources branch compatibility invalid")
    return entries

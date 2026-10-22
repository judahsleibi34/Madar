"""Validate the exact unselected 146→147 project-datasets candidate."""
import hashlib
import json
from pathlib import Path


MANIFEST_SHA256 = "a45bf8e8969210d8c2f35d6d7544b048ce11459de44885e8c71a94fd5ff12f57"
BRIDGE_SHA256 = "2b668dad1513bfd5b6c42374cf23875a42180cdc7b6768973adcf4f30ebcd967"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-146-147-project-datasets.json"
    bridge = release / "schema-146-147-project-datasets-bridge.json"
    if (
        hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
        or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256
    ):
        raise ValueError("Project-datasets candidate metadata changed")
    raw = json.loads(manifest.read_text())
    entries = raw["migrations"]
    expected = {
        "number": 147,
        "from_schema": 146,
        "to_schema": 147,
        "compatibility": "expand-only",
        "path": "web/database/migrations/147_add_project_datasets.sql",
    }
    if len(entries) != 1 or {
        key: entries[0].get(key) for key in expected
    } != expected:
        raise ValueError("Project-datasets candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/147_add_project_datasets.sql"
    if (
        original.read_bytes() != mirror.read_bytes()
        or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]
    ):
        raise ValueError("Project-datasets SQL mirror or checksum invalid")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 146,
        "compatible_max": 147,
        "target": 147,
        "migration_class": "expand-only",
        "rollback_compatible_min": 146,
        "rollback_compatible_max": 146,
    }
    if (
        value["schema"] != expected_schema
        or value["migration_manifest"] != manifest.name
        or value["deployment_profile"] != "project-datasets146-147"
    ):
        raise ValueError("Project-datasets branch compatibility invalid")
    return entries

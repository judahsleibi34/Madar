"""Validate the exact unselected 152→153 background-checkpoint candidate."""
import hashlib
import json
from pathlib import Path


MANIFEST_SHA256 = "60749b90a1815ac8fad6ef2e16ec4844f43eaae63453c9ce13edb6d778016030"
BRIDGE_SHA256 = "3819a3d9729556b6020ac9d26e9da1a774d6478c58faf3c8a85c3478b800247c"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-152-153-background-checkpoints.json"
    bridge = release / "schema-152-153-background-checkpoints-bridge.json"
    if (hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
            or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256):
        raise ValueError("background-checkpoint candidate metadata changed")
    entries = json.loads(manifest.read_text())["migrations"]
    expected = {
        "number": 153, "from_schema": 152, "to_schema": 153,
        "compatibility": "expand-only",
        "path": "web/database/migrations/153_add_background_dataset_checkpoints.sql",
    }
    if len(entries) != 1 or {key: entries[0].get(key) for key in expected} != expected:
        raise ValueError("background-checkpoint candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/153_add_background_dataset_checkpoints.sql"
    if (original.read_bytes() != mirror.read_bytes()
            or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]):
        raise ValueError("background-checkpoint SQL mirror or checksum invalid")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 152, "compatible_max": 153, "target": 153,
        "migration_class": "expand-only", "rollback_compatible_min": 152,
        "rollback_compatible_max": 152,
    }
    if (value["schema"] != expected_schema
            or value["migration_manifest"] != manifest.name
            or value["deployment_profile"] != "background-checkpoints152-153"):
        raise ValueError("background-checkpoint compatibility invalid")
    return entries

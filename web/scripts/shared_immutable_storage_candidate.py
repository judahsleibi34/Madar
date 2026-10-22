"""Validate the exact unselected 153→154 shared immutable-storage candidate."""
import hashlib
import json
from pathlib import Path


MANIFEST_SHA256 = "f2d87a0aeb12153bc4494e96c1c0b727155511f6a51dcda77ca160bc71ea6e84"
BRIDGE_SHA256 = "a6b5ceba366c52ee6025578824719ca9140c758dbbd89741c14c549683352aca"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-153-154-shared-immutable-storage.json"
    bridge = release / "schema-153-154-shared-immutable-storage-bridge.json"
    if (hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
            or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256):
        raise ValueError("shared immutable-storage candidate metadata changed")
    entries = json.loads(manifest.read_text())["migrations"]
    expected = {
        "number": 154, "from_schema": 153, "to_schema": 154,
        "compatibility": "expand-only",
        "path": "web/database/migrations/154_add_shared_immutable_storage.sql",
    }
    if len(entries) != 1 or {key: entries[0].get(key) for key in expected} != expected:
        raise ValueError("shared immutable-storage candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/154_add_shared_immutable_storage.sql"
    if (original.read_bytes() != mirror.read_bytes()
            or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]):
        raise ValueError("shared immutable-storage SQL mirror or checksum invalid")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 153, "compatible_max": 154, "target": 154,
        "migration_class": "expand-only", "rollback_compatible_min": 153,
        "rollback_compatible_max": 153,
    }
    if (value["schema"] != expected_schema
            or value["migration_manifest"] != manifest.name
            or value["deployment_profile"] != "shared-immutable-storage153-154"):
        raise ValueError("shared immutable-storage compatibility invalid")
    return entries


if __name__ == "__main__":
    validated_entries(Path(__file__).resolve().parents[2])

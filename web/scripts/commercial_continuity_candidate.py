"""Validate the exact unselected 144→145 commercial-continuity candidate."""
import hashlib
import json
from pathlib import Path


MANIFEST_SHA256 = "f111951ac1913fda0ef29b9efc42130fc0c173629648b7150b6d3484ac51fcd3"
BRIDGE_SHA256 = "4cdf436ec89a3a643d9747a67afe409b9ce35685b43521d80b6721ae8640d131"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-144-145-commercial.json"
    bridge = release / "schema-144-145-commercial-bridge.json"
    if (hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
        or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256):
        raise ValueError("Commercial continuity candidate metadata changed")
    raw = json.loads(manifest.read_text())
    entries = raw["migrations"]
    expected = {
        "number": 145,
        "from_schema": 144,
        "to_schema": 145,
        "compatibility": "forward-compatible",
        "path": "web/database/migrations/145_enforce_paid_commercial_continuity.sql",
    }
    if len(entries) != 1 or {
        key: entries[0].get(key) for key in expected
    } != expected:
        raise ValueError("Commercial continuity candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/145_enforce_paid_commercial_continuity.sql"
    if (original.read_bytes() != mirror.read_bytes()
        or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]):
        raise ValueError("Commercial continuity SQL mirror or checksum invalid")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 144,
        "compatible_max": 145,
        "target": 145,
        "migration_class": "forward-compatible",
        "rollback_compatible_min": 144,
        "rollback_compatible_max": 144,
    }
    if (value["schema"] != expected_schema
        or value["migration_manifest"] != manifest.name
        or value["deployment_profile"] != "strict-commercial-continuity144-145"):
        raise ValueError("Commercial continuity branch compatibility invalid")
    return entries

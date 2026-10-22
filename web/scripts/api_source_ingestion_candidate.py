"""Validate the exact unselected 150→151 API-source ingestion candidate."""
import hashlib
import json
from pathlib import Path


MANIFEST_SHA256 = "2eb8ffefe05cc82c814b27825650f8ee3fb77e8d5b7921c0a3a2f03f775fe655"
BRIDGE_SHA256 = "8dc353a714960223f012ff12702481694a451b1e0759cb551a1efaabbe822c82"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-150-151-api-source-ingestion.json"
    bridge = release / "schema-150-151-api-source-ingestion-bridge.json"
    if (
        hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
        or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256
    ):
        raise ValueError("API-source ingestion candidate metadata changed")
    entries = json.loads(manifest.read_text())["migrations"]
    expected = {
        "number": 151,
        "from_schema": 150,
        "to_schema": 151,
        "compatibility": "expand-only",
        "path": "web/database/migrations/151_add_api_source_ingestion.sql",
    }
    if len(entries) != 1 or {key: entries[0].get(key) for key in expected} != expected:
        raise ValueError("API-source ingestion candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/151_add_api_source_ingestion.sql"
    if (
        original.read_bytes() != mirror.read_bytes()
        or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]
    ):
        raise ValueError("API-source ingestion SQL mirror or checksum invalid")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 150,
        "compatible_max": 151,
        "target": 151,
        "migration_class": "expand-only",
        "rollback_compatible_min": 150,
        "rollback_compatible_max": 150,
    }
    if (
        value["schema"] != expected_schema
        or value["migration_manifest"] != manifest.name
        or value["deployment_profile"] != "api-source-ingestion150-151"
    ):
        raise ValueError("API-source ingestion compatibility invalid")
    return entries

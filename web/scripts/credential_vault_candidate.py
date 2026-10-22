"""Validate the exact unselected 154→155 Data Source credential-vault candidate."""
import hashlib
import json
from pathlib import Path


MANIFEST_SHA256 = "9bdd4a342f57193aa5f476e3e723e300fb347935c8b87031ab4f12aa4f2ec277"
BRIDGE_SHA256 = "a3573cedb849886871e693671360b56bbb08a52a4bc8bef81098da7c3ba826d0"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-154-155-credential-vault.json"
    bridge = release / "schema-154-155-credential-vault-bridge.json"
    if (hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
            or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256):
        raise ValueError("credential-vault candidate metadata changed")
    entries = json.loads(manifest.read_text())["migrations"]
    expected = {
        "number": 155, "from_schema": 154, "to_schema": 155,
        "compatibility": "expand-only",
        "path": "web/database/migrations/155_add_data_source_credential_vault.sql",
    }
    if len(entries) != 1 or {key: entries[0].get(key) for key in expected} != expected:
        raise ValueError("credential-vault candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/155_add_data_source_credential_vault.sql"
    if (original.read_bytes() != mirror.read_bytes()
            or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]):
        raise ValueError("credential-vault SQL mirror or checksum invalid")
    sql = original.read_text(encoding="utf-8")
    required = (
        "create table public.data_source_credentials",
        "create table public.data_source_credential_events",
        "revoke all on public.data_source_credentials,public.data_source_credential_events from public,anon,authenticated",
        "create function public.complete_incremental_ingestion155",
        "create function public.complete_data_source_credential_rewrap155",
        "v_source.credential_revision<>p_credential_revision",
        "v_credential.status<>'active'",
    )
    if any(value not in sql for value in required):
        raise ValueError("credential-vault safety contract invalid")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 154, "compatible_max": 155, "target": 155,
        "migration_class": "expand-only", "rollback_compatible_min": 154,
        "rollback_compatible_max": 154,
    }
    if (value["schema"] != expected_schema
            or value["migration_manifest"] != manifest.name
            or value["deployment_profile"] != "data-source-credential-vault154-155"):
        raise ValueError("credential-vault compatibility invalid")
    return entries


if __name__ == "__main__":
    validated_entries(Path(__file__).resolve().parents[2])

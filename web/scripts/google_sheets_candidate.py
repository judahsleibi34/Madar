"""Validate the exact unselected 160→161 Google Sheets candidate."""
import hashlib
import json
import re
from pathlib import Path


MANIFEST_SHA256 = "fdb282afa809f920413f69dadb4db70444cec7b15c06b0f1b8c02a58d781a8a8"
BRIDGE_SHA256 = "2f01a863b6c6d782e356b16834f0137aa3949e4552a768b8bb202575d24237bc"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-160-161-google-sheets.json"
    bridge = release / "schema-160-161-google-sheets-bridge.json"
    if (hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
            or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256):
        raise ValueError("google-sheets candidate metadata changed")
    entries = json.loads(manifest.read_text())["migrations"]
    expected = {
        "number": 161, "from_schema": 160, "to_schema": 161,
        "compatibility": "expand-only",
        "path": "web/database/migrations/161_add_google_sheets_connector.sql",
    }
    if len(entries) != 1 or {key: entries[0].get(key) for key in expected} != expected:
        raise ValueError("google-sheets candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/161_add_google_sheets_connector.sql"
    if (original.read_bytes() != mirror.read_bytes()
            or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]):
        raise ValueError("google-sheets SQL mirror or checksum invalid")
    sql = re.sub(r"--[^\n]*|/\*.*?\*/", "", original.read_text(), flags=re.S).lower()
    required = (
        "v_schema_version public.application_schema_state.schema_version%type",
        "where contract_key = 'core'", "for update",
        "if v_schema_version<>160", "create table public.data_source_oauth_transactions",
        "create table public.google_sheets_source_mappings",
        "create function public.begin_data_source_oauth161",
        "create function public.consume_data_source_oauth161",
        "create function public.save_google_sheets_mapping161",
        "create function public.complete_noop_source_ingestion161",
        "reconciliation_state='resolved'", "reconciliation_code='no_changes'",
        "provider_key='google_sheets'", "consumed_at is null and expires_at>now()",
        "enable row level security", "from public,anon,authenticated",
        "update public.application_schema_state set schema_version=161",
    )
    if any(value not in sql for value in required):
        raise ValueError("google-sheets safety contract invalid")
    first_ddl = min(sql.index("create table"), sql.index("create function"))
    if sql.index("for update") > first_ddl or sql.index("v_schema_version<>160") > first_ddl:
        raise ValueError("schema-state lock and predecessor guard must precede DDL")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 160, "compatible_max": 161, "target": 161,
        "migration_class": "expand-only", "rollback_compatible_min": 160,
        "rollback_compatible_max": 160,
    }
    if (value["schema"] != expected_schema
            or value["migration_manifest"] != manifest.name
            or value["deployment_profile"] != "google-sheets160-161"):
        raise ValueError("google-sheets compatibility invalid")
    return entries


if __name__ == "__main__":
    validated_entries(Path(__file__).resolve().parents[2])

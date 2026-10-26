"""Validate the exact unselected 161→162 secure-webhook candidate."""
import hashlib
import json
import re
from pathlib import Path


MANIFEST_SHA256 = "837b7660ca06e34e5b1f0ab01341d28a3bde39bd37989eab82c62f0ddce914de"
BRIDGE_SHA256 = "e3a73cec1370c543d69fe8a41ef9aa4b19b6cd3adf7dcee2ff490c5552f08dba"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-161-162-webhooks.json"
    bridge = release / "schema-161-162-webhooks-bridge.json"
    if (hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
            or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256):
        raise ValueError("webhook candidate metadata changed")
    entries = json.loads(manifest.read_text())["migrations"]
    expected = {
        "number": 162, "from_schema": 161, "to_schema": 162,
        "compatibility": "expand-only",
        "path": "web/database/migrations/162_add_secure_webhook_ingestion.sql",
    }
    if len(entries) != 1 or {key: entries[0].get(key) for key in expected} != expected:
        raise ValueError("webhook candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/162_add_secure_webhook_ingestion.sql"
    if (original.read_bytes() != mirror.read_bytes()
            or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]):
        raise ValueError("webhook SQL mirror or checksum invalid")
    sql = re.sub(r"--[^\n]*|/\*.*?\*/", "", original.read_text(), flags=re.S).lower()
    required = (
        "v_schema_version public.application_schema_state.schema_version%type",
        "where contract_key = 'core'", "for update", "if v_schema_version<>161",
        "create table public.data_source_webhook_endpoints",
        "create table public.data_source_webhook_events",
        "unique(endpoint_id,provider_event_id)", "for update skip locked",
        "create function public.resolve_data_source_webhook162",
        "create function public.accept_data_source_webhook_event162",
        "create function public.claim_data_source_webhook_events162",
        "create function public.complete_data_source_webhook_event162",
        "create function public.fail_data_source_webhook_event162",
        "create function public.request_webhook_reconciliation162",
        "enable row level security", "from public,anon,authenticated",
        "update public.application_schema_state", "set schema_version=162",
    )
    if any(value not in sql for value in required):
        raise ValueError("webhook safety contract invalid")
    first_ddl = min(sql.index("create table"), sql.index("create function"))
    transition = sql[:first_ddl]
    transition_pattern = re.compile(
        r"do\s*\$\$\s*declare\s+"
        r"v_schema_version\s+public\.application_schema_state\.schema_version%type\s*;\s*"
        r"begin\s+select\s+schema_version\s+into\s+v_schema_version\s+"
        r"from\s+public\.application_schema_state\s+where\s+contract_key\s*=\s*'core'\s+"
        r"for\s+update\s*;\s*if\s+v_schema_version\s+is\s+null\s+then\b.*?end\s+if\s*;\s*"
        r"if\s+v_schema_version\s*<>\s*161\s+then\b.*?end\s+if\s*;\s*end\s*;\s*\$\$\s*;",
        re.S,
    )
    if not transition_pattern.search(transition):
        raise ValueError("schema-state lock and predecessor guard must precede DDL")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 161, "compatible_max": 162, "target": 162,
        "migration_class": "expand-only", "rollback_compatible_min": 161,
        "rollback_compatible_max": 161,
    }
    if (value["schema"] != expected_schema
            or value["migration_manifest"] != manifest.name
            or value["deployment_profile"] != "webhooks161-162"):
        raise ValueError("webhook compatibility invalid")
    return entries


if __name__ == "__main__":
    validated_entries(Path(__file__).resolve().parents[2])

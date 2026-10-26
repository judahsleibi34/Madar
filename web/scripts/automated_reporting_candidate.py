"""Validate the exact unselected 163→164 automated reporting candidate."""
import hashlib
import json
import re
from pathlib import Path


MANIFEST_SHA256 = "982d41f6cd551118166d360a3a6aab8d233a058e570bcec5225ce791eba029e0"
BRIDGE_SHA256 = "443b6055175c1645d06d63efafb69d1ab935aab859403f4cf82ecfba10ea20a8"


def validated_entries(root):
    root = Path(root)
    releases = root / "web/deployment/releases"
    manifest = releases / "migrations-163-164-automated-reporting.json"
    bridge = releases / "schema-163-164-automated-reporting-bridge.json"
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256 \
            or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256:
        raise ValueError("automated reporting candidate metadata changed")
    entries = json.loads(manifest.read_text())["migrations"]
    expected = {"number": 164, "from_schema": 163, "to_schema": 164,
                "compatibility": "expand-only",
                "path": "web/database/migrations/164_add_automated_reporting.sql"}
    if len(entries) != 1 or {key: entries[0].get(key) for key in expected} != expected:
        raise ValueError("automated reporting candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/164_add_automated_reporting.sql"
    if original.read_bytes() != mirror.read_bytes() \
            or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]:
        raise ValueError("automated reporting SQL mirror or checksum invalid")
    sql = re.sub(r"--[^\n]*|/\*.*?\*/", "", original.read_text(), flags=re.S).lower()
    required = (
        "v_schema_version public.application_schema_state.schema_version%type",
        "where contract_key='core' for update", "if v_schema_version<>163",
        "create table public.bi_report_schedules", "create table public.bi_report_runs",
        "alter table public.bi_report_schedules enable row level security",
        "alter table public.bi_report_runs enable row level security",
        "from public,anon,authenticated", "auto_refresh_enabled",
        "create function public.enqueue_bi_report_run164",
        "create function public.claim_bi_report_runs164", "for update skip locked",
        "create function public.heartbeat_bi_report_run164",
        "create function public.complete_bi_report_run164",
        "create function public.fail_bi_report_run164",
        "create function public.recover_expired_bi_report_runs164",
        "create function public.archive_bi_report_run164", "archived_at",
        "definition_snapshot", "version_vector", "deduplication_key",
        "lease_token", "lease_fence", "artifact_sha256",
        "set schema_version=164",
    )
    if any(value not in sql for value in required):
        raise ValueError("automated reporting safety contract invalid")
    first_ddl = min(sql.index("alter table public.bi_dashboards"), sql.index("create table"))
    if "for update" not in sql[:first_ddl] or "v_schema_version<>163" not in sql[:first_ddl]:
        raise ValueError("schema-state lock and predecessor guard must precede DDL")
    value = json.loads(bridge.read_text())
    expected_schema = {"compatible_min": 163, "compatible_max": 164, "target": 164,
                       "migration_class": "expand-only", "rollback_compatible_min": 163,
                       "rollback_compatible_max": 163}
    if value["schema"] != expected_schema or value["migration_manifest"] != manifest.name \
            or value["deployment_profile"] != "automated-reporting163-164":
        raise ValueError("automated reporting compatibility invalid")
    return entries


if __name__ == "__main__":
    validated_entries(Path(__file__).resolve().parents[2])

"""Validate the exact unselected 162→163 BI dashboard candidate."""
import hashlib
import json
import re
from pathlib import Path


MANIFEST_SHA256 = "6dd760b48e35ea36c1563bc2d70bff0a6fd6cd6ee8952effe2a4f170049fd7ca"
BRIDGE_SHA256 = "da858f46ed63089c474555505dada52e8e0477ff56d381f0acf6a3efd72bdf60"


def validated_entries(root):
    root = Path(root)
    release = root / "web/deployment/releases"
    manifest = release / "migrations-162-163-bi-dashboards.json"
    bridge = release / "schema-162-163-bi-dashboards-bridge.json"
    if (hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256
            or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256):
        raise ValueError("BI dashboard candidate metadata changed")
    entries = json.loads(manifest.read_text())["migrations"]
    expected = {
        "number": 163, "from_schema": 162, "to_schema": 163,
        "compatibility": "expand-only",
        "path": "web/database/migrations/163_add_bi_dashboards.sql",
    }
    if len(entries) != 1 or {key: entries[0].get(key) for key in expected} != expected:
        raise ValueError("BI dashboard candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/163_add_bi_dashboards.sql"
    if (original.read_bytes() != mirror.read_bytes()
            or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]):
        raise ValueError("BI dashboard SQL mirror or checksum invalid")
    sql = re.sub(r"--[^\n]*|/\*.*?\*/", "", original.read_text(), flags=re.S).lower()
    required = (
        "v_schema_version public.application_schema_state.schema_version%type",
        "where contract_key = 'core'", "for update", "if v_schema_version<>162",
        "create table public.bi_dashboards", "create table public.bi_dashboard_widgets",
        "alter table public.bi_dashboards enable row level security",
        "alter table public.bi_dashboard_widgets enable row level security",
        "from public,anon,authenticated",
        "create function public.create_bi_dashboard163",
        "create function public.update_bi_dashboard163",
        "create function public.add_bi_dashboard_widget163",
        "create function public.update_bi_dashboard_widget163",
        "create function public.delete_bi_dashboard_widget163",
        "create function public.delete_bi_dashboard163",
        "dataset_version_id", "version_policy", "analysis_spec", "layout_config",
        "update public.application_schema_state", "set schema_version=163",
    )
    if any(value not in sql for value in required):
        raise ValueError("BI dashboard safety contract invalid")
    first_ddl = min(sql.index("create table"), sql.index("create function"))
    transition = sql[:first_ddl]
    transition_pattern = re.compile(
        r"do\s*\$\$\s*declare\s+"
        r"v_schema_version\s+public\.application_schema_state\.schema_version%type\s*;\s*"
        r"begin\s+select\s+schema_version\s+into\s+v_schema_version\s+"
        r"from\s+public\.application_schema_state\s+where\s+contract_key\s*=\s*'core'\s+"
        r"for\s+update\s*;\s*if\s+v_schema_version\s+is\s+null\s+then\b.*?end\s+if\s*;\s*"
        r"if\s+v_schema_version\s*<>\s*162\s+then\b.*?end\s+if\s*;\s*end\s*;\s*\$\$\s*;",
        re.S,
    )
    if not transition_pattern.search(transition):
        raise ValueError("schema-state lock and predecessor guard must precede DDL")
    value = json.loads(bridge.read_text())
    expected_schema = {
        "compatible_min": 162, "compatible_max": 163, "target": 163,
        "migration_class": "expand-only", "rollback_compatible_min": 162,
        "rollback_compatible_max": 162,
    }
    if (value["schema"] != expected_schema
            or value["migration_manifest"] != manifest.name
            or value["deployment_profile"] != "bi-dashboards162-163"):
        raise ValueError("BI dashboard compatibility invalid")
    return entries


if __name__ == "__main__":
    validated_entries(Path(__file__).resolve().parents[2])

"""Validate the exact unselected 164→165 private BI sharing candidate."""
import hashlib
import json
import re
from pathlib import Path


MANIFEST_SHA256 = "51ee4bbb4ace20c9178eb8b2b20c6b75add50e34b655ebf7ac3cacda10d42267"
BRIDGE_SHA256 = "6d7dc03ba4cd63f713d23cddbc418734af30e06b646c6bd4d7fca29a8216f771"


def validated_entries(root):
    root = Path(root)
    releases = root / "web/deployment/releases"
    manifest = releases / "migrations-164-165-bi-team-sharing.json"
    bridge = releases / "schema-164-165-bi-team-sharing-bridge.json"
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256 \
            or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256:
        raise ValueError("BI sharing candidate metadata changed")
    entries = json.loads(manifest.read_text())["migrations"]
    expected = {"number": 165, "from_schema": 164, "to_schema": 165,
                "compatibility": "expand-only",
                "path": "web/database/migrations/165_add_bi_team_sharing.sql"}
    if len(entries) != 1 or {key: entries[0].get(key) for key in expected} != expected:
        raise ValueError("BI sharing candidate transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/165_add_bi_team_sharing.sql"
    if original.read_bytes() != mirror.read_bytes() \
            or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]:
        raise ValueError("BI sharing SQL mirror or checksum invalid")
    sql = re.sub(r"--[^\n]*|/\*.*?\*/", "", original.read_text(), flags=re.S).lower()
    required = (
        "where contract_key='core'", "for update", "if v_schema_version<>164",
        "create table public.bi_dashboard_shares", "create table public.bi_report_shares",
        "permission in ('viewer','editor')", "permission='viewer'", "member_user_id<>owner_user_id",
        "foreign key(dashboard_id,tenant_id,project_id,owner_user_id)",
        "foreign key(report_id,tenant_id,project_id,owner_user_id)",
        "references public.tenant_memberships(user_id,tenant_id)",
        "alter table public.bi_dashboard_shares enable row level security",
        "alter table public.bi_report_shares enable row level security",
        "from public,anon,authenticated", "to service_role",
        "create function public.set_bi_dashboard_share165",
        "create function public.revoke_bi_dashboard_share165",
        "create function public.set_bi_report_share165",
        "create function public.revoke_bi_report_share165",
        "dashboard_revision_conflict", "report_share_revision_conflict",
        "m.status='active'", "u.account_status='active'", "set schema_version=165",
    )
    if any(value not in sql for value in required):
        raise ValueError("BI sharing safety contract invalid")
    first_ddl = min(sql.index("alter table public.bi_dashboards"), sql.index("create table"))
    if "for update" not in sql[:first_ddl] or "v_schema_version<>164" not in sql[:first_ddl]:
        raise ValueError("schema-state lock and predecessor guard must precede DDL")
    value = json.loads(bridge.read_text())
    expected_schema = {"compatible_min": 164, "compatible_max": 165, "target": 165,
                       "migration_class": "expand-only", "rollback_compatible_min": 164,
                       "rollback_compatible_max": 164}
    if value["schema"] != expected_schema or value["migration_manifest"] != manifest.name \
            or value["deployment_profile"] != "bi-team-sharing164-165":
        raise ValueError("BI sharing compatibility invalid")
    return entries


if __name__ == "__main__":
    validated_entries(Path(__file__).resolve().parents[2])

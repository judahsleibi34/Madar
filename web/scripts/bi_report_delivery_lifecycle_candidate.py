"""Validate the exact unselected 165→166 report delivery/lifecycle candidate."""
import hashlib
import json
import re
from pathlib import Path


MANIFEST_SHA256 = "7010eebcd286d44c38e6db9bad35042feddc861ea2a69a00a6d05363fee7cbe9"
BRIDGE_SHA256 = "69404241442c90b8687f77d94f4e81904079fad733ec1ce3049b535fb8e7cda6"


def validated_entries(root):
    root = Path(root)
    releases = root / "web/deployment/releases"
    manifest = releases / "migrations-165-166-bi-report-delivery-lifecycle.json"
    bridge = releases / "schema-165-166-bi-report-delivery-lifecycle-bridge.json"
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != MANIFEST_SHA256 \
            or hashlib.sha256(bridge.read_bytes()).hexdigest() != BRIDGE_SHA256:
        raise ValueError("report delivery lifecycle candidate metadata changed")
    entries = json.loads(manifest.read_text())["migrations"]
    expected = {"number": 166, "from_schema": 165, "to_schema": 166,
                "compatibility": "expand-only",
                "path": "web/database/migrations/166_add_bi_report_delivery_lifecycle.sql"}
    if len(entries) != 1 or {key: entries[0].get(key) for key in expected} != expected:
        raise ValueError("report delivery lifecycle transition invalid")
    original = root / entries[0]["path"]
    mirror = root / "web/supabase/migrations/166_add_bi_report_delivery_lifecycle.sql"
    if original.read_bytes() != mirror.read_bytes() \
            or hashlib.sha256(original.read_bytes()).hexdigest() != entries[0]["sha256"]:
        raise ValueError("report delivery lifecycle SQL mirror or checksum invalid")
    sql = re.sub(r"--[^\n]*|/\*.*?\*/", "", original.read_text(), flags=re.S).lower()
    required = (
        "if v_schema_version<>165", "for update",
        "create table public.bi_report_delivery_configs", "create table public.bi_report_delivery_recipients",
        "create table public.bi_report_lifecycle_settings", "create table public.bi_report_deliveries",
        "create table public.bi_report_cleanup_jobs", "retention_days between 7 and 365",
        "status in ('pending','processing','retry_pending','sent','failed','revoked')",
        "unique(report_id,recipient_user_id,channel)", "for update skip locked",
        "create function public.configure_bi_report_delivery166",
        "create function public.configure_bi_report_lifecycle166",
        "create function public.complete_bi_report_run166",
        "create function public.claim_bi_report_deliveries166",
        "create function public.authorize_bi_report_delivery166",
        "create function public.finish_bi_report_delivery166",
        "create function public.claim_bi_report_cleanup166",
        "create function public.authorize_bi_report_cleanup166",
        "create function public.finish_bi_report_cleanup166",
        "report_delivery_access_revoked", "cleanup_disabled", "artifact_deleted_at",
        "from public,anon,authenticated", "to service_role", "set schema_version=166",
    )
    if any(value not in sql for value in required):
        raise ValueError("report delivery lifecycle safety contract invalid")
    first_ddl = min(sql.index("alter table public.bi_report_schedules"), sql.index("create table"))
    if "for update" not in sql[:first_ddl] or "v_schema_version<>165" not in sql[:first_ddl]:
        raise ValueError("schema-state lock and predecessor guard must precede DDL")
    value = json.loads(bridge.read_text())
    expected_schema = {"compatible_min": 165, "compatible_max": 166, "target": 166,
                       "migration_class": "expand-only", "rollback_compatible_min": 165,
                       "rollback_compatible_max": 165}
    if value["schema"] != expected_schema or value["migration_manifest"] != manifest.name \
            or value["deployment_profile"] != "bi-report-delivery-lifecycle165-166":
        raise ValueError("report delivery lifecycle compatibility invalid")
    return entries


if __name__ == "__main__":
    validated_entries(Path(__file__).resolve().parents[2])

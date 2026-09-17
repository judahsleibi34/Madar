"""Guarded operator-only reconciliation of Supabase's migration ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit


SHA = re.compile(r"^[0-9a-f]{40}$")
LEDGER_ROW = re.compile(r"^\s*(\d*)\s*\|\s*(\d*)\s*\|", re.MULTILINE)


def load_json(path: Path, code: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(code) from error
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def migration_ledger(output: str) -> set[int]:
    return {int(remote) for _local, remote in LEDGER_ROW.findall(output) if remote}


def default_json_reader(url: str, headers: dict[str, str]) -> object:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read())


def _run(
    *,
    release_sha: str,
    repository_root: Path,
    state_root: Path,
    supabase_bin: str,
    confirmation: str | None,
    dry_run: bool,
    migration_version: int | None = None,
    environ: dict[str, str] | None = None,
    runner: Callable = subprocess.run,
    json_reader: Callable = default_json_reader,
) -> dict:
    environment = dict(os.environ if environ is None else environ)
    if not SHA.fullmatch(release_sha):
        raise RuntimeError("ledger_reconciliation_release_sha_invalid")
    if not repository_root.is_absolute() or not state_root.is_absolute():
        raise RuntimeError("ledger_reconciliation_absolute_roots_required")
    repository_root = repository_root.resolve()
    state_root = state_root.resolve()

    def command(arguments: list[str]) -> subprocess.CompletedProcess:
        completed = runner(arguments, cwd=repository_root, env=environment, text=True, capture_output=True, check=False)
        if completed.returncode:
            raise RuntimeError(f"ledger_reconciliation_command_failed:{arguments[0]}")
        return completed

    top = Path(command(["git", "-C", str(repository_root), "rev-parse", "--show-toplevel"]).stdout.strip()).resolve()
    if top != repository_root:
        raise RuntimeError("ledger_reconciliation_repository_root_mismatch")
    if command(["git", "-C", str(repository_root), "status", "--porcelain", "--untracked-files=normal"]).stdout.strip():
        raise RuntimeError("ledger_reconciliation_repository_dirty")
    if command(["git", "-C", str(repository_root), "rev-parse", "HEAD"]).stdout.strip().lower() != release_sha:
        raise RuntimeError("ledger_reconciliation_release_sha_mismatch")

    web_root = repository_root / "web"
    release = load_json(web_root / "deployment/releases/release.json", "ledger_reconciliation_release_contract_invalid")
    target = int(release.get("schema", {}).get("target", -1))
    manifest_name = str(release.get("migration_manifest") or "")
    version = target if migration_version is None else migration_version
    if target not in {97, 98, 99, 100, 101} or version not in {97, 98, 99, 100, 101} or version > target or not manifest_name or Path(manifest_name).name != manifest_name:
        raise RuntimeError("ledger_reconciliation_release_contract_invalid")
    manifest = load_json(web_root / "deployment/releases" / manifest_name, "ledger_reconciliation_manifest_invalid")
    manifest_release = str(manifest.get("release_sha") or "")
    if manifest_release not in {release_sha, "CURRENT", "STAGING"}:
        raise RuntimeError("ledger_reconciliation_manifest_release_mismatch")
    entries = manifest.get("migrations", [])
    numbers = [item.get("number") for item in entries]
    if not numbers or numbers != list(range(numbers[0], target + 1)):
        raise RuntimeError("ledger_reconciliation_manifest_transition_invalid")
    for item in entries:
        number = item.get("number")
        if number not in {97, 98, 99, 100, 101} or item.get("from_schema") != number - 1 or item.get("to_schema") != number:
            raise RuntimeError("ledger_reconciliation_manifest_transition_invalid")
    matching = [item for item in entries if item.get("number") == version]
    if len(matching) != 1 or int(matching[0].get("from_schema", -1)) != version - 1 or int(matching[0].get("to_schema", -1)) != version:
        raise RuntimeError("ledger_reconciliation_manifest_transition_invalid")
    migration = (repository_root / str(matching[0].get("path", ""))).resolve()
    try:
        migration.relative_to(repository_root)
    except ValueError as error:
        raise RuntimeError("ledger_reconciliation_migration_escape") from error
    canonical = list((web_root / "database/migrations").glob(f"{version:03d}_*.sql"))
    if len(canonical) != 1 or migration != canonical[0].resolve():
        raise RuntimeError("ledger_reconciliation_migration_path_invalid")
    mirror = web_root / "supabase/migrations" / migration.name
    if not mirror.is_file() or mirror.read_bytes() != migration.read_bytes():
        raise RuntimeError("ledger_reconciliation_migration_checksum_mismatch")
    expected_checksum = str(matching[0].get("sha256") or "").lower()
    actual_checksum = hashlib.sha256(migration.read_bytes()).hexdigest() if migration.is_file() else ""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_checksum) or actual_checksum != expected_checksum:
        raise RuntimeError("ledger_reconciliation_migration_checksum_mismatch")

    state = load_json(state_root / "state.json", "ledger_reconciliation_release_state_invalid")
    if state.get("in_progress_release") or state.get("rollback_failure"):
        raise RuntimeError("ledger_reconciliation_release_in_progress")
    known_good = state.get("known_good_release") or {}
    if known_good.get("sha") != release_sha or int(known_good.get("schema", -1)) != target or known_good.get("slot") != state.get("active_slot"):
        raise RuntimeError("ledger_reconciliation_known_good_not_at_target")
    migration_root = state_root / "migrations" / release_sha
    automation = load_json(migration_root / "automation.json", "ledger_reconciliation_automation_state_invalid")
    execution_file = migration_root / "execution.json"
    if automation.get("phase") == "already_at_target":
        # This canonical coordinator outcome proves a fresh release accepted
        # after the transition. It owns no SQL execution or worker refresh;
        # promotion supplied worker validation and the coordinator rechecked
        # active/stable health before atomically recording completion.
        acceptance = next((event for event in reversed(state.get("history", []))
                           if event.get("release_sha") == release_sha
                           and event.get("status") == "known_good"
                           and event.get("phase") == "complete"), None)
        if (
            automation.get("status") != "completed"
            or automation.get("release_sha") != release_sha
            or automation.get("source_schema") != entries[0]["from_schema"]
            or automation.get("target_schema") != target
            or automation.get("observed_schema") != target
            or automation.get("execution_status") != "already_at_target"
            or "backup" not in automation or automation["backup"] is not None
            or automation.get("failure_semantics") != "not_required_already_at_target"
            or not automation.get("completed_at")
            or execution_file.exists() or execution_file.is_symlink()
            or release.get("migration_policy") != "automatic-after-known-good-backup-first-forward-repair"
            or release.get("schema", {}).get("migration_class") not in {"expand-only", "forward-compatible"}
        ):
            raise RuntimeError("ledger_reconciliation_already_at_target_evidence_invalid")
        if acceptance is None or (acceptance.get("schema") or {}).get("observed") != target:
            raise RuntimeError("ledger_reconciliation_health_evidence_missing")
    else:
        if not any(event.get("release_sha") == release_sha and event.get("phase") == "post_migration_workers_refreshed" and int((event.get("schema") or {}).get("observed", -1)) == target for event in state.get("history", [])):
            raise RuntimeError("ledger_reconciliation_health_evidence_missing")
        execution = load_json(execution_file, "ledger_reconciliation_execution_state_invalid")
        if automation.get("status") != "completed" or automation.get("phase") != "post_migration_validation_complete" or int(automation.get("observed_schema", -1)) != target:
            raise RuntimeError("ledger_reconciliation_automation_not_complete")
        if execution.get("status") != "completed" or execution.get("phase") != "complete" or int(execution.get("observed_schema", -1)) != target:
            raise RuntimeError("ledger_reconciliation_execution_not_complete")
        executed = [item for item in execution.get("migrations", []) if int(item.get("number", -1)) == version]
        if len(executed) != 1 or executed[0].get("status") not in {"applied", "already_applied"} or executed[0].get("checksum") != expected_checksum:
            raise RuntimeError("ledger_reconciliation_execution_checksum_mismatch")

    supabase_url = environment.get("SUPABASE_URL", "").rstrip("/")
    service_key = environment.get("SUPABASE_SERVICE_KEY", "")
    if not supabase_url or not service_key:
        raise RuntimeError("ledger_reconciliation_supabase_read_config_missing")
    hostname = (urlsplit(supabase_url).hostname or "").lower()
    expected_project_ref = (
        hostname.split(".", 1)[0]
        if hostname.endswith(".supabase.co")
        else environment.get("MADAR_SUPABASE_PROJECT_REF", "").strip()
    )
    linked_ref_path = web_root / "supabase/.temp/project-ref"
    linked_ref = linked_ref_path.read_text(encoding="utf-8").strip() if linked_ref_path.is_file() else ""
    if not expected_project_ref or linked_ref != expected_project_ref:
        raise RuntimeError("ledger_reconciliation_linked_project_mismatch")
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
    rows = json_reader(f"{supabase_url}/rest/v1/application_schema_state?select=schema_version&contract_key=eq.core", headers)
    if not isinstance(rows, list) or len(rows) != 1 or int(rows[0].get("schema_version", -1)) != target:
        raise RuntimeError("ledger_reconciliation_live_schema_not_at_target")
    backend = environment.get("MADAR_STABLE_BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")
    identity = json_reader(f"{backend}/health/version", {})
    readiness = json_reader(f"{backend}/health/ready", {})
    if not isinstance(identity, dict) or identity.get("release_sha") != release_sha or not isinstance(readiness, dict) or readiness.get("ready") is not True:
        raise RuntimeError("ledger_reconciliation_stable_health_invalid")

    list_command = [supabase_bin, "--workdir", str(web_root), "migration", "list", "--linked"]
    before = migration_ledger(command(list_command).stdout)
    if any(version > target for version in before):
        raise RuntimeError("ledger_reconciliation_remote_ledger_ahead")
    if version - 1 not in before or any(number < version and number not in before for number in numbers):
        raise RuntimeError("ledger_reconciliation_remote_predecessor_missing")
    if version not in before and any(number > version for number in before):
        raise RuntimeError("ledger_reconciliation_remote_order_invalid")
    audit = state_root / "ledger-reconciliations" / f"{version:03d}.json"
    prior_audit = load_json(audit, "ledger_reconciliation_audit_invalid") if audit.exists() else None
    if prior_audit is not None:
        expected_identity = {
            "release_sha": release_sha,
            "migration": version,
            "migration_sha256": expected_checksum,
            "schema": target,
            "project_ref": expected_project_ref,
        }
        if any(prior_audit.get(key) != value for key, value in expected_identity.items()):
            raise RuntimeError("ledger_reconciliation_audit_identity_mismatch")
        if version not in before:
            raise RuntimeError("ledger_reconciliation_audit_ledger_drift")
    action = "already_reconciled" if version in before else "would_reconcile" if dry_run else "reconciled"
    if version not in before and not dry_run:
        if confirmation != f"{version:03d}:{expected_checksum}":
            raise RuntimeError("ledger_reconciliation_confirmation_mismatch")
        command([supabase_bin, "--workdir", str(web_root), "migration", "repair", "--linked", "--status", "applied", f"{version:03d}"])
        after = migration_ledger(command(list_command).stdout)
        if after != before | {version}:
            raise RuntimeError("ledger_reconciliation_postcondition_failed")

    result = {
        "status": "validated" if dry_run else "completed",
        "action": action,
        "release_sha": release_sha,
        "migration": version,
        "migration_sha256": expected_checksum,
        "schema": target,
        "project_ref": expected_project_ref,
        "tenant_data_touched": False,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    if not dry_run:
        if confirmation != f"{version:03d}:{expected_checksum}":
            raise RuntimeError("ledger_reconciliation_confirmation_mismatch")
        if prior_audit is not None:
            result["completed_at"] = prior_audit.get("completed_at")
            result["action"] = "already_reconciled"
        else:
            atomic_json(audit, result)
    return result



def run(*, state_root: Path, **arguments) -> dict:
    """Serialize ledger changes with the same host lock as release/migration work."""
    if not state_root.is_absolute() or not state_root.is_dir():
        raise RuntimeError("ledger_reconciliation_absolute_roots_required")
    descriptor = os.open(state_root / "deploy.lock", os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if os.name == "nt":
            import msvcrt
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"0")
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run(state_root=state_root, **arguments)
    finally:
        os.close(descriptor)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile a coordinator-verified migration into the Supabase CLI ledger.")
    parser.add_argument("--migration-version", required=True, choices=("097", "098", "099", "100", "101"))
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--supabase-bin", default="supabase")
    parser.add_argument("--confirm")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run(migration_version=int(args.migration_version), release_sha=args.release_sha.lower(), repository_root=args.repository_root, state_root=args.state_root, supabase_bin=args.supabase_bin, confirmation=args.confirm, dry_run=args.dry_run)
    except Exception as error:
        print(f"ledger reconciliation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

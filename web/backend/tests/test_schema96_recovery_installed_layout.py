"""Disposable installed-layout rehearsal for the schema-96 recovery state machine."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


WEB_ROOT = Path(
    os.getenv("MADAR_TEST_REPOSITORY_ROOT")
    or Path(__file__).resolve().parents[2]
).resolve()


class InstalledLayoutRecoveryTests(unittest.TestCase):
    def test_installed_layout_interruption_resume_and_next_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = root / "control"
            shutil.copytree(WEB_ROOT / "deployment", control / "deployment")
            shutil.copytree(WEB_ROOT / "scripts", control / "deployment/scripts")
            # Freeze this historical 096->099 recovery fixture independently of
            # the current production-based 099->101 release contract.
            metadata_path = control / "deployment/releases/release.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["schema"].update(compatible_min=81, compatible_max=99, target=99,
                                      rollback_compatible_min=81, rollback_compatible_max=98)
            metadata["migration_manifest"] = "migrations-099.json"
            metadata["notes"] = "Historical schema-096 to commercial schema-099 test fixture."
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            runtime = root / "runtime"
            candidate = os.getenv("MADAR_REHEARSAL_CANDIDATE_SHA", "a" * 40)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--installed-harness",
                    str(control),
                    str(runtime),
                    candidate,
                ],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["schema"], 96)
        self.assertEqual(result["recovery_status"], "known_good")
        self.assertEqual(result["active_slot"], "green")
        self.assertEqual(result["fallback_slot"], "blue")
        self.assertEqual(result["fallback_sha"], candidate)
        self.assertEqual(result["next_release_status"], "known_good")
        self.assertTrue(result["ordinary_fallback_retired"])
        self.assertEqual(result["retained_slot"], "green")
        self.assertEqual(result["retained_sha"], candidate)
        self.assertEqual(result["migration_status"], "completed")
        self.assertEqual(result["migration_schema"], 99)
        self.assertEqual(result["migration_numbers"], [97, 98, 99])
        self.assertEqual(result["final_active_slot"], "blue")
        self.assertEqual(result["final_known_good_sha"], "b" * 40)
        self.assertEqual(result["final_known_good_schema"], 99)
        self.assertEqual(result["final_fallback_slot"], "green")
        self.assertEqual(result["final_fallback_sha"], "b" * 40)
        self.assertEqual(result["final_fallback_schema"], 99)
        self.assertFalse(result["final_fallback_workers_active"])
        self.assertTrue(result["fresh_backup_verified_before_sql"])
        self.assertTrue(result["migration_idempotent"])
        self.assertTrue(result["installed_helpers"])
        self.assertTrue(result["interruption_resumed"])
        self.assertFalse(result["worker_overlap"])


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    os.replace(temporary, path)


def _run_installed_harness(control: Path, runtime: Path, candidate: str) -> int:
    sys.path.insert(0, str(control))
    from deployment.lib.release_deployer import Compatibility, ReleaseDeployer

    cli_path = control / "deployment/bin/madar-release-deploy"
    loader = importlib.machinery.SourceFileLoader("installed_release_cli", str(cli_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    cli = importlib.util.module_from_spec(spec)
    loader.exec_module(cli)
    helper_root = cli.DockerGitOperations.recovery_helper_root()
    installed_helpers = all(
        (helper_root / name).is_file()
        for name in ("backup_support.py", "replicate_latest_node1.py")
    )

    runtime.mkdir()
    state_root = runtime / "release-state"
    state_root.mkdir()
    old_sha = "1" * 40
    _atomic_json(state_root / "state.json", {
        "active_slot": "blue",
        "known_good_release": {
            "sha": old_sha,
            "slot": "blue",
            "schema": 93,
            "images": {
                "backend": "old@sha256:" + "1" * 64,
                "frontend": "old@sha256:" + "2" * 64,
                "worker": "old@sha256:" + "3" * 64,
            },
        },
        "history": [],
        "failed_releases": {},
    })
    _atomic_json(runtime / "actual.json", {
        "schema": 96,
        "traffic": "blue",
        "slots": {"blue": old_sha},
        "workers": {"blue": True, "green": False},
        "worker_overlap": False,
    })
    (runtime / "backup-receipt.json").write_text(json.dumps({
        "backup_id": "madar-20260914T021837Z",
        "schema": 96,
        "local_verified": True,
        "node1_verified": True,
    }), encoding="utf-8")
    events = []

    class Operations:
        def __init__(self, *, interrupt=False):
            self.interrupt = interrupt

        def actual(self):
            return json.loads((runtime / "actual.json").read_text(encoding="utf-8"))

        def save(self, value):
            value["worker_overlap"] = value["worker_overlap"] or all(
                value["workers"].values()
            )
            _atomic_json(runtime / "actual.json", value)

        def verify_source(self, sha):
            if sha not in {candidate, "b" * 40}:
                raise RuntimeError("candidate_identity_mismatch")
            self.release_root = runtime / "source"

        def build(self, sha, _slot):
            return {
                "backend": f"backend@sha256:{'4' * 64}",
                "frontend": f"frontend@sha256:{'5' * 64}",
                "worker": f"worker@sha256:{'6' * 64}",
                "build_timestamp": "2026-09-14T00:00:00Z",
            }

        def schema_version(self): return int(self.actual()["schema"])
        def preflight(self, _sha, _slot, _images, schema):
            if schema not in {96, 99}: raise RuntimeError("schema_drift")
        def start_candidate(self, sha, slot, _images):
            events.append(f"start:{sha}:{slot}")
            if sha == "b" * 40 and slot == "green" and self.actual()["schema"] == 96:
                assert (runtime / "migration-backups/madar-20260916T000000Z/verified").is_file()
            value = self.actual(); value["slots"][slot] = sha; value["workers"][slot] = False; self.save(value)
        def validate_candidate(self, sha, slot):
            if self.actual()["slots"].get(slot) != sha: raise RuntimeError("candidate_invalid")
        def validate_rollback_target(self, release, schema):
            events.append(f"rollback:{release['sha']}:{release['slot']}:{schema}")
            if self.actual()["slots"].get(release["slot"]) != release["sha"]:
                raise RuntimeError("retained_identity_mismatch")
            minimum = int(release.get("schema_compatible_min", schema))
            maximum = int(release.get("schema_compatible_max", schema))
            if not minimum <= schema <= maximum: raise RuntimeError("fallback_incompatible")
            return {"compatible_min": minimum, "compatible_max": maximum}
        def run(self, command):
            subprocess.run(command, check=True, capture_output=True, text=True)
        def _json(self, url):
            value = self.actual()
            if url.endswith("/health/version"):
                return {"release_sha": value["slots"][value["traffic"]]}
            return {"ready": True}
        def validate_stable_candidate(self, sha):
            if self._json("/health/version")["release_sha"] != sha:
                raise RuntimeError("stable_identity_mismatch")
            events.append("stable")
        def validate_active_refresh_prerequisites(self, sha, slot, _images):
            self.validate_candidate(sha, slot)
        def refresh_active_runtime_services(self, sha, slot, images):
            events.append("refresh")
            self.activate_workers(sha, slot, images)
        def activate_workers(self, _sha, slot, _images):
            value = self.actual()
            if any(active for other, active in value["workers"].items() if other != slot):
                raise RuntimeError("consumer_overlap")
            value["workers"][slot] = True; self.save(value)
        def deactivate_workers(self, release):
            value = self.actual(); value["workers"][release["slot"]] = False; self.save(value)
        def restore_workers(self, release):
            value = self.actual()
            slot = release["slot"]
            if any(active for other, active in value["workers"].items() if other != slot):
                raise RuntimeError("consumer_overlap")
            value["workers"][slot] = True; self.save(value)
        def worker_ownership(self, retained, candidate):
            value = self.actual()
            old = bool(value["workers"].get(retained["slot"]))
            new = bool(value["workers"].get(candidate["slot"]))
            if old and new: return "overlap"
            if old: return "old"
            if new: return "candidate"
            return "none"
        def switch_traffic(self, slot):
            value = self.actual(); value["traffic"] = slot; self.save(value)
        def observe(self, _sha, _slot):
            if self.interrupt:
                self.interrupt = False
                raise KeyboardInterrupt()
        def stop_candidate(self, slot, *, expected_serving=None):
            value = self.actual()
            if expected_serving is not None and (
                value["traffic"] == slot
                or expected_serving.get(value["traffic"])
                != value["slots"].get(value["traffic"])
            ):
                raise RuntimeError("cannot_stop_unverified_or_serving_slot")
            if value["traffic"] == slot: raise RuntimeError("cannot_stop_serving_slot")
            value["slots"].pop(slot, None); value["workers"][slot] = False; self.save(value)
        def current_traffic_slot(self): return str(self.actual()["traffic"])
        def resolve_serving_slot(self, expected):
            value = self.actual(); slot = value["traffic"]
            return slot if expected.get(slot) == value["slots"].get(slot) else None
        def validate_recovery_backup(self, schema):
            receipt = json.loads((runtime / "backup-receipt.json").read_text())
            if not (receipt["local_verified"] and receipt["node1_verified"] and receipt["schema"] == schema):
                raise RuntimeError("backup_gate_failed")
            return {
                "backup_id": receipt["backup_id"], "schema": schema,
                "manifest_sha256": "7" * 64,
                "node1_sha256sums_sha256": "8" * 64,
            }

    recovery = Compatibility(96, 96, 96, "none", 96, 96)
    first = ReleaseDeployer(state_root=state_root, compatibility=recovery, operations=Operations(interrupt=True))
    try:
        first.recover_current_schema(candidate)
    except KeyboardInterrupt:
        pass
    else:
        raise RuntimeError("meaningful_interruption_not_injected")
    resumed = ReleaseDeployer(state_root=state_root, compatibility=recovery, operations=Operations())
    result = resumed.recover_current_schema(candidate)
    state = json.loads((state_root / "state.json").read_text())
    actual = json.loads((runtime / "actual.json").read_text())
    compatibility = Compatibility.load(control / "deployment/releases/release.json")
    operations = Operations()
    operations.compatibility = compatibility
    normal = ReleaseDeployer(
        state_root=state_root,
        compatibility=compatibility,
        operations=operations,
    ).deploy("b" * 40)
    promoted = json.loads((state_root / "state.json").read_text())
    if "compatible_fallback_release" in promoted:
        raise RuntimeError("ordinary_promotion_preserved_stale_fallback")

    # Use the installed coordinator and real manifest/checksum/transaction
    # executor against a disposable file-backed runtime and simulated cursor.
    # No real database or operational backup helper is invoked by this harness.
    source_web = runtime / "source/web"
    shutil.copytree(control / "deployment/releases", source_web / "deployment/releases")
    shutil.copytree(WEB_ROOT / "scripts", source_web / "scripts")
    for tree in ("database", "supabase"):
        source_tree = WEB_ROOT / tree
        if not source_tree.is_dir():
            source_tree = Path("/") / tree
        shutil.copytree(source_tree, source_web / tree)

    backup_root = runtime / "migration-backups"
    backup_root.mkdir()
    backup_script = runtime / "create-test-backup"
    verifier_script = runtime / "verify-test-backup"
    backup_script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os\nfrom pathlib import Path\n"
        "root = Path(os.environ['MADAR_BACKUP_DIR'])\n"
        "backup = root / 'madar-20260916T000000Z'\nbackup.mkdir()\n"
        "(backup / 'manifest.json').write_text(json.dumps({"
        "'format_version': 3, 'status': 'complete', 'backup_id': backup.name, "
        "'release': {'git_sha': os.environ['MADAR_RELEASE_SHA']}, "
        "'database': {'schema_version': 96}}))\n"
        "print(backup)\n",
        encoding="utf-8",
    )
    verifier_script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\nfrom pathlib import Path\n"
        "backup = Path(sys.argv[1])\n"
        "manifest = json.loads((backup / 'manifest.json').read_text())\n"
        "assert manifest['status'] == 'complete'\n"
        "assert manifest['database']['schema_version'] == 96\n"
        "assert manifest['release']['git_sha'] == 'b' * 40\n"
        "(backup / 'verified').write_text('verified')\n",
        encoding="utf-8",
    )
    backup_script.chmod(0o755)
    verifier_script.chmod(0o755)
    backup = backup_root / "madar-20260916T000000Z"

    manifest = cli.MigrationManifest.load(
        source_web / "deployment/releases/migrations-099.json", source_web.parent,
    )
    sql_transitions = {
        migration.path.read_text(): migration for migration in manifest.migrations
    }

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): pass
        def execute(self, sql, _parameters=None):
            if sql in sql_transitions:
                migration = sql_transitions[sql]
                value = operations.actual()
                if value["schema"] != migration.from_schema:
                    raise RuntimeError("noncontiguous_sql")
                assert sql.lstrip().lower().startswith("begin;")
                assert sql.rstrip().lower().endswith("commit;")
                assert (backup / "verified").is_file()
                fallback = json.loads((state_root / "state.json").read_text())["compatible_fallback_release"]
                assert fallback["sha"] == "b" * 40 and fallback["slot"] == "green"
                assert not value["workers"]["green"]
                events.append(f"sql:{migration.number}")
                value["schema"] = migration.to_schema
                operations.save(value)
        def fetchone(self): return (operations.schema_version(),)

    class Connection:
        def cursor(self): return Cursor()
        def rollback(self): pass
        def close(self): pass

    def connect(_url):
        assert (backup / "verified").is_file()
        events.append("database_connect")
        return Connection()

    def stable(**_kwargs):
        operations.validate_stable_candidate("b" * 40)

    with (
        patch.dict(os.environ, {
            "MADAR_BACKUP_DIR": str(backup_root),
            "MADAR_STORAGE_ROOT": str(runtime / "storage"),
            "MADAR_MIGRATION_BACKUP_SCRIPT": str(backup_script),
            "MADAR_MIGRATION_BACKUP_VERIFY_SCRIPT": str(verifier_script),
        }),
        patch("psycopg.connect", side_effect=connect),
        patch.object(cli, "_validate_stable_known_good", side_effect=stable),
    ):
        migration_result = cli.automatic_migrate_known_good(
            sha="b" * 40, state_root=state_root,
            compatibility=compatibility, operations=operations,
        )
        final_bytes = (state_root / "state.json").read_bytes()
        automation_file = state_root / "migrations" / ("b" * 40) / "automation.json"
        automation_bytes = automation_file.read_bytes()
        events_before = list(events)
        repeated = cli.automatic_migrate_known_good(
            sha="b" * 40, state_root=state_root,
            compatibility=compatibility, operations=operations,
        )
        assert repeated == migration_result
        assert final_bytes == (state_root / "state.json").read_bytes()
        assert automation_bytes == automation_file.read_bytes()
        assert events[len(events_before):] == ["stable"]
    final = json.loads(final_bytes)
    final_actual = operations.actual()
    assert events.index(f"rollback:{candidate}:green:96") < events.index("database_connect")
    assert events.index(f"start:{'b' * 40}:green") < events.index("sql:97")
    assert events.index("sql:99") < events.index("refresh")
    execution = json.loads((state_root / "migrations" / ("b" * 40) / "execution.json").read_text())
    print(json.dumps({
        "schema": actual["schema"],
        "recovery_status": result["status"],
        "active_slot": state["active_slot"],
        "fallback_slot": state["compatible_fallback_release"]["slot"],
        "fallback_sha": state["compatible_fallback_release"]["sha"],
        "next_release_status": normal["status"],
        "ordinary_fallback_retired": "compatible_fallback_release" not in promoted,
        "retained_slot": normal["previous_known_good_release"]["slot"],
        "retained_sha": normal["previous_known_good_release"]["sha"],
        "migration_status": migration_result["status"],
        "migration_schema": final_actual["schema"],
        "migration_numbers": [entry["number"] for entry in execution["migrations"]],
        "final_active_slot": final["active_slot"],
        "final_known_good_sha": final["known_good_release"]["sha"],
        "final_known_good_schema": final["known_good_release"]["schema"],
        "final_fallback_slot": final["compatible_fallback_release"]["slot"],
        "final_fallback_sha": final["compatible_fallback_release"]["sha"],
        "final_fallback_schema": final["compatible_fallback_release"]["schema"],
        "final_fallback_workers_active": final_actual["workers"]["green"],
        "fresh_backup_verified_before_sql": execution["backup"]["verified"],
        "migration_idempotent": True,
        "installed_helpers": installed_helpers,
        "interruption_resumed": True,
        "worker_overlap": final_actual["worker_overlap"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--installed-harness":
        raise SystemExit(_run_installed_harness(
            Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
        ))
    unittest.main()

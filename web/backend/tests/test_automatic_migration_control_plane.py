import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


WEB_ROOT = Path(
    os.getenv("MADAR_TEST_REPOSITORY_ROOT")
    or Path(__file__).resolve().parents[2]
).resolve()
RELEASE_DEPLOY = WEB_ROOT / "deployment/bin/madar-release-deploy"
PRODUCTION_DEPLOY = WEB_ROOT / "deployment/bin/madar-production-deploy"


def load_release_cli():
    loader = importlib.machinery.SourceFileLoader(
        "madar_release_deploy_automatic_migration_test",
        str(RELEASE_DEPLOY),
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError("unable to load release controller")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class FakeOperations:
    def __init__(self, release_root: Path, events: list[str], schema: int = 90):
        self.release_root = release_root
        self.events = events
        self.schema = schema

    def verify_source(self, sha: str) -> None:
        self.events.append(f"source:{sha}")

    def run(self, command: list[str]) -> None:
        self.events.append(f"validator:{Path(command[-1]).name}")

    def schema_version(self) -> int:
        self.events.append(f"schema:{self.schema}")
        return self.schema

    def validate_rollback_target(self, release: dict, schema: int) -> dict[str, int]:
        self.events.append(f"rollback:{release['sha']}:{schema}")
        return {
            "compatible_min": int(release["schema_compatible_min"]),
            "compatible_max": int(release["schema_compatible_max"]),
        }

    def validate_candidate(self, sha: str, slot: str) -> None:
        self.events.append(f"validate:{sha}:{slot}")

    def activate_workers(self, sha: str, slot: str, _images: dict) -> None:
        self.events.append(f"workers:{sha}:{slot}")

    def switch_traffic(self, slot: str) -> None:
        self.events.append(f"traffic:{slot}")

    def _json(self, url: str) -> dict:
        self.events.append(f"http:{url}")
        if url.endswith("/health/version"):
            return {"release_sha": "a" * 40}
        return {"ready": True}


class AutomaticMigrationControlPlaneTests(unittest.TestCase):
    def setUp(self):
        self.module = load_release_cli()
        self.sha = "a" * 40
        self.metadata = json.loads(
            (WEB_ROOT / "deployment/releases/release.json").read_text(
                encoding="utf-8"
            )
        )

    def fixture(self, root: Path, *, schema: int = 90):
        release_root = root / "release"
        release_dir = release_root / "web/deployment/releases"
        release_dir.mkdir(parents=True)
        (release_dir / "release.json").write_text(
            json.dumps(self.metadata), encoding="utf-8"
        )
        manifest_source = WEB_ROOT / "deployment/releases/migrations-091-092.json"
        manifest = json.loads(manifest_source.read_text(encoding="utf-8"))
        for entry in manifest["migrations"]:
            migration = release_root / entry["path"]
            migration.parent.mkdir(parents=True, exist_ok=True)
            filename = Path(entry["path"]).name
            source = next(
                (
                    candidate
                    for candidate in (
                        WEB_ROOT.parent / entry["path"],
                        WEB_ROOT / Path(entry["path"]).relative_to("web"),
                        Path("/database/migrations") / filename,
                        Path("/app/database/migrations") / filename,
                    )
                    if candidate.is_file()
                ),
                None,
            )
            if source is None:
                raise RuntimeError(f"migration fixture source unavailable: {filename}")
            migration.write_bytes(source.read_bytes())
            self.assertEqual(
                hashlib.sha256(migration.read_bytes()).hexdigest(),
                entry["sha256"],
            )
        (release_dir / "migrations-091-092.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        state_root = root / "state"
        state_root.mkdir()
        (state_root / "state.json").write_text(json.dumps({
            "active_slot": "green",
            "known_good_release": {
                "sha": self.sha,
                "slot": "green",
                "images": {"build_timestamp": "2026-08-30T00:00:00Z"},
            },
            "history": [{
                "release_sha": self.sha,
                "status": "known_good",
                "phase": "complete",
                "previous_known_good_release": {
                    "sha": "b" * 40,
                    "slot": "blue",
                    "schema_compatible_min": 81,
                    "schema_compatible_max": 90,
                },
            }],
        }), encoding="utf-8")
        events: list[str] = []
        operations = FakeOperations(release_root, events, schema=schema)
        compatibility = self.module.Compatibility.load(
            WEB_ROOT / "deployment/releases/release.json"
        )
        return state_root, operations, compatibility, events

    def run_production_wrapper(self, root: Path, *, fail_promotion: bool):
        fake_bin = root / "fake-bin"
        control_bin = root / "control/bin"
        repository = root / "repository"
        fake_bin.mkdir()
        control_bin.mkdir(parents=True)
        repository.mkdir()
        event_log = root / "events.log"

        git = fake_bin / "git"
        git.write_text(
            "#!/bin/sh\n"
            "printf 'git:%s\\n' \"$*\" >> \"$MADAR_TEST_EVENT_LOG\"\n"
            "case \"$*\" in\n"
            "  *'rev-parse origin/main'*) printf '%s\\n' \"$MADAR_TEST_SHA\";;\n"
            "esac\n",
            encoding="utf-8",
        )
        git.chmod(0o700)

        guard = control_bin / "madar-control-plane-guard"
        guard.write_text(
            "#!/bin/sh\n"
            "printf 'guard:%s\\n' \"$*\" >> \"$MADAR_TEST_EVENT_LOG\"\n",
            encoding="utf-8",
        )
        guard.chmod(0o700)

        release = control_bin / "madar-release-deploy"
        release.write_text(
            "#!/bin/sh\n"
            "printf 'release:%s\\n' \"$*\" >> \"$MADAR_TEST_EVENT_LOG\"\n"
            "if [ \"$MADAR_TEST_FAIL_PROMOTION\" = 1 ] "
            "&& [ \"${2:-}\" != --automatic-migrate ]; then exit 42; fi\n",
            encoding="utf-8",
        )
        release.chmod(0o700)

        environment = {
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
            "MADAR_PRODUCTION_REPO": str(repository),
            "MADAR_CONTROL_PLANE_ROOT": str(root / "control"),
            "MADAR_RELEASE_DEPLOY_BIN": str(release),
            "MADAR_TEST_EVENT_LOG": str(event_log),
            "MADAR_TEST_SHA": self.sha,
            "MADAR_TEST_FAIL_PROMOTION": "1" if fail_promotion else "0",
        }
        completed = subprocess.run(
            ["bash", str(PRODUCTION_DEPLOY)],
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        events = event_log.read_text(encoding="utf-8").splitlines()
        return completed, events

    def test_ordinary_release_invokes_migration_after_promotion_and_fast_forward(self):
        with tempfile.TemporaryDirectory() as directory:
            completed, events = self.run_production_wrapper(
                Path(directory), fail_promotion=False
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        promotion = events.index(f"release:{self.sha}")
        fast_forward = next(
            index for index, event in enumerate(events)
            if event.startswith("git:") and "merge --ff-only" in event
        )
        migration = events.index(
            f"release:{self.sha} --automatic-migrate"
        )
        self.assertLess(promotion, fast_forward)
        self.assertLess(fast_forward, migration)

    def test_bridge_promotion_failure_invokes_zero_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            completed, events = self.run_production_wrapper(
                Path(directory), fail_promotion=True
            )

        self.assertEqual(completed.returncode, 42)
        self.assertEqual(
            [event for event in events if event.startswith("release:")],
            [f"release:{self.sha}"],
        )
        self.assertFalse(any("merge --ff-only" in event for event in events))

    def test_backup_and_execution_begin_only_after_known_good_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, events = self.fixture(root)
            backup = root / "backups/madar-20260830T000000Z"
            backup.mkdir(parents=True)

            class FakeExecutor:
                def __init__(_self, **kwargs):
                    _self.kwargs = kwargs

                def verify_migrations(_self):
                    events.append("checksums")

                def run(_self):
                    events.append("execute")
                    operations.schema = 92
                    return {"status": "completed"}

            def stable(**_kwargs):
                events.append("stable")

            def create_backup(**_kwargs):
                events.append("backup")
                return backup

            def refresh(**_kwargs):
                events.append("refresh")
                return {"phase": "post_migration_workers_refreshed"}

            with (
                patch.object(self.module, "LockedMigrationExecutor", FakeExecutor),
                patch.object(self.module, "_validate_stable_known_good", stable),
                patch.object(self.module, "_create_verified_migration_backup", create_backup),
                patch.object(self.module, "_attest_migration_backup"),
                patch.object(self.module, "refresh_active_workers", refresh),
                patch.dict(os.environ, {"MADAR_BACKUP_DIR": str(root / "backups")}),
            ):
                result = self.module.automatic_migrate_known_good(
                    sha=self.sha,
                    state_root=state_root,
                    compatibility=compatibility,
                    operations=operations,
                )

        self.assertEqual(result["status"], "completed")
        self.assertLess(events.index("stable"), events.index("backup"))
        self.assertLess(events.index("checksums"), events.index("backup"))
        self.assertLess(
            next(index for index, event in enumerate(events) if event.startswith("rollback:")),
            events.index("backup"),
        )
        self.assertLess(events.index("backup"), events.index("execute"))
        self.assertLess(events.index("execute"), events.index("refresh"))

    def test_successful_90_to_91_to_92_records_target_only_after_worker_and_route_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, events = self.fixture(root)
            backup = root / "backups/madar-20260830T000000Z"
            backup.mkdir(parents=True)

            class FakeExecutor:
                def __init__(_self, **_kwargs):
                    pass

                def verify_migrations(_self):
                    events.append("checksums")

                def run(_self):
                    events.append("execute")
                    self.assertEqual(operations.schema, 90)
                    events.append("migration:90->91")
                    operations.schema = 91
                    events.append("migration:91->92")
                    operations.schema = 92
                    return {"status": "completed"}

            with (
                patch.object(self.module, "LockedMigrationExecutor", FakeExecutor),
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(
                    self.module,
                    "_create_verified_migration_backup",
                    return_value=backup,
                ),
                patch.object(self.module, "_attest_migration_backup"),
                patch.dict(os.environ, {"MADAR_BACKUP_DIR": str(root / "backups")}),
            ):
                result = self.module.automatic_migrate_known_good(
                    sha=self.sha,
                    state_root=state_root,
                    compatibility=compatibility,
                    operations=operations,
                )

            state = json.loads((state_root / "state.json").read_text())
            automation = json.loads(
                (
                    state_root
                    / "migrations"
                    / self.sha
                    / "automation.json"
                ).read_text()
            )

        self.assertEqual(result["observed_schema"], 92)
        self.assertEqual(automation["status"], "completed")
        self.assertEqual(
            automation["phase"], "post_migration_validation_complete"
        )
        self.assertEqual(state["known_good_release"]["schema"], 92)
        self.assertEqual(
            state["history"][-1]["phase"],
            "post_migration_workers_refreshed",
        )
        self.assertIn(f"workers:{self.sha}:green", events)
        self.assertLess(
            events.index("migration:90->91"),
            events.index("migration:91->92"),
        )
        first_validation = events.index(f"validate:{self.sha}:green")
        worker_activation = events.index(f"workers:{self.sha}:green")
        second_validation = events.index(
            f"validate:{self.sha}:green", first_validation + 1
        )
        self.assertLess(first_validation, worker_activation)
        self.assertLess(worker_activation, second_validation)
        self.assertIn(
            "http:http://127.0.0.1:8001/health/version", events
        )
        self.assertIn(
            "http:http://127.0.0.1:8001/health/ready", events
        )

    def test_stable_route_failure_prevents_final_migration_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, _events = self.fixture(root)
            backup = root / "backups/madar-20260830T000000Z"
            backup.mkdir(parents=True)

            class FakeExecutor:
                def __init__(_self, **_kwargs):
                    pass

                def verify_migrations(_self):
                    pass

                def run(_self):
                    operations.schema = 92
                    return {"status": "completed"}

            with (
                patch.object(self.module, "LockedMigrationExecutor", FakeExecutor),
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(
                    self.module,
                    "_create_verified_migration_backup",
                    return_value=backup,
                ),
                patch.object(self.module, "_attest_migration_backup"),
                patch.object(
                    operations,
                    "_json",
                    side_effect=[
                        {"release_sha": self.sha},
                        {"ready": False},
                    ],
                ),
                patch.dict(os.environ, {"MADAR_BACKUP_DIR": str(root / "backups")}),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "stable_proxy_post_migration_validation_failed"
                ):
                    self.module.automatic_migrate_known_good(
                        sha=self.sha,
                        state_root=state_root,
                        compatibility=compatibility,
                        operations=operations,
                    )

            state = json.loads((state_root / "state.json").read_text())
            automation = json.loads(
                (
                    state_root
                    / "migrations"
                    / self.sha
                    / "automation.json"
                ).read_text()
            )

        self.assertNotIn("schema", state["known_good_release"])
        self.assertEqual(
            automation["status"], "failed_forward_repair_required"
        )
        self.assertEqual(
            automation["phase"], "post_migration_validation_failed"
        )

    def test_unapproved_migration_policy_is_a_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, _events = self.fixture(root)
            metadata = {**self.metadata, "migration_policy": "manual-only"}
            candidate_release = (
                operations.release_root / "web/deployment/releases/release.json"
            )
            candidate_release.write_text(json.dumps(metadata), encoding="utf-8")
            installed = root / "installed/deployment/releases"
            installed.mkdir(parents=True)
            (installed / "release.json").write_text(
                json.dumps(metadata), encoding="utf-8"
            )
            with (
                patch.object(self.module, "WEB_ROOT", root / "installed"),
                patch.object(
                    self.module,
                    "_create_verified_migration_backup",
                    side_effect=AssertionError("backup must not run"),
                ),
            ):
                result = self.module.automatic_migrate_known_good(
                    sha=self.sha,
                    state_root=state_root,
                    compatibility=compatibility,
                    operations=operations,
                )

        self.assertEqual(result["status"], "not_requested")

    def test_unsupported_release_class_is_rejected_before_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, _compatibility, _events = self.fixture(root)
            metadata = json.loads(json.dumps(self.metadata))
            metadata["schema"]["migration_class"] = "coordinated"
            candidate_release = (
                operations.release_root / "web/deployment/releases/release.json"
            )
            candidate_release.write_text(json.dumps(metadata), encoding="utf-8")
            installed = root / "installed/deployment/releases"
            installed.mkdir(parents=True)
            installed_release = installed / "release.json"
            installed_release.write_text(json.dumps(metadata), encoding="utf-8")
            compatibility = self.module.Compatibility.load(installed_release)
            with (
                patch.object(self.module, "WEB_ROOT", root / "installed"),
                patch.object(
                    self.module,
                    "_create_verified_migration_backup",
                    side_effect=AssertionError("backup must not run"),
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "automatic_migration_release_class_rejected"
                ):
                    self.module.automatic_migrate_known_good(
                        sha=self.sha,
                        state_root=state_root,
                        compatibility=compatibility,
                        operations=operations,
                    )

    def test_refuses_non_known_good_sha_before_backup_or_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, _events = self.fixture(root)
            state = json.loads((state_root / "state.json").read_text())
            state["known_good_release"]["sha"] = "b" * 40
            (state_root / "state.json").write_text(json.dumps(state))
            with patch.object(
                self.module,
                "_create_verified_migration_backup",
                side_effect=AssertionError("backup must not run"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "automatic_migration_bridge_not_known_good"
                ):
                    self.module.automatic_migrate_known_good(
                        sha=self.sha,
                        state_root=state_root,
                        compatibility=compatibility,
                        operations=operations,
                    )

    def test_refuses_manifest_drift_before_backup_or_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, _events = self.fixture(root)
            manifest_path = (
                operations.release_root
                / "web/deployment/releases/migrations-091-092.json"
            )
            manifest = json.loads(manifest_path.read_text())
            manifest["migrations"][0]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest))
            with patch.object(
                self.module,
                "_create_verified_migration_backup",
                side_effect=AssertionError("backup must not run"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "automatic_migration_manifest_contract_mismatch",
                ):
                    self.module.automatic_migrate_known_good(
                        sha=self.sha,
                        state_root=state_root,
                        compatibility=compatibility,
                        operations=operations,
                    )

    def test_partial_committed_transition_reuses_backup_without_old_release_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, events = self.fixture(
                root, schema=91
            )
            backup_root = root / "backups"
            backup = backup_root / "madar-20260830T000000Z"
            backup.mkdir(parents=True)
            migration_state = state_root / "migrations" / self.sha
            migration_state.mkdir(parents=True)
            (migration_state / "execution.json").write_text(json.dumps({
                "release_sha": self.sha,
                "status": "failed",
                "backup": {"path": str(backup), "verified": True},
            }))

            class FakeExecutor:
                def __init__(_self, **kwargs):
                    _self.backup_dir = kwargs["backup_dir"]

                def verify_migrations(_self):
                    pass

                def run(_self):
                    self.assertEqual(_self.backup_dir, backup)
                    operations.schema = 92
                    return {"status": "completed"}

            with (
                patch.object(self.module, "LockedMigrationExecutor", FakeExecutor),
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(
                    self.module,
                    "_create_verified_migration_backup",
                    side_effect=AssertionError("must reuse original backup"),
                ),
                patch.object(
                    self.module,
                    "refresh_active_workers",
                    return_value={"phase": "post_migration_workers_refreshed"},
                ),
                patch.object(self.module, "_attest_migration_backup"),
                patch.dict(os.environ, {"MADAR_BACKUP_DIR": str(backup_root)}),
            ):
                result = self.module.automatic_migrate_known_good(
                    sha=self.sha,
                    state_root=state_root,
                    compatibility=compatibility,
                    operations=operations,
                )

        self.assertEqual(result["observed_schema"], 92)
        self.assertFalse(any(event.startswith("rollback:") for event in events))
        self.assertFalse(any(event.startswith("traffic:") for event in events))

    def test_backup_failure_is_durable_and_next_attempt_is_suppressed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, _events = self.fixture(root)

            class FakeExecutor:
                def __init__(_self, **_kwargs):
                    pass

                def verify_migrations(_self):
                    pass

                def run(_self):
                    raise AssertionError("SQL must not run after backup failure")

            with (
                patch.object(self.module, "LockedMigrationExecutor", FakeExecutor),
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(
                    self.module,
                    "_create_verified_migration_backup",
                    side_effect=RuntimeError("backup_failed"),
                ) as backup,
                patch.object(self.module, "_attest_migration_backup"),
                patch.dict(os.environ, {"MADAR_BACKUP_DIR": str(root / "backups")}),
            ):
                with self.assertRaisesRegex(RuntimeError, "backup_failed"):
                    self.module.automatic_migrate_known_good(
                        sha=self.sha,
                        state_root=state_root,
                        compatibility=compatibility,
                        operations=operations,
                    )
                result = self.module.automatic_migrate_known_good(
                    sha=self.sha,
                    state_root=state_root,
                    compatibility=compatibility,
                    operations=operations,
                )

            persisted = json.loads(
                (
                    state_root
                    / "migrations"
                    / self.sha
                    / "automation.json"
                ).read_text()
            )

        self.assertEqual(
            persisted["status"], "failed_forward_repair_required"
        )
        self.assertIn("retry_after", persisted)
        self.assertEqual(result["phase"], "retry_suppressed")
        self.assertEqual(backup.call_count, 1)

    def test_initial_transition_requires_retained_target_attestation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, _events = self.fixture(root)
            state = json.loads((state_root / "state.json").read_text())
            state["history"] = []
            (state_root / "state.json").write_text(json.dumps(state))
            with (
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(
                    self.module,
                    "_create_verified_migration_backup",
                    side_effect=AssertionError("backup must not run"),
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "automatic_migration_retained_rollback_attestation_missing",
                ):
                    self.module.automatic_migrate_known_good(
                        sha=self.sha,
                        state_root=state_root,
                        compatibility=compatibility,
                        operations=operations,
                    )

    def test_backup_manifest_is_bound_to_release_and_source_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "madar-20260830T000000Z"
            backup.mkdir()
            manifest = {
                "backup_id": backup.name,
                "format_version": 3,
                "status": "complete",
                "release": {"git_sha": self.sha},
                "database": {"schema_version": "90"},
            }
            (backup / "manifest.json").write_text(json.dumps(manifest))
            self.module._attest_migration_backup(
                backup, release_sha=self.sha, source_schema=90
            )
            manifest["database"]["schema_version"] = "91"
            (backup / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(
                RuntimeError, "automatic_migration_backup_identity_mismatch"
            ):
                self.module._attest_migration_backup(
                    backup, release_sha=self.sha, source_schema=90
                )


if __name__ == "__main__":
    unittest.main()

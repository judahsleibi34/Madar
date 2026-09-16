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
    def __init__(self, release_root: Path, events: list[str], schema: int = 96):
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

    def validate_candidate_core(self, sha: str, slot: str) -> None:
        self.events.append(f"validate-core:{sha}:{slot}")

    def start_candidate(self, sha: str, slot: str, _images: dict) -> None:
        self.events.append(f"fallback:{sha}:{slot}")

    def preflight(self, sha: str, slot: str, _images: dict, schema: int) -> None:
        self.events.append(f"preflight:{sha}:{slot}:{schema}")

    def validate_active_refresh_prerequisites(
        self, sha: str, slot: str, _images: dict,
    ) -> None:
        self.events.append(f"pre-refresh:{sha}:{slot}")

    def refresh_active_runtime_services(
        self, sha: str, slot: str, _images: dict,
    ) -> None:
        self.events.append(f"workers:{sha}:{slot}")

    def validate_stable_candidate(self, sha: str) -> None:
        identity = self._json("http://127.0.0.1:8001/health/version")
        readiness = self._json("http://127.0.0.1:8001/health/ready")
        if identity.get("release_sha") != sha or not readiness.get("ready"):
            raise RuntimeError("stable_proxy_active_refresh_validation_failed")

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

    def test_current_manifest_covers_deployed_schema_96_through_target_99(self):
        manifest = json.loads(
            (
                WEB_ROOT
                / "deployment/releases"
                / self.metadata["migration_manifest"]
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            [entry["number"] for entry in manifest["migrations"]],
            [97, 98, 99],
        )
        self.assertEqual(manifest["migrations"][0]["from_schema"], 96)
        self.assertEqual(manifest["migrations"][-1]["to_schema"], 99)
        self.assertEqual(
            self.metadata["schema"]["rollback_compatible_max"], 98
        )

    def fixture(self, root: Path, *, schema: int = 96):
        release_root = root / "release"
        release_dir = release_root / "web/deployment/releases"
        release_dir.mkdir(parents=True)
        (release_dir / "release.json").write_text(
            json.dumps(self.metadata), encoding="utf-8"
        )
        manifest_name = self.metadata["migration_manifest"]
        manifest_source = WEB_ROOT / "deployment/releases" / manifest_name
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
        (release_dir / manifest_name).write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        state_root = root / "state"
        state_root.mkdir()
        (state_root / "state.json").write_text(json.dumps({
            "active_slot": "green",
            "known_good_release": {
                "sha": self.sha,
                "slot": "green",
                "schema": schema,
                "images": {"build_timestamp": "2026-08-30T00:00:00Z"},
            },
            "history": [{
                "release_sha": self.sha,
                "status": "known_good",
                "phase": "complete",
                "schema": {"observed": schema},
                "previous_known_good_release": {
                    "sha": "b" * 40,
                    "slot": "blue",
                    "schema_compatible_min": 81,
                    "schema_compatible_max": 98,
                },
            }],
        }), encoding="utf-8")
        events: list[str] = []
        operations = FakeOperations(release_root, events, schema=schema)
        compatibility = self.module.Compatibility.load(
            WEB_ROOT / "deployment/releases/release.json"
        )
        operations.compatibility = compatibility
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

    def test_normal_production_wrapper_rejects_recovery_mode(self):
        completed = subprocess.run(
            ["bash", str(PRODUCTION_DEPLOY), "--recover-current-schema"],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("coordinator-only", completed.stderr)

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
                    operations.schema = compatibility.target_schema
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
                patch.object(
                    self.module, "_attest_migration_backup"
                ) as attest_backup,
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
        attest_backup.assert_called_once_with(
            backup, release_sha=self.sha, source_schema=96
        )

    def test_recovered_fallback_is_authoritative_for_next_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, events = self.fixture(root)
            state_path = state_root / "state.json"
            state = json.loads(state_path.read_text())
            state["compatible_fallback_release"] = {
                "sha": self.sha, "slot": "blue", "schema": 96,
                "schema_compatible_min": 96, "schema_compatible_max": 96,
            }
            state_path.write_text(json.dumps(state), encoding="utf-8")
            backup = root / "backups/madar-20260830T000000Z"
            backup.mkdir(parents=True)

            class FakeExecutor:
                def __init__(_self, **kwargs): pass
                def verify_migrations(_self): pass
                def run(_self):
                    operations.schema = compatibility.target_schema
                    return {"status": "completed"}

            with (
                patch.object(self.module, "LockedMigrationExecutor", FakeExecutor),
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(self.module, "_create_verified_migration_backup", return_value=backup),
                patch.object(self.module, "_attest_migration_backup"),
                patch.dict(os.environ, {"MADAR_BACKUP_DIR": str(root / "backups")}),
            ):
                self.module.automatic_migrate_known_good(
                    sha=self.sha, state_root=state_root,
                    compatibility=compatibility, operations=operations,
                )
        self.assertIn(f"rollback:{self.sha}:96", events)
        self.assertNotIn(f"rollback:{'b' * 40}:96", events)

    def test_failed_migration_retry_reuses_replacement_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, events = self.fixture(root)
            backup = root / "backups/madar-20260830T000000Z"
            backup.mkdir(parents=True)

            class FailingExecutor:
                def __init__(_self, **_kwargs): pass
                def verify_migrations(_self): pass
                def run(_self): raise RuntimeError("synthetic_precommit_failure")

            with (
                patch.object(self.module, "LockedMigrationExecutor", FailingExecutor),
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(self.module, "_create_verified_migration_backup", return_value=backup),
                patch.object(self.module, "_attest_migration_backup"),
                patch.dict(os.environ, {"MADAR_BACKUP_DIR": str(root / "backups")}),
            ):
                with self.assertRaisesRegex(RuntimeError, "synthetic_precommit_failure"):
                    self.module.automatic_migrate_known_good(
                        sha=self.sha, state_root=state_root,
                        compatibility=compatibility, operations=operations,
                    )
                first_end = len(events)
                result = self.module.automatic_migrate_known_good(
                    sha=self.sha, state_root=state_root,
                    compatibility=compatibility, operations=operations,
                )

        self.assertEqual(result["phase"], "retry_suppressed")
        retry_events = events[first_end:]
        self.assertIn(f"rollback:{self.sha}:96", retry_events)
        self.assertNotIn(f"rollback:{'b' * 40}:96", retry_events)

    def stale_production_fixture(self, root, variant="valid", stale_variant="same_slot"):
        self.sha = "f8e9c7e3c20c5e74e5a0b130e19ec2051512cc7a"
        retained_sha = "f7dd5ea134f567018d2c0b46c1b752c57d692822"
        state_root, operations, compatibility, events = self.fixture(root)
        state_file = state_root / "state.json"
        state = json.loads(state_file.read_text())
        state["active_slot"] = "blue"
        state["known_good_release"]["slot"] = "blue"
        retained = {
            "sha": retained_sha, "slot": "green", "schema": 96,
            "schema_compatible_min": 96, "schema_compatible_max": 96,
        }
        state["history"][-1]["previous_known_good_release"] = retained
        state["compatible_fallback_release"] = {**retained, "slot": "blue"}
        if stale_variant == "wrong_sha":
            state["compatible_fallback_release"].update(slot="green", sha="c" * 40)
        if variant == "missing":
            state["history"][-1].pop("previous_known_good_release")
        elif variant == "wrong_sha":
            retained["sha"] = "d" * 40
        elif variant == "invalid_sha":
            retained["sha"] = "f7dd"
        elif variant == "same_slot":
            retained["slot"] = "blue"
        elif variant == "unknown_slot":
            retained["slot"] = "red"
        elif variant == "incompatible":
            retained["schema_compatible_max"] = 95
        elif variant == "malformed_range":
            retained["schema_compatible_max"] = None
        state_file.write_text(json.dumps(state))

        def live_identity(url):
            events.append(f"live:{url}")
            self.assertEqual(url, "http://127.0.0.1:8201/health/version")
            if variant in {"dead", "missing_runtime"}:
                raise OSError("retained_runtime_unavailable")
            return {
                "release_sha": retained_sha,
                "schema_compatible_min": 96,
                "schema_compatible_max": 95 if variant == "live_incompatible" else 96,
            }

        operations._json = live_identity
        # Exercise the real direct-slot SHA and live compatibility attestation,
        # including connection failure for a stopped/absent retained process.
        operations.validate_rollback_target = lambda release, schema: (
            self.module.DockerGitOperations.validate_rollback_target(operations, release, schema)
        )
        return state_root, operations, compatibility, events

    def test_stale_recovery_fallback_uses_only_exact_live_acceptance_target(self):
        for stale_variant in ("same_slot", "wrong_sha"):
            with self.subTest(stale_variant=stale_variant), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                state_root, operations, compatibility, events = self.stale_production_fixture(
                    root, stale_variant=stale_variant,
                )
                backup = root / "backups/madar-20260916T000000Z"

                def create_backup(**_kwargs):
                    self.assertTrue(any(event.startswith("live:") for event in events))
                    backup.mkdir(parents=True)
                    (backup / "manifest.json").write_text(json.dumps({
                        "format_version": 3, "status": "complete", "backup_id": backup.name,
                        "release": {"git_sha": self.sha}, "database": {"schema_version": 96},
                    }))
                    return backup

                class Executor:
                    def __init__(_self, **_kwargs): pass
                    def verify_migrations(_self): pass
                    def run(_self):
                        operations.schema = 99
                        return {"status": "completed"}

                with (
                    patch.object(self.module, "_validate_stable_known_good"),
                    patch.object(self.module, "_create_verified_migration_backup", side_effect=create_backup),
                    patch.object(self.module, "LockedMigrationExecutor", Executor),
                    patch.object(operations, "validate_stable_candidate"),
                ):
                    result = self.module.automatic_migrate_known_good(
                        sha=self.sha, state_root=state_root,
                        compatibility=compatibility, operations=operations,
                    )
                state = json.loads((state_root / "state.json").read_text())
                self.assertEqual(result["observed_schema"], 99)
                self.assertEqual(state["known_good_release"]["schema"], 99)
                self.assertEqual(state["compatible_fallback_release"]["sha"], self.sha)
                self.assertEqual(state["compatible_fallback_release"]["slot"], "green")
                self.assertEqual(state["compatible_fallback_release"]["schema"], 99)
                self.assertFalse(any(event.startswith("traffic:") for event in events))

    def test_stale_recovery_fallback_invalid_acceptance_targets_fail_pre_mutation(self):
        for variant in (
            "missing", "wrong_sha", "invalid_sha", "same_slot", "unknown_slot",
            "incompatible", "malformed_range", "live_incompatible", "dead", "missing_runtime",
        ):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory:
                state_root, operations, compatibility, _events = self.stale_production_fixture(
                    Path(directory), variant,
                )
                state_before = (state_root / "state.json").read_bytes()
                with (
                    patch.object(self.module, "_validate_stable_known_good"),
                    patch.object(self.module, "_create_verified_migration_backup") as backup,
                    patch.object(self.module, "_attest_migration_backup") as attest,
                    patch.object(self.module, "_establish_compatible_migration_fallback") as fallback,
                    patch("psycopg.connect") as connect,
                    patch.object(self.module.LockedMigrationExecutor, "run") as execute,
                ):
                    with self.assertRaisesRegex(RuntimeError, "retained_rollback_attestation_invalid"):
                        self.module.automatic_migrate_known_good(
                            sha=self.sha, state_root=state_root,
                            compatibility=compatibility, operations=operations,
                        )
                    for mutation in (backup, attest, fallback, connect, execute):
                        mutation.assert_not_called()
                self.assertFalse((state_root / "migrations").exists())
                self.assertEqual((state_root / "state.json").read_bytes(), state_before)

    def test_unexpected_rollback_validator_failure_propagates_pre_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root, operations, compatibility, _events = self.stale_production_fixture(
                Path(directory), stale_variant="wrong_sha",
            )
            state_before = (state_root / "state.json").read_bytes()
            validation_calls = []

            def unexpected_validator(release, schema):
                validation_calls.append(release["sha"])
                if release["sha"] == "c" * 40:
                    raise RuntimeError("unexpected_validator_internal_failure")
                return self.module.DockerGitOperations.validate_rollback_target(
                    operations, release, schema,
                )

            operations.validate_rollback_target = unexpected_validator
            with (
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(self.module, "_create_verified_migration_backup") as backup,
                patch.object(self.module, "_attest_migration_backup") as attest,
                patch.object(self.module, "_establish_compatible_migration_fallback") as fallback,
                patch("psycopg.connect") as connect,
                patch.object(self.module.LockedMigrationExecutor, "run") as execute,
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "unexpected_validator_internal_failure",
                ):
                    self.module.automatic_migrate_known_good(
                        sha=self.sha, state_root=state_root,
                        compatibility=compatibility, operations=operations,
                    )
                for mutation in (backup, attest, fallback, connect, execute):
                    mutation.assert_not_called()

            self.assertEqual(validation_calls, ["c" * 40])
            self.assertFalse((state_root / "migrations").exists())
            self.assertEqual((state_root / "state.json").read_bytes(), state_before)

    def test_successful_96_to_99_records_target_only_after_worker_and_route_validation(self):
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
                    self.assertEqual(operations.schema, 96)
                    events.append("migration:96->99")
                    operations.schema = 99
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

        self.assertEqual(result["observed_schema"], 99)
        self.assertEqual(automation["status"], "completed")
        self.assertEqual(
            automation["phase"], "post_migration_validation_complete"
        )
        self.assertEqual(state["known_good_release"]["schema"], 99)
        self.assertEqual(
            state["history"][-1]["phase"],
            "post_migration_workers_refreshed",
        )
        self.assertIn(f"workers:{self.sha}:green", events)
        self.assertIn("migration:96->99", events)
        pre_refresh_validation = events.index(f"pre-refresh:{self.sha}:green")
        worker_activation = events.index(f"workers:{self.sha}:green")
        full_validation = events.index(f"validate:{self.sha}:green")
        fallback_core_validations = [
            index
            for index, event in enumerate(events)
            if event == f"validate-core:{self.sha}:blue"
        ]

        self.assertLess(pre_refresh_validation, worker_activation)
        self.assertLess(worker_activation, full_validation)

        # The passive fallback intentionally has singleton consumers off.
        # It must receive core validation, never full worker-aware readiness.
        self.assertGreaterEqual(len(fallback_core_validations), 2)
        self.assertLess(
            full_validation,
            fallback_core_validations[-1],
        )
        self.assertNotIn(
            f"validate:{self.sha}:blue",
            events,
        )
        self.assertFalse(
            state["compatible_fallback_release"]["workers_active"]
        )

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
                    operations.schema = compatibility.target_schema
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
                    RuntimeError, "stable_proxy_active_refresh_validation_failed"
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

        self.assertEqual(state["known_good_release"]["schema"], 96)
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

    def test_refuses_wrong_active_slot_before_backup_or_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, _events = self.fixture(root)
            state = json.loads((state_root / "state.json").read_text())
            state["active_slot"] = "blue"
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
                / f"web/deployment/releases/{self.metadata['migration_manifest']}"
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

    def test_already_at_target_still_enforces_migration_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, _events = self.fixture(
                root, schema=99
            )
            candidate_manifest = (
                operations.release_root
                / f"web/deployment/releases/{self.metadata['migration_manifest']}"
            )
            manifest = json.loads(candidate_manifest.read_text())
            manifest["migrations"][0]["sha256"] = "0" * 64
            candidate_manifest.write_text(json.dumps(manifest))
            installed = root / "installed/deployment/releases"
            installed.mkdir(parents=True)
            (installed / "release.json").write_text(json.dumps(self.metadata))
            (installed / self.metadata["migration_manifest"]).write_text(
                json.dumps(manifest)
            )
            with (
                patch.object(self.module, "WEB_ROOT", root / "installed"),
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(
                    self.module,
                    "_create_verified_migration_backup",
                    side_effect=AssertionError("backup must not run"),
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "migration_checksum_mismatch:97"
                ):
                    self.module.automatic_migrate_known_good(
                        sha=self.sha,
                        state_root=state_root,
                        compatibility=compatibility,
                        operations=operations,
                    )

    def test_committed_transition_reuses_backup_without_old_release_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, events = self.fixture(
                root, schema=99
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
                    operations.schema = compatibility.target_schema
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

        self.assertEqual(result["observed_schema"], 99)
        self.assertFalse(any(event.startswith("rollback:") for event in events))
        self.assertFalse(any(event.startswith("traffic:") for event in events))

    def test_prior_release_migrates_then_later_release_noops_idempotently(self):
        previous_sha = self.sha
        current_sha = "c" * 40
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, events = self.fixture(root)
            backup_root = root / "backups"
            old_backup = backup_root / "madar-20260831T195925Z"
            old_backup.mkdir(parents=True)
            old_manifest = old_backup / "manifest.json"
            old_manifest.write_text(json.dumps({
                "format_version": 3,
                "status": "complete",
                "backup_id": old_backup.name,
                "release": {"git_sha": previous_sha},
                "database": {"schema_version": "96"},
            }))

            class TransitionExecutor:
                def __init__(_self, **kwargs):
                    _self.state_file = kwargs["state_file"]
                    _self.backup_dir = kwargs["backup_dir"]

                def verify_migrations(_self):
                    events.append("previous-checksums")

                def run(_self):
                    events.append("previous-sql:96->99")
                    operations.schema = 99
                    _self.state_file.parent.mkdir(parents=True, exist_ok=True)
                    _self.state_file.write_text(json.dumps({
                        "release_sha": previous_sha,
                        "status": "completed",
                        "backup": {
                            "path": str(_self.backup_dir),
                            "verified": True,
                        },
                        "observed_schema": 99,
                    }))
                    return {"status": "completed"}

            with (
                patch.object(
                    self.module, "LockedMigrationExecutor", TransitionExecutor,
                ),
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(
                    self.module,
                    "_create_verified_migration_backup",
                    return_value=old_backup,
                ),
                patch.object(
                    self.module,
                    "refresh_active_workers",
                    return_value={"phase": "post_migration_workers_refreshed"},
                ),
                patch.dict(os.environ, {"MADAR_BACKUP_DIR": str(backup_root)}),
            ):
                prior_result = self.module.automatic_migrate_known_good(
                    sha=previous_sha,
                    state_root=state_root,
                    compatibility=compatibility,
                    operations=operations,
                )

            state = json.loads((state_root / "state.json").read_text())
            state["known_good_release"] = {
                **state["known_good_release"],
                "sha": current_sha,
                "slot": "blue",
                "schema": 99,
            }
            state["active_slot"] = "blue"
            state["history"].extend([
                {
                    "release_sha": previous_sha,
                    "status": "known_good",
                    "phase": "post_migration_workers_refreshed",
                    "schema": {"observed": 99},
                },
                {
                    "release_sha": current_sha,
                    "status": "known_good",
                    "phase": "complete",
                    "schema": {"observed": 99, "target": 99},
                    "previous_known_good_release": {
                        "sha": previous_sha,
                        "slot": "green",
                        "schema_compatible_min": 81,
                        "schema_compatible_max": 99,
                    },
                },
            ])
            (state_root / "state.json").write_text(json.dumps(state))
            old_execution = (
                state_root / "migrations" / previous_sha / "execution.json"
            )
            old_manifest_before = old_manifest.read_bytes()
            old_execution_before = old_execution.read_bytes()

            class NoSqlExecutor:
                verify_count = 0

                def __init__(_self, **_kwargs):
                    pass

                def verify_migrations(_self):
                    NoSqlExecutor.verify_count += 1
                    events.append("current-checksums")

                def run(_self):
                    raise AssertionError("SQL must not run at an accepted target")

            with (
                patch.object(self.module, "LockedMigrationExecutor", NoSqlExecutor),
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(
                    self.module,
                    "_create_verified_migration_backup",
                    side_effect=AssertionError("backup must not be created"),
                ),
                patch.object(
                    self.module,
                    "_attest_migration_backup",
                    side_effect=AssertionError("backup must not be rebound"),
                ),
                patch.object(
                    self.module,
                    "refresh_active_workers",
                    side_effect=AssertionError("no-op must not recreate workers"),
                ),
            ):
                first = self.module.automatic_migrate_known_good(
                    sha=current_sha,
                    state_root=state_root,
                    compatibility=compatibility,
                    operations=operations,
                )
                second = self.module.automatic_migrate_known_good(
                    sha=current_sha,
                    state_root=state_root,
                    compatibility=compatibility,
                    operations=operations,
                )

            automation = json.loads((
                state_root / "migrations" / current_sha / "automation.json"
            ).read_text())
            current_execution_exists = (
                state_root / "migrations" / current_sha / "execution.json"
            ).exists()
            old_manifest_after = old_manifest.read_bytes()
            old_execution_after = old_execution.read_bytes()

        self.assertEqual(prior_result["execution_status"], "completed")
        self.assertIn("previous-sql:96->99", events)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["phase"], "already_at_target")
        self.assertEqual(first["execution_status"], "already_at_target")
        self.assertIsNone(first["backup"])
        self.assertEqual(automation, first)
        self.assertFalse(current_execution_exists)
        self.assertEqual(old_manifest_after, old_manifest_before)
        self.assertEqual(old_execution_after, old_execution_before)
        self.assertEqual(NoSqlExecutor.verify_count, 2)
        self.assertFalse(any(event.startswith("traffic:") for event in events))

    def test_current_release_partial_state_without_backup_still_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, _events = self.fixture(
                root, schema=99
            )
            state = json.loads((state_root / "state.json").read_text())
            state["known_good_release"]["schema"] = 96
            state["history"][-1]["schema"] = {"observed": 96}
            (state_root / "state.json").write_text(json.dumps(state))
            migration_state = state_root / "migrations" / self.sha
            migration_state.mkdir(parents=True)
            (migration_state / "automation.json").write_text(json.dumps({
                "release_sha": self.sha,
                "status": "running",
                "phase": "migration_execution",
            }))
            (migration_state / "execution.json").write_text(json.dumps({
                "release_sha": self.sha,
                "status": "running",
                "phase": "migration_99",
                "migrations": [{"number": 99, "status": "applying"}],
            }))
            with (
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(
                    self.module,
                    "_create_verified_migration_backup",
                    side_effect=AssertionError("new backup must not be created"),
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "automatic_migration_resume_backup_attestation_missing",
                ):
                    self.module.automatic_migrate_known_good(
                        sha=self.sha,
                        state_root=state_root,
                        compatibility=compatibility,
                        operations=operations,
                    )

    def test_source_schema_acceptance_cannot_be_reclassified_without_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, _events = self.fixture(
                root, schema=99
            )
            state = json.loads((state_root / "state.json").read_text())
            state["known_good_release"]["schema"] = 96
            state["history"][-1]["schema"] = {"observed": 96}
            (state_root / "state.json").write_text(json.dumps(state))
            with (
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(
                    self.module,
                    "_create_verified_migration_backup",
                    side_effect=AssertionError("backup must not be fabricated"),
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "automatic_migration_resume_backup_attestation_missing",
                ):
                    self.module.automatic_migrate_known_good(
                        sha=self.sha,
                        state_root=state_root,
                        compatibility=compatibility,
                        operations=operations,
                    )

    def test_current_release_substituted_resume_backup_still_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, _events = self.fixture(
                root, schema=99
            )
            state = json.loads((state_root / "state.json").read_text())
            state["known_good_release"]["schema"] = 96
            state["history"][-1]["schema"] = {"observed": 96}
            (state_root / "state.json").write_text(json.dumps(state))
            backup_root = root / "backups"
            backup = backup_root / "madar-20260831T195925Z"
            backup.mkdir(parents=True)
            (backup / "manifest.json").write_text(json.dumps({
                "format_version": 3,
                "status": "complete",
                "backup_id": backup.name,
                "release": {"git_sha": "b" * 40},
                "database": {"schema_version": "96"},
            }))
            migration_state = state_root / "migrations" / self.sha
            migration_state.mkdir(parents=True)
            (migration_state / "execution.json").write_text(json.dumps({
                "release_sha": self.sha,
                "status": "failed",
                "backup": {"path": str(backup), "verified": True},
            }))

            class NoSqlExecutor:
                def __init__(_self, **_kwargs):
                    pass

                def verify_migrations(_self):
                    pass

                def run(_self):
                    raise AssertionError("SQL must not run with substituted backup")

            with (
                patch.object(self.module, "LockedMigrationExecutor", NoSqlExecutor),
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(
                    self.module,
                    "_create_verified_migration_backup",
                    side_effect=AssertionError("must not replace resume backup"),
                ),
                patch.dict(os.environ, {"MADAR_BACKUP_DIR": str(backup_root)}),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "automatic_migration_backup_identity_mismatch"
                ):
                    self.module.automatic_migrate_known_good(
                        sha=self.sha,
                        state_root=state_root,
                        compatibility=compatibility,
                        operations=operations,
                    )

    def test_schema_above_target_fails_before_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root, operations, compatibility, _events = self.fixture(
                root, schema=100
            )
            with (
                patch.object(self.module, "_validate_stable_known_good"),
                patch.object(
                    self.module,
                    "_create_verified_migration_backup",
                    side_effect=AssertionError("backup must not run"),
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "automatic_migration_live_schema_incompatible"
                ):
                    self.module.automatic_migrate_known_good(
                        sha=self.sha,
                        state_root=state_root,
                        compatibility=compatibility,
                        operations=operations,
                    )

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
                "database": {"schema_version": "94"},
            }
            (backup / "manifest.json").write_text(json.dumps(manifest))
            self.module._attest_migration_backup(
                backup, release_sha=self.sha, source_schema=94
            )
            manifest["database"]["schema_version"] = "97"
            (backup / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(
                RuntimeError, "automatic_migration_backup_identity_mismatch"
            ):
                self.module._attest_migration_backup(
                    backup, release_sha=self.sha, source_schema=94
                )


if __name__ == "__main__":
    unittest.main()

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


WEB_ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
SCRIPT = WEB_ROOT / "deployment" / "bin" / "madar-release-deploy"
loader = importlib.machinery.SourceFileLoader("madar_release_deploy_cli", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
release_cli = importlib.util.module_from_spec(spec)
loader.exec_module(release_cli)


SHA = "c" * 40


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeOperations:
    def __init__(self):
        self.calls = []
        self.compatibility = release_cli.Compatibility(
            81, 83, 83, "expand-only", 81, 83,
        )

    def verify_source(self, sha): self.calls.append(("verify_source", sha))
    def build(self, sha, slot):
        self.calls.append(("build", sha, slot))
        return {
            "backend": "backend@sha256:1", "frontend": "frontend@sha256:2",
            "worker": "backend@sha256:1", "build_timestamp": "2026-08-25T00:00:00Z",
        }
    def schema_version(self):
        self.calls.append(("schema_version",))
        return 83
    def preflight(self, sha, slot, images, schema): self.calls.append(("preflight", sha, slot, schema))
    def start_candidate(self, sha, slot, images): self.calls.append(("start_candidate", sha, slot))
    def validate_candidate(self, sha, slot): self.calls.append(("validate_candidate", sha, slot))
    def validate_active_refresh_prerequisites(self, sha, slot, images):
        self.calls.append(("validate_active_refresh_prerequisites", sha, slot))
    def refresh_active_runtime_services(self, sha, slot, images):
        self.calls.append(("refresh_active_runtime_services", sha, slot))
    def validate_stable_candidate(self, sha):
        self.calls.append(("validate_stable_candidate", sha))
    def stop_candidate(self, slot, *, expected_serving=None):
        self.calls.append(("stop_candidate", slot))
    def activate_workers(self, sha, slot, images): self.calls.append(("activate_workers", sha, slot))
    def deactivate_workers(self, release): self.calls.append(("deactivate_workers", release["slot"]))
    def _json(self, url):
        if url.endswith("/health/version"):
            return {"release_sha": SHA}
        return {"ready": True}


class ReleaseBootstrapTests(unittest.TestCase):
    def compatibility(self):
        return release_cli.Compatibility(81, 83, 83, "expand-only", 81, 83)

    def test_schema_probe_uses_apikey_only_for_opaque_server_secret(self):
        headers = release_cli.supabase_server_headers(
            "sb_secret_synthetic_fixture_not_a_credential"
        )
        self.assertEqual({name.lower() for name in headers}, {"apikey"})

    def test_schema_probe_retains_legacy_service_role_bearer(self):
        headers = release_cli.supabase_server_headers(
            "synthetic-legacy-service-role-jwt"
        )
        self.assertEqual(
            {name.lower() for name in headers},
            {"apikey", "authorization"},
        )

    def test_prepare_keeps_workers_and_traffic_inactive(self):
        with tempfile.TemporaryDirectory() as root:
            operations = FakeOperations()
            record = release_cli.prepare_release(
                sha=SHA, slot="green", state_root=Path(root),
                compatibility=self.compatibility(), operations=operations,
            )
            persisted = json.loads((Path(root) / "prepared-release.json").read_text())
        self.assertEqual(record["status"], "candidate_validated_workers_inactive")
        self.assertEqual(persisted["release_sha"], SHA)
        self.assertFalse(any(call[0] == "activate_workers" for call in operations.calls))

    def test_normal_prepare_retry_is_idempotent_after_completed_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            recovery_state = {
                "active_slot": "green",
                "known_good_release": {
                    "sha": "a" * 40, "slot": "green", "schema": 96,
                    "schema_recovery": True, "migration_result": "not_requested",
                },
                "compatible_fallback_release": {
                    "sha": "a" * 40, "slot": "blue", "schema": 96,
                    "schema_recovery": True, "migration_result": "not_requested",
                },
                "history": [{"schema_recovery": True, "phase": "complete"}],
            }
            state_path = root_path / "state.json"
            state_path.write_text(json.dumps(recovery_state), encoding="utf-8")
            before = state_path.read_bytes()
            operations = FakeOperations()
            operations.schema_version = lambda: 96
            compatibility = release_cli.Compatibility(96, 99, 99, "expand-only", 96, 99)
            first = release_cli.prepare_release(
                sha=SHA, slot="blue", state_root=root_path,
                compatibility=compatibility, operations=operations,
            )
            second = release_cli.prepare_release(
                sha=SHA, slot="blue", state_root=root_path,
                compatibility=compatibility, operations=operations,
            )
            state_unchanged = before == state_path.read_bytes()
        self.assertEqual(first, second)
        self.assertEqual(sum(call[0] == "build" for call in operations.calls), 1)
        self.assertEqual(sum(call[0] == "start_candidate" for call in operations.calls), 1)
        self.assertTrue(state_unchanged)

    def test_interrupted_normal_prepare_reuses_images_and_retries_normally(self):
        class InterruptOnce(FakeOperations):
            failures = 1
            def start_candidate(self, sha, slot, images):
                self.calls.append(("start_candidate", sha, slot))
                if self.failures:
                    self.failures -= 1
                    raise RuntimeError("synthetic_prepare_interruption")

        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            state_path = root_path / "state.json"
            state_path.write_text(json.dumps({
                "active_slot": "green",
                "known_good_release": {"sha": "a" * 40, "slot": "green"},
                "history": [{"schema_recovery": True, "phase": "complete"}],
            }))
            operations = InterruptOnce()
            operations.schema_version = lambda: 96
            compatibility = release_cli.Compatibility(96, 99, 99, "expand-only", 96, 99)
            with self.assertRaisesRegex(RuntimeError, "synthetic_prepare_interruption"):
                release_cli.prepare_release(
                    sha=SHA, slot="blue", state_root=root_path,
                    compatibility=compatibility, operations=operations,
                )
            prepared = json.loads(
                release_cli.prepared_release_path(root_path).read_text()
            )
            self.assertEqual(prepared["status"], "preparing")
            result = release_cli.prepare_release(
                sha=SHA, slot="blue", state_root=root_path,
                compatibility=compatibility, operations=operations,
            )
        self.assertEqual(result["status"], "candidate_validated_workers_inactive")
        self.assertEqual(sum(call[0] == "build" for call in operations.calls), 1)
        self.assertEqual(sum(call[0] == "start_candidate" for call in operations.calls), 2)

    def test_normal_prepare_rejects_incompatible_candidate_after_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            operations = FakeOperations()
            operations.schema_version = lambda: 96
            with self.assertRaisesRegex(RuntimeError, "candidate_schema_incompatible"):
                release_cli.prepare_release(
                    sha=SHA, slot="blue", state_root=Path(root),
                    compatibility=release_cli.Compatibility(
                        97, 99, 99, "expand-only", 97, 99
                    ),
                    operations=operations,
                )
        self.assertFalse(any(call[0] == "build" for call in operations.calls))

    def test_stale_recovery_identity_does_not_hijack_normal_prepare(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            (root_path / "state.json").write_text(json.dumps({
                "active_slot": "green",
                "known_good_release": {
                    "sha": "a" * 40, "slot": "green", "schema": 96,
                },
                "history": [{
                    "schema_recovery": True, "phase": "complete",
                    "recovery_id": "stale-history-only",
                }],
            }))
            operations = FakeOperations()
            operations.schema_version = lambda: 96
            result = release_cli.prepare_release(
                sha=SHA, slot="blue", state_root=root_path,
                compatibility=release_cli.Compatibility(
                    96, 99, 99, "expand-only", 96, 99
                ),
                operations=operations,
            )
        self.assertEqual(result["status"], "candidate_validated_workers_inactive")

    def test_activate_requires_exact_prepared_identity(self):
        with tempfile.TemporaryDirectory() as root:
            operations = FakeOperations()
            release_cli.prepare_release(
                sha=SHA, slot="green", state_root=Path(root),
                compatibility=self.compatibility(), operations=operations,
            )
            with self.assertRaisesRegex(RuntimeError, "identity_mismatch"):
                release_cli.activate_prepared_release(
                    sha="d" * 40, slot="green", state_root=Path(root), operations=operations,
                )
            result = release_cli.activate_prepared_release(
                sha=SHA, slot="green", state_root=Path(root), operations=operations,
            )
        self.assertEqual(result["status"], "candidate_workers_active")

    def test_adoption_requires_workers_and_stable_proxy_identity(self):
        with tempfile.TemporaryDirectory() as root:
            operations = FakeOperations()
            release_cli.prepare_release(
                sha=SHA, slot="green", state_root=Path(root),
                compatibility=self.compatibility(), operations=operations,
            )
            with self.assertRaisesRegex(RuntimeError, "workers_not_active"):
                release_cli.adopt_prepared_release(
                    sha=SHA, slot="green", state_root=Path(root),
                    compatibility=self.compatibility(), operations=operations,
                )
            release_cli.activate_prepared_release(
                sha=SHA, slot="green", state_root=Path(root), operations=operations,
            )
            with patch.object(release_cli.urllib.request, "urlopen", return_value=FakeResponse()):
                result = release_cli.adopt_prepared_release(
                    sha=SHA, slot="green", state_root=Path(root),
                    compatibility=self.compatibility(), operations=operations,
                )
            state = json.loads((Path(root) / "state.json").read_text())
        self.assertEqual(result["phase"], "bootstrap_adopted")
        self.assertEqual(state["known_good_release"]["sha"], SHA)
        self.assertFalse((Path(root) / "prepared-release.json").exists())

    def test_inactive_candidate_masks_active_worker_requirements_until_cutover(self):
        operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        operations.compatibility = release_cli.Compatibility(
            schema_min=81,
            schema_max=86,
            target_schema=86,
            migration_class="expand-only",
            rollback_schema_min=81,
            rollback_schema_max=86,
        )
        operations.release_root = Path("/tmp/release")
        operations.env_file = Path("/tmp/release.env")
        operations.schema_version = lambda: 83
        images = {
            "backend": "backend@sha256:1", "frontend": "frontend@sha256:2",
            "worker": "backend@sha256:1", "build_timestamp": "2026-08-25T00:00:00Z",
        }
        with patch.dict(os.environ, {
            "MADAR_STORAGE_ROOT": "/var/lib/madar/storage",
            "NOTIFICATION_WORKER_ENABLED": "true",
            "DATA_DELETION_WORKER_ENABLED": "true",
            "CALENDAR_FEATURE_ENABLED": "true",
            "CALENDAR_SYNC_WORKER_ENABLED": "true",
        }, clear=True):
            inactive = operations._environment(SHA, "green", images, workers_active=False)
            active = operations._environment(SHA, "green", images, workers_active=True)
        self.assertEqual(inactive["NOTIFICATION_WORKER_ENABLED"], "false")
        self.assertEqual(inactive["DATA_DELETION_WORKER_ENABLED"], "false")
        self.assertEqual(inactive["CALENDAR_FEATURE_ENABLED"], "false")
        self.assertEqual(inactive["CALENDAR_SYNC_WORKER_ENABLED"], "false")
        self.assertEqual(active["NOTIFICATION_WORKER_ENABLED"], "true")
        self.assertEqual(active["DATA_DELETION_WORKER_ENABLED"], "true")
        self.assertEqual(active["CALENDAR_FEATURE_ENABLED"], "true")
        self.assertEqual(active["CALENDAR_SYNC_WORKER_ENABLED"], "true")
        self.assertEqual(inactive["MADAR_RELEASE_SLOT"], "green")

    def test_worker_stop_command_failure_is_fatal(self):
        operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        operations._container_state = lambda _name: ("sha256:x", "running", "healthy")
        operations.run = unittest.mock.Mock(side_effect=RuntimeError("docker stop failed"))
        with self.assertRaisesRegex(RuntimeError, "docker stop failed"):
            operations.deactivate_workers({"slot": "blue"})

    def test_worker_quiescence_inhibits_restart_and_proves_policy(self):
        operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        operations._worker_names = lambda _slot: ["madar-blue-notification-worker"]
        states = iter([
            ("sha256:x", "running", "healthy"),
            ("sha256:x", "exited", "none"),
            ("sha256:x", "exited", "none"),
        ])
        operations._container_state = lambda _name: next(states)
        operations._container_restart_policy = lambda _name: "no"
        operations.run = unittest.mock.Mock()
        with patch.object(release_cli.time, "sleep"):
            operations.deactivate_workers({"slot": "blue"})
        self.assertEqual(
            operations.run.call_args_list,
            [
                unittest.mock.call([
                    "docker", "update", "--restart=no",
                    "madar-blue-notification-worker",
                ]),
                unittest.mock.call([
                    "docker", "stop", "madar-blue-notification-worker",
                ]),
            ],
        )

    def test_stale_worker_authority_cannot_activate_consumers(self):
        with tempfile.TemporaryDirectory() as root:
            operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
            operations.state_root = Path(root)
            operations.schema_version = lambda: 96
            operations._compose = unittest.mock.Mock()
            (Path(root) / "state.json").write_text(json.dumps({
                "active_slot": "green",
                "known_good_release": {
                    "sha": SHA, "slot": "green",
                    "worker_generation": "2" * 64,
                },
            }))
            release_cli.write_worker_authority(
                Path(root), generation="1" * 64, owner="CANDIDATE",
                old={"sha": "a" * 40, "slot": "blue"},
                candidate={"sha": SHA, "slot": "green"},
            )
            with self.assertRaisesRegex(RuntimeError, "stale_authority"):
                operations.activate_workers(SHA, "green", {})
        operations._compose.assert_not_called()

    def test_destructive_candidate_start_rechecks_loaded_route_under_lock(self):
        with tempfile.TemporaryDirectory() as root:
            operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
            operations.state_root = Path(root)
            operations._loaded_serving_slot = lambda: "green"
            operations._inhibit_worker_slot = unittest.mock.Mock()
            operations._compose = unittest.mock.Mock()
            with self.assertRaisesRegex(RuntimeError, "target_is_serving"):
                operations.start_candidate(SHA, "green", {})
        operations._inhibit_worker_slot.assert_not_called()
        operations._compose.assert_not_called()

    def test_authority_never_overrides_contradictory_old_worker_state(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            generation = "3" * 64
            operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
            operations.state_root = root_path
            operations.container_prefix = "madar"
            operations.schema_version = lambda: 96
            operations._compose = unittest.mock.Mock()
            (root_path / "state.json").write_text(json.dumps({
                "in_progress_release": {
                    "release_sha": SHA, "candidate_slot": "green",
                    "previous_known_good_release": {
                        "sha": "a" * 40, "slot": "blue",
                    },
                    "worker_generation": generation,
                },
            }))
            release_cli.write_worker_authority(
                root_path, generation=generation, owner="CANDIDATE",
                old={"sha": "a" * 40, "slot": "blue"},
                candidate={"sha": SHA, "slot": "green"},
            )
            states = {
                "madar-blue-notification-worker": (
                    "sha256:x", "running", "healthy"
                ),
            }
            operations._container_state = states.get
            with self.assertRaisesRegex(RuntimeError, "runtime_contradiction"):
                operations.activate_workers(SHA, "green", {})
        operations._compose.assert_not_called()

    def test_worker_still_running_after_stop_is_fatal(self):
        operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        operations._container_state = lambda _name: ("sha256:x", "running", "healthy")
        operations.run = unittest.mock.Mock()
        with self.assertRaisesRegex(RuntimeError, "worker_failed_to_quiesce"):
            operations.deactivate_workers({"slot": "blue"})

    def test_worker_restart_during_quiescence_is_fatal(self):
        operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        states = iter([
            ("sha256:x", "running", "healthy"),
            ("sha256:x", "exited", "none"),
            ("sha256:x", "running", "healthy"),
        ])
        operations._worker_names = lambda _slot: ["madar-blue-notification-worker"]
        operations._container_state = lambda _name: next(states)
        operations.run = unittest.mock.Mock()
        with patch.object(release_cli.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "worker_failed_to_quiesce"):
                operations.deactivate_workers({"slot": "blue"})

    def test_worker_inspection_error_is_not_treated_as_absence(self):
        operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        failure = subprocess.CompletedProcess([], 1, "", "synthetic daemon error")
        with patch.object(release_cli.subprocess, "run", return_value=failure):
            with self.assertRaisesRegex(RuntimeError, "worker_state_unknown"):
                operations.deactivate_workers({"slot": "blue"})

    def test_worker_starting_becomes_healthy_within_bounded_wait(self):
        operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        calls = {}
        def state(name):
            calls[name] = calls.get(name, 0) + 1
            health = "starting" if calls[name] == 2 else "healthy"
            return ("sha256:x", "running", health)
        operations._container_state = state
        operations.run = unittest.mock.Mock()
        with patch.dict(os.environ, {
            "MADAR_WORKER_READY_ATTEMPTS": "2",
            "MADAR_WORKER_READY_RETRY_SECONDS": "0.1",
        }), patch.object(release_cli.time, "sleep"):
            operations.restore_workers({"slot": "blue"})
        self.assertEqual(operations.run.call_count, 2)

    def test_worker_starting_timeout_is_fatal(self):
        operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        operations._container_state = lambda _name: (
            "sha256:x", "running", "starting"
        )
        operations.run = unittest.mock.Mock()
        with patch.dict(os.environ, {
            "MADAR_WORKER_READY_ATTEMPTS": "2",
            "MADAR_WORKER_READY_RETRY_SECONDS": "0.1",
        }), patch.object(release_cli.time, "sleep"), self.assertRaisesRegex(
            RuntimeError, "retained_worker_restore_timeout"
        ):
            operations.restore_workers({"slot": "blue"})

    def test_worker_terminal_failure_is_immediately_fatal(self):
        operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        calls = 0
        def state(_name):
            nonlocal calls
            calls += 1
            return (
                ("sha256:x", "running", "healthy")
                if calls <= 3 else ("sha256:x", "exited", "unhealthy")
            )
        operations._container_state = state
        operations.run = unittest.mock.Mock()
        with self.assertRaisesRegex(RuntimeError, ":exited"):
            operations.restore_workers({"slot": "blue"})

    def test_worker_ownership_uses_actual_state_not_stale_metadata(self):
        operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        states = {
            "madar-blue-notification-worker": ("x", "exited", "none"),
            "madar-blue-calendar-sync-worker": ("x", "exited", "none"),
            "madar-blue-data-deletion-worker": ("x", "exited", "none"),
            "madar-green-notification-worker": ("x", "running", "healthy"),
            "madar-green-calendar-sync-worker": ("x", "running", "healthy"),
            "madar-green-data-deletion-worker": ("x", "running", "healthy"),
        }
        operations._container_state = states.get
        self.assertEqual(
            operations.worker_ownership(
                {"slot": "blue", "workers_active": True},
                {"slot": "green", "workers_active": False},
            ),
            "candidate",
        )

    def test_installed_recovery_helpers_resolve_inside_installed_control_root(self):
        with tempfile.TemporaryDirectory() as root:
            installed = Path(root) / "deployment"
            (installed / "bin").mkdir(parents=True)
            (installed / "scripts").mkdir()
            script = installed / "bin/madar-release-deploy"
            for name in ("backup_support.py", "replicate_latest_node1.py"):
                (installed / "scripts" / name).write_text("# fixture\n", encoding="utf-8")
            with patch.object(release_cli, "SCRIPT", script):
                resolved = release_cli.DockerGitOperations.recovery_helper_root()
        self.assertEqual(resolved, installed / "scripts")

    def test_serving_slot_identity_wins_when_proxy_file_is_stale(self):
        operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        operations._json = lambda _url: {"release_sha": SHA, "release_slot": "green"}
        operations.current_traffic_slot = lambda: "blue"
        self.assertEqual(
            operations.resolve_serving_slot({"blue": SHA, "green": SHA}),
            "green",
        )

    def test_serving_slot_is_unknown_when_health_and_proxy_cannot_identify_it(self):
        operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        operations._json = lambda _url: {"release_sha": SHA}
        operations.current_traffic_slot = lambda: (_ for _ in ()).throw(
            RuntimeError("unknown")
        )
        self.assertIsNone(
            operations.resolve_serving_slot({"blue": SHA, "green": SHA})
        )

    def test_same_sha_missing_slot_does_not_trust_proxy_file(self):
        operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
        operations._json = lambda _url: {"release_sha": SHA, "release_slot": ""}
        operations.current_traffic_slot = lambda: "blue"
        self.assertIsNone(
            operations.resolve_serving_slot({"blue": SHA, "green": SHA})
        )

    def test_loaded_serving_slot_supports_legacy_runtime_without_slot_identity(self):
        operations = release_cli.DockerGitOperations.__new__(
            release_cli.DockerGitOperations
        )
        other_sha = "d" * 40
        identities = {
            "http://127.0.0.1:8001/health/version": {
                "release_sha": SHA,
            },
            "http://127.0.0.1:8101/health/version": {
                "release_sha": SHA,
            },
            "http://127.0.0.1:8201/health/version": {
                "release_sha": other_sha,
                "release_slot": "green",
            },
        }
        operations._json = identities.__getitem__

        self.assertEqual(
            operations._loaded_serving_slot(),
            "blue",
        )

    def test_loaded_serving_slot_rejects_legacy_same_sha_ambiguity(self):
        operations = release_cli.DockerGitOperations.__new__(
            release_cli.DockerGitOperations
        )
        identities = {
            "http://127.0.0.1:8001/health/version": {
                "release_sha": SHA,
            },
            "http://127.0.0.1:8101/health/version": {
                "release_sha": SHA,
            },
            "http://127.0.0.1:8201/health/version": {
                "release_sha": SHA,
            },
        }
        operations._json = identities.__getitem__

        with self.assertRaisesRegex(
            RuntimeError,
            "runtime_mutation_traffic_ambiguous",
        ):
            operations._loaded_serving_slot()

    def test_loaded_serving_slot_rejects_explicit_slot_direct_identity_mismatch(self):
        operations = release_cli.DockerGitOperations.__new__(
            release_cli.DockerGitOperations
        )
        other_sha = "d" * 40
        identities = {
            "http://127.0.0.1:8001/health/version": {
                "release_sha": SHA,
                "release_slot": "blue",
            },
            "http://127.0.0.1:8101/health/version": {
                "release_sha": other_sha,
                "release_slot": "blue",
            },
        }
        operations._json = identities.__getitem__

        with self.assertRaisesRegex(
            RuntimeError,
            "runtime_mutation_traffic_ambiguous",
        ):
            operations._loaded_serving_slot()

    def test_candidate_cleanup_rejects_serving_target_inside_mutation_lock(self):
        with tempfile.TemporaryDirectory() as root:
            operations = release_cli.DockerGitOperations.__new__(release_cli.DockerGitOperations)
            operations.state_root = Path(root)
            operations.resolve_serving_slot = lambda _expected: "green"
            operations.release_root = None
            with self.assertRaisesRegex(RuntimeError, "candidate_cleanup_target_is_serving"):
                operations.stop_candidate(
                    "green", expected_serving={"blue": "1" * 40, "green": SHA}
                )

    def test_post_migration_refresh_requires_exact_known_good_and_schema_83(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            operations = FakeOperations()
            state = {
                "active_slot": "green",
                "known_good_release": {
                    "sha": SHA, "slot": "green", "schema": 81,
                    "images": {"backend": "b", "frontend": "f", "worker": "b"},
                },
                "history": [],
            }
            (root_path / "state.json").write_text(json.dumps(state))
            operations.schema_version = lambda: 81
            with self.assertRaisesRegex(RuntimeError, "schema_not_ready"):
                release_cli.refresh_active_workers(
                    sha=SHA, slot="green", state_root=root_path, operations=operations,
                )
            operations.schema_version = lambda: 83
            result = release_cli.refresh_active_workers(
                sha=SHA, slot="green", state_root=root_path, operations=operations,
            )
            persisted = json.loads((root_path / "state.json").read_text())
        self.assertEqual(result["phase"], "post_migration_workers_refreshed")
        self.assertEqual(persisted["known_good_release"]["schema"], 83)
        self.assertIn(("refresh_active_runtime_services", SHA, "green"), operations.calls)


if __name__ == "__main__":
    unittest.main()

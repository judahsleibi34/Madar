import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


WEB_ROOT = Path(
    os.getenv("MADAR_TEST_REPOSITORY_ROOT")
    or Path(__file__).resolve().parents[2]
).resolve()
SCRIPT = WEB_ROOT / "deployment/bin/madar-release-deploy"
loader = importlib.machinery.SourceFileLoader(
    "madar_active_runtime_refresh_test", str(SCRIPT),
)
spec = importlib.util.spec_from_loader(loader.name, loader)
release_cli = importlib.util.module_from_spec(spec)
loader.exec_module(release_cli)


SHA = "d" * 40
OTHER_SHA = "e" * 40
IMAGES = {
    "backend": "madar-backend:test@sha256:backend",
    "frontend": "madar-frontend:test@sha256:frontend",
    "worker": "madar-backend:test@sha256:backend",
    "build_timestamp": "2026-09-01T00:00:00Z",
}


class FakeOperations:
    def __init__(self, *, schema=93, missing=(), preflight_error=None,
                 prerequisite_error=None):
        self.schema = schema
        self.missing = set(missing)
        self.preflight_error = preflight_error
        self.prerequisite_error = prerequisite_error
        self.calls = []
        self.compatibility = release_cli.Compatibility(
            81, 93, 93, "expand-only", 81, 92,
        )

    def schema_version(self):
        self.calls.append(("schema_version",))
        return self.schema

    def verify_source(self, sha):
        self.calls.append(("verify_source", sha))

    def preflight(self, sha, slot, images, schema):
        self.calls.append(("preflight", sha, slot, images, schema))
        if self.preflight_error:
            raise RuntimeError(self.preflight_error)

    def validate_active_refresh_prerequisites(self, sha, slot, images):
        self.calls.append(("validate_active_refresh_prerequisites", sha, slot, images))
        if self.prerequisite_error:
            raise RuntimeError(self.prerequisite_error)

    def refresh_active_runtime_services(self, sha, slot, images):
        self.calls.append(("refresh_active_runtime_services", sha, slot, images))
        self.missing.clear()

    def validate_candidate(self, sha, slot):
        self.calls.append(("validate_candidate", sha, slot))
        if self.missing:
            raise RuntimeError("candidate_deep_validation_failed")

    def validate_stable_candidate(self, sha):
        self.calls.append(("validate_stable_candidate", sha))


class ActiveRuntimeRefreshTests(unittest.TestCase):
    def write_state(self, root, *, sha=SHA, slot="green", active_slot="green",
                    schema=93, known_good=True):
        state = {
            "active_slot": active_slot,
            "known_good_release": ({
                "sha": sha,
                "slot": slot,
                "schema": schema,
                "images": IMAGES,
            } if known_good else {}),
            "in_progress_release": None,
            "rollback_failure": None,
            "history": [],
        }
        (Path(root) / "state.json").write_text(json.dumps(state), encoding="utf-8")
        return state

    def refresh(self, root, operations, *, sha=SHA, slot="green"):
        return release_cli.refresh_active_runtime(
            sha=sha, slot=slot, state_root=Path(root), operations=operations,
        )

    def test_installed_direct_invocation_applies_canonical_path_contract(self):
        with patch.dict(os.environ, {}, clear=True):
            contract = release_cli.load_production_path_contract(installed=True)
            self.assertEqual(os.environ["MADAR_STORAGE_ROOT"], "/var/lib/madar/storage")
            self.assertEqual(os.environ["MADAR_PRODUCTION_REPO"], "/srv/madar/production")
            self.assertEqual(os.environ["MADAR_ENV_FILE"], "/etc/madar/production.env")
        self.assertEqual(contract["MADAR_DEPLOY_STATE_ROOT"], "/var/lib/madar/releases")

    def test_runtime_refresh_uses_environment_file_over_stale_shell_config(self):
        with tempfile.TemporaryDirectory() as root:
            env_file = Path(root) / "production.env"
            env_file.write_text(
                "WEB_PUSH_ENABLED=true\n"
                "WEB_PUSH_VAPID_PUBLIC_KEY=public-fixture\n"
                "MADAR_STORAGE_ROOT=/unsafe/ignored\n",
                encoding="utf-8",
            )
            env_file.chmod(0o600)
            with patch.dict(os.environ, {
                "WEB_PUSH_ENABLED": "false",
                "MADAR_STORAGE_ROOT": "/var/lib/madar/storage",
            }, clear=True):
                release_cli.load_active_runtime_environment(env_file)
                self.assertEqual(os.environ["WEB_PUSH_ENABLED"], "true")
                self.assertEqual(
                    os.environ["WEB_PUSH_VAPID_PUBLIC_KEY"], "public-fixture",
                )
                self.assertEqual(
                    os.environ["MADAR_STORAGE_ROOT"], "/var/lib/madar/storage",
                )

    def test_storage_root_is_required_absolute_and_never_release_local(self):
        operations = release_cli.DockerGitOperations.__new__(
            release_cli.DockerGitOperations
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "not_configured"):
                operations._storage_root()
        with patch.dict(os.environ, {"MADAR_STORAGE_ROOT": "backend"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "invalid"):
                operations._storage_root()
        with patch.dict(
            os.environ, {"MADAR_STORAGE_ROOT": "/var/lib/madar/storage"}, clear=True,
        ):
            self.assertEqual(
                operations._storage_root(), Path("/var/lib/madar/storage")
            )

    def test_refresh_recovers_each_supported_missing_worker(self):
        for service in (
            "notification-worker",
            "calendar-sync-worker",
            "data-deletion-worker",
            "parser-worker",
        ):
            with self.subTest(service=service), tempfile.TemporaryDirectory() as root:
                self.write_state(root)
                operations = FakeOperations(missing={service})
                result = self.refresh(root, operations)
                self.assertEqual(result["phase"], "active_runtime_refreshed")
                self.assertFalse(operations.missing)
                names = [call[0] for call in operations.calls]
                self.assertLess(
                    names.index("validate_active_refresh_prerequisites"),
                    names.index("refresh_active_runtime_services"),
                )
                self.assertLess(
                    names.index("refresh_active_runtime_services"),
                    names.index("validate_candidate"),
                )

    def test_success_keeps_state_coherent_and_revalidates_stable_proxy(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_state(root)
            operations = FakeOperations()
            result = self.refresh(root, operations)
            state = json.loads((Path(root) / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "known_good")
        self.assertEqual(state["active_slot"], "green")
        self.assertEqual(state["known_good_release"]["sha"], SHA)
        self.assertEqual(state["known_good_release"]["schema"], 93)
        self.assertEqual(state["history"][-1]["phase"], "active_runtime_refreshed")
        self.assertEqual(operations.calls[-1], ("validate_stable_candidate", SHA))
        self.assertFalse(
            {"build", "automatic_migrate", "switch_traffic"}
            & {call[0] for call in operations.calls}
        )

    def test_wrong_sha_slot_and_non_known_good_are_rejected(self):
        cases = (
            ({"sha": SHA}, OTHER_SHA, "green"),
            ({"sha": SHA}, SHA, "blue"),
            ({"sha": SHA, "known_good": False}, SHA, "green"),
        )
        for overrides, requested_sha, requested_slot in cases:
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as root:
                self.write_state(root, **overrides)
                operations = FakeOperations()
                with self.assertRaisesRegex(RuntimeError, "identity_mismatch"):
                    self.refresh(
                        root, operations, sha=requested_sha, slot=requested_slot,
                    )
                self.assertNotIn(
                    "refresh_active_runtime_services",
                    {call[0] for call in operations.calls},
                )

    def test_schema_mismatch_is_rejected_before_preflight_or_docker(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_state(root, schema=92)
            operations = FakeOperations(schema=93)
            with self.assertRaisesRegex(RuntimeError, "schema_mismatch"):
                self.refresh(root, operations)
        self.assertNotIn("preflight", {call[0] for call in operations.calls})
        self.assertNotIn(
            "refresh_active_runtime_services", {call[0] for call in operations.calls}
        )

    def test_storage_preflight_failure_leaves_docker_untouched(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_state(root)
            operations = FakeOperations(preflight_error="storage_unavailable:uploads")
            with self.assertRaisesRegex(RuntimeError, "storage_unavailable"):
                self.refresh(root, operations)
        self.assertNotIn(
            "refresh_active_runtime_services", {call[0] for call in operations.calls}
        )

    def test_image_identity_failure_leaves_docker_untouched(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_state(root)
            operations = FakeOperations(
                prerequisite_error="active_refresh_image_identity_mismatch:backend"
            )
            with self.assertRaisesRegex(RuntimeError, "image_identity_mismatch"):
                self.refresh(root, operations)
        self.assertNotIn(
            "refresh_active_runtime_services", {call[0] for call in operations.calls}
        )

    def test_worker_outages_are_allowed_but_core_degradation_is_not(self):
        operations = release_cli.DockerGitOperations.__new__(
            release_cli.DockerGitOperations
        )
        operations.compatibility = FakeOperations().compatibility
        components = {name: "ok" for name in release_cli.ACTIVE_REFRESH_CORE_COMPONENTS}
        components.update({name: "unavailable" for name in release_cli.ACTIVE_REFRESH_COMPONENTS})
        identity = {
            "release_sha": SHA,
            "schema_compatible_min": 81,
            "schema_compatible_max": 93,
        }
        operations._validate_refresh_health_payload(
            sha=SHA, readiness={"ready": False, "components": components},
            identity=identity,
        )
        components["storage"] = "unavailable"
        with self.assertRaisesRegex(RuntimeError, "core_prerequisite_failed"):
            operations._validate_refresh_health_payload(
                sha=SHA, readiness={"ready": False, "components": components},
                identity=identity,
            )

    def test_runtime_recreation_uses_only_existing_images_and_required_services(self):
        operations = release_cli.DockerGitOperations.__new__(
            release_cli.DockerGitOperations
        )
        operations.schema_version = lambda: 93
        operations._compose = Mock()
        operations.refresh_active_runtime_services(SHA, "green", IMAGES)
        args = operations._compose.call_args.args
        self.assertEqual(args[:3], (SHA, "green", IMAGES))
        for value in (
            "--no-build", "parser-worker", "backend", "notification-worker",
            "calendar-sync-worker", "data-deletion-worker",
        ):
            self.assertIn(value, args)
        self.assertNotIn("build", args)
        self.assertNotIn("down", args)
        self.assertNotIn("madar-switch-traffic", args)
        self.assertTrue(operations._compose.call_args.kwargs["workers_active"])

    def test_web_push_environment_is_propagated_without_logging_secrets(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_state(root)
            operations = FakeOperations()
            output = io.StringIO()
            secrets = {
                "WEB_PUSH_ENABLED": "true",
                "WEB_PUSH_VAPID_PUBLIC_KEY": "public-fixture",
                "WEB_PUSH_VAPID_PRIVATE_KEY": "private-fixture",
                "WEB_PUSH_VAPID_SUBJECT": "mailto:fixture@example.invalid",
                "SUPABASE_SERVICE_KEY": "supabase-fixture-secret",
            }
            with (
                patch.dict(os.environ, secrets, clear=False),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(output),
            ):
                self.refresh(root, operations)
        rendered = output.getvalue()
        for secret in secrets.values():
            self.assertNotIn(secret, rendered)


if __name__ == "__main__":
    unittest.main()

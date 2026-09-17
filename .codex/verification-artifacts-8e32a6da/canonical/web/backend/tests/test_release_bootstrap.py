import importlib.machinery
import importlib.util
import json
import os
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
    def stop_candidate(self, slot): self.calls.append(("stop_candidate", slot))
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

import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from unittest import TestCase
from unittest.mock import patch


WEB_ROOT = Path(
    os.getenv("MADAR_TEST_REPOSITORY_ROOT")
    or Path(__file__).resolve().parents[2]
).resolve()
RELEASE_DEPLOY = WEB_ROOT / "deployment/bin/madar-release-deploy"
INSTALLER = WEB_ROOT / "deployment/bin/madar-install-control-plane"
MIGRATE = WEB_ROOT / "deployment/bin/madar-migrate"
GUARD = WEB_ROOT / "deployment/bin/madar-control-plane-guard"
TRANSITION_VALIDATOR = WEB_ROOT / "scripts/check_migration_transitions.py"


def load_release_cli():
    loader = importlib.machinery.SourceFileLoader(
        "madar_release_deploy_schema_contract_test",
        str(RELEASE_DEPLOY),
    )
    spec = importlib.util.spec_from_loader(
        loader.name,
        loader,
    )
    if spec is None:
        raise RuntimeError(
            "unable to create release deployer test spec"
        )

    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class SchemaCompatibilityControlPlaneTests(TestCase):
    def test_slot_environment_uses_loaded_release_compatibility(self):
        release_cli = load_release_cli()

        compatibility = release_cli.Compatibility(
            schema_min=81,
            schema_max=86,
            target_schema=86,
            migration_class="expand-only",
            rollback_schema_min=81,
            rollback_schema_max=86,
        )

        operations = release_cli.DockerGitOperations.__new__(
            release_cli.DockerGitOperations
        )
        operations.repo = Path("/tmp/repo")
        operations.state_root = Path("/tmp/state")
        operations.env_file = Path("/tmp/env")
        operations.release_root = Path("/tmp/release")
        operations.compatibility = compatibility
        operations.schema_version = lambda: 83

        images = {
            "backend":
                "madar-backend:test@sha256:deadbeef",
            "frontend":
                "madar-frontend:test@sha256:feedface",
            "worker":
                "madar-backend:test@sha256:deadbeef",
            "build_timestamp":
                "2026-08-27T00:00:00Z",
        }

        with patch.dict(os.environ, {}, clear=True):
            environment = operations._environment(
                "a" * 40,
                "green",
                images,
                workers_active=False,
            )

        self.assertEqual(
            environment["SCHEMA_COMPATIBLE_MIN"],
            "81",
        )
        self.assertEqual(
            environment["SCHEMA_COMPATIBLE_MAX"],
            "86",
        )

    def test_schema_83_is_not_hardcoded_by_release_controller(self):
        source = RELEASE_DEPLOY.read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            '"SCHEMA_COMPATIBLE_MAX": "83"',
            source,
        )

        self.assertIn(
            "self.compatibility.schema_max",
            source,
        )

    def test_candidate_contract_is_attested(self):
        source = RELEASE_DEPLOY.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "control_plane_release_contract_mismatch",
            source,
        )

        self.assertIn(
            "release_schema_contract_mismatch",
            source,
        )

    def test_installer_installs_guard_and_migration_runner(self):
        source = INSTALLER.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "bin/madar-migrate",
            source,
        )

        self.assertIn(
            "bin/madar-control-plane-guard",
            source,
        )

        self.assertIn(
            "migrations-*.json",
            source,
        )

        self.assertIn(
            "CONTROL_PLANE_SOURCE_SHA",
            source,
        )

    def test_migration_runner_uses_explicit_git_repository(self):
        source = MIGRATE.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "MADAR_MIGRATION_REPOSITORY_ROOT",
            source,
        )

        self.assertIn(
            "--expected-sha",
            source,
        )

        self.assertIn(
            "migration_manifest",
            source,
        )

    def test_transition_validator_accepts_repository(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(TRANSITION_VALIDATOR),
            ],
            cwd=WEB_ROOT.parent,
            check=False,
        )

        self.assertEqual(
            completed.returncode,
            0,
        )

    def test_control_plane_guard_is_executable(self):
        self.assertTrue(GUARD.is_file())
        self.assertTrue(
            GUARD.stat().st_mode & 0o111
        )

import os
import unittest
from pathlib import Path


WEB_ROOT = Path(
    os.getenv("MADAR_TEST_REPOSITORY_ROOT")
    or Path(__file__).resolve().parents[2]
).resolve()
DEPLOY = WEB_ROOT / "deployment" / "bin" / "madar-production-deploy"
WRAPPER = WEB_ROOT / "deployment" / "bin" / "madar-auto-deploy"
COMPOSE = WEB_ROOT / "docker-compose.yml"


class MonorepoDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.deploy = DEPLOY.read_text(encoding="utf-8")
        self.wrapper = WRAPPER.read_text(encoding="utf-8")
        self.compose = COMPOSE.read_text(encoding="utf-8")

    def test_git_and_compose_roots_are_distinct_and_explicit(self):
        self.assertIn('readonly REPO_ROOT="/home/madar/saas/Madar"', self.deploy)
        self.assertIn('COMPOSE_ROOT="$REPO_ROOT/web"', self.deploy)
        self.assertIn('--project-directory "$COMPOSE_ROOT"', self.deploy)
        self.assertIn('-f "$COMPOSE_FILE"', self.deploy)
        self.assertIn('--project-name "$COMPOSE_PROJECT"', self.deploy)
        self.assertIn('git -C "$REPO_ROOT"', self.deploy)

    def test_env_file_is_absolute_and_shared_with_service_env_files(self):
        self.assertIn('readonly ENV_FILE="${MADAR_ENV_FILE:-$REPO_ROOT/.env}"', self.deploy)
        self.assertIn('export MADAR_ENV_FILE="$ENV_FILE"', self.deploy)
        self.assertIn('export MADAR_STORAGE_ROOT="$STORAGE_ROOT"', self.deploy)
        self.assertIn('--env-file "$ENV_FILE"', self.deploy)
        self.assertEqual(self.compose.count("${MADAR_ENV_FILE:-../.env}"), 3)

    def test_legacy_layout_remains_available_for_rollback(self):
        self.assertIn('elif [[ -f "$REPO_ROOT/docker-compose.yml" ]]', self.deploy)
        self.assertIn('git -C "$REPO_ROOT" reset --hard "$previous_commit"', self.deploy)
        self.assertIn('compose up -d --remove-orphans --wait --wait-timeout 120', self.deploy)
        self.assertIn('/health/ready', self.deploy)
        self.assertIn('merge-base --is-ancestor', self.deploy)

    def test_persistent_bind_mounts_keep_their_pre_move_host_paths(self):
        for path in (
            "${MADAR_STORAGE_ROOT:-../backend}/avatar_uploads",
            "${MADAR_STORAGE_ROOT:-../backend}/uploads",
            "${MADAR_STORAGE_ROOT:-../backend}/private_uploads",
            "${MADAR_STORAGE_ROOT:-../backend}/private_generated_charts",
        ):
            self.assertIn(path, self.compose)

    def test_wrapper_keeps_git_operations_at_repository_root(self):
        self.assertIn('git -C "$REPO_ROOT" fetch', self.wrapper)
        self.assertIn('exec "$DEPLOY_SCRIPT"', self.wrapper)


if __name__ == "__main__":
    unittest.main()

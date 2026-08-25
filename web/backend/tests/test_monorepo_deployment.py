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
RELEASE_DEPLOY = WEB_ROOT / "deployment" / "bin" / "madar-release-deploy"
RELEASE_LIBRARY = WEB_ROOT / "deployment" / "lib" / "release_deployer.py"


class MonorepoDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.deploy = DEPLOY.read_text(encoding="utf-8")
        self.wrapper = WRAPPER.read_text(encoding="utf-8")
        self.compose = COMPOSE.read_text(encoding="utf-8")
        self.release_deploy = RELEASE_DEPLOY.read_text(encoding="utf-8")
        self.release_library = RELEASE_LIBRARY.read_text(encoding="utf-8")

    def test_wrapper_delegates_a_clean_full_sha_to_immutable_deployer(self):
        self.assertIn('readonly REPO_ROOT="/home/madar/saas/Madar"', self.deploy)
        self.assertIn('git -C "$REPO_ROOT"', self.deploy)
        self.assertIn("status --porcelain --untracked-files=normal", self.deploy)
        self.assertIn('exec "$RELEASE_DEPLOY" "$TARGET_SHA"', self.deploy)

    def test_release_deployer_uses_explicit_compose_and_environment_roots(self):
        self.assertIn('"MADAR_ENV_FILE": str(self.env_file)', self.release_deploy)
        self.assertIn('"docker", "compose", "--project-name", f"madar-{slot}"', self.release_deploy)
        self.assertIn('"--project-directory", str(web)', self.release_deploy)
        self.assertIn('"--env-file", str(self.env_file)', self.release_deploy)
        self.assertEqual(self.compose.count("${MADAR_ENV_FILE:-../.env}"), 3)
        self.assertIn("candidate_image_identity_changed", self.release_deploy)
        self.assertIn("self._digest(tag)", self.release_deploy)

    def test_rollback_switches_to_retained_target_without_rebuild_or_git_reset(self):
        combined = self.deploy + self.release_deploy + self.release_library
        self.assertNotIn("reset --hard", combined)
        self.assertIn("traffic_switch_to_retained_known_good", self.release_library)
        self.assertIn("previous_traffic_target", self.release_library)
        self.assertIn("@sha256:", self.release_library)
        self.assertIn("known_bad_release_suppressed", self.release_library)
        self.assertIn("/health/ready", self.release_deploy)

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

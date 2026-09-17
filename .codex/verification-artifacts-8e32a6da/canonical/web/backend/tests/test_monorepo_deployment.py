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
ENVIRONMENT_LIBRARY = WEB_ROOT / "deployment" / "lib" / "environment_file.py"
SWITCH = WEB_ROOT / "deployment" / "bin" / "madar-switch-traffic"
PROXY_COMPOSE = WEB_ROOT / "deployment" / "proxy" / "docker-compose.yml"
PROXY_CONFIG = WEB_ROOT / "deployment" / "proxy" / "nginx.conf"
RELEASE_COMPOSE = WEB_ROOT / "deployment" / "docker-compose.release.yml"
AUTO_SERVICE = WEB_ROOT / "deployment" / "systemd" / "madar-auto-deploy.service"
AUTO_TIMER = WEB_ROOT / "deployment" / "systemd" / "madar-auto-deploy.timer"
BACKEND_DOCKERFILE = WEB_ROOT / "backend" / "Dockerfile"
FRONTEND_DOCKERFILE = WEB_ROOT / "frontend" / "Dockerfile"
INSTALLER = WEB_ROOT / "deployment" / "bin" / "madar-install-control-plane"
LEGACY_ENTRYPOINT = WEB_ROOT / "deployment" / "bin" / "madar-auto-deploy-legacy-entrypoint"
PATH_CONTRACT = WEB_ROOT / "deployment" / "production-paths.conf"
PROXY_SERVICE = WEB_ROOT / "deployment" / "systemd" / "madar-release-proxy.service"
CONTROL_UPGRADE = WEB_ROOT / "deployment" / "bin" / "madar-control-plane-upgrade"
CONTROL_UPGRADE_LIBRARY = WEB_ROOT / "deployment" / "lib" / "control_plane_upgrade.py"
CONTROL_GUARD = WEB_ROOT / "deployment" / "bin" / "madar-control-plane-guard"


class MonorepoDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.deploy = DEPLOY.read_text(encoding="utf-8")
        self.wrapper = WRAPPER.read_text(encoding="utf-8")
        self.compose = COMPOSE.read_text(encoding="utf-8")
        self.release_deploy = RELEASE_DEPLOY.read_text(encoding="utf-8")
        self.release_library = RELEASE_LIBRARY.read_text(encoding="utf-8")
        self.environment_library = ENVIRONMENT_LIBRARY.read_text(encoding="utf-8")
        self.switch = SWITCH.read_text(encoding="utf-8")
        self.proxy_compose = PROXY_COMPOSE.read_text(encoding="utf-8")
        self.proxy_config = PROXY_CONFIG.read_text(encoding="utf-8")
        self.release_compose = RELEASE_COMPOSE.read_text(encoding="utf-8")
        self.auto_service = AUTO_SERVICE.read_text(encoding="utf-8")
        self.auto_timer = AUTO_TIMER.read_text(encoding="utf-8")
        self.backend_dockerfile = BACKEND_DOCKERFILE.read_text(encoding="utf-8")
        self.frontend_dockerfile = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")
        self.installer = INSTALLER.read_text(encoding="utf-8")
        self.legacy_entrypoint = LEGACY_ENTRYPOINT.read_text(encoding="utf-8")
        self.path_contract = PATH_CONTRACT.read_text(encoding="utf-8")
        self.proxy_service = PROXY_SERVICE.read_text(encoding="utf-8")
        self.control_upgrade = CONTROL_UPGRADE.read_text(encoding="utf-8")
        self.control_upgrade_library = CONTROL_UPGRADE_LIBRARY.read_text(encoding="utf-8")
        self.control_guard = CONTROL_GUARD.read_text(encoding="utf-8")

    def test_wrapper_delegates_a_clean_full_sha_to_immutable_deployer(self):
        self.assertIn('MADAR_PRODUCTION_REPO:-/srv/madar/production', self.deploy)
        self.assertIn('git -C "$REPO_ROOT"', self.deploy)
        self.assertIn("status --porcelain --untracked-files=normal", self.deploy)
        self.assertIn('"$RELEASE_DEPLOY" "$TARGET_SHA"', self.deploy)
        self.assertIn('merge --ff-only "$TARGET_SHA"', self.deploy)
        self.assertIn(
            "/opt/madar/control-plane/deployment",
            self.deploy,
        )

    def test_release_deployer_uses_explicit_compose_and_environment_roots(self):
        self.assertIn('"MADAR_ENV_FILE": str(self.env_file)', self.release_deploy)
        self.assertIn('"docker", "compose", "--project-name", f"madar-{slot}"', self.release_deploy)
        self.assertIn('"--project-directory", str(web)', self.release_deploy)
        self.assertIn('"--env-file", str(self.env_file)', self.release_deploy)
        self.assertEqual(self.compose.count("${MADAR_ENV_FILE:-.env}"), 4)
        self.assertIn("candidate_image_identity_changed", self.release_deploy)
        self.assertIn("self._digest(tag)", self.release_deploy)
        self.assertIn("docker-compose.release.yml", self.release_deploy)
        self.assertIn('f"VITE_API_URL={frontend_api_url}"', self.release_deploy)
        self.assertIn("frontend_api_origin_missing_or_invalid", self.release_deploy)
        self.assertIn('f"madar-frontend:{sha}-{frontend_target}"', self.release_deploy)
        self.assertIn("com.madar.frontend.api_origin", self.release_deploy)
        self.assertIn("candidate_frontend_api_origin_mismatch", self.release_deploy)
        self.assertIn("self._validate_frontend_api_origin(frontend_base", self.release_deploy)
        self.assertIn('"--no-build", "--force-recreate", "--wait"', self.release_deploy)
        self.assertIn("MADAR_REQUIRE_PRODUCTION_API_URL", self.frontend_dockerfile)
        self.assertIn("MADAR_CANDIDATE_READY_ATTEMPTS", self.release_deploy)
        self.assertIn("candidate_deep_validation_failed:", self.release_deploy)
        self.assertIn('"DATA_DELETION_WORKER_HEALTH_URL": "http://data-deletion-worker:8094/health"', self.release_deploy)
        self.assertIn("DATA_DELETION_WORKER_HEALTH_URL: ${DATA_DELETION_WORKER_HEALTH_URL:-http://data-deletion-worker:8094/health}", self.compose)

    def test_release_slots_use_non_overlapping_explicit_ipam(self):
        self.assertIn('"blue": {', self.release_deploy)
        self.assertIn('"green": {', self.release_deploy)
        for variable in (
            "MADAR_DEFAULT_SUBNET",
            "MADAR_PARSER_SUBNET",
            "MADAR_REMOTE_INTERNAL_SUBNET",
            "MADAR_REMOTE_EGRESS_SUBNET",
        ):
            self.assertIn(variable, self.release_deploy)
            self.assertIn(variable, self.release_compose)
        self.assertIn("internal: true", self.release_compose)

    def test_rollback_switches_to_retained_target_without_rebuild_or_git_reset(self):
        combined = self.deploy + self.release_deploy + self.release_library
        self.assertNotIn("reset --hard", combined)
        self.assertIn("traffic_switch_to_retained_known_good", self.release_library)
        self.assertIn("previous_traffic_target", self.release_library)
        self.assertIn("@sha256:", self.release_library)
        self.assertIn("known_bad_release_suppressed", self.release_library)
        self.assertIn("/health/ready", self.release_deploy)
        self.assertIn("retained_worker_containers_missing", self.release_deploy)
        self.assertIn('["docker", "inspect", name]', self.release_deploy)

    def test_persistent_bind_mounts_keep_their_pre_move_host_paths(self):
        for path in (
            "${MADAR_STORAGE_ROOT:-./backend}/avatar_uploads",
            "${MADAR_STORAGE_ROOT:-./backend}/uploads",
            "${MADAR_STORAGE_ROOT:-./backend}/private_uploads",
            "${MADAR_STORAGE_ROOT:-./backend}/private_generated_charts",
        ):
            self.assertIn(path, self.compose)

    def test_compose_defaults_match_the_explicit_web_project_directory(self):
        self.assertEqual(COMPOSE.parent, WEB_ROOT)
        self.assertIn('"--project-directory", str(web)', self.release_deploy)
        self.assertNotIn("${MADAR_ENV_FILE:-../", self.compose)
        self.assertNotIn("${MADAR_STORAGE_ROOT:-../", self.compose)
        self.assertEqual((COMPOSE.parent / ".env").resolve(), WEB_ROOT / ".env")
        self.assertEqual((COMPOSE.parent / "backend").resolve(), WEB_ROOT / "backend")

    def test_wrapper_keeps_git_operations_at_repository_root(self):
        self.assertIn('git -C "$REPO_ROOT" fetch', self.wrapper)
        self.assertIn('exec "$DEPLOY_SCRIPT"', self.wrapper)
        self.assertIn(
            "/opt/madar/control-plane/deployment",
            self.wrapper,
        )

    def test_auto_deploy_suppresses_bad_sha_and_refuses_uninitialized_state(self):
        self.assertIn("failed_releases", self.wrapper)
        self.assertIn("remains suppressed", self.wrapper)
        self.assertIn("release state is not initialized", self.wrapper)
        self.assertIn('merge-base --is-ancestor "$KNOWN_GOOD" "$TARGET_SHA"', self.wrapper)
        self.assertIn('"$RELEASE_DEPLOY" "$TARGET_SHA" --automatic-migrate', self.wrapper)

    def test_auto_deploy_skips_only_deterministic_runtime_equivalent_commits(self):
        self.assertIn("RUNTIME_PATHS", self.wrapper)
        for path in (
            "web/backend",
            "web/frontend",
            "web/database",
            "web/supabase",
            "web/scripts",
            "web/docker-compose.yml",
            "web/deployment",
        ):
            self.assertIn(path, self.wrapper)
        self.assertIn('diff --quiet "$KNOWN_GOOD" "$TARGET_SHA"', self.wrapper)
        self.assertIn('"$RELEASE_DEPLOY" "$KNOWN_GOOD" --automatic-migrate', self.wrapper)
        self.assertIn('merge --ff-only "$TARGET_SHA"', self.wrapper)
        self.assertIn("Application-equivalent main advanced", self.wrapper)
        self.assertIn("production checkout contains local changes", self.wrapper)

    def test_timer_waits_after_completion_instead_of_retrying_immediately(self):
        self.assertIn("OnActiveSec=2min", self.auto_timer)
        self.assertIn("OnUnitInactiveSec=2min", self.auto_timer)
        self.assertIn("Persistent=true", self.auto_timer)
        self.assertNotIn("OnUnitActiveSec", self.auto_timer)
        self.assertNotIn("ExecStartPre", self.auto_service)

    def test_docker_proxy_is_hardened_and_preserves_forwarded_request_context(self):
        self.assertIn("MADAR_TRAFFIC_SWITCH_DRIVER=docker-nginx", self.auto_service)
        self.assertIn("WorkingDirectory=/srv/madar/production", self.auto_service)
        self.assertIn('driver not in {"nginx", "docker-nginx"}', self.switch)
        self.assertIn("network_mode: host", self.proxy_compose)
        self.assertIn("MADAR_PROXY_CONFIG_ROOT:-/var/lib/madar/proxy", self.proxy_compose)
        self.assertNotIn("MADAR_ACTIVE_UPSTREAMS_FILE:-", self.proxy_compose)
        self.assertIn(
            "MADAR_ACTIVE_UPSTREAMS_FILE=/var/lib/madar/proxy/active-upstreams.conf",
            self.path_contract,
        )
        self.assertIn(
            "MADAR_DEPLOY_STATE_ROOT=/var/lib/madar/releases",
            self.path_contract,
        )
        self.assertIn("stable_route_identity_not_observed", self.switch)
        self.assertIn("MADAR_STABLE_BACKEND_URL", self.switch)
        self.assertIn("_atomic_bytes(target, previous)", self.switch)
        self.assertIn("_reload(driver, container)", self.switch)
        self.assertIn("listen 127.0.0.1:8001", self.proxy_config)
        self.assertIn("listen 127.0.0.1:3000", self.proxy_config)
        self.assertIn('cap_drop: ["ALL"]', self.proxy_compose)
        self.assertIn("read_only: true", self.proxy_compose)
        self.assertIn("proxy_request_buffering off", self.proxy_config)
        self.assertIn("X-Forwarded-Proto $madar_forwarded_proto", self.proxy_config)
        self.assertIn("X-Forwarded-For $proxy_add_x_forwarded_for", self.proxy_config)

    def test_host_deployer_loads_secret_file_without_logging_values(self):
        self.assertIn("load_environment_file(env_file)", self.release_deploy)
        self.assertIn("permissions_too_broad", self.environment_library)
        self.assertNotIn("print(", self.environment_library)

    def test_operator_refresh_loads_paths_and_has_no_release_local_storage_fallback(self):
        for entrypoint in (self.deploy, self.wrapper):
            self.assertIn(
                'source "$TRACKED_CONTROL_ROOT/production-paths.conf"', entrypoint,
            )
        self.assertIn("load_production_path_contract()", self.release_deploy)
        self.assertIn("--refresh-active-runtime", self.release_deploy)
        self.assertIn("production_storage_root_not_configured", self.release_deploy)
        self.assertNotIn('str(self.repo / "backend")', self.release_deploy)
        self.assertIn("operations.preflight", self.release_deploy)
        self.assertIn("refresh_active_runtime_services", self.release_deploy)

    def test_initial_promotion_requires_prepared_candidate_before_state_adoption(self):
        self.assertIn("candidate_validated_workers_inactive", self.release_deploy)
        self.assertIn("prepared_release_workers_not_active", self.release_deploy)
        self.assertIn("stable_proxy_release_validation_failed", self.release_deploy)
        self.assertIn("immutable_release_state_already_initialized", self.release_deploy)

    def test_images_expose_release_sha_and_build_timestamp_as_oci_labels(self):
        for dockerfile in (self.backend_dockerfile, self.frontend_dockerfile):
            self.assertIn("org.opencontainers.image.revision=$MADAR_RELEASE_SHA", dockerfile)
            self.assertIn("org.opencontainers.image.created=$MADAR_BUILD_TIMESTAMP", dockerfile)

    def test_control_plane_installer_preserves_layout_and_does_not_start_timer(self):
        self.assertIn("install_root=\"$control_plane_root/deployment\"", self.installer)
        self.assertIn("control_plane_root=/opt/madar/control-plane", self.installer)
        self.assertIn("cp -a --", self.installer)
        self.assertIn("systemctl daemon-reload", self.installer)
        self.assertNotIn("systemctl start madar-auto-deploy.timer", self.installer)
        self.assertNotIn("systemctl enable", self.installer)
        self.assertIn("/home/madar/docker_auto.sh", self.installer)
        self.assertIn("/etc/systemd/system/madar-auto-deploy.service.d", self.installer)
        self.assertIn("SHA256SUMS", self.installer)
        self.assertIn("sha256sum", self.installer)
        self.assertIn("chown root:madar", self.installer)
        self.assertIn("chmod 0750", self.installer)
        self.assertIn("refusing installation while madar-auto-deploy.timer is enabled", self.installer)
        self.assertIn("refusing installation while madar-auto-deploy.service is active", self.installer)
        self.assertIn("backup directory must be outside current and legacy controller roots", self.installer)
        self.assertIn("rm -rf -- /etc/systemd/system/madar-auto-deploy.service.d", self.installer)
        self.assertIn("rm -f -- /home/madar/docker_auto.sh", self.installer)
        self.assertIn("rm -rf -- /usr/local/lib/madar/web/deployment", self.installer)
        self.assertIn("/var/lib/madar/releases/state.json", self.installer)
        self.assertIn("bin/madar-control-plane-upgrade", self.installer)
        self.assertIn("lib/control_plane_upgrade.py", self.installer)
        self.assertIn("/usr/local/sbin/madar-control-plane-upgrade", self.installer)
        self.assertIn("/var/lib/madar-control-plane/upgrades/history", self.installer)
        self.assertIn("/var/lib/madar-control-plane/backups", self.installer)

    def test_canonical_production_path_contract_is_single_and_complete(self):
        expected = {
            "MADAR_PRODUCTION_REPO": "/srv/madar/production",
            "MADAR_ENV_FILE": "/etc/madar/production.env",
            "MADAR_DEPLOY_STATE_ROOT": "/var/lib/madar/releases",
            "MADAR_STORAGE_ROOT": "/var/lib/madar/storage",
            "MADAR_ACTIVE_UPSTREAMS_FILE": "/var/lib/madar/proxy/active-upstreams.conf",
            "MADAR_PROXY_CONFIG_ROOT": "/var/lib/madar/proxy",
            "MADAR_CONTROL_PLANE_ROOT": "/opt/madar/control-plane/deployment",
            "MADAR_MIGRATION_BACKUP_SCRIPT": "/opt/madar/control-plane/deployment/scripts/backup_madar.sh",
            "MADAR_MIGRATION_BACKUP_VERIFY_SCRIPT": "/opt/madar/control-plane/deployment/scripts/verify_backup.sh",
            "MADAR_CANONICAL_GIT_REMOTE": "git@github.com:judahsleibi34/Madar.git",
        }
        assignments = dict(
            line.split("=", 1)
            for line in self.path_contract.splitlines()
            if line and not line.startswith("#")
        )
        for name, value in expected.items():
            self.assertEqual(assignments.get(name), value)
        self.assertIn(
            "EnvironmentFile=/opt/madar/control-plane/deployment/production-paths.conf",
            self.auto_service,
        )
        self.assertLess(
            self.auto_service.index("EnvironmentFile=/etc/madar/backup.env"),
            self.auto_service.index(
                "EnvironmentFile=/opt/madar/control-plane/deployment/production-paths.conf"
            ),
        )
        self.assertIn(
            "WorkingDirectory=/opt/madar/control-plane/deployment/proxy",
            self.proxy_service,
        )

    def test_privileged_upgrade_is_exact_sha_manual_and_fail_closed(self):
        self.assertTrue(self.control_upgrade.startswith("#!/usr/bin/python3 -I"))
        self.assertIn("os.environ.clear()", self.control_upgrade)
        self.assertIn("approved_sha_not_current_origin_main", self.control_upgrade_library)
        self.assertIn("candidate_not_descendant_of_production", self.control_upgrade_library)
        self.assertIn("canonical_git_remote_mismatch", self.control_upgrade_library)
        self.assertIn("candidate_protected_symlink_rejected", self.control_upgrade_library)
        self.assertIn("same_sha_cycle_mutated_release_state", self.control_upgrade_library)
        self.assertIn("post_promotion_forward_repair_timer_disabled", self.control_upgrade_library)
        self.assertIn("sudo madar-control-plane-upgrade ${target_sha}", self.control_guard)
        self.assertIn("LoadCredential=madar-control-plane-upgrade", self.control_upgrade_library)
        self.assertNotIn("authorized.credential", self.auto_service)

    def test_legacy_entrypoint_delegates_only_to_immutable_controller(self):
        self.assertIn("madar-production-deploy", self.legacy_entrypoint)
        self.assertIn("madar-release-deploy", self.legacy_entrypoint)
        self.assertIn("MADAR_DEPLOY_STATE_ROOT", self.legacy_entrypoint)
        self.assertIn('exec "$CONTROL_ROOT/bin/madar-auto-deploy"', self.legacy_entrypoint)
        self.assertNotIn("docker compose", self.legacy_entrypoint)
        self.assertNotIn("reset --hard", self.legacy_entrypoint)


if __name__ == "__main__":
    unittest.main()

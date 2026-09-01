import hashlib
import importlib.util
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from types import SimpleNamespace


WEB_ROOT = Path(
    os.getenv("MADAR_TEST_REPOSITORY_ROOT")
    or Path(__file__).resolve().parents[2]
).resolve()
MODULE_PATH = WEB_ROOT / "deployment/lib/control_plane_upgrade.py"
RELEASE_PATH = WEB_ROOT / "deployment/bin/madar-release-deploy"
WRAPPER_PATH = WEB_ROOT / "deployment/bin/madar-control-plane-upgrade"
SERVICE_PATH = WEB_ROOT / "deployment/systemd/madar-auto-deploy.service"
INSTALLER_PATH = WEB_ROOT / "deployment/bin/madar-install-control-plane"
MIGRATE_PATH = WEB_ROOT / "deployment/bin/madar-migrate"
SWITCH_PATH = WEB_ROOT / "deployment/bin/madar-switch-traffic"

spec = importlib.util.spec_from_file_location("control_plane_upgrade", MODULE_PATH)
upgrade = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = upgrade
spec.loader.exec_module(upgrade)
sys.path.insert(0, str(WEB_ROOT))
from deployment.lib.control_plane_upgrade_authorization import (  # noqa: E402
    require_upgrade_authorization,
)


class FakeOperations:
    def __init__(self, root, *, protected=True, failure=None):
        self.root = Path(root)
        self.backup_root = self.root / "backups"
        self.backup_root.mkdir()
        self.protected = protected
        self.failure = failure
        self.events = []
        self.installed = "1" * 40
        self.production = "1" * 40
        self.slot = "green"
        self.schema = 93
        self.timer = {"enabled": "enabled", "active": "active"}
        self.interlock = False
        self.snapshot = {"state": "unchanged"}

    def _event(self, name):
        self.events.append(name)
        if self.failure == name:
            raise upgrade.UpgradeError(f"failed:{name}")

    def current_preflight(self, *, lock_deployment=True):
        self._event("current_preflight")
        self.events.append(f"deployment_lock={lock_deployment}")
        return {
            "installed_sha": self.installed,
            "production_sha": self.production,
            "slot": self.slot,
            "schema": self.schema,
            "migration": "already_at_target",
            "timer": dict(self.timer),
        }

    def resolve_candidate(self, sha, *, dry_run):
        self._event("resolve_candidate")

    def protected_change_required(self, sha):
        self._event("protected_change_required")
        return self.protected

    def quiesce(self):
        self._event("quiesce")
        self.timer = {"enabled": "disabled", "active": "inactive"}

    def arm_interlock(self, sha):
        self._event("arm_interlock")
        self.interlock = True

    def release_deployment_lock(self):
        self._event("release_deployment_lock")

    def stage_candidate(self, sha):
        self._event("stage_candidate")
        transaction = self.root / "staging" / sha[:12]
        candidate = transaction / "repository"
        candidate.mkdir(parents=True)
        return transaction, candidate

    def static_preflight(self, candidate):
        self._event("static_preflight")
        return "digest"

    def installer_dry_run(self, candidate, backup):
        self._event("installer_dry_run")

    def protected_tree_digest(self, candidate):
        return "digest"

    def installer_apply(self, candidate, backup, sha):
        self._event("installer_apply")
        self.installed = sha

    def installed_sha(self):
        return self.installed

    def verify_install(self, sha, backup):
        self._event("verify_install")

    def run_deploy_service(self, label, sha):
        self._event(label)
        if label == "controlled_candidate_deployment":
            self.production = sha
            self.slot = "blue"

    def attest_serving(self, sha):
        self._event("attest_serving")
        if self.production != sha:
            raise upgrade.UpgradeError("not_promoted")
        return {
            "sha": sha,
            "slot": self.slot,
            "schema": self.schema,
            "migration": "already_at_target",
        }

    def known_good_identity(self, sha):
        if self.production == sha:
            return {"slot": self.slot, "schema": self.schema}
        return None

    def idempotence_snapshot(self, sha):
        return dict(self.snapshot)

    def restore_timer(self, original):
        self._event("restore_timer")
        self.timer = dict(original)
        return dict(self.timer)

    def disable_automation_for_failure(self):
        self.events.append("disable_automation_for_failure")
        self.timer = {"enabled": "disabled", "active": "inactive"}

    def clear_interlock(self):
        self.events.append("clear_interlock")
        self.interlock = False

    def clear_authorization(self):
        self.events.append("clear_authorization")

    def close_locks(self):
        self.events.append("close_locks")

    def cleanup_staging(self, transaction):
        self.events.append("cleanup_staging")

    def preinstall_restore_safe(self, previous_sha, production_sha):
        self.events.append("preinstall_restore_safe")
        return self.installed == previous_sha and self.production == production_sha


class ControlPlaneUpgradeTests(unittest.TestCase):
    SHA = "a" * 40

    def coordinator(self, root, *, protected=True, failure=None):
        operations = FakeOperations(root, protected=protected, failure=failure)
        record = upgrade.AuditRecord(approved_sha=self.SHA, dry_run=False)
        audit = upgrade.AuditWriter(Path(root) / "history", record)
        return operations, record, audit, upgrade.UpgradeCoordinator(operations, audit)

    def test_exact_sha_authorization_rejects_refs_and_abbreviations(self):
        self.assertEqual(upgrade.normalize_sha("A" * 40), "a" * 40)
        for invalid in (
            "a" * 39,
            "main",
            "refs/heads/main",
            "v1.0.0",
            "HEAD^{commit}",
            "a" * 40 + ";id",
            "../" + "a" * 40,
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(
                    upgrade.UpgradeError, "approved_sha_must_be_exact_40_hex"
                ):
                    upgrade.normalize_sha(invalid)

    def test_cli_requires_effective_root(self):
        with mock.patch.object(upgrade.os, "geteuid", return_value=1000):
            self.assertEqual(upgrade.main([self.SHA]), 1)

    def test_candidate_must_be_fresh_main_and_descend_from_production(self):
        operations = object.__new__(upgrade.SystemOperations)
        operations.repository_origin = mock.Mock(
            side_effect=[
                upgrade.EXPECTED_CONTRACT["MADAR_CANONICAL_GIT_REMOTE"],
                upgrade.EXPECTED_CONTRACT["MADAR_CANONICAL_GIT_REMOTE"],
            ]
        )
        operations.repository_head = mock.Mock(return_value="1" * 40)
        operations.require_clean_repository = mock.Mock()

        def git_result(label, *args, **kwargs):
            values = {
                "git_fetch_main": "",
                "git_verify_remote_main": f"{self.SHA}\trefs/heads/main",
                "git_resolve_main": self.SHA,
                "git_commit_type": "commit",
                "git_ancestry": "",
            }
            return upgrade.CommandResult(
                values[label], "", 0 if label != "git_ancestry" else 0
            )

        operations.madar_git = mock.Mock(side_effect=git_result)
        operations.resolve_candidate(self.SHA, dry_run=False)
        operations.require_clean_repository.assert_called_once()

        operations.repository_origin = mock.Mock(
            return_value=upgrade.EXPECTED_CONTRACT["MADAR_CANONICAL_GIT_REMOTE"]
        )

        def advanced_result(label, *args, **kwargs):
            if label == "git_verify_remote_main":
                return upgrade.CommandResult(
                    f"{'b' * 40}\trefs/heads/main", "", 0
                )
            return git_result(label, *args, **kwargs)

        operations.madar_git = mock.Mock(side_effect=advanced_result)
        with self.assertRaisesRegex(
            upgrade.UpgradeError, "origin_main_advanced_during_authorization"
        ):
            operations.resolve_candidate(self.SHA, dry_run=False)

        def divergent_result(label, *args, **kwargs):
            value = git_result(label, *args, **kwargs)
            if label == "git_ancestry":
                return upgrade.CommandResult("", "", 1)
            return value

        operations.madar_git = mock.Mock(side_effect=divergent_result)
        with self.assertRaisesRegex(
            upgrade.UpgradeError, "candidate_not_descendant_of_production"
        ):
            operations.resolve_candidate(self.SHA, dry_run=False)

    def test_wrong_canonical_remote_fails_before_fetch(self):
        operations = object.__new__(upgrade.SystemOperations)
        operations.repository_origin = mock.Mock(return_value="file:///tmp/evil")
        operations.madar_git = mock.Mock()
        with self.assertRaisesRegex(
            upgrade.UpgradeError, "canonical_git_remote_mismatch"
        ):
            operations.resolve_candidate(self.SHA, dry_run=False)
        operations.madar_git.assert_not_called()

    def test_active_container_images_must_match_recorded_immutable_ids(self):
        operations = object.__new__(upgrade.SystemOperations)
        backend_id = "sha256:" + "1" * 64
        frontend_id = "sha256:" + "2" * 64
        known = {
            "images": {
                "backend": f"madar-backend:{self.SHA}@{backend_id}",
                "frontend": f"madar-frontend:{self.SHA}@{frontend_id}",
                "worker": f"madar-backend:{self.SHA}@{backend_id}",
            }
        }

        def matching(label, args, **kwargs):
            container = args[-1]
            value = frontend_id if container.endswith("-frontend") else backend_id
            return upgrade.CommandResult(value, "", 0)

        operations.command = mock.Mock(side_effect=matching)
        operations.attest_active_images("green", known)
        self.assertEqual(operations.command.call_count, 7)

        operations.command = mock.Mock(
            return_value=upgrade.CommandResult("sha256:" + "9" * 64, "", 0)
        )
        with self.assertRaisesRegex(
            upgrade.UpgradeError, "running_image_identity_mismatch"
        ):
            operations.attest_active_images("green", known)

    def test_sanitized_environment_is_allowlisted(self):
        hostile = {
            "PYTHONPATH", "PYTHONHOME", "LD_PRELOAD", "LD_LIBRARY_PATH",
            "GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG_COUNT", "DOCKER_HOST",
            "COMPOSE_FILE", "COMPOSE_PROJECT_NAME", "MADAR_STORAGE_ROOT",
        }
        environment = upgrade.sanitized_environment()
        self.assertFalse(hostile & set(environment))
        self.assertEqual(environment["PATH"], "/usr/sbin:/usr/bin:/sbin:/bin")
        wrapper = WRAPPER_PATH.read_text(encoding="utf-8")
        self.assertTrue(wrapper.startswith("#!/usr/bin/python3 -I"))
        self.assertIn("os.environ.clear()", wrapper)

    def test_success_runs_bridge_then_same_sha_before_timer_restore(self):
        with tempfile.TemporaryDirectory() as root:
            operations, record, audit, coordinator = self.coordinator(root)
            coordinator.execute(dry_run=False)
            coordinator.cleanup()
        self.assertTrue(coordinator.success)
        self.assertEqual(record.status, "success")
        self.assertEqual(record.migration_result, "already_at_target")
        self.assertIn("deployment_lock=True", operations.events)
        self.assertEqual(record.same_sha_validation, "passed")
        self.assertLess(
            operations.events.index("controlled_candidate_deployment"),
            operations.events.index("same_sha_idempotence"),
        )
        self.assertLess(
            operations.events.index("same_sha_idempotence"),
            operations.events.index("restore_timer"),
        )
        self.assertEqual(operations.timer, {"enabled": "enabled", "active": "active"})
        self.assertFalse(operations.interlock)

    def test_initially_disabled_timer_remains_disabled_after_success(self):
        with tempfile.TemporaryDirectory() as root:
            operations, record, audit, coordinator = self.coordinator(root)
            operations.timer = {"enabled": "disabled", "active": "inactive"}
            coordinator.execute(dry_run=False)
            coordinator.cleanup()
        self.assertEqual(
            operations.timer, {"enabled": "disabled", "active": "inactive"}
        )

    def test_dry_run_stages_and_validates_without_quiesce_or_install(self):
        with tempfile.TemporaryDirectory() as root:
            operations, record, audit, coordinator = self.coordinator(root)
            coordinator.execute(dry_run=True)
            coordinator.cleanup()
        self.assertEqual(record.status, "dry_run_complete")
        self.assertIn("deployment_lock=False", operations.events)
        self.assertIn("installer_dry_run", operations.events)
        for forbidden in (
            "quiesce", "installer_apply", "controlled_candidate_deployment",
            "same_sha_idempotence", "restore_timer",
        ):
            self.assertNotIn(forbidden, operations.events)

    def test_non_protected_release_exits_without_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            operations, record, audit, coordinator = self.coordinator(
                root, protected=False
            )
            coordinator.execute(dry_run=False)
            coordinator.cleanup()
        self.assertEqual(record.status, "not_required")
        self.assertNotIn("quiesce", operations.events)
        self.assertNotIn("installer_apply", operations.events)

    def test_preinstall_failure_restores_original_timer_only_after_attestation(self):
        with tempfile.TemporaryDirectory() as root:
            operations, record, audit, coordinator = self.coordinator(
                root, failure="installer_dry_run"
            )
            with self.assertRaises(upgrade.UpgradeError) as raised:
                coordinator.execute(dry_run=False)
            coordinator.handle_failure(raised.exception)
            coordinator.cleanup()
        self.assertEqual(record.failure_semantics, "pre_install_production_untouched")
        self.assertIn("preinstall_restore_safe", operations.events)
        self.assertIn("restore_timer", operations.events)
        self.assertFalse(operations.interlock)

    def test_postinstall_failure_keeps_timer_disabled_without_old_restore(self):
        with tempfile.TemporaryDirectory() as root:
            operations, record, audit, coordinator = self.coordinator(
                root, failure="verify_install"
            )
            with self.assertRaises(upgrade.UpgradeError) as raised:
                coordinator.execute(dry_run=False)
            coordinator.handle_failure(raised.exception)
            coordinator.cleanup()
        self.assertTrue(record.controller_installed)
        self.assertEqual(
            record.failure_semantics,
            "post_install_manual_intervention_timer_disabled",
        )
        self.assertNotIn("restore_timer", operations.events)
        self.assertTrue(operations.interlock)

    def test_postpromotion_failure_is_forward_repair_and_never_restores_timer(self):
        with tempfile.TemporaryDirectory() as root:
            operations, record, audit, coordinator = self.coordinator(
                root, failure="same_sha_idempotence"
            )
            with self.assertRaises(upgrade.UpgradeError) as raised:
                coordinator.execute(dry_run=False)
            coordinator.handle_failure(raised.exception)
            coordinator.cleanup()
        self.assertTrue(record.application_promoted)
        self.assertEqual(
            record.failure_semantics,
            "post_promotion_forward_repair_timer_disabled",
        )
        self.assertNotIn("restore_timer", operations.events)
        self.assertTrue(operations.interlock)

    def test_timer_restore_failure_requiesces_and_rearms_interlock(self):
        with tempfile.TemporaryDirectory() as root:
            operations, record, audit, coordinator = self.coordinator(
                root, failure="restore_timer"
            )
            with self.assertRaises(upgrade.UpgradeError) as raised:
                coordinator.execute(dry_run=False)
            coordinator.handle_failure(raised.exception)
            coordinator.cleanup()
        self.assertTrue(record.application_promoted)
        self.assertIn("disable_automation_for_failure", operations.events)
        self.assertEqual(
            operations.timer, {"enabled": "disabled", "active": "inactive"}
        )
        self.assertTrue(operations.interlock)

    def test_interlock_requires_exact_sha_and_one_time_secret(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "in-progress.json"
            token = "opaque-one-time-token"
            marker.write_text(json.dumps({
                "approved_sha": self.SHA,
                "authorization_sha256": hashlib.sha256(token.encode()).hexdigest(),
            }), encoding="utf-8")
            marker.chmod(0o644)
            credentials = Path(root) / "credentials"
            credentials.mkdir()
            credential = credentials / "madar-control-plane-upgrade"
            credential.write_text(json.dumps({
                "approved_sha": self.SHA,
                "token": token,
            }), encoding="utf-8")
            root_stat = SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o644)
            environment = {
                "CREDENTIALS_DIRECTORY": str(credentials),
            }
            with mock.patch.object(Path, "stat", return_value=root_stat):
                with mock.patch.dict(os.environ, environment, clear=True):
                    require_upgrade_authorization(self.SHA, interlock=marker)
                with mock.patch.dict(os.environ, {}, clear=True):
                    with self.assertRaisesRegex(
                        RuntimeError, "control_plane_upgrade_exclusive_interlock"
                    ):
                        require_upgrade_authorization(self.SHA, interlock=marker)
                credential.write_text(json.dumps({
                    "approved_sha": "b" * 40,
                    "token": token,
                }), encoding="utf-8")
                with mock.patch.dict(os.environ, environment, clear=True):
                    with self.assertRaisesRegex(
                        RuntimeError, "control_plane_upgrade_exclusive_interlock"
                    ):
                        require_upgrade_authorization(self.SHA, interlock=marker)
                credential.write_text(json.dumps({
                    "approved_sha": self.SHA,
                    "token": "substituted-token",
                }), encoding="utf-8")
                with mock.patch.dict(os.environ, environment, clear=True):
                    with self.assertRaisesRegex(
                        RuntimeError, "control_plane_upgrade_exclusive_interlock"
                    ):
                        require_upgrade_authorization(self.SHA, interlock=marker)

    def test_interlock_rejects_symlink_and_writable_state(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "target.json"
            target.write_text("{}", encoding="utf-8")
            link = Path(root) / "in-progress.json"
            link.symlink_to(target)
            with self.assertRaisesRegex(
                RuntimeError, "control_plane_upgrade_interlock_invalid"
            ):
                require_upgrade_authorization(self.SHA, interlock=link)

            writable = Path(root) / "writable.json"
            writable.write_text("{}", encoding="utf-8")
            root_stat = SimpleNamespace(
                st_uid=0, st_mode=stat.S_IFREG | 0o666
            )
            with mock.patch.object(Path, "stat", return_value=root_stat):
                with self.assertRaisesRegex(
                    RuntimeError, "control_plane_upgrade_interlock_invalid"
                ):
                    require_upgrade_authorization(
                        self.SHA, interlock=writable
                    )

    def test_installer_and_service_define_self_update_and_authorization_boundary(self):
        installer = INSTALLER_PATH.read_text(encoding="utf-8")
        service = SERVICE_PATH.read_text(encoding="utf-8")
        self.assertIn("bin/madar-control-plane-upgrade", installer)
        self.assertIn("lib/control_plane_upgrade.py", installer)
        self.assertIn("/usr/local/sbin/madar-control-plane-upgrade", installer)
        self.assertIn("RENAME_EXCHANGE = 2", installer)
        self.assertNotIn('rm -rf -- "$install_root"', installer)
        self.assertLess(
            installer.index("RENAME_EXCHANGE = 2"),
            installer.index('"$install_root/bin/madar-control-plane-upgrade"'),
        )
        self.assertLess(
            installer.index('mv -T -- "$stage_root" "$install_root"'),
            installer.index("next-invocation bootstrap wrapper"),
        )
        self.assertNotIn("authorized.credential", service)
        self.assertIn(
            "LoadCredential=madar-control-plane-upgrade",
            MODULE_PATH.read_text(encoding="utf-8"),
        )

    def test_authorized_cycle_uses_hardened_transient_unit_not_secret_environment(self):
        operations = object.__new__(upgrade.SystemOperations)
        operations.repo = Path("/srv/madar/production")
        operations.control_root = Path("/opt/madar/control-plane/deployment")
        operations.contract_path = operations.control_root / "production-paths.conf"
        operations.authorization_file = Path(
            "/run/madar/control-plane-upgrade/authorized.credential"
        )
        operations.audit = None
        operations.write_authorization = mock.Mock()
        operations.clear_authorization = mock.Mock()
        calls = []

        def command(label, args, **kwargs):
            calls.append((label, args, kwargs))
            return upgrade.CommandResult("", "", 0)

        operations.command = mock.Mock(side_effect=command)
        operations.run_deploy_service("same_sha_idempotence", self.SHA)
        invocation = calls[0][1]
        joined = " ".join(invocation)
        self.assertEqual(invocation[0], "/usr/bin/systemd-run")
        self.assertIn("--uid=madar", invocation)
        self.assertIn("--gid=madar", invocation)
        self.assertIn("--property=NoNewPrivileges=yes", invocation)
        self.assertIn("--property=TimeoutStartSec=45min", invocation)
        self.assertIn("--property=LoadCredential=madar-control-plane-upgrade:", joined)
        self.assertNotIn("MADAR_CONTROL_PLANE_UPGRADE_TOKEN=", joined)
        self.assertNotIn("SUPABASE_SERVICE_KEY", joined)

    def test_lock_rejects_a_second_concurrent_holder(self):
        with tempfile.TemporaryDirectory() as root:
            lock = Path(root) / "upgrade.lock"
            first = upgrade.acquire_lock(lock, create=True)
            try:
                with self.assertRaisesRegex(
                    upgrade.UpgradeError, "exclusive_lock_unavailable"
                ):
                    upgrade.acquire_lock(lock, create=True)
            finally:
                os.close(first)

    def test_interlock_also_covers_manual_migration_and_traffic_switch(self):
        migrate = MIGRATE_PATH.read_text(encoding="utf-8")
        switch = SWITCH_PATH.read_text(encoding="utf-8")
        self.assertIn("require_upgrade_authorization(None)", migrate)
        self.assertIn("require_upgrade_authorization(None)", switch)

    def test_audit_is_private_atomic_and_redacts_secret_assignments(self):
        with tempfile.TemporaryDirectory() as root:
            record = upgrade.AuditRecord(approved_sha=self.SHA, dry_run=False)
            audit = upgrade.AuditWriter(Path(root) / "history", record)
            audit.log("SUPABASE_SERVICE_KEY=do-not-record VAPID_PRIVATE_KEY=hidden")
            logged = audit.log_path.read_text(encoding="utf-8")
            payload = json.loads(audit.json_path.read_text(encoding="utf-8"))
            self.assertNotIn("do-not-record", logged)
            self.assertNotIn("hidden", logged)
            self.assertEqual(payload["approved_sha"], self.SHA)
            self.assertEqual(stat.S_IMODE(audit.log_path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(audit.json_path.stat().st_mode), 0o600)

    def test_staging_cleanup_rejects_path_outside_transaction_root(self):
        operations = object.__new__(upgrade.SystemOperations)
        with tempfile.TemporaryDirectory() as root:
            operations.staging_root = Path(root) / "staging"
            operations.staging_root.mkdir()
            outside = Path(root) / "outside"
            outside.mkdir()
            with self.assertRaisesRegex(
                upgrade.UpgradeError, "staging_cleanup_scope_invalid"
            ):
                operations.cleanup_staging(outside)

    def test_protected_tree_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as root:
            candidate = Path(root)
            deployment = candidate / "web/deployment"
            scripts = candidate / "web/scripts"
            deployment.mkdir(parents=True)
            scripts.mkdir(parents=True)
            (deployment / "safe").write_text("safe", encoding="utf-8")
            for name in (
                "madar_alert_hook.sh", "backup_madar.sh", "verify_backup.sh"
            ):
                (scripts / name).write_text("safe", encoding="utf-8")
            (deployment / "escape").symlink_to("/etc/passwd")
            with self.assertRaisesRegex(
                upgrade.UpgradeError, "candidate_protected_symlink_rejected"
            ):
                upgrade.SystemOperations.protected_tree_digest(candidate)


if __name__ == "__main__":
    unittest.main()

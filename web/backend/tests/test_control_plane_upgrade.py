import hashlib
import importlib.util
import contextlib
import errno
import io
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
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
import control_plane_filesystem as filesystem  # noqa: E402


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
        self.controller_compatibility = "normal_compatible"
        self.recovery = False

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

    def current_recovery_preflight(self, *, candidate_sha=None, lock_deployment=True):
        self._event("current_recovery_preflight")
        self.events.append(f"deployment_lock={lock_deployment}")
        return {
            "installed_sha": self.installed,
            "production_sha": self.production,
            "slot": self.slot,
            "schema": 96,
            "migration": "out_of_band_schema_ahead",
            "timer": {"enabled": "disabled", "active": "inactive"},
        }

    def resolve_candidate(self, sha, *, dry_run):
        self._event("resolve_candidate")

    def validate_controller_compatibility(self, sha, current):
        self._event("validate_controller_compatibility")
        return self.controller_compatibility

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

    def validate_rehearsal_attestation(self, path, sha, schema):
        self._event("validate_rehearsal_attestation")
        self.events.append(f"attestation:{path.name}:{sha}:{schema}")
        return "a" * 64

    def validate_recovery_candidate_contract(self, candidate, schema):
        self._event("validate_recovery_candidate_contract")
        self.events.append(f"recovery_contract:{schema}")

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

    def verify_installed_controller(self, sha):
        self._event("verify_installed_controller")
        if self.installed != sha:
            raise upgrade.UpgradeError("installed_provenance_mismatch")

    def run_deploy_service(self, label, sha, *, recovery=False):
        self._event(label)
        self.events.append(f"recovery={recovery}")
        if label == "controlled_candidate_deployment":
            self.production = sha
            self.slot = "blue"
            self.recovery = recovery
            if recovery:
                self.schema = 96

    def advance_production_checkout(self, sha):
        self._event("advance_production_checkout")
        self.production = sha

    def attest_serving(self, sha, *, recovery=False):
        self._event("attest_serving")
        if self.production != sha:
            raise upgrade.UpgradeError("not_promoted")
        return {
            "sha": sha,
            "slot": self.slot,
            "schema": self.schema,
            "migration": "not_requested" if recovery else "already_at_target",
        }

    def known_good_identity(self, sha):
        if self.production == sha and not self.recovery:
            return {"slot": self.slot, "schema": self.schema}
        return None

    def recovery_traffic_identity(self, sha):
        self.events.append("recovery_traffic_identity")
        if self.production == sha:
            return {"slot": self.slot, "schema": 96}
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

    @staticmethod
    def real_git(*args, cwd=None, check=True, environment=None):
        safe_environment = dict(os.environ)
        safe_environment.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL="/dev/null",
            GIT_TERMINAL_PROMPT="0",
            GIT_NO_REPLACE_OBJECTS="1",
        )
        if environment:
            safe_environment.update(environment)
        return subprocess.run(
            ["/usr/bin/git", *map(str, args)],
            cwd=cwd,
            env=safe_environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def real_bundle_source(self, root, *, replacement=False):
        source = Path(root) / "source"
        self.real_git("init", "--quiet", "--template=", source)
        self.real_git("-C", source, "config", "user.name", "Madar test")
        self.real_git("-C", source, "config", "user.email", "madar@test.invalid")
        payload = source / "payload.txt"
        payload.write_text("approved\n", encoding="utf-8")
        self.real_git("-C", source, "add", "payload.txt")
        self.real_git("-C", source, "commit", "--quiet", "-m", "approved")
        approved = self.real_git("-C", source, "rev-parse", "HEAD").stdout.strip()
        if replacement:
            payload.write_text("replacement\n", encoding="utf-8")
            self.real_git("-C", source, "commit", "--quiet", "-am", "replacement")
            replacement_sha = self.real_git(
                "-C", source, "rev-parse", "HEAD"
            ).stdout.strip()
            # This hostile local replacement must not affect bundle creation
            # or staged object identity.
            self.real_git(
                "-C", source, "replace", approved, replacement_sha
            )
        self.real_git(
            "-C", source, "update-ref", "refs/remotes/origin/main", approved
        )
        return source, approved

    def static_preflight_candidate(self, root):
        fixture_root = Path(root)
        candidate = fixture_root / "candidate"
        shutil.copytree(
            WEB_ROOT / "deployment",
            candidate / "web/deployment",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        )
        scripts = candidate / "web/scripts"
        scripts.mkdir(parents=True)
        for name in (
            "madar_alert_hook.sh", "backup_madar.sh", "verify_backup.sh",
            "backup_support.py", "verify_latest_backup.sh", "replicate_latest_node1.py",
            "replicate_latest_offhost.sh", "replicate_backup_offhost.sh",
            "restore_madar.sh", "rehearse_backup.py",
        ):
            shutil.copy2(WEB_ROOT / "scripts" / name, scripts / name)

        operations = object.__new__(upgrade.SystemOperations)
        operations.audit = None
        operations.contract = dict(upgrade.EXPECTED_CONTRACT)
        operations.staging_root = fixture_root / "staging"
        operations.backup_root = fixture_root / "backups"
        operations.staging_root.mkdir()
        operations.backup_root.mkdir()
        return operations, candidate

    def run_static_preflight(self, operations, candidate):
        capacity = SimpleNamespace(free=2 * 1024 * 1024 * 1024)
        with (
            mock.patch.object(
                upgrade, "parse_contract", return_value=operations.contract
            ),
            mock.patch.object(upgrade.shutil, "disk_usage", return_value=capacity),
        ):
            return operations.static_preflight(candidate)

    @staticmethod
    def real_stage_operations(source, staging):
        operations = object.__new__(upgrade.SystemOperations)
        operations.audit = None
        operations.repo = Path(source)
        operations.staging_root = Path(staging)
        operations.staging_root.mkdir()
        operations.prepare_upgrade_roots = mock.Mock()
        return operations

    def coordinator(self, root, *, protected=True, failure=None):
        operations = FakeOperations(root, protected=protected, failure=failure)
        record = upgrade.AuditRecord(approved_sha=self.SHA, dry_run=False)
        audit = upgrade.AuditWriter(Path(root) / "history", record)
        return operations, record, audit, upgrade.UpgradeCoordinator(operations, audit)

    def compatibility_operations(
        self,
        *,
        production,
        installed,
        approved,
        current_guard=1,
        protected_delta=1,
        resolved=None,
        ancestry=0,
        approved_guard=0,
    ):
        operations = object.__new__(upgrade.SystemOperations)
        operations.control_root = Path("/opt/madar/control-plane/deployment")
        operations.repository_origin = mock.Mock(
            return_value=upgrade.EXPECTED_CONTRACT["MADAR_CANONICAL_GIT_REMOTE"]
        )
        operations.require_clean_repository = mock.Mock()

        def command(label, args, check=True, **_kwargs):
            returncode = {
                "guard_current": current_guard,
                "guard_approved_bridge": approved_guard,
            }.get(label, 0)
            if check and returncode:
                raise upgrade.UpgradeError(f"command_failed:{label}")
            return upgrade.CommandResult("", "", returncode)

        def madar_git(label, *args, **_kwargs):
            if label == "git_current_controller_delta":
                return upgrade.CommandResult("", "", protected_delta)
            if label == "git_bridge_resolve_main":
                return upgrade.CommandResult(resolved or approved, "", 0)
            if label in {
                "git_bridge_production_type", "git_bridge_installed_type",
            }:
                return upgrade.CommandResult("commit", "", 0)
            if label == "git_bridge_ancestry":
                return upgrade.CommandResult("", "", ancestry)
            raise AssertionError(f"unexpected Git operation: {label} {args}")

        operations.command = mock.Mock(side_effect=command)
        operations.madar_git = mock.Mock(side_effect=madar_git)
        current = {"production_sha": production, "installed_sha": installed}
        return operations, current

    def filesystem_layout(self, root):
        trust_root = Path(root)
        trust_root.chmod(0o700)
        source_root = trust_root / "candidate/repository"
        control_root = trust_root / "opt/madar/control-plane"
        install_root = control_root / "deployment"
        launcher_parent = trust_root / "usr/local/sbin"
        alert_parent = trust_root / "usr/local/lib/madar"
        systemd_parent = trust_root / "etc/systemd/system"
        for path in (
            source_root, install_root, launcher_parent, alert_parent,
            systemd_parent, trust_root / "var/lib",
        ):
            path.mkdir(parents=True, exist_ok=True)
        for path in trust_root.rglob("*"):
            if path.is_dir():
                path.chmod(0o755)
        return filesystem.InstallFilesystemLayout(
            source_root=source_root,
            backup_root=(
                trust_root / "var/lib/madar-control-plane/backups/pre-candidate"
            ),
            control_plane_root=control_root,
            install_root=install_root,
            launcher_parent=launcher_parent,
            alert_parent=alert_parent,
            systemd_parent=systemd_parent,
            state_root=trust_root / "var/lib/madar-control-plane",
            expected_uid=os.getuid(),
            rename_scratch_root=source_root.parent,
            trust_root=trust_root,
        )

    @staticmethod
    def acl_value(*entries):
        return struct.pack("<I", filesystem.ACL_XATTR_VERSION) + b"".join(
            struct.pack("<HHI", *entry) for entry in entries
        )

    def test_standard_root_owned_0755_parent_is_root_protected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "var-lib"
            path.mkdir(mode=0o755)
            filesystem.require_root_protected_directory(
                path, expected_uid=os.getuid()
            )

    def test_group_world_and_non_owner_writable_parents_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "parent"
            path.mkdir()
            for mode in (0o775, 0o757):
                with self.subTest(mode=oct(mode)):
                    path.chmod(mode)
                    with self.assertRaisesRegex(
                        filesystem.FilesystemPreflightError,
                        "root_protected_directory_invalid",
                    ):
                        filesystem.require_root_protected_directory(
                            path, expected_uid=os.getuid()
                        )
            metadata = SimpleNamespace(
                st_uid=os.getuid() + 1, st_mode=stat.S_IFDIR | 0o755
            )
            with mock.patch.object(Path, "lstat", return_value=metadata):
                with self.assertRaisesRegex(
                    filesystem.FilesystemPreflightError,
                    "root_protected_directory_invalid",
                ):
                    filesystem.require_root_protected_directory(
                        path, expected_uid=os.getuid()
                    )

    def test_unsafe_acl_write_grant_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "parent"
            path.mkdir(mode=0o755)
            acl = self.acl_value(
                (filesystem.ACL_USER_OBJ, 0o7, 0xFFFFFFFF),
                (filesystem.ACL_USER, 0o2, os.getuid() + 1),
                (filesystem.ACL_GROUP_OBJ, 0o5, 0xFFFFFFFF),
                (filesystem.ACL_MASK, 0o7, 0xFFFFFFFF),
                (filesystem.ACL_OTHER, 0o5, 0xFFFFFFFF),
            )

            def getxattr(_path, name, **_kwargs):
                if name == "system.posix_acl_access":
                    return acl
                raise OSError(errno.ENODATA, "no attribute")

            with mock.patch.object(filesystem.os, "getxattr", side_effect=getxattr):
                with self.assertRaisesRegex(
                    filesystem.FilesystemPreflightError,
                    "root_protected_acl_write_grant",
                ):
                    filesystem.require_root_protected_directory(
                        path, expected_uid=os.getuid()
                    )

    def test_symlink_parent_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            trust_root = Path(root)
            real = trust_root / "real"
            real.mkdir()
            link = trust_root / "linked"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaisesRegex(
                filesystem.FilesystemPreflightError,
                "root_protected_directory_invalid",
            ):
                filesystem.require_root_protected_ancestry(
                    link,
                    expected_uid=os.getuid(),
                    trust_root=trust_root,
                )

    def test_dry_run_and_apply_share_unchanged_filesystem_preflight(self):
        with tempfile.TemporaryDirectory() as root:
            layout = self.filesystem_layout(root)
            filesystem.validate_installation_filesystem(layout)
            # Apply re-runs the identical static contract. With no external
            # change, a successful dry-run remains successful.
            filesystem.validate_installation_filesystem(layout)
            for path in layout.state_directories:
                path.mkdir(mode=0o700, parents=True, exist_ok=True)
                path.chmod(0o700)
            filesystem.validate_installation_filesystem(layout)
            for path in layout.state_directories:
                self.assertEqual(path.stat().st_uid, os.getuid())
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)

        installer = INSTALLER_PATH.read_text(encoding="utf-8")
        shared = 'control_plane_filesystem.py"'
        self.assertIn(shared, installer)
        dry_run_boundary = installer.index("if (( ! apply ))")
        first_mutation = installer.index("# Establish only the installer-owned")
        for static_check in (
            shared,
            "for required in",
            'source_sha="$(git -C',
            '[[ -f "$alert_hook_source"',
            "systemctl is-active --quiet madar-auto-deploy.timer",
            "control-plane backup directory must be empty",
        ):
            self.assertLess(installer.index(static_check), dry_run_boundary)
            self.assertLess(installer.index(static_check), first_mutation)
        self.assertLess(
            installer.index(shared),
            installer.index('install -d -m 0700 "$backup_root"'),
        )

    def test_launcher_backup_and_state_parents_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            layout = self.filesystem_layout(root)
            layout.launcher_parent.chmod(0o775)
            with self.assertRaisesRegex(
                filesystem.FilesystemPreflightError,
                "root_protected_directory_invalid",
            ):
                filesystem.validate_installation_filesystem(layout)

        with tempfile.TemporaryDirectory() as root:
            layout = self.filesystem_layout(root)
            launcher = layout.launcher_parent / "madar-control-plane-upgrade"
            launcher.symlink_to("/tmp/untrusted-launcher")
            with self.assertRaisesRegex(
                filesystem.FilesystemPreflightError,
                "root_protected_file_invalid",
            ):
                filesystem.validate_installation_filesystem(layout)

        with tempfile.TemporaryDirectory() as root:
            layout = self.filesystem_layout(root)
            external_backup = Path(root) / "var/lib/external-backups"
            external_backup.mkdir()
            external_backup.chmod(0o777)
            layout = replace(
                layout, backup_root=external_backup / "pre-candidate"
            )
            with self.assertRaisesRegex(
                filesystem.FilesystemPreflightError,
                "root_protected_directory_invalid",
            ):
                filesystem.validate_installation_filesystem(layout)

        with tempfile.TemporaryDirectory() as root:
            layout = self.filesystem_layout(root)
            layout.state_root.mkdir(mode=0o755)
            with self.assertRaisesRegex(
                filesystem.FilesystemPreflightError,
                "root_protected_directory_mode_invalid",
            ):
                filesystem.validate_installation_filesystem(layout)

    def test_static_parent_rejection_precedes_all_install_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            layout = self.filesystem_layout(root)
            sentinel = layout.install_root / "CONTROL_PLANE_SOURCE_SHA"
            sentinel.write_text("old-controller", encoding="ascii")
            layout.control_plane_root.chmod(0o775)
            with mock.patch.object(filesystem, "require_rename_exchange") as exchange:
                with self.assertRaisesRegex(
                    filesystem.FilesystemPreflightError,
                    "root_protected_directory_invalid",
                ):
                    filesystem.validate_installation_filesystem(layout)
            exchange.assert_not_called()
            self.assertEqual(sentinel.read_text(encoding="ascii"), "old-controller")
            self.assertFalse(layout.backup_root.exists())
            self.assertFalse(layout.state_root.exists())

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
        stderr = io.StringIO()
        with (
            mock.patch.object(upgrade.os, "geteuid", return_value=1000),
            contextlib.redirect_stderr(stderr),
        ):
            self.assertEqual(upgrade.main([self.SHA]), 1)
        self.assertIn("effective_root_required", stderr.getvalue())

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

    def test_real_remote_tracking_bundle_stages_exact_detached_candidate(self):
        with tempfile.TemporaryDirectory() as root:
            source, approved = self.real_bundle_source(root)
            source_refs = self.real_git("-C", source, "show-ref").stdout
            source_status = self.real_git(
                "-C", source, "status", "--porcelain", "--untracked-files=normal"
            ).stdout

            # Reproduce the exact failed topology: clone does not import a
            # bundle whose only advertised name is a remote-tracking ref.
            proof_bundle = Path(root) / "proof.bundle"
            self.real_git(
                "-C", source, "bundle", "create", proof_bundle,
                "refs/remotes/origin/main",
            )
            advertised = self.real_git(
                "bundle", "list-heads", proof_bundle
            ).stdout.strip()
            self.assertEqual(
                advertised, f"{approved} refs/remotes/origin/main"
            )
            old_clone = Path(root) / "old-clone"
            clone = self.real_git(
                "-c", "protocol.file.allow=always", "clone", "--no-checkout",
                proof_bundle, old_clone, check=False,
            )
            self.assertEqual(clone.returncode, 0)
            self.assertIn("cloned an empty repository", clone.stderr)
            old_checkout = self.real_git(
                "-C", old_clone, "checkout", "--detach", approved, check=False
            )
            self.assertNotEqual(old_checkout.returncode, 0)
            self.assertTrue(
                "unable to read tree" in old_checkout.stderr
                or "reference is not a tree" in old_checkout.stderr
            )

            operations = self.real_stage_operations(
                source, Path(root) / "staging"
            )
            real_command = operations.command
            staging_commands = []

            def record_command(label, args, **kwargs):
                staging_commands.append((label, list(args)))
                return real_command(label, args, **kwargs)

            operations.command = record_command
            transaction, candidate = operations.stage_candidate(approved)
            self.assertEqual(
                self.real_git("-C", candidate, "rev-parse", "HEAD").stdout.strip(),
                approved,
            )
            detached = self.real_git(
                "-C", candidate, "symbolic-ref", "-q", "HEAD", check=False
            )
            self.assertNotEqual(detached.returncode, 0)
            self.assertEqual(
                self.real_git(
                    "-C", candidate, "status", "--porcelain",
                    "--untracked-files=normal",
                ).stdout,
                "",
            )
            self.assertEqual(
                self.real_git(
                    "-C", candidate, "for-each-ref", "--format=%(refname)"
                ).stdout,
                "",
            )
            self.assertEqual(self.real_git("-C", candidate, "remote").stdout, "")
            self.assertFalse((candidate / ".git/hooks").exists())
            fetch_command = dict(staging_commands)["git_fetch_bundle"]
            self.assertIn("protocol.allow=never", fetch_command)
            self.assertIn("protocol.file.allow=always", fetch_command)
            self.assertIn(str(transaction / "candidate.bundle"), fetch_command)
            self.assertFalse(
                any(
                    value.startswith(("http:", "https:", "ssh:", "git:"))
                    for value in fetch_command
                )
            )
            self.assertEqual(self.real_git("-C", source, "show-ref").stdout, source_refs)
            self.assertEqual(
                self.real_git(
                    "-C", source, "status", "--porcelain",
                    "--untracked-files=normal",
                ).stdout,
                source_status,
            )
            operations.cleanup_staging(transaction)
            self.assertFalse(transaction.exists())

    def test_real_bundle_staging_ignores_replacements_and_hostile_templates(self):
        with tempfile.TemporaryDirectory() as root:
            source, approved = self.real_bundle_source(root, replacement=True)
            hostile_template = Path(root) / "hostile-template"
            hooks = hostile_template / "hooks"
            hooks.mkdir(parents=True)
            marker = Path(root) / "hook-executed"
            hook = hooks / "post-checkout"
            hook.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
            hook.chmod(0o755)
            hostile_config = Path(root) / "hostile.gitconfig"
            hostile_config.write_text(
                f"[init]\n\ttemplateDir = {hostile_template}\n"
                "[url \"https://invalid.example/\"]\n\tinsteadOf = /tmp/\n",
                encoding="utf-8",
            )
            operations = self.real_stage_operations(
                source, Path(root) / "staging"
            )
            with mock.patch.dict(
                os.environ,
                {
                    "GIT_CONFIG_GLOBAL": str(hostile_config),
                    "GIT_TEMPLATE_DIR": str(hostile_template),
                    "GIT_DIR": str(source / ".git"),
                    "GIT_WORK_TREE": str(source),
                },
                clear=False,
            ):
                transaction, candidate = operations.stage_candidate(approved)
            self.assertEqual(
                (candidate / "payload.txt").read_text(encoding="utf-8"),
                "approved\n",
            )
            self.assertFalse(marker.exists())
            self.assertFalse((candidate / ".git/hooks").exists())
            self.assertEqual(self.real_git("-C", candidate, "remote").stdout, "")
            operations.cleanup_staging(transaction)

    def test_bundle_attestation_rejects_wrong_missing_and_multiple_heads(self):
        approved = "a" * 40
        for output in (
            "",
            f"{'b' * 40} refs/remotes/origin/main\n",
            f"{approved} refs/heads/main\n",
            (
                f"{approved} refs/remotes/origin/main\n"
                f"{'b' * 40} refs/heads/unexpected\n"
            ),
        ):
            with self.subTest(output=output):
                with self.assertRaisesRegex(
                    upgrade.UpgradeError, "candidate_bundle_identity_mismatch"
                ):
                    upgrade.attest_candidate_bundle_heads(output, approved)
        upgrade.attest_candidate_bundle_heads(
            f"{approved} refs/remotes/origin/main\n", approved
        )

        with tempfile.TemporaryDirectory() as root:
            source, actual = self.real_bundle_source(root)
            operations = self.real_stage_operations(
                source, Path(root) / "staging"
            )
            wrong = "b" * 40
            self.assertNotEqual(actual, wrong)
            with self.assertRaisesRegex(
                upgrade.UpgradeError, "candidate_bundle_identity_mismatch"
            ):
                operations.stage_candidate(wrong)
            transactions = list(operations.staging_root.iterdir())
            self.assertEqual(len(transactions), 1)
            self.assertFalse((transactions[0] / "repository").exists())

            self.real_git(
                "-C", source, "update-ref", "-d", "refs/remotes/origin/main"
            )
            with self.assertRaisesRegex(
                upgrade.UpgradeError, "command_failed:git_bundle_create"
            ):
                operations.stage_candidate(actual)

    def test_bundle_corruption_after_attestation_fails_before_checkout(self):
        with tempfile.TemporaryDirectory() as root:
            source, approved = self.real_bundle_source(root)
            operations = self.real_stage_operations(
                source, Path(root) / "staging"
            )
            real_command = operations.command
            labels = []

            def corrupt_after_heads(label, args, **kwargs):
                labels.append(label)
                result = real_command(label, args, **kwargs)
                if label == "git_bundle_heads":
                    Path(args[-1]).write_bytes(b"corrupted after attestation\n")
                return result

            operations.command = corrupt_after_heads
            with self.assertRaisesRegex(
                upgrade.UpgradeError, "command_failed:git_verify_bundle"
            ):
                operations.stage_candidate(approved)
            self.assertNotIn("git_checkout_candidate", labels)
            self.assertNotIn("git_staged_head", labels)
            transactions = list(operations.staging_root.iterdir())
            self.assertEqual(len(transactions), 1)
            candidate = transactions[0] / "repository"
            self.assertEqual(
                [entry.name for entry in candidate.iterdir()], [".git"]
            )

    def test_bundle_fetch_failure_cannot_advance_to_checkout(self):
        with tempfile.TemporaryDirectory() as root:
            source, approved = self.real_bundle_source(root)
            operations = self.real_stage_operations(
                source, Path(root) / "staging"
            )
            real_command = operations.command
            labels = []

            def corrupt_after_verify(label, args, **kwargs):
                labels.append(label)
                result = real_command(label, args, **kwargs)
                if label == "git_verify_bundle":
                    bundle = next(
                        Path(value) for value in args if str(value).endswith(".bundle")
                    )
                    bundle.write_bytes(b"corrupted before fetch\n")
                return result

            operations.command = corrupt_after_verify
            with self.assertRaisesRegex(
                upgrade.UpgradeError, "command_failed:git_fetch_bundle"
            ):
                operations.stage_candidate(approved)
            self.assertNotIn("git_checkout_candidate", labels)
            self.assertNotIn("git_staged_head", labels)

    def test_staging_failure_never_advances_to_static_preflight_or_installer(self):
        with tempfile.TemporaryDirectory() as root:
            operations, _record, _audit, coordinator = self.coordinator(
                root, failure="stage_candidate"
            )
            with self.assertRaisesRegex(
                upgrade.UpgradeError, "failed:stage_candidate"
            ):
                coordinator.execute(dry_run=False)
            self.assertNotIn("static_preflight", operations.events)
            self.assertNotIn("installer_dry_run", operations.events)
            self.assertNotIn("installer_apply", operations.events)

    def test_static_preflight_is_non_mutating_and_creates_no_bytecode(self):
        with tempfile.TemporaryDirectory() as root:
            operations, candidate = self.static_preflight_candidate(root)
            digest_before = operations.protected_tree_digest(candidate)
            artifacts_before = {
                path.relative_to(candidate)
                for pattern in ("__pycache__", "*.pyc", "*.pyo")
                for path in candidate.rglob(pattern)
            }

            returned_digest = self.run_static_preflight(operations, candidate)

            self.assertEqual(returned_digest, digest_before)
            self.assertEqual(
                operations.protected_tree_digest(candidate), digest_before
            )
            artifacts_after = {
                path.relative_to(candidate)
                for pattern in ("__pycache__", "*.pyc", "*.pyo")
                for path in candidate.rglob(pattern)
            }
            self.assertEqual(artifacts_after, artifacts_before)
            self.assertEqual(artifacts_after, set())

    def test_static_preflight_accepts_source_encoding_without_bytecode(self):
        with tempfile.TemporaryDirectory() as root:
            operations, candidate = self.static_preflight_candidate(root)
            encoded = candidate / "web/deployment/lib/encoded_source.py"
            encoded.write_bytes(
                b"# coding: latin-1\nvalue = 'caf\xe9'\n"
            )

            digest = self.run_static_preflight(operations, candidate)

            self.assertEqual(
                operations.protected_tree_digest(candidate), digest
            )
            self.assertFalse(any(candidate.rglob("*.pyc")))
            self.assertFalse(any(candidate.rglob("*.pyo")))
            self.assertFalse(any(candidate.rglob("__pycache__")))

    def test_static_preflight_invalid_python_fails_closed_without_bytecode(self):
        with tempfile.TemporaryDirectory() as root:
            operations, candidate = self.static_preflight_candidate(root)
            invalid = candidate / "web/deployment/lib/invalid_source.py"
            invalid.write_text("def invalid(:\n", encoding="utf-8")

            with self.assertRaisesRegex(
                upgrade.UpgradeError, "candidate_python_syntax_failed"
            ):
                self.run_static_preflight(operations, candidate)

            self.assertFalse(any(candidate.rglob("*.pyc")))
            self.assertFalse(any(candidate.rglob("*.pyo")))
            self.assertFalse(any(candidate.rglob("__pycache__")))

    def test_static_preflight_uses_isolated_bytecode_free_compile(self):
        with tempfile.TemporaryDirectory() as root:
            operations, candidate = self.static_preflight_candidate(root)
            candidate_interpreter = candidate / "web/deployment/bin/python3"
            candidate_interpreter.write_text(
                "#!/bin/sh\nexit 99\n", encoding="utf-8"
            )
            candidate_interpreter.chmod(0o755)
            real_run = subprocess.run
            commands = []

            def record_run(args, **kwargs):
                commands.append((list(args), dict(kwargs)))
                return real_run(args, **kwargs)

            with (
                mock.patch.object(
                    upgrade.subprocess, "run", side_effect=record_run
                ),
                mock.patch.dict(
                    os.environ,
                    {
                        "PATH": str(candidate_interpreter.parent),
                        "PYTHONPATH": str(candidate),
                        "PYTHONHOME": str(candidate),
                    },
                    clear=False,
                ),
            ):
                self.run_static_preflight(operations, candidate)

            python_commands = [
                (args, kwargs)
                for args, kwargs in commands
                if upgrade.PYTHON_SYNTAX_VALIDATOR in args
            ]
            self.assertEqual(len(python_commands), 1)
            args, kwargs = python_commands[0]
            self.assertEqual(args[0], str(Path(sys.executable).resolve()))
            self.assertNotEqual(args[0], str(candidate_interpreter))
            self.assertNotEqual(args[0], "/usr/bin/env")
            self.assertEqual(args[1:4], ["-I", "-B", "-c"])
            self.assertIn("compile(source.read()", args[4])
            self.assertNotIn("py_compile", args)
            self.assertNotIn("PYTHONPYCACHEPREFIX", kwargs["env"])
            self.assertNotIn("PYTHONPATH", kwargs["env"])
            self.assertNotIn("PYTHONHOME", kwargs["env"])

    def test_trusted_python_interpreter_rejects_candidate_and_invalid_paths(self):
        with tempfile.TemporaryDirectory() as root:
            candidate = Path(root) / "candidate"
            candidate.mkdir()
            controlled = candidate / "python3"
            controlled.write_text("not an interpreter\n", encoding="utf-8")
            controlled.chmod(0o755)

            for value in ("", "python3", str(controlled)):
                with (
                    self.subTest(value=value),
                    mock.patch.object(upgrade.sys, "executable", value),
                    self.assertRaisesRegex(
                        upgrade.UpgradeError,
                        "candidate_python_interpreter_untrusted",
                    ),
                ):
                    upgrade.trusted_python_executable(candidate)

    def test_installer_dry_run_sequence_preserves_static_preflight_digest(self):
        with tempfile.TemporaryDirectory() as root:
            operations, candidate = self.static_preflight_candidate(root)
            digest_before = self.run_static_preflight(operations, candidate)
            backup = operations.backup_root / "pre-candidate"
            operations.command = mock.Mock(
                return_value=upgrade.CommandResult("", "", 0)
            )

            operations.installer_dry_run(candidate, backup)

            self.assertEqual(
                operations.protected_tree_digest(candidate), digest_before
            )
            operations.command.assert_called_once()
            self.assertEqual(
                operations.command.call_args.args[0], "installer_dry_run"
            )

    def test_real_protected_mutation_changes_post_dry_run_digest(self):
        with tempfile.TemporaryDirectory() as root:
            operations, candidate = self.static_preflight_candidate(root)
            digest_before = self.run_static_preflight(operations, candidate)
            operations.command = mock.Mock(
                return_value=upgrade.CommandResult("", "", 0)
            )
            operations.installer_dry_run(
                candidate, operations.backup_root / "pre-candidate"
            )
            tamper = candidate / "web/deployment/tampered_after_dry_run"
            tamper.write_text("tampered\n", encoding="utf-8")

            self.assertNotEqual(
                operations.protected_tree_digest(candidate), digest_before
            )

            tamper.unlink()
            protected = candidate / "web/deployment/production-paths.conf"
            original = protected.read_bytes()
            protected.write_text(
                protected.read_text(encoding="utf-8") + "# changed\n",
                encoding="utf-8",
            )
            self.assertNotEqual(
                operations.protected_tree_digest(candidate), digest_before
            )

            protected.write_bytes(original)
            hidden = candidate / "web/deployment/.hidden-tamper"
            hidden.write_text("hidden\n", encoding="utf-8")
            self.assertNotEqual(
                operations.protected_tree_digest(candidate), digest_before
            )

    def test_post_dry_run_protected_mutation_remains_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            operations, _record, _audit, coordinator = self.coordinator(root)
            operations.protected_tree_digest = mock.Mock(
                return_value="tampered-protected-tree"
            )

            with self.assertRaisesRegex(
                upgrade.UpgradeError, "candidate_changed_after_dry_run"
            ):
                coordinator.execute(dry_run=True)

    def test_wrong_canonical_remote_fails_before_fetch(self):
        operations = object.__new__(upgrade.SystemOperations)
        operations.repository_origin = mock.Mock(return_value="file:///tmp/evil")
        operations.madar_git = mock.Mock()
        with self.assertRaisesRegex(
            upgrade.UpgradeError, "canonical_git_remote_mismatch"
        ):
            operations.resolve_candidate(self.SHA, dry_run=False)
        operations.madar_git.assert_not_called()

    def test_authorized_controller_ahead_bridge_requires_all_attestations(self):
        production = "1" * 40
        approved = "2" * 40
        operations, current = self.compatibility_operations(
            production=production, installed=approved, approved=approved
        )
        result = operations.validate_controller_compatibility(approved, current)
        self.assertEqual(result, "controller_ahead_bridge")
        labels = [call.args[0] for call in operations.command.call_args_list]
        self.assertEqual(labels, ["guard_current", "guard_approved_bridge"])
        guard_current = operations.command.call_args_list[0]
        guard_approved = operations.command.call_args_list[1]
        self.assertEqual(guard_current.args[1][-1], production)
        self.assertFalse(guard_current.kwargs["check"])
        self.assertEqual(guard_current.kwargs["user"], "madar")
        self.assertEqual(guard_approved.args[1][-1], approved)
        self.assertEqual(guard_approved.kwargs["user"], "madar")
        operations.require_clean_repository.assert_called_once()

    def test_repository_guard_uses_canonical_madar_identity_without_git_bypass(self):
        operations = object.__new__(upgrade.SystemOperations)
        operations.control_root = Path("/opt/madar/control-plane/deployment")
        operations.command = mock.Mock(
            return_value=upgrade.CommandResult("", "", 0)
        )

        operations.production_repository_guard(
            "guard_candidate", self.SHA, check=False
        )

        call = operations.command.call_args
        self.assertEqual(call.args[0], "guard_candidate")
        self.assertEqual(
            call.args[1],
            [
                "/opt/madar/control-plane/deployment/bin/"
                "madar-control-plane-guard",
                self.SHA,
            ],
        )
        self.assertEqual(call.kwargs["user"], "madar")
        self.assertFalse(call.kwargs["check"])
        self.assertNotIn("safe.directory", " ".join(call.args[1]))

    def test_repository_guard_command_crosses_sanitized_runuser_boundary(self):
        operations = object.__new__(upgrade.SystemOperations)
        operations.audit = None
        operations.control_root = Path("/opt/madar/control-plane/deployment")
        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")

        with mock.patch.object(
            upgrade.subprocess, "run", return_value=completed
        ) as run:
            operations.production_repository_guard("guard_current", self.SHA)

        command = run.call_args.args[0]
        self.assertEqual(
            command[:6],
            [
                "/usr/sbin/runuser", "-u", "madar", "--",
                "/usr/bin/env", "-i",
            ],
        )
        self.assertIn("HOME=/home/madar", command)
        self.assertIn("USER=madar", command)
        self.assertIn("GIT_CONFIG_GLOBAL=/dev/null", command)
        self.assertNotIn("safe.directory", " ".join(command))

    def test_installed_and_restore_guards_share_repository_identity_helper(self):
        operations = object.__new__(upgrade.SystemOperations)
        operations.installed_sha = mock.Mock(return_value=self.SHA)
        operations.production_repository_guard = mock.Mock(
            side_effect=upgrade.UpgradeError("stop_after_guard")
        )

        with self.assertRaisesRegex(upgrade.UpgradeError, "stop_after_guard"):
            operations.verify_installed_controller(self.SHA)
        operations.production_repository_guard.assert_called_once_with(
            "guard_candidate", self.SHA
        )

        production = "1" * 40
        operations.production_repository_guard.reset_mock(side_effect=True)
        operations.production_repository_guard.return_value = upgrade.CommandResult(
            "", "", 0
        )
        operations.attest_serving = mock.Mock()
        self.assertTrue(operations.preinstall_restore_safe(self.SHA, production))
        operations.production_repository_guard.assert_called_once_with(
            "guard_restore", production
        )
        operations.attest_serving.assert_called_once_with(production)

    def test_normal_controller_compatibility_keeps_existing_guard_semantics(self):
        production = "1" * 40
        approved = "2" * 40
        operations, current = self.compatibility_operations(
            production=production,
            installed=production,
            approved=approved,
            current_guard=0,
        )
        self.assertEqual(
            operations.validate_controller_compatibility(approved, current),
            "normal_compatible",
        )
        operations.madar_git.assert_not_called()
        self.assertEqual(operations.command.call_count, 1)
        self.assertEqual(
            operations.command.call_args.kwargs["user"], "madar"
        )

    def test_controller_ahead_must_equal_approved_current_main(self):
        production = "1" * 40
        installed = "2" * 40
        approved = "3" * 40
        operations, current = self.compatibility_operations(
            production=production, installed=installed, approved=approved
        )
        with self.assertRaisesRegex(
            upgrade.UpgradeError, "installed_controller_not_approved_bridge"
        ):
            operations.validate_controller_compatibility(approved, current)

        operations, current = self.compatibility_operations(
            production=production,
            installed=approved,
            approved=approved,
            resolved="4" * 40,
        )
        with self.assertRaisesRegex(
            upgrade.UpgradeError, "approved_sha_not_current_origin_main"
        ):
            operations.validate_controller_compatibility(approved, current)

    def test_production_ahead_of_installed_controller_is_not_a_bridge(self):
        installed = "1" * 40
        production = "2" * 40
        approved = "3" * 40
        operations, current = self.compatibility_operations(
            production=production, installed=installed, approved=approved
        )
        with self.assertRaisesRegex(
            upgrade.UpgradeError, "installed_controller_not_approved_bridge"
        ):
            operations.validate_controller_compatibility(approved, current)

    def test_controller_bridge_rejects_unrelated_or_incomplete_history(self):
        production = "1" * 40
        approved = "2" * 40
        operations, current = self.compatibility_operations(
            production=production,
            installed=approved,
            approved=approved,
            ancestry=1,
        )
        with self.assertRaisesRegex(
            upgrade.UpgradeError, "controller_bridge_not_forward_ancestor"
        ):
            operations.validate_controller_compatibility(approved, current)

        operations, current = self.compatibility_operations(
            production=production,
            installed=approved,
            approved=approved,
        )

        def missing_object(label, *args, **kwargs):
            if label == "git_bridge_production_type":
                return upgrade.CommandResult("missing", "", 0)
            return self.compatibility_operations(
                production=production, installed=approved, approved=approved
            )[0].madar_git(label, *args, **kwargs)

        operations.madar_git = mock.Mock(side_effect=missing_object)
        with self.assertRaisesRegex(
            upgrade.UpgradeError, "controller_bridge_object_not_commit"
        ):
            operations.validate_controller_compatibility(approved, current)

    def test_controller_bridge_rejects_guard_failure_and_non_delta_errors(self):
        production = "1" * 40
        approved = "2" * 40
        operations, current = self.compatibility_operations(
            production=production,
            installed=approved,
            approved=approved,
            approved_guard=1,
        )
        with self.assertRaisesRegex(
            upgrade.UpgradeError, "command_failed:guard_approved_bridge"
        ):
            operations.validate_controller_compatibility(approved, current)

        operations, current = self.compatibility_operations(
            production=production,
            installed=approved,
            approved=approved,
            protected_delta=0,
        )
        with self.assertRaisesRegex(
            upgrade.UpgradeError, "installed_controller_guard_failure"
        ):
            operations.validate_controller_compatibility(approved, current)

        operations, current = self.compatibility_operations(
            production=production,
            installed=approved,
            approved=approved,
            current_guard=2,
        )
        with self.assertRaisesRegex(
            upgrade.UpgradeError, "installed_controller_guard_failure"
        ):
            operations.validate_controller_compatibility(approved, current)
        operations.madar_git.assert_not_called()

    def test_malformed_installed_provenance_fails_before_candidate_trust(self):
        operations = object.__new__(upgrade.SystemOperations)
        operations.deploy_lock_descriptor = 1
        operations.repository_origin = mock.Mock(
            return_value=upgrade.EXPECTED_CONTRACT["MADAR_CANONICAL_GIT_REMOTE"]
        )
        operations.require_clean_repository = mock.Mock()
        operations.repository_head = mock.Mock(return_value="1" * 40)
        operations.installed_sha = mock.Mock(
            side_effect=upgrade.UpgradeError("installed_provenance_invalid")
        )
        with self.assertRaisesRegex(
            upgrade.UpgradeError, "installed_provenance_invalid"
        ):
            operations.current_preflight()
        operations.repository_head.assert_called_once()

        with tempfile.TemporaryDirectory() as root:
            missing = object.__new__(upgrade.SystemOperations)
            missing.control_root = Path(root)
            with self.assertRaisesRegex(
                upgrade.UpgradeError, "installed_provenance_missing"
            ):
                missing.installed_sha()

    def test_cli_sha_cannot_authorize_bridge_before_candidate_resolution(self):
        with tempfile.TemporaryDirectory() as root:
            operations, _record, _audit, coordinator = self.coordinator(
                root, protected=False, failure="resolve_candidate"
            )
            operations.production = "1" * 40
            operations.installed = self.SHA
            operations.controller_compatibility = "controller_ahead_bridge"
            with self.assertRaisesRegex(
                upgrade.UpgradeError, "failed:resolve_candidate"
            ):
                coordinator.execute(dry_run=True)
        self.assertNotIn("validate_controller_compatibility", operations.events)
        self.assertNotIn("protected_change_required", operations.events)

    def test_ordinary_deployers_still_invoke_the_protected_guard(self):
        for path in (
            WEB_ROOT / "deployment/bin/madar-auto-deploy",
            WEB_ROOT / "deployment/bin/madar-production-deploy",
        ):
            source = path.read_text(encoding="utf-8")
            self.assertIn("madar-control-plane-guard", source)
            self.assertIn('"$CONTROL_PLANE_GUARD" "$TARGET_SHA"', source)

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
        self.assertTrue(record.controller_installation_required)
        self.assertTrue(record.controller_installation_performed)
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

    def test_schema_recovery_is_explicit_exact_schema_and_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            attestation = Path(root) / "schema96-attestation.json"
            operations, record, _audit, coordinator = self.coordinator(root)
            coordinator.execute(
                dry_run=False,
                recovery=True,
                rehearsal_attestation=attestation,
            )
            coordinator.cleanup()
        self.assertTrue(coordinator.success)
        self.assertEqual(record.operation, "schema_recovery")
        self.assertEqual(record.schema_before, 96)
        self.assertEqual(record.schema_after, 96)
        self.assertEqual(record.migration_result, "not_requested")
        self.assertEqual(record.rehearsal_attestation_sha256, "a" * 64)
        self.assertEqual(
            operations.events.count("validate_recovery_candidate_contract"), 1
        )
        self.assertEqual(operations.events.count("recovery=True"), 2)
        self.assertNotIn("recovery=False", operations.events)
        self.assertLess(
            operations.events.index("advance_production_checkout"),
            operations.events.index("attest_serving"),
        )
        self.assertEqual(
            operations.timer, {"enabled": "disabled", "active": "inactive"}
        )

    def test_schema_recovery_requires_rehearsal_before_quiesce(self):
        with tempfile.TemporaryDirectory() as root:
            operations, _record, _audit, coordinator = self.coordinator(root)
            with self.assertRaisesRegex(
                upgrade.UpgradeError, "recovery_rehearsal_attestation_required"
            ):
                coordinator.execute(dry_run=False, recovery=True)
            coordinator.cleanup()
        self.assertNotIn("quiesce", operations.events)
        self.assertNotIn("stage_candidate", operations.events)

    def test_schema_recovery_candidate_contract_failure_never_deploys(self):
        with tempfile.TemporaryDirectory() as root:
            attestation = Path(root) / "schema96-attestation.json"
            operations, record, _audit, coordinator = self.coordinator(
                root, failure="validate_recovery_candidate_contract"
            )
            with self.assertRaises(upgrade.UpgradeError) as raised:
                coordinator.execute(
                    dry_run=False,
                    recovery=True,
                    rehearsal_attestation=attestation,
                )
            coordinator.handle_failure(raised.exception)
            coordinator.cleanup()
        self.assertFalse(record.application_promoted)
        self.assertNotIn("controlled_candidate_deployment", operations.events)

    def test_schema_recovery_contract_rejects_migrations_and_broad_ranges(self):
        valid = {
            "migration_policy": "schema-recovery-no-migration",
            "schema": {
                "compatible_min": 96,
                "compatible_max": 96,
                "target": 96,
                "migration_class": "none",
                "rollback_compatible_min": 96,
                "rollback_compatible_max": 96,
            },
        }
        with tempfile.TemporaryDirectory() as root:
            release_dir = Path(root) / "web/deployment/releases"
            release_dir.mkdir(parents=True)
            contract = release_dir / "schema-96-recovery.json"
            contract.write_text(json.dumps(valid), encoding="utf-8")
            upgrade.SystemOperations.validate_recovery_candidate_contract(
                Path(root), 96
            )
            for mutation in (
                {"migration_manifest": "migrations-097.json"},
                {"schema": {**valid["schema"], "compatible_min": 95}},
                {"schema": {**valid["schema"], "migration_class": "expand-only"}},
            ):
                invalid = {**valid, **mutation}
                contract.write_text(json.dumps(invalid), encoding="utf-8")
                with self.assertRaisesRegex(
                    upgrade.UpgradeError, "recovery_release_contract_invalid"
                ):
                    upgrade.SystemOperations.validate_recovery_candidate_contract(
                        Path(root), 96
                    )

    def test_schema_recovery_attestation_is_exact_sha_schema_and_check_set(self):
        checks = {
            name: "passed" for name in {
                "backend_authoritative", "backend_startup", "readiness",
                "auth_tenant_mfa", "builder_forms_reservations_commerce",
                "notifications_calendar_workers", "frontend_authoritative",
                "frontend_production_build", "schema_96",
                "invalid_indexes_zero", "rls_grants",
                "browser_login_workspace_public",
            }
        }
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "attestation.json"
            document = {
                "format": 1,
                "status": "passed",
                "candidate_sha": self.SHA,
                "schema": 96,
                "created_at": upgrade.datetime.now(
                    upgrade.timezone.utc
                ).isoformat(),
                "checks": checks,
            }
            path.write_text(json.dumps(document), encoding="utf-8")
            protected = SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o600)
            operations = object.__new__(upgrade.SystemOperations)
            with mock.patch.object(
                upgrade, "require_root_protected_ancestry"
            ), mock.patch.object(Path, "stat", return_value=protected):
                digest = operations.validate_rehearsal_attestation(
                    path, self.SHA, 96
                )
                self.assertEqual(len(digest), 64)
                document["candidate_sha"] = "b" * 40
                path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaisesRegex(
                    upgrade.UpgradeError,
                    "recovery_rehearsal_attestation_mismatch",
                ):
                    operations.validate_rehearsal_attestation(path, self.SHA, 96)

    def recovery_preflight_operations(self, root):
        operations = object.__new__(upgrade.SystemOperations)
        operations.state_root = Path(root) / "state"
        operations.state_root.mkdir()
        operations.storage_root = Path(root) / "storage"
        operations.storage_root.mkdir()
        operations.proxy_file = Path(root) / "proxy/active-upstreams.conf"
        operations.proxy_file.parent.mkdir()
        operations.proxy_file.write_text("fixture", encoding="utf-8")
        operations.deploy_lock_descriptor = 1
        old_sha = "1" * 40
        (operations.state_root / "state.json").write_text(json.dumps({
            "active_slot": "blue",
            "known_good_release": {
                "sha": old_sha,
                "slot": "blue",
                "schema": 93,
                "images": {},
            },
        }), encoding="utf-8")
        operations.repository_origin = mock.Mock(
            return_value=upgrade.EXPECTED_CONTRACT["MADAR_CANONICAL_GIT_REMOTE"]
        )
        operations.require_clean_repository = mock.Mock()
        operations.repository_head = mock.Mock(return_value=old_sha)
        operations.installed_sha = mock.Mock(return_value="2" * 40)
        operations.current_traffic_slot = mock.Mock(return_value="blue")
        operations.live_schema = mock.Mock(return_value=96)
        identity = {
            "release_sha": old_sha,
            "schema_compatible_min": 81,
            "schema_compatible_max": 93,
        }
        operations.http_json = mock.Mock(return_value=identity)
        operations.http_json_allow_503 = mock.Mock(return_value={
            "ready": False,
            "components": {"schema": "incompatible", "database": "ok"},
        })
        operations.http_ok = mock.Mock()
        operations.attest_active_images = mock.Mock()
        operations.systemctl_state = mock.Mock(side_effect=lambda unit: (
            {"enabled": "disabled", "active": "inactive"}
            if unit.endswith(".timer")
            else {"enabled": "static", "active": "inactive"}
        ))
        return operations

    def test_schema_recovery_origin_requires_database_ahead_and_no_fallback(self):
        with tempfile.TemporaryDirectory() as root:
            operations = self.recovery_preflight_operations(root)
            result = operations.current_recovery_preflight()
            self.assertEqual(result["schema"], 96)

            operations.live_schema.return_value = 93
            with self.assertRaisesRegex(
                upgrade.UpgradeError,
                "recovery_origin_schema_not_ahead_of_state",
            ):
                operations.current_recovery_preflight()

            operations.live_schema.return_value = 96
            state_path = operations.state_root / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["compatible_fallback_release"] = {
                "schema_compatible_min": 96,
                "schema_compatible_max": 96,
            }
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(
                upgrade.UpgradeError, "recovery_compatible_fallback_available"
            ):
                operations.current_recovery_preflight()

    def test_schema_recovery_origin_rejects_unrelated_degradation(self):
        with tempfile.TemporaryDirectory() as root:
            operations = self.recovery_preflight_operations(root)
            operations.http_json_allow_503.return_value = {
                "ready": False,
                "components": {
                    "schema": "incompatible",
                    "database": "unavailable",
                },
            }
            with self.assertRaisesRegex(
                upgrade.UpgradeError, "recovery_origin_unrelated_degradation"
            ):
                operations.current_recovery_preflight()

    def test_schema_recovery_preflight_accepts_exact_resume_after_switch(self):
        with tempfile.TemporaryDirectory() as root:
            operations = self.recovery_preflight_operations(root)
            state_path = operations.state_root / "state.json"
            state = json.loads(state_path.read_text())
            old = state["known_good_release"]
            state["in_progress_release"] = {
                "schema_recovery": True,
                "release_sha": self.SHA,
                "candidate_slot": "green",
                "previous_traffic_target": "blue",
                "previous_known_good_release": old,
                "schema": 96,
            }
            state_path.write_text(json.dumps(state), encoding="utf-8")
            operations.current_traffic_slot.return_value = "green"
            operations.http_json.return_value = {
                "release_sha": self.SHA,
                "schema_compatible_min": 96,
                "schema_compatible_max": 96,
            }
            operations.http_json_allow_503.return_value = {
                "ready": True, "components": {"schema": "ok"},
            }
            result = operations.current_recovery_preflight(candidate_sha=self.SHA)
        self.assertEqual(result["migration"], "recovery_resume")
        self.assertEqual(result["schema"], 96)

    def test_schema_recovery_preflight_accepts_completed_checkout_pending(self):
        with tempfile.TemporaryDirectory() as root:
            operations = self.recovery_preflight_operations(root)
            state_path = operations.state_root / "state.json"
            state = json.loads(state_path.read_text())
            state["active_slot"] = "green"
            state["known_good_release"] = {
                "sha": self.SHA, "slot": "green", "schema": 96,
            }
            state["compatible_fallback_release"] = {
                "sha": self.SHA, "slot": "blue", "schema": 96,
                "schema_compatible_min": 96, "schema_compatible_max": 96,
            }
            state_path.write_text(json.dumps(state), encoding="utf-8")
            operations.current_traffic_slot.return_value = "green"
            operations.http_json.return_value = {
                "release_sha": self.SHA,
                "schema_compatible_min": 96,
                "schema_compatible_max": 96,
            }
            operations.http_json_allow_503.return_value = {
                "ready": True, "components": {"schema": "ok"},
            }
            result = operations.current_recovery_preflight(candidate_sha=self.SHA)
        self.assertEqual(result["migration"], "recovery_complete_checkout_pending")

    def test_normal_preflight_accepts_completed_zero_migration_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            operations = object.__new__(upgrade.SystemOperations)
            operations.state_root = Path(root)
            release_root = Path(root) / "releases" / self.SHA
            (release_root / "web/deployment/releases").mkdir(parents=True)
            (release_root / "web/deployment/releases/schema-96-recovery.json").write_text(
                json.dumps({
                    "migration_policy": "schema-recovery-no-migration",
                    "schema": {
                        "compatible_min": 96,
                        "compatible_max": 96,
                        "target": 96,
                        "migration_class": "none",
                        "rollback_compatible_min": 96,
                        "rollback_compatible_max": 96,
                    },
                }),
                encoding="utf-8",
            )
            (Path(root) / "state.json").write_text(json.dumps({
                "known_good_release": {
                    "sha": self.SHA,
                    "schema": 96,
                    "schema_recovery": True,
                    "migration_result": "not_requested",
                },
            }), encoding="utf-8")

            self.assertEqual(
                operations.migration_terminal(self.SHA, 96), "not_requested"
            )

    def test_recovery_checkout_advance_is_fast_forward_only_and_verified(self):
        operations = object.__new__(upgrade.SystemOperations)
        old_sha = "1" * 40
        operations.require_clean_repository = mock.Mock()
        operations.repository_head = mock.Mock(side_effect=[old_sha, self.SHA])
        operations.madar_git = mock.Mock(side_effect=[
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0),
        ])
        operations.advance_production_checkout(self.SHA)
        self.assertEqual(operations.madar_git.call_args_list[0].args[1:3], (
            "merge-base", "--is-ancestor",
        ))
        self.assertIn("--ff-only", operations.madar_git.call_args_list[1].args)
        self.assertEqual(operations.require_clean_repository.call_count, 2)

    def test_recovery_checkout_rejects_non_fast_forward(self):
        operations = object.__new__(upgrade.SystemOperations)
        operations.require_clean_repository = mock.Mock()
        operations.repository_head = mock.Mock(return_value="1" * 40)
        operations.madar_git = mock.Mock(return_value=subprocess.CompletedProcess([], 1))
        with self.assertRaisesRegex(upgrade.UpgradeError, "not_fast_forward"):
            operations.advance_production_checkout(self.SHA)

    def test_schema_recovery_post_switch_attestation_failure_is_forward_only(self):
        with tempfile.TemporaryDirectory() as root:
            attestation = Path(root) / "schema96-attestation.json"
            operations, record, _audit, coordinator = self.coordinator(
                root, failure="attest_serving"
            )
            with self.assertRaises(upgrade.UpgradeError) as raised:
                coordinator.execute(
                    dry_run=False,
                    recovery=True,
                    rehearsal_attestation=attestation,
                )
            coordinator.handle_failure(raised.exception)
            coordinator.cleanup()
        self.assertEqual(operations.production, self.SHA)
        self.assertTrue(record.application_promoted)
        self.assertEqual(record.schema_after, 96)
        self.assertEqual(
            record.failure_semantics,
            "post_promotion_forward_repair_timer_disabled",
        )
        self.assertIn("recovery_traffic_identity", operations.events)
        self.assertNotIn("restore_timer", operations.events)

    def test_exact_controller_ahead_bridge_dry_run_is_non_mutating(self):
        production = "1" * 40
        approved = self.SHA
        with tempfile.TemporaryDirectory() as root:
            operations, record, _audit, coordinator = self.coordinator(
                root, protected=False
            )
            operations.production = production
            operations.installed = approved
            operations.controller_compatibility = "controller_ahead_bridge"
            operations.timer = {"enabled": "disabled", "active": "inactive"}
            coordinator.execute(dry_run=True)
            coordinator.cleanup()
            payload = json.loads(coordinator.audit.json_path.read_text())
        self.assertEqual(record.status, "dry_run_complete")
        self.assertEqual(
            record.controller_compatibility, "controller_ahead_bridge"
        )
        self.assertTrue(record.controller_preinstalled)
        self.assertFalse(record.controller_installation_required)
        self.assertFalse(record.controller_installation_performed)
        self.assertFalse(record.controller_installed)
        self.assertIsNone(record.backup_path)
        self.assertEqual(record.previous_production_sha, production)
        self.assertEqual(record.previous_control_plane_sha, approved)
        self.assertEqual(payload["controller_compatibility"], "controller_ahead_bridge")
        self.assertTrue(payload["controller_preinstalled"])
        self.assertLess(
            operations.events.index("resolve_candidate"),
            operations.events.index("validate_controller_compatibility"),
        )
        self.assertIn("verify_installed_controller", operations.events)
        for forbidden in (
            "quiesce", "arm_interlock", "installer_apply", "verify_install",
            "controlled_candidate_deployment", "same_sha_idempotence",
            "restore_timer", "disable_automation_for_failure",
            "clear_interlock", "clear_authorization",
        ):
            self.assertNotIn(forbidden, operations.events)
        self.assertEqual(operations.production, production)
        self.assertEqual(operations.installed, approved)
        self.assertEqual(
            operations.timer, {"enabled": "disabled", "active": "inactive"}
        )

    def test_preinstalled_controller_bridge_promotes_application_without_reinstall(self):
        production = "1" * 40
        approved = self.SHA
        with tempfile.TemporaryDirectory() as root:
            operations, record, _audit, coordinator = self.coordinator(
                root, protected=False
            )
            operations.production = production
            operations.installed = approved
            operations.controller_compatibility = "controller_ahead_bridge"
            operations.timer = {"enabled": "disabled", "active": "inactive"}
            coordinator.execute(dry_run=False)
            coordinator.cleanup()
        self.assertTrue(coordinator.success)
        self.assertEqual(operations.production, approved)
        self.assertEqual(operations.installed, approved)
        self.assertTrue(record.application_promoted)
        self.assertTrue(record.controller_preinstalled)
        self.assertFalse(record.controller_installation_required)
        self.assertFalse(record.controller_installation_performed)
        self.assertFalse(record.controller_installed)
        self.assertIn("verify_installed_controller", operations.events)
        self.assertNotIn("installer_apply", operations.events)
        self.assertNotIn("verify_install", operations.events)
        self.assertIn("controlled_candidate_deployment", operations.events)
        self.assertIn("same_sha_idempotence", operations.events)
        self.assertEqual(record.same_sha_validation, "passed")
        self.assertEqual(record.failure_semantics, "complete")
        self.assertEqual(
            operations.timer, {"enabled": "disabled", "active": "inactive"}
        )

    def test_preinstalled_bridge_restores_initially_enabled_timer_after_success(self):
        with tempfile.TemporaryDirectory() as root:
            operations, _record, _audit, coordinator = self.coordinator(
                root, protected=False
            )
            operations.production = "1" * 40
            operations.installed = self.SHA
            operations.controller_compatibility = "controller_ahead_bridge"
            coordinator.execute(dry_run=False)
            coordinator.cleanup()
        self.assertEqual(
            operations.timer, {"enabled": "enabled", "active": "active"}
        )

    def test_preinstalled_bridge_failure_before_promotion_preserves_split_state(self):
        production = "1" * 40
        approved = self.SHA
        with tempfile.TemporaryDirectory() as root:
            operations, record, _audit, coordinator = self.coordinator(
                root, protected=False, failure="controlled_candidate_deployment"
            )
            operations.production = production
            operations.installed = approved
            operations.controller_compatibility = "controller_ahead_bridge"
            with self.assertRaises(upgrade.UpgradeError) as raised:
                coordinator.execute(dry_run=False)
            coordinator.handle_failure(raised.exception)
            coordinator.cleanup()
        self.assertEqual(operations.production, production)
        self.assertEqual(operations.installed, approved)
        self.assertFalse(record.application_promoted)
        self.assertEqual(
            record.failure_semantics,
            "controller_ahead_bridge_application_untouched_timer_disabled",
        )
        self.assertNotIn("preinstall_restore_safe", operations.events)
        self.assertNotIn("restore_timer", operations.events)
        self.assertTrue(operations.interlock)
        self.assertEqual(
            operations.timer, {"enabled": "disabled", "active": "inactive"}
        )

    def test_preinstalled_bridge_failure_after_promotion_is_forward_repair(self):
        with tempfile.TemporaryDirectory() as root:
            operations, record, _audit, coordinator = self.coordinator(
                root, protected=False, failure="same_sha_idempotence"
            )
            operations.production = "1" * 40
            operations.installed = self.SHA
            operations.controller_compatibility = "controller_ahead_bridge"
            with self.assertRaises(upgrade.UpgradeError) as raised:
                coordinator.execute(dry_run=False)
            coordinator.handle_failure(raised.exception)
            coordinator.cleanup()
        self.assertEqual(operations.production, self.SHA)
        self.assertTrue(record.application_promoted)
        self.assertEqual(
            record.failure_semantics,
            "post_promotion_forward_repair_timer_disabled",
        )
        self.assertNotIn("restore_timer", operations.events)
        self.assertTrue(operations.interlock)

    def test_failed_bridge_dry_run_never_mutates_automation_or_interlock(self):
        with tempfile.TemporaryDirectory() as root:
            operations, record, _audit, coordinator = self.coordinator(
                root, protected=False, failure="verify_installed_controller"
            )
            operations.production = "1" * 40
            operations.installed = self.SHA
            operations.controller_compatibility = "controller_ahead_bridge"
            with self.assertRaises(upgrade.UpgradeError) as raised:
                coordinator.execute(dry_run=True)
            coordinator.handle_failure(raised.exception)
            coordinator.cleanup()
        self.assertEqual(record.failure_semantics, "dry_run_no_mutation")
        for forbidden in (
            "quiesce", "arm_interlock", "disable_automation_for_failure",
            "clear_interlock", "clear_authorization", "restore_timer",
        ):
            self.assertNotIn(forbidden, operations.events)

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
        self.assertLess(
            operations.events.index("stage_candidate"),
            operations.events.index("static_preflight"),
        )
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

    def test_recovery_authorization_is_mandatory_and_bound(self):
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / "in-progress.json"
            with self.assertRaisesRegex(RuntimeError, "recovery_authorization_required"):
                require_upgrade_authorization(
                    self.SHA, interlock=marker,
                    required_operation="schema_recovery", required_schema=96,
                    require_rehearsal=True,
                )
            token = "one-use-recovery-token"
            rehearsal = "a" * 64
            document = {
                "approved_sha": self.SHA,
                "authorization_sha256": hashlib.sha256(token.encode()).hexdigest(),
                "operation": "schema_recovery", "schema": 96,
                "rehearsal_sha256": rehearsal,
            }
            marker.write_text(json.dumps(document), encoding="utf-8")
            marker.chmod(0o644)
            credentials = Path(root) / "credentials"
            credentials.mkdir()
            (credentials / "madar-control-plane-upgrade").write_text(json.dumps({
                "approved_sha": self.SHA, "token": token,
                "operation": "schema_recovery", "schema": 96,
                "rehearsal_sha256": rehearsal,
            }), encoding="utf-8")
            root_stat = SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o644)
            with mock.patch.object(Path, "stat", return_value=root_stat), mock.patch.dict(
                os.environ, {"CREDENTIALS_DIRECTORY": str(credentials)}, clear=True
            ):
                require_upgrade_authorization(
                    self.SHA, interlock=marker,
                    required_operation="schema_recovery", required_schema=96,
                    require_rehearsal=True,
                )
                document["schema"] = 97
                marker.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "exclusive_interlock"):
                    require_upgrade_authorization(
                        self.SHA, interlock=marker,
                        required_operation="schema_recovery", required_schema=96,
                        require_rehearsal=True,
                    )

    def test_installer_and_service_define_self_update_and_authorization_boundary(self):
        installer = INSTALLER_PATH.read_text(encoding="utf-8")
        service = SERVICE_PATH.read_text(encoding="utf-8")
        self.assertIn("bin/madar-control-plane-upgrade", installer)
        self.assertIn("lib/control_plane_filesystem.py", installer)
        self.assertIn("lib/control_plane_upgrade.py", installer)
        self.assertIn("/usr/local/sbin/madar-control-plane-upgrade", installer)
        self.assertIn("RENAME_EXCHANGE = 2", installer)
        self.assertNotIn('rm -rf -- "$install_root"', installer)
        self.assertNotIn("var_lib_mode", installer)
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
        self.assertIn("--property=EnvironmentFile=/etc/madar/backup.env", invocation)
        self.assertIn("--property=EnvironmentFile=/etc/madar/node1-backup.env", invocation)
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

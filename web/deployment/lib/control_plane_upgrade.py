"""Root-owned, exact-SHA Madar control-plane upgrade bootstrapper.

The running bootstrapper remains the authority for its whole transaction.  A
candidate installer may replace the on-disk bootstrapper only for the next
invocation; no candidate module is imported into this process.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LIB_ROOT = Path(__file__).resolve().parent
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from control_plane_filesystem import (
    FilesystemPreflightError,
    require_root_protected_directory,
    require_root_protected_ancestry,
)


SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
LOWER_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
AUTOMATIC_MIGRATION_POLICY = (
    "automatic-after-known-good-backup-first-forward-repair"
)
SUCCESSFUL_MIGRATION_PHASES = {
    "already_at_target",
    "post_migration_validation_complete",
}
REQUIRED_PRODUCTION_READINESS = {
    "schema", "notification_worker", "calendar_sync_worker",
    "data_deletion_worker", "parser_isolation",
}
PROTECTED_PATHS = (
    "web/deployment",
    "web/scripts/madar_alert_hook.sh",
    "web/scripts/backup_madar.sh",
    "web/scripts/verify_backup.sh",
    "web/scripts/backup_support.py",
    "web/scripts/verify_latest_backup.sh",
    "web/scripts/replicate_latest_node1.py",
    "web/scripts/replicate_latest_offhost.sh",
    "web/scripts/replicate_backup_offhost.sh",
    "web/scripts/restore_madar.sh",
    "web/scripts/rehearse_backup.py",
)
EXPECTED_CONTRACT = {
    "MADAR_PRODUCTION_REPO": "/srv/madar/production",
    "MADAR_ENV_FILE": "/etc/madar/production.env",
    "MADAR_DEPLOY_STATE_ROOT": "/var/lib/madar/releases",
    "MADAR_STORAGE_ROOT": "/var/lib/madar/storage",
    "MADAR_ACTIVE_UPSTREAMS_FILE": "/var/lib/madar/proxy/active-upstreams.conf",
    "MADAR_PROXY_CONFIG_ROOT": "/var/lib/madar/proxy",
    "MADAR_CONTROL_PLANE_ROOT": "/opt/madar/control-plane/deployment",
    "MADAR_RELEASE_DEPLOY_BIN": (
        "/opt/madar/control-plane/deployment/bin/madar-release-deploy"
    ),
    "MADAR_PRODUCTION_DEPLOY_BIN": (
        "/opt/madar/control-plane/deployment/bin/madar-production-deploy"
    ),
    "MADAR_TRAFFIC_SWITCH_COMMAND": (
        "/opt/madar/control-plane/deployment/bin/madar-switch-traffic"
    ),
    "MADAR_MIGRATION_BACKUP_SCRIPT": (
        "/opt/madar/control-plane/deployment/scripts/backup_madar.sh"
    ),
    "MADAR_MIGRATION_BACKUP_VERIFY_SCRIPT": (
        "/opt/madar/control-plane/deployment/scripts/verify_backup.sh"
    ),
    "MADAR_CANONICAL_GIT_REMOTE": "git@github.com:judahsleibi34/Madar.git",
}
SLOT_PORTS = {
    "blue": {"backend": 8101, "frontend": 3100},
    "green": {"backend": 8201, "frontend": 3200},
}
SAFE_ENVIRONMENT = {
    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
    "HOME": "/root",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_NO_REPLACE_OBJECTS": "1",
}
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PRIVATE_KEY|SERVICE_KEY|"
    r"DATABASE_URL|SUPABASE|VAPID|SMTP|OAUTH|JWT|CSRF)[A-Z0-9_]*)\s*=\s*\S+"
)
PYTHON_SYNTAX_VALIDATOR = (
    "import sys\n"
    "for filename in sys.argv[1:]:\n"
    "    with open(filename, 'rb') as source:\n"
    "        compile(source.read(), filename, 'exec', dont_inherit=True)\n"
)


class UpgradeError(RuntimeError):
    """A stable, non-secret operator error code."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_sha(value: str) -> str:
    if not SHA_RE.fullmatch(value):
        raise UpgradeError("approved_sha_must_be_exact_40_hex")
    return value.lower()


def attest_candidate_bundle_heads(output: str, approved_sha: str) -> None:
    entries = [line.split() for line in output.splitlines() if line.strip()]
    if entries != [[approved_sha, "refs/remotes/origin/main"]]:
        raise UpgradeError("candidate_bundle_identity_mismatch")


def sanitized_environment(*, madar_user: bool = False) -> dict[str, str]:
    environment = dict(SAFE_ENVIRONMENT)
    if madar_user:
        environment.update(HOME="/home/madar", USER="madar", LOGNAME="madar")
    return environment


def trusted_python_executable(candidate: Path) -> str:
    """Bind child validation to this process's protected interpreter."""

    value = sys.executable
    if not value or not os.path.isabs(value):
        raise UpgradeError("candidate_python_interpreter_untrusted")
    original = Path(value)
    try:
        original_metadata = original.lstat()
        executable = original.resolve(strict=True)
        candidate_root = candidate.resolve(strict=True)
        metadata = executable.stat()
    except OSError as error:
        raise UpgradeError("candidate_python_interpreter_untrusted") from error
    try:
        executable.relative_to(candidate_root)
    except ValueError:
        pass
    else:
        raise UpgradeError("candidate_python_interpreter_untrusted")
    if (
        not (stat.S_ISREG(original_metadata.st_mode)
             or stat.S_ISLNK(original_metadata.st_mode))
        or (stat.S_ISREG(original_metadata.st_mode)
            and original_metadata.st_mode & 0o022)
        or (os.geteuid() == 0 and original_metadata.st_uid != 0)
    ):
        raise UpgradeError("candidate_python_interpreter_untrusted")
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_mode & 0o022
        or not os.access(executable, os.X_OK)
        or (os.geteuid() == 0 and metadata.st_uid != 0)
    ):
        raise UpgradeError("candidate_python_interpreter_untrusted")
    for path in (original, executable):
        for parent in (path.parent, *path.parent.parents):
            try:
                parent_metadata = parent.lstat()
            except OSError as error:
                raise UpgradeError(
                    "candidate_python_interpreter_untrusted"
                ) from error
            if (
                stat.S_ISLNK(parent_metadata.st_mode)
                or not stat.S_ISDIR(parent_metadata.st_mode)
                or parent_metadata.st_mode & 0o022
                or (os.geteuid() == 0 and parent_metadata.st_uid != 0)
            ):
                raise UpgradeError("candidate_python_interpreter_untrusted")
    return str(executable)


def redact(text: str) -> str:
    return SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=<redacted>", text)


def parse_contract(path: Path) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        raise UpgradeError("canonical_path_contract_missing_or_symlinked")
    file_stat = path.stat()
    if file_stat.st_uid != 0 or file_stat.st_mode & 0o022:
        raise UpgradeError("canonical_path_contract_not_root_protected")
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise UpgradeError(f"canonical_path_contract_invalid_line:{number}")
        name, value = line.split("=", 1)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name) or not value:
            raise UpgradeError(f"canonical_path_contract_invalid_line:{number}")
        values[name] = value
    if any(values.get(name) != value for name, value in EXPECTED_CONTRACT.items()):
        raise UpgradeError("canonical_path_contract_mismatch")
    return values


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def json_file(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise UpgradeError(code) from error
    if not isinstance(value, dict):
        raise UpgradeError(code)
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_root_directory(
    path: Path, *, create: bool = False, mode: int = 0o700
) -> None:
    if create:
        try:
            path.mkdir(parents=False, mode=mode)
            os.chmod(path, mode)
        except FileExistsError:
            pass
    try:
        require_root_protected_ancestry(path)
        require_root_protected_directory(
            path, exact_mode=mode if create else None
        )
    except FilesystemPreflightError as error:
        raise UpgradeError(str(error)) from error


@dataclass
class AuditRecord:
    approved_sha: str
    dry_run: bool
    started_at: str = field(default_factory=utc_now)
    completed_at: str | None = None
    phase: str = "exclusive_lock"
    status: str = "running"
    previous_control_plane_sha: str | None = None
    previous_production_sha: str | None = None
    candidate_sha: str | None = None
    active_slot_before: str | None = None
    active_slot_after: str | None = None
    schema_before: int | None = None
    schema_after: int | None = None
    backup_path: str | None = None
    migration_result: str | None = None
    timer_state_before: dict[str, str] | None = None
    timer_state_after: dict[str, str] | None = None
    same_sha_validation: str | None = None
    stable_readiness: str | None = None
    active_readiness: str | None = None
    controller_compatibility: str | None = None
    controller_preinstalled: bool = False
    controller_installation_required: bool | None = None
    controller_installation_performed: bool = False
    controller_installed: bool = False
    application_promoted: bool = False
    failure_semantics: str | None = None
    error_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class AuditWriter:
    def __init__(self, history_root: Path, record: AuditRecord):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        identity = (
            record.approved_sha[:12]
            if LOWER_SHA_RE.fullmatch(record.approved_sha)
            else "invalid"
        )
        attempt = f"{stamp}-{identity}-{os.getpid()}"
        self.json_path = history_root / f"{attempt}.json"
        self.log_path = history_root / f"{attempt}.log"
        self.record = record
        history_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(history_root, 0o700)
        self.persist()

    def persist(self) -> None:
        atomic_json(self.json_path, self.record.as_dict())

    def phase(self, name: str) -> None:
        self.record.phase = name
        self.persist()
        self.log(f"phase={name}")

    def log(self, message: str) -> None:
        safe = redact(message).replace("\x00", "")
        descriptor = os.open(
            self.log_path,
            os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
        )
        try:
            os.write(descriptor, f"{utc_now()} {safe[:8000]}\n".encode())
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


class SystemOperations:
    """Concrete host operations. Tests use a fake at this interface."""

    def __init__(self, audit: AuditWriter | None = None):
        self.audit = audit
        self.control_root = Path("/opt/madar/control-plane/deployment")
        self.contract_path = self.control_root / "production-paths.conf"
        self.contract = parse_contract(self.contract_path)
        self.repo = Path(self.contract["MADAR_PRODUCTION_REPO"])
        self.state_root = Path(self.contract["MADAR_DEPLOY_STATE_ROOT"])
        self.storage_root = Path(self.contract["MADAR_STORAGE_ROOT"])
        self.proxy_file = Path(self.contract["MADAR_ACTIVE_UPSTREAMS_FILE"])
        self.control_state_root = Path("/var/lib/madar-control-plane")
        self.upgrade_root = self.control_state_root / "upgrades"
        self.staging_root = self.upgrade_root / "staging"
        self.history_root = self.upgrade_root / "history"
        self.backup_root = self.control_state_root / "backups"
        self.runtime_root = Path("/run/madar/control-plane-upgrade")
        self.authorization_file = self.runtime_root / "authorized.credential"
        self.interlock_file = self.runtime_root / "in-progress.json"
        self.deploy_lock_descriptor: int | None = None

    def attach_audit(self, audit: AuditWriter) -> None:
        self.audit = audit

    def prepare_upgrade_roots(self) -> None:
        require_root_directory(Path("/var/lib"), mode=0o755)
        require_root_directory(self.control_state_root, create=True)
        require_root_directory(self.upgrade_root, create=True)
        require_root_directory(self.staging_root, create=True)
        require_root_directory(self.history_root, create=True)
        require_root_directory(self.backup_root, create=True)

    def command(
        self,
        label: str,
        args: list[str],
        *,
        cwd: Path | None = None,
        user: str | None = None,
        timeout: int = 300,
        check: bool = True,
    ) -> CommandResult:
        command = list(args)
        environment = sanitized_environment(madar_user=user == "madar")
        if user:
            command = [
                "/usr/sbin/runuser", "-u", user, "--",
                "/usr/bin/env", "-i",
                *[f"{name}={value}" for name, value in environment.items()],
                *command,
            ]
            environment = sanitized_environment()
        if self.audit:
            self.audit.log(f"command_start label={label} executable={args[0]}")
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise UpgradeError(f"command_failed:{label}") from error
        if self.audit:
            self.audit.log(
                f"command_complete label={label} returncode={completed.returncode} "
                f"output={redact(completed.stdout + completed.stderr)[:4000]}"
            )
        if check and completed.returncode != 0:
            raise UpgradeError(f"command_failed:{label}")
        return CommandResult(
            completed.stdout.strip(), completed.stderr.strip(), completed.returncode
        )

    def root_git(self, label: str, *args: str, cwd: Path | None = None) -> CommandResult:
        return self.command(
            label,
            [
                "/usr/bin/git",
                "-c", f"safe.directory={self.repo}",
                "-c", "core.hooksPath=/dev/null",
                "-c", "core.fsmonitor=false",
                "-c", "credential.helper=",
                "-c", "protocol.ext.allow=never",
                *args,
            ],
            cwd=cwd,
        )

    def staging_git(
        self, label: str, *args: str, timeout: int = 300
    ) -> CommandResult:
        """Run Git in private staging with local-file transport only."""
        return self.command(
            label,
            [
                "/usr/bin/git",
                "-c", "core.hooksPath=/dev/null",
                "-c", "core.fsmonitor=false",
                "-c", "credential.helper=",
                "-c", "protocol.allow=never",
                "-c", "protocol.file.allow=always",
                "-c", "protocol.ext.allow=never",
                *args,
            ],
            timeout=timeout,
        )

    def madar_git(
        self, label: str, *args: str, check: bool = True
    ) -> CommandResult:
        return self.command(
            label,
            [
                "/usr/bin/git", "-c", "core.hooksPath=/dev/null",
                "-c", "core.fsmonitor=false", "-c", "credential.helper=",
                "-c", "core.sshCommand=/usr/bin/ssh",
                "-c", "protocol.ext.allow=never", "-C", str(self.repo), *args,
            ],
            user="madar",
            timeout=180,
            check=check,
        )

    def production_repository_guard(
        self, label: str, target_sha: str, *, check: bool = True
    ) -> CommandResult:
        """Run the installed guard as the canonical production repo owner."""

        guard = self.control_root / "bin/madar-control-plane-guard"
        return self.command(
            label,
            [str(guard), target_sha],
            user="madar",
            check=check,
        )

    def systemctl_state(self, unit: str) -> dict[str, str]:
        enabled = self.command(
            "systemctl_is_enabled", ["/usr/bin/systemctl", "is-enabled", unit],
            check=False,
        )
        active = self.command(
            "systemctl_is_active", ["/usr/bin/systemctl", "is-active", unit],
            check=False,
        )
        return {
            "enabled": enabled.stdout or "unknown",
            "active": active.stdout or "unknown",
        }

    def installed_sha(self) -> str:
        marker = self.control_root / "CONTROL_PLANE_SOURCE_SHA"
        if not marker.is_file() or marker.is_symlink():
            raise UpgradeError("installed_provenance_missing")
        marker_stat = marker.stat()
        if marker_stat.st_uid != 0 or marker_stat.st_mode & 0o022:
            raise UpgradeError("installed_provenance_not_root_protected")
        value = marker.read_text(encoding="utf-8").strip()
        if not LOWER_SHA_RE.fullmatch(value):
            raise UpgradeError("installed_provenance_invalid")
        return value

    def repository_origin(self) -> str:
        return self.madar_git("git_remote", "remote", "get-url", "origin").stdout

    def repository_head(self) -> str:
        value = self.madar_git("git_head", "rev-parse", "HEAD").stdout
        if not LOWER_SHA_RE.fullmatch(value):
            raise UpgradeError("production_head_invalid")
        return value

    def require_clean_repository(self) -> None:
        if self.madar_git(
            "git_status", "status", "--porcelain", "--untracked-files=normal"
        ).stdout:
            raise UpgradeError("production_checkout_dirty")

    @staticmethod
    def http_json(url: str) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status != 200:
                    raise UpgradeError("production_health_http_failure")
                value = json.loads(response.read())
        except (OSError, ValueError, urllib.error.URLError) as error:
            raise UpgradeError("production_health_unavailable") from error
        if not isinstance(value, dict):
            raise UpgradeError("production_health_invalid")
        return value

    @staticmethod
    def http_ok(url: str) -> None:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status != 200:
                    raise UpgradeError("production_frontend_unavailable")
        except (OSError, urllib.error.URLError) as error:
            raise UpgradeError("production_frontend_unavailable") from error

    def migration_terminal(self, sha: str, schema: int) -> str:
        release = json_file(
            self.state_root / "releases" / sha / "web/deployment/releases/release.json",
            "known_good_release_contract_missing",
        )
        policy = str(release.get("migration_policy") or "")
        migration_dir = self.state_root / "migrations" / sha
        automation = migration_dir / "automation.json"
        execution = migration_dir / "execution.json"
        if execution.exists():
            execution_state = json_file(execution, "migration_execution_state_invalid")
            if execution_state.get("status") not in {"completed"}:
                raise UpgradeError("migration_execution_not_terminal")
        if policy != AUTOMATIC_MIGRATION_POLICY:
            if automation.exists():
                state = json_file(automation, "migration_automation_state_invalid")
                if state.get("status") not in {"completed"}:
                    raise UpgradeError("migration_automation_not_terminal")
            return "not_requested"
        if not automation.exists():
            raise UpgradeError("migration_automation_terminal_missing")
        state = json_file(automation, "migration_automation_state_invalid")
        if (
            state.get("release_sha") != sha
            or state.get("status") != "completed"
            or state.get("phase") not in SUCCESSFUL_MIGRATION_PHASES
            or int(state.get("observed_schema", -1)) != schema
        ):
            raise UpgradeError("migration_automation_not_terminal")
        return str(state.get("phase"))

    def attest_active_images(
        self, slot: str, known_good: dict[str, Any]
    ) -> None:
        images = known_good.get("images") or {}
        if not isinstance(images, dict):
            raise UpgradeError("known_good_image_state_invalid")

        def image_id(component: str) -> str:
            value = str(images.get(component) or "")
            if "@sha256:" not in value:
                raise UpgradeError("known_good_image_state_invalid")
            return "sha256:" + value.rsplit("@sha256:", 1)[1]

        expected = {
            f"madar-{slot}-backend": image_id("backend"),
            f"madar-{slot}-frontend": image_id("frontend"),
        }
        worker_id = image_id("worker")
        for service in (
            "parser-worker", "remote-ingestion-worker", "notification-worker",
            "calendar-sync-worker", "data-deletion-worker",
        ):
            expected[f"madar-{slot}-{service}"] = worker_id
        for container, expected_id in expected.items():
            actual = self.command(
                "running_image_identity",
                [
                    "/usr/bin/docker", "inspect", "--format", "{{.Image}}",
                    container,
                ],
            ).stdout
            if actual != expected_id:
                raise UpgradeError("running_image_identity_mismatch")

    def attest_serving(self, expected_sha: str) -> dict[str, Any]:
        state = json_file(self.state_root / "state.json", "release_state_invalid")
        known = state.get("known_good_release") or {}
        slot = str(state.get("active_slot") or "")
        if (
            slot not in SLOT_PORTS
            or known.get("slot") != slot
            or known.get("sha") != expected_sha
            or state.get("in_progress_release")
            or state.get("rollback_failure")
        ):
            raise UpgradeError("release_state_incoherent")
        try:
            schema = int(known["schema"])
        except (KeyError, TypeError, ValueError) as error:
            raise UpgradeError("known_good_schema_invalid") from error
        stable_version = self.http_json("http://127.0.0.1:8001/health/version")
        stable_ready = self.http_json("http://127.0.0.1:8001/health/ready")
        port = SLOT_PORTS[slot]["backend"]
        active_version = self.http_json(f"http://127.0.0.1:{port}/health/version")
        active_ready = self.http_json(f"http://127.0.0.1:{port}/health/ready")
        for identity in (stable_version, active_version):
            if identity.get("release_sha") != expected_sha:
                raise UpgradeError("serving_release_identity_mismatch")
            try:
                minimum = int(identity["schema_compatible_min"])
                maximum = int(identity["schema_compatible_max"])
            except (KeyError, TypeError, ValueError) as error:
                raise UpgradeError("serving_schema_contract_invalid") from error
            if not minimum <= schema <= maximum:
                raise UpgradeError("serving_schema_incompatible")
        for readiness in (stable_ready, active_ready):
            if readiness.get("ready") is not True:
                raise UpgradeError("serving_readiness_degraded")
            components = readiness.get("components")
            if not isinstance(components, dict) or components.get("schema") != "ok":
                raise UpgradeError("serving_readiness_invalid")
            if any(
                components.get(component) != "ok"
                for component in REQUIRED_PRODUCTION_READINESS
            ):
                raise UpgradeError("required_production_component_not_ready")
        self.http_ok("http://127.0.0.1:3000/")
        self.http_ok(f"http://127.0.0.1:{SLOT_PORTS[slot]['frontend']}/")
        if not self.proxy_file.is_file() or self.proxy_file.is_symlink():
            raise UpgradeError("traffic_target_file_invalid")
        proxy = self.proxy_file.read_text(encoding="utf-8")
        if (
            f"127.0.0.1:{SLOT_PORTS[slot]['backend']}" not in proxy
            or f"127.0.0.1:{SLOT_PORTS[slot]['frontend']}" not in proxy
        ):
            raise UpgradeError("traffic_target_slot_mismatch")
        self.attest_active_images(slot, known)
        migration = self.migration_terminal(expected_sha, schema)
        return {
            "sha": expected_sha,
            "slot": slot,
            "schema": schema,
            "migration": migration,
            "state": state,
        }

    def known_good_identity(self, expected_sha: str) -> dict[str, Any] | None:
        """Read the durable promotion boundary without implying health."""

        try:
            state = json_file(self.state_root / "state.json", "release_state_invalid")
            known = state.get("known_good_release") or {}
            slot = str(state.get("active_slot") or "")
            schema = int(known["schema"])
        except (UpgradeError, KeyError, TypeError, ValueError):
            return None
        if (
            known.get("sha") != expected_sha
            or known.get("slot") != slot
            or slot not in SLOT_PORTS
        ):
            return None
        return {"slot": slot, "schema": schema}

    def current_preflight(
        self, *, lock_deployment: bool = True
    ) -> dict[str, Any]:
        if lock_deployment and self.deploy_lock_descriptor is None:
            self.deploy_lock_descriptor = acquire_lock(
                self.state_root / "deploy.lock", create=False
            )
        if self.repository_origin() != EXPECTED_CONTRACT["MADAR_CANONICAL_GIT_REMOTE"]:
            raise UpgradeError("canonical_git_remote_mismatch")
        self.require_clean_repository()
        production_sha = self.repository_head()
        installed_sha = self.installed_sha()
        serving = self.attest_serving(production_sha)
        timer = self.systemctl_state("madar-auto-deploy.timer")
        service = self.systemctl_state("madar-auto-deploy.service")
        if service["active"] != "inactive":
            raise UpgradeError("auto_deploy_service_already_active")
        guard = self.control_root / "bin/madar-control-plane-guard"
        if not guard.is_file() or not os.access(guard, os.X_OK):
            raise UpgradeError("installed_control_plane_guard_unavailable")
        for path in (self.state_root, self.storage_root, self.proxy_file.parent):
            if not path.exists() or path.is_symlink():
                raise UpgradeError("canonical_production_path_invalid")
        return {
            "production_sha": production_sha,
            "installed_sha": installed_sha,
            "slot": serving["slot"],
            "schema": serving["schema"],
            "migration": serving["migration"],
            "timer": timer,
        }

    def resolve_candidate(self, approved_sha: str, *, dry_run: bool) -> None:
        if self.repository_origin() != EXPECTED_CONTRACT["MADAR_CANONICAL_GIT_REMOTE"]:
            raise UpgradeError("canonical_git_remote_mismatch")
        if dry_run:
            remote = self.madar_git(
                "git_ls_remote", "ls-remote", "--exit-code", "origin", "refs/heads/main"
            ).stdout.split()
            if not remote or remote[0] != approved_sha:
                raise UpgradeError("approved_sha_not_current_origin_main")
        else:
            self.madar_git("git_fetch_main", "fetch", "--quiet", "origin", "main")
            remote = self.madar_git(
                "git_verify_remote_main", "ls-remote", "--exit-code", "origin",
                "refs/heads/main",
            ).stdout.split()
            if not remote or remote[0] != approved_sha:
                raise UpgradeError("origin_main_advanced_during_authorization")
        resolved = self.madar_git(
            "git_resolve_main", "rev-parse", "refs/remotes/origin/main^{commit}"
        ).stdout
        if resolved != approved_sha:
            raise UpgradeError("approved_sha_not_current_origin_main")
        if self.madar_git("git_commit_type", "cat-file", "-t", approved_sha).stdout != "commit":
            raise UpgradeError("approved_object_not_commit")
        current = self.repository_head()
        ancestor = self.madar_git(
            "git_ancestry", "merge-base", "--is-ancestor", current, approved_sha,
            check=False,
        )
        if ancestor.returncode != 0:
            raise UpgradeError("candidate_not_descendant_of_production")
        self.require_clean_repository()
        if self.repository_origin() != EXPECTED_CONTRACT["MADAR_CANONICAL_GIT_REMOTE"]:
            raise UpgradeError("canonical_git_remote_changed")

    def validate_controller_compatibility(
        self, approved_sha: str, current: dict[str, Any]
    ) -> str:
        """Classify controller compatibility only after candidate authorization."""

        production_sha = str(current.get("production_sha") or "")
        installed_sha = str(current.get("installed_sha") or "")
        if not LOWER_SHA_RE.fullmatch(production_sha):
            raise UpgradeError("production_head_invalid")
        if not LOWER_SHA_RE.fullmatch(installed_sha):
            raise UpgradeError("installed_provenance_invalid")
        current_guard = self.production_repository_guard(
            "guard_current", production_sha, check=False
        )
        if current_guard.returncode == 0:
            return "normal_compatible"
        if current_guard.returncode != 1:
            raise UpgradeError("installed_controller_guard_failure")

        # A failed guard is not itself bridge authorization. Prove that it is
        # specifically the protected-tree delta between the installed future
        # controller and the serving ancestor, then re-attest every exact-SHA
        # invariant established by candidate resolution.
        protected_delta = self.madar_git(
            "git_current_controller_delta", "diff", "--quiet",
            installed_sha, production_sha, "--", *PROTECTED_PATHS,
            check=False,
        )
        if protected_delta.returncode != 1:
            raise UpgradeError("installed_controller_guard_failure")
        if installed_sha != approved_sha or production_sha == approved_sha:
            raise UpgradeError("installed_controller_not_approved_bridge")
        if self.repository_origin() != EXPECTED_CONTRACT["MADAR_CANONICAL_GIT_REMOTE"]:
            raise UpgradeError("canonical_git_remote_mismatch")
        resolved = self.madar_git(
            "git_bridge_resolve_main", "rev-parse",
            "refs/remotes/origin/main^{commit}",
        ).stdout
        if resolved != approved_sha:
            raise UpgradeError("approved_sha_not_current_origin_main")
        for label, sha in (
            ("git_bridge_production_type", production_sha),
            ("git_bridge_installed_type", installed_sha),
        ):
            if self.madar_git(label, "cat-file", "-t", sha).stdout != "commit":
                raise UpgradeError("controller_bridge_object_not_commit")
        ancestry = self.madar_git(
            "git_bridge_ancestry", "merge-base", "--is-ancestor",
            production_sha, approved_sha, check=False,
        )
        if ancestry.returncode != 0:
            raise UpgradeError("controller_bridge_not_forward_ancestor")
        self.require_clean_repository()
        self.production_repository_guard("guard_approved_bridge", approved_sha)
        if self.repository_origin() != EXPECTED_CONTRACT["MADAR_CANONICAL_GIT_REMOTE"]:
            raise UpgradeError("canonical_git_remote_changed")
        return "controller_ahead_bridge"

    def protected_change_required(self, approved_sha: str) -> bool:
        installed = self.installed_sha()
        result = self.madar_git(
            "git_protected_diff", "diff", "--quiet", installed, approved_sha,
            "--", *PROTECTED_PATHS,
            check=False,
        )
        if result.returncode not in {0, 1}:
            raise UpgradeError("protected_control_plane_diff_failed")
        return result.returncode == 1

    def quiesce(self) -> None:
        self.backup_timer_states = {}
        for name in ('madar-backup', 'madar-backup-verify', 'madar-node1-backup', 'madar-offhost-backup'):
            service = self.systemctl_state(name + '.service')
            if service['active'] in ('active', 'activating', 'deactivating', 'reloading'):
                raise UpgradeError('backup_operation_running_retry_after_completion')
            state = self.systemctl_state(name + '.timer')
            self.backup_timer_states[name + '.timer'] = state
            if state['active'] == 'active':
                self.command('backup_timer_stop', ['/usr/bin/systemctl', 'stop', name + '.timer'])
        self.command(
            "timer_disable_now",
            ["/usr/bin/systemctl", "disable", "--now", "madar-auto-deploy.timer"],
        )
        self.command(
            "service_stop",
            ["/usr/bin/systemctl", "stop", "madar-auto-deploy.service"],
        )
        self.command(
            "service_reset_failed",
            ["/usr/bin/systemctl", "reset-failed", "madar-auto-deploy.service"],
            check=False,
        )
        timer = self.systemctl_state("madar-auto-deploy.timer")
        service = self.systemctl_state("madar-auto-deploy.service")
        if timer["active"] != "inactive" or timer["enabled"] != "disabled":
            raise UpgradeError("auto_deploy_timer_not_quiesced")
        if service["active"] != "inactive":
            raise UpgradeError("auto_deploy_service_not_quiesced")

    def arm_interlock(self, approved_sha: str) -> None:
        runtime_parent = self.runtime_root.parent
        if not runtime_parent.exists():
            require_root_directory(runtime_parent.parent, mode=0o755)
            require_root_directory(runtime_parent, create=True, mode=0o711)
        else:
            require_root_directory(runtime_parent, mode=0o711)
        require_root_directory(self.runtime_root, create=True, mode=0o711)
        atomic_json(
            self.interlock_file,
            {
                "approved_sha": approved_sha,
                "authorization_sha256": None,
                "status": "quiesced",
            },
        )
        os.chmod(self.interlock_file, 0o644)

    def release_deployment_lock(self) -> None:
        if self.deploy_lock_descriptor is not None:
            os.close(self.deploy_lock_descriptor)
            self.deploy_lock_descriptor = None

    def clear_interlock(self) -> None:
        try:
            self.interlock_file.unlink()
        except FileNotFoundError:
            pass

    def restore_timer(self, original: dict[str, str]) -> dict[str, str]:
        if original.get("enabled") == "enabled":
            self.command(
                "timer_enable",
                ["/usr/bin/systemctl", "enable", "madar-auto-deploy.timer"],
            )
        else:
            self.command(
                "timer_disable",
                ["/usr/bin/systemctl", "disable", "madar-auto-deploy.timer"],
                check=False,
            )
        if original.get("active") == "active":
            self.command(
                "timer_start",
                ["/usr/bin/systemctl", "start", "madar-auto-deploy.timer"],
            )
        else:
            self.command(
                "timer_stop",
                ["/usr/bin/systemctl", "stop", "madar-auto-deploy.timer"],
                check=False,
            )
        restored = self.systemctl_state("madar-auto-deploy.timer")
        expected_enabled = "enabled" if original.get("enabled") == "enabled" else "disabled"
        expected_active = "active" if original.get("active") == "active" else "inactive"
        if restored != {"enabled": expected_enabled, "active": expected_active}:
            raise UpgradeError("auto_deploy_timer_restore_failed")
        for name, state in getattr(self, 'backup_timer_states', {}).items():
            if state['active'] == 'active':
                self.command('backup_timer_restore', ['/usr/bin/systemctl', 'start', name])
        return restored

    def disable_automation_for_failure(self) -> None:
        self.command(
            "failure_timer_disable",
            ["/usr/bin/systemctl", "disable", "--now", "madar-auto-deploy.timer"],
            check=False,
        )
        self.command(
            "failure_service_stop",
            ["/usr/bin/systemctl", "stop", "madar-auto-deploy.service"],
            check=False,
        )
        timer = self.systemctl_state("madar-auto-deploy.timer")
        service = self.systemctl_state("madar-auto-deploy.service")
        if (
            timer.get("enabled") != "disabled"
            or timer.get("active") != "inactive"
            or service.get("active") != "inactive"
        ):
            raise UpgradeError("failed_upgrade_automation_not_quiesced")

    def stage_candidate(self, approved_sha: str) -> tuple[Path, Path]:
        self.prepare_upgrade_roots()
        transaction = Path(tempfile.mkdtemp(prefix=f"{approved_sha[:12]}-", dir=self.staging_root))
        os.chmod(transaction, 0o700)
        bundle = transaction / "candidate.bundle"
        candidate = transaction / "repository"
        self.root_git(
            "git_bundle_create", "-C", str(self.repo), "bundle", "create",
            str(bundle), "refs/remotes/origin/main",
        )
        bundle_heads = self.staging_git(
            "git_bundle_heads", "bundle", "list-heads", str(bundle)
        ).stdout
        attest_candidate_bundle_heads(bundle_heads, approved_sha)
        # A bundle whose only advertised name is refs/remotes/origin/main is
        # intentionally not a cloneable branch topology: ordinary clone sees
        # no refs/heads/* and creates an empty repository.  Initialize a
        # template-free private repository and import that one attested ref
        # explicitly.  The fetch URL is the already-created local bundle, so
        # this phase has no network or mutable-ref fallback.
        self.staging_git(
            "git_init_candidate",
            "init", "--quiet", "--template=", str(candidate),
        )
        self.staging_git(
            "git_verify_bundle",
            "-C", str(candidate), "bundle", "verify", str(bundle),
        )
        staged_ref = "refs/madar-control-plane/approved"
        self.staging_git(
            "git_fetch_bundle",
            "-C", str(candidate), "fetch", "--no-tags",
            "--no-recurse-submodules", "--no-write-fetch-head",
            str(bundle), f"refs/remotes/origin/main:{staged_ref}",
            timeout=300,
        )
        fetched = self.staging_git(
            "git_fetched_candidate",
            "-C", str(candidate), "rev-parse", "--verify",
            f"{staged_ref}^{{commit}}",
        ).stdout
        if fetched != approved_sha:
            raise UpgradeError("staged_candidate_object_mismatch")
        self.staging_git(
            "git_checkout_candidate",
            "-C", str(candidate), "checkout", "--detach", approved_sha,
        )
        self.staging_git(
            "git_delete_staging_ref",
            "-C", str(candidate), "update-ref", "-d", staged_ref,
            approved_sha,
        )
        actual = self.staging_git(
            "git_staged_head", "-C", str(candidate), "rev-parse", "HEAD"
        ).stdout
        dirty = self.staging_git(
            "git_staged_status",
            "-C", str(candidate), "status", "--porcelain",
            "--untracked-files=normal",
        ).stdout
        remaining_refs = self.staging_git(
            "git_staged_refs",
            "-C", str(candidate), "for-each-ref", "--format=%(refname)",
        ).stdout
        remotes = self.staging_git(
            "git_staged_remotes", "-C", str(candidate), "remote"
        ).stdout
        if actual != approved_sha or dirty or remaining_refs or remotes:
            raise UpgradeError("staged_candidate_identity_mismatch")
        return transaction, candidate

    @staticmethod
    def protected_tree_digest(candidate: Path) -> str:
        digest = hashlib.sha256()
        for relative in PROTECTED_PATHS:
            root = candidate / relative
            current = candidate
            for part in Path(relative).parts:
                current = current / part
                if current.is_symlink():
                    raise UpgradeError("candidate_protected_symlink_rejected")
            if not root.exists():
                raise UpgradeError("candidate_protected_path_missing")
            entries = [root] if root.is_file() else sorted(root.rglob("*"))
            for entry in entries:
                if entry.is_symlink():
                    raise UpgradeError("candidate_protected_symlink_rejected")
                relative_name = entry.relative_to(candidate).as_posix().encode()
                digest.update(relative_name + b"\0")
                if entry.is_file():
                    digest.update(sha256_file(entry).encode() + b"\0")
        return digest.hexdigest()

    def static_preflight(self, candidate: Path) -> str:
        required = (
            "web/deployment/bin/madar-install-control-plane",
            "web/deployment/bin/madar-control-plane-upgrade",
            "web/deployment/lib/control_plane_upgrade.py",
            "web/deployment/production-paths.conf",
            "web/deployment/bin/madar-control-plane-guard",
            "web/deployment/bin/madar-auto-deploy",
            "web/deployment/bin/madar-production-deploy",
        )
        for relative in required:
            path = candidate / relative
            if not path.is_file() or path.is_symlink():
                raise UpgradeError(f"candidate_required_file_invalid:{relative}")
        candidate_contract = parse_contract(
            candidate / "web/deployment/production-paths.conf"
        )
        if candidate_contract != self.contract:
            raise UpgradeError("candidate_path_contract_changed")
        digest = self.protected_tree_digest(candidate)
        bin_files: list[tuple[Path, bytes]] = []
        for path in sorted((candidate / "web/deployment/bin").iterdir()):
            if not path.is_file() or path.is_symlink():
                raise UpgradeError("candidate_bin_entry_invalid")
            with path.open("rb") as handle:
                first = handle.readline(256)
            bin_files.append((path, first))
            if b"bash" in first:
                self.command(
                    "candidate_bash_syntax",
                    ["/usr/bin/bash", "-n", str(path)],
                )
        python_files = sorted((candidate / "web/deployment/lib").glob("*.py"))
        python_files.extend(
            path for path, first in bin_files if b"python" in first
        )
        try:
            completed = subprocess.run(
                [
                    trusted_python_executable(candidate), "-I", "-B", "-c",
                    PYTHON_SYNTAX_VALIDATOR,
                    *map(str, python_files),
                ],
                env=sanitized_environment(),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise UpgradeError("candidate_python_syntax_failed") from error
        if completed.returncode != 0:
            raise UpgradeError("candidate_python_syntax_failed")
        for root in (self.staging_root, self.backup_root):
            if shutil.disk_usage(root).free < 1024 * 1024 * 1024:
                raise UpgradeError("control_plane_upgrade_disk_space_insufficient")
        return digest

    def installer_dry_run(self, candidate: Path, backup: Path) -> None:
        self.command(
            "installer_dry_run",
            [
                str(candidate / "web/deployment/bin/madar-install-control-plane"),
                "--backup-dir", str(backup),
            ],
            cwd=candidate,
        )

    def installer_apply(self, candidate: Path, backup: Path, approved_sha: str) -> None:
        self.command(
            "installer_apply",
            [
                str(candidate / "web/deployment/bin/madar-install-control-plane"),
                "--apply", "--backup-dir", str(backup),
            ],
            cwd=candidate,
            timeout=600,
        )
        if self.installed_sha() != approved_sha:
            raise UpgradeError("installed_provenance_mismatch")

    def verify_installed_controller(self, approved_sha: str) -> None:
        if self.installed_sha() != approved_sha:
            raise UpgradeError("installed_provenance_mismatch")
        self.production_repository_guard("guard_candidate", approved_sha)
        parse_contract(self.contract_path)
        for relative in PROTECTED_PATHS:
            if not relative.startswith('web/scripts/') or relative.endswith('madar_alert_hook.sh'):
                continue
            name = Path(relative).name
            installed = Path('/usr/local/lib/madar') / name
            canonical = self.control_root / 'scripts' / name
            if (installed.is_symlink() or not installed.is_file() or installed.stat().st_uid != 0
                    or stat.S_IMODE(installed.stat().st_mode) != 0o755
                    or sha256_file(installed) != sha256_file(canonical)):
                raise UpgradeError('installed_backup_helper_integrity_invalid')
        for path in self.control_root.rglob("*"):
            if path.is_symlink() or path.stat().st_uid != 0:
                raise UpgradeError("installed_control_plane_ownership_invalid")
            if path.is_file() and path.stat().st_mode & 0o022:
                raise UpgradeError("installed_control_plane_mode_invalid")
        for unit in (
            "madar-auto-deploy.service", "madar-auto-deploy.timer",
            "madar-release-proxy.service", "madar-ops-alert@.service",
            "madar-backup.service", "madar-backup.timer",
            "madar-backup-verify.service", "madar-backup-verify.timer",
            "madar-node1-backup.service", "madar-node1-backup.timer",
            "madar-offhost-backup.service", "madar-offhost-backup.timer",
        ):
            path = Path("/etc/systemd/system") / unit
            if (
                not path.is_file()
                or path.is_symlink()
                or path.stat().st_uid != 0
                or stat.S_IMODE(path.stat().st_mode) != 0o644
            ):
                raise UpgradeError("installed_systemd_unit_invalid")
        upgrader = Path("/usr/local/sbin/madar-control-plane-upgrade")
        if (
            not upgrader.is_file()
            or upgrader.is_symlink()
            or upgrader.stat().st_uid != 0
            or stat.S_IMODE(upgrader.stat().st_mode) != 0o755
        ):
            raise UpgradeError("installed_bootstrapper_invalid")
        legacy = (
            Path("/usr/local/lib/madar/web/deployment"),
            Path("/usr/local/sbin/madar-auto-deploy"),
        )
        if any(path.exists() or path.is_symlink() for path in legacy):
            raise UpgradeError("legacy_control_plane_still_authoritative")
        service = self.command(
            "systemd_service_definition",
            ["/usr/bin/systemctl", "cat", "madar-auto-deploy.service"],
        ).stdout
        if (
            str(self.control_root / "bin/madar-auto-deploy") not in service
            or str(self.contract_path) not in service
        ):
            raise UpgradeError("installed_systemd_contract_invalid")

    def verify_install(self, approved_sha: str, backup: Path) -> None:
        self.verify_installed_controller(approved_sha)
        sums = backup / "SHA256SUMS"
        if not sums.is_file() or sums.is_symlink():
            raise UpgradeError("control_plane_backup_manifest_missing")
        self.command(
            "control_plane_backup_verify",
            ["/usr/bin/sha256sum", "--check", "SHA256SUMS"],
            cwd=backup,
        )

    def write_authorization(self, approved_sha: str) -> None:
        require_root_directory(self.runtime_root, mode=0o711)
        token = secrets.token_urlsafe(32)
        descriptor, temporary = tempfile.mkstemp(prefix=".authorized.", dir=self.runtime_root)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(
                    {"approved_sha": approved_sha, "token": token}, handle,
                    sort_keys=True,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.authorization_file)
            atomic_json(
                self.interlock_file,
                {
                    "approved_sha": approved_sha,
                    "authorization_sha256": hashlib.sha256(
                        token.encode("utf-8")
                    ).hexdigest(),
                    "status": "authorized_cycle",
                },
            )
            os.chmod(self.interlock_file, 0o644)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def clear_authorization(self) -> None:
        try:
            self.authorization_file.unlink()
        except FileNotFoundError:
            pass

    def run_deploy_service(self, label: str, approved_sha: str) -> None:
        self.write_authorization(approved_sha)
        unit = f"madar-control-plane-upgrade-{os.getpid()}-{label}"
        started = time.time()
        try:
            start_result = self.command(
                label,
                [
                    "/usr/bin/systemd-run", "--quiet", "--wait", "--collect",
                    "--service-type=oneshot", f"--unit={unit}",
                    "--uid=madar", "--gid=madar",
                    f"--working-directory={self.repo}",
                    "--property=UMask=0077",
                    "--property=NoNewPrivileges=yes",
                    "--property=TimeoutStartSec=45min",
                    "--property=EnvironmentFile=/etc/madar/backup.env",
                    f"--property=EnvironmentFile={self.contract_path}",
                    "--property=Environment=MADAR_TRAFFIC_SWITCH_DRIVER=docker-nginx",
                    "--property=Environment=MADAR_PROXY_CONTAINER=madar-release-proxy",
                    "--property=LoadCredential=madar-control-plane-upgrade:"
                    f"{self.authorization_file}",
                    str(self.control_root / "bin/madar-auto-deploy"),
                ],
                timeout=3000,
                check=False,
            )
        finally:
            self.clear_authorization()
        journal = self.command(
            f"{label}_journal",
            [
                "/usr/bin/journalctl", f"--unit={unit}",
                "--since", f"@{int(started)}", "--no-pager", "--output=short-iso",
            ],
            check=False,
        ).stdout
        if self.audit:
            self.audit.log(f"journal label={label} {journal[:12000]}")
        if start_result.returncode != 0:
            raise UpgradeError(f"{label}_failed")

    def idempotence_snapshot(self, sha: str) -> dict[str, str]:
        files = {
            "release_state": self.state_root / "state.json",
            "proxy_target": self.proxy_file,
            "automation": self.state_root / "migrations" / sha / "automation.json",
        }
        return {
            name: sha256_file(path) if path.is_file() else "absent"
            for name, path in files.items()
        }

    def cleanup_staging(self, transaction: Path | None) -> None:
        if transaction is None:
            return
        resolved = transaction.resolve()
        if resolved.parent != self.staging_root.resolve() or not resolved.name:
            raise UpgradeError("staging_cleanup_scope_invalid")
        shutil.rmtree(resolved)

    def close_locks(self) -> None:
        self.release_deployment_lock()

    def preinstall_restore_safe(self, previous_sha: str, production_sha: str) -> bool:
        try:
            if self.installed_sha() != previous_sha:
                return False
            self.production_repository_guard("guard_restore", production_sha)
            self.attest_serving(production_sha)
            return True
        except UpgradeError:
            return False


class UpgradeCoordinator:
    def __init__(self, operations: SystemOperations, audit: AuditWriter):
        self.operations = operations
        self.audit = audit
        self.record = audit.record
        self.transaction: Path | None = None
        self.candidate: Path | None = None
        self.quiesced = False
        self.success = False

    def execute(self, *, dry_run: bool) -> None:
        self.record.dry_run = dry_run
        self.audit.phase("current_production_preflight")
        before = self.operations.current_preflight(lock_deployment=not dry_run)
        self.record.previous_control_plane_sha = before["installed_sha"]
        self.record.previous_production_sha = before["production_sha"]
        self.record.active_slot_before = before["slot"]
        self.record.schema_before = before["schema"]
        self.record.timer_state_before = before["timer"]
        self.audit.persist()

        self.audit.phase("candidate_resolution")
        self.operations.resolve_candidate(self.record.approved_sha, dry_run=dry_run)
        self.record.candidate_sha = self.record.approved_sha
        self.audit.persist()

        self.audit.phase("controller_compatibility")
        controller_compatibility = self.operations.validate_controller_compatibility(
            self.record.approved_sha, before
        )
        self.record.controller_compatibility = controller_compatibility
        self.record.controller_preinstalled = (
            controller_compatibility == "controller_ahead_bridge"
        )
        self.record.controller_installation_required = not (
            self.record.controller_preinstalled
        )
        self.audit.persist()

        self.audit.phase("protected_change_detection")
        protected_change = self.operations.protected_change_required(
            self.record.approved_sha
        )
        if self.record.controller_preinstalled and protected_change:
            raise UpgradeError("preinstalled_controller_identity_drift")
        if not self.record.controller_preinstalled and not protected_change:
            self.record.controller_installation_required = False
            self.record.status = "not_required"
            self.record.failure_semantics = "ordinary_auto_deploy_required"
            self.record.completed_at = utc_now()
            self.record.timer_state_after = before["timer"]
            self.success = True
            self.audit.persist()
            return

        if not dry_run:
            self.audit.phase("automation_quiesce")
            self.quiesced = True
            self.operations.quiesce()
            self.operations.arm_interlock(self.record.approved_sha)
            # The root-owned interlock now blocks every ordinary/manual
            # controller entrypoint. Release deploy.lock so the explicitly
            # authorized systemd cycle can acquire its normal lock later.
            self.operations.release_deployment_lock()

        self.audit.phase("candidate_staging")
        self.transaction, self.candidate = self.operations.stage_candidate(
            self.record.approved_sha
        )
        self.audit.phase("candidate_static_preflight")
        candidate_digest = self.operations.static_preflight(self.candidate)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = self.operations.backup_root / (
            f"pre-{self.record.approved_sha[:12]}-{stamp}"
        )
        if backup.exists() or backup.is_symlink():
            raise UpgradeError("control_plane_backup_path_already_exists")
        if self.record.controller_installation_required:
            self.record.backup_path = str(backup)
        self.audit.persist()

        self.audit.phase("installer_dry_run")
        self.operations.installer_dry_run(self.candidate, backup)
        if self.operations.protected_tree_digest(self.candidate) != candidate_digest:
            raise UpgradeError("candidate_changed_after_dry_run")
        if self.record.controller_preinstalled:
            self.audit.phase("preinstalled_control_plane_attestation")
            self.operations.verify_installed_controller(self.record.approved_sha)
        if dry_run:
            self.audit.phase("candidate_cleanup")
            self.operations.cleanup_staging(self.transaction)
            self.transaction = None
            self.record.status = "dry_run_complete"
            self.record.phase = "dry_run_complete"
            self.record.completed_at = utc_now()
            self.record.timer_state_after = before["timer"]
            self.success = True
            self.audit.persist()
            return

        if not self.record.controller_preinstalled:
            self.audit.phase("control_plane_install")
            try:
                self.operations.installer_apply(
                    self.candidate, backup, self.record.approved_sha
                )
            finally:
                try:
                    self.record.controller_installed = (
                        self.operations.installed_sha() == self.record.approved_sha
                    )
                    self.record.controller_installation_performed = (
                        self.record.controller_installed
                    )
                except UpgradeError:
                    self.record.controller_installed = False
                self.audit.persist()
            self.audit.phase("control_plane_install_attestation")
            self.operations.verify_install(self.record.approved_sha, backup)

        self.audit.phase("controlled_candidate_deployment")
        self.operations.run_deploy_service(
            "controlled_candidate_deployment", self.record.approved_sha
        )
        serving = self.operations.attest_serving(self.record.approved_sha)
        self.record.application_promoted = True
        self.record.active_slot_after = serving["slot"]
        self.record.schema_after = serving["schema"]
        self.record.migration_result = serving["migration"]
        self.record.stable_readiness = "ready"
        self.record.active_readiness = "ready"
        self.audit.persist()

        self.audit.phase("same_sha_idempotence")
        snapshot = self.operations.idempotence_snapshot(self.record.approved_sha)
        self.operations.run_deploy_service(
            "same_sha_idempotence", self.record.approved_sha
        )
        confirmed = self.operations.attest_serving(self.record.approved_sha)
        if self.operations.idempotence_snapshot(self.record.approved_sha) != snapshot:
            raise UpgradeError("same_sha_cycle_mutated_release_state")
        if confirmed["slot"] != serving["slot"] or confirmed["schema"] != serving["schema"]:
            raise UpgradeError("same_sha_cycle_identity_changed")
        self.record.same_sha_validation = "passed"

        self.audit.phase("candidate_cleanup")
        self.operations.cleanup_staging(self.transaction)
        self.transaction = None
        self.audit.phase("automation_restore")
        self.operations.clear_interlock()
        self.record.timer_state_after = self.operations.restore_timer(before["timer"])
        self.record.status = "success"
        self.record.phase = "complete"
        self.record.failure_semantics = "complete"
        self.record.completed_at = utc_now()
        self.success = True
        self.audit.persist()

    def handle_failure(self, error: Exception) -> None:
        code = str(error) if isinstance(error, UpgradeError) else "unexpected_internal_error"
        if self.record.dry_run:
            self.record.status = "failed"
            self.record.error_code = code[:200]
            self.record.completed_at = utc_now()
            self.record.failure_semantics = "dry_run_no_mutation"
            if self.record.timer_state_before:
                self.record.timer_state_after = dict(self.record.timer_state_before)
            self.audit.log(f"failure code={self.record.error_code}")
            self.audit.persist()
            return
        if (
            self.record.controller_installed or self.record.controller_preinstalled
        ) and not self.record.application_promoted:
            promoted = self.operations.known_good_identity(self.record.approved_sha)
            if promoted:
                self.record.application_promoted = True
                self.record.active_slot_after = promoted["slot"]
                self.record.schema_after = promoted["schema"]
        self.record.status = "failed"
        self.record.error_code = code[:200]
        self.record.completed_at = utc_now()
        if self.record.application_promoted:
            self.record.failure_semantics = "post_promotion_forward_repair_timer_disabled"
        elif self.record.controller_preinstalled:
            self.record.failure_semantics = (
                "controller_ahead_bridge_application_untouched_timer_disabled"
            )
        elif self.record.controller_installed:
            self.record.failure_semantics = "post_install_manual_intervention_timer_disabled"
        else:
            self.record.failure_semantics = "pre_install_production_untouched"
            if self.quiesced and self.record.timer_state_before:
                if self.operations.preinstall_restore_safe(
                    self.record.previous_control_plane_sha or "",
                    self.record.previous_production_sha or "",
                ):
                    try:
                        self.operations.clear_interlock()
                        self.record.timer_state_after = self.operations.restore_timer(
                            self.record.timer_state_before
                        )
                    except UpgradeError:
                        self.record.failure_semantics = (
                            "pre_install_timer_restore_failed_manual_intervention"
                        )
                else:
                    self.record.failure_semantics = (
                        "pre_install_restore_not_attested_timer_disabled"
                    )
        if self.record.controller_installed or self.record.controller_preinstalled:
            try:
                self.operations.disable_automation_for_failure()
                self.operations.arm_interlock(self.record.approved_sha)
            except (AttributeError, UpgradeError):
                self.audit.log("failure_automation_quiesce_or_interlock_failed")
        try:
            self.record.timer_state_after = self.operations.systemctl_state(
                "madar-auto-deploy.timer"
            )
        except (AttributeError, UpgradeError):
            pass
        self.audit.log(f"failure code={self.record.error_code}")
        self.audit.persist()

    def cleanup(self) -> None:
        if not self.record.dry_run:
            self.operations.clear_authorization()
        self.operations.close_locks()
        if not self.record.dry_run and (
            self.success or not (
                self.record.controller_installed
                or self.record.controller_preinstalled
            )
        ):
            self.operations.clear_interlock()
        try:
            self.operations.cleanup_staging(self.transaction)
        except UpgradeError as error:
            self.audit.log(f"cleanup_failure code={error}")


def acquire_lock(path: Path, *, create: bool) -> int:
    flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW
    if create:
        flags |= os.O_CREAT
    try:
        descriptor = os.open(path, flags, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError) as error:
        raise UpgradeError(f"exclusive_lock_unavailable:{path.name}") from error
    return descriptor


def print_success(record: AuditRecord, audit: AuditWriter) -> None:
    title = (
        "CONTROL-PLANE UPGRADE: SUCCESS"
        if record.status == "success"
        else "CONTROL-PLANE UPGRADE: INSPECTION COMPLETE"
    )
    print(title)
    print(f"approved SHA: {record.approved_sha}")
    print(f"previous SHA: {record.previous_production_sha or 'n/a'}")
    print(f"new SHA: {record.candidate_sha or 'n/a'}")
    provenance_after = (
        record.candidate_sha
        if record.controller_installed
        else record.previous_control_plane_sha
    )
    print(
        "control-plane provenance: "
        f"{record.previous_control_plane_sha or 'n/a'} -> "
        f"{provenance_after or 'n/a'}"
    )
    print(
        f"active slot: {record.active_slot_before or 'n/a'} -> "
        f"{record.active_slot_after or record.active_slot_before or 'n/a'}"
    )
    schema_before = record.schema_before if record.schema_before is not None else "n/a"
    schema_after = (
        record.schema_after
        if record.schema_after is not None
        else schema_before
    )
    print(f"schema: {schema_before} -> {schema_after}")
    print(f"migration result: {record.migration_result or 'not_run'}")
    print(
        "controller compatibility: "
        f"{record.controller_compatibility or 'not_classified'}"
    )
    print(
        "controller installation: "
        f"required={record.controller_installation_required} "
        f"performed={record.controller_installation_performed}"
    )
    print(f"stable readiness: {record.stable_readiness or 'not_attested'}")
    print(f"active readiness: {record.active_readiness or 'not_attested'}")
    print(f"same-SHA verification: {record.same_sha_validation or 'not_run'}")
    print(f"timer restored state: {record.timer_state_after or 'unchanged'}")
    backup = record.backup_path or "not_created"
    if record.dry_run and record.backup_path:
        backup = f"planned:{record.backup_path}"
    print(f"control-plane backup: {backup}")
    print(f"audit record: {audit.json_path}")


def print_failure(record: AuditRecord, audit: AuditWriter) -> None:
    print("CONTROL-PLANE UPGRADE: FAILED", file=sys.stderr)
    print(f"phase: {record.phase}", file=sys.stderr)
    print(f"error: {record.error_code or 'unexpected_internal_error'}", file=sys.stderr)
    traffic_sha = (
        record.candidate_sha
        if record.application_promoted
        else record.previous_production_sha
    )
    print(f"safe current traffic SHA: {traffic_sha or 'unknown'}", file=sys.stderr)
    current_slot = record.active_slot_after or record.active_slot_before or "unknown"
    current_schema = (
        record.schema_after
        if record.schema_after is not None
        else record.schema_before
        if record.schema_before is not None
        else "unknown"
    )
    timer = record.timer_state_after or {
        "enabled": "unknown", "active": "unknown",
    }
    print(f"current active slot: {current_slot}", file=sys.stderr)
    print(f"schema: {current_schema}", file=sys.stderr)
    print(f"timer state: {timer}", file=sys.stderr)
    print(f"candidate controller installed: {record.controller_installed}", file=sys.stderr)
    print(
        f"candidate controller preinstalled: {record.controller_preinstalled}",
        file=sys.stderr,
    )
    print(f"candidate application promoted: {record.application_promoted}", file=sys.stderr)
    print(f"failure semantics: {record.failure_semantics}", file=sys.stderr)
    print(f"audit record: {audit.json_path}", file=sys.stderr)
    if record.application_promoted:
        print(
            "next action: keep traffic on the known-good candidate and diagnose "
            "forward repair; do not roll back schema or traffic automatically",
            file=sys.stderr,
        )
    elif record.controller_preinstalled:
        print(
            "next action: keep the timer disabled and diagnose the authorized "
            "controller-ahead bridge; no controller backup was created by this "
            "transaction",
            file=sys.stderr,
        )
    elif record.controller_installed:
        print(
            "next action: keep the timer disabled and diagnose the installed "
            "candidate controller using the preserved backup",
            file=sys.stderr,
        )
    else:
        print(
            "next action: correct the reported preflight failure and rerun with "
            "an explicitly approved exact SHA",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="madar-control-plane-upgrade",
        description="Install and deploy one explicitly authorized Madar control-plane SHA.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help=(
            "Inspect and stage without changing production, services, or the "
            "installed controller"
        ),
    )
    parser.add_argument("sha", help="Exact 40-character origin/main commit SHA")
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        print("CONTROL-PLANE UPGRADE: FAILED\nerror: effective_root_required", file=sys.stderr)
        return 1
    try:
        approved_sha = normalize_sha(args.sha)
        operations = SystemOperations()
        operations.prepare_upgrade_roots()
        upgrade_lock = acquire_lock(operations.upgrade_root / "upgrade.lock", create=True)
    except UpgradeError as error:
        print(f"CONTROL-PLANE UPGRADE: FAILED\nerror: {error}", file=sys.stderr)
        return 1

    record = AuditRecord(approved_sha=approved_sha, dry_run=args.dry_run)
    audit = AuditWriter(operations.history_root, record)
    operations.attach_audit(audit)
    coordinator = UpgradeCoordinator(operations, audit)
    try:
        coordinator.execute(dry_run=args.dry_run)
    except Exception as error:
        coordinator.handle_failure(error)
    finally:
        coordinator.cleanup()
        os.close(upgrade_lock)
    if coordinator.success:
        print_success(record, audit)
        return 0
    print_failure(record, audit)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

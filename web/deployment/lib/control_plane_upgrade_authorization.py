"""One-time authorization interlock for privileged control-plane upgrades."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import pwd
import re
from pathlib import Path


UPGRADE_INTERLOCK = Path("/run/madar/control-plane-upgrade/in-progress.json")
PRODUCTION_CONTROL_ROOT = Path("/opt/madar/control-plane/deployment")
PRODUCTION_MUTATION_USER = "madar"


def require_production_mutation_identity(
    script: Path,
    *,
    installed_root: Path = PRODUCTION_CONTROL_ROOT,
    user: str = PRODUCTION_MUTATION_USER,
) -> None:
    """Fail closed when installed production mutators run as another identity.

    Repository, staging, and test copies are intentionally unaffected. Only
    executables beneath the installed production control-plane root enforce
    the canonical deployment UID/GID.
    """

    resolved_script = Path(script).resolve()
    resolved_root = Path(installed_root).resolve()

    if not resolved_script.is_relative_to(resolved_root):
        return

    try:
        identity = pwd.getpwnam(user)
    except KeyError as error:
        raise RuntimeError(
            "production_mutation_identity_invalid"
        ) from error

    if (
        os.geteuid() != identity.pw_uid
        or os.getegid() != identity.pw_gid
    ):
        raise RuntimeError("production_mutation_identity_invalid")


def require_upgrade_authorization(
    sha: str | None, *, interlock: Path = UPGRADE_INTERLOCK,
    required_operation: str | None = None,
    required_schema: int | None = None,
    require_rehearsal: bool = False,
    required_context_digest: str | None = None,
) -> None:
    """Reject deployment races while a root upgrader owns orchestration.

    A transient systemd unit exposes a root-sourced credential only inside the
    unit credential boundary. The public interlock contains only a SHA and a
    one-way digest, never the bearer token.
    """

    if not interlock.exists() and required_operation is not None:
        raise RuntimeError("control_plane_recovery_authorization_required")
    if not interlock.exists():
        return
    if interlock.is_symlink():
        raise RuntimeError("control_plane_upgrade_interlock_invalid")
    interlock_stat = interlock.stat()
    if interlock_stat.st_uid != 0 or interlock_stat.st_mode & 0o022:
        raise RuntimeError("control_plane_upgrade_interlock_invalid")
    try:
        state = json.loads(interlock.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError("control_plane_upgrade_interlock_invalid") from error
    if state.get("operation") == "provider402-signin" and required_operation != "provider402-signin":
        raise RuntimeError("provider_recovery_operation_not_authorized")
    credential_root = os.getenv("CREDENTIALS_DIRECTORY", "").strip()
    credential = (
        Path(credential_root) / "madar-control-plane-upgrade"
        if credential_root.startswith("/")
        else None
    )
    try:
        if credential is None or not credential.is_file() or credential.is_symlink():
            raise OSError
        authorization = json.loads(credential.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError("control_plane_upgrade_exclusive_interlock") from error
    authorized_sha = str(authorization.get("approved_sha") or "").lower()
    token = str(authorization.get("token") or "")
    expected_digest = str(state.get("authorization_sha256") or "")
    actual_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if (
        (sha is not None and state.get("approved_sha") != sha)
        or authorized_sha != state.get("approved_sha")
        or not token
        or not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
        or not hmac.compare_digest(actual_digest, expected_digest)
        or (required_operation is not None and state.get("operation") != required_operation)
        or (required_operation is not None and authorization.get("operation") != required_operation)
        or (required_schema is not None and state.get("schema") != required_schema)
        or (required_schema is not None and authorization.get("schema") != required_schema)
        or (required_context_digest is not None and (
            not re.fullmatch(r"[0-9a-f]{64}", required_context_digest)
            or state.get("context_sha256") != required_context_digest
            or authorization.get("context_sha256") != required_context_digest
        ))
        or (
            require_rehearsal
            and (
                not re.fullmatch(r"[0-9a-f]{64}", str(state.get("rehearsal_sha256") or ""))
                or authorization.get("rehearsal_sha256") != state.get("rehearsal_sha256")
            )
        )
    ):
        raise RuntimeError("control_plane_upgrade_exclusive_interlock")

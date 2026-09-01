"""One-time authorization interlock for privileged control-plane upgrades."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from pathlib import Path


UPGRADE_INTERLOCK = Path("/run/madar/control-plane-upgrade/in-progress.json")


def require_upgrade_authorization(
    sha: str | None, *, interlock: Path = UPGRADE_INTERLOCK
) -> None:
    """Reject deployment races while a root upgrader owns orchestration.

    A transient systemd unit exposes a root-sourced credential only inside the
    unit credential boundary. The public interlock contains only a SHA and a
    one-way digest, never the bearer token.
    """

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
    ):
        raise RuntimeError("control_plane_upgrade_exclusive_interlock")

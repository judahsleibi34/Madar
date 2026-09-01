"""Filesystem trust checks shared by control-plane dry-run and apply.

The installer invokes this module before either its dry-run report or its first
mutation.  Keep the checks read-only except for the disposable renameat2 probe
inside the already trusted candidate staging parent.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import os
import stat
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path


ACL_XATTR_VERSION = 0x0002
ACL_USER_OBJ = 0x01
ACL_USER = 0x02
ACL_GROUP_OBJ = 0x04
ACL_GROUP = 0x08
ACL_MASK = 0x10
ACL_OTHER = 0x20
ACL_WRITE = 0x02
AT_FDCWD = -100
RENAME_EXCHANGE = 2


class FilesystemPreflightError(RuntimeError):
    """A stable, non-secret filesystem preflight failure."""


@dataclass(frozen=True)
class InstallFilesystemLayout:
    source_root: Path
    backup_root: Path
    control_plane_root: Path = Path("/opt/madar/control-plane")
    install_root: Path = Path("/opt/madar/control-plane/deployment")
    launcher_parent: Path = Path("/usr/local/sbin")
    alert_parent: Path = Path("/usr/local/lib/madar")
    systemd_parent: Path = Path("/etc/systemd/system")
    state_root: Path = Path("/var/lib/madar-control-plane")
    expected_uid: int = 0
    rename_scratch_root: Path | None = None
    trust_root: Path = Path("/")

    @property
    def state_directories(self) -> tuple[Path, ...]:
        return (
            self.state_root,
            self.state_root / "upgrades",
            self.state_root / "upgrades/staging",
            self.state_root / "upgrades/history",
            self.state_root / "backups",
        )

    @property
    def privileged_files(self) -> tuple[Path, ...]:
        return (
            self.launcher_parent / "madar-control-plane-upgrade",
            self.alert_parent / "madar_alert_hook.sh",
            self.systemd_parent / "madar-auto-deploy.service",
            self.systemd_parent / "madar-auto-deploy.timer",
            self.systemd_parent / "madar-release-proxy.service",
            self.systemd_parent / "madar-ops-alert@.service",
        )


def _acl_entries(value: bytes, *, path: Path, name: str) -> list[tuple[int, int, int]]:
    if len(value) < 4 or (len(value) - 4) % 8:
        raise FilesystemPreflightError(f"root_protected_acl_invalid:{path}:{name}")
    version = struct.unpack_from("<I", value)[0]
    if version != ACL_XATTR_VERSION:
        raise FilesystemPreflightError(f"root_protected_acl_invalid:{path}:{name}")
    entries = list(struct.iter_unpack("<HHI", value[4:]))
    if not entries:
        raise FilesystemPreflightError(f"root_protected_acl_invalid:{path}:{name}")
    if any(permissions & ~0o7 for _, permissions, _ in entries):
        raise FilesystemPreflightError(f"root_protected_acl_invalid:{path}:{name}")
    tags = [tag for tag, _, _ in entries]
    if any(tags.count(tag) != 1 for tag in (ACL_USER_OBJ, ACL_GROUP_OBJ, ACL_OTHER)):
        raise FilesystemPreflightError(f"root_protected_acl_invalid:{path}:{name}")
    if any(tag in {ACL_USER, ACL_GROUP} for tag in tags) and tags.count(ACL_MASK) != 1:
        raise FilesystemPreflightError(f"root_protected_acl_invalid:{path}:{name}")
    return entries


def _require_safe_acl(path: Path, *, expected_uid: int) -> None:
    unsupported = {errno.ENODATA, errno.ENOTSUP, errno.EOPNOTSUPP}
    for name in ("system.posix_acl_access", "system.posix_acl_default"):
        try:
            value = os.getxattr(path, name, follow_symlinks=False)
        except OSError as error:
            if error.errno in unsupported:
                continue
            raise FilesystemPreflightError(
                f"root_protected_acl_unreadable:{path}:{name}"
            ) from error
        entries = _acl_entries(value, path=path, name=name)
        masks = [permissions for tag, permissions, _ in entries if tag == ACL_MASK]
        mask = masks[0] if len(masks) == 1 else 0o7
        if len(masks) > 1:
            raise FilesystemPreflightError(f"root_protected_acl_invalid:{path}:{name}")
        for tag, permissions, identity in entries:
            effective = permissions
            if tag in {ACL_USER, ACL_GROUP_OBJ, ACL_GROUP}:
                effective &= mask
            trusted_owner = tag == ACL_USER_OBJ or (
                tag == ACL_USER and identity == expected_uid
            )
            if effective & ACL_WRITE and not trusted_owner:
                raise FilesystemPreflightError(
                    f"root_protected_acl_write_grant:{path}:{name}"
                )
            if tag not in {
                ACL_USER_OBJ, ACL_USER, ACL_GROUP_OBJ, ACL_GROUP, ACL_MASK,
                ACL_OTHER,
            }:
                raise FilesystemPreflightError(f"root_protected_acl_invalid:{path}:{name}")


def require_root_protected_directory(
    path: Path,
    *,
    expected_uid: int = 0,
    exact_mode: int | None = None,
) -> None:
    """Require a real root-owned directory with no effective non-owner write."""

    try:
        metadata = path.lstat()
    except OSError as error:
        raise FilesystemPreflightError(
            f"root_protected_directory_missing:{path}"
        ) from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise FilesystemPreflightError(f"root_protected_directory_invalid:{path}")
    if metadata.st_uid != expected_uid or metadata.st_mode & 0o022:
        raise FilesystemPreflightError(f"root_protected_directory_invalid:{path}")
    if exact_mode is not None and stat.S_IMODE(metadata.st_mode) != exact_mode:
        raise FilesystemPreflightError(f"root_protected_directory_mode_invalid:{path}")
    _require_safe_acl(path, expected_uid=expected_uid)


def require_root_protected_file(path: Path, *, expected_uid: int = 0) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise FilesystemPreflightError(f"root_protected_file_missing:{path}") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise FilesystemPreflightError(f"root_protected_file_invalid:{path}")
    if metadata.st_uid != expected_uid or metadata.st_mode & 0o022:
        raise FilesystemPreflightError(f"root_protected_file_invalid:{path}")
    _require_safe_acl(path, expected_uid=expected_uid)


def require_root_protected_ancestry(
    path: Path,
    *,
    expected_uid: int = 0,
    require_leaf: bool = True,
    trust_root: Path = Path("/"),
) -> Path:
    """Validate every existing path component without following symlinks."""

    if not path.is_absolute() or not trust_root.is_absolute():
        raise FilesystemPreflightError(f"root_protected_path_not_absolute:{path}")
    try:
        relative = path.relative_to(trust_root)
    except ValueError as error:
        raise FilesystemPreflightError(
            f"root_protected_path_outside_trust_root:{path}"
        ) from error
    current = trust_root
    require_root_protected_directory(current, expected_uid=expected_uid)
    parts = relative.parts
    for part in parts:
        current = current / part
        try:
            current.lstat()
        except FileNotFoundError:
            if require_leaf:
                raise FilesystemPreflightError(
                    f"root_protected_directory_missing:{current}"
                )
            return current.parent
        require_root_protected_directory(current, expected_uid=expected_uid)
    return current


def _require_destination_parent(
    path: Path, *, expected_uid: int, trust_root: Path
) -> None:
    if path == Path("/") or not path.is_absolute():
        raise FilesystemPreflightError(f"privileged_destination_invalid:{path}")
    require_root_protected_ancestry(
        path.parent,
        expected_uid=expected_uid,
        require_leaf=True,
        trust_root=trust_root,
    )
    if path.exists() or path.is_symlink():
        require_root_protected_directory(path, expected_uid=expected_uid)


def _require_empty_backup(layout: InstallFilesystemLayout) -> None:
    backup = layout.backup_root
    canonical_parent = layout.state_root / "backups"
    if backup.parent == canonical_parent and not canonical_parent.exists():
        # Apply creates this exact private hierarchy under the already-attested
        # state parent before creating the per-attempt backup directory.
        require_root_protected_ancestry(
            layout.state_root.parent,
            expected_uid=layout.expected_uid,
            require_leaf=True,
            trust_root=layout.trust_root,
        )
    else:
        _require_destination_parent(
            backup, expected_uid=layout.expected_uid,
            trust_root=layout.trust_root,
        )
    if backup.exists() and any(backup.iterdir()):
        raise FilesystemPreflightError("control_plane_backup_directory_not_empty")


def _require_state_layout(layout: InstallFilesystemLayout) -> None:
    require_root_protected_ancestry(
        layout.state_root.parent,
        expected_uid=layout.expected_uid,
        require_leaf=True,
        trust_root=layout.trust_root,
    )
    for path in layout.state_directories:
        if path.exists() or path.is_symlink():
            require_root_protected_ancestry(
                path,
                expected_uid=layout.expected_uid,
                require_leaf=True,
                trust_root=layout.trust_root,
            )
            require_root_protected_directory(
                path, expected_uid=layout.expected_uid, exact_mode=0o700
            )


def require_rename_exchange(scratch_root: Path, target_parent: Path) -> None:
    """Prove the kernel/filesystem exchange operation without touching targets."""

    if scratch_root.stat().st_dev != target_parent.stat().st_dev:
        raise FilesystemPreflightError("rename_exchange_scratch_device_mismatch")
    with tempfile.TemporaryDirectory(
        prefix=".madar-rename-exchange-", dir=scratch_root
    ) as temporary:
        left = Path(temporary) / "left"
        right = Path(temporary) / "right"
        left.mkdir(mode=0o700)
        right.mkdir(mode=0o700)
        (left / "identity").write_text("left", encoding="ascii")
        (right / "identity").write_text("right", encoding="ascii")
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is None:
            raise FilesystemPreflightError("rename_exchange_unavailable")
        renameat2.argtypes = [
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        if renameat2(
            AT_FDCWD, os.fsencode(left), AT_FDCWD, os.fsencode(right),
            RENAME_EXCHANGE,
        ) != 0:
            error = ctypes.get_errno()
            raise FilesystemPreflightError("rename_exchange_unavailable") from OSError(
                error, os.strerror(error)
            )
        if (
            (left / "identity").read_text(encoding="ascii") != "right"
            or (right / "identity").read_text(encoding="ascii") != "left"
        ):
            raise FilesystemPreflightError("rename_exchange_attestation_failed")


def validate_installation_filesystem(layout: InstallFilesystemLayout) -> None:
    """Run all deterministic destination checks shared by dry-run and apply."""

    require_root_protected_ancestry(
        layout.source_root,
        expected_uid=layout.expected_uid,
        require_leaf=True,
        trust_root=layout.trust_root,
    )
    for destination_parent in (
        layout.control_plane_root,
        layout.launcher_parent,
        layout.alert_parent,
        layout.systemd_parent,
    ):
        require_root_protected_ancestry(
            destination_parent,
            expected_uid=layout.expected_uid,
            require_leaf=True,
            trust_root=layout.trust_root,
        )
    if layout.install_root.exists() or layout.install_root.is_symlink():
        require_root_protected_ancestry(
            layout.install_root,
            expected_uid=layout.expected_uid,
            require_leaf=True,
            trust_root=layout.trust_root,
        )
    for path in layout.privileged_files:
        if path.exists() or path.is_symlink():
            require_root_protected_file(path, expected_uid=layout.expected_uid)
    _require_empty_backup(layout)
    _require_state_layout(layout)
    for parent in (
        layout.control_plane_root,
        layout.launcher_parent,
        layout.alert_parent,
        layout.systemd_parent,
        layout.state_root.parent,
    ):
        if os.statvfs(parent).f_flag & os.ST_RDONLY:
            raise FilesystemPreflightError(f"privileged_destination_read_only:{parent}")
    backup_filesystem_parent = (
        layout.backup_root.parent
        if layout.backup_root.parent.exists()
        else layout.state_root.parent
    )
    if os.statvfs(backup_filesystem_parent).f_flag & os.ST_RDONLY:
        raise FilesystemPreflightError(
            f"privileged_destination_read_only:{backup_filesystem_parent}"
        )
    scratch = layout.rename_scratch_root or layout.source_root.parent
    require_root_protected_ancestry(
        scratch,
        expected_uid=layout.expected_uid,
        require_leaf=True,
        trust_root=layout.trust_root,
    )
    require_rename_exchange(scratch, layout.control_plane_root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--backup-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate_installation_filesystem(
            InstallFilesystemLayout(
                source_root=args.source_root,
                backup_root=args.backup_root,
            )
        )
    except FilesystemPreflightError as error:
        print(f"control-plane filesystem preflight failed: {error}", file=os.sys.stderr)
        return 1
    print("control-plane filesystem preflight PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

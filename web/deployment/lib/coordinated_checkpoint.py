"""Sealed coordinated checkpoint inventories and offline archive recovery.

Never update a manifest to attach restore claims. Execution receipts are separate.
No database, Docker, SSH or authorization mutation is available in this module.
Archive recovery is into a new private directory, never a production destination.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile

KINDS = frozenset({"database", "roles", "storage", "auth_metadata",
    "application_storage", "native_config", "production_config", "images",
    "controller", "schema", "ledgers"})


def digest_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative(value):
    if not isinstance(value, str) or not value or "\x00" in value:
        raise RuntimeError("checkpoint_path_invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() == ".":
        raise RuntimeError("checkpoint_path_invalid")
    return Path(path.as_posix())


def regular(path, root):
    path = Path(path)
    root = Path(root)
    if not path.is_relative_to(root):
        raise RuntimeError("checkpoint_path_escape")
    for part in (path, *path.parents):
        if part.is_symlink():
            raise RuntimeError("checkpoint_symlink_denied")
        if part == root:
            break
    if not stat.S_ISREG(path.stat().st_mode):
        raise RuntimeError("checkpoint_regular_file_required")
    return path


def verify_inventory(root):
    root = Path(root)
    manifest = regular(root / "manifest.json", root)
    packet = json.loads(manifest.read_text())
    if packet.get("schema") != 115 or packet.get("version") != 1 or packet.get("sealed") is not True:
        raise RuntimeError("checkpoint_contract_invalid")
    inventory = {}
    kinds = set()
    for entry in packet.get("files", []):
        name = relative(entry["path"]).as_posix()
        if name in inventory or name == "manifest.json":
            raise RuntimeError("checkpoint_duplicate_path")
        file = regular(root / name, root)
        if type(entry.get("size")) is not int or entry["size"] != file.stat().st_size or entry["sha256"] != digest_file(file):
            raise RuntimeError("checkpoint_bytes_changed")
        kinds.add(entry["kind"])
        inventory[name] = entry["sha256"]
    if not KINDS <= kinds:
        raise RuntimeError("checkpoint_scope_incomplete")
    actual = {file.relative_to(root).as_posix() for file in root.rglob("*") if file.is_file()}
    if actual != set(inventory) | {"manifest.json"}:
        raise RuntimeError("checkpoint_inventory_inexact")
    return packet, inventory


def seal(root, *, created_at, binding):
    root = Path(root)
    if (root / "manifest.json").exists():
        raise RuntimeError("checkpoint_already_sealed")
    entries = []
    for name, kind in binding.items():
        file = regular(root / relative(name), root)
        entries.append({"path": name, "kind": kind, "size": file.stat().st_size,
                        "sha256": digest_file(file)})
    packet = {"version": 1, "schema": 115, "sealed": True, "created_at": created_at,
              "restore_verified": False, "migrations_executed": False, "files": entries}
    with (root / "manifest.json").open("x") as stream:
        json.dump(packet, stream, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush(); os.fsync(stream.fileno())
    verify_inventory(root)
    for file in root.rglob("*"):
        if file.is_file():
            file.chmod(0o400)
    root.chmod(0o500)
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return digest_file(root / "manifest.json")


def restore_archive(source, destination, *, max_bytes=16 * 1024**3, max_members=200000):
    """Restore regular files/directories only, preserving bytes without execution.

    Symlinks, hardlinks, devices, sockets, traversal, duplicate paths and sparse
    members are rejected before extraction. Backed-up executable bits and file
    ownership confer no execution authority in the restored quarantine.
    """
    source, destination = Path(source), Path(destination)
    if destination.exists() or destination.is_symlink():
        raise RuntimeError("checkpoint_restore_destination_exists")
    with tarfile.open(source, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) > max_members:
            raise RuntimeError("checkpoint_archive_member_limit")
        seen, total = set(), 0
        for member in members:
            name = relative(member.name).as_posix()
            if name in seen or not (member.isfile() or member.isdir()) or member.sparse:
                raise RuntimeError("checkpoint_archive_unsafe_member")
            seen.add(name)
            total += member.size
            if total > max_bytes:
                raise RuntimeError("checkpoint_archive_size_limit")
        destination.mkdir(mode=0o700)
        inventory = {}
        for member in members:
            target = destination / relative(member.name)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if member.isdir():
                target.mkdir(exist_ok=True, mode=0o700)
                continue
            with archive.extractfile(member) as stream, target.open("xb") as output:
                while chunk := stream.read(1024 * 1024):
                    output.write(chunk)
                output.flush(); os.fsync(output.fileno())
            target.chmod(0o600)
            inventory[relative(member.name).as_posix()] = digest_file(target)
        # Compare actual restored bytes to the archive, independently of its
        # checksum inventory. Never follow restored paths outside quarantine.
        for member in members:
            if member.isfile():
                with archive.extractfile(member) as stream:
                    expected = hashlib.file_digest(stream, "sha256").hexdigest()
                if inventory[relative(member.name).as_posix()] != expected:
                    raise RuntimeError("checkpoint_archive_restore_mismatch")
    return {"files": len(inventory), "bytes": total, "restored_bytes_verified": True,
            "code_executed": False, "configuration_activated": False}

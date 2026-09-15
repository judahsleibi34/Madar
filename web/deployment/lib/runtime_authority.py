"""Durable worker ownership and routing/slot mutation authorities."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


WORKER_OWNERS = {"OLD", "NONE", "CANDIDATE"}


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
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


def worker_authority_path(state_root: Path) -> Path:
    return state_root / "worker-ownership.json"


def load_worker_authority(state_root: Path) -> dict[str, Any] | None:
    path = worker_authority_path(state_root)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError("worker_authority_invalid") from error
    if (
        not isinstance(value, dict)
        or value.get("version") != 1
        or value.get("owner") not in WORKER_OWNERS
        or not isinstance(value.get("generation"), str)
        or len(value["generation"]) != 64
        or not isinstance(value.get("old"), dict)
        or not isinstance(value.get("candidate"), dict)
    ):
        raise RuntimeError("worker_authority_invalid")
    for identity in (value["old"], value["candidate"]):
        if identity.get("slot") not in {"blue", "green"}:
            raise RuntimeError("worker_authority_invalid")
        sha = str(identity.get("sha") or "")
        if len(sha) != 40 or any(character not in "0123456789abcdef" for character in sha):
            raise RuntimeError("worker_authority_invalid")
    if value["old"]["slot"] == value["candidate"]["slot"]:
        raise RuntimeError("worker_authority_invalid")
    return value


def write_worker_authority(
    state_root: Path, *, generation: str, owner: str,
    old: dict[str, str], candidate: dict[str, str],
) -> dict[str, Any]:
    if (
        owner not in WORKER_OWNERS
        or len(generation) != 64
        or any(character not in "0123456789abcdef" for character in generation)
    ):
        raise RuntimeError("worker_authority_invalid")
    payload = {
        "version": 1,
        "generation": generation,
        "owner": owner,
        "old": {"sha": str(old["sha"]), "slot": str(old["slot"])},
        "candidate": {
            "sha": str(candidate["sha"]), "slot": str(candidate["slot"]),
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    for identity in (payload["old"], payload["candidate"]):
        sha = identity["sha"]
        if (
            identity["slot"] not in {"blue", "green"}
            or len(sha) != 40
            or any(character not in "0123456789abcdef" for character in sha)
        ):
            raise RuntimeError("worker_authority_invalid")
    if payload["old"]["slot"] == payload["candidate"]["slot"]:
        raise RuntimeError("worker_authority_invalid")
    _atomic_json(worker_authority_path(state_root), payload)
    return load_worker_authority(state_root) or {}


@contextmanager
def runtime_mutation_lock(state_root: Path) -> Iterator[None]:
    """Serialize loaded-route changes with destructive blue/green mutation."""

    state_root = state_root.resolve()
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state_root / "runtime-mutation.lock").open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield

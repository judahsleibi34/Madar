"""Immutable blue/green release state machine.

The active target is never rebuilt or replaced. A failed pre-switch candidate
is destroyed; a failed post-switch candidate is routed away from by selecting
the retained known-good target.
"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
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
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@dataclass(frozen=True)
class Compatibility:
    schema_min: int
    schema_max: int
    target_schema: int
    migration_class: str
    rollback_schema_min: int
    rollback_schema_max: int

    @classmethod
    def load(cls, path: Path) -> "Compatibility":
        raw = json.loads(path.read_text(encoding="utf-8"))["schema"]
        result = cls(
            schema_min=int(raw["compatible_min"]),
            schema_max=int(raw["compatible_max"]),
            target_schema=int(raw["target"]),
            migration_class=str(raw["migration_class"]),
            rollback_schema_min=int(raw["rollback_compatible_min"]),
            rollback_schema_max=int(raw["rollback_compatible_max"]),
        )
        if result.migration_class not in {"none", "expand-only", "forward-compatible", "coordinated", "breaking"}:
            raise ValueError("unsupported migration compatibility class")
        if not result.schema_min <= result.target_schema <= result.schema_max:
            raise ValueError("target schema is outside candidate compatibility range")
        return result


class Operations(Protocol):
    def verify_source(self, sha: str) -> None: ...
    def build(self, sha: str, slot: str) -> dict[str, str]: ...
    def schema_version(self) -> int: ...
    def preflight(self, sha: str, slot: str, images: dict[str, str], schema: int) -> None: ...
    def start_candidate(self, sha: str, slot: str, images: dict[str, str]) -> None: ...
    def validate_candidate(self, sha: str, slot: str) -> None: ...
    def switch_traffic(self, slot: str) -> None: ...
    def observe(self, sha: str, slot: str) -> None: ...
    def stop_candidate(self, slot: str) -> None: ...


class ReleaseDeployer:
    def __init__(self, *, state_root: Path, compatibility: Compatibility, operations: Operations, retry_minutes: int = 60):
        self.state_root = state_root
        self.compatibility = compatibility
        self.operations = operations
        self.retry_minutes = max(1, retry_minutes)
        self.state_file = state_root / "state.json"
        self.lock_file = state_root / "deploy.lock"

    def _state(self) -> dict[str, Any]:
        try:
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
            return state if isinstance(state, dict) else {}
        except (OSError, ValueError):
            return {}

    def _record(self, state: dict[str, Any], release: dict[str, Any]) -> None:
        history = list(state.get("history") or [])[-49:]
        history.append(release)
        state["history"] = history
        atomic_json(self.state_file, state)

    def _checkpoint(self, state: dict[str, Any], release: dict[str, Any]) -> None:
        state["in_progress_release"] = dict(release)
        atomic_json(self.state_file, state)

    def _recover_interrupted(self, state: dict[str, Any]) -> None:
        interrupted = state.get("in_progress_release")
        if not isinstance(interrupted, dict):
            return
        sha = str(interrupted.get("release_sha") or "")
        slot = str(interrupted.get("candidate_slot") or "")
        previous = str(interrupted.get("previous_traffic_target") or "")
        if len(sha) != 40 or slot not in {"blue", "green"} or previous not in {"blue", "green"}:
            raise RuntimeError("interrupted_release_state_invalid")
        # Preparing the old release source gives the operations layer the
        # immutable Compose definition needed to remove only that candidate.
        self.operations.verify_source(sha)
        if interrupted.get("rollback_required"):
            self.operations.switch_traffic(previous)
        self.operations.stop_candidate(slot)
        interrupted.update(
            status="interrupted_recovered",
            phase="recovered",
            completed_at=utc_now().isoformat(),
            failure_code="previous_process_interrupted",
        )
        state.pop("in_progress_release", None)
        self._record(state, interrupted)

    def deploy(self, sha: str, *, manual_retry: bool = False) -> dict[str, Any]:
        if len(sha) != 40 or any(char not in "0123456789abcdef" for char in sha.lower()):
            raise ValueError("candidate must be a full lowercase Git SHA")
        self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.lock_file.open("a+", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("deployment_already_running") from error
            state = self._state()
            self._recover_interrupted(state)
            state = self._state()
            failure = (state.get("failed_releases") or {}).get(sha)
            if failure and not manual_retry:
                retry_at = datetime.fromisoformat(failure["retry_after"])
                if utc_now() < retry_at:
                    raise RuntimeError("known_bad_release_suppressed")

            previous_slot = str(state.get("active_slot") or "blue")
            candidate_slot = "green" if previous_slot == "blue" else "blue"
            release = {
                "release_sha": sha,
                "candidate_slot": candidate_slot,
                "previous_known_good_release": state.get("known_good_release"),
                "previous_traffic_target": previous_slot,
                "started_at": utc_now().isoformat(),
                "status": "running",
                "phase": "source_validation",
                "schema": {},
                "images": {},
            }
            switched = False
            self._checkpoint(state, release)
            try:
                self.operations.verify_source(sha)
                release["phase"] = "immutable_build"
                self._checkpoint(state, release)
                images = self.operations.build(sha, candidate_slot)
                required_images = ("backend", "frontend", "worker")
                if any("@sha256:" not in str(images.get(name) or "") for name in required_images):
                    raise RuntimeError("immutable_image_digest_missing")
                release["images"] = images
                self._checkpoint(state, release)
                schema = self.operations.schema_version()
                release["schema"] = {
                    "observed": schema,
                    "compatible_min": self.compatibility.schema_min,
                    "compatible_max": self.compatibility.schema_max,
                    "target": self.compatibility.target_schema,
                    "migration_class": self.compatibility.migration_class,
                }
                if not self.compatibility.schema_min <= schema <= self.compatibility.schema_max:
                    raise RuntimeError("candidate_schema_incompatible")
                if state.get("known_good_release") and not (
                    self.compatibility.rollback_schema_min <= schema <= self.compatibility.rollback_schema_max
                ):
                    raise RuntimeError("known_good_rollback_schema_incompatible")
                release["phase"] = "preflight"
                self._checkpoint(state, release)
                self.operations.preflight(sha, candidate_slot, images, schema)
                release["phase"] = "candidate_start"
                self._checkpoint(state, release)
                self.operations.start_candidate(sha, candidate_slot, images)
                release["phase"] = "deep_validation"
                self._checkpoint(state, release)
                self.operations.validate_candidate(sha, candidate_slot)
                release["phase"] = "traffic_switch"
                release["rollback_required"] = True
                self._checkpoint(state, release)
                self.operations.switch_traffic(candidate_slot)
                switched = True
                release["phase"] = "observation"
                self._checkpoint(state, release)
                self.operations.observe(sha, candidate_slot)
                release.update(status="known_good", phase="complete", completed_at=utc_now().isoformat(), traffic_target=candidate_slot)
                state["active_slot"] = candidate_slot
                state["known_good_release"] = {
                    "sha": sha, "slot": candidate_slot, "images": images, "schema": schema,
                }
                state.setdefault("failed_releases", {}).pop(sha, None)
                state.pop("in_progress_release", None)
                self._record(state, release)
                return release
            except Exception as error:
                release.update(
                    status="failed", completed_at=utc_now().isoformat(),
                    failure_reason=type(error).__name__, failure_code=str(error)[:200],
                )
                if switched:
                    release["rollback"] = "traffic_switch_to_retained_known_good"
                    self.operations.switch_traffic(previous_slot)
                else:
                    release["rollback"] = "not_required_active_target_untouched"
                self.operations.stop_candidate(candidate_slot)
                retry_after = utc_now() + timedelta(minutes=self.retry_minutes)
                state.setdefault("failed_releases", {})[sha] = {
                    "failed_at": release["completed_at"], "retry_after": retry_after.isoformat(),
                    "reason": release["failure_code"],
                }
                state.pop("in_progress_release", None)
                self._record(state, release)
                raise

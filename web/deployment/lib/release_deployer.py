"""Immutable blue/green release state machine.

The active target is never rebuilt or replaced. A failed pre-switch candidate
is destroyed; a failed post-switch candidate is routed away from by selecting
the retained known-good target.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from deployment.lib.runtime_authority import (
    load_worker_authority,
    write_worker_authority,
)


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
    def validate_candidate_core(self, sha: str, slot: str) -> None: ...
    def validate_rollback_target(self, release: dict[str, Any], schema: int) -> dict[str, int]: ...
    def activate_workers(self, sha: str, slot: str, images: dict[str, str]) -> None: ...
    def deactivate_workers(self, release: dict[str, Any]) -> None: ...
    def restore_workers(self, release: dict[str, Any]) -> None: ...
    def switch_traffic(self, slot: str) -> None: ...
    def observe(self, sha: str, slot: str) -> None: ...
    def stop_candidate(
        self, slot: str, *, expected_serving: dict[str, str] | None = None
    ) -> None: ...
    def current_traffic_slot(self) -> str: ...
    def resolve_serving_slot(self, expected: dict[str, str]) -> str | None: ...
    def worker_ownership(
        self, retained: dict[str, Any], candidate: dict[str, Any]
    ) -> str: ...
    def validate_recovery_backup(self, schema: int) -> dict[str, Any]: ...


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

    @staticmethod
    def _worker_identity(release: dict[str, Any]) -> dict[str, str]:
        return {
            "sha": str(release.get("sha") or release.get("release_sha") or ""),
            "slot": str(release.get("slot") or release.get("candidate_slot") or ""),
        }

    def _worker_generation(self, release: dict[str, Any]) -> str:
        existing = str(release.get("worker_generation") or "")
        if len(existing) == 64:
            return existing
        material = ":".join((
            str(release.get("recovery_id") or "release"),
            str(release.get("release_sha") or ""),
            str(release.get("started_at") or ""),
            str((release.get("previous_known_good_release") or {}).get("sha") or ""),
        ))
        generation = hashlib.sha256(material.encode()).hexdigest()
        release["worker_generation"] = generation
        return generation

    def _set_worker_authority(
        self, state: dict[str, Any], release: dict[str, Any], owner: str,
        *, expected: set[str] | None = None,
    ) -> None:
        previous = release.get("previous_known_good_release")
        if not isinstance(previous, dict):
            raise RuntimeError("worker_authority_old_identity_invalid")
        old = self._worker_identity(previous)
        candidate = {
            "sha": str(release.get("release_sha") or ""),
            "slot": str(release.get("candidate_slot") or ""),
        }
        generation = self._worker_generation(release)
        current = load_worker_authority(self.state_root)
        if expected is not None and current is None and owner != "OLD":
            raise RuntimeError("worker_authority_missing")
        if expected is not None and current is not None:
            current_identity = (
                current["old"] if current["owner"] == "OLD"
                else current["candidate"] if current["owner"] == "CANDIDATE"
                else None
            )
            same_generation = current["generation"] == generation
            rebased_old = owner == "OLD" and current_identity == old
            if current["owner"] not in expected or not (same_generation or rebased_old):
                raise RuntimeError("worker_authority_transition_invalid")
        write_worker_authority(
            self.state_root, generation=generation, owner=owner,
            old=old, candidate=candidate,
        )
        release["worker_owner"] = owner.lower()
        self._checkpoint(state, release)

    def _require_worker_authority(
        self, release: dict[str, Any], owner: str,
    ) -> None:
        current = load_worker_authority(self.state_root)
        if current is None:
            raise RuntimeError("worker_authority_missing")
        if (
            current["generation"] != self._worker_generation(release)
            or current["owner"] != owner
            or current["old"] != self._worker_identity(
                release.get("previous_known_good_release") or {}
            )
            or current["candidate"] != {
                "sha": str(release.get("release_sha") or ""),
                "slot": str(release.get("candidate_slot") or ""),
            }
        ):
            raise RuntimeError("worker_authority_mismatch")

    def _recover_interrupted(self, state: dict[str, Any]) -> None:
        interrupted = state.get("in_progress_release")
        if not isinstance(interrupted, dict):
            return
        sha = str(interrupted.get("release_sha") or "")
        slot = str(interrupted.get("candidate_slot") or "")
        previous = str(interrupted.get("previous_traffic_target") or "")
        if len(sha) != 40 or slot not in {"blue", "green"} or previous not in {"blue", "green"}:
            raise RuntimeError("interrupted_release_state_invalid")
        known_good = interrupted.get("previous_known_good_release")
        if known_good is None:
            # Legacy/uninitialized state has no old consumer identity to
            # authorize. It may only quiesce and remove the interrupted
            # candidate; bootstrap adoption is the supported activation path.
            self.operations.verify_source(sha)
            traffic = self.operations.current_traffic_slot()
            if traffic == slot:
                if not interrupted.get("rollback_required"):
                    raise RuntimeError(
                        "interrupted_release_operator_intervention:unexpected_candidate_traffic"
                    )
                self.operations.switch_traffic(previous)
            elif traffic != previous:
                raise RuntimeError(
                    "interrupted_release_operator_intervention:traffic_ambiguous"
                )
            if interrupted.get("workers_cut_over"):
                self.operations.deactivate_workers({
                    "sha": sha, "slot": slot,
                    "images": interrupted.get("images") or {},
                })
            self.operations.stop_candidate(slot)
            interrupted.update(
                status="interrupted_recovered", phase="recovered",
                completed_at=utc_now().isoformat(),
                failure_code="previous_process_interrupted",
            )
            state.pop("in_progress_release", None)
            state.pop("rollback_failure", None)
            self._record(state, interrupted)
            return
        if not isinstance(known_good, dict):
            raise RuntimeError("interrupted_release_known_good_invalid")
        candidate = {
            "sha": sha, "slot": slot,
            "images": interrupted.get("images") or {},
        }
        expected_serving = {
            previous: str(known_good.get("sha") or ""), slot: sha,
        }

        # Discover traffic and both worker groups before interpreting the
        # durable phase/authority.  Unknown or overlapping reality is never an
        # instruction to activate either side.
        traffic = self.operations.resolve_serving_slot(expected_serving)
        if traffic is None:
            raise RuntimeError("interrupted_release_operator_intervention:traffic_ambiguous")
        ownership = self.operations.worker_ownership(known_good, candidate)
        if ownership in {"overlap", "ambiguous"}:
            raise RuntimeError(
                "interrupted_release_operator_intervention:worker_state_ambiguous"
            )

        authority = load_worker_authority(self.state_root)
        recorded_owner = str(interrupted.get("worker_owner") or "").upper()
        if authority is None:
            # Compatibility for an interruption before the first authority
            # checkpoint on a controller upgraded from the legacy format.
            if ownership != "old":
                raise RuntimeError("worker_authority_missing")
            self._set_worker_authority(state, interrupted, "OLD", expected=None)
            recorded_owner = "OLD"
        elif recorded_owner in {"OLD", "NONE", "CANDIDATE"}:
            self._require_worker_authority(interrupted, recorded_owner)
        elif (
            authority.get("owner") == "CANDIDATE"
            and authority.get("candidate") == self._worker_identity(known_good)
        ):
            # The last completed release's CANDIDATE becomes this generation's
            # OLD only while actual workers still prove that identity owns work.
            if ownership != "old":
                raise RuntimeError("worker_authority_transition_invalid")
            self._set_worker_authority(
                state, interrupted, "OLD", expected={"CANDIDATE"},
            )
            recorded_owner = "OLD"
        else:
            raise RuntimeError("worker_authority_mismatch")

        # Preparing the candidate source gives the operations layer the
        # immutable Compose definition needed to remove only that candidate.
        self.operations.verify_source(sha)
        if traffic == slot:
            if not interrupted.get("rollback_required"):
                raise RuntimeError(
                    "interrupted_release_operator_intervention:unexpected_candidate_traffic"
                )
            self.operations.switch_traffic(previous)
            if self.operations.resolve_serving_slot(expected_serving) != previous:
                raise RuntimeError(
                    "interrupted_release_operator_intervention:rollback_unproven"
                )
        elif traffic != previous:
            raise RuntimeError("interrupted_release_operator_intervention:traffic_ambiguous")

        if ownership in {"candidate", "candidate_starting", "candidate_partial"}:
            if recorded_owner != "CANDIDATE":
                raise RuntimeError("worker_authority_mismatch")
            self._set_worker_authority(
                state, interrupted, "NONE", expected={"CANDIDATE"},
            )
            recorded_owner = "NONE"
            self.operations.deactivate_workers(candidate)
            ownership = self.operations.worker_ownership(known_good, candidate)
        elif ownership == "old_starting":
            if recorded_owner not in {"OLD", "NONE"}:
                raise RuntimeError("worker_authority_mismatch")
            if recorded_owner == "OLD":
                self._set_worker_authority(
                    state, interrupted, "NONE", expected={"OLD"},
                )
                recorded_owner = "NONE"
            self.operations.deactivate_workers(known_good)
            ownership = self.operations.worker_ownership(known_good, candidate)
        elif ownership == "old" and recorded_owner != "OLD":
            # NONE plus old-active is valid only at the persisted inhibition
            # boundary; quiesce it before making any activation decision.
            if recorded_owner != "NONE" or interrupted.get("phase") != "worker_cutover":
                raise RuntimeError("worker_authority_mismatch")
            self.operations.deactivate_workers(known_good)
            ownership = self.operations.worker_ownership(known_good, candidate)

        if ownership == "none":
            if recorded_owner != "NONE":
                self._set_worker_authority(
                    state, interrupted, "NONE", expected={recorded_owner},
                )
            self._set_worker_authority(state, interrupted, "OLD", expected={"NONE"})
            self.operations.restore_workers(known_good)
            ownership = self.operations.worker_ownership(known_good, candidate)
        if ownership != "old":
            raise RuntimeError(
                "interrupted_release_operator_intervention:retained_workers_unproven"
            )

        self.operations.stop_candidate(
            slot, expected_serving=expected_serving,
        )
        interrupted.update(
            status="interrupted_recovered",
            phase="recovered",
            completed_at=utc_now().isoformat(),
            failure_code="previous_process_interrupted",
        )
        state.pop("in_progress_release", None)
        state.pop("rollback_failure", None)
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
            known_good = state.get("known_good_release")
            switched = False
            workers_cut_over = False
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
                known_good = state.get("known_good_release")
                if known_good:
                    # A candidate manifest cannot prove what the retained old
                    # process supports. Attest the running rollback target
                    # itself immediately before touching the inactive slot.
                    attested = self.operations.validate_rollback_target(known_good, schema)
                    known_good["schema_compatible_min"] = int(attested["compatible_min"])
                    known_good["schema_compatible_max"] = int(attested["compatible_max"])
                    known_good["schema_attested_at"] = utc_now().isoformat()
                    self._checkpoint(state, release)
                release["phase"] = "preflight"
                self._checkpoint(state, release)
                self.operations.preflight(sha, candidate_slot, images, schema)
                release["phase"] = "candidate_start"
                self._checkpoint(state, release)
                self.operations.start_candidate(sha, candidate_slot, images)
                release["phase"] = "deep_validation"
                self._checkpoint(state, release)
                validate_core = getattr(
                    self.operations, "validate_candidate_core",
                    self.operations.validate_candidate,
                )
                validate_core(sha, candidate_slot)
                release["phase"] = "worker_cutover"
                self._checkpoint(state, release)
                candidate_identity = {"sha": sha, "slot": candidate_slot, "images": images}
                if known_good:
                    if self.operations.worker_ownership(known_good, candidate_identity) != "old":
                        raise RuntimeError("worker_ownership_initial_invalid")
                    self._set_worker_authority(state, release, "OLD", expected={"OLD", "CANDIDATE"})
                    self._set_worker_authority(state, release, "NONE", expected={"OLD"})
                    self.operations.deactivate_workers(known_good)
                    if self.operations.worker_ownership(known_good, candidate_identity) != "none":
                        raise RuntimeError("worker_quiescence_unverified")
                try:
                    if known_good:
                        self._set_worker_authority(state, release, "CANDIDATE", expected={"NONE"})
                    self.operations.activate_workers(sha, candidate_slot, images)
                    self.operations.validate_candidate(sha, candidate_slot)
                    workers_cut_over = True
                    release["workers_cut_over"] = True
                    self._checkpoint(state, release)
                except Exception:
                    if known_good:
                        self._set_worker_authority(
                            state, release, "NONE", expected={"CANDIDATE", "NONE"}
                        )
                    self.operations.deactivate_workers(candidate_identity)
                    if known_good:
                        if self.operations.worker_ownership(known_good, candidate_identity) != "none":
                            raise RuntimeError("candidate_worker_shutdown_unverified")
                        self._set_worker_authority(state, release, "OLD", expected={"NONE"})
                        self.operations.restore_workers(known_good)
                    raise
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
                    "worker_generation": release.get("worker_generation"),
                    "schema_compatible_min": self.compatibility.schema_min,
                    "schema_compatible_max": self.compatibility.schema_max,
                }
                # Recovery/migration fallbacks describe the prior operation's
                # topology. Ordinary promotion reuses that slot; its retained
                # target is now the attested previous known-good in history.
                state.pop("compatible_fallback_release", None)
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
                    if known_good:
                        self._set_worker_authority(
                            state, release, "NONE", expected={"CANDIDATE", "NONE"}
                        )
                    self.operations.deactivate_workers({
                        "sha": sha, "slot": candidate_slot, "images": release.get("images") or {},
                    })
                    if known_good:
                        candidate_identity = {
                            "sha": sha, "slot": candidate_slot,
                            "images": release.get("images") or {},
                        }
                        if self.operations.worker_ownership(known_good, candidate_identity) != "none":
                            raise RuntimeError("candidate_worker_shutdown_unverified")
                        self._set_worker_authority(state, release, "OLD", expected={"NONE"})
                        self.operations.restore_workers(known_good)
                    try:
                        self.operations.switch_traffic(previous_slot)
                    except Exception as rollback_error:
                        release.update(
                            status="rollback_failed_manual_intervention",
                            phase="rollback_failed",
                            rollback="traffic_switch_failed_retained_artifacts_preserved",
                            rollback_failure_reason=type(rollback_error).__name__,
                            rollback_failure_code=str(rollback_error)[:200],
                        )
                        state["in_progress_release"] = dict(release)
                        state["rollback_failure"] = {
                            "release_sha": sha,
                            "candidate_slot": candidate_slot,
                            "required_target": previous_slot,
                            "recorded_at": utc_now().isoformat(),
                            "failure_code": release["rollback_failure_code"],
                        }
                        atomic_json(self.state_file, state)
                        raise RuntimeError("automatic_rollback_failed_manual_intervention") from rollback_error
                else:
                    release["rollback"] = "not_required_active_target_untouched"
                    if workers_cut_over:
                        if known_good:
                            self._set_worker_authority(
                                state, release, "NONE", expected={"CANDIDATE", "NONE"}
                            )
                        self.operations.deactivate_workers({
                            "sha": sha, "slot": candidate_slot, "images": release.get("images") or {},
                        })
                        if known_good:
                            candidate_identity = {
                                "sha": sha, "slot": candidate_slot,
                                "images": release.get("images") or {},
                            }
                            if self.operations.worker_ownership(known_good, candidate_identity) != "none":
                                raise RuntimeError("candidate_worker_shutdown_unverified")
                            self._set_worker_authority(state, release, "OLD", expected={"NONE"})
                            self.operations.restore_workers(known_good)
                self.operations.stop_candidate(
                    candidate_slot,
                    expected_serving={
                        previous_slot: str((known_good or {}).get("sha") or ""),
                        candidate_slot: sha,
                    },
                )
                retry_after = utc_now() + timedelta(minutes=self.retry_minutes)
                state.setdefault("failed_releases", {})[sha] = {
                    "failed_at": release["completed_at"], "retry_after": retry_after.isoformat(),
                    "reason": release["failure_code"],
                }
                state.pop("in_progress_release", None)
                self._record(state, release)
                raise

    def recover_current_schema(self, sha: str) -> dict[str, Any]:
        """Replace an incompatible serving release without changing schema.

        This path is intentionally separate from ordinary deployment.  Its
        caller is the root-owned recovery coordinator, which supplies the
        one-use control-plane authorization.  The candidate contract is pinned
        to one schema and cannot carry a migration.
        """

        if len(sha) != 40 or any(char not in "0123456789abcdef" for char in sha):
            raise ValueError("candidate must be a full lowercase Git SHA")
        if not (
            self.compatibility.schema_min
            == self.compatibility.schema_max
            == self.compatibility.target_schema
        ):
            raise RuntimeError("recovery_candidate_not_exact_schema")
        if self.compatibility.migration_class != "none":
            raise RuntimeError("recovery_candidate_requires_migration")

        self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.lock_file.open("a+", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("deployment_already_running") from error

            state = self._state()
            schema = self.operations.schema_version()
            if schema != self.compatibility.target_schema:
                raise RuntimeError("recovery_live_schema_changed")
            known_good = state.get("known_good_release")
            initial_slot = str(state.get("active_slot") or "")
            if not isinstance(known_good, dict) or initial_slot not in {"blue", "green"}:
                raise RuntimeError("recovery_origin_state_invalid")
            initial_candidate_slot = "green" if initial_slot == "blue" else "blue"
            initial_expected = {
                initial_slot: str(known_good.get("sha") or ""),
                initial_candidate_slot: sha,
            }
            traffic = self.operations.resolve_serving_slot(initial_expected)
            if traffic is None:
                raise RuntimeError("recovery_origin_traffic_ambiguous")

            fallback = state.get("compatible_fallback_release")
            if (
                isinstance(known_good, dict)
                and known_good.get("sha") == sha
                and known_good.get("slot") == traffic
                and int(known_good.get("schema", -1)) == schema
                and isinstance(fallback, dict)
                and fallback.get("sha") == sha
                and fallback.get("slot") in {"blue", "green"} - {traffic}
                and int(fallback.get("schema", -1)) == schema
            ):
                self.operations.verify_source(sha)
                self.operations.validate_candidate(sha, traffic)
                validate_core = getattr(
                    self.operations, "validate_candidate_core",
                    self.operations.validate_candidate,
                )
                validate_core(sha, str(fallback["slot"]))
                if self.operations.schema_version() != schema:
                    raise RuntimeError("recovery_live_schema_changed")
                authority = load_worker_authority(self.state_root)
                active_identity = {"sha": sha, "slot": traffic}
                if (
                    authority is None
                    or authority.get("owner") != "CANDIDATE"
                    or authority.get("candidate") != active_identity
                    or authority.get("generation") != known_good.get("worker_generation")
                    or self.operations.worker_ownership(fallback, known_good)
                    != "candidate"
                ):
                    raise RuntimeError("recovery_completed_worker_authority_invalid")
                return {
                    "release_sha": sha,
                    "status": "already_recovered",
                    "phase": "complete",
                    "schema": schema,
                    "traffic_target": traffic,
                    "fallback_slot": fallback["slot"],
                }

            interrupted = state.get("in_progress_release")
            if interrupted:
                if not isinstance(interrupted, dict) or not interrupted.get("schema_recovery"):
                    raise RuntimeError("unrelated_release_in_progress")
                if interrupted.get("release_sha") != sha:
                    raise RuntimeError("different_schema_recovery_in_progress")
                expected_recovery_id = hashlib.sha256(
                    f"{sha}:{schema}:{(interrupted.get('previous_known_good_release') or {}).get('sha', '')}".encode()
                ).hexdigest()
                if interrupted.get("recovery_id") != expected_recovery_id:
                    raise RuntimeError("interrupted_recovery_id_invalid")
                previous_slot = str(interrupted.get("previous_traffic_target") or "")
                candidate_slot = str(interrupted.get("candidate_slot") or "")
                if {previous_slot, candidate_slot} != {"blue", "green"}:
                    raise RuntimeError("interrupted_recovery_state_invalid")
                images = interrupted.get("images") or {}
                expected_serving = {
                    previous_slot: str((interrupted.get("previous_known_good_release") or {}).get("sha") or ""),
                    candidate_slot: sha,
                }
                candidate_identity = {
                    "sha": sha, "slot": candidate_slot, "images": images,
                }
                previous = interrupted.get("previous_known_good_release")
                if not isinstance(previous, dict):
                    raise RuntimeError("interrupted_recovery_state_invalid")
                try:
                    traffic = self.operations.resolve_serving_slot(expected_serving)
                except Exception as error:
                    interrupted.update(
                        status="operator_intervention_required",
                        phase="traffic_reconciliation",
                        rollback="traffic_unknown_preserve_both_targets",
                    )
                    self._checkpoint(state, interrupted)
                    raise RuntimeError(
                        "recovery_operator_intervention_required:traffic_unknown"
                    ) from error
                if traffic is None:
                    raise RuntimeError("recovery_operator_intervention_required:traffic_unknown")
                ownership = self.operations.worker_ownership(previous, candidate_identity)
                authority = load_worker_authority(self.state_root)
                if authority is None:
                    durable_owner = str(interrupted.get("worker_owner") or "unknown").upper()
                    if durable_owner not in {"OLD", "NONE", "CANDIDATE"}:
                        raise RuntimeError("worker_authority_missing")
                    self._set_worker_authority(
                        state, interrupted, durable_owner, expected=None,
                    )
                else:
                    self._require_worker_authority(
                        interrupted, str(interrupted.get("worker_owner") or "").upper()
                    )
                durable_owner = str(interrupted.get("worker_owner") or "").upper()
                phase = str(interrupted.get("phase") or "")
                if ownership in {"overlap", "ambiguous"}:
                    raise RuntimeError(
                        "recovery_operator_intervention_required:worker_state_ambiguous"
                    )
                if ownership == "candidate":
                    if durable_owner != "CANDIDATE":
                        raise RuntimeError(
                            "recovery_operator_intervention_required:worker_authority_contradiction"
                        )
                elif ownership in {"candidate_starting", "candidate_partial"}:
                    none_candidate_handoff = (
                        durable_owner == "NONE"
                        and traffic == candidate_slot
                        and phase in {
                            "traffic_switch", "post_switch_validation",
                            "worker_ownership_reconciliation", "worker_cutover",
                        }
                    )
                    if durable_owner != "CANDIDATE" and not none_candidate_handoff:
                        raise RuntimeError(
                            "recovery_operator_intervention_required:worker_authority_contradiction"
                        )
                elif ownership in {"old", "old_starting", "old_partial"}:
                    none_inhibition_boundary = (
                        durable_owner == "NONE"
                        and phase in {"candidate_start_workers_inactive", "worker_cutover"}
                    )
                    if durable_owner != "OLD" and not none_inhibition_boundary:
                        raise RuntimeError(
                            "recovery_operator_intervention_required:worker_authority_contradiction"
                        )
                if traffic == candidate_slot:
                    # The schema-compatible candidate is already serving.  A
                    # database rollback and a switch to the old incompatible
                    # release are both forbidden; finish forward from here.
                    self.operations.verify_source(sha)
                    validate_core = getattr(
                        self.operations, "validate_candidate_core",
                        self.operations.validate_candidate,
                    )
                    validate_core(sha, candidate_slot)
                    if ownership in {"old", "old_starting", "old_partial"}:
                        try:
                            self._set_worker_authority(
                                state, interrupted, "NONE",
                                expected={"OLD", "CANDIDATE", "NONE"},
                            )
                            self.operations.deactivate_workers(previous)
                        except Exception as error:
                            interrupted.update(
                                status="operator_intervention_required",
                                phase="worker_ownership_reconciliation",
                                worker_owner="unknown",
                                rollback="retained_workers_not_proven_inactive",
                            )
                            self._checkpoint(state, interrupted)
                            raise RuntimeError(
                                "recovery_operator_intervention_required:retained_workers_not_inactive"
                            ) from error
                        ownership = self.operations.worker_ownership(
                            previous, candidate_identity
                        )
                    if ownership in {"none", "candidate_starting", "candidate_partial"}:
                        if ownership != "none":
                            self._set_worker_authority(
                                state, interrupted, "NONE",
                                expected={"CANDIDATE", "NONE"},
                            )
                            self.operations.deactivate_workers(candidate_identity)
                            ownership = self.operations.worker_ownership(
                                previous, candidate_identity
                            )
                        if ownership != "none":
                            raise RuntimeError(
                                "recovery_operator_intervention_required:candidate_workers_not_inactive"
                            )
                        self._set_worker_authority(
                            state, interrupted, "CANDIDATE", expected={"NONE"},
                        )
                        self.operations.activate_workers(sha, candidate_slot, images)
                        ownership = self.operations.worker_ownership(
                            previous, candidate_identity
                        )
                    if ownership != "candidate":
                        interrupted.update(
                            status="operator_intervention_required",
                            phase="worker_ownership_reconciliation",
                            worker_owner="unknown",
                        )
                        self._checkpoint(state, interrupted)
                        raise RuntimeError(
                            "recovery_operator_intervention_required:worker_ownership"
                        )
                    interrupted["worker_owner"] = "candidate"
                    self._checkpoint(state, interrupted)
                    return self._finish_schema_recovery(
                        state=state,
                        release=interrupted,
                        sha=sha,
                        schema=schema,
                        candidate_slot=candidate_slot,
                        previous_slot=previous_slot,
                        images=images,
                    )
                if traffic != previous_slot:
                    raise RuntimeError("interrupted_recovery_traffic_unknown")
                if ownership in {"candidate", "candidate_starting", "candidate_partial"}:
                    try:
                        self._set_worker_authority(
                            state, interrupted, "NONE",
                            expected={"CANDIDATE", "NONE"},
                        )
                        self.operations.deactivate_workers(candidate_identity)
                    except Exception as error:
                        interrupted.update(
                            status="operator_intervention_required",
                            phase="worker_ownership_reconciliation",
                            worker_owner="unknown",
                            rollback="candidate_workers_not_proven_inactive",
                        )
                        self._checkpoint(state, interrupted)
                        raise RuntimeError(
                            "recovery_operator_intervention_required:candidate_workers_not_inactive"
                        ) from error
                    ownership = self.operations.worker_ownership(previous, candidate_identity)
                if ownership not in {"none", "old", "old_starting"}:
                    interrupted.update(
                        status="operator_intervention_required",
                        phase="worker_ownership_reconciliation",
                        worker_owner="unknown",
                    )
                    self._checkpoint(state, interrupted)
                    raise RuntimeError(
                        "recovery_operator_intervention_required:candidate_workers_not_inactive"
                    )
                if ownership in {"none", "old_starting"}:
                    if ownership == "old_starting":
                        self._set_worker_authority(
                            state, interrupted, "NONE", expected={"OLD", "NONE"},
                        )
                        self.operations.deactivate_workers(previous)
                        if self.operations.worker_ownership(previous, candidate_identity) != "none":
                            raise RuntimeError("recovery_retained_worker_inhibition_unverified")
                    self._set_worker_authority(
                        state, interrupted, "OLD", expected={"NONE"},
                    )
                    self.operations.restore_workers(previous)
                elif ownership == "old":
                    self._set_worker_authority(
                        state, interrupted, "OLD", expected={"NONE", "OLD"},
                    )
                if self.operations.worker_ownership(previous, candidate_identity) != "old":
                    raise RuntimeError("recovery_retained_worker_restore_unverified")
                interrupted["worker_owner"] = "old"
                self._checkpoint(state, interrupted)
                if self.operations.resolve_serving_slot(expected_serving) != previous_slot:
                    raise RuntimeError(
                        "recovery_operator_intervention_required:traffic_changed_before_cleanup"
                    )
                self.operations.stop_candidate(
                    candidate_slot, expected_serving=expected_serving
                )
                state.pop("in_progress_release", None)
                atomic_json(self.state_file, state)

            if state.get("rollback_failure"):
                raise RuntimeError("release_rollback_failure_present")
            known_good = state.get("known_good_release")
            previous_slot = str(state.get("active_slot") or "")
            if (
                not isinstance(known_good, dict)
                or known_good.get("slot") != previous_slot
                or previous_slot not in {"blue", "green"}
                or known_good.get("sha") == sha
            ):
                raise RuntimeError("recovery_origin_state_invalid")
            if traffic != previous_slot:
                raise RuntimeError("recovery_origin_traffic_mismatch")

            backup = self.operations.validate_recovery_backup(schema)
            candidate_slot = "green" if previous_slot == "blue" else "blue"
            release = {
                "release_sha": sha,
                "candidate_slot": candidate_slot,
                "previous_known_good_release": dict(known_good),
                "previous_traffic_target": previous_slot,
                "schema_recovery": True,
                "schema": schema,
                "recovery_id": hashlib.sha256(
                    f"{sha}:{schema}:{known_good.get('sha', '')}".encode()
                ).hexdigest(),
                "backup_attestation": backup,
                "images": {},
                "started_at": utc_now().isoformat(),
                "status": "running",
                "phase": "source_validation",
                "worker_owner": "old",
            }
            self._checkpoint(state, release)
            switched = False
            switch_ambiguous = False
            old_workers_may_be_inactive = False
            try:
                self.operations.verify_source(sha)
                release["phase"] = "immutable_build"
                self._checkpoint(state, release)
                images = self.operations.build(sha, candidate_slot)
                if any(
                    "@sha256:" not in str(images.get(name) or "")
                    for name in ("backend", "frontend", "worker")
                ):
                    raise RuntimeError("immutable_image_digest_missing")
                release["images"] = images
                self._checkpoint(state, release)
                if self.operations.schema_version() != schema:
                    raise RuntimeError("recovery_live_schema_changed")
                release["phase"] = "preflight"
                self._checkpoint(state, release)
                self.operations.preflight(sha, candidate_slot, images, schema)
                release["phase"] = "candidate_start_workers_inactive"
                self._checkpoint(state, release)
                self.operations.start_candidate(sha, candidate_slot, images)
                validate_core = getattr(
                    self.operations, "validate_candidate_core",
                    self.operations.validate_candidate,
                )
                validate_core(sha, candidate_slot)
                candidate_identity = {
                    "sha": sha, "slot": candidate_slot, "images": images,
                }
                if self.operations.worker_ownership(known_good, candidate_identity) != "old":
                    raise RuntimeError("recovery_initial_worker_ownership_invalid")
                self._set_worker_authority(
                    state, release, "OLD", expected={"OLD", "CANDIDATE"},
                )

                # Queue consumers never overlap. The durable handoff is old ->
                # none here; candidate consumers start only after the stable
                # route independently proves that the candidate is serving.
                release["phase"] = "worker_cutover"
                self._checkpoint(state, release)
                # A compose-level stop can fail after stopping only a subset
                # of services.  Treat the retained workers as potentially
                # inactive before issuing the operation so every pre-switch
                # failure restores the complete retained worker set.
                old_workers_may_be_inactive = True
                self._set_worker_authority(state, release, "NONE", expected={"OLD"})
                self.operations.deactivate_workers(known_good)
                if self.operations.worker_ownership(known_good, candidate_identity) != "none":
                    raise RuntimeError("recovery_worker_quiescence_unverified")
                release["retained_workers_quiesced"] = True
                release["worker_owner"] = "none"
                self._checkpoint(state, release)

                release["phase"] = "final_pre_switch_attestation"
                self._checkpoint(state, release)
                current = self._state()
                if (
                    current.get("active_slot") != previous_slot
                    or (current.get("known_good_release") or {}).get("sha")
                    != known_good.get("sha")
                    or self.operations.resolve_serving_slot({
                        previous_slot: str(known_good.get("sha") or ""),
                        candidate_slot: sha,
                    }) != previous_slot
                ):
                    raise RuntimeError("recovery_pre_switch_state_changed")
                if self.operations.validate_recovery_backup(schema) != backup:
                    raise RuntimeError("recovery_pre_switch_backup_changed")
                # Pin again after the potentially remote backup check so a
                # concurrent schema change during that check cannot slip past.
                if self.operations.schema_version() != schema:
                    raise RuntimeError("recovery_pre_switch_state_changed")
                validate_core(sha, candidate_slot)
                if self.operations.worker_ownership(known_good, candidate_identity) != "none":
                    raise RuntimeError("recovery_worker_ownership_changed_before_switch")
                if self.operations.resolve_serving_slot({
                    previous_slot: str(known_good.get("sha") or ""),
                    candidate_slot: sha,
                }) != previous_slot:
                    raise RuntimeError("recovery_pre_switch_traffic_changed")

                release["phase"] = "traffic_switch"
                release["forward_only_after_switch"] = True
                self._checkpoint(state, release)
                try:
                    self.operations.switch_traffic(candidate_slot)
                except Exception:
                    resolved = self.operations.resolve_serving_slot({
                        previous_slot: str(known_good.get("sha") or ""),
                        candidate_slot: sha,
                    })
                    if resolved == candidate_slot:
                        switched = True
                    elif resolved == previous_slot:
                        raise
                    else:
                        switch_ambiguous = True
                        raise RuntimeError("recovery_traffic_state_ambiguous")
                else:
                    resolved = self.operations.resolve_serving_slot({
                        previous_slot: str(known_good.get("sha") or ""),
                        candidate_slot: sha,
                    })
                    if resolved != candidate_slot:
                        switch_ambiguous = True
                        raise RuntimeError("recovery_traffic_state_ambiguous")
                    switched = True
                release["phase"] = "post_switch_validation"
                self._checkpoint(state, release)
                # Traffic switching is outside Docker's restart-policy state.
                # Reconcile the durable NONE authority and actual inhibition at
                # the activation boundary; a retained restart starts nobody else.
                if self.operations.worker_ownership(known_good, candidate_identity) != "none":
                    raise RuntimeError("recovery_worker_ownership_changed_during_switch")
                self._require_worker_authority(release, "NONE")
                self._set_worker_authority(
                    state, release, "CANDIDATE", expected={"NONE"},
                )
                self.operations.activate_workers(sha, candidate_slot, images)
                if self.operations.worker_ownership(known_good, candidate_identity) != "candidate":
                    raise RuntimeError("recovery_candidate_worker_activation_unverified")
                release["workers_cut_over"] = True
                release["worker_owner"] = "candidate"
                self._checkpoint(state, release)
                self.operations.observe(sha, candidate_slot)
                if self.operations.schema_version() != schema:
                    raise RuntimeError("recovery_live_schema_changed_after_switch")
                return self._finish_schema_recovery(
                    state=state,
                    release=release,
                    sha=sha,
                    schema=schema,
                    candidate_slot=candidate_slot,
                    previous_slot=previous_slot,
                    images=images,
                )
            except Exception as error:
                release.update(
                    status="failed_forward_repair_required" if switched else "failed",
                    completed_at=utc_now().isoformat(),
                    failure_reason=type(error).__name__,
                    failure_code=str(error)[:200],
                )
                expected_serving = {
                    previous_slot: str(known_good.get("sha") or ""),
                    candidate_slot: sha,
                }
                try:
                    actual_traffic = self.operations.resolve_serving_slot(expected_serving)
                except Exception:
                    actual_traffic = None
                if switched or switch_ambiguous or actual_traffic != previous_slot:
                    # The former target cannot run the current schema.  Keep
                    # the candidate and checkpoint for an explicit forward
                    # recovery rerun; never switch traffic backward.
                    release["rollback"] = (
                        "traffic_unknown_preserve_both_targets"
                        if switch_ambiguous or actual_traffic is None
                        else "forbidden_old_target_schema_incompatible"
                    )
                    state["in_progress_release"] = dict(release)
                    atomic_json(self.state_file, state)
                    raise RuntimeError(
                        "recovery_traffic_state_ambiguous"
                        if switch_ambiguous or actual_traffic is None
                        else "recovery_post_switch_forward_repair_required"
                    ) from error
                release["rollback"] = "not_required_old_traffic_untouched"
                candidate_identity = {
                    "sha": sha, "slot": candidate_slot,
                    "images": release.get("images") or {},
                }
                try:
                    ownership = self.operations.worker_ownership(
                        known_good, candidate_identity
                    )
                    if ownership in {
                        "candidate", "candidate_starting", "candidate_partial", "overlap",
                    }:
                        self._set_worker_authority(
                            state, release, "NONE",
                            expected={"CANDIDATE", "NONE"},
                        )
                        self.operations.deactivate_workers(candidate_identity)
                        ownership = self.operations.worker_ownership(
                            known_good, candidate_identity
                        )
                    candidate_inactive = ownership in {"none", "old", "old_starting"}
                except Exception:
                    candidate_inactive = False
                if not candidate_inactive:
                    release.update(
                        status="operator_intervention_required",
                        phase="worker_ownership_reconciliation",
                        rollback="candidate_workers_not_proven_inactive",
                        worker_owner="unknown",
                    )
                    self._checkpoint(state, release)
                    raise RuntimeError(
                        "recovery_operator_intervention_required:candidate_workers_not_inactive"
                    ) from error
                if old_workers_may_be_inactive:
                    if ownership in {"none", "old_starting"}:
                        if ownership == "old_starting":
                            self.operations.deactivate_workers(known_good)
                            if self.operations.worker_ownership(known_good, candidate_identity) != "none":
                                raise RuntimeError("recovery_retained_worker_inhibition_unverified")
                        self._set_worker_authority(
                            state, release, "OLD", expected={"NONE"},
                        )
                        self.operations.restore_workers(known_good)
                    elif ownership == "old":
                        self._set_worker_authority(
                            state, release, "OLD", expected={"NONE", "OLD"},
                        )
                    if self.operations.worker_ownership(
                        known_good,
                        {"sha": sha, "slot": candidate_slot, "images": release.get("images") or {}},
                    ) != "old":
                        raise RuntimeError("recovery_retained_worker_restore_unverified")
                if self.operations.resolve_serving_slot(expected_serving) != previous_slot:
                    release.update(
                        status="operator_intervention_required",
                        phase="traffic_reconciliation",
                        rollback="traffic_changed_preserve_both_targets",
                    )
                    self._checkpoint(state, release)
                    raise RuntimeError(
                        "recovery_operator_intervention_required:traffic_changed_before_cleanup"
                    ) from error
                self.operations.stop_candidate(
                    candidate_slot, expected_serving=expected_serving
                )
                state.pop("in_progress_release", None)
                self._record(state, release)
                raise

    def _finish_schema_recovery(
        self, *, state: dict[str, Any], release: dict[str, Any], sha: str,
        schema: int, candidate_slot: str, previous_slot: str,
        images: dict[str, str],
    ) -> dict[str, Any]:
        if self.operations.resolve_serving_slot({
            previous_slot: str((release.get("previous_known_good_release") or {}).get("sha") or ""),
            candidate_slot: sha,
        }) != candidate_slot:
            raise RuntimeError("recovery_candidate_not_serving")
        if self.operations.schema_version() != schema:
            raise RuntimeError("recovery_live_schema_changed")
        self.operations.validate_candidate(sha, candidate_slot)
        previous = release.get("previous_known_good_release")
        candidate_identity = {"sha": sha, "slot": candidate_slot, "images": images}
        if not isinstance(previous, dict) or self.operations.worker_ownership(
            previous, candidate_identity
        ) != "candidate":
            raise RuntimeError("recovery_candidate_worker_ownership_invalid")

        release["phase"] = "compatible_fallback_establishment"
        self._checkpoint(state, release)
        if self.operations.resolve_serving_slot({
            previous_slot: str((release.get("previous_known_good_release") or {}).get("sha") or ""),
            candidate_slot: sha,
        }) != candidate_slot:
            raise RuntimeError("recovery_fallback_target_became_serving")
        self.operations.start_candidate(sha, previous_slot, images)
        validate_core = getattr(
            self.operations, "validate_candidate_core",
            self.operations.validate_candidate,
        )
        validate_core(sha, previous_slot)
        if self.operations.worker_ownership(previous, candidate_identity) != "candidate":
            raise RuntimeError("recovery_fallback_worker_ownership_invalid")
        if (
            self.operations.resolve_serving_slot({
                previous_slot: sha,
                candidate_slot: sha,
            }) != candidate_slot
            or self.operations.schema_version() != schema
        ):
            raise RuntimeError("recovery_state_changed_during_fallback")

        old_release = release.get("previous_known_good_release")
        known_good = {
            "sha": sha,
            "slot": candidate_slot,
            "images": images,
            "schema": schema,
            "schema_compatible_min": self.compatibility.schema_min,
            "schema_compatible_max": self.compatibility.schema_max,
            "worker_generation": release.get("worker_generation"),
            "schema_recovery": True,
            "migration_result": "not_requested",
            "recovery_id": release.get("recovery_id"),
        }
        compatible_fallback = {
            "sha": sha,
            "slot": previous_slot,
            "images": images,
            "schema": schema,
            "schema_compatible_min": self.compatibility.schema_min,
            "schema_compatible_max": self.compatibility.schema_max,
            "workers_active": False,
            "schema_recovery": True,
            "migration_result": "not_requested",
            "recovery_id": release.get("recovery_id"),
        }
        release.update(
            status="known_good",
            phase="complete",
            completed_at=utc_now().isoformat(),
            traffic_target=candidate_slot,
            fallback_slot=previous_slot,
        )
        state["active_slot"] = candidate_slot
        state["known_good_release"] = known_good
        state["compatible_fallback_release"] = compatible_fallback
        state["incompatible_pre_recovery_release"] = old_release
        state.pop("in_progress_release", None)
        state.pop("rollback_failure", None)
        state.setdefault("failed_releases", {}).pop(sha, None)
        self._record(state, release)
        return release

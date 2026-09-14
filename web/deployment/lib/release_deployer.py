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
    def validate_rollback_target(self, release: dict[str, Any], schema: int) -> dict[str, int]: ...
    def activate_workers(self, sha: str, slot: str, images: dict[str, str]) -> None: ...
    def deactivate_workers(self, release: dict[str, Any]) -> None: ...
    def restore_workers(self, release: dict[str, Any]) -> None: ...
    def switch_traffic(self, slot: str) -> None: ...
    def observe(self, sha: str, slot: str) -> None: ...
    def stop_candidate(self, slot: str) -> None: ...
    def current_traffic_slot(self) -> str: ...
    def resolve_serving_slot(self, expected: dict[str, str]) -> str | None: ...
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
        if interrupted.get("workers_cut_over"):
            self.operations.deactivate_workers({"sha": sha, "slot": slot, "images": interrupted.get("images") or {}})
            known_good = interrupted.get("previous_known_good_release")
            if isinstance(known_good, dict):
                self.operations.restore_workers(known_good)
        self.operations.stop_candidate(slot)
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
                self.operations.validate_candidate(sha, candidate_slot)
                release["phase"] = "worker_cutover"
                self._checkpoint(state, release)
                candidate_identity = {"sha": sha, "slot": candidate_slot, "images": images}
                if known_good:
                    self.operations.deactivate_workers(known_good)
                try:
                    self.operations.activate_workers(sha, candidate_slot, images)
                    self.operations.validate_candidate(sha, candidate_slot)
                    workers_cut_over = True
                    release["workers_cut_over"] = True
                    self._checkpoint(state, release)
                except Exception:
                    self.operations.deactivate_workers(candidate_identity)
                    if known_good:
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
                    "schema_compatible_min": self.compatibility.schema_min,
                    "schema_compatible_max": self.compatibility.schema_max,
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
                    self.operations.deactivate_workers({
                        "sha": sha, "slot": candidate_slot, "images": release.get("images") or {},
                    })
                    if known_good:
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
                        self.operations.deactivate_workers({
                            "sha": sha, "slot": candidate_slot, "images": release.get("images") or {},
                        })
                        if known_good:
                            self.operations.restore_workers(known_good)
                self.operations.stop_candidate(candidate_slot)
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
            traffic = self.operations.current_traffic_slot()
            known_good = state.get("known_good_release")

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
                self.operations.validate_candidate(sha, str(fallback["slot"]))
                if self.operations.schema_version() != schema:
                    raise RuntimeError("recovery_live_schema_changed")
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
                traffic = self.operations.resolve_serving_slot({
                    previous_slot: str((interrupted.get("previous_known_good_release") or {}).get("sha") or ""),
                    candidate_slot: sha,
                })
                if traffic == candidate_slot:
                    # The schema-compatible candidate is already serving.  A
                    # database rollback and a switch to the old incompatible
                    # release are both forbidden; finish forward from here.
                    self.operations.verify_source(sha)
                    self.operations.validate_candidate(sha, candidate_slot)
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
                self.operations.deactivate_workers(
                    {"sha": sha, "slot": candidate_slot, "images": images}
                )
                previous = interrupted.get("previous_known_good_release")
                if isinstance(previous, dict):
                    self.operations.restore_workers(previous)
                self.operations.stop_candidate(candidate_slot)
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
            }
            self._checkpoint(state, release)
            switched = False
            switch_ambiguous = False
            workers_cut_over = False
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
                self.operations.validate_candidate(sha, candidate_slot)

                # Queue consumers never overlap.  The old release continues
                # serving while its consumers are stopped and the candidate's
                # consumers are proven before the atomic traffic transition.
                release["phase"] = "worker_cutover"
                self._checkpoint(state, release)
                # A compose-level stop can fail after stopping only a subset
                # of services.  Treat the retained workers as potentially
                # inactive before issuing the operation so every pre-switch
                # failure restores the complete retained worker set.
                old_workers_may_be_inactive = True
                self.operations.deactivate_workers(known_good)
                release["retained_workers_quiesced"] = True
                self._checkpoint(state, release)
                try:
                    self.operations.activate_workers(sha, candidate_slot, images)
                    self.operations.validate_candidate(sha, candidate_slot)
                    workers_cut_over = True
                    release["workers_cut_over"] = True
                    self._checkpoint(state, release)
                except Exception:
                    self.operations.deactivate_workers(
                        {"sha": sha, "slot": candidate_slot, "images": images}
                    )
                    self.operations.restore_workers(known_good)
                    old_workers_may_be_inactive = False
                    raise

                release["phase"] = "final_pre_switch_attestation"
                self._checkpoint(state, release)
                current = self._state()
                if (
                    current.get("active_slot") != previous_slot
                    or (current.get("known_good_release") or {}).get("sha")
                    != known_good.get("sha")
                    or self.operations.current_traffic_slot() != previous_slot
                ):
                    raise RuntimeError("recovery_pre_switch_state_changed")
                if self.operations.validate_recovery_backup(schema) != backup:
                    raise RuntimeError("recovery_pre_switch_backup_changed")
                # Pin again after the potentially remote backup check so a
                # concurrent schema change during that check cannot slip past.
                if self.operations.schema_version() != schema:
                    raise RuntimeError("recovery_pre_switch_state_changed")
                self.operations.validate_candidate(sha, candidate_slot)

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
                if switched or switch_ambiguous:
                    # The former target cannot run the current schema.  Keep
                    # the candidate and checkpoint for an explicit forward
                    # recovery rerun; never switch traffic backward.
                    release["rollback"] = (
                        "traffic_unknown_preserve_both_targets"
                        if switch_ambiguous
                        else "forbidden_old_target_schema_incompatible"
                    )
                    state["in_progress_release"] = dict(release)
                    atomic_json(self.state_file, state)
                    raise RuntimeError(
                        "recovery_traffic_state_ambiguous"
                        if switch_ambiguous
                        else "recovery_post_switch_forward_repair_required"
                    ) from error
                release["rollback"] = "not_required_old_traffic_untouched"
                if workers_cut_over:
                    self.operations.deactivate_workers(
                        {"sha": sha, "slot": candidate_slot, "images": release.get("images") or {}}
                    )
                if old_workers_may_be_inactive:
                    self.operations.restore_workers(known_good)
                self.operations.stop_candidate(candidate_slot)
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

        release["phase"] = "compatible_fallback_establishment"
        self._checkpoint(state, release)
        self.operations.start_candidate(sha, previous_slot, images)
        self.operations.validate_candidate(sha, previous_slot)
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
            "schema_recovery": True,
            "migration_result": "not_requested",
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

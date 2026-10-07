"""Separately authorized provider402 recovery contract and transaction.

This module never invokes schema recovery, migration, normal promotion or worker
activation. Its adapter must supply fresh independently collected attestations.
It cannot be authorized by an ordinary release credential.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import fcntl
import json
import re
from pathlib import Path
from typing import Any, Protocol

from deployment.lib.control_plane_upgrade_authorization import require_upgrade_authorization
from deployment.lib.release_deployer import atomic_json
from deployment.lib.runtime_authority import write_worker_authority, runtime_mutation_lock

PROFILE = "provider402-signin"
PROVIDER_FAILURE_COMPONENTS = frozenset({
    "database", "auth", "schema", "calendar_sync_worker", "calendar_sync_queue",
    "notification_worker", "data_deletion_worker", "notification_queue",
})
ACCEPTED = frozenset({"ok", "disabled", "configured", "not_required", "development"})


@dataclass(frozen=True)
class RecoveryContract:
    sha: str
    origin_sha: str
    installed_sha: str
    origin_slot: str
    images: dict[str, str]
    production_fingerprints: dict[str, str]
    checkpoint_digest: str
    rollback_runtime_digest: str
    rehearsal_digest: str

    def validate(self, metadata: dict[str, Any]) -> None:
        for value in (self.sha, self.origin_sha, self.installed_sha):
            if not re.fullmatch(r"[0-9a-f]{40}", value):
                raise RuntimeError("provider_recovery_sha_invalid")
        if self.origin_slot not in {"blue", "green"}:
            raise RuntimeError("provider_recovery_slot_invalid")
        for value in (self.checkpoint_digest, self.rollback_runtime_digest, self.rehearsal_digest):
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                raise RuntimeError("provider_recovery_evidence_invalid")
        if set(self.images) != {"backend", "frontend"} or any(
                not re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in self.images.values()):
            raise RuntimeError("provider_recovery_images_unpinned")
        if set(self.production_fingerprints) != {"environment", "state", "upstream", "worker_authority", "controller"} or any(
                not re.fullmatch(r"[0-9a-f]{64}", value) for value in self.production_fingerprints.values()):
            raise RuntimeError("provider_recovery_provenance_invalid")
        schema = metadata.get("schema", {})
        if (metadata.get("migration_policy") != "none" or "migration_manifest" in metadata
                or schema.get("migration_class") != "none"
                or any(schema.get(key) != 115 for key in (
                    "compatible_min", "compatible_max", "target", "rollback_compatible_min", "rollback_compatible_max"))):
            raise RuntimeError("provider_recovery_non_migrating_schema115_required")

    def validate_origin(self, evidence: dict[str, Any]) -> None:
        # A status from both actual provider endpoints is required. A readiness
        # 503 alone, a transport error, or an operator guess cannot authorize.
        if evidence.get("provider_http") != {"auth": 402, "rest": 402}:
            raise RuntimeError("provider_recovery_origin_not_http402")
        expected = {"sha": self.origin_sha, "slot": self.origin_slot,
                    "installed_sha": self.installed_sha, "schema": 115,
                    "production_fingerprints": self.production_fingerprints}
        if any(evidence.get(key) != value for key, value in expected.items()):
            raise RuntimeError("provider_recovery_origin_changed")
        if any(evidence.get(key) is not True for key in (
            "canonical_repository", "clean_repository", "controller_provenance_valid",
            "traffic_identity_valid", "no_pending_release_or_migration", "source_schema115",
        )):
            raise RuntimeError("provider_recovery_origin_unsafe")
        for endpoint in ("stable", "active"):
            components = evidence.get("readiness", {}).get(endpoint)
            if not isinstance(components, dict) or not {"environment", "redis", "storage", "admin_mfa_policy", "parser_isolation"}.issubset(components):
                raise RuntimeError("provider_recovery_origin_readiness_missing")
            for name, value in components.items():
                if value in ACCEPTED:
                    continue
                if name in PROVIDER_FAILURE_COMPONENTS and value == "unavailable":
                    continue
                # A known stale hosted-era backup must be replaced by a freshly
                # verified LOCAL checkpoint, never by touching the old marker.
                if name == "backup_freshness" and value == "stale" and evidence.get("local_checkpoint_valid") is True:
                    continue
                raise RuntimeError("provider_recovery_unrelated_degradation:" + name)

    def validate_target(self, evidence: dict[str, Any]) -> None:
        if (evidence.get("sha") != self.sha or evidence.get("images") != self.images
                or evidence.get("schema") != 115 or evidence.get("migrations_executed") is not False
                or evidence.get("supabase_url") != "http://madar-supabase:8000"
                or evidence.get("network") != "madar-supabase-client"
                or evidence.get("checkpoint_digest") != self.checkpoint_digest
                or evidence.get("rollback_runtime_digest") != self.rollback_runtime_digest):
            raise RuntimeError("provider_recovery_target_contract_invalid")
        for key in ("auth", "rest", "storage", "schema", "all_supabase_services",
                    "internal_network", "loopback_ports", "auth_linkage", "mfa_aal2",
                    "tenant_isolation", "business_write_fence", "no_consumers",
                    "checkpoint_valid", "rollback_live_local_compatible", "image_provenance"):
            if evidence.get("checks", {}).get(key) is not True:
                raise RuntimeError("provider_recovery_target_unready:" + key)


class RecoveryOperations(Protocol):
    def authorize(self, contract: RecoveryContract) -> None: ...
    def origin_evidence(self) -> dict: ...
    def target_evidence(self) -> dict: ...
    def prepare_candidate(self, contract: RecoveryContract, slot: str) -> None: ...
    def inhibit_all_workers(self) -> None: ...
    def require_all_workers_off(self) -> None: ...
    def switch_recovery_traffic(self, contract: RecoveryContract, slot: str) -> None: ...
    def smoke_recovery(self, contract: RecoveryContract, slot: str) -> None: ...
    def switch_local_rollback(self, contract: RecoveryContract) -> None: ...
    def verify_local_rollback(self, contract: RecoveryContract) -> None: ...


def require_provider_recovery_authorization(contract: RecoveryContract) -> None:
    digest = hashlib.sha256(json.dumps(contract.__dict__, sort_keys=True).encode()).hexdigest()
    require_upgrade_authorization(contract.sha, required_operation=PROFILE,
                                 required_schema=115, require_rehearsal=True,
                                 required_context_digest=digest)


def reject_ordinary_operation(state_root: Path) -> None:
    """Prevent ordinary automation or migration from taking over recovery."""
    if (state_root / "provider-recovery.json").exists():
        raise RuntimeError("provider_recovery_requires_separate_operator_exit")


class ProviderRecoveryTransaction:
    def __init__(self, state_root: Path, operations: RecoveryOperations):
        self.root = state_root
        self.ops = operations

    def activate(self, contract: RecoveryContract, metadata: dict) -> dict:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.root / "deploy.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return self._activate_locked(contract, metadata)

    def _activate_locked(self, contract: RecoveryContract, metadata: dict) -> dict:
        contract.validate(metadata)
        require_provider_recovery_authorization(contract)
        self.ops.authorize(contract)
        path = self.root / "provider-recovery.json"
        if path.exists():
            raise RuntimeError("provider_recovery_already_present_operator_resume_required")
        contract.validate_origin(self.ops.origin_evidence())
        contract.validate_target(self.ops.target_evidence())
        slot = "green" if contract.origin_slot == "blue" else "blue"
        generation = hashlib.sha256(json.dumps(contract.__dict__, sort_keys=True).encode()).hexdigest()
        state = {"version": 1, "profile": PROFILE, "phase": "prepared", "sha": contract.sha,
                 "slot": slot, "schema": 115, "migration_policy": "none", "worker_owner": "RECOVERY",
                 "checkpoint_digest": contract.checkpoint_digest,
                 "rollback_runtime_digest": contract.rollback_runtime_digest,
                 "restore_database_on_rollback": False}
        # Durable interlock precedes every production operation. A crash never
        # silently resumes normal deployment or starts old-slot consumers.
        atomic_json(path, state)
        try:
            self.ops.prepare_candidate(contract, slot)
            contract.validate_origin(self.ops.origin_evidence())
            contract.validate_target(self.ops.target_evidence())
            self.ops.inhibit_all_workers()
            self.ops.require_all_workers_off()
            with runtime_mutation_lock(self.root):
                write_worker_authority(self.root, generation=generation, owner="RECOVERY",
                    old={"sha": contract.origin_sha, "slot": contract.origin_slot},
                    candidate={"sha": contract.sha, "slot": slot})
            state["phase"] = "switch_pending"
            atomic_json(path, state)
            self.ops.switch_recovery_traffic(contract, slot)
            self.ops.require_all_workers_off()
            self.ops.smoke_recovery(contract, slot)
            state["phase"] = "active"
            atomic_json(path, state)
            return state
        except Exception:
            # Switching may have succeeded before an exception/timeout. Never
            # route to hosted HTTP, reactivate workers, or restore old Auth.
            if state["phase"] != "switch_pending":
                state["phase"] = "pre_switch_failed_operator_review_required"
                atomic_json(path, state)
                raise
            state["phase"] = "rollback_pending"
            atomic_json(path, state)
            self.ops.require_all_workers_off()
            self.ops.switch_local_rollback(contract)
            self.ops.verify_local_rollback(contract)
            self.ops.require_all_workers_off()
            state["phase"] = "local_rollback_active"
            atomic_json(path, state)
            raise

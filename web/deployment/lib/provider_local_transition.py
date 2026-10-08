"""Separately governed graduation from provider402 to normal local production.

Normal deployment remains unable to consume recovery state. This transaction
does not execute migrations or restore data. Its privileged adapter must verify
the final reconciliation, independently restored checkpoint and off-host proof.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re

from deployment.lib.provider_recovery_bootstrap import exclusive_lock
from deployment.lib.provider_recovery_runtime import digest, protected
from deployment.lib.release_deployer import atomic_json

GATES = frozenset({
    "exact_main", "exact_images", "schema115", "no_migrations", "human_auth",
    "mfa_aal2", "tenant_isolation", "synthetic_cleanup", "source_fence",
    "typed_reconciliation", "storage_integrity", "fresh_checkpoint",
    "independent_restore", "offhost_backup", "backup_freshness", "auth_smtp",
    "local_supabase_health", "local_fallback", "queue_inventory",
    "transition_rehearsal", "failure_injection",
})
SMOKE_GATES = frozenset({
    "exact_release", "schema115", "no_migrations", "frontend", "api", "readiness",
    "auth", "mfa_aal2", "tenant_isolation", "assets", "range_mime_cache",
    "business_reads", "reversible_business_smoke", "security", "no_internal_url_leak",
    "workers_healthy", "one_worker_owner", "queues", "auth_smtp", "backup_freshness",
    "local_supabase_health", "local_fallback", "write_fence",
})


@dataclass(frozen=True)
class LocalTransitionContract:
    sha: str
    images: dict[str, str]
    recovery_context: str
    checkpoint_digest: str
    reconciliation_digest: str
    evidence_digest: str
    production_fingerprints: dict[str, str]

    def validate(self, metadata: dict) -> None:
        from deployment.lib.provider_recovery import RecoveryContract
        # Reuse the exact non-migrating schema predicate, not schema recovery.
        RecoveryContract(self.sha, self.sha, self.sha, "green", self.images,
            {key: "0" * 64 for key in ("environment", "state", "upstream", "worker_authority", "controller")},
            self.checkpoint_digest, self.reconciliation_digest, self.evidence_digest).validate(metadata)
        if not re.fullmatch(r"[0-9a-f]{64}", self.recovery_context):
            raise RuntimeError("local_transition_recovery_binding_invalid")
        if set(self.production_fingerprints) != {
                "environment", "state", "upstream", "worker_authority", "controller", "recovery", "traffic"} or any(
                not re.fullmatch(r"[0-9a-f]{64}", value) for value in self.production_fingerprints.values()):
            raise RuntimeError("local_transition_fingerprint_binding_invalid")


def validate_evidence(contract, report):
    if (digest(report) != contract.evidence_digest or report.get("schema") != 115
            or report.get("source_sha") != contract.sha or report.get("images") != contract.images
            or report.get("checkpoint_digest") != contract.checkpoint_digest
            or report.get("reconciliation_digest") != contract.reconciliation_digest
            or report.get("recovery_context") != contract.recovery_context
            or report.get("migrations_executed") is not False
            or report.get("unexplained_differences") != 0
            or report.get("database_restore_on_runtime_rollback") is not False):
        raise RuntimeError("local_transition_evidence_binding_invalid")
    from deployment.lib.provider_recovery_phases import EMERGENCY_MODE
    mode = report.get("acceptance_mode", "human")
    if mode not in {"human", EMERGENCY_MODE}:
        raise RuntimeError("local_transition_unknown_acceptance_mode")
    required = GATES if mode == "human" else (GATES - {"human_auth"}) | {"automated_auth"}
    if mode == EMERGENCY_MODE and not re.fullmatch(r"[0-9a-f]{64}", report.get("auth_acceptance_digest", "")):
        raise RuntimeError("local_transition_acceptance_binding_missing")
    gates = report.get("gates", {})
    if set(gates) != required or any(value != "PASS" for value in gates.values()):
        raise RuntimeError("local_transition_mandatory_gate_incomplete")


class LocalProviderTransition:
    """Durable stage boundaries; only FINALIZE grants public business writes.

    The adapter has no SQL mutation/restore capability. Before normal writes,
    failure inhibits consumers and switches only to the registered local runtime.
    After writes, the same rollback first fences requests and preserves live data.
    """
    def __init__(self, root: Path, operations):
        self.root, self.ops = root, operations
        self.path = operations.transaction_path

    def _require(self, contract, metadata):
        if os.geteuid() != 0:
            raise RuntimeError("local_transition_root_entry_required")
        contract.validate(metadata)
        self.ops.require_authorization(contract)
        validate_evidence(contract, self.ops.evidence())
        self.ops.verify_immutable_inputs(contract)

    def _state(self, contract, phases):
        state = json.loads(protected(self.path, private=True).read_text())
        if state.get("contract_digest") != digest(asdict(contract)) or state.get("phase") not in phases:
            raise RuntimeError("local_transition_phase_or_binding_invalid")
        if state.get("fingerprints") != self.ops.fingerprints():
            raise RuntimeError("local_transition_production_changed")
        return state

    def _record(self, state, phase):
        observed = self.ops.fingerprints()
        permitted = {
            "handoff_pending": set(), "workers_ready": {"worker_authority"},
            "switch_pending": set(), "serving_read_only": {"upstream", "traffic"},
            "resume_pending": set(), "normal": {"environment", "state", "recovery", "traffic"},
            "rollback_pending": set(), "local_rollback_active": {"worker_authority", "upstream", "recovery", "traffic"},
            "rollback_required": {"worker_authority", "upstream", "traffic"},
            "prepare_pending": set(), "prepared": set(),
        }[phase]
        prior = state.get("fingerprints", observed)
        if {key for key in prior if prior[key] != observed[key]} - permitted:
            raise RuntimeError("local_transition_unexpected_fingerprint_change")
        state["fingerprints"] = observed
        state["phase"] = phase
        atomic_json(self.path, state)
        os.chmod(self.path, 0o600)

    def prepare(self, contract, metadata):
        self._require(contract, metadata)
        with exclusive_lock(self.root / "deploy.lock"):
            if self.path.exists() or self.path.is_symlink():
                raise RuntimeError("local_transition_already_present")
            if self.ops.fingerprints() != contract.production_fingerprints:
                raise RuntimeError("local_transition_production_changed")
            self.ops.require_recovery_active(contract.recovery_context)
            self.ops.require_all_workers_off()
            self.ops.verify_local_fallback()
            state = {"version": 1, "contract_digest": digest(asdict(contract)),
                     "sha": contract.sha, "images": contract.images, "schema": 115,
                     "migration_policy": "none", "database_restore": False,
                     "normal_writes_ever_enabled": False}
            self._record(state, "prepare_pending")
            self.ops.set_write_authority(contract, "READ_ONLY")
            self.ops.prepare_normal_candidate(contract)
            self.ops.verify_private_candidate(contract, workers_required=False)
            self.ops.require_all_workers_off()
            self._record(state, "prepared")
            return state

    def handoff(self, contract, metadata):
        self._require(contract, metadata)
        with exclusive_lock(self.root / "deploy.lock"):
            state = self._state(contract, {"prepared"})
            self.ops.require_write_authority(contract, "READ_ONLY")
            self.ops.require_all_workers_off()
            self._record(state, "handoff_pending")
            try:
                self.ops.designate_single_normal_owner(contract)
                for kind in ("notification", "calendar-sync", "data-deletion"):
                    self.ops.start_and_verify_worker(contract, kind)
                    self.ops.require_single_owner(contract)
                self.ops.verify_private_candidate(contract, workers_required=True)
                self._record(state, "workers_ready")
            except Exception:
                self.ops.inhibit_all_workers()
                self.ops.require_all_workers_off()
                self._record(state, "rollback_required")
                raise
            return state

    def switch(self, contract, metadata):
        self._require(contract, metadata)
        with exclusive_lock(self.root / "deploy.lock"):
            state = self._state(contract, {"workers_ready"})
            self.ops.require_write_authority(contract, "READ_ONLY")
            self.ops.require_single_owner(contract)
            self.ops.verify_local_fallback()
            self.ops.verify_private_candidate(contract, workers_required=True)
            self._record(state, "switch_pending")
            try:
                self.ops.switch_normal_traffic(contract)
                self.ops.verify_serving_candidate(contract)
                self.ops.require_write_authority(contract, "READ_ONLY")
                self._record(state, "serving_read_only")
            except Exception:
                # The durable pending state is rollback-authorized even if the
                # proxy reload partially completed. Never use hosted traffic.
                self._record(state, "rollback_required")
                raise
            return state

    def finalize(self, contract, metadata):
        self._require(contract, metadata)
        with exclusive_lock(self.root / "deploy.lock"):
            state = self._state(contract, {"serving_read_only"})
            self.ops.require_write_authority(contract, "READ_ONLY")
            self.ops.require_single_owner(contract)
            self.ops.verify_serving_candidate(contract)
            smoke = self.ops.final_smoke(contract)
            if set(smoke) != SMOKE_GATES or any(value != "PASS" for value in smoke.values()):
                raise RuntimeError("local_transition_final_smoke_incomplete")
            # Record the irreversibility boundary before granting writes. A
            # crash here permits only current-data runtime rollback.
            state["normal_writes_ever_enabled"] = True
            state["final_smoke_digest"] = digest(smoke)
            state["pre_resume_fingerprints"] = self.ops.fingerprints()
            self._record(state, "resume_pending")
            self.ops.retire_hosted_writers(contract)
            self.ops.commit_normal_release_state(contract)
            self.ops.set_write_authority(contract, "NORMAL")
            self.ops.require_write_authority(contract, "NORMAL")
            self._record(state, "normal")
            return state

    def rollback(self, contract, metadata):
        if os.geteuid() != 0:
            raise RuntimeError("local_transition_root_entry_required")
        contract.validate(metadata)
        self.ops.require_authorization(contract)
        validate_evidence(contract, self.ops.evidence())
        self.ops.verify_runtime_rollback_inputs(contract)
        with exclusive_lock(self.root / "deploy.lock"):
            state = self._state(contract, {"prepare_pending", "prepared", "handoff_pending", "workers_ready",
                "switch_pending", "serving_read_only", "rollback_required", "resume_pending", "normal", "rollback_pending"})
            self._record(state, "rollback_pending")
            self.ops.set_write_authority(contract, "READ_ONLY")
            self.ops.inhibit_all_workers()
            self.ops.require_all_workers_off()
            self.ops.verify_local_fallback()
            self.ops.switch_current_data_local_fallback(contract)
            self.ops.verify_local_fallback_serving()
            self._record(state, "local_rollback_active")
            return state

    def restart_worker(self, contract, metadata, kind):
        """Repair only the existing normal owner, never hand off or promote."""
        if kind not in {"notification", "calendar-sync", "data-deletion"}:
            raise RuntimeError("local_transition_worker_kind_invalid")
        if os.geteuid() != 0:
            raise RuntimeError("local_transition_root_entry_required")
        contract.validate(metadata)
        self.ops.require_authorization(contract)
        validate_evidence(contract, self.ops.evidence())
        self.ops.verify_runtime_rollback_inputs(contract)
        with exclusive_lock(self.root / "deploy.lock"):
            state = self._state(contract, {"normal"})
            self.ops.require_write_authority(contract, "NORMAL")
            self.ops.require_single_owner(contract)
            self.ops.restart_existing_worker(contract, kind)
            self.ops.require_single_owner(contract)
            if state["fingerprints"] != self.ops.fingerprints():
                raise RuntimeError("local_transition_repair_changed_authority")
            return state

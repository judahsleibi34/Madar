"""Protected recovery phases. Preparation receipts never authorize activation."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from deployment.lib.provider_recovery import RecoveryContract
from deployment.lib.release_deployer import atomic_json

PREPARE = "PREPARE_AND_REHEARSE"
AUTHORIZE = "AUTHORIZE_ACTIVATION"
ACTIVATE = "ACTIVATE_RECOVERY"
ACTIVATION_RECEIPT = Path("/var/lib/madar-control-plane/provider402/activation-authorization.json")
ACTIVATION_REHEARSAL = Path("/var/lib/madar-control-plane/provider402/rehearsal.json")
MANDATORY_GATES = frozenset({
    "human_auth", "invalid_password", "logout_relogin", "refresh_persistence",
    "accessible_mfa", "aal2", "tenant_isolation", "business_write_fence",
    "both_slot_worker_inhibition_rehearsal", "passive_local_fallback",
    "traffic_switch_rehearsal", "interruption_recovery", "runtime_only_local_rollback",
    "failure_injection_suite", "checkpoint",
})
PRECONDITIONS = frozenset({
    "exact_contract", "exact_source", "pinned_images", "schema115", "no_migrations",
    "provider402_origin", "valid_checkpoint", "provenance_match",
    "private_target_health", "write_fence_source_validation",
})


def sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def preparation_binding(contract: RecoveryContract, metadata: dict):
    contract.validate(metadata)
    fields = asdict(contract)
    # Completed evidence cannot hash itself. The preparation identity binds
    # all immutable inputs; the final contract additionally binds the report.
    fields.pop("rehearsal_digest")
    return {"contract": fields, "schema_contract": metadata}


def validate_completed_rehearsal(contract, metadata, report):
    expected = sha256(preparation_binding(contract, metadata))
    if (report.get("format") != 2 or report.get("phase") != PREPARE
            or report.get("preparation_binding") != expected
            or report.get("production_modified") is not False
            or report.get("migrations_executed") is not False
            or report.get("schema") != 115):
        raise RuntimeError("recovery_rehearsal_binding_invalid")
    preconditions = report.get("preconditions", {})
    if set(preconditions) != PRECONDITIONS or any(value != "PASS" for value in preconditions.values()):
        raise RuntimeError("recovery_preparation_evidence_incomplete")
    checks = report.get("checks", {})
    if set(checks) != MANDATORY_GATES:
        raise RuntimeError("recovery_activation_evidence_missing")
    for name in sorted(MANDATORY_GATES):
        if checks[name] != "PASS":
            raise RuntimeError("recovery_activation_evidence_incomplete:" + name)
    origin = report.get("origin_evidence")
    if not isinstance(origin, dict):
        raise RuntimeError("recovery_provider_evidence_missing")
    contract.validate_origin(origin)
    return sha256(origin)


def require_completed_evidence(contract, metadata, report_path=ACTIVATION_REHEARSAL):
    """Validate rehearsal inputs before installation; never authorize traffic."""
    from deployment.lib.provider_recovery_runtime import protected, file_digest
    report_path = protected(report_path, private=True)
    if file_digest(report_path) != contract.rehearsal_digest:
        raise RuntimeError("recovery_rehearsal_digest_changed")
    report = json.loads(report_path.read_text())
    validate_completed_rehearsal(contract, metadata, report)
    return report


def authorize_activation(contract, metadata, report_path, receipt_path=ACTIVATION_RECEIPT):
    """Phase 2: issue a root-protected receipt after every required gate passes.

    No caller option can waive a gate. Credential issuance is a separate final
    step and must consume this receipt before accepting activation operations.
    """
    from deployment.lib.provider_recovery_runtime import protected, file_digest
    import os
    if os.geteuid() != 0:
        raise RuntimeError("recovery_root_authorization_required")
    report_path = protected(report_path, private=True)
    report_digest = file_digest(report_path)
    if report_digest != contract.rehearsal_digest:
        raise RuntimeError("recovery_rehearsal_digest_changed")
    report = json.loads(report_path.read_text())
    provider_digest = validate_completed_rehearsal(contract, metadata, report)
    if receipt_path.exists() or receipt_path.is_symlink():
        raise RuntimeError("recovery_activation_authorization_already_present")
    from deployment.lib.provider_recovery import require_provider_recovery_authorization
    require_provider_recovery_authorization(contract)
    receipt = {"format": 2, "phase": AUTHORIZE, "contract_digest": sha256(asdict(contract)),
               "preparation_binding": sha256(preparation_binding(contract, metadata)),
               "schema": 115, "rehearsal_digest": report_digest,
               "provider_evidence_digest": provider_digest,
               "authorized_at": datetime.now(timezone.utc).isoformat()}
    atomic_json(receipt_path, receipt)
    os.chmod(receipt_path, 0o600)
    return receipt


def require_activation_evidence(contract, metadata, receipt_path=ACTIVATION_RECEIPT,
                                report_path=ACTIVATION_REHEARSAL):
    """Mandatory at every production mutation boundary, never a preparation flag."""
    from deployment.lib.provider_recovery_runtime import protected, file_digest
    receipt = json.loads(protected(receipt_path, private=True).read_text())
    report = json.loads(protected(report_path, private=True).read_text())
    provider_digest = validate_completed_rehearsal(contract, metadata, report)
    if (receipt.get("format") != 2 or receipt.get("phase") != AUTHORIZE
            or receipt.get("contract_digest") != sha256(asdict(contract))
            or receipt.get("preparation_binding") != sha256(preparation_binding(contract, metadata))
            or receipt.get("schema") != 115
            or receipt.get("rehearsal_digest") != contract.rehearsal_digest
            or file_digest(report_path) != contract.rehearsal_digest
            or receipt.get("provider_evidence_digest") != provider_digest):
        raise RuntimeError("recovery_activation_authorization_invalid")
    return receipt


class PreparationTransaction:
    """Phase 1 only. Its operations expose only isolated mutation capabilities."""
    def __init__(self, operations):
        self.ops = operations

    def prepare(self, contract, metadata):
        contract.validate(metadata)
        self.ops.require_isolated()
        preconditions, origin = self.ops.collect_preconditions(contract, metadata)
        if set(preconditions) != PRECONDITIONS or any(v != "PASS" for v in preconditions.values()):
            raise RuntimeError("recovery_preparation_evidence_incomplete")
        contract.validate_origin(origin)
        report = {"format": 2, "phase": PREPARE,
                  "preparation_binding": sha256(preparation_binding(contract, metadata)),
                  "schema": 115, "production_modified": False, "migrations_executed": False,
                  "preconditions": preconditions, "origin_evidence": origin,
                  "checks": {name: "PENDING" for name in sorted(MANDATORY_GATES)}}
        self.ops.prepare_isolated_candidate_and_fallback(contract)
        self.ops.require_isolated()
        self.ops.save_preparation_report(report)
        return report

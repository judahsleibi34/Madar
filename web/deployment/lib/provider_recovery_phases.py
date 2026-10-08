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
PREPARATION_REHEARSAL = Path("/var/lib/madar-control-plane/provider402/rehearsal.json")
ACTIVATION_REHEARSAL = Path("/var/lib/madar-control-plane/provider402/completed-rehearsal.json")
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

EMERGENCY_MODE = "operator-authorized-automated-exact-images-v1"
EMERGENCY_AUTHORIZATION = Path("/var/lib/madar-control-plane/provider402/emergency-operator-authorization.json")
AUTOMATED_AUTH_CHECKS = frozenset({
    "password_login", "invalid_password", "logout_invalidation", "refresh_rotation",
    "totp_challenge_verification", "aal2_required", "tenant_dashboard_read",
    "cross_tenant_denial", "recovery_business_mutation_denied", "browser_api_connectivity",
})


def acceptance_gates(report):
    mode = report.get("acceptance_mode", "human")
    if mode == "human":
        return MANDATORY_GATES
    if mode == EMERGENCY_MODE:
        return (MANDATORY_GATES - {"human_auth"}) | {"automated_auth"}
    raise RuntimeError("recovery_unknown_acceptance_mode")


def validate_automated_acceptance(contract, metadata, report, authorization, *, authorized_at=None):
    """Explicit operator exception, never represented as human verification."""
    if "human_evidence" in report:
        raise RuntimeError("recovery_emergency_must_not_claim_human_evidence")
    now = datetime.now(timezone.utc)
    try:
        effective = now if authorized_at is None else datetime.fromisoformat(authorized_at)
        issued = datetime.fromisoformat(authorization["issued_at"])
        expires = datetime.fromisoformat(authorization["expires_at"])
    except (KeyError, TypeError, ValueError):
        raise RuntimeError("recovery_emergency_authorization_invalid") from None
    if (issued.tzinfo is None or expires.tzinfo is None or not issued <= effective < expires
            or effective.tzinfo is None or effective > now
            or (expires-issued).total_seconds() > 86400
            or authorization.get("scope") != EMERGENCY_MODE
            or authorization.get("operator") != "Madar production operator"
            or authorization.get("explicitly_authorized") is not True
            or authorization.get("preparation_binding") != sha256(preparation_binding(contract, metadata))):
        raise RuntimeError("recovery_emergency_authorization_invalid")
    evidence = report.get("automated_evidence", {})
    if (evidence.get("source_sha") != contract.sha or evidence.get("images") != contract.images
            or evidence.get("schema") != 115 or evidence.get("isolated_fixture") is not True
            or evidence.get("customer_credentials_used") is not False
            or evidence.get("sensitive_values_recorded") is not False
            or evidence.get("migrations_executed") is not False
            or evidence.get("checks") != {key: "PASS" for key in AUTOMATED_AUTH_CHECKS}
            or report.get("operator_authorization_digest") != sha256(authorization)):
        raise RuntimeError("recovery_exact_image_automated_evidence_missing")
    return sha256({"mode": EMERGENCY_MODE, "authorization": authorization, "evidence": evidence})


def auth_acceptance_digest(contract, metadata, report, *, authorized_at=None):
    if report.get("acceptance_mode", "human") == EMERGENCY_MODE:
        from deployment.lib.provider_recovery_runtime import protected
        authorization = json.loads(protected(EMERGENCY_AUTHORIZATION, private=True).read_text())
        return validate_automated_acceptance(contract, metadata, report, authorization, authorized_at=authorized_at)
    human = report.get("human_evidence")
    if (not isinstance(human, dict) or human.get("source_sha") != contract.sha
            or human.get("images") != contract.images
            or human.get("results") != {"existing_login": "PASS", "accessible_mfa_aal2": "PASS",
                "tenant_dashboard_read": "PASS", "business_mutation_denied": "PASS"}):
        raise RuntimeError("recovery_exact_image_human_evidence_missing")
    return sha256(human)


def sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def preparation_binding(contract: RecoveryContract, metadata: dict):
    contract.validate(metadata)
    fields = asdict(contract)
    # Preparation evidence cannot hash itself. The preparation identity binds
    # all immutable inputs; the contract additionally binds that frozen report.
    fields.pop("rehearsal_digest")
    return {"contract": fields, "schema_contract": metadata}


def validate_preparation_rehearsal(contract, metadata, report):
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
    if set(checks) != acceptance_gates(report) or any(value not in {"PASS", "PENDING"} for value in checks.values()):
        raise RuntimeError("recovery_preparation_gate_shape_invalid")
    origin = report.get("origin_evidence")
    if not isinstance(origin, dict):
        raise RuntimeError("recovery_provider_evidence_missing")
    contract.validate_origin(origin)
    return sha256(origin)


def validate_completed_rehearsal(contract, metadata, report, *, authorized_at=None):
    provider_digest = validate_preparation_rehearsal(contract, metadata, report)
    checks = report.get("checks", {})
    if set(checks) != acceptance_gates(report):
        raise RuntimeError("recovery_activation_evidence_missing")
    for name in sorted(acceptance_gates(report)):
        if checks[name] != "PASS":
            raise RuntimeError("recovery_activation_evidence_incomplete:" + name)
    auth_acceptance_digest(contract, metadata, report, authorized_at=authorized_at)
    return provider_digest


def require_preparation_evidence(contract, metadata, report_path=PREPARATION_REHEARSAL):
    """Immutable pre-human installation inputs; never authorize activation.

    Completion is a separate root-protected record. Updating final human or
    rollback evidence must not rewrite the contract/credential needed to
    prepare the environment in which that evidence is obtained.
    """
    from deployment.lib.provider_recovery_runtime import protected, file_digest
    report_path = protected(report_path, private=True)
    if file_digest(report_path) != contract.rehearsal_digest:
        raise RuntimeError("recovery_rehearsal_digest_changed")
    report = json.loads(report_path.read_text())
    validate_preparation_rehearsal(contract, metadata, report)
    return report


def authorize_activation(contract, metadata, report_path, receipt_path=ACTIVATION_RECEIPT):
    """Phase 2: issue a root-protected receipt after every required gate passes.

    No caller option can waive a gate. The installed-controller credential is
    required here; activation additionally consumes this completed receipt.
    """
    from deployment.lib.provider_recovery_runtime import protected, file_digest
    import os
    if os.geteuid() != 0:
        raise RuntimeError("recovery_root_authorization_required")
    report_path = protected(report_path, private=True)
    report_digest = file_digest(report_path)
    require_preparation_evidence(contract, metadata)
    report = json.loads(report_path.read_text())
    provider_digest = validate_completed_rehearsal(contract, metadata, report)
    if receipt_path.exists() or receipt_path.is_symlink():
        raise RuntimeError("recovery_activation_authorization_already_present")
    from deployment.lib.provider_recovery import require_provider_recovery_authorization
    require_provider_recovery_authorization(contract)
    receipt = {"format": 2, "phase": AUTHORIZE, "contract_digest": sha256(asdict(contract)),
               "preparation_binding": sha256(preparation_binding(contract, metadata)),
               "schema": 115, "rehearsal_digest": report_digest,
               "preparation_evidence_digest": contract.rehearsal_digest,
               "acceptance_mode": report.get("acceptance_mode", "human"),
               "human_evidence_digest": (sha256(report["human_evidence"]) if report.get("acceptance_mode", "human") == "human" else None),
               "auth_acceptance_digest": auth_acceptance_digest(contract, metadata, report),
               "provider_evidence_digest": provider_digest,
               "authorized_at": datetime.now(timezone.utc).isoformat()}
    atomic_json(receipt_path, receipt)
    os.chmod(receipt_path, 0o600)
    return receipt


def require_activation_evidence(contract, metadata, receipt_path=ACTIVATION_RECEIPT,
                                report_path=ACTIVATION_REHEARSAL):
    """Mandatory at every production mutation boundary, never a preparation flag."""
    from deployment.lib.provider_recovery_runtime import protected, file_digest
    require_preparation_evidence(contract, metadata)
    receipt = json.loads(protected(receipt_path, private=True).read_text())
    report = json.loads(protected(report_path, private=True).read_text())
    provider_digest = validate_completed_rehearsal(contract, metadata, report, authorized_at=receipt.get("authorized_at"))
    if (receipt.get("format") != 2 or receipt.get("phase") != AUTHORIZE
            or receipt.get("contract_digest") != sha256(asdict(contract))
            or receipt.get("preparation_binding") != sha256(preparation_binding(contract, metadata))
            or receipt.get("schema") != 115
            or receipt.get("preparation_evidence_digest") != contract.rehearsal_digest
            or receipt.get("rehearsal_digest") != file_digest(report_path)
            or receipt.get("acceptance_mode", "human") != report.get("acceptance_mode", "human")
            or receipt.get("auth_acceptance_digest") != auth_acceptance_digest(contract, metadata, report, authorized_at=receipt.get("authorized_at"))
            or receipt.get("human_evidence_digest") != (sha256(report["human_evidence"]) if report.get("acceptance_mode", "human") == "human" else None)
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

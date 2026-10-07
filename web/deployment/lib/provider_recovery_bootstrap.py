"""Root-owned, separately authorized provider402 installation transaction.

The trusted staging entrypoint must supply independently verified operations.
Normal upgrade authorization and schema recovery are deliberately not reused.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets

from deployment.lib.provider_recovery import PROFILE, RecoveryContract
from deployment.lib.provider_recovery_runtime import digest, protected
from deployment.lib.release_deployer import atomic_json


@contextmanager
def exclusive_lock(path: Path):
    if path.is_symlink():
        raise RuntimeError("recovery_lock_symlink")
    with path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def installation_interlock(contract):
    return {"version": 1, "approved_sha": contract.sha, "operation": PROFILE,
            "schema": 115, "context_sha256": digest(contract.__dict__),
            "rehearsal_sha256": contract.rehearsal_digest,
            "status": "provider_recovery_installing"}


def issue_authorization(contract: RecoveryContract, runtime: Path):
    """Write a one-time root credential bound to the complete reviewed packet.

    Only root may call this. A retained interlock prevents unattended normal
    deployments even after the transient credential is revoked.
    """
    if os.geteuid() != 0:
        raise RuntimeError("recovery_root_authorization_required")
    from deployment.lib.provider_recovery_phases import require_completed_evidence
    # Installed-controller witness precedes issuance. This credential alone
    # cannot activate traffic: Phase 2 and every Phase-3 guard remain required.
    metadata = json.loads(protected(runtime / "schema-contract.json").read_text())
    require_completed_evidence(contract, metadata)
    protected(runtime / "contract.json", private=True)
    stored = json.loads((runtime / "contract.json").read_text())
    if stored != contract.__dict__:
        raise RuntimeError("recovery_authorization_contract_changed")
    witness = json.loads(protected(runtime / "installation.json", private=True).read_text())
    if witness != {"contract_digest": digest(contract.__dict__), "source": contract.sha, "installed": True}:
        raise RuntimeError("recovery_installation_witness_invalid")
    credential = runtime / "authorized.credential"
    interlock = runtime / "in-progress.json"
    if credential.exists() or credential.is_symlink():
        raise RuntimeError("recovery_existing_authorization_requires_operator_review")
    if json.loads(protected(interlock).read_text()) != installation_interlock(contract):
        raise RuntimeError("recovery_installation_interlock_invalid")
    token = secrets.token_urlsafe(48)
    document = {"version": 1, "approved_sha": contract.sha, "operation": PROFILE,
                "schema": 115, "context_sha256": digest(contract.__dict__),
                "rehearsal_sha256": contract.rehearsal_digest}
    # Exclusive creation; no previous credential or interlock is overwritten.
    fd = os.open(credential, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(dict(document, token=token), handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    atomic_json(interlock, dict(document, authorization_sha256=hashlib.sha256(token.encode()).hexdigest(),
                               status="provider_recovery_authorized"))
    os.chmod(interlock, 0o644)
    return credential


class TrustedRecoveryBootstrap:
    """Installation ordering shared by the root launcher and fixture rehearsal.

    Installation methods must be the existing trusted staging/filesystem/backup
    operations. Completed evidence and explicit root approval precede install;
    the credential is issued only after successful installation attestation.
    """
    def __init__(self, operations):
        self.ops = operations

    def install(self, contract: RecoveryContract, metadata: dict, approved_digest: str):
        if os.geteuid() != 0:
            raise RuntimeError("recovery_root_bootstrap_required")
        contract.validate(metadata)
        if approved_digest != digest(contract.__dict__):
            raise RuntimeError("recovery_operator_contract_digest_mismatch")
        from deployment.lib.provider_recovery_phases import require_completed_evidence
        require_completed_evidence(contract, metadata)
        with self.ops.upgrade_lock(), self.ops.deploy_lock():
            # No timer, worker, config or installation changes before these
            # independent fresh checks have completed.
            self.ops.verify_trusted_bootstrap()
            contract.validate_origin(self.ops.origin_evidence())
            contract.validate_target(self.ops.target_evidence())
            candidate, backup = self.ops.stage_candidate(contract.sha)
            self.ops.static_preflight(candidate)
            self.ops.installer_dry_run(candidate, backup)
            # Root exact-contract approval and completed evidence authorize
            # installation only. No bearer credential exists at this boundary.
            self.ops.require_fresh_installation()
            self.ops.begin_installation(contract)
            self.ops.quiesce_normal_automation()
            # Guard again after timer shutdown; no readiness waiver is used.
            contract.validate_origin(self.ops.origin_evidence())
            self.ops.installer_apply(candidate, backup, contract.sha)
            self.ops.verify_installed_controller(contract.sha)
            self.ops.record_controller_transition(contract)
            self.ops.record_installation(contract)
            self.ops.issue_authorization(contract)
            # No automatic deployment follows installation. The separately
            # credentialed transaction must be dispatched explicitly.
            return {"source": contract.sha, "contract_digest": approved_digest,
                    "installed": True, "activated": False}


class ProductionBootstrapOperations:
    """Canonical root installation adapter; fixture overrides cannot enter CLI."""
    def __init__(self, recovery):
        from deployment.lib.control_plane_upgrade import SystemOperations
        self.recovery = recovery
        self.system = SystemOperations()
        self.runtime = self.system.runtime_root
        self.receipt = Path("/var/lib/madar-control-plane/provider402/controller-transition.json")

    def upgrade_lock(self):
        self.system.prepare_upgrade_roots()
        return exclusive_lock(self.system.upgrade_root / "upgrade.lock")

    def deploy_lock(self):
        return exclusive_lock(self.system.state_root / "deploy.lock")

    def verify_trusted_bootstrap(self):
        if os.geteuid() != 0:
            raise RuntimeError("recovery_root_bootstrap_required")
        protected(Path(__file__).resolve())
        self.system.verify_installed_controller(self.recovery.contract.installed_sha)

    def origin_evidence(self):
        return self.recovery.origin_evidence()

    def target_evidence(self):
        return self.recovery.target_evidence()

    def stage_candidate(self, sha):
        # Resolve immutable current main with the existing canonical remote,
        # ancestry, clean-worktree and hook-free protected staging checks.
        self.system.resolve_candidate(sha, dry_run=False)
        transaction, candidate = self.system.stage_candidate(sha)
        # Canonical staging returns its transaction parent and repository,
        # whereas recovery installation consumes a repository and an empty
        # backup destination. Never use either staging path as that backup.
        backup = self.system.backup_root / ("provider402-" + transaction.name)
        if backup.exists() or backup.is_symlink():
            raise RuntimeError("recovery_installation_backup_already_exists")
        return candidate, backup

    def static_preflight(self, candidate):
        self.system.static_preflight(candidate)

    def installer_dry_run(self, candidate, backup):
        self.system.installer_dry_run(candidate, backup)

    def installer_apply(self, candidate, backup, sha):
        self.system.installer_apply(candidate, backup, sha)

    def verify_installed_controller(self, sha):
        self.system.verify_installed_controller(sha)

    def require_fresh_installation(self):
        # Reject an earlier credential/interlock, even for the same contract.
        # Installation is never a reusable credential refresh endpoint.
        for name in ("contract.json", "authorized.credential", "in-progress.json", "installation.json"):
            path = self.runtime / name
            if path.exists() or path.is_symlink():
                raise RuntimeError("recovery_existing_authorization_requires_operator_review")
        if self.receipt.exists() or self.receipt.is_symlink():
            raise RuntimeError("recovery_controller_transition_already_present")

    def begin_installation(self, contract):
        # Credential-free pending interlock blocks every ordinary mutator while
        # root holds installation locks. It cannot authorize a runtime action.
        from deployment.lib.control_plane_upgrade import require_root_directory
        require_root_directory(self.runtime.parent, mode=0o711, create=True)
        require_root_directory(self.runtime, mode=0o711, create=True)
        for name, value in (("schema-contract.json", self.recovery.metadata()),
                            ("contract.json", contract.__dict__),
                            ("in-progress.json", installation_interlock(contract))):
            path = self.runtime / name
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w") as handle:
                json.dump(value, handle, sort_keys=True)
                handle.flush(); os.fsync(handle.fileno())
            if name == "in-progress.json": os.chmod(path, 0o644)

    def record_installation(self, contract):
        from deployment.lib.control_plane_upgrade import require_root_directory
        require_root_directory(self.runtime, mode=0o711, create=True)
        witness = self.runtime / "installation.json"
        if witness.exists() or witness.is_symlink():
            raise RuntimeError("recovery_installation_witness_already_present")
        atomic_json(witness, {"contract_digest": digest(contract.__dict__), "source": contract.sha, "installed": True})
        os.chmod(witness, 0o600)

    def issue_authorization(self, contract):
        # Pending files were exclusively written before installation. Do not
        # overwrite or refresh them while attesting the installed controller.
        if json.loads(protected(self.runtime / "contract.json", private=True).read_text()) != contract.__dict__:
            raise RuntimeError("recovery_authorization_contract_changed")
        return issue_authorization(contract, self.runtime)

    def quiesce_normal_automation(self):
        # Explicit separate upgrade, not the ordinary quiesce method which
        # issues a release credential. Never auto-resume on failure/recovery.
        for unit in ("madar-auto-deploy.timer", "madar-auto-deploy.service"):
            self.recovery.command(["systemctl", "stop", unit])
        self.recovery.command(["systemctl", "mask", "--runtime", "madar-auto-deploy.timer", "madar-auto-deploy.service"])

    def record_controller_transition(self, contract):
        if self.receipt.exists():
            raise RuntimeError("recovery_controller_transition_already_present")
        # Root witness binds only this approved installer transition. All
        # environment/state/upstream/worker fingerprints still have to match.
        current = self.recovery.fingerprints()
        if any(current[key] != contract.production_fingerprints[key]
               for key in current if key != "controller"):
            raise RuntimeError("recovery_unapproved_installation_effect")
        atomic_json(self.receipt, {
            "contract_digest": digest(contract.__dict__),
            "old_sha": contract.installed_sha,
            "old_controller_digest": contract.production_fingerprints["controller"],
            "new_sha": contract.sha, "new_controller_digest": current["controller"],
        })
        os.chmod(self.receipt, 0o600)

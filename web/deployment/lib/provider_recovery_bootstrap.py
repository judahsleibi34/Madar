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
from datetime import datetime, timezone

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
    from deployment.lib.provider_recovery_phases import require_preparation_evidence
    # Installed-controller witness and immutable preparation evidence precede
    # issuance. This credential alone cannot activate traffic: completed
    # exact-image human/rollback evidence and Phase 2 remain mandatory.
    metadata = json.loads(protected(runtime / "schema-contract.json").read_text())
    require_preparation_evidence(contract, metadata)
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
    operations. Preparation evidence and explicit root approval precede install;
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
        from deployment.lib.provider_recovery_phases import require_preparation_evidence
        require_preparation_evidence(contract, metadata)
        with self.ops.upgrade_lock(), self.ops.deploy_lock():
            # No timer, worker, config or installation changes before these
            # independent fresh checks have completed.
            self.ops.verify_trusted_bootstrap()
            contract.validate_origin(self.ops.origin_evidence())
            contract.validate_target(self.ops.target_evidence())
            candidate, backup = self.ops.stage_candidate(contract.sha)
            self.ops.static_preflight(candidate)
            self.ops.installer_dry_run(candidate, backup)
            # Root exact-contract approval and preparation evidence authorize
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
        # A separately bound, unused pre-activation installation may be repaired.
        # Ordinary fresh installation still cannot refresh any credential.
        if self.recovery.contract.repair_context_digest is not None:
            self.require_unused_installation_repair()
            return
        # Reject an earlier credential/interlock, even for the same contract.
        # Installation is never a reusable credential refresh endpoint.
        for name in ("contract.json", "authorized.credential", "madar-control-plane-upgrade", "installation.json"):
            path = self.runtime / name
            if path.exists() or path.is_symlink():
                raise RuntimeError("recovery_existing_authorization_requires_operator_review")
        if self.receipt.exists() or self.receipt.is_symlink():
            raise RuntimeError("recovery_controller_transition_already_present")
        self.legacy_quiesced_interlock()

    def require_unused_installation_repair(self):
        """Validate the existing unused credential and exact prior attestation.

        No runtime activation can use this path. It is available only inside
        the root-approved canonical installer, before any traffic/ownership
        transition, and consumes/archives the previous authorization.
        """
        import re
        from deployment.lib.provider_recovery_runtime import file_digest
        from deployment.lib.control_plane_upgrade_authorization import require_upgrade_authorization
        from deployment.lib.provider_recovery_phases import EMERGENCY_MODE, AUTOMATED_AUTH_CHECKS
        packet = self.receipt.parent / "repair-prior.json"
        prior = json.loads(protected(packet, private=True).read_text())
        old = prior["contract_document"]
        context = digest(old)
        c = self.recovery.contract
        if (context != c.repair_context_digest or old["sha"] != c.installed_sha
                or old["origin_sha"] != c.origin_sha or old["origin_slot"] != c.origin_slot):
            raise RuntimeError("recovery_repair_prior_context_changed")
        allowed = {"authorized.credential", "madar-control-plane-upgrade", "contract.json",
                   "schema-contract.json", "installation.json", "in-progress.json"}
        if set(prior["live_file_digests"]) != allowed:
            raise RuntimeError("recovery_repair_prior_authorization_incomplete")
        for relative, expected in prior["live_file_digests"].items():
            if relative not in allowed or file_digest(protected(self.runtime / relative, private=True if relative != "in-progress.json" else False)) != expected:
                raise RuntimeError("recovery_repair_prior_authorization_changed")
        auxiliary = {"controller-transition.json", "activation-authorization.json", "installation-automation.json"}
        if set(prior["live_aux_file_digests"]) != auxiliary:
            raise RuntimeError("recovery_repair_prior_receipts_incomplete")
        for name, expected in prior["live_aux_file_digests"].items():
            if file_digest(protected(self.receipt.parent / name, private=True)) != expected:
                raise RuntimeError("recovery_repair_prior_receipt_changed")
        os.environ["CREDENTIALS_DIRECTORY"] = str(self.runtime)
        require_upgrade_authorization(old["sha"], required_operation=PROFILE,
            required_schema=115, require_rehearsal=True, required_context_digest=context)
        if json.loads(protected(self.runtime / "installation.json", private=True).read_text()) != {
                "contract_digest": context, "source": old["sha"], "installed": True}:
            raise RuntimeError("recovery_repair_prior_witness_changed")
        phase2 = json.loads(protected(self.receipt.parent / "activation-authorization.json", private=True).read_text())
        completed = prior["completed_report"]
        if (json.loads(prior["completed_raw"]) != completed
                or phase2 != prior["activation_receipt"] or phase2.get("contract_digest") != context
                or phase2.get("phase") != "AUTHORIZE_ACTIVATION"
                or phase2.get("rehearsal_digest") != hashlib.sha256(prior["completed_raw"].encode()).hexdigest()
                or any(v != "PASS" for v in completed["checks"].values())
                or completed.get("acceptance_mode") != EMERGENCY_MODE
                or "human_evidence" in completed):
            raise RuntimeError("recovery_repair_prior_phase2_invalid")
        evidence = completed["automated_evidence"]
        authorization = prior["operator_authorization"]
        binding_contract = dict(old); binding_contract.pop("rehearsal_digest")
        if (authorization["preparation_binding"] != digest({"contract": binding_contract, "schema_contract": prior["schema_metadata"]})
                or completed["operator_authorization_digest"] != digest(authorization)
                or evidence["source_sha"] != old["sha"] or evidence["images"] != old["images"]
                or evidence["checks"] != {key: "PASS" for key in AUTOMATED_AUTH_CHECKS}
                or phase2["auth_acceptance_digest"] != digest({"mode": EMERGENCY_MODE, "authorization": authorization, "evidence": evidence})):
            raise RuntimeError("recovery_repair_prior_evidence_changed")
        transition = json.loads(protected(self.receipt, private=True).read_text())
        if transition != prior["controller_transition"] or transition["contract_digest"] != context or transition["new_sha"] != old["sha"]:
            raise RuntimeError("recovery_repair_prior_transition_changed")
        # The explicit repair attests all original files. Only known bytecode
        # from the previous source-only install may be archived, never executed.
        entries = []
        for path in sorted(self.recovery.paths.controller.rglob("*")):
            if path.is_symlink():
                raise RuntimeError("recovery_repair_controller_symlink")
            if not path.is_file():
                continue
            protected(path)
            if path.parent.name == "__pycache__":
                match = re.fullmatch(r"([A-Za-z_]\w*)[.]cpython-\d+(?:[.]opt-[12])?[.]pyc", path.name)
                if not match or not (path.parent.parent / (match[1] + ".py")).is_file():
                    raise RuntimeError("recovery_repair_unrecognized_cache")
                continue
            entries.append((str(path.relative_to(self.recovery.paths.controller)), file_digest(path)))
        if digest(entries) != transition["new_controller_digest"]:
            raise RuntimeError("recovery_repair_protected_controller_changed")
        if any((self.recovery.paths.state / name).exists() for name in (
                "provider-recovery.json", "provider-recovery-fallback.json", "provider-recovery-traffic.json")):
            raise RuntimeError("recovery_repair_already_activated")
        if self.recovery.fingerprints() != c.production_fingerprints:
            raise RuntimeError("recovery_repair_production_changed")
        origin = self.recovery.origin_evidence()
        c.validate_origin(origin)
        return prior

    def retire_unused_installation(self, contract):
        """Archive the old authority under both locks; never refresh a token."""
        self.require_unused_installation_repair()
        from deployment.lib.control_plane_upgrade import require_root_directory
        archive = self.receipt.parent / "retired-unused-installations" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        require_root_directory(archive.parent, mode=0o700, create=True)
        archive.mkdir(mode=0o700)
        require_root_directory(archive, mode=0o700)
        # Preserve every old credential/witness/receipt before making it invalid.
        for name in ("authorized.credential", "madar-control-plane-upgrade", "contract.json", "schema-contract.json", "installation.json", "in-progress.json"):
            source = protected(self.runtime / name)
            with (archive / name).open("xb") as handle:
                os.fchmod(handle.fileno(), 0o600); handle.write(source.read_bytes()); handle.flush(); os.fsync(handle.fileno())
        for source in (self.receipt, self.receipt.parent / "activation-authorization.json", self.receipt.parent / "installation-automation.json"):
            with (archive / source.name).open("xb") as handle:
                os.fchmod(handle.fileno(), 0o600); handle.write(protected(source, private=True).read_bytes()); handle.flush(); os.fsync(handle.fileno())
        atomic_json(archive / "retirement.json", {"previous_context": contract.repair_context_digest,
            "replacement_context": digest(contract.__dict__), "runtime_activated": False})
        # Atomic pending interlock first: there is never an unguarded interval.
        atomic_json(self.runtime / "in-progress.json", installation_interlock(contract))
        os.chmod(self.runtime / "in-progress.json", 0o644)
        for name in ("authorized.credential", "madar-control-plane-upgrade", "contract.json", "schema-contract.json", "installation.json"):
            (self.runtime / name).unlink()
        self.receipt.unlink()
        (self.receipt.parent / "activation-authorization.json").unlink()
        (self.receipt.parent / "installation-automation.json").unlink()
        return archive

    def legacy_quiesced_interlock(self):
        """Accept only an explicitly pinned, credential-free old quiesce.

        This does not authorize a runtime operation or clear an interlock.
        Trusted installation preserves the original and atomically replaces
        it with a credential-free pending-install interlock under both locks.
        """
        from deployment.lib.provider_recovery_runtime import file_digest
        from deployment.lib.control_plane_upgrade import BACKUP_TIMERS, validate_backup_timer_states
        contract = self.recovery.contract
        path = self.runtime / "in-progress.json"
        expected = contract.legacy_quiesced_interlock_digest
        if not path.exists() and not path.is_symlink():
            if expected is not None:
                raise RuntimeError("recovery_expected_legacy_interlock_missing")
            return None
        protected(path)
        if expected is None or file_digest(path) != expected:
            raise RuntimeError("recovery_existing_authorization_requires_operator_review")
        document = json.loads(path.read_text())
        if (set(document) != {"version", "approved_sha", "authorization_sha256", "backup_timer_states", "status"}
                or document["version"] != 2 or document["status"] != "quiesced"
                or document["authorization_sha256"] is not None
                or document["approved_sha"] != contract.installed_sha
                or contract.installed_sha != contract.origin_sha):
            raise RuntimeError("recovery_legacy_interlock_not_quiesced")
        validate_backup_timer_states(document["backup_timer_states"])
        for unit in ("madar-auto-deploy.service", *(name.replace(".timer", ".service") for name in BACKUP_TIMERS)):
            if self.recovery.command(["systemctl", "show", "--property=ActiveState", "--value", unit]) != "inactive":
                raise RuntimeError("recovery_legacy_upgrade_operation_active")
        return path

    def begin_installation(self, contract):
        # Credential-free pending interlock blocks every ordinary mutator while
        # root holds installation locks. It cannot authorize a runtime action.
        from deployment.lib.control_plane_upgrade import require_root_directory
        require_root_directory(self.runtime.parent, mode=0o711, create=True)
        require_root_directory(self.runtime, mode=0o711, create=True)
        repairing = contract.repair_context_digest is not None
        if repairing:
            self.retire_unused_installation(contract)
        legacy = None if repairing else self.legacy_quiesced_interlock()
        if legacy is not None:
            from deployment.lib.provider_recovery_runtime import file_digest
            # Keep the protected history durably; never remove the original
            # interlock before the replacement is ready. Both deploy/upgrade
            # locks are held and ordinary mutation remains blocked throughout.
            archive_root = self.receipt.parent / "retired-quiesced-interlocks"
            require_root_directory(archive_root, mode=0o700, create=True)
            archive = archive_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            require_root_directory(archive, mode=0o700, create=True)
            saved = archive / "in-progress.json"
            with saved.open("xb") as handle:
                os.chmod(saved, 0o600)
                handle.write(legacy.read_bytes()); handle.flush(); os.fsync(handle.fileno())
            if file_digest(saved) != contract.legacy_quiesced_interlock_digest:
                raise RuntimeError("recovery_legacy_interlock_archive_changed")
            atomic_json(archive / "receipt.json", {
                "contract_digest": digest(contract.__dict__), "source": contract.sha,
                "legacy_sha": contract.installed_sha,
                "legacy_interlock_digest": contract.legacy_quiesced_interlock_digest,
                "backup_timer_states_preserved": True, "runtime_authorization_issued": False,
            })
            os.chmod(archive / "receipt.json", 0o600)
            for directory in (archive, archive_root, self.receipt.parent):
                descriptor = os.open(directory, os.O_DIRECTORY)
                try: os.fsync(descriptor)
                finally: os.close(descriptor)
        for name, value in (("schema-contract.json", self.recovery.metadata()),
                            ("contract.json", contract.__dict__),
                            ("in-progress.json", installation_interlock(contract))):
            path = self.runtime / name
            if name == "in-progress.json" and repairing:
                if json.loads(protected(path).read_text()) != value:
                    raise RuntimeError("recovery_repair_pending_interlock_changed")
                continue
            if name == "in-progress.json" and legacy is not None:
                # Recheck after archival. Atomic replacement has no interval
                # during which ordinary deployment loses its interlock.
                if self.legacy_quiesced_interlock() != path:
                    raise RuntimeError("recovery_legacy_interlock_changed")
                atomic_json(path, value)
                os.chmod(path, 0o644)
                descriptor = os.open(self.runtime, os.O_DIRECTORY)
                try: os.fsync(descriptor)
                finally: os.close(descriptor)
                continue
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
        from deployment.lib.control_plane_upgrade import BACKUP_TIMERS, validate_backup_timer_states
        if os.geteuid() != 0:
            raise RuntimeError("recovery_root_bootstrap_required")
        pending = json.loads(protected(self.runtime / "in-progress.json").read_text())
        if pending != installation_interlock(self.recovery.contract):
            raise RuntimeError("recovery_installation_interlock_invalid")
        if (self.runtime / "authorized.credential").exists():
            raise RuntimeError("recovery_existing_authorization_requires_operator_review")
        services = tuple(name.replace(".timer", ".service") for name in BACKUP_TIMERS)
        # A scheduled timer may be stopped; a running backup must complete.
        # Inspect the complete set before making any automation changes.
        for unit in services:
            if self.system.systemctl_state(unit)["active"] not in ("inactive", "failed"):
                raise RuntimeError("recovery_backup_operation_running")
        timers = validate_backup_timer_states({
            name: self.system.systemctl_state(name) for name in BACKUP_TIMERS
        })
        snapshot = self.receipt.parent / "installation-automation.json"
        if snapshot.exists() or snapshot.is_symlink():
            raise RuntimeError("recovery_installation_automation_snapshot_exists")
        atomic_json(snapshot, {"contract_digest": digest(self.recovery.contract.__dict__),
            "source": self.recovery.contract.sha, "backup_timer_states": timers,
            "automatic_resumption_authorized": False})
        os.chmod(snapshot, 0o600)
        descriptor = os.open(snapshot.parent, os.O_DIRECTORY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
        for unit in BACKUP_TIMERS:
            self.recovery.command(["systemctl", "stop", unit])
        for unit in BACKUP_TIMERS:
            if self.system.systemctl_state(unit)["active"] != "inactive":
                raise RuntimeError("recovery_backup_timer_not_quiesced")
        for unit in services:
            if self.system.systemctl_state(unit)["active"] not in ("inactive", "failed"):
                raise RuntimeError("recovery_backup_operation_running")
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

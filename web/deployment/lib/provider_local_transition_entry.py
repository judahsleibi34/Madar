"""Installed root-only normal-local transition; no path or driver overrides."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

# Direct trusted execution must have the same source-only import policy as -IB.
sys.dont_write_bytecode = True
if __name__ == "__main__":
    if not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        safe = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root",
                "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
        os.execve(sys.executable, [sys.executable, "-I", "-B",
                  str(Path(__file__).resolve()), *sys.argv[1:]], safe)
    controller = Path(__file__).resolve().parents[1]
    if any(path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
           for path in controller.rglob("*")):
        raise SystemExit("protected_controller_bytecode_present")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from deployment.lib.provider_local_transition import LocalProviderTransition, LocalTransitionContract, validate_evidence
from deployment.lib.provider_local_transition_runtime import ROOT, ProductionLocalTransitionOperations
from deployment.lib.provider_recovery_runtime import digest, protected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("auth-configure", "authorize", "prepare", "handoff", "switch", "finalize", "rollback", "restart-worker"))
    parser.add_argument("--approved-contract", required=True)
    parser.add_argument("--worker", choices=("notification", "calendar-sync", "data-deletion"))
    args = parser.parse_args()
    if (args.operation == "restart-worker") != (args.worker is not None):
        parser.error("worker argument is required only for restart-worker")
    if os.geteuid() != 0:
        raise RuntimeError("local_transition_root_entry_required")
    os.umask(0o077)
    protected(Path(__file__).resolve())
    packet = json.loads(protected(ROOT / "contract.json", private=True).read_text())
    contract = LocalTransitionContract(**packet)
    if args.approved_contract != digest(packet):
        raise RuntimeError("local_transition_operator_digest_mismatch")
    metadata = json.loads(protected(ROOT / "schema-contract.json", private=True).read_text())
    contract.validate(metadata)
    os.environ["CREDENTIALS_DIRECTORY"] = "/run/madar/control-plane-upgrade"
    credential = protected(Path("/run/madar/control-plane-upgrade/authorized.credential"), private=True)
    alias = protected(credential.with_name("madar-control-plane-upgrade"), private=True)
    if alias.stat().st_ino != credential.stat().st_ino:
        raise RuntimeError("local_transition_credential_alias_invalid")
    ops = ProductionLocalTransitionOperations()
    if args.operation == "auth-configure":
        from deployment.lib.provider_local_auth_configuration import configure_auth
        configure_auth(ops, contract)
    elif args.operation == "authorize":
        from deployment.lib.provider_recovery_bootstrap import exclusive_lock
        ops.recovery.authorize(ops.recovery.contract)
        validate_evidence(contract, ops.evidence())
        ops.verify_immutable_inputs(contract)
        with exclusive_lock(ops.state / "deploy.lock"):
            ops.require_recovery_active(contract.recovery_context)
            ops.require_all_workers_off()
            ops.verify_local_fallback()
            if ops.fingerprints() != contract.production_fingerprints:
                raise RuntimeError("local_transition_production_changed")
            path = ROOT / "authorization.json"
            # Exclusive issuance: a retained receipt cannot authorize a new
            # packet or be silently refreshed after any source/evidence change.
            with path.open("x") as handle:
                os.chmod(path, 0o600)
                json.dump({"version": 1, "operation": "normal-local-provider", "schema": 115,
                    "contract_digest": digest(asdict(contract)), "evidence_digest": contract.evidence_digest}, handle)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
    elif args.operation == "restart-worker":
        LocalProviderTransition(ops.state, ops).restart_worker(contract, metadata, args.worker)
    else:
        getattr(LocalProviderTransition(ops.state, ops), args.operation)(contract, metadata)
    print("protected_normal_local_operation_complete")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("protected_normal_local_operation_failed", file=sys.stderr)
        raise SystemExit(1)

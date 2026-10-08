"""Fixed-path root recovery entrypoint. No arbitrary drivers or env overrides."""
from pathlib import Path
import argparse
import json
import os
import re
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

# Only a root-protected installed or trusted root-staged package may execute.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from deployment.lib.provider_recovery import RecoveryContract, ProviderRecoveryTransaction
from deployment.lib.provider_recovery_runtime import ProductionRecoveryOperations, RecoveryPaths, protected, digest
from deployment.lib.provider_recovery_bootstrap import ProductionBootstrapOperations, TrustedRecoveryBootstrap

PACKET = Path("/var/lib/madar-control-plane/provider402/contract.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("authorize-activation", "install", "register-fallback", "activate", "rollback"))
    parser.add_argument("--approved-contract", required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError("recovery_root_entrypoint_required")
    protected(Path(__file__).resolve())
    document = json.loads(protected(PACKET, private=True).read_text())
    contract = RecoveryContract(**document)
    if not re.fullmatch(r"[0-9a-f]{64}", args.approved_contract) or args.approved_contract != digest(document):
        raise RuntimeError("recovery_operator_contract_digest_mismatch")
    paths = RecoveryPaths()
    metadata = json.loads(protected(PACKET.parent / "schema-contract.json", private=True).read_text())
    contract.validate(metadata)
    if args.operation == "install":
        # Fresh root installation consumes immutable preparation evidence, not a credential
        # that can only exist after the installed-controller attestation.
        from deployment.lib.provider_recovery_phases import require_preparation_evidence
        require_preparation_evidence(contract, metadata)
        operations = ProductionRecoveryOperations(paths, contract)
        TrustedRecoveryBootstrap(ProductionBootstrapOperations(operations)).install(
            contract, metadata, args.approved_contract)
        print("protected_recovery_operation_complete")
        return
    os.environ["CREDENTIALS_DIRECTORY"] = "/run/madar/control-plane-upgrade"
    credential = Path("/run/madar/control-plane-upgrade/authorized.credential")
    protected(credential, private=True)
    credential_alias = credential.with_name("madar-control-plane-upgrade")
    if not credential_alias.exists():
        os.link(credential, credential_alias)
    if credential_alias.is_symlink() or credential_alias.stat().st_ino != credential.stat().st_ino:
        raise RuntimeError("recovery_credential_alias_invalid")
    from deployment.lib.provider_recovery import require_provider_recovery_authorization
    require_provider_recovery_authorization(contract)
    if args.operation == "authorize-activation":
        from deployment.lib.provider_recovery_phases import authorize_activation, ACTIVATION_REHEARSAL
        authorize_activation(contract, metadata, ACTIVATION_REHEARSAL)
        print("protected_recovery_activation_authorized")
        return
    operations = ProductionRecoveryOperations(paths, contract)
    operations.authorize(contract)
    from deployment.lib.provider_recovery_bootstrap import exclusive_lock
    if args.operation == "register-fallback":
        with exclusive_lock(paths.state / "deploy.lock"):
            contract.validate_origin(operations.origin_evidence())
            operations.checkpoint(); operations.rehearsal()
            operations.register_fallback()
    elif args.operation == "activate":
        ProviderRecoveryTransaction(paths.state, operations).activate(contract, metadata)
    else:
        ProviderRecoveryTransaction(paths.state, operations).rollback(contract, metadata)
    print("protected_recovery_operation_complete")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Provider errors may contain credentials; never emit tracebacks.
        print("protected_recovery_operation_failed", file=sys.stderr)
        raise SystemExit(1)

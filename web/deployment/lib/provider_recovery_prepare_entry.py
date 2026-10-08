"""Trusted fixed-path Phase-1 launcher; no production activation operation."""
import argparse
import json
from pathlib import Path
import os
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
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from deployment.lib.provider_recovery import RecoveryContract
from deployment.lib.provider_recovery_phases import PreparationTransaction, preparation_binding, sha256
from deployment.lib.provider_recovery_preparation import PrivatePreparationOperations, ROOT
from deployment.lib.provider_recovery_runtime import protected
from deployment.lib.provider_recovery_bootstrap import exclusive_lock
from deployment.lib.release_deployer import atomic_json
PACKET=Path('/var/lib/madar-control-plane/provider402/preparation-contract.json')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('operation',choices=('prepare-and-rehearse','rehearse-traffic','rehearse-rollback'))
    parser.add_argument('--approved-contract',required=True)
    args=parser.parse_args()
    if os.geteuid()!=0:
        raise RuntimeError('recovery_private_root_required')
    protected(Path(__file__).resolve())
    document=json.loads(protected(PACKET,private=True).read_text())
    if sha256(document)!=args.approved_contract:
        raise RuntimeError('recovery_operator_contract_digest_mismatch')
    contract=RecoveryContract(**document)
    # Immutable metadata is read from the pinned, root-protected staging tree.
    metadata=json.loads(protected(Path(__file__).resolve().parents[1]/'releases/release.json').read_text())
    directory=ROOT/sha256(preparation_binding(contract,metadata))
    operations=PrivatePreparationOperations(contract,metadata,directory)
    with exclusive_lock(directory/'preparation.lock'):
        if args.operation=='prepare-and-rehearse':
            PreparationTransaction(operations).prepare(contract,metadata)
        elif args.operation=='rehearse-traffic':
            operations.switch('blue' if contract.origin_slot=='green' else 'green')
        else:
            # Rollback changes runtimes only. The native target and accepted
            # Auth sessions are never restored or copied by this operation.
            state_path=operations.paths.state/'provider-recovery.json'
            state=json.loads(state_path.read_text());state['phase']='rollback_pending'
            atomic_json(state_path,state)
            operations.switch_local_rollback(contract)
            operations.verify_local_rollback(contract)
            state['phase']='local_rollback_active';atomic_json(state_path,state)
    print('isolated_recovery_operation_complete')


if __name__=='__main__':
    try:
        main()
    except Exception:
        print('isolated_recovery_operation_failed',file=sys.stderr)
        raise SystemExit(1)

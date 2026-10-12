#!/usr/bin/env python3
"""Credential-delivered adapter for an already fenced, stopped origin.

Uses the installed controller and its genuine Docker operations. A fresh root
continuation witness permits the NONE-to-candidate handoff; it never invents an
active old owner or grants writes. No production entrypoint or file is replaced.
"""
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import pwd
import sys

CONTROL = Path('/opt/madar/control-plane/deployment')


def verify_witness():
    identity = pwd.getpwnam('madar')
    if (os.geteuid(), os.getegid()) != (identity.pw_uid, identity.pw_gid) or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('continuation_child_identity_invalid')
    sys.path.insert(0, str(CONTROL.parent))
    from deployment.lib.completed_normal_admission import credential_witness, require_admission, require_fresh_authorization
    witness = credential_witness('completed_continuation', 'completed_continuation_sha256')
    if (witness.get('operation') != 'retained-normal-schema136-144-continuation'
            or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != witness.get('child_sha256')):
        raise RuntimeError('continuation_child_source_invalid')
    contract = require_admission(Path('/var/lib/madar/releases'), witness['application_sha'])
    require_fresh_authorization(contract)
    from deployment.lib.completed_normal_admission import digest
    from deployment.lib.completed_normal_profile import MANUAL, profile
    from deployment.lib.active_recovery_inputs import controller_tree_digest
    if (profile(contract) is not MANUAL or digest(contract) != witness.get('parent_context_sha256')
            or (CONTROL/'CONTROL_PLANE_SOURCE_SHA').read_text().strip() != contract['candidate']['controller_sha']
            or controller_tree_digest() != contract['candidate']['controller_tree_sha256']):
        raise RuntimeError('continuation_child_controller_changed')
    return witness, contract


def activate_stopped_origin(module, operations, witness, contract):
    from deployment.lib.completed_normal_admission import require_candidate_authority
    from deployment.lib.completed_normal_profile import expected_origin_grant
    from deployment.lib.runtime_authority import load_worker_authority, write_worker_authority
    from deployment.lib.completed_normal_resources import measured_spec_matches
    state_root = operations.state_root;sha = contract['candidate']['source_sha'];slot = contract['candidate']['slot']
    record = module.load_prepared_release(state_root, sha, slot, operations)
    operations.verify_source(sha);operations.validate_candidate_core(sha,slot)
    require_candidate_authority(contract,mode='READ_ONLY')
    state = module._json_file(state_root/'state.json','continuation_release_state_invalid')
    known=state.get('known_good_release') or {};owner=load_worker_authority(state_root)
    if (known.get('sha') != contract['source_roles']['application_sha']
            or known.get('slot') != contract['origin']['slot'] or known.get('schema') != 136
            or state.get('active_slot') != known.get('slot') or state.get('in_progress_release') or state.get('rollback_failure')
            or owner is None or owner['owner'] != 'CANDIDATE' or owner['generation'] != contract['origin']['worker_generation']
            or owner['candidate'] != {'sha':known['sha'],'slot':known['slot']}
            or hashlib.sha256((state_root/'worker-ownership.json').read_bytes()).hexdigest() != witness['worker_owner_sha256']
            or witness['origin_grant'] != expected_origin_grant(contract,'READ_ONLY')
            or operations.worker_ownership(known, {'sha':sha,'slot':slot}) != 'none'):
        raise RuntimeError('continuation_stopped_origin_required')
    from deployment.lib.completed_normal_admission import credential_witness
    original=credential_witness('origin_runtime','origin_runtime_sha256')
    from deployment.lib.emergency_routing_repair import Runtime
    runtime=Runtime()
    for kind in ('notification-worker','calendar-sync-worker','data-deletion-worker'):
        expected=original['runtimes'][kind];rows=runtime.inspect([expected['id']]);row=next(iter(rows.values()))
        if row['State']['Running'] or row['Image'] != expected['image'] or not measured_spec_matches(row,expected['spec_sha256']):
            raise RuntimeError('continuation_origin_worker_changed')
    operations.require_completed_normal_standbys(record)
    generation=module.hashlib.sha256(f"bootstrap:{sha}:{slot}:{record['prepared_at']}".encode()).hexdigest()
    if generation != witness['worker_generation']:raise RuntimeError('continuation_worker_generation_changed')
    previous={'sha':known['sha'],'slot':known['slot']};candidate={'sha':sha,'slot':slot}
    write_worker_authority(state_root,generation=generation,owner='NONE',old=previous,candidate=candidate)
    operations.deactivate_workers(known)
    if operations.worker_ownership(known,candidate) != 'none':raise RuntimeError('continuation_worker_quiescence_failed')
    write_worker_authority(state_root,generation=generation,owner='CANDIDATE',old=previous,candidate=candidate)
    record['worker_generation']=generation;module.atomic_json(module.prepared_release_path(state_root,operations),record)
    try:
        operations.activate_workers(sha,slot,record['images']);operations.validate_candidate_core(sha,slot)
        require_candidate_authority(contract,mode='READ_ONLY')
    except Exception:
        operations.deactivate_workers({'sha':sha,'slot':slot,'images':record['images']});raise
    record.update(status='candidate_workers_active',business_writes='READ_ONLY',workers_activated_at=module.utc_now().isoformat())
    module.atomic_json(module.prepared_release_path(state_root,operations),record)
    return record


def main():
    if sys.argv[1:] not in (['activate'], ['migrate']):raise RuntimeError('continuation_child_stage_invalid')
    witness,contract=verify_witness()
    loader=importlib.machinery.SourceFileLoader('continuation_installed_deploy',str(CONTROL/'bin/madar-release-deploy'))
    module=importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name,loader));loader.exec_module(module)
    module.load_production_path_contract()
    module.load_environment_file(Path('/etc/madar/production.env'))
    from deployment.lib.completed_normal_profile import profile
    selected=profile(contract);compatibility=module.Compatibility.load(CONTROL/'releases'/selected.metadata)
    if (compatibility.schema_min,compatibility.schema_max,compatibility.target_schema,compatibility.excluded_schemas)!=(136,144,144,(142,)):
        raise RuntimeError('continuation_migration_contract_changed')
    operations=module.DockerGitOperations(Path('/srv/madar/production'),Path('/var/lib/madar/releases'),
        Path('/etc/madar/production.env'),compatibility,metadata_filename=selected.metadata)
    operations.completed_normal_admission=contract
    with module.deployment_lock(operations.state_root):
        if sys.argv[1]=='activate':result=activate_stopped_origin(module,operations,witness,contract)
        else:
            operations.verify_source(contract['candidate']['source_sha'])
            from deployment.lib.completed_normal_migration import run_migration
            result=run_migration(contract,operations.release_root,operations.state_root,operations)
    print(json.dumps({'stage':sys.argv[1],'completed':True}))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'failed','exception_type':type(error).__name__}));raise SystemExit(1)

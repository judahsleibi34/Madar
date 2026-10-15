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
import re
import traceback

CONTROL = Path('/opt/madar/control-plane/deployment')


def verify_witness():
    identity = pwd.getpwnam('madar')
    if (os.geteuid(), os.getegid()) != (identity.pw_uid, identity.pw_gid) or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('continuation_child_identity_invalid')
    sys.path.insert(0, str(CONTROL.parent))
    from deployment.lib.completed_normal_admission import credential_witness, require_admission, require_fresh_authorization
    witness = credential_witness('completed_continuation', 'completed_continuation_sha256')
    if (witness.get('operation') != 'retained-normal-schema144-146-pre-sql-continuation'
            or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != witness.get('child_sha256')):
        raise RuntimeError('continuation_child_source_invalid')
    contract = require_admission(Path('/var/lib/madar/releases'), witness['application_sha'])
    require_fresh_authorization(contract)
    from deployment.lib.completed_normal_admission import digest
    from deployment.lib.completed_normal_profile import COMMERCIAL, profile
    from deployment.lib.active_recovery_inputs import controller_tree_digest
    if (profile(contract) is not COMMERCIAL or digest(contract) != witness.get('parent_context_sha256')
            or (CONTROL/'CONTROL_PLANE_SOURCE_SHA').read_text().strip() != contract['candidate']['controller_sha']
            or controller_tree_digest() != contract['candidate']['controller_tree_sha256']):
        raise RuntimeError('continuation_child_controller_changed')
    return witness, contract



def main():
    if sys.argv[1:] != ['migrate']:raise RuntimeError('continuation_child_stage_invalid')
    witness,contract=verify_witness()
    loader=importlib.machinery.SourceFileLoader('continuation_installed_deploy',str(CONTROL/'bin/madar-release-deploy'))
    module=importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name,loader));loader.exec_module(module)
    module.load_production_path_contract()
    module.load_environment_file(Path('/etc/madar/production.env'))
    from deployment.lib.completed_normal_profile import profile
    selected=profile(contract);compatibility=module.Compatibility.load(CONTROL/'releases'/selected.metadata)
    if (compatibility.schema_min,compatibility.schema_max,compatibility.target_schema,compatibility.excluded_schemas)!=(144,146,146,()):
        raise RuntimeError('continuation_migration_contract_changed')
    operations=module.DockerGitOperations(Path('/srv/madar/production'),Path('/var/lib/madar/releases'),
        Path('/etc/madar/production.env'),compatibility,metadata_filename=selected.metadata)
    operations.completed_normal_admission=contract
    with module.deployment_lock(operations.state_root):
        operations.verify_source(contract['candidate']['source_sha'])
        path=Path(os.environ['CREDENTIALS_DIRECTORY'])/'completed-continuation-migration'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=witness['migration_sha256']:
            raise RuntimeError('continuation_migration_source_changed')
        loader=importlib.machinery.SourceFileLoader('continuation_measured_migration',str(path))
        migration=importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name,loader));loader.exec_module(migration)
        result=migration.run_migration(contract,operations.release_root,operations.state_root,operations)
    print(json.dumps({'stage':sys.argv[1],'completed':True}))


if __name__=='__main__':
    try:main()
    except Exception as error:
        code=str(error)
        print(json.dumps({'status':'failed','exception_type':type(error).__name__,
            'failure_code':code if isinstance(error,RuntimeError) and re.fullmatch('[a-z][a-z0-9_]{1,120}',code) else 'sanitized_exception',
            'frames':[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)[-12:]]}));raise SystemExit(1)

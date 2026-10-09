#!/usr/bin/env python3
"""Stdlib-only hash gate before importing any privileged continuation source.

Execute only after explicit approval of these exact source/plan hashes. The
package is a previously frozen root-private snapshot, never mutable repo code.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

BASE=Path('/var/lib/madar-control-plane/normal-local-preparation')

def secured(path, *, directory=False):
    path=Path(path)
    for item in (path,*path.parents):
        st=item.lstat()
        if item.is_symlink() or st.st_uid!=0 or st.st_mode&0o022:
            raise RuntimeError('continuation_bootstrap_untrusted_path')
    if path.stat().st_mode&0o077 or path.stat().st_mode&0o200:
        raise RuntimeError('continuation_bootstrap_source_not_frozen_private')
    if not (path.is_dir() if directory else path.is_file()):raise RuntimeError('continuation_bootstrap_missing_source')
    return path

def measure(package,approved_source,approved_plan):
    if not re.fullmatch('[0-9a-f]{64}',approved_source) or not re.fullmatch('[0-9a-f]{64}',approved_plan):
        raise RuntimeError('continuation_bootstrap_approval_invalid')
    if package!=BASE/('normal-source-'+approved_source):raise RuntimeError('continuation_bootstrap_namespace_invalid')
    secured(package,directory=True)
    bundle=secured(package/'source-bundle.json').read_bytes()
    plan=secured(package/'plan.json').read_bytes()
    if hashlib.sha256(bundle).hexdigest()!=approved_source or hashlib.sha256(plan).hexdigest()!=approved_plan:
        raise RuntimeError('continuation_bootstrap_approved_bytes_changed')
    manifest=json.loads(bundle);saved=json.loads(plan)
    if saved.get('source_bundle_sha256')!=approved_source or manifest.get('source_sha')!=saved.get('source_sha'):
        raise RuntimeError('continuation_bootstrap_source_plan_mismatch')
    files=manifest.get('files',{})
    if not isinstance(files,dict) or not files:raise RuntimeError('continuation_bootstrap_inventory_missing')
    source=secured(package/'source',directory=True)
    actual={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file() or p.is_symlink()}
    if actual!=set(files):raise RuntimeError('continuation_bootstrap_inventory_changed')
    for relative,sha in files.items():
        target=Path(relative)
        if target.is_absolute() or '..' in target.parts or target.as_posix()!=relative or target.suffix in {'.pyc','.pyo'}:
            raise RuntimeError('continuation_bootstrap_source_path_invalid')
        if hashlib.sha256(secured(source/target).read_bytes()).hexdigest()!=sha:
            raise RuntimeError('continuation_bootstrap_source_hash_changed')
    # No deployment code was imported before every executable byte was checked.
    return saved,source

def main():
    if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('continuation_bootstrap_isolated_root_required')
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['verify','execute'])
    for name in ('source-package','approved-source','approved-plan'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args();package=Path(args.source_package)
    saved,source=measure(package,args.approved_source,args.approved_plan)
    sys.path.insert(0,str(source/'web'));sys.path.insert(1,str(source/'web/scripts'))
    from deployment.lib.active_recovery_resumption import ResumptionPlan,ActiveRecoveryResumption
    from deployment.lib.active_recovery_operations import ProductionActiveRecoveryOperations
    plan=ResumptionPlan(**saved);plan.validate()
    if plan.digest!=args.approved_plan:raise RuntimeError('continuation_bootstrap_noncanonical_plan')
    operations=ProductionActiveRecoveryOperations(plan,package)
    if args.mode=='verify':
        operations.verify_actual_execution_evidence(plan)
        operations.verify_active_rollback_inputs(plan);operations.verify_emergency_installation(plan)
        operations.verify_restricted_fallback(plan);operations.require_no_normal_write_authority()
        operations.require_all_consumers_stopped()
        result={'operation':'verify-active-recovery-continuation','production_modified':False,'plan_sha256':plan.digest}
    else:
        transaction=ActiveRecoveryResumption(plan,operations)
        transaction.authorize(approved_plan=args.approved_plan,approved_source=args.approved_source)
        result=transaction.execute()
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'operation':'active-recovery-continuation','status':'failed','exception_type':type(error).__name__}),flush=True)
        raise SystemExit(1)

#!/usr/bin/env python3
"""Stdlib-first boot/proxy gate for the freshly approved compatible handoff.

This entrypoint cannot start a cutover or issue operator approval. Its durable
receipt must already exist from the separately approved complete operation.
Every privileged import is measured before loading it. No historical code is
imported to manufacture a matching application/controller revision.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

BASE=Path('/var/lib/madar-control-plane/normal-local-preparation')
REQUIRED_FILES={'web/scripts/continue_completed_normal_upgrade.py',*(
    'web/deployment/lib/'+name+'.py' for name in (
        'completed_normal_boot_actor','completed_normal_admission','completed_normal_baseline',
        'completed_normal_runtime','completed_normal_migration','completed_normal_database',
        'completed_normal_resources','compatible_normal_boot','completed_normal_boot_installation',
        'completed_normal_write_handoff','completed_normal_backup','completed_normal_execution',
        'completed_normal_model','completed_normal_evidence'))}
def secured(path, *, directory=False):
    for part in (path,*path.parents):
        st=part.lstat()
        if part.is_symlink() or st.st_uid!=0 or st.st_mode&0o022:
            raise RuntimeError('completed_upgrade_boot_source_untrusted')
    if path.stat().st_mode&0o277 or not (path.is_dir() if directory else path.is_file()):
        raise RuntimeError('completed_upgrade_boot_source_not_frozen')
    return path

def measure(package,source_hash,plan_hash):
    if (not re.fullmatch('[0-9a-f]{64}',source_hash) or not re.fullmatch('[0-9a-f]{64}',plan_hash)
            or package!=BASE/('normal-source-'+source_hash)):
        raise RuntimeError('completed_upgrade_boot_package_binding_invalid')
    secured(package,directory=True)
    manifest_bytes=secured(package/'source-bundle.json').read_bytes()
    plan_bytes=secured(package/'plan.json').read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest()!=source_hash or hashlib.sha256(plan_bytes).hexdigest()!=plan_hash:
        raise RuntimeError('completed_upgrade_boot_approved_bytes_changed')
    manifest=json.loads(manifest_bytes);document=json.loads(plan_bytes)
    # Actor/contract digests use this canonical encoding. Reject another raw
    # representation before any import so one operator-approved plan has one
    # byte identity throughout boot, installation and authorization.
    canonical=lambda value:(json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
    if manifest_bytes!=canonical(manifest) or plan_bytes!=canonical(document):
        raise RuntimeError('completed_upgrade_boot_noncanonical_package')
    if (document.get('source_bundle_sha256')!=source_hash
            or document.get('controller_source_sha')!=manifest.get('source_sha')):
        raise RuntimeError('completed_upgrade_boot_source_plan_mismatch')
    source=secured(package/'source',directory=True)
    files=manifest.get('files',{})
    actual={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file() or p.is_symlink()}
    if not isinstance(files,dict) or not REQUIRED_FILES.issubset(files) or set(files)!=actual:
        raise RuntimeError('completed_upgrade_boot_source_inventory_changed')
    for relative,expected in files.items():
        path=Path(relative)
        if (path.is_absolute() or '..' in path.parts or path.as_posix()!=relative
                or path.suffix in {'.pyc','.pyo'} or not re.fullmatch('[0-9a-f]{64}',str(expected))
                or hashlib.sha256(secured(source/path).read_bytes()).hexdigest()!=expected):
            raise RuntimeError('completed_upgrade_boot_source_bytes_changed')
    return document,source

def main():
    if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('completed_upgrade_boot_isolated_root_required')
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('boot','proxy-gate'))
    for name in ('source-package','approved-source','approved-plan'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args();package=Path(args.source_package)
    document,source=measure(package,args.approved_source,args.approved_plan)
    if Path(__file__)!=source/'web/scripts/continue_completed_normal_upgrade.py':
        raise RuntimeError('completed_upgrade_boot_entry_location_changed')
    sys.path.insert(0,str(source/'web'))
    from deployment.lib.completed_normal_boot_actor import CompletedNormalBootActor
    actor=CompletedNormalBootActor(document,package,lambda:measure(package,args.approved_source,args.approved_plan))
    result=actor.resume() if args.mode=='boot' else actor.proxy_gate()
    print(json.dumps({'operation':args.mode,'result':result},sort_keys=True))

if __name__=='__main__':
    try:main()
    except Exception as error:
        import traceback
        frames=[{'source':Path(row.filename).name,'line':row.lineno,'function':row.name}
            for row in traceback.extract_tb(error.__traceback__)[-24:]]
        code=str(error)
        print(json.dumps({'operation':'compatible-normal-boot','status':'failed','exception_type':type(error).__name__,
            'failure_code':code if isinstance(error,RuntimeError) and re.fullmatch('[a-z][a-z0-9_]{1,100}',code) else 'sanitized_exception',
            'frames':frames,'customer_database_restored':False}),flush=True)
        raise SystemExit(1)

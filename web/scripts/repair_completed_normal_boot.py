#!/usr/bin/env python3
"""Stdlib hash gate for ONE exact-approved boot installation, no cutover replay."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import re

BASE=Path('/var/lib/madar-control-plane/normal-local-preparation')
def secured(path,*,directory=False):
    for item in (path,*path.parents):
        st=item.lstat()
        if item.is_symlink() or st.st_uid!=0 or st.st_mode&0o022:raise RuntimeError('boot_repair_untrusted_path')
    if path.stat().st_mode&0o277 or not (path.is_dir() if directory else path.is_file()):
        raise RuntimeError('boot_repair_source_not_frozen')
    return path
def measure(package,approved_source,approved_plan):
    if not re.fullmatch('[0-9a-f]{64}',approved_source) or not re.fullmatch('[0-9a-f]{64}',approved_plan):
        raise RuntimeError('boot_repair_approval_invalid')
    if package!=BASE/('normal-source-'+approved_source):raise RuntimeError('boot_repair_package_namespace_invalid')
    secured(package,directory=True)
    body=secured(package/'source-bundle.json').read_bytes();plan=secured(package/'plan.json').read_bytes()
    if hashlib.sha256(body).hexdigest()!=approved_source or hashlib.sha256(plan).hexdigest()!=approved_plan:
        raise RuntimeError('boot_repair_approved_bytes_changed')
    manifest=json.loads(body);document=json.loads(plan)
    if document.get('source_bundle_sha256')!=approved_source or document.get('controller_source_sha')!=manifest.get('source_sha'):
        raise RuntimeError('boot_repair_source_plan_mismatch')
    source=secured(package/'source',directory=True);files=manifest.get('files',{})
    actual={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file() or p.is_symlink()}
    if not files or set(files)!=actual:raise RuntimeError('boot_repair_inventory_changed')
    for name,expected in files.items():
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts or relative.as_posix()!=name or relative.suffix in {'.pyc','.pyo'}:
            raise RuntimeError('boot_repair_source_path_invalid')
        if hashlib.sha256(secured(source/relative).read_bytes()).hexdigest()!=expected:
            raise RuntimeError('boot_repair_source_bytes_changed')
    return document,source

def main():
    if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('boot_repair_isolated_root_required')
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['verify','execute','resume-boot','check-proxy-gate','verify-upgrade-baseline'])
    for name in ('source-package','approved-source','approved-plan'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    document,source=measure(Path(args.source_package),args.approved_source,args.approved_plan)
    if __file__!=str(source/'web/scripts/repair_completed_normal_boot.py'):
        raise RuntimeError('boot_repair_entry_location_changed')
    sys.path.insert(0,str(source/'web'))
    from deployment.lib.normal_boot_repair import NormalBootRepair
    operation=NormalBootRepair(document,Path(args.source_package))
    if args.mode=='verify':
        with operation.locks():result=operation.preflight()
    elif args.mode=='execute':result=operation.install()
    elif args.mode=='resume-boot':result=operation.resume()
    elif args.mode=='check-proxy-gate':result=operation.proxy_gate()
    else:
        with operation.locks():result=operation.ops.current_preflight(lock_deployment=False)
    print(json.dumps({'operation':args.mode,'result':result},sort_keys=True))

if __name__=='__main__':
    try:main()
    except Exception as error:
        import traceback
        frames=[{'source':Path(row.filename).name,'line':row.lineno,'function':row.name}
            for row in traceback.extract_tb(error.__traceback__)]
        print(json.dumps({'operation':'normal-boot-repair','status':'failed','exception_type':type(error).__name__,
            'failure_code':str(error) if isinstance(error,RuntimeError) and re.fullmatch('[a-z][a-z0-9_]{1,100}',str(error)) else 'sanitized_exception','frames':frames}),flush=True)
        raise SystemExit(1)

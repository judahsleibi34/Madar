#!/usr/bin/env python3
"""Stdlib-first exact-source entrypoint for the compatible handoff.

Preflight consumes no authorization. Execute requires a separately approved
complete operation and independently verified full private rehearsal. Boot and
proxy-gate require the durable receipt from that operation.
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
        'completed_normal_model','completed_normal_evidence','completed_normal_forward','completed_normal_profile','schema148_release','schema148_artifacts','schema148_consumers','schema149_release','schema149_consumers','schema149_provider_lifecycle','schema149_controller','schema150_release','schema150_provider_lifecycle','schema150_actor_inventory','schema150_object_inventory','schema150_provider_adapter','schema150_status'))}
REQUIRED_FILES.update({
    'web/backend/Dockerfile','web/backend/requirements.txt','web/backend/constraints.txt',
    'web/frontend/Dockerfile','web/frontend/package.json','web/frontend/package-lock.json',
    '.github/workflows/schema148-artifacts.yml','web/scripts/build_schema148_artifacts.py',
})
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
    parser.add_argument('mode',choices=('preflight','execute','forward-preflight','forward-resume','boot','proxy-gate'))
    for name in ('source-package','approved-source','approved-plan'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--resumption-plan');parser.add_argument('--approved-resumption')
    args=parser.parse_args();package=Path(args.source_package)
    document,source=measure(package,args.approved_source,args.approved_plan)
    if Path(__file__)!=source/'web/scripts/continue_completed_normal_upgrade.py':
        raise RuntimeError('completed_upgrade_boot_entry_location_changed')
    if args.mode in {'preflight','execute','forward-preflight','forward-resume'} and (document.get('fixture_only') or document.get('production_authorization') is False):
        raise RuntimeError('completed_upgrade_fixture_cannot_authorize_production')
    sys.path.insert(0,str(source/'web'))
    from deployment.lib.completed_normal_boot_actor import CompletedNormalBootActor
    actor=CompletedNormalBootActor(document,package,lambda:measure(package,args.approved_source,args.approved_plan))
    if args.mode in {'forward-preflight','forward-resume'}:
        if not re.fullmatch('[0-9a-f]{64}',str(args.approved_resumption)):
            raise RuntimeError('completed_forward_plan_hash_required')
        path=Path(args.resumption_plan or '')
        if path!=BASE/('forward-resumption-'+args.approved_resumption)/'plan.json':
            raise RuntimeError('completed_forward_plan_location_invalid')
        body=secured(path).read_bytes();resume=json.loads(body)
        if (body!=(json.dumps(resume,sort_keys=True,indent=2)+'\n').encode()
                or hashlib.sha256(body).hexdigest()!=args.approved_resumption
                or resume.get('fixture_only') or resume.get('production_authorization') is not True):
            raise RuntimeError('completed_forward_approved_plan_changed')
        from deployment.lib.completed_normal_forward import CompletedNormalForwardResumption
        from deployment.lib.completed_normal_evidence import verify_application_evidence,verify_complete_rehearsal
        driver=CompletedNormalForwardResumption(actor,resume,artifact_guard=lambda:verify_application_evidence(actor),
            rehearsal_guard=lambda:verify_complete_rehearsal(actor))
        try:result=driver.preflight() if args.mode=='forward-preflight' else driver.execute()
        finally:actor.ops.close_locks()
    elif args.mode in {'preflight','execute'}:
        from deployment.lib.completed_normal_execution import CompletedNormalUpgrade,verify_serving
        from deployment.lib.completed_normal_evidence import verify_application_evidence,verify_complete_rehearsal
        from deployment.lib.completed_normal_model import render_candidate_model
        driver=CompletedNormalUpgrade(actor,
            artifact_guard=lambda:verify_application_evidence(actor),
            model_loader=lambda:render_candidate_model(actor),
            acceptance_guard=lambda **kw:verify_serving(actor,**kw),
            rehearsal_guard=lambda:verify_complete_rehearsal(actor))
        try:result=driver.preflight() if args.mode=='preflight' else driver.execute()
        finally:actor.ops.close_locks()
    else:result=actor.resume() if args.mode=='boot' else actor.proxy_gate()
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

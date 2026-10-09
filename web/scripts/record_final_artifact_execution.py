#!/usr/bin/env python3
"""Root-frozen supervisor retaining actual final-artifact process provenance.

No authorization is issued. The child owns only disposable acceptance resources.
Run from a previously measured, immutable source-only private snapshot.
"""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

BASE=Path('/var/lib/madar-control-plane/normal-local-preparation/artifact-acceptance')

def secure(path,directory=False):
    for item in (path,*path.parents):
        stat=item.lstat()
        if item.is_symlink() or stat.st_uid!=0 or stat.st_mode&0o022:raise RuntimeError('artifact_supervisor_untrusted_path')
    if path.stat().st_mode&0o200 or path.stat().st_mode&0o077:raise RuntimeError('artifact_supervisor_source_not_frozen')
    if not (path.is_dir() if directory else path.is_file()):raise RuntimeError('artifact_supervisor_source_missing')
    return path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('artifact_supervisor_isolated_root_required')
    root=Path(__file__).resolve().parents[3]
    if root.parent!=BASE or not re.fullmatch('run-[0-9a-f]{12}',root.name):raise RuntimeError('artifact_supervisor_namespace_invalid')
    secure(root,directory=True)
    manifest_path=secure(root/'source-bundle.json');manifest=json.loads(manifest_path.read_text())
    source=secure(root/'source',directory=True);files=manifest['files']
    if {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file() or p.is_symlink()}!=set(files):
        raise RuntimeError('artifact_supervisor_inventory_changed')
    for relative,expected in files.items():
        name=Path(relative)
        if name.is_absolute() or '..' in name.parts or name.as_posix()!=relative or name.suffix in {'.pyc','.pyo'}:
            raise RuntimeError('artifact_supervisor_source_path_invalid')
        if sha(secure(source/name))!=expected:raise RuntimeError('artifact_supervisor_source_changed')
    input_path=secure(root/'inputs.json');input_sha=sha(input_path);inputs=json.loads(input_path.read_text())
    if inputs['source_sha']!=manifest['source_sha']:raise RuntimeError('artifact_supervisor_source_binding_changed')
    output=root/'execution.json'
    if output.exists() or output.is_symlink():raise FileExistsError('artifact_supervisor_execution_exists')
    argv=['/usr/bin/python3','-I','-B',str(source/'web/scripts/verify_final_application_artifacts.py')]
    started=datetime.now(timezone.utc).isoformat()
    env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','HOME':'/root'}
    try:
        result=subprocess.run(argv,env=env,cwd='/opt/madar-development/repository',capture_output=True,text=True,timeout=1260)
        stdout,stderr,code=result.stdout,result.stderr,result.returncode
    except subprocess.TimeoutExpired:
        # The child has its own1200-second alarm/cleanup; a missing completion is
        # never a PASS. Preserve this independently observed supervisor timeout.
        stdout='';stderr='artifact_supervisor_deadline';code=124
    changed=sha(input_path)!=input_sha or sha(manifest_path)!=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    for relative,expected in files.items():changed=changed or sha(secure(source/relative))!=expected
    if changed:code=125
    record={'version':1,'operation':'actual-final-application-artifact-acceptance','started_at':started,
        'finished_at':datetime.now(timezone.utc).isoformat(),'argv':argv,'source_files':files,
        'inputs_sha256':input_sha,'source_bundle_sha256':sha(manifest_path),'stdout':stdout,'stderr':stderr,'exit_code':code,
        'production_authorization_issued':False}
    with output.open('x') as stream:
        os.fchmod(stream.fileno(),0o600);json.dump(record,stream,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    measured=sha(output)
    if code==0:
        index=BASE/('index-'+measured+'.json')
        with index.open('x') as stream:
            os.fchmod(stream.fileno(),0o600);json.dump({'execution':str(output)},stream);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    print(json.dumps({'operation':'actual-artifact-execution-supervisor','exit_code':code,'execution':str(output),'execution_sha256':measured},sort_keys=True))
    return code

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'operation':'actual-artifact-execution-supervisor','status':'failed','exception_type':type(error).__name__}),flush=True)
        raise SystemExit(1)

#!/usr/bin/env python3
"""Retain an actual new private restore execution as root-protected evidence.

Run only from an independently hash-frozen root-private source snapshot. Never
import installed or restored controller code. The scope is native core, never
normal-source acceptance or full platform recovery. Original evidence is retained.
"""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.provider_recovery_runtime import protected
from deployment.lib.coordinated_checkpoint import verify_inventory,digest_file
from deployment.lib.coordinated_archive_restore import verify_restored_archive

ROOT=Path('/var/lib/madar-control-plane/normal-local-preparation')
SOURCE=ROOT/'offhost-restore-input-n1cv5bua'
NODE1='/srv/data2/madar-backups/normal-local-preparation/checkpoint-20261008T224529Z'
MANIFEST='4c3fe669e4c00e3e8221e8db304d55d5a463d6e3e53cfb0209320b3a8bb0feeb'
ENV={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/root','LANG':'C.UTF-8'}


def execute():
    if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('native_record_frozen_root_required')
    entry=protected(Path(__file__).absolute(),private=True)
    web=entry.parents[1]
    sources={}
    for path in [entry,*sorted((web/'deployment').rglob('*.py')),web/'scripts/verify_restored_native_platform.py',web/'scripts/restore_coordinated_checkpoint.py']:
        protected(path,private=True)
        if path.stat().st_mode&0o200:raise RuntimeError('native_record_source_not_frozen')
        sources[path.relative_to(web).as_posix()]=digest_file(path)
    if digest_file(SOURCE/'manifest.json')!=MANIFEST:raise RuntimeError('native_record_manifest_changed')
    manifest,inventory=verify_inventory(SOURCE);expected={**inventory,'manifest.json':MANIFEST}
    # Read only the known replica as its existing SSH operator. No payload/key
    # export, remote writes, destination guessing or permission bypass.
    remote_code="""import pathlib,hashlib,json,os
root=pathlib.Path(%r);rows={}
if root.is_symlink() or root.stat().st_uid!=os.getuid() or root.stat().st_mode&0o077:raise RuntimeError('replica_directory_untrusted')
for path in sorted(root.iterdir()):
 if not path.is_file() or path.is_symlink() or path.stat().st_uid!=os.getuid() or path.stat().st_mode&0o077:raise RuntimeError('replica_file_untrusted')
 with path.open('rb') as stream:rows[path.name]=hashlib.file_digest(stream,'sha256').hexdigest()
print(json.dumps(rows))
"""%NODE1
    command=['/usr/sbin/runuser','-u','madar','--','/usr/bin/ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
        '-o','UpdateHostKeys=no','-o','ControlMaster=no','-o','ControlPath=none','-o','ConnectTimeout=10',
        'madar-node1-lan','python3 -c '+shlex.quote(remote_code)]
    replica=subprocess.run(command,capture_output=True,text=True,timeout=180,env=ENV)
    if replica.returncode or json.loads(replica.stdout)!=expected:raise RuntimeError('native_record_replica_inventory_changed')
    directory=Path(tempfile.mkdtemp(prefix='native-restore-execution-',dir=ROOT));directory.chmod(0o700)
    def retain(name,payload):
        with (directory/name).open('x') as output:
            os.fchmod(output.fileno(),0o600);output.write(payload);output.flush();os.fsync(output.fileno())
    retain('source-files.json',json.dumps(sources,sort_keys=True)+'\n')
    archives={}
    for entry in manifest['files']:
        if entry['path'].endswith('.tar.gz'):
            archives[entry['path']]=verify_restored_archive(SOURCE/entry['path'],ROOT/'restore-components-aloinivd'/entry['path'].removesuffix('.tar.gz'))
    retain('archive-verification.json',json.dumps(archives,sort_keys=True)+'\n')
    retain('replica-check.json',json.dumps({'node':'madar-node1-lan','object_id':NODE1,'exit_code':replica.returncode,
        'files':expected,'successful_files':len(expected),'manifest_sha256':MANIFEST},sort_keys=True)+'\n')
    argv=['/usr/bin/python3','-I','-B',str(web/'scripts/verify_restored_native_platform.py')]
    started=datetime.now(timezone.utc).isoformat()
    result=subprocess.run(argv,capture_output=True,text=True,timeout=660,env=ENV)
    finished=datetime.now(timezone.utc).isoformat()
    retain('stdout.jsonl',result.stdout);retain('stderr.txt',result.stderr)
    # Record actual failure as failure; never manufacture a matching PASS packet.
    lines=[json.loads(line) for line in result.stdout.splitlines()]
    report=lines[-1] if lines else {}
    receipt={'version':1,'operation':'supervised-private-native-core-restore','scope':'native-core',
        'checkpoint_manifest_sha256':MANIFEST,'started_at':started,'finished_at':finished,'argv':argv,
        'exit_code':result.returncode,'source_files_sha256':digest_file(directory/'source-files.json'),
        'stdout_sha256':digest_file(directory/'stdout.jsonl'),'stderr_sha256':digest_file(directory/'stderr.txt'),
        'replica_check_sha256':digest_file(directory/'replica-check.json'),
        'archive_verification_sha256':digest_file(directory/'archive-verification.json'),
        'original_evidence_modified':False,'source_application_acceptance_claimed':False}
    retain('execution.json',json.dumps(receipt,sort_keys=True)+'\n')
    if result.returncode or report.get('operation')!='actual-offhost-private-native-core-restore':
        raise RuntimeError('native_record_actual_execution_failed')
    return {'root_execution_directory':str(directory),'execution_sha256':digest_file(directory/'execution.json'),
        'native_core_restored':True,'storage_objects':report['storage_objects'],'native_login_aal2':report['native_login_and_aal2_verified'],
        'replica_files_verified':len(expected),'production_modified':False,'normal_acceptance_proven':False}

if __name__=='__main__':
    try:print(json.dumps(execute()))
    except Exception as error:
        print(json.dumps({'status':'failed','exception_type':type(error).__name__,'category':str(error) if type(error) is RuntimeError else 'native_record_failed'}))
        raise SystemExit(1)

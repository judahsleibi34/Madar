#!/usr/bin/env python3
"""Restore the exact existing Node 1 replica without altering its backup.

Read-only SSH streams precisely the fourteen approved files into a NEW private
restore-input quarantine on Node 2. No checkpoint is captured, original changed,
key exported, remote file written, image pulled or production service altered.
The recovered archive quarantine is independently measured again, and a NEW
networkless database restore is executed from those
transported bytes. This is component proof, not platform/application acceptance.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.coordinated_checkpoint import verify_inventory,digest_file
from scripts.restore_coordinated_checkpoint import restore,stage,ROOT

MANIFEST='4c3fe669e4c00e3e8221e8db304d55d5a463d6e3e53cfb0209320b3a8bb0feeb'
LOCAL=ROOT/'checkpoint-20261008T224529Z'
REMOTE='/srv/data2/madar-backups/normal-local-preparation/checkpoint-20261008T224529Z'
SSH=['sudo','-n','-u','madar','ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
     '-o','UpdateHostKeys=no','-o','ControlMaster=no','-o','ControlPath=none','-o','ConnectTimeout=10','madar-node1-lan']


def receive(stream,destination,expected):
    """No links, traversal, sparse entries, duplicates, extra or partial files."""
    seen=set()
    with tarfile.open(fileobj=stream,mode='r|') as archive:
        for member in archive:
            if (member.name not in expected or member.name in seen or not member.isfile()
                    or member.sparse or member.size!=expected[member.name]['size']):
                raise RuntimeError('offhost_restore_transport_member_invalid')
            seen.add(member.name);target=destination/member.name;check=hashlib.sha256()
            with archive.extractfile(member) as source,target.open('xb') as output:
                while chunk:=source.read(1024*1024):output.write(chunk);check.update(chunk)
                output.flush();os.fsync(output.fileno())
            target.chmod(0o400)
            if check.hexdigest()!=expected[member.name]['sha256'] or digest_file(target)!=check.hexdigest():
                raise RuntimeError('offhost_restore_transport_bytes_changed')
    if seen!=set(expected):raise RuntimeError('offhost_restore_transport_incomplete')
    return {name:expected[name]['sha256'] for name in sorted(seen)}


def execute():
    if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('offhost_restore_frozen_root_entry_required')
    if digest_file(LOCAL/'manifest.json')!=MANIFEST:raise RuntimeError('offhost_restore_reference_changed')
    packet,_=verify_inventory(LOCAL)
    expected={entry['path']:{'sha256':entry['sha256'],'size':entry['size']} for entry in packet['files']}
    expected['manifest.json']={'sha256':MANIFEST,'size':(LOCAL/'manifest.json').stat().st_size}
    if len(expected)!=14 or any(Path(name).name!=name for name in expected):
        raise RuntimeError('offhost_restore_exact_scope_required')
    destination=Path(tempfile.mkdtemp(prefix='offhost-restore-input-',dir=ROOT));destination.chmod(0o700)
    stage('read_existing_node1_replica')
    command=shlex.join(['tar','-C',REMOTE,'-cf','-','--',*sorted(expected)])
    process=subprocess.Popen(SSH+[command],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8'})
    try:
        transported=receive(process.stdout,destination,expected)
        if process.wait(timeout=30)!=0:raise RuntimeError('offhost_restore_ssh_failed')
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=10)
    destination.chmod(0o500)
    if verify_inventory(destination)[1]!=verify_inventory(LOCAL)[1]:
        raise RuntimeError('offhost_restore_inventory_changed')
    result=restore(destination,MANIFEST,existing_quarantine=ROOT/'restore-components-aloinivd')
    result.update({'operation':'actual-node1-replica-component-restore','source_replica':REMOTE,
        'source_host':'madar-node1-lan','restore_host':'node2','transport_exit_code':0,
        'existing_archive_quarantine_independently_reverified':True,
        'transported_files':transported,'transported_file_count':14,'original_backup_modified':False,
        'new_checkpoint_captured':False,'offhost_restore_proven':False,
        'offhost_component_restore_verified':True,
        'offhost_restore_scope':'coordinated-components-only'})
    return result

if __name__=='__main__':
    def expired(*_):raise RuntimeError('offhost_restore_deadline')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,1800)
    try:print(json.dumps(execute()),flush=True)
    except Exception as error:
        print(json.dumps({'operation':'actual-node1-replica-component-restore','status':'failed',
            'exception_type':type(error).__name__,'failure_category':str(error) if type(error) is RuntimeError else 'restore_failed'}),flush=True);sys.exit(1)
    finally:signal.setitimer(signal.ITIMER_REAL,0)

#!/usr/bin/env python3
"""Exact append-only transfer of the approved sealed recovery checkpoint.

Requires root-owned frozen sender and receiver source plus explicit operator
approval of this payload, source, manifest and destination. No production state,
backup LATEST/freshness/retention or historical evidence mutation is available.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tarfile

SOURCE=Path('/var/lib/madar-control-plane/normal-local-preparation/checkpoint-20261008T224529Z')
MANIFEST='4c3fe669e4c00e3e8221e8db304d55d5a463d6e3e53cfb0209320b3a8bb0feeb'
SSH=['sudo','-n','-u','madar','ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
     '-o','UpdateHostKeys=no','-o','ControlMaster=no','-o','ControlPath=none','-o','ConnectTimeout=10','madar-node1-lan']


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def transfer(expected_receiver):
    if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('checkpoint_transfer_frozen_root_entry_required')
    receiver=Path(__file__).with_name('checkpoint_replica.py')
    for path in (Path(__file__),receiver,receiver.parent):
        st=path.lstat()
        if path.is_symlink() or st.st_uid!=0 or st.st_mode&0o022:
            raise RuntimeError('checkpoint_transfer_source_untrusted')
    # Frozen code snapshots under /tmp have a sticky writable /tmp ancestor;
    # stop trust traversal at the root-private snapshot, not the public parent.
    code=receiver.read_bytes()
    if hashlib.sha256(code).hexdigest()!=expected_receiver:
        raise RuntimeError('checkpoint_receiver_source_changed')
    for path in (SOURCE,*SOURCE.parents):
        st=path.lstat()
        if path.is_symlink() or st.st_uid!=0 or st.st_mode&0o022:
            raise RuntimeError('checkpoint_transfer_payload_untrusted')
    manifest=SOURCE/'manifest.json'
    if sha(manifest)!=MANIFEST:raise RuntimeError('checkpoint_transfer_manifest_changed')
    packet=json.loads(manifest.read_text())
    selected=[manifest]
    for entry in packet['files']:
        name=entry['path']
        if Path(name).name!=name or name in {'','.','..','manifest.json'}:
            raise RuntimeError('checkpoint_transfer_payload_path_invalid')
        path=SOURCE/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size!=entry['size'] or sha(path)!=entry['sha256']:
            raise RuntimeError('checkpoint_transfer_payload_changed')
        selected.append(path)
    if {p.name for p in SOURCE.iterdir()}!={p.name for p in selected}:
        raise RuntimeError('checkpoint_transfer_inventory_inexact')
    invocation="import base64;exec(compile(base64.b64decode("+repr(base64.b64encode(code).decode())+"),'approved-checkpoint-receiver','exec'))"
    remote=shlex.join(['python3','-I','-B','-c',invocation,SOURCE.name,MANIFEST])
    process=subprocess.Popen(SSH+[remote],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8'})
    try:
        with tarfile.open(fileobj=process.stdin,mode='w|') as archive:
            for path in selected:archive.add(path,arcname=path.name,recursive=False)
        process.stdin.close();process.stdin=None
        stdout,stderr=process.communicate(timeout=1200)
        if process.returncode:raise RuntimeError('checkpoint_transfer_remote_failed')
        receipt=json.loads(stdout)
        if receipt.get('manifest_sha256')!=MANIFEST or receipt.get('files')!=len(packet['files']) or receipt.get('latest_modified') is not False:
            raise RuntimeError('checkpoint_transfer_receipt_invalid')
        return {'operation':'actual-append-only-checkpoint-transfer','receiver_sha256':expected_receiver,
                'source_manifest_sha256':MANIFEST,'receiver':receipt,'stderr_present':bool(stderr)}
    finally:
        if process.poll() is None:
            process.kill();process.wait(timeout=10)

if __name__=='__main__':
    def deadline(signum,frame):raise RuntimeError('checkpoint_transfer_deadline')
    signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,1200)
    try:print(json.dumps(transfer(sys.argv[1])))
    except Exception as error:
        print(json.dumps({'operation':'actual-append-only-checkpoint-transfer','status':'failed',
                         'exception_type':type(error).__name__,'stage':str(error) if type(error) is RuntimeError else 'transfer_failed'}));sys.exit(1)
    finally:signal.setitimer(signal.ITIMER_REAL,0)

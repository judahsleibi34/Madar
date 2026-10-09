#!/usr/bin/env python3
"""Append-only sealed checkpoint receiver; no retention or LATEST publication.

Run this exact reviewed source over the existing pinned SSH connection. The
payload is an unencrypted online SSH replica, not an offline/immutable medium.
Partial attempts remain retained and cannot replace an existing replica.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile

ROOT=Path('/srv/data2/madar-backups')
UUID='aafa8641-ab59-4927-9146-c1f9bf9abf3f'
MAX_BYTES=40*1024**3
KINDS={'database','roles','storage','auth_metadata','application_storage',
       'native_config','production_config','images','controller','schema','ledgers'}


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify(root, expected_manifest):
    manifest=root/'manifest.json'
    if manifest.is_symlink() or not manifest.is_file() or sha(manifest)!=expected_manifest:
        raise RuntimeError('replica_manifest_mismatch')
    packet=json.loads(manifest.read_text())
    if packet.get('schema')!=115 or packet.get('sealed') is not True or packet.get('version')!=1:
        raise RuntimeError('replica_manifest_scope_invalid')
    inventory={};kinds=set()
    for entry in packet['files']:
        name=entry['path']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',name) or name in inventory or name=='manifest.json':
            raise RuntimeError('replica_inventory_invalid')
        file=root/name
        if file.is_symlink() or not file.is_file() or file.stat().st_size!=entry['size'] or sha(file)!=entry['sha256']:
            raise RuntimeError('replica_bytes_mismatch')
        inventory[name]=entry['sha256'];kinds.add(entry['kind'])
    if not KINDS<=kinds or {p.name for p in root.iterdir()}!=set(inventory)|{'manifest.json'}:
        raise RuntimeError('replica_inventory_incomplete')
    return inventory


def storage():
    for part in (ROOT,*ROOT.parents):
        stat=part.lstat()
        if part.is_symlink() or stat.st_mode&0o022 or stat.st_uid not in {0,os.geteuid()}:
            raise RuntimeError('replica_destination_untrusted')
    if ROOT.stat().st_uid!=os.geteuid() or ROOT.stat().st_mode&0o077:
        raise RuntimeError('replica_private_destination_required')
    result=subprocess.run(['findmnt','-n','-o','UUID','-T',str(ROOT)],capture_output=True,text=True,timeout=10)
    if result.returncode or result.stdout.strip()!=UUID:
        raise RuntimeError('replica_filesystem_binding_changed')
    return ROOT


def receive(checkpoint_id, manifest_hash):
    if not re.fullmatch(r'checkpoint-[0-9]{8}T[0-9]{6}Z',checkpoint_id) or not re.fullmatch(r'[0-9a-f]{64}',manifest_hash):
        raise RuntimeError('replica_argument_invalid')
    parent=storage()/'normal-local-preparation'
    if not parent.exists():parent.mkdir(mode=0o700)
    if parent.is_symlink() or parent.stat().st_uid!=os.geteuid() or parent.stat().st_mode&0o077:
        raise RuntimeError('replica_namespace_untrusted')
    final=parent/checkpoint_id
    if final.exists() or final.is_symlink():raise RuntimeError('replica_destination_exists')
    incomplete=parent/('.'+checkpoint_id+'.incomplete')
    incomplete.mkdir(mode=0o700) # exclusive; retain failed attempts
    total=0;seen=set()
    with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:
        for member in archive:
            name=member.name
            if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',name) or name in seen
                    or not member.isfile() or member.sparse or len(seen)>=64):
                raise RuntimeError('replica_unsafe_archive')
            total+=member.size
            if total>MAX_BYTES:raise RuntimeError('replica_size_limit')
            seen.add(name)
            with archive.extractfile(member) as source,(incomplete/name).open('xb') as target:
                while chunk:=source.read(1024*1024):target.write(chunk)
                target.flush();os.fsync(target.fileno())
            (incomplete/name).chmod(0o400)
    inventory=verify(incomplete,manifest_hash)
    incomplete.chmod(0o500)
    # Existing final path must never be silently replaced. Rename with Linux
    # RENAME_NOREPLACE rather than an exists/rename TOCTOU window.
    import ctypes
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.renameat2(-100,os.fsencode(incomplete),-100,os.fsencode(final),1)!=0:
        raise RuntimeError('replica_exclusive_publication_failed')
    fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    # Independent second measurement of the published destination.
    if verify(final,manifest_hash)!=inventory:raise RuntimeError('replica_postpublication_changed')
    return {'operation':'append-only-checkpoint-replica','destination':str(final),'manifest_sha256':manifest_hash,
        'files':len(inventory),'bytes':total,'filesystem_uuid':UUID,'protection':'online-ssh-unencrypted',
        'restore_verified':False,'historical_backups_modified':False,'latest_modified':False,'retention_run':False}

if __name__=='__main__':
    try:print(json.dumps(receive(sys.argv[1],sys.argv[2])))
    except Exception as error:
        print(json.dumps({'operation':'append-only-checkpoint-replica','status':'failed',
            'exception_type':type(error).__name__,'stage':str(error) if type(error) is RuntimeError else 'receiver_failed'}));sys.exit(1)

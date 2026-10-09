#!/usr/bin/env python3
"""Append-only receiver for a newly approved post-normal logical backup.

Run only as the existing Node 1 SSH operator with reviewed source in memory.
No historical backup, LATEST pointer, retention, key or installed service changes.
Online SSH replication is not offline encryption or physical immutability.
"""
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import backup_support as backup

BASE=Path('/srv/data2/madar-backups')

def receive(plan_sha,backup_id,sums_sha,filesystem_uuid):
    if (not re.fullmatch(r'[0-9a-f]{64}',plan_sha) or not backup.BACKUP_ID.fullmatch(backup_id)
            or not re.fullmatch(r'[0-9a-f]{64}',sums_sha) or not re.fullmatch(r'[0-9a-f-]{36}',filesystem_uuid)):
        raise RuntimeError('normal_replica_binding_invalid')
    for path in (BASE,*BASE.parents):
        st=path.lstat()
        if path.is_symlink() or st.st_uid not in {0,os.getuid()} or st.st_mode&0o002:
            raise RuntimeError('normal_replica_parent_untrusted')
    if BASE.stat().st_uid!=os.getuid() or BASE.stat().st_mode&0o077:
        raise RuntimeError('normal_replica_base_not_private')
    observed=subprocess.run(['findmnt','-T',str(BASE),'-n','-o','SOURCE,FSTYPE,TARGET,UUID'],capture_output=True,text=True,timeout=10)
    if observed.returncode or observed.stdout.split()!=['/dev/sdc1','ext4','/srv/data2',filesystem_uuid]:
        raise RuntimeError('normal_replica_filesystem_changed')
    parent=BASE/'normal-local-production';parent.mkdir(mode=0o700,exist_ok=True)
    if parent.is_symlink() or parent.stat().st_uid!=os.getuid() or parent.stat().st_mode&0o077:
        raise RuntimeError('normal_replica_namespace_untrusted')
    scope=parent/plan_sha
    # A failed previous transfer and its partial input remain preserved. No
    # silent replacement, deletion, reauthorization or idempotent overwrite.
    scope.mkdir(mode=0o700)
    staging=scope/'incoming';staging.mkdir(mode=0o700)
    available=shutil.disk_usage(scope).free-10*1024**3;count=0;size=0
    with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:
        for member in archive:
            relative=PurePosixPath(member.name)
            if relative.is_absolute() or '..' in relative.parts or not (member.isfile() or member.isdir()):
                raise RuntimeError('normal_replica_archive_member_invalid')
            count+=1;size+=member.size
            if count>1000000 or member.size<0 or size>available:raise RuntimeError('normal_replica_capacity_exceeded')
            target=staging.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True,exist_ok=True,mode=0o700);continue
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            with target.open('xb') as stream:
                os.fchmod(stream.fileno(),0o600)
                shutil.copyfileobj(archive.extractfile(member),stream,length=1024*1024)
                stream.flush();os.fsync(stream.fileno())
    if backup.digest(staging/'SHA256SUMS')!=sums_sha:raise RuntimeError('normal_replica_checksum_manifest_changed')
    manifest=backup.verify(staging,dump=False)
    if manifest.get('backup_id')!=backup_id or int(manifest.get('database',{}).get('schema_version',0))!=115:
        raise RuntimeError('normal_replica_backup_identity_changed')
    final=scope/backup_id;os.rename(staging,final)
    for path in final.rglob('*'):path.chmod(0o400 if path.is_file() else 0o500)
    final.chmod(0o500);scope.chmod(0o500)
    descriptor=os.open(scope,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)
    # backup.verify has independently checked the complete received inventory.
    return {'operation':'actual-append-only-normal-backup-replica','plan_sha256':plan_sha,
        'backup_id':backup_id,'destination':str(final),'sha256sums_sha256':sums_sha,
        'archive_entries':count,'files':sum(path.is_file() for path in final.rglob('*')),'bytes':size,'checksum_exit_code':0,'historical_backups_modified':False,
        'latest_modified':False,'retention_performed':False,'schema':115}

if __name__=='__main__':
    try:print(json.dumps(receive(*sys.argv[1:]),sort_keys=True))
    except Exception as error:
        print(json.dumps({'operation':'normal-backup-replica','status':'failed','exception_type':type(error).__name__}),flush=True)
        raise SystemExit(1)

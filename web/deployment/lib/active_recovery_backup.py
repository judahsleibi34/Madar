"""Execute supported post-normal backup/restore and append-only Node 1 replication.

A new scoped ordinary backup is not a replacement coordinated checkpoint.
No historical LATEST/retention target, production database or schema is changed.
"""
import base64
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import shlex
import subprocess
import tarfile
import tempfile

from deployment.lib.active_recovery_artifact_evidence import verify_artifact_acceptance, NODE1_CONFIGURATION
from deployment.lib.active_recovery_inputs import INPUTS
from deployment.lib.environment_file import load_environment_file
from deployment.lib.provider_recovery_runtime import protected, readonly_configuration, file_digest
from deployment.lib.emergency_routing_repair import exclusive, encoded

ENVIRONMENT={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}

def checked(args, *, env=None, user=None, timeout=1800, stdin=None):
    result=subprocess.run(args,env=env or ENVIRONMENT,user=user,group=user,extra_groups=[] if user is not None else None,
        stdin=stdin,capture_output=True,text=True,timeout=timeout)
    if result.returncode:raise RuntimeError('normal_backup_command_failed')
    return result.stdout

def remote_receiver(package,plan,backup,sums,filesystem_uuid):
    # Freeze only reviewed non-secret code at a NEW append-only Node 1 path.
    # SSH uses the operator's existing alias/host-key/key policy; no private key
    # content is read, copied or recorded by this operation.
    files={name:(package/'source/web/scripts'/name).read_bytes()
        for name in ('normal_backup_replica.py','backup_support.py')}
    payload={name:{'bytes':base64.b64encode(data).decode(),'sha256':hashlib.sha256(data).hexdigest()}
        for name,data in files.items()}
    code="""import base64,hashlib,json,os,pathlib,runpy,sys
payload=json.loads(base64.b64decode(sys.argv[1]))
base=pathlib.Path('/srv/data2/madar-backups/normal-local-production-code')
for p in (base.parent,*base.parent.parents):
 s=p.lstat()
 if p.is_symlink() or s.st_mode&2:raise RuntimeError('receiver_parent_untrusted')
base.mkdir(mode=0o700,exist_ok=True)
if base.is_symlink() or base.stat().st_uid!=os.getuid() or base.stat().st_mode&0o077:raise RuntimeError('receiver_namespace_untrusted')
root=base/sys.argv[2];root.mkdir(mode=0o700)
for name,item in payload.items():
 if name not in {'normal_backup_replica.py','backup_support.py'}:raise RuntimeError('receiver_source_invalid')
 data=base64.b64decode(item['bytes'])
 if hashlib.sha256(data).hexdigest()!=item['sha256']:raise RuntimeError('receiver_source_changed')
 with (root/name).open('xb') as out:out.write(data);out.flush();os.fsync(out.fileno())
 (root/name).chmod(0o500)
root.chmod(0o500)
sys.path.insert(0,str(root));sys.argv=[str(root/'normal_backup_replica.py'),*sys.argv[2:]]
runpy.run_path(sys.argv[0],run_name='__main__')
"""
    args=['/usr/bin/python3','-I','-B','-c',code,base64.b64encode(json.dumps(payload).encode()).decode(),
        plan.digest,backup.name,sums,filesystem_uuid]
    return ['/usr/sbin/runuser','-u','madar','--','/usr/bin/ssh','-o','BatchMode=yes',
        '-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no','-o','ControlMaster=no',
        '-o','ControlPath=none','-o','ConnectTimeout=10','madar-node1-lan',shlex.join(args)]

def capture_and_replicate(plan,root,package,source_guard,kernel):
    source_guard();kernel.normal()
    acceptance=verify_artifact_acceptance(plan)
    replica=acceptance['node1_replica']
    if file_digest(readonly_configuration(NODE1_CONFIGURATION,private=True))!=replica['configuration_sha256']:
        raise RuntimeError('normal_backup_node1_configuration_changed')
    started=datetime.now(timezone.utc).isoformat()
    identity=pwd.getpwnam('madar')
    canonical=Path('/var/lib/madar/backups')
    scope=canonical/('normal-local-'+plan.digest)
    if scope.exists() or scope.is_symlink():raise FileExistsError('normal_backup_scope_exists')
    if not scope.parent.is_dir() or scope.parent.is_symlink():raise RuntimeError('normal_backup_parent_missing')
    scope.mkdir(mode=0o700);os.chown(scope,identity.pw_uid,identity.pw_gid)
    cfg={};load_environment_file(readonly_configuration(INPUTS['backup_configuration'],private=True),environ=cfg)
    paths={};load_environment_file(protected(Path('/opt/madar/control-plane/deployment/production-paths.conf')),environ=paths)
    # Configuration data cannot select a shell/interpreter/loader or credentials.
    if any(key.startswith(('LD_','PYTHON','DOCKER_','GIT_')) or key in {'PATH','HOME','BASH_ENV','ENV','SHELL','CREDENTIALS_DIRECTORY'} for key in cfg):
        raise RuntimeError('normal_backup_environment_invalid')
    env={**ENVIRONMENT,**cfg,**paths,'HOME':'/home/madar','CREDENTIALS_DIRECTORY':'/etc/madar',
        'MADAR_BACKUP_DIR':str(scope),'MADAR_BACKUP_FRESHNESS_MARKER':'','MADAR_BACKUP_STATE_DIR':'',
        'MADAR_BACKUP_KEEP_COUNT':'1','MADAR_PROVIDER_BACKUP_REQUIRED':'true'}
    for name in ('backup_support.py','backup_madar.sh','verify_backup.sh'):
        actual=Path('/usr/local/lib/madar')/name
        expected=package/'source/web/scripts'/name
        if file_digest(protected(actual))!=file_digest(protected(expected,private=True)):
            raise RuntimeError('normal_backup_installed_helper_changed')
    checked(['/usr/bin/python3','-I','-B','/usr/local/lib/madar/backup_support.py','scheduled',
        '/usr/local/lib/madar/backup_madar.sh'],env=env,user=identity.pw_uid)
    backups=list(scope.glob('madar-*'))
    if len(backups)!=1 or not backups[0].is_dir():raise RuntimeError('normal_backup_output_invalid')
    backup=backups[0]
    from scripts import backup_support
    manifest=backup_support.verify(backup)
    if int(manifest['database']['schema_version'])!=115 or manifest['release']['git_sha']!=plan.source_sha:
        raise RuntimeError('normal_backup_release_changed')
    row=json.loads(checked(['/usr/bin/docker','--host','unix:///var/run/docker.sock','image','inspect',
        kernel.runtime.inspect(['supabase-db'])['supabase-db']['Image']]))[0]
    digests=row.get('RepoDigests',[])
    if not digests:raise RuntimeError('normal_backup_restore_image_digest_missing')
    from scripts.rehearse_backup import rehearse
    restore=rehearse(backup,digests[0],postgres_preload=('pg_cron','pg_net'))
    if restore.get('status')!='logical_database_and_file_restore_passed' or restore.get('backup_schema')!=115:
        raise RuntimeError('normal_backup_actual_restore_incomplete')
    sums=backup_support.digest(backup/'SHA256SUMS')
    # Stream only this verified scoped backup. A failed receiver is retained;
    # no second attempt silently overwrites it.
    with tempfile.TemporaryFile() as archive:
        with tarfile.open(fileobj=archive,mode='w') as tar:
            for child in sorted(backup.iterdir()):tar.add(child,arcname=child.name,recursive=True)
        archive.seek(0)
        output=checked(remote_receiver(package,plan,backup,sums,replica['filesystem_uuid']),stdin=archive)
    remote=json.loads(output)
    if (remote.get('operation')!='actual-append-only-normal-backup-replica' or remote.get('plan_sha256')!=plan.digest
            or remote.get('backup_id')!=backup.name or remote.get('sha256sums_sha256')!=sums
            or type(remote.get('checksum_exit_code')) is not int or remote['checksum_exit_code']!=0
            or remote.get('historical_backups_modified') is not False):
        raise RuntimeError('normal_backup_replica_verification_failed')
    if backup_support.digest(backup/'SHA256SUMS')!=sums:raise RuntimeError('normal_backup_changed_during_replication')
    backup_support.verify(backup);source_guard();kernel.normal()
    # Publish this same already-verified backup (no second dump/checkpoint) to
    # the configured ordinary root before restoring its backup timers. Existing
    # LATEST bytes are archived; directory publication refuses all collisions.
    if cfg.get('MADAR_BACKUP_DIR')!=str(canonical) or cfg.get('MADAR_BACKUP_FRESHNESS_MARKER')!=str(canonical/'LATEST'):
        raise RuntimeError('normal_backup_configured_root_changed')
    latest=canonical/'LATEST'
    exclusive(root/'ordinary-latest-preimage',readonly_configuration(latest,private=False).read_bytes())
    final=canonical/backup.name
    libc=ctypes.CDLL(None,use_errno=True)
    rename=libc.renameat2;rename.argtypes=(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint)
    if rename(-100,os.fsencode(backup),-100,os.fsencode(final),1)!=0:
        raise OSError(ctypes.get_errno(),'normal_backup_collision_or_publication_failed')
    backup=final
    descriptor=os.open(canonical,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)
    backup_support.verify(backup)
    exclusive(root/'post-cutover-backup.json',encoded({'operation':'actual-post-normal-backup-restore-replica',
        'plan_sha256':plan.digest,'source_sha':plan.source_sha,'images':plan.candidate_images,'schema':115,
        'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
        'local_path':str(backup),'sha256sums_sha256':sums,'restore':restore,'node1':remote,
        'customer_database_restored':False,'migration_executed':False,'historical_backups_modified':False}))
    # Publish freshness only after actual local restore and complete remote proof.
    backup_support.publish_marker(backup,canonical/'LATEST',Path('/var/lib/madar/backup-state'))
    os.chown(canonical/'LATEST',identity.pw_uid,identity.pw_gid)
    os.chown(Path('/var/lib/madar/backup-state/latest.json'),identity.pw_uid,identity.pw_gid)

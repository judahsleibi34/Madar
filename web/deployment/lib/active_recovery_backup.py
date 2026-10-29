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
import re
import shlex
import subprocess
import tarfile
import tempfile

from deployment.lib.active_recovery_artifact_evidence import verify_artifact_acceptance, NODE1_CONFIGURATION
from deployment.lib.active_recovery_inputs import INPUTS
from deployment.lib.environment_file import load_environment_file
from deployment.lib.provider_recovery_runtime import protected, readonly_configuration, file_digest
from deployment.lib.emergency_routing_repair import exclusive, encoded
from deployment.lib.completed_normal_profile import maintenance_role

ENVIRONMENT={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8'}

def latest_preimage_name(completed_context=None):
    # A compatible upgrade publishes two distinct ordinary backups. Preserve
    # each exact LATEST preimage without replaying or replacing the first one.
    if completed_context is None:return 'ordinary-latest-preimage'
    if completed_context.stage not in {'pre-migration','post-migration'}:
        raise RuntimeError('normal_backup_preimage_stage_invalid')
    return completed_context.stage+'-ordinary-latest-preimage'

def checked(args, *, env=None, user=None, timeout=1800, stdin=None, pass_fds=()):
    if user is not None:args=['/usr/bin/setpriv','--no-new-privs',*args]
    result=subprocess.run(args,env=env or ENVIRONMENT,user=user,group=user,extra_groups=[] if user is not None else None,
        stdin=stdin,capture_output=True,text=True,timeout=timeout,pass_fds=pass_fds)
    if result.returncode:
        # Never retain raw child output: it can contain private paths or values.
        codes = {'local_backup_direct_database_unavailable', 'local_backup_binding_invalid',
                 'local_backup_database_configuration_mismatch', 'backup_live_release_mismatch',
                 'retention_minimum_two'}
        code = next((line[7:] for line in result.stderr.splitlines()
                     if line.startswith('ERROR: ') and line[7:] in codes), 'child_exit_nonzero')
        raise RuntimeError('normal_backup_command_failed:' + code)
    return result.stdout

def verify_backup_execution_context(package, *, expected_schema=115, completed_context=None, maintenance_contract=None):
    """Read-only gate with the exact uid/gid, empty groups and sealed DB lease.

    Recovery's version endpoint deliberately differs from known-good normal
    production; the scheduled release-match check remains mandatory at capture.
    This gate tests direct libpq and every managed source before any write grant.
    No dump, freshness publication, retention, service or customer write occurs.
    """
    from scripts import backup_support
    if completed_context is not None and maintenance_contract is not None:
        raise RuntimeError('normal_backup_operation_context_conflict')
    contract=maintenance_contract
    if maintenance_contract is not None:
        from deployment.lib.completed_normal_admission import validate_provider_preparation
        from deployment.lib.completed_normal_profile import RECONCILED
        if (validate_provider_preparation(maintenance_contract) is not RECONCILED
                or type(expected_schema) is not int or expected_schema!=146):
            raise RuntimeError('normal_backup_preflight_contract_invalid')
    if expected_schema==160 and type(expected_schema) is int:
        from deployment.lib.completed_normal_backup import CompletedNormalBackupContext
        from deployment.lib.completed_normal_admission import validate_provider_preparation
        from deployment.lib.completed_normal_profile import RECONCILED
        if (type(completed_context) is not CompletedNormalBackupContext
                or validate_provider_preparation(completed_context.contract) is not RECONCILED
                or completed_context.schema!=160 or completed_context.stage!='post-migration'
                or completed_context.provider_adapter is None or Path(package)!=completed_context.package):
            raise RuntimeError('normal_backup_canonical_context_required')
        completed_context.validate(completed_context.plan,completed_context.root,package)
        completed_context.guard()
        contract=completed_context.contract
    elif completed_context is not None or type(expected_schema) is not int or expected_schema not in {115,136,144,146,148}:
        raise RuntimeError('normal_backup_execution_schema_invalid')
    identity = pwd.getpwnam('madar')
    cfg = {}
    configuration=readonly_configuration(INPUTS['backup_configuration'], private=True)
    if contract is not None and file_digest(configuration)!=contract['database']['backup_configuration_sha256']:
        raise RuntimeError('normal_backup_preflight_configuration_changed')
    load_environment_file(configuration, environ=cfg)
    if any(key.startswith(('LD_', 'PYTHON', 'DOCKER_', 'GIT_')) or key in {
            'PATH', 'HOME', 'BASH_ENV', 'ENV', 'SHELL', 'CREDENTIALS_DIRECTORY',
            backup_support.LOCAL_DATABASE_FD} for key in cfg):
        raise RuntimeError('normal_backup_environment_invalid')
    env = {**ENVIRONMENT, **cfg, 'HOME':'/home/madar', 'PGCONNECT_TIMEOUT':'5'}
    role=maintenance_role(contract) if contract is not None else 'postgres'
    expected = {'PGHOST':'supabase-db', 'PGPORT':'5432', 'PGUSER':role,
                'PGDATABASE':'postgres', 'PGSSLMODE':'disable'}
    if any(env.get(key) != value for key, value in expected.items()):
        raise RuntimeError('normal_backup_database_configuration_mismatch')
    descriptor = backup_support.sealed_local_database_binding(**({'maintenance_role':role} if role!='postgres' else {}))
    try:
        address = json.loads(os.pread(descriptor,4096,0))['address']
        env['PGHOSTADDR'] = address
        code = """import json,os,pathlib,subprocess
if os.getgroups():raise RuntimeError('backup_supplementary_groups_present')
if not pathlib.Path('/etc/madar/production.env').is_file():raise RuntimeError('backup_credential_missing')
with open('/etc/madar/production.env','rb') as source:source.read()
roots=[pathlib.Path(os.environ.get(key, '/var/lib/madar/storage/'+name)) for key,name in (
 ('MADAR_BUILDER_ASSETS_DIR','uploads'),('MADAR_PRIVATE_UPLOADS_DIR','private_uploads'),
 ('MADAR_GENERATED_ARTIFACTS_DIR','private_generated_charts'),('MADAR_AVATARS_DIR','avatar_uploads'))]
def denied(error):raise RuntimeError('backup_managed_source_denied')
for root in roots:
 if root.is_symlink() or not root.is_dir():raise RuntimeError('backup_managed_source_missing')
 for base,dirs,files in os.walk(root,onerror=denied):
  for name in dirs+files:
   path=pathlib.Path(base)/name
   if path.is_symlink():raise RuntimeError('backup_managed_source_symlink')
   if path.is_file():
    with path.open('rb') as source:
     while source.read(1024*1024):pass
result=subprocess.run(['/usr/bin/psql','-X','-At','-v','ON_ERROR_STOP=1','-c',
 "BEGIN READ ONLY; SELECT schema_version FROM public.application_schema_state WHERE contract_key='core'; COMMIT;"],
 capture_output=True,text=True,timeout=15)
if result.returncode or '115' not in result.stdout.splitlines():raise RuntimeError('backup_direct_postgresql_unavailable')
print(json.dumps({'uid':os.getuid(),'gid':os.getgid(),'supplementary_groups':os.getgroups(),
 'schema':115,'database_read_only':True,'managed_sources_readable':True,'credential_readable':True}))
"""
        expected=str(expected_schema)
        if contract is not None:
            code=code.replace('SELECT schema_version FROM public.application_schema_state',
                "SELECT schema_version::text || ':' || (SELECT system_identifier::text FROM pg_control_system()) FROM public.application_schema_state")
            expected+=':'+contract['database']['system_identifier']
        code=code.replace("'115'",repr(expected)).replace("'schema':115","'schema':"+str(expected_schema))
        result = json.loads(checked(['/usr/bin/python3','-I','-B','-c',code], env=env,
                                    user=identity.pw_uid, timeout=120))
    finally:
        os.close(descriptor)
    if backup_support.direct_local_database_address() != address:
        raise RuntimeError('normal_backup_database_address_changed')
    return result


def remote_receiver(package,plan,backup,sums,filesystem_uuid,*,expected_schema=115,namespace='normal-local-production',maintenance_manifest_sha256=None):
    if type(expected_schema) is int and expected_schema==160:
        from scripts import backup_support
        backup_support.verify_reconciled_maintenance(backup,expected_sha256=maintenance_manifest_sha256,
            schema=160,scope=plan.digest)
    if (type(expected_schema) is not int or expected_schema not in {115,136,144,146,148,150,160}
            or namespace not in {'normal-local-production','private-schema136-rehearsal'}
            or expected_schema in {150,160} and maintenance_manifest_sha256 is None
            or maintenance_manifest_sha256 is not None and not re.fullmatch('[0-9a-f]{64}',str(maintenance_manifest_sha256))):
        raise RuntimeError('normal_backup_replica_scope_invalid')
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
        plan.digest,backup.name,sums,filesystem_uuid,str(expected_schema),namespace]
    if maintenance_manifest_sha256 is not None:args.append(maintenance_manifest_sha256)
    return ['/usr/sbin/runuser','-u','madar','--','/usr/bin/ssh','-o','BatchMode=yes',
        '-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no','-o','ControlMaster=no',
        '-o','ControlPath=none','-o','ConnectTimeout=10','madar-node1-lan',shlex.join(args)]

def replica_namespace_scope(namespace,private_guard):
    """An isolated rehearsal replica must never become production evidence.

    Production callers always use the default and expose no namespace option.
    A private fixture's measured entrypoint must additionally attest isolation;
    the native host cannot select the private path even with a caller flag.
    """
    if namespace=='normal-local-production' and private_guard is None:return namespace
    if (namespace!='private-schema136-rehearsal' or not callable(private_guard)
            or private_guard()!={'fixture_only':True,'production_modified':False}):
        raise RuntimeError('normal_backup_private_replica_guard_required')
    result=subprocess.run(['/usr/bin/systemd-detect-virt','--container'],capture_output=True,text=True,timeout=5)
    if result.returncode or result.stdout.strip()!='docker':
        raise RuntimeError('normal_backup_private_replica_isolation_required')
    return namespace

def capture_and_replicate(plan,root,package,source_guard,kernel, *, recovery_context=None,authorizing_context=None,completed_context=None,
                          replica_namespace='normal-local-production',private_replica_guard=None):
    from scripts import backup_support
    source_guard()
    replica_namespace=replica_namespace_scope(replica_namespace,private_replica_guard)
    if completed_context is not None:
        if recovery_context is not None or authorizing_context is not None:
            raise RuntimeError('normal_backup_operation_context_conflict')
        completed_context.validate(plan,root,package)
        if completed_context.schema==160:
            verify_backup_execution_context(package,expected_schema=160,completed_context=completed_context)
    if authorizing_context is not None:
        import re
        if (recovery_context is not None or set(authorizing_context)!={'plan_sha256','source_bundle_sha256'}
                or any(not re.fullmatch('[0-9a-f]{64}',value) for value in authorizing_context.values())
                or Path(root)!=Path('/var/lib/madar-control-plane/normal-local-resumption')/authorizing_context['plan_sha256']
                or file_digest(protected(Path(package)/'source-bundle.json',private=True))!=authorizing_context['source_bundle_sha256']):
            raise RuntimeError('normal_backup_fresh_boot_binding_invalid')
        receipt=json.loads(protected(Path(root)/'authorization.json',private=True).read_text())
        document=json.loads(protected(Path(package)/'plan.json',private=True).read_text())
        if (receipt!={'operation':'repair-completed-normal-boot',**authorizing_context}
                or document.get('original_plan_sha256')!=plan.digest):
            raise RuntimeError('normal_backup_fresh_boot_authorization_required')
    if completed_context is not None:completed_context.guard()
    elif recovery_context is None:kernel.normal()
    else:recovery_context.guard()
    acceptance=completed_context.artifacts() if completed_context is not None else verify_artifact_acceptance(plan)
    replica=acceptance['node1_replica']
    if file_digest(readonly_configuration(NODE1_CONFIGURATION,private=True))!=replica['configuration_sha256']:
        raise RuntimeError('normal_backup_node1_configuration_changed')
    started=datetime.now(timezone.utc).isoformat()
    identity=pwd.getpwnam('madar')
    canonical=Path('/var/lib/madar/backups')
    scope_digest=plan.digest if authorizing_context is None else authorizing_context['plan_sha256']
    scope=canonical/(('normal-local-' if recovery_context is None else 'recovery-before-normal-')+scope_digest)
    if scope.exists() or scope.is_symlink():raise FileExistsError('normal_backup_scope_exists')
    if not scope.parent.is_dir() or scope.parent.is_symlink():raise RuntimeError('normal_backup_parent_missing')
    scope.mkdir(mode=0o700);os.chown(scope,identity.pw_uid,identity.pw_gid)
    cfg={};load_environment_file(readonly_configuration(INPUTS['backup_configuration'],private=True),environ=cfg)
    paths={};load_environment_file(protected(Path('/opt/madar/control-plane/deployment/production-paths.conf')),environ=paths,require_private=False)
    # Configuration data cannot select a shell/interpreter/loader or credentials.
    if any(key.startswith(('LD_','PYTHON','DOCKER_','GIT_')) or key in {'PATH','HOME','BASH_ENV','ENV','SHELL','CREDENTIALS_DIRECTORY',backup_support.LOCAL_DATABASE_FD} for key in cfg):
        raise RuntimeError('normal_backup_environment_invalid')
    env={**ENVIRONMENT,**cfg,**paths,'HOME':'/home/madar','CREDENTIALS_DIRECTORY':'/etc/madar',
        'MADAR_BACKUP_DIR':str(scope),'MADAR_BACKUP_FRESHNESS_MARKER':'','MADAR_BACKUP_STATE_DIR':'',
        'MADAR_BACKUP_KEEP_COUNT':'2','MADAR_PROVIDER_BACKUP_REQUIRED':'true',
        'PGOPTIONS':'-c default_transaction_read_only=on'}
    for name in ('backup_support.py','backup_madar.sh','verify_backup.sh'):
        actual=(Path('/usr/local/lib/madar') if recovery_context is None else recovery_context.helpers)/name
        expected=package/'source/web/scripts'/name
        if file_digest(protected(actual))!=file_digest(protected(expected,private=True)):
            raise RuntimeError('normal_backup_installed_helper_changed')
    maintenance_capture=None
    role=maintenance_role(completed_context.contract) if completed_context is not None else 'postgres'
    if role!='postgres' and cfg.get('PGUSER')!=role:
        raise RuntimeError('normal_backup_maintenance_configuration_changed')
    descriptor = backup_support.sealed_local_database_binding(**({'maintenance_role':role} if role!='postgres' else {}))
    try:
        address = json.loads(os.pread(descriptor,4096,0))['address']
        env[backup_support.LOCAL_DATABASE_FD] = str(descriptor)
        if completed_context is not None and getattr(completed_context,'provider_adapter',None) is not None:
            maintenance_capture=completed_context.capture_fenced(env,descriptor,identity)
        elif recovery_context is None:
            checked(['/usr/bin/python3','-I','-B','/usr/local/lib/madar/backup_support.py','scheduled',
                '/usr/local/lib/madar/backup_madar.sh'],env=env,user=identity.pw_uid,pass_fds=(descriptor,))
        else:
            recovery_context.capture(env,descriptor,identity)
    finally:
        os.close(descriptor)
    # A restart/address change during capture invalidates the lease and backup.
    if backup_support.direct_local_database_address() != address:
        raise RuntimeError('normal_backup_database_address_changed')

    if maintenance_capture is None:
        backups=list(scope.glob('madar-*'))
        if len(backups)!=1 or not backups[0].is_dir():raise RuntimeError('normal_backup_output_invalid')
        backup=backups[0]
    else:backup=Path(maintenance_capture['path'])
    from scripts import backup_support
    manifest=backup_support.verify(backup)
    expected_source=plan.source_sha if recovery_context is None else recovery_context.release_sha
    expected_schema=completed_context.schema if completed_context is not None else 115
    if int(manifest['database']['schema_version'])!=expected_schema or manifest['release']['git_sha']!=expected_source:
        raise RuntimeError('normal_backup_release_changed')
    row=json.loads(checked(['/usr/bin/docker','--host','unix:///var/run/docker.sock','image','inspect',
        kernel.runtime.inspect(['supabase-db'])['supabase-db']['Image']]))[0]
    digests=row.get('RepoDigests',[])
    if not digests:raise RuntimeError('normal_backup_restore_image_digest_missing')
    from scripts.rehearse_backup import rehearse
    # The exact independently restored checkpoint supplies only role NAMES
    # required by native policy definitions. NOLOGIN prerequisites do not
    # restore historical credentials, owners, memberships or authorization.
    maintenance_digest=(completed_context.maintenance_manifest(backup)
        if completed_context is not None and getattr(completed_context,'provider_adapter',None) is not None else None)
    if maintenance_capture is not None and maintenance_capture['manifest_sha256']!=maintenance_digest:
        raise RuntimeError('normal_backup_maintenance_capture_changed')
    if maintenance_digest is not None:
        role_names=()
    elif completed_context is not None:
        role_names=completed_context.role_names()
    else:
        from deployment.lib.active_recovery_execution import CHECKPOINT
        checkpoint_manifest=json.loads(protected(CHECKPOINT/'manifest.json',private=True).read_text())
        roles=protected(CHECKPOINT/'roles.sql',private=True)
        entries=[row for row in checkpoint_manifest['files'] if row['path']=='roles.sql']
        if len(entries)!=1 or file_digest(roles)!=entries[0]['sha256']:
            raise RuntimeError('normal_backup_restore_role_inventory_changed')
        role_names=tuple(sorted(set(re.findall(r'^CREATE ROLE ([a-zA-Z_][a-zA-Z0-9_]*);$',roles.read_text(),re.MULTILINE))))
    if maintenance_digest is None and not {'anon','authenticated','service_role'}.issubset(role_names):
        raise RuntimeError('normal_backup_restore_role_inventory_missing')
    restore=rehearse(backup,digests[0],postgres_preload=('pg_cron','pg_net'),additional_roles=role_names,
        **({'maintenance_manifest_sha256':maintenance_digest} if maintenance_digest is not None else {}))
    if restore.get('status')!='logical_database_and_file_restore_passed' or restore.get('backup_schema')!=expected_schema:
        raise RuntimeError('normal_backup_actual_restore_incomplete')
    if maintenance_digest is not None and (restore.get('maintenance_manifest_sha256')!=maintenance_digest
            or any(restore.get(k) is not True for k in ('role_attributes_restored','ownership_and_acls_restored',
                'database_fingerprint_verified','native_object_bytes_restored'))):
        raise RuntimeError('normal_backup_maintenance_restore_incomplete')
    sums=backup_support.digest(backup/'SHA256SUMS')
    # Stream only this verified scoped backup. A failed receiver is retained;
    # no second attempt silently overwrites it.
    with tempfile.TemporaryFile() as archive:
        with tarfile.open(fileobj=archive,mode='w') as tar:
            for child in sorted(backup.iterdir()):tar.add(child,arcname=child.name,recursive=True)
        archive.seek(0)
        replica_plan=plan if recovery_context is None else recovery_context.replica_plan
        if authorizing_context is not None:
            from types import SimpleNamespace
            replica_plan=SimpleNamespace(digest=scope_digest)
        output=checked(remote_receiver(package,replica_plan,backup,sums,replica['filesystem_uuid'],expected_schema=expected_schema,
            namespace=replica_namespace,maintenance_manifest_sha256=maintenance_digest),stdin=archive)
    remote=json.loads(output)
    if (remote.get('operation')!='actual-append-only-normal-backup-replica' or remote.get('plan_sha256')!=replica_plan.digest
            or remote.get('backup_id')!=backup.name or remote.get('sha256sums_sha256')!=sums
            or remote.get('schema')!=expected_schema or remote.get('namespace')!=replica_namespace
            or type(remote.get('checksum_exit_code')) is not int or remote['checksum_exit_code']!=0
            or remote.get('historical_backups_modified') is not False):
        raise RuntimeError('normal_backup_replica_verification_failed')
    if maintenance_digest is not None and remote.get('maintenance_manifest_sha256')!=maintenance_digest:
        raise RuntimeError('normal_backup_maintenance_replica_changed')
    if backup_support.digest(backup/'SHA256SUMS')!=sums:raise RuntimeError('normal_backup_changed_during_replication')
    backup_support.verify(backup);source_guard()
    if completed_context is not None:completed_context.guard()
    elif recovery_context is None:kernel.normal()
    else:recovery_context.close_and_guard()
    # Publish this same already-verified backup (no second dump/checkpoint) to
    # the configured ordinary root before restoring its backup timers. Existing
    # LATEST bytes are archived; directory publication refuses all collisions.
    if cfg.get('MADAR_BACKUP_DIR')!=str(canonical) or cfg.get('MADAR_BACKUP_FRESHNESS_MARKER')!=str(canonical/'LATEST'):
        raise RuntimeError('normal_backup_configured_root_changed')
    latest=canonical/'LATEST'
    exclusive(root/latest_preimage_name(completed_context),readonly_configuration(latest,private=False).read_bytes())
    final=canonical/backup.name
    if maintenance_digest is not None:
        from deployment.lib.maintenance_backup import release_ownership
        release_ownership(completed_context,backup,identity)
    libc=ctypes.CDLL(None,use_errno=True)
    rename=libc.renameat2;rename.argtypes=(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint)
    if rename(-100,os.fsencode(backup),-100,os.fsencode(final),1)!=0:
        raise OSError(ctypes.get_errno(),'normal_backup_collision_or_publication_failed')
    backup=final
    descriptor=os.open(canonical,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)
    backup_support.verify(backup)
    receipt_name=completed_context.receipt_name if completed_context is not None else ('post-boot-backup.json' if authorizing_context is not None else ('post-cutover-backup.json' if recovery_context is None else 'verified-recovery-backup.json'))
    receipt={'operation':('actual-post-normal-backup-restore-replica' if recovery_context is None else 'actual-pre-normal-current-data-backup-restore-replica'),
        'plan_sha256':scope_digest,
        'source_sha':plan.source_sha,'images':plan.candidate_images,'schema':expected_schema,
        'captured_release_sha':expected_source,
        'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
        'local_path':str(backup),'sha256sums_sha256':sums,'restore':restore,'node1':remote,
        'customer_database_restored':False,'migration_executed':False,'historical_backups_modified':False}
    if completed_context is not None:
        receipt.update(operation='actual-completed-normal-backup-restore-replica',context_sha256=completed_context.context,
            stage=completed_context.stage,authorizing_plan_sha256=completed_context.contract['plan_sha256'])
        if maintenance_digest is not None:receipt['maintenance_manifest_sha256']=maintenance_digest
    if authorizing_context is not None:
        receipt.update(runtime_plan_sha256=plan.digest,authorizing_context=authorizing_context)
    exclusive(root/receipt_name,encoded(receipt))
    # Publish freshness only after actual local restore and complete remote proof.
    backup_support.publish_marker(backup,canonical/'LATEST',Path('/var/lib/madar/backup-state'))
    os.chown(canonical/'LATEST',identity.pw_uid,identity.pw_gid)
    os.chown(Path('/var/lib/madar/backup-state/latest.json'),identity.pw_uid,identity.pw_gid)
    if recovery_context is not None:recovery_context.record_publication(backup,sums)
    return receipt

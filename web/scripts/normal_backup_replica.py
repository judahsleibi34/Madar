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

def verify_replica_payload(staging,backup_id,sums_sha,expected_schema,plan_sha,maintenance_manifest_sha256=None):
    """Shared format/integrity gate for production and independently enrolled tests."""
    if backup.digest(staging/'SHA256SUMS')!=sums_sha:raise RuntimeError('normal_replica_checksum_manifest_changed')
    manifest=backup.verify(staging,dump=False)
    if manifest.get('backup_id')!=backup_id or int(manifest.get('database',{}).get('schema_version',0))!=expected_schema:
        raise RuntimeError('normal_replica_backup_identity_changed')
    if maintenance_manifest_sha256 is not None:
        maintenance=(backup.verify_reconciled_maintenance(staging,expected_sha256=maintenance_manifest_sha256,
            schema=160,scope=plan_sha) if expected_schema==160 else
            backup.verify_maintenance(staging,expected_sha256=maintenance_manifest_sha256))
        if maintenance['schema']!=expected_schema or manifest.get('maintenance_backup')!='maintenance/manifest.json':
            raise RuntimeError('normal_replica_maintenance_binding_changed')
    elif manifest.get('maintenance_backup') is not None:
        raise RuntimeError('normal_replica_maintenance_expected_digest_required')
    return manifest


def extract_replica(staging,stream,max_bytes):
    count=0;size=0
    with tarfile.open(fileobj=stream,mode='r|') as archive:
        for member in archive:
            relative=PurePosixPath(member.name)
            if relative.is_absolute() or '..' in relative.parts or not (member.isfile() or member.isdir()):
                raise RuntimeError('normal_replica_archive_member_invalid')
            count+=1;size+=member.size
            if count>1000000 or member.size<0 or size>max_bytes:raise RuntimeError('normal_replica_capacity_exceeded')
            target=staging.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True,exist_ok=True,mode=0o700);continue
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            with target.open('xb') as output:
                os.fchmod(output.fileno(),0o600)
                shutil.copyfileobj(archive.extractfile(member),output,length=1024*1024)
                output.flush();os.fsync(output.fileno())
    return count,size


def receive(plan_sha,backup_id,sums_sha,filesystem_uuid,expected_schema=115,namespace='normal-local-production',maintenance_manifest_sha256=None):
    if (not re.fullmatch(r'[0-9a-f]{64}',plan_sha) or not backup.BACKUP_ID.fullmatch(backup_id)
            or not re.fullmatch(r'[0-9a-f]{64}',sums_sha) or not re.fullmatch(r'[0-9a-f-]{36}',filesystem_uuid)
            or type(expected_schema) is not int or expected_schema not in {115,136,144,146,148,150,160}
            or expected_schema in {150,160} and maintenance_manifest_sha256 is None
            or maintenance_manifest_sha256 is not None and not re.fullmatch('[0-9a-f]{64}',str(maintenance_manifest_sha256))
            or namespace not in {'normal-local-production','private-schema136-rehearsal'}):
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
    parent=BASE/namespace;parent.mkdir(mode=0o700,exist_ok=True)
    if parent.is_symlink() or parent.stat().st_uid!=os.getuid() or parent.stat().st_mode&0o077:
        raise RuntimeError('normal_replica_namespace_untrusted')
    scope=parent/plan_sha
    # A failed previous transfer and its partial input remain preserved. No
    # silent replacement, deletion, reauthorization or idempotent overwrite.
    scope.mkdir(mode=0o700)
    staging=scope/'incoming';staging.mkdir(mode=0o700)
    count,size=extract_replica(staging,sys.stdin.buffer,shutil.disk_usage(scope).free-10*1024**3)
    verify_replica_payload(staging,backup_id,sums_sha,expected_schema,plan_sha,maintenance_manifest_sha256)
    final=scope/backup_id;os.rename(staging,final)
    for path in final.rglob('*'):path.chmod(0o400 if path.is_file() else 0o500)
    final.chmod(0o500);scope.chmod(0o500)
    descriptor=os.open(scope,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)
    # backup.verify has independently checked the complete received inventory.
    result={'operation':'actual-append-only-normal-backup-replica','plan_sha256':plan_sha,
        'backup_id':backup_id,'destination':str(final),'sha256sums_sha256':sums_sha,
        'archive_entries':count,'files':sum(path.is_file() for path in final.rglob('*')),'bytes':size,'checksum_exit_code':0,'historical_backups_modified':False,
        'latest_modified':False,'retention_performed':False,'schema':expected_schema,'namespace':namespace}
    if maintenance_manifest_sha256 is not None:result['maintenance_manifest_sha256']=maintenance_manifest_sha256
    return result


def receive_enrolled_maintenance(run_id,packet,*,stream=None):
    """Same logical maintenance format, separate root-enrolled test namespace.

    Production BASE, mount contract and SSH policy stay unchanged. The parent
    signs only an independently pinned exact frozen operation. The receiver
    verifies bytes and canonical maintenance inputs; it does not execute SQL.
    """
    import base64,time
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from deployment.lib import isolated_backup_replica as transport
    from deployment.lib.provider_recovery_runtime import protected
    from deployment.lib.migration_inventory import canonical,digest,strict_json
    from deployment.lib.migration_executor import atomic_json
    from deployment.lib.control_plane_upgrade import require_root_directory
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    if os.geteuid()!=0 or not isinstance(run_id,str) or not re.fullmatch(transport.RUN,run_id):
        raise RuntimeError('isolated_replica_receiver_root_scope_required')
    root=Path('/opt/madar-recovery-tests')/run_id
    require_root_directory(root,create=False)
    if root.stat().st_mode&0o077:raise RuntimeError('isolated_replica_receiver_scope_not_private')
    enrollment=strict_json(protected(root/'maintenance-enrollment.json',private=True).read_bytes())
    fields={'version','kind','policy','policy_sha256','machine_id','context_sha256','plan_sha256','stage_scopes'}
    if (not isinstance(enrollment,dict) or set(enrollment)!=fields or type(enrollment['version']) is not int or enrollment['version']!=1
            or enrollment['kind']!='independently-enrolled-maintenance-replica'
            or not re.fullmatch('[a-f0-9]{32}',str(enrollment['machine_id']))
            or any(not re.fullmatch('[a-f0-9]{64}',str(enrollment[k])) for k in ('policy_sha256','context_sha256','plan_sha256'))
            or not isinstance(enrollment['stage_scopes'],dict) or set(enrollment['stage_scopes'])!={'pre-migration','post-migration'}
            or any(not re.fullmatch('[a-f0-9]{64}',str(v)) for v in enrollment['stage_scopes'].values())):
        raise RuntimeError('isolated_replica_receiver_enrollment_invalid')
    p=transport.validate_policy(enrollment['policy'],now=int(time.time()))
    if (p['receiver_run_id']!=run_id or Path('/etc/machine-id').read_text().strip()!=enrollment['machine_id']
            or Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower()!=p['receiver_physical_host_uuid']
            or subprocess.run(['systemd-detect-virt'],capture_output=True,text=True,timeout=10).stdout.strip()!='none'
            or subprocess.check_output(['findmnt','-n','-o','FSTYPE,UUID','-T',str(root)],text=True,timeout=10).split()!=['ext4',p['receiver_filesystem_uuid']]):
        raise RuntimeError('isolated_replica_receiver_physical_identity_changed')
    q=transport.verify_signature(packet,p['source_public_key'])
    stage=q.get('stage') if isinstance(q,dict) else None
    if stage not in enrollment['stage_scopes']:raise RuntimeError('isolated_replica_receiver_stage_invalid')
    expected={k:enrollment[k] for k in ('policy_sha256','context_sha256','plan_sha256')}
    expected.update(stage=stage,scope_sha256=enrollment['stage_scopes'][stage],schema={'pre-migration':146,'post-migration':160}[stage])
    transport.validate_request(q,p,expected,now=int(time.time()))
    if shutil.disk_usage(root).free<q['archive_bytes']*3+5*1024**3:
        raise RuntimeError('isolated_replica_receiver_headroom')
    key=Ed25519PrivateKey.from_private_bytes(protected(root/'receiver.key',private=True).read_bytes())
    if base64.b64encode(key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()!=p['receiver_public_key']:
        raise RuntimeError('isolated_replica_receiver_key_changed')
    atomic_json(root/'maintenance-attempts'/(q['nonce']+'.json'),{'request_sha256':digest(q),'consumed_at':int(time.time())},exclusive=True)
    parent=root/'maintenance-replicas';require_root_directory(parent,create=True)
    if parent.stat().st_mode&0o077:raise RuntimeError('isolated_replica_receiver_scope_not_private')
    scope=parent/q['scope_sha256'];scope.mkdir(mode=0o700)
    staging=scope/'incoming';staging.mkdir(mode=0o700)
    stream=sys.stdin.buffer if stream is None else stream
    with tempfile.TemporaryFile(dir=scope) as archive:
        checksum=hashlib.sha256();remaining=q['archive_bytes']
        while remaining:
            chunk=stream.read(min(1024**2,remaining))
            if not chunk:raise RuntimeError('isolated_replica_archive_truncated')
            archive.write(chunk);checksum.update(chunk);remaining-=len(chunk)
        if stream.read(1) or checksum.hexdigest()!=q['archive_sha256']:
            raise RuntimeError('isolated_replica_archive_bytes_changed')
        archive.seek(0);count,size=extract_replica(staging,archive,p['max_archive_bytes'])
    manifest=verify_replica_payload(staging,q['backup_id'],q['sha256sums_sha256'],q['schema'],q['scope_sha256'],q['maintenance_manifest_sha256'])
    maintenance=backup.verify_reconciled_maintenance(staging,expected_sha256=q['maintenance_manifest_sha256'],schema=q['schema'],scope=q['scope_sha256'])
    binding=maintenance['binding']
    if (binding['context_sha256']!=q['context_sha256'] or binding['system_identifier']!=p['database_system_identifier']
            or binding['source_sha']!=p['candidate_application_sha'] or binding['controller_sha']!=p['controller_sha']
            or maintenance['recovery']['controller_tree_sha256']!=p['controller_tree_sha256']
            or manifest['release']['git_sha']!=p['candidate_application_sha']):
        raise RuntimeError('isolated_replica_received_operation_changed')
    transport.validate_request(q,p,expected,now=int(time.time()))
    final=scope/q['backup_id'];os.rename(staging,final)
    for path in final.rglob('*'):path.chmod(0o400 if path.is_file() else 0o500)
    final.chmod(0o500);scope.chmod(0o500)
    descriptor=os.open(scope,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)
    result={'operation':'actual-append-only-normal-backup-replica','plan_sha256':q['scope_sha256'],
        'backup_id':q['backup_id'],'destination':str(final),'sha256sums_sha256':q['sha256sums_sha256'],
        'archive_entries':count,'files':sum(path.is_file() for path in final.rglob('*')),'bytes':size,
        'checksum_exit_code':0,'historical_backups_modified':False,'latest_modified':False,'retention_performed':False,
        'schema':q['schema'],'namespace':transport.NAMESPACE,'maintenance_manifest_sha256':q['maintenance_manifest_sha256']}
    value={'version':1,'kind':'independently-received-maintenance-replica','request_sha256':digest(q),
        'receiver_id':p['receiver_id'],'physical_host_uuid':p['receiver_physical_host_uuid'],'filesystem_uuid':p['receiver_filesystem_uuid'],
        'received_at':int(time.time()),'replica':result,'database_restored':False,'application_restored':False,
        'deployment_authority_issued':False,'migration_sql_executed':False}
    receipt={'payload':value,'signature':base64.b64encode(key.sign(canonical(value))).decode()}
    atomic_json(root/'maintenance-attempts'/(q['nonce']+'.received.json'),receipt,exclusive=True)
    return receipt

def receive_enrolled_test(run_id, packet, *, stream=None):
    """Existing append-only receiver, separately enrolled physical-host tests.

    No production BASE, mount contract or schema allowlist changes. Enrollment
    is root-private on the actual receiver, not an untrusted source PASS packet.
    Physical PostgreSQL backups preserve the source system identifier; host and
    runtime identity, not a rewritten database ID, establish independence.
    """
    import base64,time,uuid
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from deployment.lib.provider_recovery_runtime import protected
    from deployment.lib.migration_inventory import canonical,digest,strict_json
    from deployment.lib.migration_executor import atomic_json
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if (os.geteuid()!=0 or not isinstance(run_id,str)
            or not re.fullmatch(r'codex-[0-9]{8}T[0-9]{6}Z-automatic-execution-[a-f0-9]{8}',run_id)):
        raise RuntimeError('test_receiver_owned_root_scope_required')
    root=Path('/opt/madar-recovery-tests')/run_id
    enrollment=strict_json(protected(root/'enrollment.json',private=True).read_bytes())
    fields={'version','kind','run_id','receiver_id','machine_id','product_uuid','filesystem_uuid',
        'source_guest_uuid','source_product_uuid','source_database_system_identifier','denied_database_identifiers',
        'source_sha','backup_operation_id','manifest_sha256','source_public_key','expires_at','max_transfer_bytes'}
    bootstrap=isinstance(enrollment,dict) and enrollment.get('version')==2 and type(enrollment.get('version')) is int
    if bootstrap:fields|={'source_origin_kind','source_origin_sha256'}
    now=int(time.time())
    if (not isinstance(enrollment,dict) or set(enrollment)!=fields or type(enrollment['version']) is not int or enrollment['version'] not in {1,2}
            or enrollment['kind']!='independent-physical-test-receiver' or enrollment['run_id']!=run_id
            or type(enrollment['expires_at']) is not int or not now<enrollment['expires_at']<=now+14400
            or type(enrollment['max_transfer_bytes']) is not int or not 0<enrollment['max_transfer_bytes']<=2*1024**3
            or enrollment['source_database_system_identifier'] in enrollment['denied_database_identifiers']
            or not enrollment['denied_database_identifiers']
            or not re.fullmatch('[1-9][0-9]{0,19}',str(enrollment['source_database_system_identifier']))
            or not re.fullmatch('[a-f0-9]{40}',str(enrollment['source_sha']))
            or not re.fullmatch('[a-f0-9]{64}',str(enrollment['manifest_sha256']))):
        raise RuntimeError('test_receiver_enrollment_invalid')
    if bootstrap and (enrollment['source_origin_kind']!='independently-enrolled-historical-bootstrap-origin'
            or not re.fullmatch('[a-f0-9]{64}',str(enrollment['source_origin_sha256']))):
        raise RuntimeError('test_receiver_historical_origin_invalid')
    for key in ('receiver_id','source_guest_uuid','product_uuid','source_product_uuid','filesystem_uuid','backup_operation_id'):
        if str(uuid.UUID(enrollment[key]))!=enrollment[key]:raise RuntimeError('test_receiver_identity_invalid')
    if (Path('/etc/machine-id').read_text().strip()!=enrollment['machine_id']
            or Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower()!=enrollment['product_uuid']
            or enrollment['product_uuid'] in {enrollment['source_guest_uuid'],enrollment['source_product_uuid']}
            or subprocess.run(['systemd-detect-virt'],capture_output=True,text=True,timeout=10).stdout.strip()!='none'):
        raise RuntimeError('test_receiver_physical_host_changed')
    fs=subprocess.check_output(['findmnt','-n','-o','FSTYPE,UUID','-T',str(root)],text=True,timeout=10).split()
    if fs!=['ext4',enrollment['filesystem_uuid']]:raise RuntimeError('test_receiver_filesystem_changed')
    if not isinstance(packet,dict) or set(packet)!={'payload','signature'}:raise RuntimeError('test_receiver_packet_invalid')
    value=packet['payload']
    try:Ed25519PublicKey.from_public_bytes(base64.b64decode(enrollment['source_public_key'],validate=True)).verify(base64.b64decode(packet['signature'],validate=True),canonical(value))
    except Exception:raise RuntimeError('test_receiver_source_signature_invalid') from None
    if bootstrap and (value.get('source_origin_kind')!=enrollment['source_origin_kind']
            or value.get('source_origin_sha256')!=enrollment['source_origin_sha256']):
        raise RuntimeError('test_receiver_historical_origin_changed')
    if (digest(value)!=enrollment['manifest_sha256']
            or value.get('operation')!='independent-synthetic-application-restoration'
            or value.get('operation_id')!=enrollment['backup_operation_id']
            or value.get('receiver_id')!=enrollment['receiver_id']
            or value.get('source_sha')!=enrollment['source_sha']
            or value.get('source_guest_uuid')!=enrollment['source_guest_uuid']
            or value.get('source_database_system_identifier')!=enrollment['source_database_system_identifier']
            or value.get('backup_format')!='postgres-physical-and-application-v1'
            or type(value.get('expires_at')) is not int or not now<value['expires_at']<=enrollment['expires_at']):
        raise RuntimeError('test_receiver_operation_binding_invalid')
    expected=value.get('files')
    if (not isinstance(expected,dict) or set(expected)!={'postgres.tar.gz','objects.tar.gz','application.json'}
            or any(set(row)!={'size','sha256'} or type(row['size']) is not int or row['size']<=0
                or not re.fullmatch('[a-f0-9]{64}',str(row['sha256'])) for row in expected.values())
            or expected['application.json']['size']>32*1024**2
            or sum(row['size'] for row in expected.values())>enrollment['max_transfer_bytes']
            or shutil.disk_usage(root).free<sum(row['size'] for row in expected.values())*3+5*1024**3):
        raise RuntimeError('test_receiver_backup_inventory_or_headroom_invalid')
    # Link-based exclusive publication in the existing journal implementation
    # consumes a failed transfer as well. No overwrite or silent retry.
    atomic_json(root/'receive-consumed.json',{'operation_id':value['operation_id'],'manifest_sha256':digest(value),'consumed_at':now},exclusive=True)
    incoming=root/'incoming';incoming.mkdir(mode=0o700)
    from scripts.restore_node1_checkpoint import receive as receive_exact
    transported=receive_exact(stream if stream is not None else sys.stdin.buffer,incoming,expected)
    receipt={'operation':'independent-test-backup-received','receiver_id':enrollment['receiver_id'],
        'operation_id':value['operation_id'],'manifest_sha256':digest(value),'source_sha':value['source_sha'],
        'source_database_system_identifier':value['source_database_system_identifier'],
        'physical_host_uuid':enrollment['product_uuid'],'files':transported,'received_at':int(time.time()),
        'database_restored':False,'application_restored':False,'production_modified':False}
    atomic_json(root/'received.json',receipt,exclusive=True)
    return receipt


if __name__=='__main__':
    try:
        args=sys.argv[1:]
        if len(args)==3 and args[0] in {'--enrolled-test','--enrolled-maintenance'}:
            import base64
            packet=json.loads(base64.b64decode(args[2],validate=True))
            operation=receive_enrolled_test if args[0]=='--enrolled-test' else receive_enrolled_maintenance
            print(json.dumps(operation(args[1],packet),sort_keys=True))
        else:
            if len(args)>4:args[4]=int(args[4])
            print(json.dumps(receive(*args),sort_keys=True))
    except Exception as error:
        print(json.dumps({'operation':'normal-backup-replica','status':'failed','exception_type':type(error).__name__}),flush=True)
        raise SystemExit(1)

"""Validate exact-snapshot restore applicability; PASS summaries are insufficient.

This validator does not issue evidence or restore data. A separately authorized
supervisor must retain its actual execution and independently approved digest.
Historical summaries remain valid only for their explicitly verified snapshot.
Binding checks are not proof of execution provenance. The caller must first
verify the trusted supervisor and independently retained actual execution; this
module must never turn an agent-authored packet into independent evidence.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

HEX = re.compile(r'[0-9a-f]{64}')

SEALED_COMPONENTS = {
    'database.dump':'database','roles.sql':'roles','native-storage.tar.gz':'storage',
    'function-cache.tar.gz':'native_config','native-configuration.tar.gz':'native_config',
    'managed-storage.tar.gz':'application_storage','production-configuration.tar.gz':'production_config',
    'controller-state.tar.gz':'controller','images.json':'images','auth-metadata.json':'auth_metadata',
    'schema.json':'schema','ledgers.json':'ledgers','capture-bindings.json':'controller',
}


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require_hash(value):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise RuntimeError('checkpoint_execution_digest_invalid')
    return value


def safe_relative(value):
    if not isinstance(value, str):
        raise RuntimeError('checkpoint_execution_path_invalid')
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or path.as_posix() == '.':
        raise RuntimeError('checkpoint_execution_path_invalid')
    return path


def verify_checkpoint_execution(checkpoint: Path, proof: Path, *, approved_execution_digest: str,
                                protected_file, now: datetime) -> dict:
    """Root-protected execution packet, approved independently of its PASS labels.

    Explicitly require complete coordinated scope, retained successful execution,
    full inventory binding, and an independently restored off-host copy. This
    cannot authorize a supplemented manifest using an older dump-only report.
    """
    require_hash(approved_execution_digest)
    proof = protected_file(proof, private=True)
    if sha256(proof) != approved_execution_digest:
        raise RuntimeError('checkpoint_execution_not_independently_approved')
    record = json.loads(proof.read_text())
    manifest_path = protected_file(checkpoint / 'manifest.json', private=True)
    manifest = json.loads(manifest_path.read_text())
    if (type(manifest.get('version')) is not int or manifest['version'] != 1
            or manifest.get('schema') != 115 or manifest.get('sealed') is not True
            or manifest.get('migrations_executed') is not False
            or {entry.get('path'):entry.get('kind') for entry in manifest.get('files',[])} != SEALED_COMPONENTS
            or len(manifest.get('files',[])) != len(SEALED_COMPONENTS)):
        raise RuntimeError('checkpoint_execution_complete_manifest_required')
    if (type(record.get('version')) is not int or record.get('version') != 1 or record.get('operation') != 'coordinated-checkpoint-restore'
            or record.get('checkpoint_manifest_sha256') != sha256(manifest_path)
            or record.get('schema') != 115 or record.get('migrations_executed') is not False
            or record.get('production_modified') is not False
            or record.get('scope') != 'complete-coordinated-checkpoint'
            or record.get('workers_started') is not False):
        raise RuntimeError('checkpoint_execution_scope_or_snapshot_invalid')
    inventory = {}
    for entry in manifest.get('files', []):
        relative = Path(entry['path'])
        if (relative.is_absolute() or '..' in relative.parts or relative.as_posix() in inventory
                or relative.as_posix() in {'.', 'manifest.json'}):
            raise RuntimeError('checkpoint_execution_path_invalid')
        file = protected_file(checkpoint / relative, private=True)
        actual = sha256(file)
        if type(entry.get('size')) is not int or file.stat().st_size != entry['size'] or actual != entry['sha256']:
            raise RuntimeError('checkpoint_execution_inventory_changed')
        inventory[relative.as_posix()] = actual
    if not inventory or record.get('restored_files') != inventory:
        raise RuntimeError('checkpoint_execution_incomplete_restore')
    execution = record.get('execution', {})
    started, finished = datetime.fromisoformat(execution['started_at']), datetime.fromisoformat(execution['finished_at'])
    created = datetime.fromisoformat(manifest['created_at'])
    if (any(value.tzinfo is None for value in (started, finished, created, now))
            or not created <= started <= finished <= now
            or type(execution.get('exit_code')) is not int or execution['exit_code'] != 0
            or not execution.get('argv') or not isinstance(execution['argv'], list)
            or not all(isinstance(arg, str) for arg in execution['argv'])
            or execution.get('network') != 'none'
            or execution.get('customer_endpoints_used') is not False):
        raise RuntimeError('checkpoint_execution_not_completed_safely')
    for key in ('runner_sha256', 'transcript_sha256'):
        require_hash(execution.get(key))
    runner = protected_file(proof.parent / safe_relative(execution.get('runner_path')), private=True)
    if sha256(runner) != execution['runner_sha256']:
        raise RuntimeError('checkpoint_execution_runner_changed')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', str(execution.get('image_id'))):
        raise RuntimeError('checkpoint_execution_image_unbound')
    relative = Path(execution['transcript_path'])
    if relative.is_absolute() or '..' in relative.parts or relative.as_posix() == '.':
        raise RuntimeError('checkpoint_execution_transcript_path_invalid')
    transcript = protected_file(proof.parent / relative, private=True)
    if not transcript.stat().st_size or sha256(transcript) != execution['transcript_sha256']:
        raise RuntimeError('checkpoint_execution_transcript_changed')
    offhost = record.get('offhost', {})
    if (offhost.get('checkpoint_manifest_sha256') != sha256(manifest_path)
            or offhost.get('restored_files') != inventory
            or offhost.get('independent_restore_exit_code') != 0
            or type(offhost.get('independent_restore_exit_code')) is not int
            or offhost.get('independent_restore_verified') is not True
            or offhost.get('source_host_id') == offhost.get('backup_host_id')
            or not all(isinstance(offhost.get(key), str) and offhost[key]
                       for key in ('source_host_id', 'backup_host_id', 'object_id'))):
        raise RuntimeError('checkpoint_offhost_restore_unverified')
    if offhost.get('protection') not in {'online-ssh-unencrypted', 'age-encrypted'}:
        raise RuntimeError('checkpoint_offhost_protection_unbound')
    require_hash(offhost.get('object_sha256'))
    require_hash(offhost.get('execution_receipt_sha256'))
    offhost_receipt = protected_file(proof.parent / safe_relative(offhost.get('execution_receipt_path')), private=True)
    if sha256(offhost_receipt) != offhost['execution_receipt_sha256']:
        raise RuntimeError('checkpoint_offhost_execution_changed')
    measured = json.loads(offhost_receipt.read_text())
    expected = {key: value for key, value in offhost.items() if key not in {'execution_receipt_path', 'execution_receipt_sha256'}}
    if measured != expected:
        raise RuntimeError('checkpoint_offhost_measurement_changed')
    return {'checkpoint_manifest_sha256': sha256(manifest_path),
            'approved_execution_digest': approved_execution_digest, 'files': len(inventory)}


def coordinated_health_marker(checkpoint: Path, proof: Path, *, approved_execution_digest,
                              protected_file, now):
    """Build health data ONLY after complete exact approved restore validation.

    This function publishes nothing and grants no authorization. The caller must
    independently verify execution provenance, preserve any prior health marker,
    and publish through the approved governed operation. No old PASS flag is used.
    """
    operation=json.loads(protected_file(proof,private=True).read_text()).get('operation')
    if operation=='supervised-private-native-core-restore':
        verified=verify_supervised_native_restore(checkpoint,proof,approved_execution_digest=approved_execution_digest,
            protected_file=protected_file,now=now)
        result={'checkpoint_manifest_sha256':verified['checkpoint_manifest_sha256'],'approved_execution_digest':verified['execution_sha256']}
    else:
        result=verify_checkpoint_execution(checkpoint,proof,approved_execution_digest=approved_execution_digest,
            protected_file=protected_file,now=now)
    if not re.fullmatch(r'checkpoint-[0-9]{8}T[0-9]{6}Z',checkpoint.name):
        raise RuntimeError('checkpoint_health_identity_invalid')
    manifest=json.loads(protected_file(checkpoint/'manifest.json',private=True).read_text())
    return {'format':2,'scope':'complete-coordinated-checkpoint','schema':115,
        'checkpoint_id':checkpoint.name,'created_at':manifest['created_at'],'verified':True,
        'manifest_sha256':result['checkpoint_manifest_sha256'],
        'execution_sha256':result['approved_execution_digest']}



def verify_supervised_native_restore(checkpoint: Path, receipt: Path, *, approved_execution_digest,
                                     protected_file, now):
    """Consume actual root-retained data/core recovery without scope relabelling.

    The executing supervisor's approved hash and root-protected source/transcript
    remain the provenance boundary. This returns no normal application, tenant,
    full eleven-service or bare-host disaster-recovery acceptance claim.
    """
    require_hash(approved_execution_digest)
    receipt=protected_file(receipt,private=True)
    if sha256(receipt)!=approved_execution_digest:raise RuntimeError('native_execution_not_approved')
    record=json.loads(receipt.read_text())
    if (record.get('operation')!='supervised-private-native-core-restore' or record.get('scope')!='native-core'
            or type(record.get('version')) is not int or record['version']!=1
            or type(record.get('exit_code')) is not int or record['exit_code']!=0
            or record.get('original_evidence_modified') is not False or record.get('source_application_acceptance_claimed') is not False):
        raise RuntimeError('native_execution_scope_invalid')
    manifest_path=protected_file(checkpoint/'manifest.json',private=True)
    manifest=json.loads(manifest_path.read_text())
    if (record.get('checkpoint_manifest_sha256')!=sha256(manifest_path) or type(manifest.get('version')) is not int
            or manifest['version']!=1 or manifest.get('schema')!=115 or manifest.get('sealed') is not True
            or manifest.get('migrations_executed') is not False
            or len(manifest.get('files',[]))!=len(SEALED_COMPONENTS)
            or {row.get('path'):row.get('kind') for row in manifest['files']}!=SEALED_COMPONENTS):
        raise RuntimeError('native_execution_snapshot_invalid')
    inventory={}
    for row in manifest['files']:
        file=protected_file(checkpoint/safe_relative(row['path']),private=True)
        if sha256(file)!=row['sha256'] or type(row['size']) is not int or file.stat().st_size!=row['size']:
            raise RuntimeError('native_execution_inventory_changed')
        inventory[row['path']]=row['sha256']
    paths={'source_files':'source-files.json','stdout':'stdout.jsonl','stderr':'stderr.txt',
        'replica_check':'replica-check.json','archive_verification':'archive-verification.json'}
    contents={}
    for key,name in paths.items():
        file=protected_file(receipt.parent/name,private=True)
        if sha256(file)!=require_hash(record.get(key+'_sha256')):raise RuntimeError('native_execution_retained_record_changed')
        contents[key]=file.read_text()
    if contents['stderr']:raise RuntimeError('native_execution_stderr_present')
    argv=record.get('argv',[])
    if (not isinstance(argv,list) or len(argv)!=4 or argv[:3]!=['/usr/bin/python3','-I','-B']
            or not isinstance(argv[3],str) or Path(argv[3]).name!='verify_restored_native_platform.py'):
        raise RuntimeError('native_execution_runner_invalid')
    web=Path(argv[3]).parents[1]
    sources=json.loads(contents['source_files'])
    if not isinstance(sources,dict) or not {'scripts/record_native_restore_execution.py','scripts/verify_restored_native_platform.py','scripts/restore_coordinated_checkpoint.py'}.issubset(sources):
        raise RuntimeError('native_execution_source_inventory_invalid')
    for relative,expected in sources.items():
        source=protected_file(web/safe_relative(relative),private=True)
        if source.stat().st_mode&0o200 or sha256(source)!=require_hash(expected):raise RuntimeError('native_execution_source_changed')
    started,finished,created=(datetime.fromisoformat(value) for value in (record['started_at'],record['finished_at'],manifest['created_at']))
    if any(value.tzinfo is None for value in (started,finished,created,now)) or not created<=started<=finished<=now:
        raise RuntimeError('native_execution_time_invalid')
    replica=json.loads(contents['replica_check'])
    if (replica.get('node')!='madar-node1-lan' or type(replica.get('exit_code')) is not int or replica['exit_code']!=0
            or replica.get('successful_files')!=14 or replica.get('files')!={**inventory,'manifest.json':sha256(manifest_path)}
            or replica.get('object_id')!='/srv/data2/madar-backups/normal-local-preparation/'+checkpoint.name):
        raise RuntimeError('native_execution_replica_invalid')
    archives=json.loads(contents['archive_verification'])
    if set(archives)!={name for name in inventory if name.endswith('.tar.gz')} or any(
            type(row.get('files')) is not int or row['files']<=0 or type(row.get('bytes')) is not int or row['bytes']<=0 for row in archives.values()):
        raise RuntimeError('native_execution_archive_inventory_invalid')
    transcript=[json.loads(line) for line in contents['stdout'].splitlines()]
    if not transcript:raise RuntimeError('native_execution_transcript_empty')
    result=transcript[-1]
    if (result.get('operation')!='actual-offhost-private-native-core-restore' or result.get('checkpoint_manifest_sha256')!=sha256(manifest_path)
            or result.get('restored_files')!=inventory or result.get('schema')!=115
            or result.get('database_network_during_restore')!='none' or result.get('runtime_network')!='isolated-internal'
            or result.get('production_modified') is not False or result.get('original_checkpoint_modified') is not False
            or result.get('application_migrations_executed') is not False or result.get('business_consumers_started') is not False
            or result.get('application_acceptance_proven') is not False or result.get('tenant_isolation_proven') is not False
            or result.get('full_eleven_service_platform_proven') is not False):
        raise RuntimeError('native_execution_result_scope_invalid')
    for key in ('owners_and_acls_restored','role_attributes_password_verifiers_and_grantors_verified',
                'mime_cache_verified','native_login_and_aal2_verified','synthetic_identity_removed'):
        if result.get(key) is not True:raise RuntimeError('native_execution_integrity_failed')
    if (result.get('database_integrity')!={'database_owner':'postgres','invalid_indexes':'0','identities':'18','factors':'2'}
            or type(result.get('storage_objects')) is not int or result['storage_objects']!=235 or result.get('range_checks')!=235):
        raise RuntimeError('native_execution_dataset_invalid')
    runtimes=result.get('runtimes',{})
    if len(runtimes)!=4 or any(not HEX.fullmatch(str(row.get('id'))) or not re.fullmatch(r'sha256:[0-9a-f]{64}',str(row.get('image'))) for row in runtimes.values()):
        raise RuntimeError('native_execution_runtime_identities_invalid')
    images=json.loads(protected_file(checkpoint/'images.json',private=True).read_text())
    roles={'db':'supabase-db','auth':'supabase-auth','rest':'supabase-rest','storage':'supabase-storage'}
    selected={}
    for name,row in runtimes.items():
        role=name.rsplit('-',1)[-1]
        if role not in roles or role in selected or row['image']!=images[roles[role]]['image']:
            raise RuntimeError('native_execution_runtime_images_changed')
        selected[role]=row['id']
    if len(set(selected.values()))!=4:raise RuntimeError('native_execution_runtime_identities_invalid')
    if any(row.get('event')=='native_restore_cleanup_failed' for row in transcript):
        raise RuntimeError('native_execution_cleanup_failed')
    return {'checkpoint_manifest_sha256':sha256(manifest_path),'execution_sha256':approved_execution_digest,
        'coordinated_components_verified':len(inventory),'replica_files_verified':14,'native_core_verified':True,
        'normal_application_acceptance':False,'full_eleven_service_platform_acceptance':False}

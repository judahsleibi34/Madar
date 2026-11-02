"""Authenticated transport for the EXISTING maintenance backup receiver.

The parent retains Node1 SSH credentials. The isolated guest keeps its exact
effect fence. This adapter changes no archive format, restore checks, migration
authority or production backup namespace. Receipt of bytes is not restoration.
"""
import base64,hashlib,os,re,shutil,time,uuid
from pathlib import Path
from .migration_inventory import canonical,digest,strict_json
from .migration_executor import atomic_json
from .provider_recovery_runtime import protected

POLICY=Path('/etc/madar/node1-backup.env')
ROOT=Path('/var/lib/madar-control-plane/maintenance-replica-transfers')
NAMESPACE='isolated-historical-maintenance-rehearsal'
RUN=r'codex-[0-9]{8}T[0-9]{6}Z-automatic-execution-[a-f0-9]{8}'
SCOPE=('environment_id','guest_uuid','machine_id','root_filesystem_uuid','database_system_identifier',
       'controller_sha','controller_tree_sha256','historical_origin','source_origin_sha256',
       'source_physical_host_uuid','receiver_physical_host_uuid','receiver_filesystem_uuid',
       'receiver_run_id','receiver_id','candidate_application_sha')


def validate_policy(p,*,now):
    fields={'version','kind',*SCOPE,'source_public_key','receiver_public_key','expires_at',
        'max_archive_bytes','denied_database_identifiers'}
    if (not isinstance(p,dict) or set(p)!=fields or type(p['version']) is not int or p['version']!=1
            or p['kind']!='isolated-enrolled-maintenance-replica'
            or type(p['expires_at']) is not int or not now<p['expires_at']<=now+14400
            or type(p['max_archive_bytes']) is not int or not 0<p['max_archive_bytes']<=1024**3
            or not re.fullmatch(RUN,str(p['receiver_run_id']))
            or not re.fullmatch('[a-f0-9]{32}',str(p['machine_id']))
            or not re.fullmatch('[1-9][0-9]{0,19}',str(p['database_system_identifier']))
            or not isinstance(p['denied_database_identifiers'],list) or not 1<=len(p['denied_database_identifiers'])<=64
            or any(not re.fullmatch('[1-9][0-9]{0,19}',str(v)) for v in p['denied_database_identifiers'])
            or p['database_system_identifier'] in p['denied_database_identifiers']
            or any(not re.fullmatch('[a-f0-9]{40}',str(p[k])) for k in ('controller_sha','candidate_application_sha'))
            or any(not re.fullmatch('[a-f0-9]{64}',str(p[k])) for k in ('controller_tree_sha256','source_origin_sha256'))
            or p['receiver_physical_host_uuid'] in {p['source_physical_host_uuid'],p['guest_uuid']}):
        raise RuntimeError('isolated_replica_policy_invalid')
    from .historical_origin import validate_source_binding
    validate_source_binding(p['historical_origin'])
    if p['historical_origin']['controller_sha']!=p['controller_sha']:
        raise RuntimeError('isolated_replica_historical_controller_changed')
    try:
        for key in ('guest_uuid','root_filesystem_uuid','source_physical_host_uuid','receiver_physical_host_uuid','receiver_filesystem_uuid','receiver_id'):
            if str(uuid.UUID(p[key]))!=p[key]:raise ValueError()
        if p['environment_id']!='isolated-'+str(uuid.UUID(p['environment_id'].removeprefix('isolated-'))):raise ValueError()
        for key in ('source_public_key','receiver_public_key'):
            if len(base64.b64decode(p[key],validate=True))!=32:raise ValueError()
    except (ValueError,TypeError,AttributeError):raise RuntimeError('isolated_replica_policy_identity_invalid') from None
    return p


def request_context(context):
    return {'context_sha256':context.context,'plan_sha256':context.contract['plan_sha256'],
        'stage':context.stage,'scope_sha256':context.scope,'schema':context.schema}


def validate_request(q,p,expected,*,now):
    fields={'version','kind','nonce','policy_sha256','created_at','expires_at','backup_id',
        'sha256sums_sha256','maintenance_manifest_sha256','archive_sha256','archive_bytes',
        'context_sha256','plan_sha256','stage','scope_sha256','schema'}
    from scripts.backup_support import BACKUP_ID
    if (not isinstance(q,dict) or set(q)!=fields or type(q['version']) is not int or q['version']!=1
            or q['kind']!='isolated-maintenance-replica-transfer'
            or any(q[k]!=expected[k] for k in ('context_sha256','plan_sha256','stage','scope_sha256','schema','policy_sha256'))
            or q['stage'] not in {'pre-migration','post-migration'} or type(q['schema']) is not int
            or q['schema']!={'pre-migration':146,'post-migration':160}[q['stage']]
            or type(q['created_at']) is not int or type(q['expires_at']) is not int
            or not q['created_at']<=now<q['expires_at']<=min(q['created_at']+300,p['expires_at'])
            or type(q['archive_bytes']) is not int or not 0<q['archive_bytes']<=p['max_archive_bytes']
            or not isinstance(q['backup_id'],str) or not BACKUP_ID.fullmatch(q['backup_id'])
            or any(not re.fullmatch('[a-f0-9]{64}',str(q[k])) for k in
                ('policy_sha256','context_sha256','plan_sha256','scope_sha256','sha256sums_sha256','maintenance_manifest_sha256','archive_sha256'))):
        raise RuntimeError('isolated_replica_request_scope_or_freshness')
    try:
        if str(uuid.UUID(q['nonce']))!=q['nonce']:raise ValueError()
    except (ValueError,TypeError,AttributeError):raise RuntimeError('isolated_replica_request_nonce_invalid') from None
    return q


def policy(context):
    """Root policy + authentic enrolled historical source; never caller PASS."""
    if os.geteuid()!=0:raise RuntimeError('isolated_replica_root_required')
    from .completed_normal_admission import validate_provider_preparation
    from .completed_normal_backup import CompletedNormalBackupContext
    from .completed_normal_profile import RECONCILED
    from .historical_origin import KIND
    if (type(context) is not CompletedNormalBackupContext or validate_provider_preparation(context.contract) is not RECONCILED
            or context.contract['source_roles'].get('origin_kind')!=KIND or context.provider_adapter is None):
        raise RuntimeError('isolated_replica_historical_context_required')
    raw=protected(POLICY,private=True).read_bytes()
    if not 0<len(raw)<=32768:raise RuntimeError('isolated_replica_configuration_size')
    p=validate_policy(strict_json(raw),now=int(time.time()));sha=hashlib.sha256(raw).hexdigest()
    from .automatic_release_recovery import historical_context
    from .historical_origin import restored_context
    from .isolated_release_environment import observe_host,observe_effect_fence
    from .active_recovery_inputs import controller_tree_digest
    from .control_plane_upgrade import SystemOperations
    host=observe_host();source=historical_context(p['historical_origin'])
    original=restored_context(p['historical_origin'],source,now=int(time.time()))
    if (p['environment_id']!='isolated-'+host['realm_id'] or host['version']!=2
            or any(p[k]!=host[k] for k in ('guest_uuid','machine_id','root_filesystem_uuid','database_system_identifier'))
            or p['controller_sha']!=SystemOperations().installed_sha() or p['controller_tree_sha256']!=controller_tree_digest()
            or p['historical_origin']!=context.contract['source_roles'] or digest(source)!=p['source_origin_sha256']
            or original['database']['system_identifier']!=p['database_system_identifier']
            or context.contract['candidate']['source_sha']!=p['candidate_application_sha']
            or sha!=context.document['live_configuration_sha256']['node1_configuration']):
        raise RuntimeError('isolated_replica_source_or_policy_changed')
    context.guard();observe_effect_fence(execution=True)
    return p,sha


def sign_parent_request(q,p,expected,private_key):
    """Independent parent pins the exact frozen operation before signing."""
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    validate_policy(p,now=int(time.time()));validate_request(q,p,expected,now=int(time.time()))
    public=base64.b64encode(private_key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()
    if public!=p['source_public_key']:raise RuntimeError('isolated_replica_parent_key_changed')
    return {'payload':q,'signature':base64.b64encode(private_key.sign(canonical(q))).decode()}


def verify_signature(packet,key):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if not isinstance(packet,dict) or set(packet)!={'payload','signature'}:
        raise RuntimeError('isolated_replica_packet_invalid')
    try:Ed25519PublicKey.from_public_bytes(base64.b64decode(key,validate=True)).verify(
        base64.b64decode(packet['signature'],validate=True),canonical(packet['payload']))
    except Exception:raise RuntimeError('isolated_replica_signature_invalid') from None
    return packet['payload']


def verify_receipt(packet,q,p,*,now):
    value=verify_signature(packet,p['receiver_public_key'])
    if (not isinstance(value,dict) or set(value)!={'version','kind','request_sha256','receiver_id',
            'physical_host_uuid','filesystem_uuid','received_at','replica','database_restored','application_restored',
            'deployment_authority_issued','migration_sql_executed'}
            or type(value['version']) is not int or value['version']!=1
            or value['kind']!='independently-received-maintenance-replica'
            or value['request_sha256']!=digest(q) or value['receiver_id']!=p['receiver_id']
            or value['physical_host_uuid']!=p['receiver_physical_host_uuid'] or value['filesystem_uuid']!=p['receiver_filesystem_uuid']
            or type(value['received_at']) is not int or not q['created_at']<=value['received_at']<=now<q['expires_at']
            or any(value[k] is not False for k in ('database_restored','application_restored','deployment_authority_issued','migration_sql_executed'))):
        raise RuntimeError('isolated_replica_receipt_scope_invalid')
    replica=value['replica']
    expected={'operation':'actual-append-only-normal-backup-replica','plan_sha256':q['scope_sha256'],
        'backup_id':q['backup_id'],'sha256sums_sha256':q['sha256sums_sha256'],'schema':q['schema'],
        'namespace':NAMESPACE,'maintenance_manifest_sha256':q['maintenance_manifest_sha256'],
        'checksum_exit_code':0,'historical_backups_modified':False,'latest_modified':False,'retention_performed':False}
    if (not isinstance(replica,dict) or any(replica.get(k)!=v or type(replica.get(k)) is not type(v) for k,v in expected.items())
            or replica.get('destination')!='/opt/madar-recovery-tests/'+p['receiver_run_id']+'/maintenance-replicas/'+q['scope_sha256']+'/'+q['backup_id']):
        raise RuntimeError('isolated_replica_received_inventory_invalid')
    return {**replica,'independent_receiver_receipt':packet}


def replicate(context,archive,backup,sums,maintenance_sha):
    """Parent-mediated bytes transport; local restore has already executed."""
    from .control_plane_upgrade import require_root_directory
    p,sha=policy(context);context.authority()
    require_root_directory(ROOT,create=True)
    if len(list(ROOT.iterdir()))>=8:raise RuntimeError('isolated_replica_transfer_retention_required')
    archive.seek(0,os.SEEK_END);size=archive.tell();archive.seek(0)
    if not 0<size<=p['max_archive_bytes'] or shutil.disk_usage(ROOT).free<size+5*1024**3:
        raise RuntimeError('isolated_replica_archive_headroom')
    nonce=str(uuid.uuid4());directory=ROOT/nonce;directory.mkdir(mode=0o700)
    destination=directory/'archive.tar';checksum=hashlib.sha256()
    with destination.open('xb') as output:
        os.fchmod(output.fileno(),0o600)
        while chunk:=archive.read(1024**2):output.write(chunk);checksum.update(chunk)
        output.flush();os.fsync(output.fileno())
    if destination.stat().st_size!=size:raise RuntimeError('isolated_replica_archive_changed')
    now=int(time.time())
    q={'version':1,'kind':'isolated-maintenance-replica-transfer','nonce':nonce,'policy_sha256':sha,
        **request_context(context),'created_at':now,'expires_at':min(now+300,p['expires_at']),
        'backup_id':backup.name,'sha256sums_sha256':sums,'maintenance_manifest_sha256':maintenance_sha,
        'archive_sha256':checksum.hexdigest(),'archive_bytes':size}
    validate_request(q,p,{**request_context(context),'policy_sha256':sha},now=now)
    atomic_json(directory/'request.json',q,exclusive=True);response=directory/'response.json'
    deadline=time.monotonic()+300;status='FAILED';receipt_sha=None
    try:
        while time.monotonic()<deadline and int(time.time())<q['expires_at']:
            if response.exists() or response.is_symlink():
                raw=protected(response,private=True).read_bytes()
                if not 0<len(raw)<=65536:raise RuntimeError('isolated_replica_response_size')
                packet=strict_json(raw);result=verify_receipt(packet,q,p,now=int(time.time()))
                if policy(context)!=(p,sha):raise RuntimeError('isolated_replica_policy_changed_during_transfer')
                context.authority();receipt_sha=digest(packet);status='RECEIVED'
                return result
            time.sleep(.25)
        raise RuntimeError('isolated_replica_transfer_timeout')
    finally:
        atomic_json(directory/'audit.json',{'request':q,'status':status,'receiver_receipt_sha256':receipt_sha,
            'recorded_at':int(time.time()),'deployment_authority_issued':False},exclusive=True)
        # This exact root-created copy only. Failed transfers stay fenced and
        # retain compact request/audit evidence, not a duplicate bulk archive.
        with protected(destination,private=True).open('rb') as stream:
            retained_digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if retained_digest!=q['archive_sha256']:
            raise RuntimeError('isolated_replica_local_archive_changed')
        destination.unlink()

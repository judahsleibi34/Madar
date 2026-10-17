"""Exact coordinated admission inside the existing protected coordinator.

No CLI, credential issuer, database connection factory or production executor.
The ordinary automatic manifest loader deliberately continues to reject147.
"""
import hashlib
import json
from pathlib import Path
import re

MANIFEST='migrations-147-148-coordinated.json'
BRIDGE='schema-146-148-coordinated.json'
MANIFEST_SHA256='ddc9d0efc386f43cf35c6b73edc394feab5a7f29576596cc2df53340b5111051'
BRIDGE_SHA256='60a6b0ad05d0d823e88db963522835459287698ac94bef7cbdea1615240d55a7'
SQL_SHA256={147:'bc76737e03ddf3dc369e444f34435dbded600ab1cae3209555b5bde6647d60f3',
            148:'a6788acfbe91129fcc55cbcd9c42440bbb91a785518afb99830c6137ed3c3096'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_manifest(root):
    root=Path(root).resolve();release=root/'web/deployment/releases'
    if sha((release/MANIFEST).read_bytes())!=MANIFEST_SHA256 or sha((release/BRIDGE).read_bytes())!=BRIDGE_SHA256:
        raise RuntimeError('schema148_metadata_changed')
    raw=json.loads((release/MANIFEST).read_text())
    original=[]
    for name in ('migrations-146-147-notification-fencing.json','migrations-147-148-reservation-capacity.json'):
        original+=json.loads((release/name).read_text())['migrations']
    if raw['migrations']!=original or [row['number'] for row in original]!=[147,148]:
        raise RuntimeError('schema148_migration_order_changed')
    for row in original:
        path=root/row['path'];mirror=root/'web/supabase/migrations'/path.name
        if (root not in path.resolve().parents or path.is_symlink() or mirror.is_symlink()
                or path.read_bytes()!=mirror.read_bytes() or sha(path.read_bytes())!=row['sha256']
                or row['sha256']!=SQL_SHA256[row['number']]):
            raise RuntimeError('schema148_sql_changed')
    return raw


def admitted_manifest(root,contract):
    """Only the fresh protected maintenance caller may select coordinated SQL."""
    from deployment.lib.completed_normal_profile import profile,FENCED
    from deployment.lib.completed_normal_admission import require_fresh_authorization
    from deployment.lib.migration_executor import MigrationManifest,Migration
    if profile(contract) is not FENCED or contract['migration_manifest_sha256']!=MANIFEST_SHA256:
        raise RuntimeError('schema148_operation_required')
    require_fresh_authorization(contract)
    raw=source_manifest(root)
    return MigrationManifest(contract['candidate']['source_sha'],tuple(Migration(
        row['number'],Path(root)/row['path'],row['sha256'],row['from_schema'],row['to_schema'],row['compatibility'])
        for row in raw['migrations']),coordinated=True)


QUIESCENCE_SQL="""
select json_build_object(
 'system_identifier',(select system_identifier::text from pg_control_system()),
 'schema',(select schema_version from public.application_schema_state where contract_key='core'),
 'processing',(select count(*) from public.notification_deliveries where status='processing'),
 'expired_processing',(select count(*) from public.notification_deliveries where status='processing' and processing_lease_until<=clock_timestamp()),
 'other_transactions',(select count(*) from pg_stat_activity where datname=current_database() and pid<>pg_backend_pid()
   and backend_type='client backend' and xact_start is not null),
 'prepared_transactions',(select count(*) from pg_prepared_xacts where database=current_database()),
 'queue_locks',(select count(*) from pg_locks where relation='public.notification_deliveries'::regclass and pid is distinct from pg_backend_pid()),
 'protocol',case when to_regprocedure('public.notification_delivery_protocol()') is null then 1 else 2 end)
"""


def require_database_quiescence(observed,contract,expected_schema):
    if (set(observed)!={'system_identifier','schema','processing','expired_processing','other_transactions','prepared_transactions','queue_locks','protocol'}
            or observed['system_identifier']!=contract['database']['system_identifier']
            or type(observed['schema']) is not int or observed['schema']!=expected_schema
            or type(observed['protocol']) is not int or observed['protocol']!=(1 if expected_schema==146 else 2)
            or any(type(observed[key]) is not int or observed[key]!=0 for key in
                   ('processing','expired_processing','other_transactions','prepared_transactions','queue_locks'))):
        raise RuntimeError('schema148_database_not_quiescent')
    return observed


def consumer_inventory(rows,origin_image,candidate_image):
    """Report possible consumers without emitting environment/command contents.

    Unknown images running notification code remain ambiguous. A different
    project label alone is never proof of a different database.
    """
    result={}
    for row in rows:
        config=row.get('Config',{});command=json.dumps([config.get('Entrypoint'),config.get('Cmd')])
        possible='notification_worker' in command or ('notification' in row.get('Name','') and row.get('Image') in {origin_image,candidate_image})
        if possible:
            result[row['Id']]={'image':row['Image'],'running':bool(row['State'].get('Running') or row['State'].get('Restarting')),
                'restart':row['HostConfig']['RestartPolicy']['Name']}
    return result


def verify_consumer_inventory(observed,policy,candidate_ids):
    legacy=policy.get('legacy_consumers')
    if (set(policy)!={'version','operation','legacy_consumers'} or type(policy['version']) is not int or policy['version']!=1
            or policy['operation']!='notification-protocol2-exclusive-cutover'
            or not isinstance(legacy,dict) or not legacy
            or any(not re.fullmatch('[0-9a-f]{64}',str(k)) or not re.fullmatch('sha256:[0-9a-f]{64}',str(v)) for k,v in legacy.items())
            or set(legacy)&set(candidate_ids) or set(observed)!=set(legacy)|set(candidate_ids)):
        raise RuntimeError('schema148_consumer_inventory_ambiguous')
    for identifier,image in legacy.items():
        if observed[identifier]!={'image':image,'running':False,'restart':'no'}:
            raise RuntimeError('schema148_legacy_consumer_not_fenced')
    # Candidate processes may remain healthy READ_ONLY; real grant/worker
    # ownership is independently verified by the existing kernel, not here.
    return {'legacy_consumers':len(legacy),'candidate_consumers':len(candidate_ids),'unknown_consumers':0}


def live_consumer_inventory(runtime,contract,policy,candidate_ids,*,rows=None):
    from deployment.lib.schema148_consumers import unrelated_consumers,host_processes
    if rows is None:
        identifiers=runtime.command(['docker','ps','--all','--quiet','--no-trunc']).split()
        rows=list(runtime.inspect(identifiers).values())
    excluded=unrelated_consumers(rows,contract,policy.get('unrelated_consumers',{}),candidate_ids=candidate_ids,target_rest_binding=policy.get('target_rest'))
    if excluded & (set(policy.get('legacy_consumers',{}))|set(candidate_ids)):
        raise RuntimeError('schema148_consumer_scope_overlap')
    if set(policy) not in ({'version','operation','legacy_consumers'},{'version','operation','legacy_consumers','unrelated_consumers','target_rest'}):
        raise RuntimeError('schema148_consumer_policy_invalid')
    inventory=consumer_inventory(rows,contract['origin']['images']['backend'],contract['candidate']['images']['backend'])
    if not excluded.issubset(inventory):raise RuntimeError('schema148_unrelated_consumer_missing')
    result=verify_consumer_inventory({key:value for key,value in inventory.items() if key not in excluded},
        {key:policy[key] for key in ('version','operation','legacy_consumers')},candidate_ids)
    for identifier in candidate_ids:
        if inventory[identifier]['image']!=contract['candidate']['images']['backend'] or inventory[identifier]['restart']!='no':
            raise RuntimeError('schema148_candidate_consumer_changed')
    result.update(unrelated_consumers_verified=len(excluded),host_processes_verified=host_processes(runtime,set(candidate_ids)|excluded,
        required_pids={row['State'].get('Pid',0) for row in rows if row['Id'] in candidate_ids}))
    return result


def verify_actor_consumers(actor):
    from deployment.lib.completed_normal_admission import digest
    from deployment.lib.provider_recovery_runtime import protected
    policy=actor.document.get('notification_cutover')
    if digest(policy)!=actor.contract['notification_cutover_sha256']:
        raise RuntimeError('schema148_cutover_policy_changed')
    origin=json.loads(protected(Path(actor.contract['source_roles']['completion_root'])/'candidate-runtime.json',private=True).read_text())
    origin_id=origin['runtimes']['notification-worker']['id']
    if policy.get('legacy_consumers',{}).get(origin_id)!=actor.contract['origin']['images']['backend']:
        raise RuntimeError('schema148_origin_consumer_missing')
    candidate=json.loads(protected(actor.root/'candidate-runtime.json',private=True).read_text())
    new_id=candidate['runtimes']['notification-worker']['id']
    return live_consumer_inventory(actor.runtime,actor.contract,policy,{new_id})


def seal_quiescence(actor):
    """Root orchestration checkpoint after existing worker/boot/write fences."""
    from deployment.lib.completed_normal_admission import digest,encoded,require_fresh_authorization
    from deployment.lib.emergency_routing_repair import exclusive
    actor.guard();require_fresh_authorization(actor.contract)
    actor.candidate().round(normal=False)
    workers=verify_actor_consumers(actor)
    raw=actor.runtime.command(['docker','exec',actor.contract['database']['container_id'],'psql','-XqAt',
        '-v','ON_ERROR_STOP=1','-U','postgres','-d','postgres','-c',
        "BEGIN READ ONLY; SET LOCAL statement_timeout='5s'; "+QUIESCENCE_SQL+'; COMMIT;'])
    database=require_database_quiescence(json.loads(raw),actor.contract,146)
    record={'operation':actor.contract['operation'],'context_sha256':digest(actor.contract),
        'policy_sha256':actor.contract['notification_cutover_sha256'],'database':database,'consumers':workers,
        'customer_database_restored':False}
    exclusive(actor.root/'notification-quiescence.json',encoded(record))
    return record


def migration_guard(contract,cursor,migration,*,consumer_guard):
    from deployment.lib.completed_normal_admission import require_fresh_authorization
    require_fresh_authorization(contract);consumer_guard()
    cursor.execute("set lock_timeout='5s'; set statement_timeout='60s'")
    cursor.execute(QUIESCENCE_SQL)
    require_database_quiescence(cursor.fetchone()[0],contract,migration.from_schema)
    if migration.from_schema>=147:
        cursor.execute('select public.notification_delivery_protocol()')
        if cursor.fetchone()[0]!=2:raise RuntimeError('schema148_protocol_invalid')

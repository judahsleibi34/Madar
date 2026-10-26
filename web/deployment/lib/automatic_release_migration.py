"""Automatic lifecycle adapter to LockedMigrationExecutor, never another engine.

Only independently enrolled isolated execution is currently enabled. Exact
selection, signed native acceptance, real backup bytes, live history and both
controller locks are mandatory. Unknown commit outcomes retain the durable fence.
"""
import hashlib,os,time
from pathlib import Path
from .migration_inventory import canonical,digest,strict_json
from .migration_plan import generate
from .migration_executor import LockedMigrationExecutor,MigrationManifest,Migration,atomic_json
from .provider_recovery_runtime import protected
from . import automatic_release_admission as admission

BACKUPS=Path('/var/lib/madar-control-plane/automatic-backups')
HISTORY=Path('/var/lib/madar-control-plane/automatic-history.json')
MIGRATION_FIELDS={'plan_sha256','origin_schema','target_schema','boundaries','backup_files','native_exit_codes'}


def proof_scope(value,proof):
    record=proof.get('migration')
    plan=value['plan'];rows=plan['migrations']
    if (not isinstance(record,dict) or set(record)!=MIGRATION_FIELDS
            or record['plan_sha256']!=digest(plan)
            or (record['origin_schema'],record['target_schema'])!=(plan['origin_schema'],plan['target_schema'])
            or not isinstance(record['native_exit_codes'],list) or not record['native_exit_codes']
            or any(type(n) is not int or n!=0 for n in record['native_exit_codes'])
            or not isinstance(record['boundaries'],list) or len(record['boundaries'])!=len(rows)
            or not isinstance(record['backup_files'],dict)
            or set(record['backup_files'])!={'database.dump','roles.sql','objects.tar'}):
        raise RuntimeError('automatic_migration_native_acceptance_required')
    import re
    for boundary,row in zip(record['boundaries'],rows):
        if (set(boundary)!={'schema','sql_sha256','structure_sha256','protocols'}
                or type(boundary['schema']) is not int or boundary['schema']!=row['to_schema']
                or boundary['sql_sha256']!=row['sha256']
                or not re.fullmatch('[a-f0-9]{64}',str(boundary['structure_sha256']))
                or boundary['protocols']!=plan['compatibility_intent']['worker_protocols']):
            raise RuntimeError('automatic_migration_boundary_acceptance_changed')
    for name,item in record['backup_files'].items():
        if (not isinstance(item,dict) or set(item)!={'sha256','bytes'}
                or not re.fullmatch('[a-f0-9]{64}',str(item['sha256']))
                or type(item['bytes']) is not int or not 0<item['bytes']<=1024**3):
            raise RuntimeError('automatic_migration_backup_manifest_invalid')
    recovery=proof['gates']['recovery']
    if (record['backup_files']['database.dump']['sha256']!=recovery['backup_sha256']
            or record['backup_files']['objects.tar']['sha256']!=recovery['objects_sha256']):
        raise RuntimeError('automatic_migration_recovery_bytes_disagree')
    return record


def verify_backup(value,proof,record):
    path=BACKUPS/value['source_sha']
    for name,item in record['backup_files'].items():
        file=protected(path/name,private=True)
        if file.stat().st_size!=item['bytes']:raise RuntimeError('automatic_migration_backup_size_changed')
        h=hashlib.sha256();count=0;deadline=time.monotonic()+30
        with file.open('rb') as stream:
            while block:=stream.read(65536):
                count+=len(block);h.update(block)
                if count>item['bytes'] or time.monotonic()>deadline:raise RuntimeError('automatic_migration_backup_budget')
        if count!=item['bytes'] or h.hexdigest()!=item['sha256']:
            raise RuntimeError('automatic_migration_backup_corrupt')
    return path


def prepared(value,system):
    """Read and independently reauthenticate before issuance and execution."""
    from .migration_policy import load_policy
    from .automatic_release_selection import select
    policy,_=admission.execution_policy(system);routine=load_policy()
    proof=admission.independent_evidence(value['source_sha'],policy,now=int(time.time()))
    inventory,target,selection=select(system,value['source_sha'],proof,policy,routine,value['database']['origin_schema'])
    plan=generate(system.repo,inventory,origin=value['database']['origin_schema'],target=target)
    if (selection is None or plan.document()!=value['plan']
            or value['policy_sha256']!=digest({'routine':routine,'execution':policy})
            or value['evidence'].get('migration')!=digest(proof.get('migration'))):
        raise RuntimeError('automatic_migration_selected_scope_changed')
    record=proof_scope(value,proof)
    backup=verify_backup(value,proof,record)
    if routine['version']!=2:
        raise RuntimeError('automatic_migration_budget_policy_required')
    return inventory,plan,routine,record,backup


def execute(value,system,guard):
    from .schema150_provider_adapter import require_owned_lock
    from .migration_policy import apply_transaction_limits
    from .migration_drift import history_digest,observe,measure_class_b
    from psycopg import sql
    admission.sealed(value);admission.require_reserved(value)
    require_owned_lock(system.automatic_upgrade_lock,system.upgrade_root/'upgrade.lock')
    require_owned_lock(system.deploy_lock_descriptor,system.state_root/'deploy.lock')
    inventory,plan,policy,proof,backup=prepared(value,system);document=plan.document()
    directory=admission.ROOT/'attempts'/value['attempt_id'];captured=directory/'sql'
    captured.mkdir(mode=0o700)
    rows=inventory.forward(document['origin_schema'],document['target_schema']);migrations=[]
    for item,expected in zip(rows,document['migrations']):
        if item.record()!={k:expected[k] for k in item.record()}:raise RuntimeError('automatic_migration_sql_changed')
        path=captured/(str(item.number)+'.sql')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
        with os.fdopen(fd,'wb') as f:f.write(item.sql);f.flush();os.fsync(f.fileno())
        migrations.append(Migration(item.number,path,item.sha256,expected['from_schema'],expected['to_schema'],'expand-only'))
    boundaries={b['schema']:b for b in proof['boundaries']}
    original=strict_json(protected(HISTORY,private=True).read_bytes())
    expected_original={'version':1,'system_identifier':value['database']['system_identifier'],
        'schema':document['origin_schema'],'structure_sha256':value['database']['structure_sha256'],
        'history_sha256':history_digest(inventory,document['origin_schema'])}
    if original!=expected_original:raise RuntimeError('automatic_migration_origin_history_changed')
    def before(cursor,migration):
        guard()
        cursor.execute("SELECT system_identifier::text,schema_version FROM pg_catalog.pg_control_system(),public.application_schema_state WHERE contract_key='core'")
        if cursor.fetchone()!=(value['database']['system_identifier'],migration.from_schema):
            raise RuntimeError('automatic_migration_executor_database_changed')
        cursor.execute("SELECT 1 FROM pg_catalog.pg_locks WHERE pid=pg_backend_pid() AND locktype='advisory' AND granted AND ((classid::bigint<<32)|objid::bigint)=%s",(LockedMigrationExecutor.LOCK_KEY,))
        if cursor.fetchone()!=(1,):raise RuntimeError('automatic_migration_executor_lock_missing')
        structure=value['database']['structure_sha256'] if migration.from_schema==document['origin_schema'] else boundaries[migration.from_schema]['structure_sha256']
        observed=observe(cursor.connection,required_protocols=document['compatibility_intent']['worker_protocols'],expected_structure_sha256=structure)
        if observed.system_identifier!=value['database']['system_identifier']:raise RuntimeError('automatic_migration_executor_database_changed')
        # Conservative A budgets use the same independently protected ceilings.
        # B permission itself remains operation-specific and independently checked.
        apply_transaction_limits(cursor,policy,expected_schema=migration.from_schema)
    live_measurements=[]
    def transaction(cursor,migration):
        row=next(r for r in document['migrations'] if r['number']==migration.number)
        if row['risk']['class']=='A':return
        ops=row['measurable_operations'];limits=policy['class_b']
        if row['risk']['class']!='B' or 'B' not in policy['risk_classes'] or not ops:
            raise RuntimeError('automatic_class_b_operation_not_approved')
        for operation in ops:
            if operation['kind'] not in limits['operations']:raise RuntimeError('automatic_class_b_operation_not_approved')
            cursor.execute(sql.SQL('LOCK TABLE {}.{} IN ACCESS EXCLUSIVE MODE').format(sql.Identifier(operation['schema']),sql.Identifier(operation['table'])))
            cursor.execute(sql.SQL('SELECT pg_total_relation_size(%s::regclass),count(*) FROM {}.{}').format(sql.Identifier(operation['schema']),sql.Identifier(operation['table'])),(operation['schema']+'.'+operation['table'],))
            size,count=cursor.fetchone()
            cursor.execute("SELECT pg_backend_pid(),current_setting('lock_timeout'),current_setting('statement_timeout'),current_setting('transaction_timeout')")
            pid,lock_wait,statement_deadline,transaction_deadline=cursor.fetchone()
            live_measurements.append({'migration':migration.number,'operation_sha256':digest(operation),
                'table_bytes':size,'table_rows':count,'backend_pid':pid,'lock_timeout':lock_wait,
                'statement_timeout':statement_deadline,'transaction_timeout':transaction_deadline})
            atomic_json(directory/'locked-measurements.json',{'measurements':live_measurements})
            if size>limits['max_table_bytes'] or count>limits['max_table_rows']:
                raise RuntimeError('automatic_class_b_live_budget_exceeded')
    def complete(cursor):
        guard()
        boundary=boundaries[document['target_schema']]
        observation=observe(cursor.connection,required_protocols=boundary['protocols'],expected_structure_sha256=boundary['structure_sha256'])
        if (observation.system_identifier,observation.schema)!=(value['database']['system_identifier'],document['target_schema']):
            raise RuntimeError('automatic_migration_target_changed')
    executor=LockedMigrationExecutor(connection_factory=admission.connect_database,
        manifest=MigrationManifest(value['source_sha'],tuple(migrations),coordinated=True),
        state_file=directory/'migration-execution.json',backup_dir=backup,
        backup_verifier=lambda _:verify_backup(value,None,proof),migration_guard=before,
        transaction_guard=transaction,completion_guard=complete,expected_origin=document['origin_schema'],
        failure_formatter=lambda e:type(e).__name__)
    try:result=executor.run()
    except Exception as error:
        code=str(error) if type(error) is RuntimeError and str(error).startswith(('automatic_','migration_')) else type(error).__name__
        raise RuntimeError('automatic_migration_execution_refused:'+code[:160]) from None
    target=boundaries[document['target_schema']]
    # A lost COMMIT never reaches this publication. Durable pending state then
    # requires independent observation/recovery rather than replaying this SQL.
    history={'version':1,'system_identifier':value['database']['system_identifier'],'schema':document['target_schema'],
        'structure_sha256':target['structure_sha256'],'history_sha256':history_digest(inventory,document['target_schema'])}
    atomic_json(HISTORY,history)
    receipt={'admission_sha256':digest(value),'operation_id':value['operation_id'],'attempt_id':value['attempt_id'],
        'source_sha':value['source_sha'],'database':value['database'],'plan_sha256':plan.sha256,
        'history_sha256':digest(history),'execution_sha256':digest(result),'execution':result,
        'locked_measurements':live_measurements}
    atomic_json(directory/'migration-completion.json',receipt,exclusive=True)
    return receipt

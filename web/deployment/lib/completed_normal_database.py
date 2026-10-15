"""Measured native database and customer baseline; all observation is read-only."""
import json
from pathlib import Path
from deployment.lib.completed_normal_admission import digest
from deployment.lib.completed_normal_profile import profile, LEGACY, APPLICATION, COMMERCIAL

IDENTITY_SQL="BEGIN READ ONLY; SELECT json_build_object('system_identifier',system_identifier::text,'schema',schema_version)::text FROM pg_control_system(),public.application_schema_state WHERE contract_key='core'; COMMIT;"

def database_structure_digest(contract,runtime):
    """Bind schema/roles/ACLs during NORMAL activity without freezing rows.

    No role verifier or definition leaves PostgreSQL, only one digest. The
    authoritative row baseline is still sealed after fencing and checked after
    SQL. This never changes an already approved source or migration contract.
    """
    observe_native(contract,runtime)
    sql="""BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
    SELECT encode(sha256(convert_to(coalesce(string_agg(v,'' ORDER BY v COLLATE "C"),''),'UTF8')),'hex')
    FROM (
      SELECT 'class:'||(to_jsonb(c)-ARRAY['relpages','reltuples','relallvisible','relallfrozen','relfrozenxid','relminmxid'])::text v FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('public','auth','storage')
      UNION ALL SELECT 'attribute:'||to_jsonb(a)::text FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','auth','storage') AND a.attnum>0
      UNION ALL SELECT 'constraint:'||to_jsonb(x)::text FROM pg_constraint x JOIN pg_namespace n ON n.oid=x.connamespace
        WHERE n.nspname IN ('public','auth','storage')
      UNION ALL SELECT 'proc:'||to_jsonb(p)::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname IN ('public','auth','storage')
      UNION ALL SELECT 'policy:'||to_jsonb(p)::text FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','auth','storage')
      UNION ALL SELECT 'trigger:'||to_jsonb(t)::text FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','auth','storage')
      UNION ALL SELECT 'role:'||to_jsonb(r)::text FROM pg_authid r
      UNION ALL SELECT 'membership:'||to_jsonb(m)::text FROM pg_auth_members m
    ) objects; COMMIT;"""
    value=runtime.command(['docker','exec',contract['database']['container_id'],'psql','-XqAt',
        '-v','ON_ERROR_STOP=1','-U','postgres','-d','postgres','-c',sql]).strip()
    import re
    if not re.fullmatch('[0-9a-f]{64}',value):raise RuntimeError('completed_database_structure_invalid')
    return value

def verify_preparation_baseline(contract,runtime,baseline):
    """Only the explicit new profile uses a protected execution row boundary."""
    if profile(contract) is COMMERCIAL:
        if database_structure_digest(contract,runtime)!=contract['database_structure_sha256']:
            raise RuntimeError('completed_upgrade_database_structure_changed')
        return
    if (baseline['table_roots_sha256']!=contract['customer_table_roots_sha256']
            or baseline['identity_roots_sha256']!=contract['customer_identity_roots_sha256']):
        raise RuntimeError('completed_upgrade_current_customer_data_changed')

def observe_native(contract,runtime, *, allow_pending=False):
    expected=contract['database']
    rows=runtime.inspect([expected['container_id']])
    row=next(iter(rows.values())) if len(rows)==1 else None
    if (row is None or row.get('Name')!='/supabase-db' or row['Id']!=expected['container_id'] or row['Image']!=expected['image']):
        raise RuntimeError('completed_normal_native_database_identity_changed')
    from deployment.lib.completed_normal_resources import measured_spec_matches
    if not measured_spec_matches(row,expected['spec_sha256']):
        raise RuntimeError('completed_normal_native_database_configuration_changed')
    networks=row['NetworkSettings']['Networks']
    if set(networks)!={expected['network_name']}:
        raise RuntimeError('completed_normal_native_database_network_changed')
    network=networks[expected['network_name']]
    if network.get('NetworkID')!=expected['network_id']:
        # Docker can retain declarations but clear endpoints on a stopped
        # container. The intended network object is still mandatory below.
        if (row['State']['Running'] or network.get('NetworkID')!='' or network.get('EndpointID')
                or network.get('IPAddress') or row['State'].get('Status') not in {'created','exited'}):
            raise RuntimeError('completed_normal_native_database_network_changed')
    objects=json.loads(runtime.command(['docker','network','inspect',expected['network_name']]))
    if len(objects)!=1 or objects[0]['Id']!=expected['network_id']:
        raise RuntimeError('completed_normal_native_database_network_changed')
    if not row['State']['Running'] or row['State'].get('Health',{}).get('Status')!='healthy':
        if allow_pending:
            from deployment.lib.emergency_routing_repair import AvailabilityFailure
            raise AvailabilityFailure('completed_normal_native_database_start_pending')
        raise RuntimeError('completed_normal_native_database_unhealthy')
    observed=json.loads(runtime.command(['docker','exec',expected['container_id'],'psql','-XqAt',
        '-v','ON_ERROR_STOP=1','-U','postgres','-d','postgres','-c',IDENTITY_SQL]))
    if (observed.get('system_identifier')!=expected['system_identifier']
            or not profile(contract).supports(observed.get('schema'))):
        raise RuntimeError('completed_normal_native_database_schema_changed')
    return observed['schema']

def require_normal_migration_boundary(contract, schema, root, state_root):
    """Boot may recover a grant, but must never finish an interrupted upgrade.

    The root intent is sealed BEFORE the first SQL connection. Even an
    interruption before migration116 commits requires read-only forward repair.
    Only independently sealed completion of this exact chain permits NORMAL
    recovery after advancement. Historical schema115 publication is insufficient.
    """
    from deployment.lib.provider_recovery_runtime import protected, file_digest
    selected = profile(contract)
    intent=Path(root)/'migration-intent.json'
    if selected is APPLICATION:
        if schema != 144 or any((Path(root)/name).exists() for name in (
                'migration-intent.json', 'migration-completion.json', 'migration-execution.json')):
            raise RuntimeError('compatible_boot_application_only_schema_changed')
        return
    if not intent.exists():
        if schema!=selected.source:
            raise RuntimeError('compatible_boot_unattested_schema_advancement')
        return
    expected={'operation':contract['operation'],'context_sha256':digest(contract),
              'source_sha':contract['candidate']['source_sha'],
              'manifest_sha256':contract['migration_manifest_sha256'],
              'source_schema':selected.source,'target_schema':selected.target,'database_restored':False}
    if json.loads(protected(intent,private=True).read_text())!=expected:
        raise RuntimeError('compatible_boot_migration_intent_changed')
    completion=Path(root)/'migration-completion.json'
    if not completion.exists():
        raise RuntimeError('compatible_boot_migration_forward_repair_required')
    record=json.loads(protected(completion,private=True).read_text())
    # Root seals copies of the actual child execution and frozen manifest only
    # after independent native-schema validation. Operator-writable release
    # state is never an authorization source for reboot recovery.
    execution=Path(root)/'migration-execution.json'
    if (set(record)!=set(expected)|{'execution_sha256','observed_schema'}
            or any(record[k]!=v for k,v in expected.items()) or record['observed_schema']!=selected.target
            or schema!=selected.target or file_digest(protected(execution,private=True))!=record['execution_sha256']):
        raise RuntimeError('compatible_boot_migration_completion_changed')
    result=json.loads(execution.read_text())
    manifest_path=Path(root)/'migration-manifest.json'
    if file_digest(protected(manifest_path))!=contract['migration_manifest_sha256']:
        raise RuntimeError('compatible_boot_migration_manifest_changed')
    manifest=json.loads(manifest_path.read_text())
    expected_records=[(m.get('number'),m.get('sha256')) for m in manifest.get('migrations',[])]
    actual=[(r.get('number'),r.get('checksum')) for r in result.get('migrations',[])
            if r.get('status') in {'applied','already_applied'}]
    if (result.get('release_sha')!=contract['candidate']['source_sha'] or result.get('status')!='completed'
            or result.get('phase')!='complete' or result.get('observed_schema')!=selected.target
            or (result.get('backup') or {}).get('verified') is not True
            or [n for n,_ in expected_records]!=list(selected.migrations) or actual!=expected_records):
        raise RuntimeError('compatible_boot_migration_execution_invalid')

def require_manual_normal_completion(contract, root):
    """An interrupted manual operation must recover READ_ONLY after reboot."""
    selected=profile(contract)
    if selected is LEGACY:return
    from deployment.lib.provider_recovery_runtime import protected
    path=Path(root)/'normal-completion.json'
    if not path.exists():raise RuntimeError('compatible_boot_normal_completion_pending')
    record=json.loads(protected(path,private=True).read_text())
    backup=json.loads(protected(Path(root)/'post-migration-backup.json',private=True).read_text())
    if (record.get('operation')!=selected.operation or record.get('context_sha256')!=digest(contract)
            or record.get('schema')!=selected.target or record.get('mode')!='NORMAL'
            or record.get('application_sha')!=contract['candidate']['source_sha']
            or record.get('controller_sha')!=contract['candidate']['controller_sha']
            or record.get('images')!=contract['candidate']['images'] or record.get('backup')!=backup
            or record.get('customer_database_restored') is not False or backup.get('schema')!=selected.target
            or backup.get('source_sha')!=contract['candidate']['source_sha']
            or backup.get('images')!=contract['candidate']['images']
            or backup.get('restore',{}).get('status')!='logical_database_and_file_restore_passed'
            or backup.get('restore',{}).get('backup_schema')!=selected.target
            or backup.get('node1',{}).get('checksum_exit_code')!=0):
        raise RuntimeError('compatible_boot_normal_completion_changed')


def customer_baseline(contract,runtime):
    """No customer field leaves PostgreSQL; return only table/Auth/storage roots."""
    from deployment.lib.active_recovery_reconciliation import CurrentLocalReconciliation
    if profile(contract) is not LEGACY:
        current = migration_customer_snapshot(contract, runtime)
        identities = [row for name,row in sorted(current['roots'].items()) if not name.startswith('public.')]
        return {'tables':current, 'table_roots_sha256':digest(current),
            'identity_roots':identities, 'identity_roots_sha256':digest({'roots':identities})}
    from deployment.lib.active_recovery_resumption import load_saved_resumption_plan
    root=Path(contract['source_roles']['completion_root'])
    def guard():
        if observe_native(contract,runtime)!=115:
            raise RuntimeError('completed_normal_customer_source_schema_changed')
    guard()
    packet,table_digest=CurrentLocalReconciliation(load_saved_resumption_plan(root),root,runtime,
        guard,guard).snapshot()
    if len(packet['table_roots'])!=96:raise RuntimeError('completed_normal_customer_table_inventory_changed')
    statements=[]
    for name in ('auth.users','auth.identities','auth.mfa_factors','storage.objects','storage.buckets'):
        statements.append("SELECT json_build_object('table','"+name+"','count',count(*),'sha256',"
            "encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h COLLATE \"C\"),''),'UTF8')),'hex'))::text "
            "FROM (SELECT encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') h FROM "+name+" t) rows;")
    sql="BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL statement_timeout='60s'; SET LOCAL TIME ZONE 'UTC';\n"+'\n'.join(statements)+'\nCOMMIT;'
    raw=runtime.command(['docker','exec',contract['database']['container_id'],'psql','-XqAt',
        '-v','ON_ERROR_STOP=1','-U','postgres','-d','postgres','-c',sql])
    identities=[json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(identities)!=5 or any(r['table']!=name for r,name in zip(identities,('auth.users','auth.identities','auth.mfa_factors','storage.objects','storage.buckets'))):
        raise RuntimeError('completed_normal_customer_identity_inventory_changed')
    guard()
    return {'tables':packet,'table_roots_sha256':table_digest,'identity_roots':identities,
            'identity_roots_sha256':digest({'roots':identities})}


def migration_customer_snapshot(contract,runtime,*,columns=None):
    """Measure original columns inside one current-data, read-only snapshot.

    Added columns/tables are legitimate expand migrations. Existing customer
    values, password verifiers, original MFA factors and object metadata must
    remain exact. No rows, credentials or object names leave PostgreSQL.
    This strict SQL-boundary check does not treat concurrent Auth changes as a
    migration success: it fails safely for independent reconciliation instead.
    """
    from deployment.lib.active_recovery_reconciliation import identifier
    schema=observe_native(contract,runtime)
    def query(body):
        sql=("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL statement_timeout='60s'; "
             "SET LOCAL TIME ZONE 'UTC';\n"+body+"\nCOMMIT;")
        raw=runtime.command(['docker','exec',contract['database']['container_id'],'psql','-XqAt',
            '-v','ON_ERROR_STOP=1','-U','postgres','-d','postgres','-c',sql])
        return [json.loads(line) for line in raw.splitlines() if line.strip()]
    if columns is None:
        if schema!=profile(contract).source:raise RuntimeError('completed_migration_customer_source_schema_changed')
        rows=query("SELECT json_build_object('schema',n.nspname,'table',c.relname,'columns',"
            "json_agg(a.attname ORDER BY a.attnum))::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped "
            "WHERE c.relkind IN ('r','p') AND (n.nspname='public' OR "
            "(n.nspname='auth' AND c.relname IN ('users','identities','mfa_factors')) OR "
            "(n.nspname='storage' AND c.relname IN ('objects','buckets'))) "
            "GROUP BY n.nspname,c.relname ORDER BY n.nspname,c.relname;")
        columns={row['schema']+'.'+row['table']:row['columns'] for row in rows}
    if (not isinstance(columns,dict) or (len(columns)!=101 if profile(contract) is LEGACY else len(columns)<101)
            or (len([name for name in columns if name.startswith('public.')])!=96 if profile(contract) is LEGACY
                else len([name for name in columns if name.startswith('public.')])!=len(columns)-5)
            or not {'auth.users','auth.identities','auth.mfa_factors','storage.objects','storage.buckets'}.issubset(columns)
            or any(not isinstance(names,list) or not names or len(names)!=len(set(names))
                or any(not isinstance(n,str) or not n for n in names) for names in columns.values())):
        raise RuntimeError('completed_migration_customer_column_inventory_invalid')
    statements=[]
    for name,names in sorted(columns.items()):
        parts=name.split('.')
        if len(parts)!=2 or parts[0] not in {'public','auth','storage'}:
            raise RuntimeError('completed_migration_customer_column_inventory_invalid')
        table='.'.join(identifier(part) for part in parts)
        projection=','.join('t.'+identifier(n) for n in names)
        literal="'"+name.replace("'","''")+"'"
        statements.append("SELECT json_build_object('table',"+literal+",'count',count(*),'sha256',"
            "encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h COLLATE \"C\"),''),'UTF8')),'hex'))::text "
            "FROM (SELECT encode(sha256(convert_to(to_jsonb(ROW("+projection+"))::text,'UTF8')),'hex') h FROM "+table+" t) rows;")
    statements.append("SELECT json_build_object('schema',schema_version)::text FROM public.application_schema_state WHERE contract_key='core';")
    rows=query('\n'.join(statements))
    if (len(rows)!=len(columns)+1 or rows[-1]!={'schema':schema}
            or [row.get('table') for row in rows[:-1]]!=sorted(columns)):
        raise RuntimeError('completed_migration_customer_snapshot_invalid')
    if observe_native(contract,runtime)!=schema:
        raise RuntimeError('completed_migration_customer_snapshot_schema_changed')
    result={'schema':schema,'columns':columns,'roots':{row['table']:row for row in rows[:-1]}}
    if profile(contract) is COMMERCIAL:
        #146 adds exactly one immutable catalog row, not customer activity.
        #Measure every original row as well as the exact approved addition.
        expected="""jsonb_build_object('id','launch_2026_v2','version','2026-10-14',
            'effective_from','2026-10-14T00:00:00+00:00','currency','USD','billing_interval','month',
            'standalone_minor','{"forms":1500,"website":2000,"ecommerce":2500}'::jsonb,
            'bundle_minor','{"2":3000,"3":4000}'::jsonb,'sales_start_at',null,'sales_end_at',null)"""
        addition=query("SELECT json_build_object('count',count(*),'exact',coalesce(bool_and(to_jsonb(b)="+
            expected+"),false))::text FROM public.commercial_price_books b WHERE id='launch_2026_v2';")[0]
        if schema==144:
            if addition['count']!=0:raise RuntimeError('completed_commercial_price_book_already_present')
        elif schema==146:
            if addition!={'count':1,'exact':True}:
                raise RuntimeError('completed_commercial_price_book_delta_changed')
            original=query("SELECT json_build_object('table','public.commercial_price_books','count',count(*),'sha256',"
                "encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h COLLATE \"C\"),''),'UTF8')),'hex'))::text "
                "FROM (SELECT encode(sha256(convert_to(to_jsonb(ROW(t.*))::text,'UTF8')),'hex') h "
                "FROM public.commercial_price_books t WHERE id<>'launch_2026_v2') rows;")[0]
            result['commercial_addition']={'verified':True,'preserved_original_rows':original}
    return result


def verify_migration_customer_preservation(before,after, *, contract=None):
    """Only the approved schema-state row may differ across the SQL chain."""
    selected = LEGACY if contract is None else profile(contract)
    if (before.get('schema')!=selected.source or after.get('schema')!=selected.target
            or before.get('columns')!=after.get('columns')
            or set(before.get('roots',{}))!=set(after.get('roots',{}))
            or (len(before['roots'])!=101 if selected is LEGACY else len(before['roots'])<101)):
        raise RuntimeError('completed_migration_customer_preservation_inventory_changed')
    changed=[name for name in before['roots'] if before['roots'][name]!=after['roots'][name]]
    if selected is COMMERCIAL:
        delta=after.get('commercial_addition',{})
        original=before['roots']['public.commercial_price_books']
        if (set(changed)!={'public.application_schema_state','public.commercial_price_books'}
                or delta.get('verified') is not True or delta.get('preserved_original_rows')!=original
                or after['roots']['public.commercial_price_books']['count']!=original['count']+1
                or before['roots']['public.application_schema_state']['count']!=after['roots']['public.application_schema_state']['count']):
            raise RuntimeError('completed_migration_existing_customer_values_changed')
        return {'operation':'current-data-commercial-migration-comparison',
            'starting_schema':selected.source,'final_schema':selected.target,
            'original_rows_preserved':True,'price_book_delta_verified':True,
            'source_snapshot_sha256':digest(before),'target_snapshot_sha256':digest(after),'database_restored':False}
    if (changed!=['public.application_schema_state']
            or before['roots']['public.application_schema_state']['count']!=after['roots']['public.application_schema_state']['count']):
        raise RuntimeError('completed_migration_existing_customer_values_changed')
    return {'operation':'current-data-original-column-migration-comparison','starting_schema':selected.source,'final_schema':selected.target,
        'original_public_tables':len(before['roots'])-5,'original_identity_storage_tables':5,'only_schema_state_changed':True,
        'source_snapshot_sha256':digest(before),'target_snapshot_sha256':digest(after),'database_restored':False}

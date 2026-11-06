"""Bounded read-only catalog observation; no baseline learning or drift repair.

A caller must authenticate the expected root baseline/receipts independently.
A database schema number alone is not evidence of applied SQL hashes. Reuse the
existing structural digest and journals; do not invent a parallel SQL ledger.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
import time
from .completed_normal_database import STRUCTURE_SQL
from .migration_inventory import digest

PROTOCOL_FUNCTIONS={'delivery':'notification_delivery_protocol',
    'outbox':'notification_outbox_protocol','deletion':'data_deletion_ownership_protocol'}
HEX=re.compile('[a-f0-9]{64}')


# Portable schema/security semantics for independently restored rehearsal DBs.
# Historical STRUCTURE_SQL remains deliberately OID-sensitive for LOCAL drift.
SEMANTIC_SQL="""SELECT encode(sha256(convert_to(coalesce(string_agg(v,'' ORDER BY v COLLATE "C"),''),'UTF8')),'hex') FROM (
 SELECT jsonb_build_array('schema',n.nspname,pg_get_userbyid(n.nspowner),ARRAY(SELECT item::text FROM unnest(coalesce(n.nspacl,acldefault('n',n.nspowner))) item ORDER BY item::text))::text v
 FROM pg_namespace n WHERE n.nspname IN ('public','auth','storage')
 UNION ALL SELECT jsonb_build_array('class',n.nspname,c.relname,c.relkind,c.relpersistence,pg_get_userbyid(c.relowner),c.relrowsecurity,c.relforcerowsecurity,c.relreplident,c.reloptions,ARRAY(SELECT item::text FROM unnest(coalesce(c.relacl,acldefault(CASE WHEN c.relkind='S' THEN 'S'::"char" ELSE 'r'::"char" END,c.relowner))) item ORDER BY item::text),
 CASE WHEN c.relkind IN ('v','m') THEN pg_get_viewdef(c.oid,true) END,
 CASE WHEN c.relkind IN ('i','I') THEN pg_get_indexdef(c.oid) END)::text
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','auth','storage')
 UNION ALL SELECT jsonb_build_array('column',n.nspname,c.relname,row_number() OVER (PARTITION BY a.attrelid ORDER BY a.attnum),a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attidentity,a.attgenerated,a.attisdropped,a.attstorage,a.attcompression,a.attndims,ARRAY(SELECT item::text FROM unnest(a.attacl) item ORDER BY item::text),coll.collname,cn.nspname,pg_get_expr(d.adbin,d.adrelid))::text
 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
 LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum LEFT JOIN pg_collation coll ON coll.oid=a.attcollation LEFT JOIN pg_namespace cn ON cn.oid=coll.collnamespace
 WHERE n.nspname IN ('public','auth','storage') AND a.attnum>0 AND NOT a.attisdropped
 UNION ALL SELECT jsonb_build_array('constraint',n.nspname,c.relname,x.conname,x.contype,x.condeferrable,x.condeferred,x.convalidated,pg_get_constraintdef(x.oid,true))::text
 FROM pg_constraint x JOIN pg_namespace n ON n.oid=x.connamespace LEFT JOIN pg_class c ON c.oid=x.conrelid WHERE n.nspname IN ('public','auth','storage')
 UNION ALL SELECT jsonb_build_array('function',n.nspname,p.proname,pg_get_userbyid(p.proowner),ARRAY(SELECT item::text FROM unnest(coalesce(p.proacl,acldefault('f',p.proowner))) item ORDER BY item::text),pg_get_functiondef(p.oid))::text
 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('public','auth','storage') AND p.prokind<>'a'
 UNION ALL SELECT jsonb_build_array('policy',n.nspname,c.relname,p.polname,p.polcmd,p.polpermissive,ARRAY(SELECT CASE WHEN r=0 THEN 'public' ELSE pg_get_userbyid(r) END FROM unnest(p.polroles) r ORDER BY 1),pg_get_expr(p.polqual,p.polrelid),pg_get_expr(p.polwithcheck,p.polrelid))::text
 FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','auth','storage')
 UNION ALL SELECT jsonb_build_array('trigger',n.nspname,c.relname,t.tgenabled,t.tgisinternal,CASE WHEN t.tgisinternal THEN jsonb_build_array(x.conname,pg_get_constraintdef(x.oid,true),t.tgfoid::regprocedure::text,t.tgtype,t.tgdeferrable,t.tginitdeferred) ELSE jsonb_build_array(t.tgname,pg_get_triggerdef(t.oid,true)) END)::text
 FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_constraint x ON x.oid=t.tgconstraint WHERE n.nspname IN ('public','auth','storage')
 UNION ALL SELECT jsonb_build_array('type',n.nspname,t.typname,t.typtype,pg_get_userbyid(t.typowner),ARRAY(SELECT item::text FROM unnest(coalesce(t.typacl,acldefault('T',t.typowner))) item ORDER BY item::text),format_type(t.typbasetype,t.typtypmod),format_type(t.typelem,NULL),t.typnotnull,t.typdefault,t.typinput::regprocedure::text,t.typoutput::regprocedure::text)::text
 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname IN ('public','auth','storage')
 UNION ALL SELECT jsonb_build_array('enum',n.nspname,t.typname,e.enumsortorder,e.enumlabel)::text FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname IN ('public','auth','storage')
 UNION ALL SELECT jsonb_build_array('database',to_jsonb(d)-ARRAY['oid','datdba','dattablespace','datacl','datfrozenxid','datminmxid'],pg_get_userbyid(d.datdba),s.spcname,ARRAY(SELECT item::text FROM unnest(coalesce(d.datacl,acldefault('d',d.datdba))) item ORDER BY item::text))::text FROM pg_database d JOIN pg_tablespace s ON s.oid=d.dattablespace WHERE d.datname=current_database()
 UNION ALL SELECT jsonb_build_array('default_acl',pg_get_userbyid(d.defaclrole),n.nspname,d.defaclobjtype,ARRAY(SELECT item::text FROM unnest(d.defaclacl) item ORDER BY item::text))::text FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace
 UNION ALL SELECT jsonb_build_array('role_setting',r.rolname,d.datname,s.setconfig)::text FROM pg_db_role_setting s LEFT JOIN pg_roles r ON r.oid=s.setrole LEFT JOIN pg_database d ON d.oid=s.setdatabase
 UNION ALL SELECT jsonb_build_array('role',to_jsonb(r)-'oid')::text FROM pg_authid r
 UNION ALL SELECT jsonb_build_array('membership',pg_get_userbyid(m.roleid),pg_get_userbyid(m.member),pg_get_userbyid(m.grantor),m.admin_option,m.inherit_option,m.set_option)::text FROM pg_auth_members m
) objects"""


def history_digest(inventory,schema):
    inventory.forward(schema,schema)  # validates exact admitted source boundary
    return digest([m.record() for m in inventory.migrations if m.number<=schema and m.number not in inventory.excluded_versions])


@dataclass(frozen=True)
class CatalogObservation:
    system_identifier: str
    schema: int
    structure_sha256: str
    protocols: tuple[tuple[str,int],...]
    semantic_sha256: str | None = None

    def document(self):
        return {**({'semantic_sha256':self.semantic_sha256} if self.semantic_sha256 is not None else {}),'system_identifier':self.system_identifier,'schema':self.schema,
                'structure_sha256':self.structure_sha256,'protocols':dict(self.protocols),'read_only':True}


def observe(connection, *, required_protocols, expected_structure_sha256=None, expected_semantic_sha256=None, semantic=False):
    if (not isinstance(required_protocols,dict) or not set(required_protocols)<=set(PROTOCOL_FUNCTIONS)
            or any(type(v) is not int or not 0<v<1000 for v in required_protocols.values())):
        raise RuntimeError('migration_drift_protocol_expectation_invalid')
    if expected_semantic_sha256 is not None and (not isinstance(expected_semantic_sha256,str) or not HEX.fullmatch(expected_semantic_sha256)):
        raise RuntimeError('migration_drift_semantic_baseline_invalid')
    if required_protocols and expected_semantic_sha256 is None and (not isinstance(expected_structure_sha256,str) or not HEX.fullmatch(expected_structure_sha256)):
        raise RuntimeError('migration_drift_protocol_catalog_baseline_required')
    # Refuse a caller's existing transaction; do not commit or roll back its work.
    if not connection.autocommit: raise RuntimeError('migration_drift_idle_autocommit_connection_required')
    from psycopg.pq import TransactionStatus
    if connection.info.transaction_status!=TransactionStatus.IDLE:
        raise RuntimeError('migration_drift_existing_transaction_refused')
    try:
        with connection.cursor() as cursor:
            cursor.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
            cursor.execute("SET LOCAL statement_timeout='5s'")
            cursor.execute("SET LOCAL lock_timeout='1s'")
            cursor.execute('SET LOCAL search_path=pg_catalog')
            cursor.execute("SELECT system_identifier::text,schema_version FROM pg_catalog.pg_control_system(),public.application_schema_state WHERE contract_key='core'")
            identity=cursor.fetchone()
            if (not identity or len(identity)!=2 or not isinstance(identity[0],str)
                    or not re.fullmatch('[0-9]{1,32}',identity[0]) or type(identity[1]) is not int):
                raise RuntimeError('migration_drift_database_identity_invalid')
            # Shared structural aggregation inside a fixed catalog search path.
            query=STRUCTURE_SQL.removeprefix('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;').removesuffix(' COMMIT;').strip()
            query=query.removeprefix('SET LOCAL search_path=pg_catalog;').strip()
            cursor.execute(query); structure=cursor.fetchone()[0]
            if not isinstance(structure,str) or not HEX.fullmatch(structure): raise RuntimeError('migration_drift_structure_invalid')
            if expected_structure_sha256 is not None and structure!=expected_structure_sha256:
                raise RuntimeError('migration_drift_detected_before_protocol_execution')
            semantic_digest=None
            if semantic or expected_semantic_sha256 is not None:
                cursor.execute(SEMANTIC_SQL);semantic_digest=cursor.fetchone()[0]
                if not isinstance(semantic_digest,str) or not HEX.fullmatch(semantic_digest):raise RuntimeError('migration_semantic_structure_invalid')
                if expected_semantic_sha256 is not None and semantic_digest!=expected_semantic_sha256:
                    raise RuntimeError('migration_semantic_drift_before_protocol_execution')
            protocols=[]
            for name in sorted(required_protocols):
                cursor.execute('SELECT public.'+PROTOCOL_FUNCTIONS[name]+'()')
                row=cursor.fetchone()
                if not row or type(row[0]) is not int: raise RuntimeError('migration_drift_protocol_invalid')
                protocols.append((name,row[0]))
        return CatalogObservation(identity[0],identity[1],structure,tuple(protocols),semantic_digest)
    finally:
        connection.rollback()  # observer writes nothing, releases only its snapshot


def compare(inventory,observation,*,expected):
    """Expected must come from protected receipts, never auto-captured live state.

    No mismatch is repaired or marked applied. Missing historical hash evidence
    fails closed even if live core schema and protocol functions look correct.
    """
    keys={'version','system_identifier','schema','structure_sha256','protocols','history_sha256'}
    if (not isinstance(expected,dict) or set(expected)!=keys or type(expected['version']) is not int
            or expected['version']!=1 or type(expected['schema']) is not int
            or not isinstance(expected['history_sha256'],str) or not HEX.fullmatch(expected['history_sha256'])):
        raise RuntimeError('migration_drift_protected_baseline_required')
    require=dict(observation.document()); require.pop('read_only')
    if (require!={k:expected[k] for k in require}
            or history_digest(inventory,expected['schema'])!=expected['history_sha256']):
        raise RuntimeError('migration_drift_detected')
    return {'status':'PASS','coverage':'catalog-and-protected-history-comparison',
            'schema':observation.schema,'database_repaired':False,'authority_issued':False}


def measure_class_b(connection,plan,*,expected_system_identifier,expected_structure_sha256,now=None):
    """Bounded native measurements, not authorization or a lock-duration claim.

    The controller authenticates the expected catalog baseline independently.
    This snapshot neither changes data nor takes exclusive table locks. Actual
    execution must enforce its independently approved lock/statement budgets on
    the existing executor connection; an idle snapshot cannot promise no future
    contention. Large/unsupported/changed relations cannot obtain measurements.
    """
    value=plan.document()
    if (value.get('risk_class')!='B' or not value.get('migrations')
            or not isinstance(expected_system_identifier,str)
            or not re.fullmatch('[0-9]{1,32}',expected_system_identifier)
            or not isinstance(expected_structure_sha256,str) or not HEX.fullmatch(expected_structure_sha256)):
        raise RuntimeError('migration_measurement_scope_invalid')
    operations=[]
    for row in value['migrations']:
        if row['risk']['class']=='A':continue
        if row['risk']['class']!='B' or not row.get('measurable_operations'):
            raise RuntimeError('migration_measurement_operation_unsupported')
        operations.extend((row['number'],op) for op in row['measurable_operations'])
    from psycopg.pq import TransactionStatus
    from psycopg import sql
    if not connection.autocommit or connection.info.transaction_status!=TransactionStatus.IDLE:
        raise RuntimeError('migration_measurement_existing_transaction_refused')
    observed=[]
    try:
        with connection.cursor() as cursor:
            cursor.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
            cursor.execute("SET LOCAL statement_timeout='5s'; SET LOCAL lock_timeout='250ms'; SET LOCAL search_path=pg_catalog")
            cursor.execute("SELECT system_identifier::text,schema_version FROM pg_catalog.pg_control_system(),public.application_schema_state WHERE contract_key='core'")
            if cursor.fetchone()!=(expected_system_identifier,value['origin_schema']):
                raise RuntimeError('migration_measurement_database_changed')
            query=STRUCTURE_SQL.removeprefix('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;').removesuffix(' COMMIT;').strip()
            query=query.removeprefix('SET LOCAL search_path=pg_catalog;').strip()
            cursor.execute(query)
            if cursor.fetchone()!=(expected_structure_sha256,):raise RuntimeError('migration_measurement_catalog_changed')
            cursor.execute("SELECT count(*) FROM pg_catalog.pg_event_trigger WHERE evtenabled<>'D'")
            if cursor.fetchone()!=(0,):raise RuntimeError('migration_measurement_ddl_hooks_unsupported')
            for number,op in operations:
                if op.get('kind') not in {'create_btree_index','add_nullable_column'} or op.get('schema')!='public':
                    raise RuntimeError('migration_measurement_operation_unsupported')
                cursor.execute("SELECT c.oid,c.relkind,c.relpersistence,c.relispartition,pg_total_relation_size(c.oid) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=%s",(op['schema'],op['table']))
                relation=cursor.fetchone()
                if not relation or relation[1:4]!=('r','p',False):raise RuntimeError('migration_measurement_relation_unsupported')
                oid=relation[0]
                cursor.execute("SELECT a.attname,t.typname,n.nspname,t.typtype FROM pg_attribute a JOIN pg_type t ON t.oid=a.atttypid JOIN pg_namespace n ON n.oid=t.typnamespace WHERE a.attrelid=%s AND a.attnum>0 AND NOT a.attisdropped",(oid,))
                columns={row[0]:row[1:] for row in cursor.fetchall()}
                if op['kind']=='create_btree_index':
                    from .migration_risk import BUILTINS
                    if any(name not in columns or columns[name][0] not in BUILTINS
                           or columns[name][1:]!=('pg_catalog','b') for name in op['columns']):
                        raise RuntimeError('migration_measurement_column_type_unsupported')
                    cursor.execute("SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=%s",(op['schema'],op['index']))
                    if cursor.fetchone() is not None:raise RuntimeError('migration_measurement_index_already_exists')
                elif op['column'] in columns:raise RuntimeError('migration_measurement_column_already_exists')
                cursor.execute(sql.SQL('SELECT count(*) FROM {}.{}').format(sql.Identifier(op['schema']),sql.Identifier(op['table'])))
                count=cursor.fetchone()[0]
                compatible=('AccessShareLock','RowShareLock') if op['kind']=='create_btree_index' else ()
                cursor.execute("SELECT count(*) FROM pg_locks WHERE relation=%s AND pid<>pg_backend_pid() AND (NOT granted OR NOT (mode=ANY(%s)))",(oid,list(compatible)))
                conflicts=cursor.fetchone()[0]
                observed.append({'migration':number,'operation_sha256':digest(op),'table_bytes':relation[4],
                                 'table_rows':count,'conflicting_locks':conflicts})
        return {'version':1,'source_sha':value['source_sha'],'plan_sha256':plan.sha256,
            'system_identifier':expected_system_identifier,'origin_schema':value['origin_schema'],
            'structure_sha256':expected_structure_sha256,'observed_at':int(time.time()) if now is None else now,
            'operations':observed,'read_only':True}
    finally:connection.rollback()

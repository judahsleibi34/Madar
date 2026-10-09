"""Current-local read-only reconciliation and governed retained writer fence.

No migration, ledger repair, table/role mutation or checkpoint restoration.
Customer rows/credentials never leave PostgreSQL: only counts and SHA-256 roots
are emitted. All table roots in a packet share one read-only repeatable snapshot.
"""
from datetime import datetime,timezone
import json
import re
from pathlib import Path
from deployment.lib.emergency_routing_repair import exclusive,encoded,spec
from deployment.lib.provider_recovery_runtime import protected,digest

DB='supabase-db'

def identifier(value):
    if not isinstance(value,str) or not value or '\x00' in value:
        raise RuntimeError('reconciliation_identifier_invalid')
    return '"'+value.replace('"','""')+'"'

CATALOG="""SELECT json_build_object('schema',n.nspname,'table',c.relname)::text
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind IN ('r','p') ORDER BY n.nspname,c.relname;"""

class CurrentLocalReconciliation:
    def __init__(self,plan,root,candidate,source_guard,registered_runtime_verifier):
        if not callable(source_guard) or not callable(registered_runtime_verifier):
            raise RuntimeError('reconciliation_independent_guards_required')
        self.plan,self.root,self.candidate=plan,Path(root),candidate
        self.source_guard,self.registered_runtime_verifier=source_guard,registered_runtime_verifier
    def query(self,body):
        # Every command is explicitly read-only even though the connection uses
        # the already installed postgres operator. Results contain hashes/counts
        # or fixed catalog identifiers, never customer fields or secret values.
        sql="BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL statement_timeout='60s'; SET LOCAL TIME ZONE 'UTC';\n"+body+"\nCOMMIT;"
        text=self.candidate.command(['docker','exec',DB,'psql','--username','postgres','--dbname','postgres',
            '--no-psqlrc','--quiet','--tuples-only','--no-align','--set','ON_ERROR_STOP=1','--command',sql])
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    def snapshot(self):
        self.source_guard();self.registered_runtime_verifier()
        tables=self.query(CATALOG)
        if not tables or any(set(row)!={'schema','table'} or row['schema']!='public' for row in tables):
            raise RuntimeError('reconciliation_catalog_invalid')
        statements=[]
        for row in tables:
            table=identifier(row['schema'])+'.'+identifier(row['table'])
            name=json.dumps(row['table']).replace("'","''")
            statements.append("SELECT json_build_object('table',"+"'"+name+"'::json,'count',count(*),'sha256',"
                "encode(sha256(convert_to(coalesce(string_agg(row_sha,'' ORDER BY row_sha COLLATE \"C\"),''),'UTF8')),'hex'))::text "
                "FROM (SELECT encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') AS row_sha FROM "+table+" t) rows;")
        # The application schema is observed inside the SAME snapshot.
        statements.append("SELECT json_build_object('schema',schema_version)::text FROM public.application_schema_state WHERE contract_key='core';")
        results=self.query('\n'.join(statements))
        if (len(results)!=len(tables)+1 or results[-1]!={'schema':115}
                or any(row.get('table')!=table['table'] or type(row.get('count')) is not int or row['count']<0
                    or not isinstance(row.get('sha256'),str) or not re.fullmatch(r'[0-9a-f]{64}',row['sha256']) for row,table in zip(results[:-1],tables))):
            raise RuntimeError('reconciliation_snapshot_invalid')
        if self.query(CATALOG)!=tables:raise RuntimeError('reconciliation_catalog_changed')
        self.registered_runtime_verifier();self.source_guard()
        packet={'version':1,'operation':'current-local-read-only-reconciliation','schema':115,
            'migration_executed':False,'customer_data_modified':False,'database_restore_performed':False,
            'table_roots':results[:-1]}
        return packet,digest(packet)
    def fence_retained_hosted_writers(self):
        # This production effect is usable only through the freshly approved
        # controller-resumed continuation after sustained read-only publication.
        from deployment.lib.active_recovery_resumption import ROOT
        import os
        self.source_guard()
        receipt=json.loads(protected(self.root/'authorization.json',private=True).read_text())
        events=[json.loads(line) for line in protected(self.root/'events.jsonl',private=True).read_text().splitlines()]
        if (os.geteuid()!=0 or self.root!=ROOT/self.plan.digest
                or receipt.get('operation')!='active-local-rollback-resumption'
                or receipt.get('plan_sha256')!=self.plan.digest
                or receipt.get('source_bundle_sha256')!=self.plan.source_bundle_sha256
                or not events or events[-1].get('phase')!='controller_resume_pending'
                or any(row.get('plan_sha256')!=self.plan.digest for row in events)
                or 'read_only_serving' not in [row.get('phase') for row in events]):
            raise RuntimeError('reconciliation_writer_fence_denied')
        self.candidate.require_write_authority(self.candidate.contract,'READ_ONLY')
        dependencies=json.loads(protected(self.root/'runtime-dependencies.json',private=True).read_text())
        if digest(dependencies)!=self.plan.retained_inputs['runtime_dependencies']:
            raise RuntimeError('reconciliation_retained_binding_changed')
        selected={}
        slot=self.plan.candidate_destination['retained_slot']
        for role in ('backend','frontend'):
            name=f'madar-{slot}-{role}';expected=dependencies['runtimes'][name];row=self.candidate.inspect(expected['container_id'])
            if row['Image']!=expected['image_id'] or spec(row)!=expected['spec_sha256']:
                raise RuntimeError('reconciliation_retained_writer_changed')
            selected[role]=row['Id']
        exclusive(self.root/'retained-writer-fence.json',encoded({'version':1,'plan_sha256':self.plan.digest,
            'began_at':datetime.now(timezone.utc).isoformat(),'retained_container_ids':selected,'database_restore':False}))
        for identity in selected.values():
            self.candidate.command(['docker','update','--restart=no',identity])
            self.candidate.command(['docker','stop',identity])
        for identity in selected.values():
            row=self.candidate.inspect(identity)
            if row['State']['Running'] or row['HostConfig']['RestartPolicy']['Name']!='no':
                raise RuntimeError('reconciliation_retained_writer_fence_failed')
        self.source_guard()

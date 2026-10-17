#!/usr/bin/env python3
"""Explicit synthetic-VM upgrade; never a production migration controller."""
import hashlib
import importlib.util
import json
import secrets

import manage
from restore import write_binary


PRESERVATION_SQL = """
begin;
create temporary table notification_upgrade_preservation(name text,rows bigint,digest text);
do $$ declare relation record; amount bigint; fingerprint text; row_expression text; begin
 for relation in select schemaname,tablename from pg_catalog.pg_tables
   where schemaname in ('public','auth','storage')
     and not (schemaname='public' and tablename='application_schema_state')
   order by schemaname,tablename loop
   row_expression:=case when {exclude_generation} and relation.schemaname='public' and relation.tablename='notification_deliveries'
     then 'to_jsonb(t)-''claim_generation''' else 'to_jsonb(t)' end;
   execute format('select count(*),encode(extensions.digest(coalesce(jsonb_agg(%s order by (%s)::text)::text,''[]''),''sha256''),''hex'') from %I.%I t',
     row_expression,row_expression,relation.schemaname,relation.tablename) into amount,fingerprint;
   insert into notification_upgrade_preservation values(relation.schemaname||'.'||relation.tablename,amount,fingerprint);
 end loop;
end $$;
select json_build_object(
 'tables',(select json_object_agg(name,json_build_object('rows',rows,'sha256',digest) order by name) from notification_upgrade_preservation),
 'sequences',(select json_object_agg(schemaname||'.'||sequencename,last_value order by schemaname,sequencename)
              from pg_catalog.pg_sequences where schemaname in ('public','auth','storage')));
rollback;
"""


def entries(module):
    path=manage.REPOSITORY/'web/scripts'/f'{module}.py'
    spec=importlib.util.spec_from_file_location(module,path)
    candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
    return candidate.validated_entries(manage.REPOSITORY)


def main():
    manage.require_staging_host()
    manage.require_database_marker()
    manage.attest_resources()
    migrations=entries('notification_fencing_candidate')+entries('reservation_integrity_candidate')
    observed=int(manage.sql("select schema_version from public.application_schema_state where contract_key='core';"))
    if observed not in (146,147,148):
        raise RuntimeError('Synthetic notification upgrade accepts only146/147/148')
    starting_schema=observed
    if observed==148:
        receipt=manage.RUNTIME/'notification-upgrade.json'
        if receipt.exists() and not json.loads(receipt.read_text()).get('preservation_verified'):
            raise RuntimeError('Synthetic148 upgrade preservation remains unverified; diagnose before admission')
        print('Synthetic schema148 already present; no SQL replay or worker activation')
        return
    services=('notification-worker','frontend','backend','gateway','auth','storage')
    running=[]
    for service in services:
        identifier=manage.compose('ps','-q',service).decode().strip()
        resource=json.loads(manage.docker('inspect',identifier))[0] if identifier else {}
        if resource.get('State',{}).get('Running',False):running.append(service)
    if running:
        manage.compose('stop','--timeout','30',*running)
    try:
        if manage.sql("select count(*) from public.notification_deliveries where status='processing';")!='0':
            raise RuntimeError('Reconcile synthetic processing deliveries before this upgrade; no automatic requeue')
        preservation_sql=PRESERVATION_SQL.format(exclude_generation='true' if starting_schema==146 else 'false')
        before=json.loads(manage.sql(preservation_sql))
        archive=manage.docker('exec',manage.database_container(),'pg_dump','-U','postgres','-d','madar_hardening','-Fc')
        name=f'before-notification-upgrade-{secrets.token_hex(8)}.dump'
        write_binary(manage.RUNTIME/name,archive)
        backup_hash=hashlib.sha256(archive).hexdigest()
        for entry in migrations:
            if observed==entry['from_schema']:
                manage.sql((manage.REPOSITORY/entry['path']).read_text())
                observed=int(manage.sql("select schema_version from public.application_schema_state where contract_key='core';"))
                if observed!=entry['to_schema']:
                    raise RuntimeError('Synthetic migration checkpoint mismatch')
                manage.private_write('notification-upgrade.json',json.dumps({
                    'schema':observed,'backup_sha256':backup_hash,'backup':name,
                    'migration_sha256':entry['sha256'],'scope':'owned synthetic staging only'})+'\n')
        if observed!=148:
            raise RuntimeError('Synthetic schema148 target not reached')
        after=json.loads(manage.sql(preservation_sql))
        if before!=after:
            raise RuntimeError('Synthetic original-row/Auth/MFA/Storage preservation mismatch; retain backup and repair forward')
        manage.private_write('notification-upgrade.json',json.dumps({
            'from_schema':starting_schema,'schema':observed,
            'backup_sha256':backup_hash,'backup':name,'scope':'owned synthetic staging only',
            'preservation_verified':True,'preserved_tables':len(before['tables']),
            'preserved_sequences':len(before['sequences'])})+'\n')
        print('PASS owned synthetic146/147→148 checkpointed upgrade; original rows/Auth/MFA/Storage/sequences preserved; private backup retained; writers remain stopped until new image admission')
    except BaseException:
        # Only an unchanged146 transaction can restore the old protocol1 worker.
        # Never roll back worker code after the durable147 protocol cutover.
        current=manage.sql("select schema_version from public.application_schema_state where contract_key='core';")
        if current=='146' and running:
            manage.compose('start','--wait','--wait-timeout','60',*reversed(running))
        raise


if __name__=='__main__':
    main()

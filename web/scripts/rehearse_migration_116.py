#!/usr/bin/env python3
"""Replay migrations and catalog regressions in a disposable networkless PostgreSQL.
No production URLs, credentials, volumes or data are used.
"""
from pathlib import Path
import subprocess
import json
import time
import uuid
from rehearse_migration_101 import BOOTSTRAP

WEB = Path(__file__).resolve().parents[1]

def main():
    name = 'madar-116-rehearsal-' + uuid.uuid4().hex[:12]
    def command(args, payload=None):
        result = subprocess.run(args, input=payload, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        return result.stdout
    def sql(payload):
        return command(['docker','exec','-e','PGOPTIONS=-c client_min_messages=warning','-i',name,'psql','-X','-U','postgres','-v','ON_ERROR_STOP=1','-qAt'],payload)
    command(['docker','run','-d','--name',name,'--network','none','--tmpfs','/var/lib/postgresql/data:rw,noexec,nosuid,size=1g','-e','POSTGRES_HOST_AUTH_METHOD=trust','postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73'])
    try:
        for _ in range(30):
            if subprocess.run(['docker','exec',name,'pg_isready','-U','postgres'],capture_output=True).returncode == 0: break
            time.sleep(1)
        sql('create role anon nologin;create role authenticated nologin;create role service_role nologin;'+BOOTSTRAP)
        for migration in sorted((WEB/'database/migrations').glob('*.sql')):
            if migration.name.startswith('116'):
                sql((WEB/'database/verification/116_preservation_seed.sql').read_text())
                tables=['ecommerce_products','ecommerce_product_attributes','ecommerce_product_options','ecommerce_product_option_values','ecommerce_product_variants','ecommerce_variant_option_values','ecommerce_product_tags','ecommerce_orders','ecommerce_order_items','ecommerce_inventory_movements','builder_assets','builder_asset_references','ecommerce_brands','ecommerce_product_categories','tenant_commercial_state','commercial_access_periods','commercial_access_events','notification_outbox','notification_events','notification_deliveries','commercial_manual_payments','tenant_commercial_holds','commercial_price_books']
                def snapshot(table):
                    return json.loads(sql("select coalesce(jsonb_agg(to_jsonb(t) order by to_jsonb(t)::text),'[]') from public."+table+' t;'))
                tables=[table for table in tables if sql("select to_regclass('public."+table+"') is not null;").strip()=='t']
                before={table:snapshot(table) for table in tables}
                checkout_before=sql("select pg_get_functiondef('public.create_ecommerce_order_safe(jsonb,text,text,text,integer)'::regprocedure);")
                assert all(before[table] for table in ('ecommerce_order_items','ecommerce_inventory_movements','ecommerce_brands','ecommerce_product_categories','builder_assets','notification_events'))
                sql("insert into ecommerce_product_option_values(tenant_id,product_id,option_id,code,value_translations,normalized_value,active) values (1071,'10710000-0000-4000-8000-000000000002','10710000-0000-4000-8000-000000000003','ambiguous-a','{\"en\":\"Case\"}','case',false),(1071,'10710000-0000-4000-8000-000000000002','10710000-0000-4000-8000-000000000003','ambiguous-b','{\"en\":\"Case\"}','CASE',false);")
                try:
                    sql(migration.read_text())
                except RuntimeError as error:
                    assert 'migration_116_ambiguous_value_history' in str(error)
                else:
                    raise AssertionError('ambiguous_history_was_not_refused')
                assert sql("select schema_version from application_schema_state where contract_key='core';").strip()=='115'
                assert sql("select count(*) from information_schema.columns where table_schema='public' and table_name='ecommerce_product_options' and column_name='active';").strip()=='0'
                sql("delete from ecommerce_product_option_values where tenant_id=1071 and code in ('ambiguous-a','ambiguous-b');")
                print('AMBIGUOUS_HISTORY_PREFLIGHT_ROLLBACK PASS')
            started=time.perf_counter()
            try: sql(migration.read_text())
            except RuntimeError as error: raise RuntimeError('failed_migration:'+migration.name+'\n'+str(error)) from error
            if migration.name.startswith('116'):
                print(f'Migration 116: {time.perf_counter()-started:.3f}s')
                for table in tables:
                    after=snapshot(table)
                    if table=='ecommerce_product_options':
                        by_id={row['id']:row for row in before[table]}
                        for row in after:
                            expected=row['id']=='10710000-0000-4000-8000-000000000012'
                            assert row.pop('active') is (not expected), 'historical_option_membership'
                            if expected:row['updated_at']=by_id[row['id']]['updated_at']
                    assert after==before[table], 'migration_preservation_failed:'+table
                checkout_after=sql("select pg_get_functiondef('public.create_ecommerce_order_safe(jsonb,text,text,text,integer)'::regprocedure);")
                assert checkout_after==checkout_before.replace('public.ecommerce_product_options','public.ecommerce_current_product_options')
                print('115_TO_116_HISTORY_AND_CHECKOUT_PRESERVATION PASS')
        assert sql("select schema_version from application_schema_state where contract_key='core';").strip()=='116'
        print('FRESH_001_TO_116_REPLAY PASS')
        print(sql((WEB/'database/verification/116_catalog_reconciliation.sql').read_text()))
    finally:
        command(['docker','rm','-f',name])

if __name__=='__main__': main()

#!/usr/bin/env python3
"""Disposable PostgreSQL 17 fresh replay and production-lineage 099->101 proof."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

WEB = Path(__file__).resolve().parents[1]
IMAGE = 'postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73'
BOOTSTRAP = '''
create schema auth;
create table auth.users(id uuid primary key,email_confirmed_at timestamptz,confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$select null::uuid$$;
create schema storage;
create table storage.buckets(id text primary key,name text not null,public boolean not null default false,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text);
alter table storage.objects enable row level security;
create schema extensions; create extension pgcrypto schema extensions;
'''

def main() -> None:
    name = 'madar-forward-101-rehearsal-' + uuid.uuid4().hex[:12]
    created = False
    def command(args: list[str], payload: str | None = None) -> str:
        result = subprocess.run(args, input=payload, text=True, encoding="utf-8", capture_output=True)
        if result.returncode:
            error_file = WEB.parent / '.runtime/rehearsal-error.log'
            error_file.parent.mkdir(exist_ok=True)
            error_file.write_text(result.stderr)
            raise RuntimeError('disposable_rehearsal_command_failed:' + args[0])
        return result.stdout
    def sql(text: str, db: str = 'postgres') -> str:
        return command(['docker','exec','-e','PGOPTIONS=-c client_min_messages=warning','-i',name,'psql','-X','-U','postgres','-d',db,'-v','ON_ERROR_STOP=1','-q','-A','-t'],text)
    def schema(db: str = 'postgres') -> int:
        return int(sql("select schema_version from public.application_schema_state where contract_key='core';",db).strip())
    try:
        command(['docker','run','--detach','--name',name,'--label','madar.rehearsal=forward-only-101','--network','none','--tmpfs','/var/lib/postgresql/data:rw,noexec,nosuid,size=1g','--env','POSTGRES_HOST_AUTH_METHOD=trust',IMAGE]);created=True
        for _ in range(60):
            if subprocess.run(['docker','exec',name,'pg_isready','-U','postgres'],capture_output=True).returncode==0:break
            time.sleep(1)
        else:raise RuntimeError('disposable_postgres_not_ready')
        sql('create role anon nologin; create role authenticated nologin; create role service_role nologin;'+BOOTSTRAP)
        migrations=sorted((WEB/'database/migrations').glob('*.sql'))
        for path in migrations:
            if int(path.name[:3])<=99:
                try: sql(path.read_text(encoding='utf-8'))
                except RuntimeError as error: raise RuntimeError('failed_migration:' + path.name) from error
        assert schema()==99
        sql((WEB/'database/verification/101_preservation_seed.sql').read_text(encoding='utf-8'))
        tables=['ecommerce_products','ecommerce_product_attributes','ecommerce_product_options','ecommerce_product_option_values','ecommerce_product_variants','ecommerce_variant_option_values','ecommerce_orders','ecommerce_order_items','ecommerce_inventory_movements','site_visit_counters','tenant_commercial_state','commercial_manual_payments','commercial_access_periods','commercial_access_events','audit_logs']
        def snapshot(table: str) -> list:
            return json.loads(sql("select coalesce(jsonb_agg(to_jsonb(t) order by to_jsonb(t)::text),'[]') from public."+table+' t;'))
        before={t:snapshot(t) for t in tables}
        functions=['resolve_commercial_access(integer)','apply_commercial_access_command(integer,integer,text,text,text,text,jsonb)']
        commercial_before={f:sql("select pg_get_functiondef('public."+f+"'::regprocedure);") for f in functions}
        assert all(before[t] for t in ['ecommerce_product_variants','ecommerce_order_items','ecommerce_inventory_movements','commercial_manual_payments','commercial_access_periods','commercial_access_events'])
        # A custom-format source-schema backup and disposable restore bind the proof to schema 099.
        command(['docker','exec',name,'pg_dump','-U','postgres','--format=custom','--file=/tmp/source-099.dump','postgres'])
        assert command(['docker','exec',name,'pg_restore','--list','/tmp/source-099.dump'])
        command(['docker','exec',name,'createdb','-U','postgres','production_like_099'])
        command(['docker','exec',name,'pg_restore','-U','postgres','--exit-on-error','--dbname=production_like_099','/tmp/source-099.dump'])
        db='production_like_099';assert schema(db)==99
        for number in (100,101):
            path=next(p for p in migrations if int(p.name[:3])==number);sql(path.read_text(encoding='utf-8'),db);assert schema(db)==number
        for table in tables:
            after=json.loads(sql("select coalesce(jsonb_agg(to_jsonb(t) order by to_jsonb(t)::text),'[]') from public."+table+' t;',db))
            if table=='ecommerce_product_options':after=[{k:v for k,v in row.items() if k!='display_type'} for row in after]
            if table=='ecommerce_product_option_values':after=[{k:v for k,v in row.items() if k!='color_hex'} for row in after]
            assert after==before[table], 'data_preservation_failed:'+table
        for f in functions:assert sql("select pg_get_functiondef('public."+f+"'::regprocedure);",db)==commercial_before[f]
        sql((WEB/'database/verification/101_preservation_assertions.sql').read_text(encoding='utf-8'),db)
        print('099_TO_101_REHEARSAL PASS; counters, product/variant/order/inventory data and commercial objects preserved',flush=True)
        command(['docker','exec',name,'createdb','-U','postgres','fresh_101']);sql(BOOTSTRAP,'fresh_101')
        for path in migrations:sql(path.read_text(encoding='utf-8'),'fresh_101')
        assert schema('fresh_101')==101
        print('FRESH_001_TO_101_REPLAY PASS',flush=True)
    finally:
        if created:command(['docker','rm','--force',name])

if __name__=='__main__':main()

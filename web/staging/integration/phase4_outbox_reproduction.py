#!/usr/bin/env python3
"""Reproduce unfenced resolver ownership on a fully migrated synthetic database.

This is an adversarial reproduction, not a successful ownership acceptance test.
It creates one network-isolated, resource-bounded staging container, applies the
immutable source migrations through148, and removes only that exact owned ID.
No retained application database, provider or worker is contacted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
IMAGE = "postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73"
OWNER = "architecture-phase4-20261017"
LABEL = "madar.phase4.owner"


def run(*arguments: str, body: str | None = None) -> str:
    result = subprocess.run(arguments, input=body, text=True, capture_output=True,
                            timeout=90, check=False)
    if result.returncode:
        raise RuntimeError(f"Reproduction command failed ({arguments[0]}): {result.stderr[-2000:]}")
    return result.stdout.strip()


def rehearse() -> dict:
    if socket.gethostname() != "madar-staging":
        raise RuntimeError("Only the dedicated staging host is accepted")
    available_kib = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                             if line.startswith('MemAvailable:')))
    if available_kib < 768 * 1024 or shutil.disk_usage('/').free < 1024**3:
        raise RuntimeError("Insufficient safe staging resource headroom")
    name = "phase4-outbox-repro-20261017-" + uuid4().hex[:10]
    identifier = run('sudo', '-n', 'docker', 'create', '--name', name,
                     '--label', f'{LABEL}={OWNER}', '--network', 'none',
                     '--memory', '256m', '--cpus', '0.5', '--pids-limit', '128',
                     '--tmpfs', '/var/lib/postgresql/data:rw,noexec,nosuid,size=512m',
                     '--env', 'POSTGRES_HOST_AUTH_METHOD=trust', IMAGE)

    def sql(body: str) -> str:
        return run('sudo', '-n', 'docker', 'exec', '-i',
                   '--env', 'PGOPTIONS=-c client_min_messages=warning', identifier,
                   'psql', '-X', '-U', 'postgres', '-v', 'ON_ERROR_STOP=1', '-qAt', body=body)

    def row(outbox_id: str) -> dict:
        return json.loads(sql(f"select to_jsonb(o) from public.notification_outbox o where id='{outbox_id}'"))

    def fresh(*, max_attempts: int = 5) -> str:
        value = str(uuid4())
        sql(f"insert into public.notification_outbox(id,channel,template,max_attempts) "
            f"values('{value}','email','synthetic',{max_attempts})")
        return value

    def reclaim(outbox_id: str) -> tuple[dict, dict]:
        sql('set role service_role; select public.claim_notification_outbox(1,clock_timestamp())')
        old = row(outbox_id)
        sql(f"update public.notification_outbox set processing_started_at=clock_timestamp()-interval '16 minutes' where id='{outbox_id}'")
        sql('set role service_role; select public.claim_notification_outbox(1,clock_timestamp())')
        new = row(outbox_id)
        assert (old['attempts'], new['attempts'], new['status']) == (1, 2, 'processing')
        return old, new

    started = time.monotonic()
    try:
        run('sudo', '-n', 'docker', 'start', identifier)
        for _ in range(60):
            ready = subprocess.run(['sudo', '-n', 'docker', 'exec', identifier,
                                    'pg_isready', '-U', 'postgres'], capture_output=True,
                                   timeout=5, check=False)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Disposable database did not start')
        sql("""create role anon nologin;
create role authenticated nologin;
create role service_role nologin;
create schema auth;
create table auth.users(id uuid primary key,email_confirmed_at timestamptz,confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$ select null::uuid $$;
create schema storage;
create table storage.buckets(id text primary key,name text not null,public boolean not null default false,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text references storage.buckets(id),name text);
alter table storage.objects enable row level security;
create schema extensions;
create extension pgcrypto schema extensions;
comment on database postgres is 'madar-phase4-outbox-synthetic';""")
        migrations = sorted((ROOT / 'web/database/migrations').glob('*.sql'))
        applied = []
        for migration in migrations:
            number = int(migration.name.split('_', 1)[0])
            if number > 148 or number == 142:
                continue
            if number == 115:
                sql('alter table auth.users add column email text')
            sql(migration.read_text())
            applied.append(migration.name)
        assert sql("select schema_version from public.application_schema_state where contract_key='core'") == '148'
        assert sql("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()") == 'madar-phase4-outbox-synthetic'
        cases = []
        for outcome, success, attempts in [('sent', True, 5), ('failed', False, 5), ('dead', False, 2)]:
            outbox_id = fresh(max_attempts=attempts)
            _, successor = reclaim(outbox_id)
            sql(f"set role service_role; select public.finish_notification_outbox('{outbox_id}',{str(success).lower()},'synthetic_failure')")
            result = row(outbox_id)
            assert result['status'] == outcome
            assert result['processing_started_at'] is None
            assert result['attempts'] == successor['attempts'] == 2
            cases.append({'scenario': f'superseded_finish_{outcome}', 'ownership_invariant': 'FAIL',
                          'successor_attempts': 2, 'stale_mutation_accepted': True,
                          'result_status': result['status'], 'successor_lease_cleared': True})
            sql(f"delete from public.notification_outbox where id='{outbox_id}'")
        outbox_id = fresh()
        reclaim(outbox_id)
        count = int(sql(f"set role service_role; select public.resolve_notification_outbox_v2('{outbox_id}',clock_timestamp(),false,false)"))
        result = row(outbox_id)
        assert (count, result['status']) == (0, 'sent')
        cases.append({'scenario': 'superseded_resolver_disabled_channel', 'ownership_invariant': 'FAIL',
                      'successor_attempts': 2, 'stale_mutation_accepted': True,
                      'result_status': result['status'], 'materialized_deliveries': count})
        expired_id = fresh()
        sql('set role service_role; select public.claim_notification_outbox(1,clock_timestamp())')
        sql(f"update public.notification_outbox set processing_started_at=clock_timestamp()-interval '16 minutes' where id='{expired_id}'")
        sql(f"set role service_role; select public.finish_notification_outbox('{expired_id}',true)")
        assert row(expired_id)['status'] == 'sent'
        cases.append({'scenario': 'expired_unreclaimed_finish', 'ownership_invariant': 'FAIL',
                      'stale_mutation_accepted': True, 'result_status': 'sent'})
        return {'mode': 'REPRODUCE', 'fixture': 'synthetic-independent-postgresql',
                'schema': 148, 'source_migrations_applied': len(applied),
                'migration147_sha256': hashlib.sha256((ROOT/'web/database/migrations/147_fence_notification_delivery_claims.sql').read_bytes()).hexdigest(),
                'migration148_sha256': hashlib.sha256((ROOT/'web/database/migrations/148_guard_reservation_reactivation_capacity.sql').read_bytes()).hexdigest(),
                'cases': cases, 'elapsed_seconds': round(time.monotonic()-started, 3),
                'external_provider_requests': 0, 'retained_stack_mutations': 0,
                'production_authorized': False}
    finally:
        actual = json.loads(run('sudo', '-n', 'docker', 'inspect', identifier))[0]
        if (actual['Id'] != identifier or actual['Config']['Labels'].get(LABEL) != OWNER
                or actual['Name'] != '/'+name or actual['HostConfig']['NetworkMode'] != 'none'):
            raise RuntimeError('Refusing cleanup: disposable ownership changed')
        run('sudo', '-n', 'docker', 'rm', '-f', identifier)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['INSPECT', 'REPRODUCE'], default='INSPECT')
    options = parser.parse_args()
    if options.mode == 'INSPECT':
        print(json.dumps({'mode': 'INSPECT', 'mutates_retained_resources': False,
                          'execution_requires': '--mode REPRODUCE on madar-staging',
                          'schema_target': 148, 'production_authorized': False}, indent=2))
    else:
        print(json.dumps(rehearse(), indent=2))

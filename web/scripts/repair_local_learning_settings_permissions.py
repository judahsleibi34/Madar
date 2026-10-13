"""Repair the schema139 helper ACL on the existing local141/preview144 databases.

No migration, schema-version update, row change, or production target is allowed.
The grant enables only a verified immutable JSON normalizer, not its trigger.
"""
import argparse
import json
import os
import subprocess
import re
from pathlib import Path
from urllib.parse import urlsplit
import psycopg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
FUNCTION = 'public.normalize_academy_programme_settings(jsonb)'


def repair(target='application', apply=False):
    preview = target == 'preview'
    cfg = ROOT / ('web/.eduhope-preview.local/backend.env' if preview else 'web/.env.database.local')
    values = dotenv_values(cfg)
    uri = urlsplit(values.get('SUPABASE_DB_URL', ''))
    expected_db = 'madar_eduhope_preview_144' if preview else 'postgres'
    expected_schema = 144 if preview else 141
    if values.get('APP_ENV') != 'development' or uri.hostname not in {'127.0.0.1', 'localhost', '::1'} or uri.port != 54322 or uri.path != '/' + expected_db:
        raise RuntimeError('Expected the existing loopback local development database')
    # A loopback address may be an SSH tunnel. Verify the PostgreSQL cluster
    # against the actual labelled local Supabase container before any DB write.
    if os.getenv('DOCKER_HOST') and not os.environ['DOCKER_HOST'].startswith('unix://'):
        raise RuntimeError('A local Docker socket is required')
    endpoint = subprocess.check_output(['docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}'], text=True).strip()
    if not endpoint.startswith('unix://'):
        raise RuntimeError('Refusing a remote Docker context')
    container = json.loads(subprocess.check_output(['docker', 'inspect', 'supabase_db_web'], text=True))[0]
    labels = container['Config'].get('Labels', {})
    if labels.get('com.supabase.cli.project') != 'web' or labels.get('com.supabase.cli.workdir') != str(ROOT / 'web'):
        raise RuntimeError('Local Supabase identity does not match this workspace')
    cluster = subprocess.check_output(['docker', 'exec', 'supabase_db_web', 'psql', '-U', 'postgres', '-d', 'postgres', '-Atc', 'select system_identifier from pg_control_system()'], text=True).strip()
    original = (ROOT / 'web/database/migrations/139_generalize_academy_programme_configuration.sql').read_text()
    match = re.search(r'create function public\.normalize_academy_programme_settings\(cfg jsonb\).*?as \$\$(.*?)\$\$;', original, re.S)
    if not match:
        raise RuntimeError('Cannot verify the immutable source function')
    with psycopg.connect(values['SUPABASE_DB_URL']) as db:
        if str(db.execute('select system_identifier from pg_control_system()').fetchone()[0]) != cluster:
            raise RuntimeError('Connection is not the local Supabase cluster; no repair applied')
        db.execute("select pg_advisory_xact_lock(hashtext('madar-local-learning-settings-acl'))")
        if db.execute("select current_database()").fetchone()[0] != expected_db:
            raise RuntimeError('Database identity changed')
        version = db.execute("select schema_version from public.application_schema_state where contract_key='core' for update").fetchone()[0]
        if version != expected_schema:
            raise RuntimeError('Unexpected local schema; no repair applied')
        if preview and db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()").fetchone()[0] != 'madar-eduhope-local-preview-v1':
            raise RuntimeError('Preview database marker does not match')
        source, volatility, definer = db.execute('select prosrc,provolatile,prosecdef from pg_proc where oid=%s::regprocedure', (FUNCTION,)).fetchone()
        if source != match.group(1) or volatility != 'i' or definer:
            raise RuntimeError('Function differs from the immutable, invoker-only JSON normalizer')
        for role in ('anon', 'authenticated'):
            if db.execute('select has_function_privilege(%s,%s,\'EXECUTE\')', (role, FUNCTION)).fetchone()[0]:
                raise RuntimeError('Unexpected public helper access; no repair applied')
        before = db.execute("select has_function_privilege('service_role',%s,'EXECUTE')", (FUNCTION,)).fetchone()[0]
        db.execute('grant execute on function public.normalize_academy_programme_settings(jsonb) to service_role')
        # Rehearse the exact service-role writer inside a rolled-back savepoint.
        row = db.execute('select tenant_id,settings from public.elearning_settings order by tenant_id limit 1').fetchone()
        db.execute('savepoint writer_check')
        db.execute('set local role service_role')
        if row:
            db.execute('select public.save_elearning_settings(%s,%s::jsonb)', (row[0], psycopg.types.json.Jsonb(row[1])))
        else:
            db.execute('select public.normalize_academy_programme_settings(%s::jsonb)', (psycopg.types.json.Jsonb({}),))
        db.execute('rollback to savepoint writer_check')
        db.execute('release savepoint writer_check')
        if db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0] != expected_schema:
            raise RuntimeError('Schema version changed during validation')
        if not apply:
            db.rollback()
        print(f'{target}: service-role Settings writer passed; schema{expected_schema}; ' + ('permission already present' if before else 'permission repaired' if apply else 'grant rehearsed and rolled back'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=['application','preview'], default='application')
    parser.add_argument('--apply', action='store_true', help='Commit only the verified local helper EXECUTE grant')
    args = parser.parse_args()
    repair(args.target, args.apply)

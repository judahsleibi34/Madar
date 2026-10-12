#!/usr/bin/env python3
"""Create an isolated, persistent local academy preview. Never copy user data.

The current application database is a schema-only source. Learning143 is applied
only to a new explicitly marked database via the pinned locked executor and a
verified141 dump. Private config and storage survive preview service restarts.
"""
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

import psycopg
from psycopg import sql
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / 'web'
DB_NAME = 'madar_eduhope_preview_143'
MARKER = 'madar-eduhope-local-preview-v1'
FOLDER = Path('/tmp/madar-eduhope-preview')
LABEL = 'madar.preview=eduhope'


def docker(*args, **kwargs):
    return subprocess.run(['docker', *args], check=True, stdout=subprocess.PIPE, **kwargs).stdout


def inspect(name):
    return json.loads(docker('inspect', name))[0]


def private_file(path, content):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        handle.write(content)
    path.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create', action='store_true', help='Explicitly create the isolated local preview')
    args = parser.parse_args()
    if not args.create:
        print('Dry-run: create marked madar_eduhope_preview_143 with schema141 backup then pinned143; localhost5180/8010; original app untouched.')
        return
    if os.getenv('APP_ENV', '').lower() in {'production', 'prod', 'staging'}:
        raise RuntimeError('Refusing production environment')
    endpoint = json.loads(docker('context', 'inspect'))[0]['Endpoints']['docker']['Host']
    if not endpoint.startswith('unix://') or (os.getenv('DOCKER_HOST') and not os.environ['DOCKER_HOST'].startswith('unix://')):
        raise RuntimeError('Local Docker socket required')
    values = dotenv_values(WEB / '.env.database.local')
    dsn = values['SUPABASE_DB_URL']; url = urlsplit(dsn)
    if url.hostname not in {'localhost', '127.0.0.1'} or url.port != 54322 or url.path != '/postgres':
        raise RuntimeError('Expected loopback local database54322')
    originals = {name:inspect('supabase_'+name+'_web') for name in ['auth','rest','storage','kong','db']}
    for name in ['auth','rest','storage','kong']:
        existing = subprocess.run(['docker','inspect','madar-eduhope-'+name],capture_output=True)
        if existing.returncode == 0:
            raise RuntimeError('Preview service already exists; use existing workspace instead of recreating it')
    subprocess.run(['/usr/bin/python3','-c','import yaml'],check=True)
    sys.path.insert(0,str(WEB))
    from deployment.lib.migration_executor import MigrationManifest,LockedMigrationExecutor
    manifest=MigrationManifest.load(WEB/'deployment/releases/migrations-141-143-learning.json',ROOT)
    assert [entry.number for entry in manifest.migrations]==[143] and manifest.excluded_schemas==(142,)
    FOLDER.mkdir(mode=0o700,exist_ok=True); FOLDER.chmod(0o700)
    with psycopg.connect(dsn,autocommit=True) as source:
        if source.execute('select 1 from pg_database where datname=%s',(DB_NAME,)).fetchone():
            raise RuntimeError('Preview database already exists; no records were changed')
        current = source.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]
        if current != 141:
            raise RuntimeError('Schema-only source must be141')
        source.execute(sql.SQL('create database {} template template0').format(sql.Identifier(DB_NAME)))
        source.execute(sql.SQL('comment on database {} is {}').format(sql.Identifier(DB_NAME),sql.Literal(MARKER)))
    preview_dsn = psycopg.conninfo.make_conninfo(dsn,dbname=DB_NAME)
    ddl = docker('exec','supabase_db_web','pg_dump','-U','postgres','--schema-only','--no-owner','--no-privileges','-n','auth','-n','storage','postgres').decode()
    ddl = re.sub(r'^\\.*$', '', ddl, flags=re.M)
    ddl = re.sub(r'CREATE POLICY .*?;', '', ddl, flags=re.S)
    with psycopg.connect(preview_dsn,autocommit=True) as db:
        db.execute('set client_min_messages=warning')
        db.execute('create schema extensions; create extension pgcrypto schema extensions; create extension pg_trgm schema extensions;')
        db.execute(ddl)
        for namespace,role in [('auth','supabase_auth_admin'),('storage','supabase_storage_admin')]:
            db.execute(sql.SQL('grant usage on schema {} to {}; grant all on all tables in schema {} to {}; grant all on all sequences in schema {} to {}; grant execute on all functions in schema {} to {}').format(*[sql.Identifier(item) for item in [namespace,role]*4]))
        with psycopg.connect(dsn) as source:
            source.execute('set transaction read only')
            for table in ['auth.schema_migrations','storage.migrations']:
                rows=source.execute('select * from '+table);columns=[column.name for column in rows.description];data=rows.fetchall()
                if data:
                    statement=sql.SQL('insert into {} ({}) values ({})').format(sql.Identifier(*table.split('.')),sql.SQL(',').join(map(sql.Identifier,columns)),sql.SQL(',').join(sql.Placeholder()*len(columns)))
                    db.cursor().executemany(statement,data)
        db.execute('set search_path=public,extensions')
        for path in sorted((WEB/'database/migrations').glob('*.sql')):
            if int(path.name.split('_')[0]) <= 141:
                db.execute(path.read_text())
        db.execute(sql.SQL('grant connect on database {} to authenticator,supabase_auth_admin,supabase_storage_admin').format(sql.Identifier(DB_NAME)))
    backup=FOLDER/'backup141';backup.mkdir(mode=0o700,exist_ok=True)
    dump=backup/'schema141.dump';dump.write_bytes(docker('exec','supabase_db_web','pg_dump','-U','postgres','-Fc',DB_NAME));dump.chmod(0o600)
    checksum=hashlib.sha256(dump.read_bytes()).hexdigest()
    def verify_backup(_):
        if hashlib.sha256(dump.read_bytes()).hexdigest()!=checksum:raise RuntimeError('Backup digest changed')
        listing=docker('exec','-i','supabase_db_web','pg_restore','--list',input=dump.read_bytes())
        if b'elearning_form_responses' not in listing:raise RuntimeError('Backup schema contract missing')
    sys.path.insert(0,str(WEB))
    from deployment.lib.migration_executor import MigrationManifest,LockedMigrationExecutor
    manifest=MigrationManifest.load(WEB/'deployment/releases/migrations-141-143-learning.json',ROOT)
    assert [entry.number for entry in manifest.migrations]==[143] and manifest.excluded_schemas==(142,)
    LockedMigrationExecutor(connection_factory=lambda:psycopg.connect(preview_dsn),manifest=manifest,state_file=backup/'execution.json',backup_dir=backup,backup_verifier=verify_backup).run()
    # Provider ACLs are schema metadata, never identities or customer data.
    provider_ddl=docker('exec','supabase_db_web','pg_dump','-U','postgres','--schema-only','--no-owner','-n','auth','-n','storage','postgres').decode()
    grants=re.findall(r'^GRANT .*?;',provider_ddl,re.M|re.S)
    subprocess.run(['docker','exec','-i','supabase_db_web','psql','-U','supabase_admin','-d',DB_NAME,'-v','ON_ERROR_STOP=1','-q'],input=('\n'.join(grants)).encode(),check=True)
    statements=[]
    with psycopg.connect(preview_dsn) as db:
     assert db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()").fetchone()[0]=='madar-eduhope-local-preview-v1'
     for namespace,role in [('auth','supabase_auth_admin'),('storage','supabase_storage_admin')]:
      statements.append(sql.SQL('alter schema {} owner to {}').format(sql.Identifier(namespace),sql.Identifier(role)).as_string(db)+';')
      for name,kind in db.execute("select c.relname,c.relkind from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname=%s and c.relkind in ('r','p','v','m','S')",(namespace,)).fetchall():
       token={'r':'table','p':'table','v':'view','m':'materialized view','S':'sequence'}[kind]
       if kind=='S':continue
       statements.append(sql.SQL('alter '+token+' {}.{} owner to {}').format(sql.Identifier(namespace),sql.Identifier(name),sql.Identifier(role)).as_string(db)+';')
      for name,args in db.execute('select p.proname,pg_get_function_identity_arguments(p.oid) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname=%s',(namespace,)).fetchall():
       statements.append(sql.SQL('alter function {}.{}({}) owner to {}').format(sql.Identifier(namespace),sql.Identifier(name),sql.SQL(args),sql.Identifier(role)).as_string(db)+';')
    guard="do $$ begin if (select shobj_description(oid,'pg_database') from pg_database where datname=current_database()) <> 'madar-eduhope-local-preview-v1' then raise exception 'preview marker mismatch'; end if; end $$;"
    subprocess.run(['docker','exec','-i','supabase_db_web','psql','-U','supabase_admin','-d','madar_eduhope_preview_143','-v','ON_ERROR_STOP=1','-q'],input=('begin;'+guard+'\n'.join(statements)+'commit;').encode(),check=True)
    network=next(iter(originals['db']['NetworkSettings']['Networks']))
    for name,port,inside in [('auth',55441,9999),('rest',55442,3000),('storage',55443,5000)]:
        original=originals[name];config=dict(item.split('=',1) for item in original['Config']['Env'])
        key={'auth':'GOTRUE_DB_DATABASE_URL','rest':'PGRST_DB_URI','storage':'DATABASE_URL'}[name]
        uri=urlsplit(config[key]);config[key]=urlunsplit((uri.scheme,uri.netloc,'/'+DB_NAME,uri.query,uri.fragment))
        if name=='rest':config['PGRST_DB_SCHEMAS']='public'
        if name=='auth':
            config.update(GOTRUE_SITE_URL='http://127.0.0.1:5180',GOTRUE_URI_ALLOW_LIST='http://127.0.0.1:5180/**',GOTRUE_MAILER_AUTOCONFIRM='false',API_EXTERNAL_URL='http://127.0.0.1:55440',GOTRUE_API_EXTERNAL_URL='http://127.0.0.1:55440',GOTRUE_JWT_ISSUER='http://127.0.0.1:55440/auth/v1')
        if name=='auth':
            for kind in ['INVITE','RECOVERY','EMAIL_CHANGE','CONFIRMATION']:config['GOTRUE_MAILER_URLPATHS_'+kind]='http://127.0.0.1:55440/auth/v1/verify'
        if name=='storage':config.update(POSTGREST_URL='http://madar-eduhope-rest:3000',FILE_STORAGE_BACKEND_PATH='/mnt',ENABLE_IMAGE_TRANSFORMATION='false')
        envfile=FOLDER/(name+'.env');private_file(envfile,'\n'.join(k+'='+v for k,v in config.items() if '\n' not in v)+'\n')
        args=['run','-d','--name','madar-eduhope-'+name,'--label',LABEL,'--network',network,'--env-file',str(envfile),'-p',f'127.0.0.1:{port}:{inside}']
        if name=='storage':
            docker('volume','create','--label',LABEL,'madar-eduhope-storage')
            args+=['-v','madar-eduhope-storage:/mnt']
        docker(*args,original['Config']['Image'])
    kong=originals['kong'];configenv=dict(item.split('=',1) for item in kong['Config']['Env'])
    config=json.loads(subprocess.run(['/usr/bin/python3','-c','import json,sys,yaml; print(json.dumps(yaml.safe_load(sys.stdin.read())))'],input=docker('exec','supabase_kong_web','cat',configenv['KONG_DECLARATIVE_CONFIG']),stdout=subprocess.PIPE,check=True).stdout)
    keep={'auth-v1','auth-v1-open','auth-v1-open-callback','auth-v1-open-authorize','rest-v1','storage-v1'}
    config['services']=[service for service in config['services'] if service['name'] in keep]
    for service in config['services']:
        name='storage' if service['name']=='storage-v1' else 'rest' if service['name']=='rest-v1' else 'auth'
        uri=urlsplit(service['url']);port={'auth':9999,'rest':3000,'storage':5000}[name]
        service['url']=urlunsplit((uri.scheme,'madar-eduhope-'+name+':'+str(port),uri.path,uri.query,uri.fragment))
    image=kong['Config']['Image'];uid=docker('run','--rm','--network','none','--entrypoint','id',image,'-u','kong').decode().strip()
    if not uid.isdigit():raise RuntimeError('Unprivileged gateway UID unavailable')
    volume='madar-eduhope-private-config';docker('volume','create','--label',LABEL,volume)
    docker('run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN','--security-opt','no-new-privileges:true','--entrypoint','sh','-v',volume+':/private',image,'-c','umask 077; cat > /private/kong.yml; chown '+uid+':'+uid+' /private/kong.yml',input=json.dumps(config).encode())
    docker('run','-d','--name','madar-eduhope-kong','--label',LABEL,'--user',uid+':'+uid,'--cap-drop','ALL','--security-opt','no-new-privileges:true','--network',network,'-p','127.0.0.1:55440:8000','-v',volume+':/private:ro','-e','KONG_DATABASE=off','-e','KONG_DECLARATIVE_CONFIG=/private/kong.yml','-e','KONG_PLUGINS=cors,key-auth,acl,basic-auth,request-transformer','-e','KONG_NGINX_WORKER_PROCESSES=1',image,'kong','docker-start')
    backend={key:value for key,value in values.items() if value is not None}
    backend.update(APP_ENV='development',RELEASE_SHA='eduhope-local143',SUPABASE_URL='http://127.0.0.1:55440',SUPABASE_DB_URL=urlunsplit((url.scheme,url.netloc,'/'+DB_NAME,url.query,url.fragment)),SCHEMA_COMPATIBLE_MIN='143',SCHEMA_COMPATIBLE_MAX='143',SCHEMA_TARGET_VERSION='143',SCHEMA_EXCLUDED_VERSIONS='',MADAR_ENV_OVERRIDE='false',FRONTEND_URLS='http://127.0.0.1:5180,http://localhost:5180',FRONTEND_URL='http://127.0.0.1:5180',EMAIL_CHANNEL_ENABLED='false',COMMERCIAL_ENTITLEMENT_ENFORCEMENT='false',PUBLIC_UPLOADS_DIR=str(FOLDER/'uploads'),DATA_UPLOAD_DIR=str(FOLDER/'private'),PRIVATE_CHARTS_DIR=str(FOLDER/'charts'),AVATAR_UPLOAD_DIR=str(FOLDER/'avatars'))
    private_file(FOLDER/'backend.env','\n'.join(k+'='+v for k,v in backend.items() if '\n' not in v)+'\n')
    private_file(FOLDER/'preview.marker',MARKER+'\n')
    print('Isolated EduHope schema143 preview created; original database141 untouched,142 unexecuted. Private configuration: /tmp/madar-eduhope-preview/backend.env. No identities copied.')


if __name__=='__main__':
    try:main()
    except Exception as error:
        import traceback
        FOLDER.mkdir(mode=0o700,exist_ok=True); FOLDER.chmod(0o700)
        private_file(FOLDER/'private-error.log',traceback.format_exc())
        print('Preview creation stopped safely: '+type(error).__name__+'. Private diagnosis saved; no automatic reset/cleanup of existing data.',file=sys.stderr)
        raise SystemExit(1)

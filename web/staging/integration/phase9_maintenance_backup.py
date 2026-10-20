#!/usr/bin/env python3
"""Native synthetic ordinary maintenance backup and independent restore drill.

Creates only a labeled networkless tmpfs database and a new private temporary
folder. No production endpoint/configuration/credential/controller is loaded.
This is database/object recovery proof, not a protected release or replica proof.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

WEB=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(WEB))
from scripts import backup_support
from scripts.rehearse_backup import rehearse,RehearsalError
from deployment.lib.maintenance_backup import seal_capture
from deployment.lib.schema150_object_inventory import measure_roots
from deployment.lib.schema150_actor_inventory import REQUIRED_OBJECT_ROOTS
from deployment.lib.completed_normal_profile import DELETION

IMAGE='postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73'
DOCKER=['/usr/bin/docker','--host','unix:///var/run/docker.sock']
LABEL='madar.rehearsal=phase9-maintenance-backup'


def command(args,*,data=None,env=None,timeout=120):
    result=subprocess.run(args,input=data,env=env,capture_output=True,timeout=timeout)
    if result.returncode:
        target=Path(__file__).resolve().parents[3]/('native-child-failure-'+uuid.uuid4().hex+'.log')
        with target.open('xb') as output:
            os.fchmod(output.fileno(),0o600);output.write(result.stderr);output.flush();os.fsync(output.fileno())
        raise RuntimeError('native_maintenance_child_failed:'+str(result.returncode))
    return result.stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('operation',choices=['REHEARSE']);parser.parse_args()
    if shutil.disk_usage(tempfile.gettempdir()).free<1024**3:raise RuntimeError('native_maintenance_disk_required')
    os.umask(0o077);name='madar-phase9-backup-'+uuid.uuid4().hex[:12];created=False;started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='madar-phase9-backup-') as folder:
        root=Path(folder);tools=root/'tools';tools.mkdir();rows={}
        # Commands inside ordinary backup tooling are pinned to this owned
        # database. pg_restore --list consumes the dump through stdin. No port.
        wrapper='''#!/usr/bin/env python3
import json,os,pathlib,subprocess,sys
name=os.environ['MADAR_NATIVE_BACKUP_CONTAINER']
docker=['/usr/bin/docker','--host','unix:///var/run/docker.sock']
row=json.loads(subprocess.check_output(docker+['inspect',name]))[0]
assert row['Config']['Labels'].get('madar.rehearsal')=='phase9-maintenance-backup'
assert row['HostConfig']['NetworkMode']=='none' and not row['HostConfig'].get('PortBindings')
cmd=pathlib.Path(sys.argv[0]).name;args=sys.argv[1:]
if cmd=='docker':os.execv('/usr/bin/docker',docker+args)
assert cmd in {'psql','pg_dump','pg_restore'}
if cmd=='pg_restore' and len(args)==2 and args[0]=='--list':
 with open(args[1],'rb') as source:raise SystemExit(subprocess.run(docker+['exec','-i',name,cmd,'--list'],stdin=source).returncode)
if cmd=='pg_dump' and any(arg.startswith('--file=') for arg in args):
 target=next(arg[7:] for arg in args if arg.startswith('--file='));args=[arg for arg in args if not arg.startswith('--file=')]
 with open(target,'xb') as out:raise SystemExit(subprocess.run(docker+['exec','-i',name,cmd,'-U','postgres','-d','postgres']+args,stdout=out).returncode)
os.execv('/usr/bin/docker',docker+['exec','-i','-e','PGHOST=127.0.0.1','-e','PGPORT=5432','-e','PGUSER=postgres','-e','PGDATABASE=postgres',name,cmd]+args)
'''
        for executable in ('psql','pg_dump','pg_restore','docker'):
            path=tools/executable;path.write_text(wrapper);path.chmod(0o700)
        env=dict(os.environ,PATH=str(tools)+':/usr/sbin:/usr/bin:/sbin:/bin',MADAR_NATIVE_BACKUP_CONTAINER=name)
        try:
            command(DOCKER+['create','--name',name,'--network','none','--memory','256m','--cpus','.5','--pids-limit','96',
                '--label',LABEL,'--tmpfs','/var/lib/postgresql/data:rw,noexec,nosuid,size=256m',
                '-e','POSTGRES_HOST_AUTH_METHOD=trust',IMAGE]);created=True
            command(DOCKER+['start',name])
            for _ in range(60):
                ready=subprocess.run(DOCKER+['exec',name,'pg_isready','-U','postgres'],capture_output=True,timeout=5)
                if ready.returncode==0:break
                time.sleep(.5)
            else:raise RuntimeError('native_maintenance_database_start_timeout')
            def sql(body):
                return command(DOCKER+['exec','-i',name,'psql','-XqAt','-U','postgres','-v','ON_ERROR_STOP=1'],data=body.encode()).decode()
            def query(body):return sql("BEGIN READ ONLY; SET LOCAL search_path=pg_catalog; SET LOCAL statement_timeout='60s'; SET LOCAL TIME ZONE 'UTC';\n"+body+'\nCOMMIT;')
            sql('''CREATE ROLE fixture_owner NOLOGIN;
CREATE ROLE fixture_group NOLOGIN;
DO $$ BEGIN EXECUTE format('CREATE ROLE fixture_provider LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD %L',gen_random_uuid()::text); END $$;
GRANT fixture_group TO fixture_provider WITH INHERIT FALSE;
ALTER ROLE fixture_provider SET statement_timeout='9s';
ALTER ROLE fixture_provider IN DATABASE postgres SET lock_timeout='3s';
ALTER DATABASE postgres OWNER TO fixture_owner;
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;
GRANT CONNECT ON DATABASE postgres TO fixture_provider;
CREATE TABLE public.application_schema_state(contract_key text primary key,schema_version integer);
INSERT INTO public.application_schema_state VALUES('core',146);
CREATE TABLE public.synthetic_tenants(id integer primary key,payload jsonb);
ALTER TABLE public.synthetic_tenants OWNER TO fixture_owner;
INSERT INTO public.synthetic_tenants VALUES(1,'{"synthetic":true}'),(2,'{"foreign":true}');
GRANT SELECT ON public.synthetic_tenants TO fixture_provider;
CREATE SEQUENCE public.synthetic_sequence OWNED BY NONE;
SELECT setval('public.synthetic_sequence',37,false);
CREATE SCHEMA auth;CREATE SCHEMA storage;
CREATE TABLE auth.users(id text primary key,encrypted_password text);
CREATE TABLE auth.mfa_factors(id text primary key,user_id text,factor_type text);
INSERT INTO auth.users VALUES('synthetic-user','synthetic-verifier');
INSERT INTO auth.mfa_factors VALUES('synthetic-factor','synthetic-user','totp');
CREATE TABLE storage.objects(id text primary key,name text);
INSERT INTO storage.objects VALUES('synthetic-object','fixture/asset');''')
            original=command(DOCKER+['exec',name,'pg_dumpall','-U','postgres','--roles-only'])
            snapshot=json.loads(query(backup_support.ROLE_SNAPSHOT_SQL));fingerprint=backup_support.database_fingerprint(query)
            before_snapshot=backup_support.database_snapshot(query)
            cluster=query('SELECT system_identifier::text FROM pg_control_system();').strip()
            # Real role fencing changes current state while saved recovery state
            # must retain the original LOGIN and original password verifier.
            sql('ALTER ROLE fixture_provider NOLOGIN;')
            for logical in sorted(REQUIRED_OBJECT_ROOTS):
                source=root/logical;source.mkdir();rows[logical]={'type':'bind','source':str(source),'content_sha256':'a'*64}
                if logical!='database':
                    (source/'nested').mkdir();(source/'nested/asset').write_bytes(b'owned synthetic '+logical.encode())
            os.setxattr(root/'provider_storage/nested/asset','user.synthetic',b'preserved-object-metadata')
            before=measure_roots(rows,phase='fenced');destination=root/'backups'
            env.update(MADAR_BACKUP_DIR=str(destination),PGHOST='127.0.0.1',PGPORT='5432',PGUSER='postgres',
                PGPASSWORD='unused-synthetic-loopback',PGDATABASE='postgres',MADAR_PROVIDER_BACKUP_REQUIRED='false',
                MADAR_BACKUP_CREATE_DATABASE='true',MADAR_RELEASE_SHA='b'*40,MADAR_BACKUP_KEEP_COUNT='2',
                MADAR_BACKUP_FRESHNESS_MARKER='',MADAR_BACKUP_STATE_DIR='')
            for key,logical in [('MADAR_BUILDER_ASSETS_DIR','builder_assets'),('MADAR_PRIVATE_UPLOADS_DIR','private_uploads'),
                    ('MADAR_GENERATED_ARTIFACTS_DIR','generated_artifacts'),('MADAR_AVATARS_DIR','avatars')]:env[key]=rows[logical]['source']
            command(['/bin/bash',str(WEB/'scripts/backup_madar.sh')],env=env)
            backups=list(destination.glob('madar-*'));assert len(backups)==1;backup=backups[0]
            binding={'operation':DELETION.operation,'context_sha256':'a'*64,'source_sha':'b'*40,'controller_sha':'c'*40,
                'inventory_sha256':'d'*64,'system_identifier':cluster,'source_schema':146,'target_schema':150}
            # subprocess observations in backup verification use the same pinned
            # CLI wrappers. No connection to any ambient database is possible.
            previous_env=dict(os.environ);os.environ.clear();os.environ.update(env)
            try:
                digest=seal_capture(backup,binding=binding,stage='pre-migration',original_roles=original,roles_snapshot=snapshot,
                    bootstrap_role='postgres',roots=rows,previous=before,database_fingerprint=fingerprint,
                    recovery={'origin_source_sha':'a'*40,'origin_images':{'backend':'sha256:'+'1'*64,'frontend':'sha256:'+'2'*64},
                        'candidate_images':{'backend':'sha256:'+'3'*64,'frontend':'sha256:'+'4'*64},
                        'database_image':json.loads(command(DOCKER+['inspect',name]))[0]['Image'],
                        'migration_manifest_sha256':'6'*64,'controller_tree_sha256':'7'*64,
                        'configuration_sha256':{'synthetic':'8'*64},'configuration_escrow_required':True})
                # Instrument the unchanged read-only measurement, not its
                # result. Keep private component differences if restore fails.
                measure=backup_support.database_snapshot;observations=[]
                def record(query):
                    value=measure(query);observations.append(value);return value
                backup_support.database_snapshot=record
                try:report=rehearse(backup,IMAGE,maintenance_manifest_sha256=digest)
                except Exception:
                    target=Path(__file__).resolve().parents[3]/('native-snapshot-failure-'+uuid.uuid4().hex+'.json')
                    target.write_text(json.dumps({'before':before_snapshot,'observed':observations},indent=2)+'\n');target.chmod(0o600)
                    raise
                finally:backup_support.database_snapshot=measure
                assert all(report[k] is True for k in ('role_attributes_restored','ownership_and_acls_restored',
                    'database_fingerprint_verified','native_object_bytes_restored'))
                # Receiver and restore must require the independent expected
                # manifest, rather than trusting a caller-recomputed checksum.
                for wrong in (None,'0'*64):
                    try:rehearse(backup,IMAGE,maintenance_manifest_sha256=wrong)
                    except (RehearsalError,backup_support.BackupError):pass
                    else:raise AssertionError('unbound maintenance restore accepted')
                print(json.dumps({'operation':'native-synthetic-maintenance-backup-restore','status':'PASS',
                    'schema':146,'original_roles_restored':True,'database_owner_acl_data_sequences_verified':True,
                    'native_object_bytes_restored':True,'native_object_metadata_activated':False,
                    'missing_wrong_expected_manifest_rejected':True,'production_authorized':False,
                    'protected_controller_execution':False,'replica_verified':False,
                    'elapsed_seconds':round(time.monotonic()-started,3)}))
            finally:os.environ.clear();os.environ.update(previous_env)
        finally:
            if created:
                row=json.loads(command(DOCKER+['inspect',name]))[0]
                if row['Config']['Labels'].get('madar.rehearsal')!='phase9-maintenance-backup':
                    raise RuntimeError('native_maintenance_cleanup_identity_changed')
                command(DOCKER+['rm','--force',name])

if __name__=='__main__':main()

#!/usr/bin/env python3
"""Independently restore sealed checkpoint components into private quarantine.

Restore roles, database owners and ACLs in a networkless disposable PostgreSQL;
restore every archive to a NEW non-executable quarantine; measure all JSON
components and required image availability. Never execute restored controller
code, enable jobs, use customer endpoints, mutate production or alter a manifest.
This proves component recovery, not full Supabase/application readiness.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.coordinated_checkpoint import verify_inventory,digest_file
from deployment.lib.coordinated_archive_restore import restore_archive,verify_restored_archive
from deployment.lib.coordinated_storage_restore import recover_metadata

ROOT=Path('/var/lib/madar-control-plane/normal-local-preparation')
BOOTSTRAP='supabase_admin'
IMAGE='sha256:f371b5f3f2ac0a05703f33d6e6134515fb2498cab708fb948a0aeb7481467c00'
CURRENT_STAGE='entry'
STAGE_STARTED=time.monotonic()
RESTORE_STARTED=STAGE_STARTED


def stage(name):
    global CURRENT_STAGE,STAGE_STARTED
    CURRENT_STAGE=name;STAGE_STARTED=time.monotonic()
    print(json.dumps({'event':'restore_stage','stage':name,'elapsed_seconds':round(STAGE_STARTED-RESTORE_STARTED,3)}),flush=True)


ROLE_QUERY="SELECT md5(string_agg(row_to_json(r)::text, E'\\n' ORDER BY rolname)) FROM (SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolconnlimit,rolvaliduntil,rolreplication,rolbypassrls,rolpassword FROM pg_authid ) r;"


ROLE_MEMBERSHIP_QUERY="SELECT md5(COALESCE(string_agg(row_to_json(r)::text, E'\\n' ORDER BY role_name,member_name,grantor_name),'')) FROM (SELECT a.rolname role_name,b.rolname member_name,c.rolname grantor_name,m.admin_option,m.inherit_option,m.set_option FROM pg_auth_members m JOIN pg_roles a ON a.oid=m.roleid JOIN pg_roles b ON b.oid=m.member JOIN pg_roles c ON c.oid=m.grantor ) r;"


def role_restore_sql(saved):
    """Keep the original bootstrap superuser at OID 10 in the private cluster.

    PostgreSQL 17's recorded role grants distinguish the cluster bootstrap
    superuser. initdb creates that exact role; skip only its duplicate CREATE,
    preserving every original ALTER, grantor, membership and password verifier.
    """
    create='CREATE ROLE '+BOOTSTRAP+';'
    if saved.splitlines().count(create)!=1:
        raise RuntimeError('coordinated_restore_bootstrap_identity_invalid')
    if not re.search(r'^ALTER ROLE '+re.escape(BOOTSTRAP)+r' WITH SUPERUSER\b',saved,re.M):
        raise RuntimeError('coordinated_restore_bootstrap_identity_invalid')
    return re.sub(r'^'+re.escape(create)+r'\n','',saved,count=1,flags=re.M)


def run(args,*,sql=None,timeout=90):
    result=subprocess.run(args,input=sql,capture_output=True,text=True,timeout=timeout)
    if result.returncode:
        # No SQL, COPY rows, passwords or application configuration in logs.
        category='command_failed'
        for code,pattern in [('missing_role',r'role .* does not exist'),('extension_prerequisite',r'must be preloaded|requires.*preload'),('duplicate_object',r'already exists'),('database_in_use',r'database .* is being accessed by other users'),('role_grantor_denied',r'permission denied to grant privileges as role'),('role_alter_denied',r'permission denied to alter role'),('role_create_denied',r'permission denied to create role'),('superuser_required',r'must be superuser'),('permission_denied',r'permission denied')]:
            if re.search(pattern,result.stderr,re.I):category=code;break
        raise RuntimeError(category)
    return result.stdout.strip()


def psql(name,query,*,database='postgres'):
    return run(['docker','exec','-i',name,'psql','-X','-h','/tmp','-U',BOOTSTRAP,'-d',database,'-At','-v','ON_ERROR_STOP=1'],sql=query)


def restore(source,expected_manifest,*,existing_quarantine=None):
    if os.geteuid()!=0 or not sys.flags.isolated or not sys.flags.dont_write_bytecode:
        raise RuntimeError('coordinated_restore_frozen_root_entry_required')
    if source.parent!=ROOT or source.is_symlink() or source.stat().st_uid!=0:
        raise RuntimeError('coordinated_restore_source_untrusted')
    if digest_file(source/'manifest.json')!=expected_manifest:
        raise RuntimeError('coordinated_restore_manifest_changed')
    stage('verify_sealed_inventory')
    packet,inventory=verify_inventory(source)
    if existing_quarantine is None:
        quarantine=Path(tempfile.mkdtemp(prefix='restore-components-',dir=ROOT));quarantine.chmod(0o700)
    else:
        quarantine=Path(existing_quarantine)
        if (quarantine.parent!=ROOT or not quarantine.name.startswith('restore-components-')
                or quarantine.is_symlink() or quarantine.stat().st_uid!=0 or quarantine.stat().st_mode&0o077):
            raise RuntimeError('coordinated_restore_quarantine_untrusted')
    results={};started=datetime.now(timezone.utc).isoformat()
    for entry in packet['files']:
        path=source/entry['path']
        stage('restore_'+path.name)
        if path.name.endswith('.tar.gz'):
            results[path.name]=(verify_restored_archive if existing_quarantine is not None else restore_archive)(path,quarantine/path.name.removesuffix('.tar.gz'))
        elif path.suffix=='.json':
            json.loads(path.read_text());target=quarantine/path.name
            if existing_quarantine is None:
                with target.open('xb') as output:output.write(path.read_bytes())
                target.chmod(0o600)
            elif target.is_symlink() or not target.is_file() or target.stat().st_uid!=0:
                raise RuntimeError('coordinated_restore_json_untrusted')
            if digest_file(target)!=entry['sha256']:raise RuntimeError('coordinated_restore_json_changed')
            results[path.name]={'parsed':True,'restored_bytes_verified':True}
        elif path.name not in {'database.dump','roles.sql'}:
            raise RuntimeError('coordinated_restore_component_unsupported')
    stage('verify_image_availability')
    images=json.loads((source/'images.json').read_text())
    required=sorted({row['image'] for row in images.values()})
    actual=run(['docker','image','inspect',*required,'--format','{{.Id}}'],timeout=240).splitlines()
    if set(actual)!=set(required):raise RuntimeError('coordinated_restore_image_unavailable')
    name='madar-checkpoint-component-restore-'+uuid.uuid4().hex[:12]
    dump=quarantine/'database.dump'
    if dump.exists() or dump.is_symlink():
        if dump.is_symlink() or not dump.is_file() or dump.stat().st_uid!=0 or digest_file(dump)!=digest_file(source/'database.dump'):
            raise RuntimeError('coordinated_restore_dump_changed')
    else:
        with dump.open('xb') as output:output.write((source/'database.dump').read_bytes())
        dump.chmod(0o444)
    stage('start_networkless_database')
    run(['docker','run','--pull','never','--detach','--name',name,'--network','none','--user','65534:65534',
        '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','2g','--cpus','2','--pids-limit','128',
        '--tmpfs','/tmp:rw,nosuid,nodev,size=64m,mode=1777','--tmpfs','/restore-data:rw,nosuid,nodev,size=2g,mode=1777',
        '--mount',f'type=bind,src={dump},dst=/backup.dump,readonly','--entrypoint','sh',IMAGE,'-ec',
        "initdb -D /restore-data/pgdata -U supabase_admin --auth=trust >/dev/null; exec postgres -D /restore-data/pgdata -k /tmp -c listen_addresses='' -c log_statement=none -c log_min_error_statement=panic -c shared_preload_libraries=pg_cron,pg_net -c cron.launch_active_jobs=off -c pg_net.database_name=madar_restore_disabled"])
    try:
        for attempt in range(60):
            try:psql(name,'SELECT 1;');break
            except RuntimeError:
                if attempt==59:raise
                time.sleep(0.5)
        jobs=psql(name,"SELECT current_setting('cron.launch_active_jobs')='off'; SELECT current_setting('pg_net.database_name')='madar_restore_disabled'; SELECT NOT EXISTS(SELECT 1 FROM pg_database WHERE datname='madar_restore_disabled');")
        if jobs.splitlines()!=['t','t','t']:raise RuntimeError('coordinated_restore_jobs_not_disabled')
        stage('restore_role_attributes')
        roles=(source/'roles.sql').read_text()
        # Preserve the original cluster bootstrap identity at OID 10.
        # postgres remains NOSUPERUSER throughout this private restore.
        psql(name,role_restore_sql(roles))
        stage('recreate_private_database')
        psql(name,'DROP DATABASE postgres WITH (FORCE);',database='template1')
        stage('restore_database_owners_acls')
        run(['docker','exec',name,'pg_restore','--exit-on-error','--create','-h','/tmp','-U',BOOTSTRAP,'-d','template1','/backup.dump'])
        # Exact owners/ACLs were applied, without --no-owner or --no-acl.
        stage('verify_database_integrity')
        metadata=psql(name,"SELECT 'schema='||schema_version FROM public.application_schema_state WHERE contract_key='core'; SELECT 'users='||count(*) FROM auth.users; SELECT 'identities='||count(*) FROM auth.identities; SELECT 'factors='||count(*) FROM auth.mfa_factors; SELECT 'invalid_indexes='||count(*) FROM pg_index WHERE NOT indisvalid; SELECT 'database_owner='||r.rolname FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba WHERE d.datname=current_database();")
        summary=dict(line.split('=',1) for line in metadata.splitlines())
        if summary['schema']!='115' or summary['invalid_indexes']!='0':raise RuntimeError('coordinated_restore_database_integrity_failed')
        roles_digest=psql(name,ROLE_QUERY+'\n'+ROLE_MEMBERSHIP_QUERY).splitlines()
        # Source comparison is strictly read-only; its role hash is not printed.
        source_digest=run(['docker','exec','-i','supabase-db','psql','-X','-U','postgres','-d','postgres','-At','-v','ON_ERROR_STOP=1'],sql='BEGIN READ ONLY;\n'+ROLE_QUERY+'\n'+ROLE_MEMBERSHIP_QUERY+'\nROLLBACK;\n').splitlines()[1:-1]
        if source_digest!=roles_digest:raise RuntimeError('coordinated_restore_role_attributes_changed')
        stage('recover_native_storage_metadata_from_restored_database')
        objects=json.loads(psql(name,"SELECT COALESCE(jsonb_agg(jsonb_build_object('bucket',bucket_id,'name',name,'version',version,'metadata',metadata)),'[]') FROM storage.objects;"))
        storage_quarantine=Path(tempfile.mkdtemp(prefix='restore-storage-metadata-',dir=ROOT));storage_quarantine.chmod(0o700)
        restore_archive(source/'native-storage.tar.gz',storage_quarantine/'native')
        storage_root=storage_quarantine/'native/opt/madar/local-supabase/volumes/storage'
        results['native-storage.tar.gz']['metadata_recovery']=recover_metadata(objects,storage_root,source_root=Path('/opt/madar/local-supabase/volumes/storage'))
        results['native-storage.tar.gz']['metadata_quarantine']=str(storage_quarantine)
        results['database.dump']={'schema':115,'owners_and_acls_restored':True,'database_recreated_from_archive':True,'metadata':summary,'network':'none'}
        results['roles.sql']={'attributes_and_password_verifiers_match_current_source':True,'original_cluster_bootstrap_role_preserved':True,'memberships_and_original_grantors_match_current_source':True,'secret_values_reported':False}
    finally:
        # Only this NEW test-owned target is removed. Original recovery/rollback
        # containers, volumes, source, archives and quarantine remain untouched.
        run(['docker','rm','--force',name])
    stage('verify_original_unchanged')
    if verify_inventory(source)[1]!=inventory:raise RuntimeError('coordinated_restore_original_changed')
    return {'operation':'actual-coordinated-component-restore','checkpoint_manifest_sha256':expected_manifest,
        'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),'restored_files':inventory,
        'components':results,'images_available':len(required),'quarantine':str(quarantine),'schema':115,
        'network':'none','migrations_executed':False,'production_modified':False,'workers_started':False,
        'component_restore_verified':True,'platform_recovery_proven':False,'application_acceptance_proven':False,
        'offhost_restore_proven':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('manifest_sha256');parser.add_argument('--verify-quarantine',type=Path);args=parser.parse_args()
    def expired(signum,frame):raise RuntimeError('coordinated_restore_deadline')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,900)
    try:print(json.dumps(restore(args.source,args.manifest_sha256,existing_quarantine=args.verify_quarantine)))
    except Exception as error:
        print(json.dumps({'operation':'actual-coordinated-component-restore','status':'failed',
            'exception_type':type(error).__name__,'stage':CURRENT_STAGE,'failure_category':str(error) if type(error) is RuntimeError else 'restore_failed',
            'elapsed_seconds':round(time.monotonic()-RESTORE_STARTED,3),'stage_seconds':round(time.monotonic()-STAGE_STARTED,3)}));sys.exit(1)
    finally:signal.setitimer(signal.ITIMER_REAL,0)

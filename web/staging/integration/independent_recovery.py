#!/usr/bin/env python3
"""Independent synthetic-cluster/full-application recovery on the staging VM only."""
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import time

import manage
import restore
import smoke

TARGET_PROJECT='madar-independent-recovery-20261017'
TARGET_MARKER='madar-hardening-synthetic-148-independent'
PORTS={'18080':'19080','18443':'19443','18081':'19081'}
ROLE_FINGERPRINT="""select encode(sha256(convert_to(json_build_object(
 'roles',(select json_agg(to_jsonb(r)-'oid' order by rolname) from pg_authid r),
 'memberships',(select json_agg(json_build_object('role',r.rolname,'member',m.rolname,'grantor',g.rolname,
   'admin',a.admin_option,'inherit',a.inherit_option,'set',a.set_option) order by r.rolname,m.rolname,g.rolname)
   from pg_auth_members a join pg_roles r on r.oid=a.roleid join pg_roles m on m.oid=a.member join pg_roles g on g.oid=a.grantor))::text,'UTF8')),'hex');"""

PRIVILEGE_FINGERPRINT="""select encode(sha256(convert_to(coalesce(string_agg(value,'' order by value COLLATE "C"),''),'UTF8')),'hex') from (
 select jsonb_build_object('schema',n.nspname,'relation',c.relname,'owner',pg_get_userbyid(c.relowner),
   'rls',c.relrowsecurity,'force_rls',c.relforcerowsecurity,'acl',array(select a::text from unnest(coalesce(c.relacl,acldefault(case when c.relkind='S' then 'S'::"char" else 'r'::"char" end,c.relowner))) a order by a::text))::text value
 from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname in ('public','auth','storage') and c.relkind in ('r','p','v','m','S')
 union all select jsonb_build_object('schema',n.nspname,'function',p.proname,'arguments',pg_get_function_identity_arguments(p.oid),
   'owner',pg_get_userbyid(p.proowner),'definer',p.prosecdef,'configuration',p.proconfig,
   'acl',array(select a::text from unnest(coalesce(p.proacl,acldefault('f',p.proowner))) a order by a::text))::text
 from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname in ('public','auth','storage')
 union all select jsonb_build_object('schema',nspname,'owner',pg_get_userbyid(nspowner),
   'acl',array(select a::text from unnest(coalesce(nspacl,acldefault('n',nspowner))) a order by a::text))::text
 from pg_namespace where nspname in ('public','auth','storage')
 union all select jsonb_build_object('schema',n.nspname,'table',c.relname,'policy',p.polname,'command',p.polcmd,
   'roles',array(select pg_get_userbyid(oid) from unnest(p.polroles) oid order by pg_get_userbyid(oid)),
   'using',pg_get_expr(p.polqual,p.polrelid),'check',pg_get_expr(p.polwithcheck,p.polrelid))::text
 from pg_policy p join pg_class c on c.oid=p.polrelid join pg_namespace n on n.oid=c.relnamespace where n.nspname in ('public','auth','storage')
) objects;"""


def private_copy(source,target):
    if source.is_symlink() or not source.is_file():raise RuntimeError('Recovery source file identity invalid')
    restore.write_binary(target,source.read_bytes())


def replacement_ports(value):
    for before,after in PORTS.items():value=value.replace(':'+before,':'+after)
    return value


def render_compose(text,source_here,frontend_dist):
    text=replacement_ports(text)
    text=text.replace('./gateway.conf',str(source_here/'gateway.conf')).replace('./frontend.conf',str(source_here/'frontend.conf'))
    text=text.replace('../../frontend/dist',str(frontend_dist))
    for before,after in (('mem_limit: 1280m','mem_limit: 768m'),('mem_limit: 768m','mem_limit: 512m'),
                         ('mem_limit: 256m','mem_limit: 192m'),('mem_limit: 128m','mem_limit: 96m')):
        # Keep backend at768m; PostgreSQL was the sole original768m service.
        if before=='mem_limit: 768m':continue
        text=text.replace(before,after)
    text=text.replace('    mem_limit: 768m\n    cpus: 2.0','    mem_limit: 512m\n    cpus: 1.0')
    return text


@contextmanager
def target_context(runtime):
    previous=(manage.PROJECT,manage.RUNTIME,manage.HERE,manage.MARKER,smoke.PROVIDER,smoke.APPLICATION)
    manage.PROJECT=TARGET_PROJECT;manage.RUNTIME=runtime;manage.HERE=runtime;manage.MARKER=TARGET_MARKER
    smoke.PROVIDER='http://127.0.0.1:19081';smoke.APPLICATION='http://127.0.0.1:19080/api'
    try:yield
    finally:
        manage.PROJECT,manage.RUNTIME,manage.HERE,manage.MARKER,smoke.PROVIDER,smoke.APPLICATION=previous


def prepare_target(runtime,source_state,source_runtime,source_here):
    if (runtime.exists() or runtime.is_symlink() or runtime.parent.resolve()!=Path.home().resolve()
            or source_state['project']==TARGET_PROJECT):raise RuntimeError('Preserve existing or ambiguous recovery resources')
    if shutil.disk_usage(runtime.parent).free<4*1024**3:raise RuntimeError('Recovery disk headroom insufficient')
    available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))
    if available<2200*1024:raise RuntimeError('Recovery memory headroom insufficient')
    runtime.mkdir(mode=0o700)
    with target_context(runtime):
        owner={**source_state,'project':TARGET_PROJECT,'marker':TARGET_MARKER}
        manage.private_write('owner.json',json.dumps(owner)+'\n')
        for name in ('compose.env','application.env'):
            value=(source_runtime/name).read_text().replace(str(source_runtime),str(runtime))
            manage.private_write(name,replacement_ports(value))
        for name in ('tls.crt','tls.key'):private_copy(source_runtime/name,runtime/name);(runtime/name).chmod(0o444)
        # No copied role/schema bootstrap: target must begin with initdb roles only.
        manage.private_write('bootstrap.sql',"-- Independent restore target: deliberately no application roles or schema.\n",mounted=True)
        text=render_compose((source_here/'compose.yaml').read_text(),source_here,manage.REPOSITORY/'web/frontend/dist')
        manage.private_write('compose.yaml',text)
        manage.state();manage.attest_resources()


def original_identity_acceptance(fixture):
    session,_=smoke.http('POST','/auth/v1/token?grant_type=password',body={'email':fixture['admin_email'],'password':fixture['admin_password']})
    if session.get('user',{}).get('id')!=fixture['admin_auth_id']:raise RuntimeError('Restored original Auth identity changed')
    factor=manage.sql("select id from auth.mfa_factors where user_id="+smoke.literal(fixture['admin_auth_id'])+" and status='verified' and factor_type='totp' order by created_at limit 1;")
    challenge,_=smoke.http('POST',f'/auth/v1/factors/{factor}/challenge',token=session['access_token'],body={})
    elevated,_=smoke.http('POST',f'/auth/v1/factors/{factor}/verify',token=session['access_token'],body={'challenge_id':challenge['id'],'code':smoke.totp(fixture['mfa_secret'])})
    if not elevated.get('access_token'):raise RuntimeError('Restored original TOTP rejected')
    values=dict(line.split('=',1) for line in (manage.RUNTIME/'application.env').read_text().splitlines())
    data,_=smoke.http('GET',f"/storage/v1/object/{fixture['private_bucket']}/fixture.txt",token=values['SUPABASE_SERVICE_KEY'])
    if data!=b'synthetic private storage fixture':raise RuntimeError('Restored original private object changed')
    smoke.http('GET',f"/storage/v1/object/{fixture['private_bucket']}/fixture.txt",token=values['SUPABASE_ANON_KEY'],expected=(400,403,404))
    return {'original_password_login':True,'original_auth_id':True,'original_totp':True,'original_private_storage':True,'anonymous_storage_denied':True}


def main(mode):
    manage.require_staging_host();manage.require_database_marker();manage.attest_resources()
    source_state=manage.state();source_runtime=manage.RUNTIME;source_here=manage.HERE
    source_container=manage.database_container()
    source_system=manage.sql('select system_identifier from pg_control_system();')
    if manage.sql("select schema_version from public.application_schema_state where contract_key='core';")!='148':
        raise RuntimeError('Independent full-app recovery requires verified synthetic schema148')
    if mode=='INSPECT':
        print(json.dumps({'mode':mode,'source_schema':148,'target_project':TARGET_PROJECT,'ports':PORTS,'production_modified':False}));return
    fixture=json.loads((source_runtime/'smoke-fixture.json').read_text())
    runtime=Path.home()/TARGET_PROJECT
    # A fresh retry preserves prior archives/volumes and never overlaps a live
    # recovery stack. Unknown ownership is handled by existing attestation.
    for line in manage.docker('ps','--format','{{.Names}}').decode().splitlines():
        if line.startswith('madar-independent-recovery-20261017-'):
            raise RuntimeError('Stop and attest the earlier owned recovery attempt before a fresh retry')
    prepare_target(runtime,source_state,source_runtime,source_here)
    services=['frontend','backend','notification-worker','gateway','auth','storage']
    started=time.monotonic();target_started=False
    manage.compose('stop','--timeout','30',*services)
    try:
        manage.require_database_marker()
        original=json.loads(manage.sql(restore.FINGERPRINT_SQL))
        roles_sha=manage.sql(ROLE_FINGERPRINT)
        privileges_sha=manage.sql(PRIVILEGE_FINGERPRINT)
        dump=manage.docker('exec',source_container,'pg_dump','-U','postgres','-d','madar_hardening','-Fc')
        roles=manage.docker('exec',source_container,'pg_dumpall','-U','postgres','--roles-only')
        objects=restore.helper(manage.PROJECT+'_objects',"import sys,tarfile; t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|'); t.add('/objects',arcname='.'); t.close()")
        object_inventory=restore.inventory(manage.PROJECT+'_objects')
        # Verify all member paths/types before copying into a new object volume.
        import io,tarfile
        from pathlib import PurePosixPath
        with tarfile.open(fileobj=io.BytesIO(objects)) as archive:
            for member in archive.getmembers():
                path=PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):raise RuntimeError('Unsafe recovery object archive')
        for name,data in (('database.dump',dump),('roles.sql',roles),('objects.tar',objects)):
            restore.write_binary(runtime/name,data)
        restore.write_binary(runtime/'capture-checkpoint.json',json.dumps({
            'source_system_identifier':source_system,'source_sha':source_state['source_sha'],
            'rows_sequences_sha256':hashlib.sha256(json.dumps(original,sort_keys=True).encode()).hexdigest(),
            'roles_sha256':roles_sha,'privileges_sha256':privileges_sha,
            'archive_sha256':{name:hashlib.sha256(data).hexdigest() for name,data in (('database.dump',dump),('roles.sql',roles),('objects.tar',objects))}
        },sort_keys=True).encode())
    finally:
        manage.compose('start','--wait','--wait-timeout','90',*services)
    with target_context(runtime):
        try:
            manage.compose('up','--detach','--wait','--wait-timeout','90','postgres')
            target_started=True;manage.attest_resources()
            target_system=manage.sql('select system_identifier from pg_control_system();')
            if target_system==source_system or manage.database_container()==source_container:raise RuntimeError('Recovery is not an independent cluster')
            if manage.sql("select count(*) from pg_roles where rolname in ('supabase_auth_admin','supabase_storage_admin','authenticator');")!='0':
                raise RuntimeError('Recovery unexpectedly inherited application roles')
            # initdb owns postgres; restore its attributes/password, not a duplicate CREATE.
            filtered='\n'.join(line for line in roles.decode().splitlines() if line.strip()!='CREATE ROLE postgres;')+'\n'
            manage.sql(filtered,database='postgres')
            if manage.sql(ROLE_FINGERPRINT)!=roles_sha:raise RuntimeError('Independent restored role attributes/passwords/memberships differ')
            manage.docker('exec','-i',manage.database_container(),'pg_restore','-U','postgres','--exit-on-error','--single-transaction','-d','madar_hardening',data=dump)
            manage.sql("comment on database madar_hardening is '"+TARGET_MARKER+"';")
            manage.require_database_marker()
            if manage.sql(PRIVILEGE_FINGERPRINT)!=privileges_sha:raise RuntimeError('Independent restored grants/owners/RLS/definer settings differ')
            if json.loads(manage.sql(restore.FINGERPRINT_SQL))!=original:raise RuntimeError('Independent restored original rows/sequences differ')
            manage.private_write('database-restored-checkpoint.json',json.dumps({
                'independent_cluster':True,'system_identifier':target_system,
                'original_rows_sequences_preserved':True,'roles_preserved':True,'privileges_preserved':True})+'\n')
            manage.compose('create','storage')
            restore.helper(TARGET_PROJECT+'_objects',"import sys,tarfile; t=tarfile.open(fileobj=sys.stdin.buffer,mode='r|'); t.extractall('/objects',filter='data')",writable=True,data=objects)
            if restore.inventory(TARGET_PROJECT+'_objects')!=object_inventory:raise RuntimeError('Independent restored object bytes differ')
            manage.private_write('objects-restored-checkpoint.json',json.dumps({'objects_verified':len(object_inventory),'independent_objects':True})+'\n')
            manage.compose('up','--detach','--wait','--wait-timeout','120')
            manage.attest_resources();manage.require_database_marker()
            identity=original_identity_acceptance(fixture)
            smoke.main()
            # Real reservations/orders/payment SQL on the independent restored DB.
            # Stop only this target's worker while fixture transactions execute.
            manage.compose('stop','--timeout','15','notification-worker')
            values=dict(line.split('=',1) for line in (manage.RUNTIME/'compose.env').read_text().splitlines())
            try:
                output=manage.docker('run','--rm','--read-only','--memory=768m','--cpus=1','--pids-limit=256',
                    '--network','container:'+manage.database_container(),'--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
                    '--env','PYTHONPATH=/app','--env','PYTHONDONTWRITEBYTECODE=1',
                    '--env','PGPASSWORD='+values['DATABASE_PASSWORD'],
                    '--env','BUSINESS_INTEGRITY_SYNTHETIC_DATABASE_DSN=host=127.0.0.1 port=5432 dbname=madar_hardening user=postgres connect_timeout=5',
                    '--volume',str(manage.REPOSITORY/'web/backend')+':/app:ro','--entrypoint','python',
                    'madar-schema136-preparation-test:working','-c',
                    "import unittest,sys; suite=unittest.defaultTestLoader.loadTestsFromName('tests.test_native_business_integrity_database'); result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(suite); sys.exit(0 if result.wasSuccessful() and result.testsRun==22 and not result.skipped else 1)",timeout=180)
                manage.private_write('restored-business.log',output.decode())
            finally:manage.compose('start','--wait','--wait-timeout','60','notification-worker')
            report={'scope':'synthetic independent PostgreSQL roles/data/object restoration plus full native application',
                'source_sha':source_state['source_sha'],'schema':148,'source_system_identifier':source_system,
                'restored_system_identifier':target_system,'target_project':TARGET_PROJECT,'independent_cluster':True,
                'roles_absent_before_restore':True,'role_attributes_passwords_memberships_preserved':True,
                'owners_grants_rls_definer_settings_preserved':True,'restored_native_business_tests':22,
                'original_rows_and_sequences_preserved':True,'tables_verified':len(original['tables']),
                'sequences_verified':len(original['sequences'] or {}),'objects_verified':len(object_inventory),
                'original_identity_acceptance':identity,'new_auth_mfa_storage_worker_api_acceptance':True,
                'database_sha256':hashlib.sha256(dump).hexdigest(),'roles_sha256':hashlib.sha256(roles).hexdigest(),
                'objects_sha256':hashlib.sha256(objects).hexdigest(),'elapsed_seconds':round(time.monotonic()-started,3),
                'production_modified':False,'limitations':['same VM, different cluster/volumes/networks','offline source-overlay application images','not off-host/bare-host/PITR','not full browser product E2E','not production RPO/RTO or authorization']}
            manage.private_write('result.json',json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,sort_keys=True))
        except BaseException:
            if target_started:
                # Preserve all archives/volumes. Stop only this attested project.
                manage.attest_resources();manage.compose('stop','--timeout','15')
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('INSPECT','REHEARSE'),nargs='?',default='INSPECT')
    parser.add_argument('--attempt',type=int,choices=(1,2,3),default=1)
    args=parser.parse_args()
    if args.attempt>1:TARGET_PROJECT+='-attempt'+str(args.attempt)
    main(args.mode)

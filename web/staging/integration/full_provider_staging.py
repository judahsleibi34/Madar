#!/usr/bin/env python3
"""Owned fresh-provider acceptance from a Git inventory, never production dispatch.

Fresh synthetic genesis is separate from current-data migration and recovery
rehearsals. No customer archive, production environment file, issuer or privileged
controller path is accepted. Historical specialized acceptance remains intact.
"""
from contextlib import contextmanager
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import stat
import sys
import time

import manage
import smoke
import tenant_smoke
import schema150_acceptance as application
import schema150_restore_configuration as configuration

sys.path.insert(0,str(manage.REPOSITORY/'web'))
from deployment.lib.migration_inventory import discover,GitSource,canonical
from deployment.lib.migration_plan import generate
from deployment.lib.schema148_artifacts import INPUTS,capture_candidate_archive,verify_required_ci,authenticated_archive
from fresh_artifact_acceptance import import_authenticated_image

PORTS={22080,22443,22081}
SERVICES=set(configuration.BOUNDS)


def identity(source):
    import re
    if not isinstance(source,str) or not re.fullmatch('[0-9a-f]{40}',source):
        raise RuntimeError('full_staging_exact_source_required')
    return 'madar-full-provider-'+source[:12]


def require_host(runtime):
    name=socket.gethostname()
    hosted=(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted'
        and os.environ.get('GITHUB_REPOSITORY')=='judahsleibi34/Madar')
    if name in ('madar-gpu','madar-node1') or not (name=='madar-staging' or hosted) or os.getuid()==0:
        raise RuntimeError('full_staging_isolated_host_required')
    if runtime.is_symlink() or runtime.parent!=Path.home() or not runtime.name.startswith('madar-full-provider-'):
        raise RuntimeError('full_staging_owned_scope_required')


@contextmanager
def lease():
    path=Path.home()/'.madar-full-provider-staging.lock'
    descriptor=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        info=os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_nlink!=1:
            raise RuntimeError('full_staging_lock_untrusted')
        try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('full_staging_busy') from None
        yield
    finally:os.close(descriptor)


@contextmanager
def target(source,schema):
    project=identity(source);runtime=Path.home()/project
    require_host(runtime)
    saved={key:getattr(manage,key) for key in ('PROJECT','OWNER','MARKER','RUNTIME','HERE','require_staging_host','compose')}
    old=(smoke.PROVIDER,smoke.APPLICATION)
    try:
        manage.PROJECT=manage.OWNER=project;manage.MARKER=project+'-synthetic'
        manage.RUNTIME=manage.HERE=runtime
        manage.require_staging_host=lambda:require_host(runtime)
        manage.compose=lambda *args,timeout=180:configuration.invoke(runtime,args,project,project,timeout=timeout,target_schema=schema)
        smoke.PROVIDER='http://127.0.0.1:22081';smoke.APPLICATION='http://127.0.0.1:22080/api'
        yield runtime,project
    finally:
        for key,value in saved.items():setattr(manage,key,value)
        smoke.PROVIDER,smoke.APPLICATION=old


def source_plan(source,baseline):
    git=GitSource(manage.REPOSITORY)
    if git.command('rev-parse','HEAD').strip().decode()!=source or git.command('status','--porcelain','--untracked-files=normal').strip():
        raise RuntimeError('full_staging_clean_exact_source_required')
    origin=discover(manage.REPOSITORY,source_sha=baseline,history_base_sha=baseline).target
    inventory=discover(manage.REPOSITORY,source_sha=source,history_base_sha=baseline)
    plan=generate(manage.REPOSITORY,inventory,origin=origin)
    if plan.document()['execution_class']!='transactional':raise RuntimeError('full_staging_transactional_path_required')
    return inventory,plan


def admission_headroom(runtime,project):
    if runtime.exists() or runtime.is_symlink():raise RuntimeError('full_staging_attempt_consumed')
    if shutil.disk_usage(Path.home()).free<8*1024**3:raise RuntimeError('full_staging_disk_headroom')
    available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))
    if available<2200*1024:raise RuntimeError('full_staging_memory_headroom')
    for file in ('/proc/net/tcp','/proc/net/tcp6'):
        for raw in Path(file).read_text().splitlines()[1:]:
            row=raw.split()
            if row[3]=='0A' and int(row[1].rsplit(':',1)[1],16) in PORTS:
                raise RuntimeError('full_staging_port_in_use')
    if manage.docker('ps','-aq','--filter','label=com.docker.compose.project='+project).strip():
        raise RuntimeError('full_staging_existing_containers')
    for kind in ('network','volume'):
        if manage.docker(kind,'ls','--filter','name='+project,'--format','{{.Name}}').strip():
            raise RuntimeError('full_staging_existing_resources')


def actors(images,*,complete):
    manage.attest_resources()
    identifiers=manage.docker('ps','-aq','--filter','label=com.docker.compose.project='+manage.PROJECT).decode().split()
    rows=json.loads(manage.docker('inspect',*identifiers)) if identifiers else []
    result={}
    for row in rows:
        labels=row['Config'].get('Labels',{});name=labels.get('com.docker.compose.service')
        if name not in SERVICES or name in result or labels.get('com.madar.staging.owner')!=manage.OWNER:
            raise RuntimeError('full_staging_unknown_actor')
        reference=configuration.INFRA_IMAGES.get(name,images['backend' if name in ('backend','notification-worker','deletion-worker') else 'frontend'])
        image=json.loads(manage.docker('image','inspect',reference))[0]
        memory,cpu=configuration.BOUNDS[name];host=row['HostConfig']
        if (row['Image']!=image['Id'] or host.get('RestartPolicy',{}).get('Name')!='no' or host.get('Privileged')
                or not 0<host.get('Memory',0)<=memory*1024**2 or not 0<host.get('NanoCpus',0)<=int(cpu*10**9)
                or not 0<host.get('PidsLimit',0)<=256 or any(m.get('Destination','').startswith('/app') for m in row.get('Mounts',[]))):
            raise RuntimeError('full_staging_runtime_identity_or_bounds')
        result[name]={'id':row['Id'],'image':row['Image'],'running':row['State']['Running'],
            'health':row['State'].get('Health',{}).get('Status','not-configured')}
    if complete and set(result)!=SERVICES:raise RuntimeError('full_staging_missing_actor')
    return result


def initialize(inventory,origin):
    """Fresh genesis only: no live database origin inference or history repair."""
    manage.compose('up','--detach','--wait','--wait-timeout','90','postgres','redis','auth','rest','storage','gateway')
    manage.require_database_marker()
    if manage.sql("select to_regclass('public.application_schema_state') is null;")!='t':
        raise RuntimeError('full_staging_fresh_database_required')
    deadline=time.monotonic()+90
    while manage.sql("select to_regclass('auth.users') is not null and to_regclass('storage.objects') is not null;")!='t':
        if time.monotonic()>deadline:raise RuntimeError('full_staging_native_provider_bootstrap_timeout')
        time.sleep(1)
    manage.configure_provider_access()
    manage.compose('stop','--timeout','15','gateway','auth','rest','storage')
    deadline=time.monotonic()+15
    while manage.sql("select (select count(*) from pg_stat_activity where pid<>pg_backend_pid() and backend_type='client backend')+(select count(*) from pg_prepared_xacts);")!='0':
        if time.monotonic()>deadline:raise RuntimeError('full_staging_unknown_session_or_prepared_transaction')
        time.sleep(.2)
    # Discover, authenticate and capture once from Git; never reopen SQL paths.
    for migration in inventory.migrations:
        if migration.number in inventory.excluded_versions or migration.number>origin:continue
        manage.require_database_marker()
        manage.sql("set lock_timeout='5s';set statement_timeout='45s';"+migration.sql.decode())
    if manage.sql("select schema_version from public.application_schema_state where contract_key='core';")!=str(origin):
        raise RuntimeError('full_staging_origin_bootstrap_failed')


def require_protocols(schema):
    if type(schema) is not int or not 1<=schema<10**9 or manage.sql(application.PROTOCOL_SQL)!=str(schema)+':2:2:2':
        raise RuntimeError('full_staging_native_worker_protocol_mismatch')


def main(mode,directory,source,baseline):
    if mode not in ('INSPECT','REHEARSE'):raise RuntimeError('full_staging_explicit_mode_required')
    project=identity(source);runtime=Path.home()/project
    require_host(runtime)
    inventory,plan=source_plan(source,baseline);value=plan.document();schema=value['target_schema']
    directory=Path(directory)
    if directory.is_symlink() or directory.parent!=Path.home():raise RuntimeError('full_staging_artifact_directory_scope')
    metadata=directory.stat()
    if metadata.st_uid!=os.getuid() or stat.S_IMODE(metadata.st_mode)!=0o700:
        raise RuntimeError('full_staging_artifact_directory_ownership')
    artifact=json.loads(configuration.regular(directory/'artifact.json'))
    run=json.loads(configuration.regular(directory/'run.json'))
    ci={name:json.loads(configuration.regular(directory/(name+'.json'))) for name in ('backend-check.yml','frontend-check.yml')}
    verify_required_ci(ci,source)
    # These staging API packets are obtained by the read-only trusted workflow;
    # they are not production evidence or authority. Native root admission must
    # requery APIs independently rather than trusting a local PASS packet.
    images=json.loads(configuration.regular(directory/'receipt.json'))['images']
    inputs={name:hashlib.sha256((manage.REPOSITORY/name).read_bytes()).hexdigest() for name in INPUTS}
    if mode=='INSPECT':
        from deployment.lib.schema148_artifacts import verify_archive
        verify_archive(directory/'candidate.zip',artifact,run,source_sha=source,images=images,expected_inputs=inputs)
        return {'mode':mode,'source_sha':source,'project':project,'plan_sha256':plan.sha256,
            'origin_schema':value['origin_schema'],'target_schema':schema,'mutations_executed':False,'production_authorized':False}
    if value['risk_class']=='D':raise RuntimeError('full_staging_exceptional_sql_requires_separate_review')
    started=time.monotonic()
    with lease(),target(source,schema):
        admission_headroom(runtime,project)
        # Reserve the attempt before parsing mutable artifacts. A failed capture
        # remains consumed, with no container/provider mutation or replay.
        capture=directory/'staging-capture'
        receipt=capture_candidate_archive(directory/'candidate.zip',capture,artifact,run,
            source_sha=source,images=images,expected_inputs=inputs)
        configuration.generate(runtime,source,images,receipt,
            {'DATABASE_PASSWORD':secrets.token_hex(32),'JWT_SECRET':secrets.token_hex(32)},project,project,
            target_schema=schema,fresh_database=True)
        manage.private_write('release-plan.json',plan.encoded.decode())
        manage.private_write('migration-inventory.json',canonical(inventory.document()).decode())
        try:
            with authenticated_archive(capture/'archive.zip',artifact['digest']) as archive:
                for role in ('backend','frontend'):
                    import_authenticated_image(archive,role,receipt['archives'][role],capture/(role+'.tar.gz'))
                    row=json.loads(manage.docker('image','inspect',images[role]))[0]
                    if row['Id']!=images[role]:raise RuntimeError('full_staging_imported_image_identity')
            for image in sorted(set(configuration.INFRA_IMAGES.values())):
                if not manage.docker('image','ls','--quiet',image).strip():manage.docker('pull',image,timeout=240)
            initialize(inventory,value['origin_schema'])
            checkpoints=[];migrations={migration.number:migration for migration in inventory.migrations}
            for step in value['migrations']:
                manage.require_database_marker()
                if manage.sql("select schema_version from public.application_schema_state where contract_key='core';")!=str(step['from_schema']):
                    raise RuntimeError('full_staging_migration_origin_changed')
                migration=migrations[step['number']]
                if migration.sha256!=step['sha256']:raise RuntimeError('full_staging_captured_sql_changed')
                boundary=time.monotonic()
                manage.sql("set lock_timeout='5s';set statement_timeout='45s';"+migration.sql.decode())
                observed=manage.sql("select schema_version from public.application_schema_state where contract_key='core';")
                if observed!=str(step['to_schema']):raise RuntimeError('full_staging_migration_commit_not_observed')
                checkpoints.append({'schema':int(observed),'sql_sha256':migration.sha256,'elapsed_seconds':round(time.monotonic()-boundary,3)})
                manage.private_write('migration-boundaries.json',json.dumps(checkpoints)+'\n')
            require_protocols(schema)
            manage.compose('up','--detach','--wait','--wait-timeout','180',*sorted(SERVICES))
            actors(images,complete=True);manage.require_database_marker()
            smoke.main();tenant_smoke.main()
            application.worker_health()
            deletion=application.deletion_workflow(expected_schema=schema)
            code=application.runtime_identity(images,source)
            runtime_rows=actors(images,complete=True)
            if not all(row['running'] for row in runtime_rows.values()):raise RuntimeError('full_staging_component_not_running')
            report={'version':1,'status':'PASS','scope':'fresh-synthetic-genesis-full-provider-application-acceptance',
                'source_sha':source,'history_base_sha':baseline,'project':project,'schema':schema,
                'origin_schema':value['origin_schema'],'plan_sha256':plan.sha256,'risk_class':value['risk_class'],
                'artifact_id':artifact['id'],'run_id':run['id'],'run_attempt':run['run_attempt'],
                'archive_sha256':artifact['digest'],'images':images,'runtime':runtime_rows,
                'worker_protocols':{'delivery':2,'outbox':2,'deletion':2},'migration_boundaries':checkpoints,
                'configuration_sha256':hashlib.sha256(configuration.regular(runtime/'verified-compose.json')).hexdigest(),
                'native_auth_mfa_refresh_csrf_storage_notifications_readiness':True,'native_tenant_read_write_isolation':True,
                'deletion_workflow':deletion,'runtime_code_sha256':code,'source_overlay_used':False,
                'elapsed_seconds':round(time.monotonic()-started,3),'stopped_after_acceptance':True,
                'protected_controller_execution':False,'production_authorized':False,
                'limitations':['synthetic genesis is not current-data preservation or independent restoration',
                    'no protected write handoff or privileged controller/reboot acceptance',
                    'not complete product browser, object-aware PITR or off-host recovery',
                    'schema151 native deletion protocol remains incompatible until separately coordinated correction']}
            manage.private_write('full-provider-acceptance.json',json.dumps(report,sort_keys=True,indent=2)+'\n')
            actors(images,complete=True);manage.compose('stop','--timeout','15')
            return report
        except BaseException:
            # A partial/unknown inventory refuses cleanup rather than touching
            # another project. Preserve failed data, queues and private logs.
            actors(images,complete=False);manage.compose('stop','--timeout','15')
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('INSPECT','REHEARSE'))
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--source-sha',required=True);parser.add_argument('--history-base-sha',required=True)
    args=parser.parse_args()
    print(json.dumps(main(args.mode,args.artifacts,args.source_sha,args.history_base_sha),sort_keys=True))

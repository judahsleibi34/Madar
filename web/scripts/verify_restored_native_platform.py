#!/usr/bin/env python3
"""Narrow native API restore validation from the exact received Node 1 copy.

Only NEW disposable targets on a NEW internal bridge are mutated. The original
backup, recovered evidence, production services and database are read-only.
No source credentials/HTTP response bodies are emitted. No application image is
built, business worker started or application migration executed. This helper
proves native core functionality only, not normal-source application acceptance.
"""
from datetime import datetime,timezone
import base64
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import struct
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.parse import quote
import urllib.request
import urllib.error
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deployment.lib.coordinated_checkpoint import verify_inventory,digest_file
from deployment.lib.coordinated_archive_restore import verify_restored_archive
from deployment.lib.environment_file import load_environment_file
from scripts.restore_coordinated_checkpoint import role_restore_sql,psql,run,IMAGE,ROLE_QUERY,ROLE_MEMBERSHIP_QUERY

ROOT=Path('/var/lib/madar-control-plane/normal-local-preparation')
SOURCE=ROOT/'offhost-restore-input-n1cv5bua'
QUARANTINE=ROOT/'restore-components-aloinivd'
STORAGE=ROOT/'restore-storage-metadata-eo7iqwvy/native/opt/madar/local-supabase/volumes/storage'
MANIFEST='4c3fe669e4c00e3e8221e8db304d55d5a463d6e3e53cfb0209320b3a8bb0feeb'
STAGE='entry'


def require(value,category):
    if not value:raise RuntimeError(category)


def stage(value):
    global STAGE
    STAGE=value;print(json.dumps({'event':'native_restore_stage','stage':value}),flush=True)


def totp(secret,counter=None):
    key=base64.b32decode(secret+'='*((-len(secret))%8))
    digest=hmac.new(key,struct.pack('>Q',int(time.time())//30 if counter is None else counter),hashlib.sha1).digest()
    offset=digest[-1]&15
    return str((struct.unpack('>I',digest[offset:offset+4])[0]&0x7fffffff)%1000000).zfill(6)


def fetch(url,*,headers=None,body=None,method=None):
    # No proxy or redirect can move secret-bearing requests outside the owned
    # private targets. URLs are constructed only from their measured addresses.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args):return None
    request=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json',**(headers or {})},method=method)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect)
    try:
        with opener.open(request,timeout=8) as response:return response.status,{key.lower():value for key,value in response.headers.items()},response.read()
    except urllib.error.HTTPError as error:return error.code,{key.lower():value for key,value in error.headers.items()},error.read()



def wait_for_storage(url, headers, inspect_target, *, deadline_seconds=90,
                     clock=time.monotonic, pause=time.sleep, request=fetch):
    """Retry connection replacement/startup only; reject exited targets or auth.

    Successful bytes and headers are checked separately for every restored
    object. No response body or container log is included in failure reports.
    """
    deadline=clock()+deadline_seconds
    while True:
        row=inspect_target()
        state=row.get('State',{})
        require(state.get('Running') is True,'native_restore_storage_exited')
        try:
            status,_,_=request(url+'/status',headers=headers)
            if status==200:return
            require(status in {502,503,504},'native_restore_storage_health_rejected')
        except (urllib.error.URLError,TimeoutError):
            pass
        require(clock()<deadline,'native_restore_storage_readiness_deadline')
        pause(min(1,max(0,deadline-clock())))


def available_subnet():
    ids=run(['docker','network','ls','-q']).splitlines()
    rows=json.loads(run(['docker','network','inspect',*ids]))
    used=[ipaddress.ip_network(entry['Subnet']) for row in rows for entry in row.get('IPAM',{}).get('Config') or [] if entry.get('Subnet')]
    used += [ipaddress.ip_network(row['dst'],strict=False) for row in json.loads(run(['ip','-j','route'])) if row.get('dst') not in {None,'default'}]
    for candidate in ipaddress.ip_network('10.252.0.0/16').subnets(new_prefix=24):
        if not any(candidate.overlaps(other) for other in used if other.version==4):return str(candidate)
    raise RuntimeError('private_native_network_capacity_unavailable')


def restore_storage_timestamps(archive,root):
    prefix='opt/madar/local-supabase/volumes/storage/'
    seen=set()
    with tarfile.open(archive,'r|gz') as tar:
        for member in tar:
            if not member.isfile():continue
            require(member.name.startswith(prefix),'native_storage_timestamp_path_invalid')
            relative=Path(member.name[len(prefix):]);require(not relative.is_absolute() and '..' not in relative.parts,'native_storage_timestamp_path_invalid')
            path=root/relative;require(path.is_file() and not path.is_symlink(),'native_storage_timestamp_file_missing')
            os.utime(path,(member.mtime,member.mtime),follow_symlinks=False);seen.add(relative.as_posix())
    require(seen=={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()},'native_storage_timestamp_inventory_changed')


def execute(*,existing_mfa_verifier=None):
    require(os.geteuid()==0 and sys.flags.isolated and sys.flags.dont_write_bytecode,'native_restore_frozen_root_required')
    require(digest_file(SOURCE/'manifest.json')==MANIFEST,'native_restore_manifest_changed')
    stage('verify_exact_received_inventory')
    manifest,inventory=verify_inventory(SOURCE)
    require(len(inventory)==13,'native_restore_inventory_incomplete')
    verify_restored_archive(SOURCE/'native-configuration.tar.gz',QUARANTINE/'native-configuration')
    native=QUARANTINE/'native-configuration/opt/madar/local-supabase'
    stage('render_inactive_native_configuration')
    rendered=json.loads(run(['docker','compose','--env-file',str(native/'.env'),'-f',str(native/'docker-compose.yml'),
        '-f',str(native/'docker-compose.madar-local.yml'),'config','--format','json']))
    config={};load_environment_file(native/'.env',environ=config)
    images=json.loads((SOURCE/'images.json').read_text())
    target=Path(tempfile.mkdtemp(prefix='private-native-runtime-',dir=ROOT));target.chmod(0o700)
    dump=target/'database.dump'
    shutil.copyfile(SOURCE/'database.dump',dump);dump.chmod(0o444)
    require(digest_file(dump)==inventory['database.dump'],'native_restore_dump_copy_changed')
    require(images['supabase-db']['image']==IMAGE,'native_restore_database_image_changed')
    stage('prepare_new_storage_input')
    shutil.copytree(STORAGE,target/'storage',copy_function=shutil.copy2)
    restore_storage_timestamps(SOURCE/'native-storage.tar.gz',target/'storage')
    prefix='madar-checkpoint-native-'+uuid.uuid4().hex[:12];network=prefix+'-network';db=prefix+'-db'
    created=[];created_network=False;auth_ids=[];started=datetime.now(timezone.utc).isoformat()
    subnet=available_subnet();endpoints={};runtimes={}
    def inspect(name):return json.loads(run(['docker','inspect',name]))[0]
    def endpoint(name,port):
        row=inspect(name);require(set(row['NetworkSettings']['Networks'])=={network} and row['Image']==runtimes[name]['image'],'native_restore_target_changed')
        require(not any(row['NetworkSettings']['Ports'].values()),'native_restore_public_binding')
        return 'http://'+row['NetworkSettings']['Networks'][network]['IPAddress']+':'+str(port)
    try:
        stage('restore_new_networkless_database')
        run(['docker','run','--pull','never','--detach','--name',db,'--network','none','--user','65534:65534',
            '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','2g','--cpus','2','--pids-limit','128',
            '--log-driver','none','--tmpfs','/tmp:rw,nosuid,nodev,size=64m,mode=1777','--tmpfs','/restore-data:rw,nosuid,nodev,size=2g,mode=1777',
            '--mount',f'type=bind,src={dump},dst=/backup.dump,readonly','--entrypoint','sh',IMAGE,'-ec',
            "initdb -D /restore-data/pgdata -U supabase_admin --auth=trust >/dev/null; exec postgres -D /restore-data/pgdata -k /tmp -c listen_addresses='*' -c log_statement=none -c log_min_error_statement=panic -c shared_preload_libraries=pg_cron,pg_net -c cron.launch_active_jobs=off -c pg_net.database_name=madar_restore_disabled"])
        created.append(db)
        for attempt in range(60):
            try:psql(db,'SELECT 1;');break
            except RuntimeError:
                if attempt==59:raise
                time.sleep(.5)
        require(psql(db,"SELECT current_setting('cron.launch_active_jobs')='off'; SELECT current_setting('pg_net.database_name')='madar_restore_disabled';").splitlines()==['t','t'],'native_restore_jobs_enabled')
        psql(db,role_restore_sql((SOURCE/'roles.sql').read_text()))
        psql(db,'DROP DATABASE postgres WITH (FORCE);',database='template1')
        run(['docker','exec',db,'pg_restore','--exit-on-error','--create','-h','/tmp','-U','supabase_admin','-d','template1','/backup.dump'])
        require(psql(db,"SELECT schema_version FROM public.application_schema_state WHERE contract_key='core';")=='115','native_restore_schema_invalid')
        require(psql(db,"SELECT count(*) FROM auth.users;")=='18','native_restore_auth_snapshot_changed')
        stage('verify_restored_roles_owners_and_integrity')
        private_roles=psql(db,ROLE_QUERY+'\n'+ROLE_MEMBERSHIP_QUERY).splitlines()
        source_roles=run(['docker','exec','-i','supabase-db','psql','-X','-U','postgres','-d','postgres','-At','-v','ON_ERROR_STOP=1'],
            sql='BEGIN READ ONLY;\n'+ROLE_QUERY+'\n'+ROLE_MEMBERSHIP_QUERY+'\nROLLBACK;\n').splitlines()[1:-1]
        require(private_roles==source_roles,'native_restore_role_attributes_changed')
        metadata=psql(db,"SELECT 'database_owner='||r.rolname FROM pg_database d JOIN pg_roles r ON r.oid=d.datdba WHERE d.datname=current_database(); SELECT 'invalid_indexes='||count(*) FROM pg_index WHERE NOT indisvalid; SELECT 'identities='||count(*) FROM auth.identities; SELECT 'factors='||count(*) FROM auth.mfa_factors;")
        integrity=dict(line.split('=',1) for line in metadata.splitlines())
        require(integrity=={'database_owner':'postgres','invalid_indexes':'0','identities':'18','factors':'2'},'native_restore_database_integrity_failed')
        # Native services must authenticate using the ORIGINAL restored roles and
        # verifiers. Only the private test CIDR is allowed; no trust-over-network.
        hba='local all all trust\nhost all all '+subnet+' scram-sha-256\n'
        run(['docker','exec','-i',db,'sh','-c','cat > /restore-data/pgdata/pg_hba.conf'],sql=hba)
        require(psql(db,'SELECT pg_reload_conf();')=='t','native_restore_hba_reload_failed')
        run(['docker','network','create','--internal','--driver','bridge','--subnet',subnet,network]);created_network=True
        run(['docker','network','disconnect','none',db])
        run(['docker','network','connect','--alias','db',network,db]);runtimes[db]={'image':IMAGE}
        stage('start_owned_private_native_apis')
        for role,port in [('auth',9999),('rest',3000),('storage',5000)]:
            name=prefix+'-'+role;image=images['supabase-'+role]['image'];service=rendered['services'][role]
            env={key:str(value) for key,value in service.get('environment',{}).items() if value is not None}
            require(not any(key.startswith(('LD_','PYTHON','DOCKER_','COMPOSE_','GIT_')) or key in {'PATH','HOME','SHELL','BASH_ENV','ENV','IFS','CDPATH'} for key in env),'native_restore_host_loader_override')
            if role=='storage':env.update(STORAGE_BACKEND='file',FILE_STORAGE_BACKEND_PATH='/var/lib/storage')
            args=['docker','create','--pull','never','--name',name,'--network',network,'--network-alias',role,
                '--restart','no','--log-driver','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
                '--memory','512m','--cpus','1','--pids-limit','128','--tmpfs','/tmp:rw,nosuid,nodev,size=64m,mode=1777']
            if role=='storage':args += ['--mount',f'type=bind,src={target}/storage,dst=/var/lib/storage']
            for key in env:args += ['--env',key]
            run(args+[image],timeout=90) if not env else run_env(args+[image],env)
            created.append(name);runtimes[name]={'image':image};run(['docker','start',name]);endpoints[role]=endpoint(name,port)
        service_key=config['SERVICE_ROLE_KEY'];anon_key=config['ANON_KEY']
        admin={'apikey':service_key,'Authorization':'Bearer '+service_key}
        for attempt in range(90):
            try:
                status,_,_=fetch(endpoints['auth']+'/health')
                status_rest,_,data=fetch(endpoints['rest']+'/application_schema_state?select=schema_version&contract_key=eq.core',headers=admin)
                require(status==200 and status_rest==200 and json.loads(data)==[{'schema_version':115}],'native_restore_api_pending')
                break
            except (RuntimeError,urllib.error.URLError,TimeoutError):
                if attempt==89:raise
                time.sleep(1)
        stage('wait_for_owned_storage_activation')
        wait_for_storage(endpoints['storage'],admin,lambda:inspect(prefix+'-storage'))
        stage('verify_restored_native_asset_bytes_and_headers')
        objects=json.loads(psql(db,"SELECT COALESCE(jsonb_agg(jsonb_build_object('bucket',bucket_id,'name',name,'version',version,'metadata',metadata)),'[]') FROM storage.objects;"))
        total=0;ranges=0
        for obj in objects:
            relative=Path('stub/stub')/obj['bucket']/obj['name']/obj['version'];local=target/'storage'/relative
            require(local.is_relative_to(target/'storage') and '..' not in relative.parts,'native_restore_asset_path_invalid')
            path='/object/authenticated/'+quote(obj['bucket'],safe='')+'/'+quote(obj['name'],safe='/')
            status,headers,data=fetch(endpoints['storage']+path,headers=admin)
            require(status==200 and hashlib.sha256(data).hexdigest()==digest_file(local),'native_restore_asset_bytes_failed')
            require(headers.get('content-type','').split(';')[0]==obj['metadata']['mimetype'],'native_restore_asset_mime_failed')
            require(headers.get('cache-control')==obj['metadata']['cacheControl'],'native_restore_asset_cache_failed')
            if data:
                status,headers,part=fetch(endpoints['storage']+path,headers={**admin,'Range':'bytes=0-0'})
                require(status==206 and part==data[:1] and headers.get('content-range','').startswith('bytes 0-0/'),'native_restore_asset_range_failed');ranges+=1
            total+=len(data)
        existing_mfa_result=None
        if existing_mfa_verifier is not None:
            stage('verify_original_factors_in_private_restore')
            existing_mfa_result=existing_mfa_verifier(db,endpoints,config)
        stage('verify_native_authentication_and_aal2')
        email='checkpoint-native-'+uuid.uuid4().hex+'@example.invalid';password=secrets.token_urlsafe(32)
        status,_,data=fetch(endpoints['auth']+'/admin/users',headers=admin,body={'email':email,'password':password,'email_confirm':True})
        require(status in {200,201},'native_restore_fixture_create_failed');user=json.loads(data);auth_ids.append(user['id'])
        status,_,data=fetch(endpoints['auth']+'/token?grant_type=password',headers={'apikey':anon_key},body={'email':email,'password':password})
        require(status==200,'native_restore_login_failed');session=json.loads(data);token=session['access_token']
        user_header={'apikey':anon_key,'Authorization':'Bearer '+token}
        status,_,data=fetch(endpoints['auth']+'/factors',headers=user_header,body={'factor_type':'totp','friendly_name':'Disposable checkpoint verification'})
        require(status in {200,201},'native_restore_mfa_enroll_failed');factor=json.loads(data)
        status,_,data=fetch(endpoints['auth']+'/factors/'+factor['id']+'/challenge',headers=user_header,body={})
        require(status==200,'native_restore_mfa_challenge_failed');challenge=json.loads(data)
        status,_,data=fetch(endpoints['auth']+'/factors/'+factor['id']+'/verify',headers=user_header,body={'challenge_id':challenge['id'],'code':totp(factor['totp']['secret'])})
        require(status==200,'native_restore_mfa_verify_failed');session=json.loads(data);token=session['access_token']
        payload=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'='*((-len(token.split('.')[1]))%4)))
        require(payload.get('aal')=='aal2' and payload.get('sub')==user['id'],'native_restore_aal2_failed')
        status,_,_=fetch(endpoints['auth']+'/user',headers={'apikey':anon_key,'Authorization':'Bearer '+token})
        require(status==200,'native_restore_aal2_user_failed')
        stage('remove_only_synthetic_identity')
        for identifier in auth_ids:
            status,_,_=fetch(endpoints['auth']+'/admin/users/'+identifier,headers=admin,method='DELETE')
            require(status in {200,204},'native_restore_fixture_cleanup_failed')
        auth_ids.clear();require(psql(db,'SELECT count(*) FROM auth.users;')=='18','native_restore_fixture_remaining')
        for name in created:
            row=inspect(name);require(row['Image']==runtimes[name]['image'] and set(row['NetworkSettings']['Networks'])=={network} and not any(row['NetworkSettings']['Ports'].values()),'native_restore_target_changed')
            runtimes[name]['id']=row['Id']
        require(verify_inventory(SOURCE)[1]==inventory,'native_restore_original_changed')
        return {'operation':'actual-offhost-private-native-core-restore','checkpoint_manifest_sha256':MANIFEST,
            'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),'restored_files':inventory,
            'schema':115,'database_integrity':integrity,'role_attributes_password_verifiers_and_grantors_verified':True,'owners_and_acls_restored':True,'database_network_during_restore':'none','runtime_network':'isolated-internal',
            'network_id':json.loads(run(['docker','network','inspect',network]))[0]['Id'],'runtimes':runtimes,
            'storage_objects':len(objects),'asset_bytes':total,'range_checks':ranges,'mime_cache_verified':True,
            'native_login_and_aal2_verified':True,'existing_factor_verification':existing_mfa_result,'synthetic_identity_removed':True,'customer_passwords_used':False,
            'production_modified':False,'application_migrations_executed':False,'business_consumers_started':False,
            'application_acceptance_proven':False,'tenant_isolation_proven':False,'full_eleven_service_platform_proven':False,
            'original_checkpoint_modified':False,'runtime_input':str(target)}
    finally:
        # Only targets created by this invocation; never an existing resource.
        for name in reversed(created):
            try:run(['docker','rm','--force',name],timeout=30)
            except Exception as error:
                print(json.dumps({'event':'native_restore_cleanup_failed','resource':name,'exception_type':type(error).__name__}),flush=True)
        if created_network:
            try:run(['docker','network','rm',network],timeout=30)
            except Exception as error:
                print(json.dumps({'event':'native_restore_cleanup_failed','resource':network,'exception_type':type(error).__name__}),flush=True)


def run_env(args,env):
    result=subprocess.run(args,capture_output=True,text=True,timeout=90,env={**env,'PATH':'/usr/bin:/bin','HOME':'/root','LANG':'C.UTF-8'})
    if result.returncode:raise RuntimeError('native_restore_container_create_failed')
    return result.stdout.strip()

if __name__=='__main__':
    def expired(*args):raise RuntimeError('native_restore_deadline')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,600)
    try:print(json.dumps(execute()))
    except Exception as error:
        print(json.dumps({'operation':'actual-offhost-private-native-core-restore','status':'failed','stage':STAGE,'exception_type':type(error).__name__,
            'failure_category':str(error) if type(error) is RuntimeError else 'native_restore_failed'}));raise SystemExit(1)
    finally:signal.setitimer(signal.ITIMER_REAL,0)

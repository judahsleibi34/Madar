#!/usr/bin/env python3
"""Actual final-image API acceptance against an owned restored schema115 fixture.

No production writes, original passwords, migrations or external integrations.
Every image is content-addressed. Original MFA secrets remain memory-only. The
private commercial fixtures exercise the existing authorization RPC unchanged.
"""
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
import json
import hashlib
import subprocess
import os
from pathlib import Path
import re
import secrets
import signal
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.verify_restored_native_platform import execute, QUARANTINE, fetch, require, totp, run_env
from scripts.restore_coordinated_checkpoint import run,psql
from deployment.lib.environment_file import load_environment_file
from deployment.lib.provider_recovery_runtime import protected,readonly_configuration,file_digest
from deployment.lib.active_recovery_artifact_evidence import CASES,NODE1_CONFIGURATION

INPUT=Path(__file__).resolve().parents[3]/'inputs.json'
CASES_OBSERVED={}

def observed(name, **values):
    require(name in CASES and values,'artifact_case_invalid')
    CASES_OBSERVED[name]={'verified':True,'observations':values}
    print(json.dumps({'event':'artifact_case_complete','case':name}),flush=True)

def quote(value):return "'"+str(value).replace("'","''")+"'"

class Session:
    def __init__(self,base):self.base=base;self.cookies={};self.csrf=''
    def request(self,path,body=None,method=None):
        headers={'User-Agent':'Madar-owned-artifact-verifier/1','Origin':'https://madarportal.com',
            'X-Forwarded-Proto':'https','X-Madar-Builder-Contract':'cloud-draft-v1'}
        if self.cookies:headers['Cookie']='; '.join(key+'='+value for key,value in self.cookies.items())
        if self.csrf:headers['X-CSRF-Token']=self.csrf
        if body is not None:headers['Content-Type']='application/json'
        req=urllib.request.Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers=headers,method=method)
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args):return None
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect)
        try:response=opener.open(req,timeout=10)
        except urllib.error.HTTPError as error:response=error
        with response:
            raw=response.read(2*1024*1024);code=response.code
            cookie_headers=response.headers.get_all('Set-Cookie',[])
            for value in cookie_headers:
                cookie=SimpleCookie();cookie.load(value)
                for key,item in cookie.items():
                    if item.value:self.cookies[key]=item.value
                    else:self.cookies.pop(key,None)
            try:payload=json.loads(raw)
            except ValueError:payload=None
            if isinstance(payload,dict) and payload.get('csrf_token'):self.csrf=payload['csrf_token']
            return code,payload,cookie_headers,raw
    def ok(self,path,body=None,method=None):
        code,payload,_,_=self.request(path,body,method)
        require(code in {200,201,204},'artifact_api_case_failed:'+path.split('?')[0])
        return payload


def verify_images(inputs):
    require(re.fullmatch('[0-9a-f]{40}',inputs['source_sha']) is not None,'artifact_source_invalid')
    require(set(inputs['images'])=={'backend','frontend'},'artifact_images_missing')
    created=set()
    for image in inputs['images'].values():
        require(re.fullmatch('sha256:[0-9a-f]{64}',image) is not None,'artifact_image_not_pinned')
        row=json.loads(run(['docker','image','inspect',image]))[0]
        require(row['Id']==image and row['Config']['Labels'].get('org.opencontainers.image.revision')==inputs['source_sha'], 'artifact_image_source_changed')
        created.add(row['Config']['Labels'].get('org.opencontainers.image.created'))
    require(len(created)==1 and None not in created and '' not in created,'artifact_build_pair_changed')


def verify_backend_source_contents(inputs):
    # A revision label alone cannot establish image/source provenance. Compare
    # actual immutable application bytes with the exact tracked Git revision.
    def git(*arguments):
        result=subprocess.run(['/usr/bin/git','-c','safe.directory=/opt/madar-development/repository','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false',*arguments],cwd='/opt/madar-development/repository',capture_output=True,timeout=30)
        require(result.returncode==0,'artifact_git_source_unavailable')
        return result.stdout
    names=git('ls-tree','-r','--name-only',inputs['source_sha'],'--','web/backend').decode().splitlines()
    expected={}
    for name in names:
        relative=name.removeprefix('web/backend/')
        if (name.endswith('.py') and not relative.startswith('cv_reranker/')) or relative in {'requirements.txt','constraints.txt'}:
            expected[relative]=hashlib.sha256(git('show',inputs['source_sha']+':'+name)).hexdigest()
    require(expected and 'app.py' in expected,'artifact_backend_inventory_missing')
    code="import hashlib,json,pathlib,sys;expected=json.load(sys.stdin);actual={name:hashlib.sha256((pathlib.Path('/app')/name).read_bytes()).hexdigest() for name in expected};assert actual==expected;print(json.dumps({'files':len(actual),'source_bytes_verified':True}))"
    result=json.loads(run(['docker','run','--pull','never','--rm','-i','--network','none',
        '--name','normal-artifact-source-'+uuid.uuid4().hex[:12],'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--entrypoint','python',inputs['images']['backend'],'-I','-B','-c',code],sql=json.dumps(expected)))
    require(result=={'files':len(expected),'source_bytes_verified':True},'artifact_backend_source_contents_changed')
    return result


def application_cases(db,endpoints,native):
    inputs=json.loads(protected(INPUT,private=True).read_text());verify_images(inputs)
    verified_source=verify_backend_source_contents(inputs)
    prefix='normal-acceptance-'+uuid.uuid4().hex[:12]
    network=db[:-3]+'-network';rows=json.loads(run(['docker','network','inspect',network]))
    require(rows[0]['Internal'] is True,'artifact_network_not_isolated')
    cfg={};local=Path('/var/lib/madar-control-plane/local-provider-transition/configuration.env')
    load_environment_file(protected(local,private=True),environ=cfg)
    require(file_digest(local)==inputs['local_configuration_sha256'],'artifact_local_configuration_changed')
    require(cfg['SUPABASE_ANON_KEY']==native['ANON_KEY'] and cfg['SUPABASE_SERVICE_KEY']==native['SERVICE_ROLE_KEY'], 'artifact_native_keys_incompatible')
    created=[];original_verifiers=[];private_projects=[]
    target=Path(tempfile.mkdtemp(prefix='artifact-private-',dir=str(INPUT.parent)))
    authority=target/'authority';authority.mkdir(mode=0o755)
    health=target/'health';health.mkdir(mode=0o755)
    marker={'format':2,'scope':'complete-coordinated-checkpoint','schema':115,'checkpoint_id':'checkpoint-20261008T224529Z',
        'created_at':inputs['checkpoint_created_at'],'verified':True,'manifest_sha256':inputs['checkpoint_manifest_sha256'],
        'execution_sha256':inputs['checkpoint_execution_sha256']}
    (health/'latest.json').write_text(json.dumps(marker));(health/'latest.json').chmod(0o444)
    contract=uuid.uuid4().hex*2
    def mode(value):
        document={'version':1,'schema':115,'release_sha':inputs['source_sha'],'contract_digest':contract,'mode':value}
        temporary=authority/'new.json';temporary.write_text(json.dumps(document));temporary.chmod(0o444);os.replace(temporary,authority/'authority.json')
    def inspect(name):return json.loads(run(['docker','inspect',name]))[0]
    def endpoint(name,port):return 'http://'+inspect(name)['NetworkSettings']['Networks'][network]['IPAddress']+':'+str(port)
    def create(kind,image,alias,environment=None,command=None,mounts=()):
        require(not any(key.startswith(('LD_','PYTHON','DOCKER_','COMPOSE_','GIT_')) or key in {'PATH','HOME','SHELL','BASH_ENV','ENV','IFS','CDPATH'} for key in environment or {}),'artifact_loader_environment_rejected')
        name=prefix+'-'+kind
        args=['docker','create','--pull','never','--name',name,'--network',network,'--network-alias',alias,
            '--restart','no','--log-driver','none','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--memory','1g','--pids-limit','256']
        for mount in mounts:args+=['--mount',mount]
        for key in environment or {}:args+=['--env',key]
        run_env(args+[image]+(command or []),environment or {});created.append(name)
        run(['docker','start',name]);return name
    def ready(check):
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            try:return check()
            except (urllib.error.URLError,TimeoutError,ConnectionError):time.sleep(1)
            except RuntimeError as error:
                if str(error) not in {'artifact_startup_pending'}:raise
                time.sleep(1)
        raise RuntimeError('artifact_startup_deadline')
    try:
        mode('READ_ONLY')
        gateway=inspect('supabase-envoy');gateway_env={x.split('=',1)[0]:x.split('=',1)[1] for x in gateway['Config']['Env']
            if x.split('=',1)[0] not in {'PATH','DEBIAN_FRONTEND'}}
        native_dir=QUARANTINE/'native-configuration/opt/madar/local-supabase/volumes/api/envoy'
        mounts=[f'type=bind,src={native_dir}/{name},dst={dest},readonly' for name,dest in [
            ('docker-entrypoint.sh','/docker-entrypoint.sh'),('cds.yaml','/etc/envoy/cds.yaml'),
            ('envoy.yaml','/etc/envoy/envoy.yaml'),('lds.template.yaml','/etc/envoy/lds.template.yaml')]]
        gw=create('gateway',gateway['Image'],'madar-supabase',gateway_env,mounts=mounts)
        redis_image=inspect('madar-provider402-rehearsal-94750f00e0d3-candidate-redis')['Image']
        redis=create('redis',redis_image,'redis',command=['redis-server','--save','','--appendonly','no'])
        cfg.update(APP_ENV='production',MADAR_ENV_FILE='/tmp/no-env',MADAR_ENV_OVERRIDE='false',
            MADAR_RELEASE_SHA=inputs['source_sha'],MADAR_RELEASE_SLOT='green',SCHEMA_COMPATIBLE_MIN='115',SCHEMA_COMPATIBLE_MAX='115',
            REDIS_URL='redis://redis:6379/0',COOKIE_SECURE='true',ADMIN_MFA_LOGIN_ENFORCEMENT='true',RATE_LIMIT_FAIL_OPEN='false',RATE_LIMIT_ENABLED='true',
            NOTIFICATION_WORKER_ENABLED='true',CALENDAR_SYNC_WORKER_ENABLED='true',DATA_DELETION_WORKER_ENABLED='true',
            NOTIFICATION_WORKER_REQUIRED='true',DATA_DELETION_WORKER_REQUIRED='true',CALENDAR_SYNC_REQUIRED='true',
            NOTIFICATION_WORKER_HEALTH_HOST='0.0.0.0',CALENDAR_SYNC_WORKER_HEALTH_HOST='0.0.0.0',DATA_DELETION_WORKER_HEALTH_HOST='0.0.0.0',
            NOTIFICATION_WORKER_HEALTH_URL='http://notification-worker:8090/health',CALENDAR_SYNC_WORKER_HEALTH_URL='http://calendar-sync-worker:8091/health',
            DATA_DELETION_WORKER_HEALTH_URL='http://data-deletion-worker:8094/health',EMAIL_CHANNEL_ENABLED='false',
            PARSER_ISOLATED_WORKER_ENABLED='true',PARSER_WORKER_URL='http://parser:8000',PARSER_WORKER_HEALTH_URL='http://parser:8000/health',
            REMOTE_INGESTION_ENABLED='false',ALLOW_REMOTE_DATASET_URLS='false',AI_ALLOW_LOCAL_EXEC='false',
            PUBLIC_UPLOADS_DIR='/tmp/app-public',DATA_UPLOAD_DIR='/tmp/app-private',PRIVATE_CHARTS_DIR='/tmp/app-charts',
            BACKUP_FRESHNESS_REQUIRED='true',BACKUP_FRESHNESS_MARKER='/run/madar/backup-state/latest.json',
            MADAR_BUSINESS_WRITE_AUTHORITY='/run/madar/business-write-authority/authority.json',MADAR_BUSINESS_WRITE_CONTRACT=contract)
        cfg.pop('MADAR_RECOVERY_PROFILE',None)
        mounts=[f'type=bind,src={authority},dst=/run/madar/business-write-authority,readonly',
            f'type=bind,src={health},dst=/run/madar/backup-state,readonly']
        parser=create('parser',inputs['images']['backend'],'parser',{'PARSER_WORKER_HEALTH_HOST':'0.0.0.0','DATA_UPLOAD_DIR':'/tmp/parser'},['python','-m','workers.parser_worker'])
        worker_names={kind:create(kind,inputs['images']['backend'],kind+'-worker',cfg,
            ['python','-m','workers.'+kind.replace('-','_')+'_worker'],mounts) for kind in ('notification','calendar-sync','data-deletion')}
        backend=create('backend',inputs['images']['backend'],'backend',cfg,mounts=mounts)
        frontend=create('frontend',inputs['images']['frontend'],'frontend',{'MADAR_CSP_CONNECT_SRC':"'self' https://api.madarportal.com",'MADAR_PUBLIC_SITE_DOMAIN':'madarportal.com','MADAR_HSTS':'max-age=31536000'})
        session=Session(endpoint(backend,8000));front=Session(endpoint(frontend,8080))
        def startup():
            code,version,_,_=session.request('/health/version')
            require(code==200,'artifact_startup_pending')
            require(version['release_sha']==inputs['source_sha'],'artifact_version_changed')
        ready(startup)
        require(front.request('/')[0]==200 and front.ok('/api/health/version')==session.ok('/health/version'),'artifact_frontend_origin_failed')
        html=front.request('/')[3].decode()
        scripts=re.findall(r'<script[^>]+src=[\"\']([^\"\']+)[\"\']',html)
        require(scripts and all(path.startswith('/assets/') for path in scripts),'artifact_frontend_bundle_missing')
        bundle=front.request(scripts[0])[3]
        require(b'\"/api\"' in bundle or b"'/api'" in bundle,'artifact_frontend_compiled_origin_wrong')
        require(b'madar-supabase:8000' not in bundle and b'127.0.0.1:8201' not in bundle,'artifact_frontend_internal_origin_leaked')
        observed('frontend_api_origin',http_status=200,same_image_release=True,api_origin='/api',compiled_bundle_checked=True)
        require(psql(db,"SELECT schema_version FROM public.application_schema_state WHERE contract_key='core';")=='115','artifact_schema_changed')
        observed('local_schema115',schema=115,migrations_executed=False)
        require(session.ok('/health/recovery')=={'restricted':True,'business_writes_enabled':False},'artifact_initial_fence_failed')
        require(session.request('/builder/projects',{'name':'denied','slug':'denied','draft_schema':{}})[0]==503,'artifact_restricted_write_failed')
        observed('restricted_write_denial',http_status=503)
        def workers(consuming):
            for kind,name in worker_names.items():
                port={'notification':8090,'calendar-sync':8091,'data-deletion':8094}[kind]
                code,_,data=fetch(endpoint(name,port)+'/health');value=json.loads(data)
                require(code==200 and value.get('consuming') is consuming,'artifact_startup_pending')
                require(value.get('healthy') is True if kind=='calendar-sync' else value.get('status')=='ok','artifact_worker_health_failed')
        ready(lambda:workers(False))
        factors=json.loads(psql(db,"SELECT jsonb_agg(jsonb_build_object('factor_id',f.id,'user_id',u.id,'secret',f.secret,'email',u.email,'verifier',u.encrypted_password)) FROM auth.mfa_factors f JOIN auth.users u ON u.id=f.user_id WHERE f.status='verified' AND f.factor_type='totp';"))
        require(len(factors)==2,'artifact_original_factors_changed')
        admin_headers={'apikey':native['SERVICE_ROLE_KEY'],'Authorization':'Bearer '+native['SERVICE_ROLE_KEY']}
        admins=[];aal1_denials=[]
        for factor in factors:
            original_verifiers.append((factor['user_id'],factor['verifier']));password=secrets.token_urlsafe(32)
            code,_,_=fetch(endpoints['auth']+'/admin/users/'+factor['user_id'],headers=admin_headers,method='PUT',body={'password':password});require(code==200,'artifact_private_password_setup_failed')
            login=Session(endpoint(backend,8000));code,result,headers,_=login.request('/auth/login',{'email':factor['email'],'password':password})
            require(code==200 and result.get('mfa_required') is True and 'madar_access_token' not in login.cookies,'artifact_aal1_session_escaped')
            status_code,status_body,_,_=login.request('/auth/user_status')
            require(status_code==200 and status_body.get('logged_in') is False,'artifact_aal1_session_escaped')
            denied_code=login.request('/admin/profile/info')[0]
            require(denied_code in {401,403},'artifact_aal1_privilege_not_denied');aal1_denials.append(denied_code)
            pending=[x for x in headers if x.startswith('madar_mfa_pending=')]
            require(len(pending)==1 and all(x in pending[0] for x in ('HttpOnly','Secure','SameSite=lax','Path=/')),'artifact_pending_cookie_unsafe')
            challenge=login.ok('/auth/mfa/login/challenge',{'factor_id':factor['factor_id']})
            result=login.ok('/auth/mfa/login/verify',{'factor_id':factor['factor_id'],'challenge_id':challenge['challenge_id'],'code':totp(factor['secret'])})
            status=login.ok('/auth/user_status');require(status.get('logged_in') is True,'artifact_existing_session_failed')
            import base64
            token=login.cookies['madar_access_token'].split('.')[1]
            claims=json.loads(base64.urlsafe_b64decode(token+'='*((-len(token))%4)))
            require(claims.get('aal')=='aal2' and claims.get('sub')==factor['user_id'],'artifact_backend_aal2_failed')
            admins.append(login)
        observed('existing_authentication',existing_accounts=2,private_known_passwords_only=True,actual_image_source_files=verified_source['files'])
        observed('original_mfa_aal2',original_factors=2,backend_aal2_verified=True)
        observed('aal1_privilege_denied',http_statuses=aal1_denials,user_status_logged_in=False,ordinary_session_issued_before_mfa=False)
        observed('session_cookie_policy',pending_http_only=True,secure=True,same_site='lax',path='/')
        mode('NORMAL');ready(lambda:workers(True))
        require(session.ok('/health/recovery')=={'restricted':False,'business_writes_enabled':True},'artifact_private_normal_failed')
        # Privileged primary accounts cannot acquire tenant-owner business scope.
        require(admins[0].request('/builder/projects',{'name':'scope','slug':'scope','draft_schema':{}})[0]==403,'artifact_admin_business_scope_escaped')
        observed('business_permissions',admin_owner_scope_denied_http_status=403)
        # Actual tenant-owner work is exercised by restored active memberships.
        owners=json.loads(psql(db,"SELECT jsonb_agg(x) FROM (SELECT DISTINCT ON(m.tenant_id) m.tenant_id,u.id,u.auth_id,u.email,a.encrypted_password AS verifier FROM public.tenant_memberships m JOIN public.users u ON u.id=m.user_id JOIN auth.users a ON a.id=u.auth_id WHERE m.status='active' AND m.role='owner' AND u.user_type='user' AND u.account_kind='platform' AND u.account_status='active' ORDER BY m.tenant_id,u.id LIMIT 2) x;"))
        require(owners and len(owners)==2,'artifact_two_owner_fixtures_unavailable')
        owner_sessions=[]
        admin_id=psql(db,"SELECT id FROM public.users WHERE user_type='admin' ORDER BY id LIMIT 1;")
        for owner in owners:
            state=json.loads(psql(db,'SELECT public.resolve_commercial_access('+str(owner['tenant_id'])+');'))
            modern=psql(db,"SELECT EXISTS(SELECT 1 FROM public.commercial_price_books WHERE sales_start_at<=statement_timestamp() AND (sales_end_at IS NULL OR sales_end_at>statement_timestamp()));")=='t'
            def commercial(operation,request):
                command='SELECT public.apply_commercial_access_command('+str(owner['tenant_id'])+','+admin_id+",'aal2',"+quote(operation)+','+quote(str(uuid.uuid4()))+",'private-artifact-case',"+quote(json.dumps({'request':request,'quote':{}}))+'::jsonb);'
                psql(db,command)
            if modern:
                commercial('assign_modules',{'reason':'Owned private artifact fixture','expected_revision':state['revision'],'module_ids':['forms','website','ecommerce'],'price_books':{}})
                state=json.loads(psql(db,'SELECT public.resolve_commercial_access('+str(owner['tenant_id'])+');'))
            request={'reason':'Owned private artifact fixture','expected_revision':state['revision'],
                'valid_from':datetime.now(timezone.utc).isoformat(),'valid_until':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
            request.update({'module_ids':['forms','website','ecommerce']} if modern else {'plan_id':'business_plus'})
            commercial('complimentary',request)
            password=secrets.token_urlsafe(32);original_verifiers.append((str(owner['auth_id']),owner['verifier']))
            code,_,_=fetch(endpoints['auth']+'/admin/users/'+str(owner['auth_id']),headers=admin_headers,method='PUT',body={'password':password});require(code==200,'artifact_owner_password_setup_failed')
            owner_login=Session(endpoint(backend,8000));owner_login.ok('/auth/login',{'email':owner['email'],'password':password});owner_sessions.append(owner_login)
        first,second=owner_sessions
        project=first.ok('/builder/projects',{'name':'Owned artifact test','slug':'artifact-'+uuid.uuid4().hex[:12],
            'draft_schema':{'forms':[],'pages':[]}})['project'];private_projects.append(project['id'])
        path='/builder/projects/'+project['id']
        first.ok(path);require(second.request(path)[0]==404,'artifact_cross_tenant_access_failed')
        require(second.request(path,{'name':'denied cross-tenant edit','expected_revision':project['draft_revision']},'PUT')[0]==404,'artifact_cross_tenant_write_failed')
        code,_,body=fetch(endpoints['rest']+'/builder_projects?select=id&id=eq.'+project['id'],
            headers={'apikey':native['ANON_KEY'],'Authorization':'Bearer '+second.cookies['madar_access_token']})
        require(code==200 and json.loads(body)==[],'artifact_native_rls_tenant_leak')
        observed('tenant_isolation',distinct_tenants=2,cross_tenant_read_http_status=404,cross_tenant_write_http_status=404,native_rls_rows=0)
        observed('private_normal_write_activation',authorized_project_creation_http_status=200,production_modified=False)
        form_id=str(uuid.uuid4());reservation_id=str(uuid.uuid4())
        psql(db,"INSERT INTO public.builder_form_submissions(id,tenant_id,project_id,form_id,answers,status) VALUES("+quote(form_id)+','+str(owners[0]['tenant_id'])+','+quote(project['id'])+",'artifact-form','{}','new');")
        first.ok(path+'/form-submissions/'+form_id,{'status':'contacted'},'PUT')
        require(psql(db,'SELECT status FROM public.builder_form_submissions WHERE id='+quote(form_id)+';')=='contacted','artifact_form_write_not_persisted')
        observed('forms',authorized_submission_update=True,private_persistence_verified=True)
        psql(db,"INSERT INTO public.builder_reservations(id,tenant_id,project_id,customer_name,status) VALUES("+quote(reservation_id)+','+str(owners[0]['tenant_id'])+','+quote(project['id'])+",'Owned private fixture','new');")
        first.ok('/builder/reservations/'+reservation_id+'/status',{'status':'confirmed'},'PATCH')
        require(psql(db,'SELECT status FROM public.builder_reservations WHERE id='+quote(reservation_id)+';')=='confirmed','artifact_reservation_write_not_persisted')
        observed('reservations',authorized_status_update=True,private_persistence_verified=True)
        first.ok(path,{'name':'Owned artifact revised','draft_schema':{'pages':[],'forms':[]},'expected_revision':project['draft_revision']},'PUT')
        first.ok(path,method='DELETE');private_projects.remove(project['id'])
        observed('builder',create_read_update_delete=True)
        tag=first.ok('/ecommerce/tags',{'slug':'artifact-'+uuid.uuid4().hex[:12],'translations':{'en':{'name':'Owned artifact tag'}}})
        identifier=tag.get('id') or tag.get('tag',{}).get('id')
        require(identifier,'artifact_ecommerce_tag_identity_missing')
        first.ok('/ecommerce/tags/'+str(identifier),method='DELETE');first.ok('/ecommerce/orders')
        observed('schema115_ecommerce',catalog_create_delete=True,orders_read=True,higher_schema_features_not_enabled=True)
        def normal_ready():
            code,result,_,_=session.request('/health/ready')
            require(code==200 and result.get('ready') is True,'artifact_startup_pending')
            return result
        readiness=ready(normal_ready)
        observed('backend_readiness',http_status=200,ready=True,components=readiness['components'])
        observed('singleton_workers',workers=3,nonconsuming_before_grant=True,consuming_after_private_grant=True)
        observed('required_integrations',components=readiness['components'],email_channel_enabled=False,isolated_parser=True)
        marker_row=psql(db,"SELECT count(*) FROM public.users;")
        mode('READ_ONLY');ready(lambda:workers(False))
        require(session.request('/builder/projects',{'name':'denied','slug':'denied','draft_schema':{}})[0]==503 and psql(db,'SELECT count(*) FROM public.users;')==marker_row,'artifact_runtime_rollback_failed')
        observed('rollback_current_data',write_denied=True,consumer_fenced=True,customer_database_restored=False)
        require(set(CASES_OBSERVED)==CASES,'artifact_acceptance_incomplete')
        for name in created:
            row=inspect(name)
            require(set(row['NetworkSettings']['Networks'])=={network} and not any(row['NetworkSettings']['Ports'].values()),'artifact_fixture_escape')
        verify_images(inputs)
        return {'cases':CASES_OBSERVED,'images':inputs['images'],'source_sha':inputs['source_sha']}
    finally:
        # Preserve original private password verifiers even when a test fails.
        for auth_id,verifier in original_verifiers:
            psql(db,'UPDATE auth.users SET encrypted_password='+quote(verifier)+' WHERE id='+quote(auth_id)+';')
        for name in reversed(created):run(['docker','rm','--force',name])


def main():
    require(os.geteuid()==0 and sys.flags.isolated and sys.flags.dont_write_bytecode,'artifact_frozen_root_required')
    inputs=json.loads(protected(INPUT,private=True).read_text())
    started=datetime.now(timezone.utc).isoformat()
    report=execute(existing_mfa_verifier=application_cases)
    result=report['existing_factor_verification']
    cfg={};load_environment_file(readonly_configuration(NODE1_CONFIGURATION,private=True),environ=cfg)
    require(cfg.get('MADAR_NODE1_SSH_HOST','madar-node1-lan')=='madar-node1-lan','artifact_replica_host_changed')
    output={'operation':'actual-final-application-artifact-acceptance','started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
        'source_sha':inputs['source_sha'],'images':inputs['images'],'cases':result['cases'],
        'checkpoint_manifest_sha256':inputs['checkpoint_manifest_sha256'],'local_configuration_sha256':inputs['local_configuration_sha256'],
        'schema':115,'migrations_executed':False,'production_modified':False,'private_fixture_only':True,
        'node1_replica':{'host':'madar-node1-lan','filesystem_uuid':cfg['MADAR_NODE1_FILESYSTEM_UUID'],
            'configuration_sha256':file_digest(NODE1_CONFIGURATION)}}
    print(json.dumps(output,sort_keys=True))

if __name__=='__main__':
    def expired(*args):raise RuntimeError('artifact_acceptance_deadline')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,1200)
    try:main()
    except Exception as error:
        print(json.dumps({'operation':'actual-final-application-artifact-acceptance','status':'failed',
            'exception_type':type(error).__name__,'category':str(error) if type(error) is RuntimeError else 'artifact_acceptance_failed'}),flush=True)
        raise SystemExit(1)
    finally:signal.setitimer(signal.ITIMER_REAL,0)

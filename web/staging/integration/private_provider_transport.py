"""Disposable native146 provider/transport integration, not protected admission."""
import argparse,hashlib,json,os,secrets,shutil,subprocess,sys,time,traceback
from datetime import datetime,timezone
import re,signal
from pathlib import Path
ROOT=Path('/opt/madar-development/repository');sys.path[:0]=[str(ROOT/'web/staging/integration'),str(ROOT/'web')]
import manage,full_provider_staging as full,schema150_restore_configuration as cfg
from fresh_artifact_acceptance import import_authenticated_image
from deployment.lib.schema148_artifacts import verify_archive,authenticated_archive,INPUTS
from deployment.lib.migration_inventory import discover
from deployment.lib.completed_normal_private_provider import verify_gateway
def require_disposable_guest(guest_uuid):
    """A root-created test marker is not a release credential or approval."""
    if (not __debug__ or not re.fullmatch('[0-9a-f-]{36}',guest_uuid)
            or subprocess.check_output(['sudo','cat','/sys/class/dmi/id/product_uuid']).decode().strip()!=guest_uuid):
        raise RuntimeError('private_transport_owned_guest_required')
    marker='/etc/madar-disposable-test.json'
    if subprocess.check_output(['sudo','stat','-c','%u:%a:%h:%F',marker]).decode().strip()!='0:600:1:regular file':
        raise RuntimeError('private_transport_root_marker_required')
    value=json.loads(subprocess.check_output(['sudo','cat',marker]))
    if (set(value)!={'guest_uuid','disposable','production_authority','expires_at'}
            or value['guest_uuid']!=guest_uuid or value['disposable'] is not True
            or value['production_authority'] is not False
            or datetime.fromisoformat(value['expires_at'])<=datetime.now(timezone.utc)):
        raise RuntimeError('private_transport_root_marker_invalid')
    subprocess.run(['sudo','systemctl','is-active','--quiet','codex-test-isolation.service'],check=True)
    if subprocess.check_output(['sudo','docker','ps','-aq']).strip():
        raise RuntimeError('private_transport_empty_disposable_daemon_required')


def main(source,guest_uuid,artifacts):
    if not re.fullmatch('[0-9a-f]{40}',source):raise RuntimeError('private_transport_exact_source_required')
    if subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD']).decode().strip()!=source:
        raise RuntimeError('private_transport_source_changed')
    if artifacts.is_symlink() or artifacts.parent!=full.STAGING_EVIDENCE or artifacts.name!='artifacts-'+source[:12]:
        raise RuntimeError('private_transport_artifact_scope_invalid')
    require_disposable_guest(guest_uuid)
    if shutil.disk_usage(ROOT).free<8*1024**3:raise RuntimeError('private_transport_disk_headroom')
    # Convert orderly process termination to unwinding so the same finally
    # removes owned runtime resources. SIGKILL/guest loss still requires the
    # host's independently bounded guest watchdog and explicit disk teardown.
    def interrupted(signum,frame):raise SystemExit(128+signum)
    for signum in (signal.SIGTERM,signal.SIGHUP):signal.signal(signum,interrupted)
    SOURCE,UUID,ART=source,guest_uuid,artifacts
    result={'scope':'native146 private provider transport only','source_sha':SOURCE,'guest_uuid':UUID,'protected_upgrade':False,'production_modified':False}
    with full.target(SOURCE,146) as (runtime,project):
        full.admission_headroom(runtime,project);manage.prepare(SOURCE)
        def compose(*args,timeout=240):return manage.docker('compose','--project-name',project,'--file',str(runtime/'native.json'),*args,timeout=timeout)
        def sql(query):
            return manage.docker('exec','-i','supabase-db','psql','-U','postgres','-d','postgres',
                '-XAtq','-v','ON_ERROR_STOP=1',data=query.encode(),timeout=180).decode().strip()
        def phase(name):print(name,flush=True);result['phase']=name
        created=False
        try:
            phase('artifact_verification')
            run=json.loads((ART/'run.json').read_text());artifact=json.loads((ART/'artifact.json').read_text());images=json.loads((ART/'receipt.json').read_text())['images']
            receipt=verify_archive(ART/'candidate.zip',artifact,run,source_sha=SOURCE,images=images,expected_inputs={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in INPUTS})
            with authenticated_archive(ART/'candidate.zip',artifact['digest']) as archive:
                for role in ('backend','frontend'):
                    path=runtime/(role+'.tar.gz')
                    import_authenticated_image(archive,role,receipt['archives'][role],path)
                    path.unlink()
            phase('native_image_pull')
            for image in cfg.INFRA_IMAGES.values():
                try:manage.docker('image','inspect',image)
                except RuntimeError:manage.docker('pull',image,timeout=360)
            values=dict(line.split('=',1) for line in (runtime/'compose.env').read_text().splitlines());pw=values['DATABASE_PASSWORD']
            env=dict(line.split('=',1) for line in (runtime/'application.env').read_text().splitlines())
            bootstrap=(runtime/'bootstrap.sql').read_text().replace('comment on database madar_hardening','comment on database postgres')
            manage.private_write('bootstrap.sql',bootstrap,mounted=True)
            base=(ROOT/'web/staging/integration/compose.yaml').read_text()
            manage.private_write('base.yaml',base)
            rendered=manage.docker('compose','--project-name',project,'--env-file',str(runtime/'compose.env'),'--file',str(runtime/'base.yaml'),'config','--format','json')
            template=json.loads(rendered);services={k:template['services'][k] for k in ('postgres','auth','rest','storage','redis','backend')}
            names={'postgres':'supabase-db','auth':'supabase-auth','rest':'supabase-rest','storage':'supabase-storage','backend':project+'-backend','redis':project+'-redis'}
            for key,s in services.items():
                s['container_name']=names[key];s['networks']={'native' if key in ('postgres','auth','rest','storage') else 'client':{}}
                s['labels']={'com.madar.staging.owner':project};s.pop('depends_on',None);s.pop('ports',None)
                for k,v in s.get('environment',{}).items():
                    if isinstance(v,str):s['environment'][k]=v.replace('@postgres:5432/madar_hardening','@supabase-db:5432/postgres').replace('http://rest:3000','http://supabase-rest:3000')
            services['postgres']['environment']['POSTGRES_DB']='postgres'
            services['postgres']['healthcheck']['test']=['CMD-SHELL','pg_isready -h 127.0.0.1 -U postgres -d postgres']
            services['postgres']['mem_limit']='768m';services['postgres']['cpus']=1
            services['backend']['image']=images['backend'];services['backend']['environment']={}
            gateway=project+'-provider-gateway'
            common={'restart':'no','init':True,'read_only':True,'cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],'pids_limit':64,'labels':{'com.madar.staging.owner':project},'logging':{'driver':'json-file','options':{'max-size':'2m','max-file':'2'}}}
            services['gateway']={**common,'image':images['frontend'],'container_name':gateway,'user':'nginx','entrypoint':['nginx'],'command':['-c','/etc/nginx/private-provider160.conf','-g','daemon off;'],'mem_limit':'128m','cpus':.25,'tmpfs':['/tmp:rw,noexec,nosuid,size=16m,mode=1777'],'networks':{'native':{},'client':{}},'healthcheck':{'test':['CMD','wget','--spider','--quiet','http://127.0.0.1:8000/health'],'interval':'3s','timeout':'3s','retries':20}}
            (runtime/'uploads').mkdir(mode=0o755)
            services['parser']={**common,'image':images['backend'],'container_name':project+'-parser','user':'65534:65534','command':['python','-m','workers.parser_worker'],'mem_limit':'768m','cpus':.75,'tmpfs':['/tmp:rw,noexec,nosuid,size=256m,uid=65534,gid=65534'],'networks':{'parser':{}},'volumes':[str(runtime/'uploads')+':/app/private_uploads:ro'],'environment':{'APP_ENV':'production','DATA_UPLOAD_DIR':'/app/private_uploads','MADAR_UPLOAD_WORKSPACE_DIR':'/tmp/madar_parser','PARSER_WORKER_PROCESS':'true','PARSER_WORKER_HEALTH_HOST':'0.0.0.0','PARSER_WORKER_PORT':'8092','ALLOW_REMOTE_DATASET_URLS':'false'},'healthcheck':{'test':['CMD','python','-c',"import urllib.request;urllib.request.urlopen('http://127.0.0.1:8092/health',timeout=2)"],'interval':'3s','timeout':'3s','retries':40}}
            services['backend']['networks']['parser']={}
            config={'services':services,'networks':{'native':{'name':'madar-local-supabase_default','labels':{'com.madar.staging.owner':project}},'client':{'name':'madar-supabase-client','internal':True,'labels':{'com.madar.staging.owner':project}},'parser':{'internal':True,'labels':{'com.madar.staging.owner':project}}},'volumes':{k:template['volumes'][k] for k in ('database','objects')}}
            for v in config['volumes'].values():v['labels']={'com.madar.staging.owner':project}
            def save():manage.private_write('native.json',json.dumps(config))
            save();created=True
            phase('native_provider_bootstrap');compose('up','-d','postgres')
            deadline=time.monotonic()+60
            while True:
                try:
                    if manage.docker('exec','supabase-db','pg_isready','-h','127.0.0.1','-U','postgres','-d','postgres').strip() and sql('select 1')=='1':break
                except RuntimeError:pass
                if time.monotonic()>deadline:raise RuntimeError('native_postgres_timeout')
                time.sleep(1)
            assert sql("select shobj_description(oid,'pg_database') from pg_database where datname='postgres'")==manage.MARKER
            compose('up','-d','--wait','--wait-timeout','100','auth','rest','storage')
            deadline=time.monotonic()+90
            while sql("select to_regclass('auth.users') is not null and to_regclass('storage.objects') is not null")!='t':
                if time.monotonic()>deadline:raise RuntimeError('native_provider_tables_timeout')
                time.sleep(1)
            compose('stop','--timeout','15','auth','rest','storage')
            assert sql("select count(*) from pg_stat_activity where pid<>pg_backend_pid() and backend_type='client backend'")=='0'
            sql('grant usage on schema storage to anon,authenticated,service_role; grant select,insert,update,delete on storage.buckets,storage.objects to anon,authenticated,service_role; grant usage on all sequences in schema storage to service_role; create extension if not exists pg_stat_statements with schema extensions;')
            assert sql("select to_regclass('public.application_schema_state') is null")=='t'
            inventory=discover(ROOT,source_sha=SOURCE,history_base_sha=SOURCE)
            for migration in inventory.migrations:
                if migration.number in inventory.excluded_versions or migration.number>146:continue
                phase('genesis_'+str(migration.number));sql("set lock_timeout='5s';set statement_timeout='45s';"+migration.sql.decode())
            assert sql("select schema_version from application_schema_state where contract_key='core'")=='146'
            identifier=sql('select system_identifier::text from pg_control_system()')
            sql('alter role authenticator connection limit 32;grant execute on function pg_catalog.pg_control_system() to service_role;')
            env.update({'SUPABASE_URL':'http://'+gateway+':8000','MADAR_BUILD_TIMESTAMP':receipt['build_timestamp'],'MADAR_CALENDAR_DATABASE_DSN':'postgresql://authenticator:'+pw+'@'+gateway+':5432/postgres?sslmode=disable','MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER':identifier,'PARSER_WORKER_ENABLED':'true','PARSER_WORKER_REQUIRED':'true','PARSER_WORKER_URL':'http://'+project+'-parser:8092/parse','PARSER_WORKER_HEALTH_URL':'http://'+project+'-parser:8092/health','CALENDAR_FEATURE_ENABLED':'true','CALENDAR_SYNC_WORKER_ENABLED':'true','CALENDAR_SYNC_REQUIRED':'false','CALENDAR_CREDENTIALS_SECRET':secrets.token_hex(32),'NOTIFICATION_WORKER_REQUIRED':'false'})
            services['redis']['networks']={'client':{'aliases':['redis']}}
            services['backend']['environment']=env
            manage.private_write('application.env',''.join(k+'='+v+'\n' for k,v in env.items()));save()
            phase('private_runtime_start');compose('up','-d','--wait','--wait-timeout','150','auth','rest','storage','redis','parser','gateway','backend',timeout=240)
            phase('native_auth_mfa_storage_calendar_probe')
            gateway_row=json.loads(manage.docker('inspect',gateway))[0]
            verify_gateway(gateway_row,source_sha=SOURCE,image=images['frontend'])
            assert sql("select rolconnlimit from pg_roles where rolname='authenticator'")=='32'
            probe=Path(__file__).with_name('private_provider_probe.py').read_bytes()
            output=manage.docker('exec','-i',names['backend'],'python','-',data=probe,timeout=180)
            observations=json.loads(output);assert observations['calendar_transport']=='ok'
            result.update(status='PASS',schema=146,system_identifier=identifier,services={k:manage.docker('inspect','--format','{{.Id}}',v).decode().strip() for k,v in {**names,'gateway':gateway,'parser':project+'-parser'}.items()},observations=observations,images=images,artifact_id=artifact['id'])
        except Exception as error:
            result.update(status='FAIL',exception_type=type(error).__name__,failure_code=str(error) if isinstance(error,RuntimeError) and str(error).replace('_','').isalnum() else 'private_diagnostic_required',frames=[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(error.__traceback__)[-8:]])
            manage.private_write('failure-private.log',traceback.format_exc())
            if created:
                try:manage.private_write('service-private.log',compose('logs','--tail','60').decode(errors='replace'))
                except Exception:pass
        finally:
            result.setdefault('status','INTERRUPTED')
            if created:
                compose('down','--volumes','--remove-orphans','--timeout','15')
                assert not manage.docker('ps','-aq','--filter','label=com.docker.compose.project='+project).strip()
                for kind in ('network','volume'):
                    assert not manage.docker(kind,'ls','--filter','label=com.docker.compose.project='+project,'--format','{{.Name}}').strip()
            result['cleanup']='PASS';result['disk_free_after']=shutil.disk_usage(ROOT).free
            result['retained_guest_images']={
                'purpose':'Reuse only during the bounded disposable guest lifetime; destroyed with its owned disk',
                'references':[*cfg.INFRA_IMAGES.values(),*images.values()] if 'images' in locals() else []}
            manage.private_write('native-private-provider-result.json',json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
    if result['status']!='PASS':raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha',required=True)
    parser.add_argument('--guest-uuid',required=True)
    parser.add_argument('--artifacts',required=True,type=Path)
    args=parser.parse_args();main(args.source_sha,args.guest_uuid,args.artifacts)

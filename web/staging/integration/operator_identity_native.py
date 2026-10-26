#!/usr/bin/env python3
"""Bounded real operator-identity fixture; no issuer, main release or production.

Internal Docker network, pinned images, tmpfs database, synthetic MFA and TLS,
root-private policies only inside a read-only test container. Always tears down
exact labelled resources; records unknown cleanup without claiming success.
"""
import hashlib,ipaddress,json,os,secrets,shutil,signal,subprocess,sys,tempfile,time
from pathlib import Path

PG='postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73'
AUTH='supabase/gotrue:v2.196.0@sha256:c0c25187a6b835e65a6f6e6c6b39d090e832d40e6de5186f2c038e0411944232'
LABEL='com.madar.rehearsal.run'
WEB=Path(__file__).resolve().parents[2]
DOCKER=['/usr/bin/docker','--host','unix:///var/run/docker.sock']


def main():
    parent=Path('/opt/madar-development/scratch/codex-runs')
    if not parent.is_dir():parent=Path(tempfile.gettempdir())
    available=int(next(v.split()[1] for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith('MemAvailable:')))*1024
    if shutil.disk_usage(parent).free<2*1024**3 or available<1500*1024**2:raise RuntimeError('operator_fixture_headroom_insufficient')
    run=Path(tempfile.mkdtemp(prefix='codex-operator-native-',dir=parent));run.chmod(0o700);identity=run.name
    record={'run_id':identity,'created':[],'removed':[],'network':None,'network_removed':False,'passed':False}
    def command(args,*,data=None,timeout=30):
        result=subprocess.run(args,input=data,capture_output=True,timeout=timeout)
        if result.returncode:
            # Private bounded diagnostics; no argv/env/token bodies in report.
            (run/'private-failure.log').write_bytes((result.stdout+result.stderr)[-65536:]);(run/'private-failure.log').chmod(0o600)
            raise RuntimeError('operator_fixture_command_failed')
        return result.stdout
    def docker(*args,data=None,timeout=30):
        if args and args[0]=='logs':
            result=subprocess.run(DOCKER+list(args),capture_output=True,timeout=timeout)
            if result.returncode:raise RuntimeError('operator_fixture_private_logs_unavailable')
            return (result.stdout+result.stderr)[-65536:]
        return command(DOCKER+list(args),data=data,timeout=timeout)
    def secret_file(name,value):
        fd=os.open(run/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as stream:stream.write(value)
        return str(run/name)
    def create(role,image,args):
        cid=docker('create','--name',identity+'-'+role,'--label',LABEL+'='+identity,*args,image).decode().strip()
        record['created'].append(cid);journal();docker('start',cid);return cid
    def journal():
        path=run/'resources.json'
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:
            json.dump(record,stream,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    journal()
    original_error=None
    def interrupted(signum,frame):raise InterruptedError('owned_operator_fixture_interrupted')
    for signum in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(signum,interrupted)
    try:
        # No implicit pull/build; pinned infrastructure and locked tool image
        # must already be available from their authenticated preparation.
        tool=os.getenv('BACKEND_TEST_IMAGE','madar-backend-test')
        for image in (PG,AUTH,tool):docker('image','inspect','--format','{{.Id}}',image)
        ids=docker('network','ls','--quiet').decode().split()
        if len(ids)>2048:raise RuntimeError('operator_fixture_network_inventory_unbounded')
        networks=json.loads(docker('network','inspect',*ids)) if ids else []
        allocations=[ipaddress.ip_network(v['Subnet']) for n in networks for v in (n.get('IPAM',{}).get('Config') or []) if v.get('Subnet')]
        routes=json.loads(command(['/usr/sbin/ip','-json','route','show','table','all']))
        allocations += [ipaddress.ip_network(r['dst'],strict=False) for r in routes if r.get('dst') and r['dst']!='default']
        choices=(ipaddress.ip_network('10.241.'+str(i)+'.0/28') for i in range(256))
        subnet=next((str(n) for n in choices if not any(n.version==a.version and n.overlaps(a) for a in allocations)),None)
        if subnet is None:raise RuntimeError('operator_fixture_no_nonoverlapping_internal_subnet')
        record['internal_subnet']=subnet
        network=docker('network','create','--internal','--subnet',subnet,'--label',LABEL+'='+identity,identity).decode().strip();record['network']=network;journal()
        password=secrets.token_hex(24);jwt=secrets.token_hex(32)
        pg_env=secret_file('postgres.env','POSTGRES_PASSWORD='+password+'\nPOSTGRES_DB=operator_identity_fixture\n')
        pg=create('postgres',PG,['--network',network,'--network-alias','postgres','--memory','384m','--cpus','.5','--pids-limit','96',
            '--env-file',pg_env,'--tmpfs','/var/lib/postgresql/data:rw,noexec,nosuid,size=256m'])
        for _ in range(60):
            result=subprocess.run(DOCKER+['exec',pg,'pg_isready','-h','127.0.0.1','-U','postgres'],capture_output=True)
            if result.returncode==0:break
            time.sleep(.5)
        else:raise RuntimeError('operator_fixture_database_not_ready')
        sql=("CREATE ROLE supabase_auth_admin LOGIN NOINHERIT PASSWORD '"+password+"';\n"
             "CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; CREATE ROLE service_role NOLOGIN;\n"
             "CREATE SCHEMA auth AUTHORIZATION supabase_auth_admin;\n"
             "ALTER ROLE supabase_auth_admin SET search_path=auth,public;\n"
             "COMMENT ON DATABASE operator_identity_fixture IS '"+identity+"';\n")
        docker('exec','-i',pg,'psql','-Xq','-U','postgres','-d','operator_identity_fixture','-v','ON_ERROR_STOP=1',data=sql.encode())
        dbid=docker('exec',pg,'psql','-XAt','-U','postgres','-c','SELECT system_identifier FROM pg_control_system()').decode().strip()
        values={'GOTRUE_API_HOST':'0.0.0.0','GOTRUE_API_PORT':'9999','API_EXTERNAL_URL':'https://operator.test/auth/v1',
            'GOTRUE_DB_DRIVER':'postgres','GOTRUE_DB_DATABASE_URL':'postgres://supabase_auth_admin:'+password+'@postgres:5432/operator_identity_fixture',
            'GOTRUE_DB_NAMESPACE':'auth','GOTRUE_SITE_URL':'https://operator.test','GOTRUE_JWT_SECRET':jwt,
            'GOTRUE_JWT_ADMIN_ROLES':'service_role','GOTRUE_JWT_AUD':'authenticated','GOTRUE_JWT_DEFAULT_GROUP_NAME':'authenticated',
            'GOTRUE_JWT_EXP':'300','GOTRUE_JWT_ISSUER':'https://operator.test/auth/v1','GOTRUE_EXTERNAL_EMAIL_ENABLED':'true',
            'GOTRUE_MAILER_AUTOCONFIRM':'true','GOTRUE_DISABLE_SIGNUP':'true',
            'GOTRUE_MFA_TOTP_ENROLL_ENABLED':'true','GOTRUE_MFA_TOTP_VERIFY_ENABLED':'true','GOTRUE_LOG_LEVEL':'error'}
        env=secret_file('auth.env',''.join(k+'='+v+'\n' for k,v in values.items()))
        provider=create('auth',AUTH,['--network',network,'--network-alias','auth','--memory','192m','--cpus','.5','--pids-limit','64','--env-file',env])
        for _ in range(60):
            result=subprocess.run(DOCKER+['exec',provider,'wget','--spider','--quiet','http://127.0.0.1:9999/health'],capture_output=True)
            if result.returncode==0:break
            if not json.loads(docker('inspect',provider))[0]['State']['Running']:
                (run/'private-failure.log').write_bytes(docker('logs','--tail','30',provider));(run/'private-failure.log').chmod(0o600)
                raise RuntimeError('operator_fixture_auth_exited')
            time.sleep(.5)
        else:
            (run/'private-failure.log').write_bytes(docker('logs','--tail','30',provider));(run/'private-failure.log').chmod(0o600)
            raise RuntimeError('operator_fixture_auth_not_ready')
        command(['/usr/bin/openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=127.0.0.1',
            '-addext','subjectAltName=IP:127.0.0.1','-keyout',str(run/'key.pem'),'-out',str(run/'cert.pem')])
        (run/'key.pem').chmod(0o600);(run/'cert.pem').chmod(0o600)
        env=secret_file('client.env','NATIVE_OPERATOR_KEY='+jwt+'\nNATIVE_OPERATOR_DATABASE_IDENTIFIER='+dbid+'\n')
        cid=docker('create','--name',identity+'-client','--label',LABEL+'='+identity,'--network',network,
            '--hostname','madar-operator-native','--read-only','--user','0:0','--memory','384m','--cpus','.75','--pids-limit','96',
            '--env-file',env,'--env','MADAR_NATIVE_OPERATOR_IDENTITY=1','--env','PYTHONDONTWRITEBYTECODE=1',
            '--env','PYTHONPATH=/source:/source/backend/tests','--env','SSL_CERT_FILE=/test-certificate/cert.pem',
            '--tmpfs','/etc/madar:rw,noexec,nosuid,nodev,size=1m,mode=700',
            '--volume',str(WEB)+':/source:ro','--volume',str(run)+':/test-certificate:ro','--entrypoint','python',tool,
            '-B','-m','unittest','test_release_operator_native','-v').decode().strip()
        record['created'].append(cid);journal()
        result=docker('start','--attach',cid,timeout=90);print(result.decode(),flush=True)
        logs=docker('logs',cid);print(logs.decode(),flush=True)
        if json.loads(docker('inspect',cid))[0]['State']['ExitCode']!=0:raise RuntimeError('operator_fixture_tests_failed')
        record['passed']=True
    except Exception as error:
        original_error=error;record['failure']=str(error) if isinstance(error,RuntimeError) else type(error).__name__
    finally:
        for signum in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(signum,signal.SIG_IGN)
        cleanup_errors=[]
        for cid in reversed(record['created']):
            try:
                row=json.loads(docker('inspect',cid))[0]
                if row['Id']!=cid or row['Config'].get('Labels',{}).get(LABEL)!=identity:raise RuntimeError('operator_fixture_cleanup_owner_changed')
                docker('rm','-f','-v',cid);record['removed'].append(cid);journal()
            except Exception as error:cleanup_errors.append(type(error).__name__)
        if record['network']:
            try:
                row=json.loads(docker('network','inspect',record['network']))[0]
                if row['Labels'].get(LABEL)!=identity or row.get('Containers'):raise RuntimeError('operator_fixture_network_referenced')
                docker('network','rm',record['network']);record['network_removed']=True;journal()
            except Exception as error:cleanup_errors.append(type(error).__name__)
        record['cleanup_errors']=cleanup_errors;record['disk_free_after']=shutil.disk_usage(parent).free
        # No synthetic passwords, access tokens, MFA secrets or TLS private
        # keys survive even a test failure. Keep only bounded diagnostics.
        for name in ('postgres.env','auth.env','client.env','key.pem','cert.pem'):(run/name).unlink(missing_ok=True)
        print(json.dumps(record,sort_keys=True),flush=True)
        if cleanup_errors or original_error:
            (run/'retained.json').write_text(json.dumps(record));(run/'retained.json').chmod(0o600)
            raise RuntimeError('operator_fixture_failed_diagnostics_retained:'+str(run)) from None
        for name in ('private-failure.log','resources.json'):(run/name).unlink(missing_ok=True)
        run.rmdir()


if __name__=='__main__':main()

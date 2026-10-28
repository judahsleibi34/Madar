#!/usr/bin/env python3
"""Real independent Auth/TOTP test operator inside an enrolled disposable guest.

Creates no approval, policy enrollment or deployment authority. The trusted
external test parent separately enrolls the measured service and operator ID.
The owning KVM supervisor bounds lifetime and removes its complete disk/runtime.
"""
import hashlib,json,os,secrets,subprocess,sys,time
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler


def prepare():
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    from deployment.lib.isolated_release_environment import observe,REALM_LABEL
    from deployment.lib.provider_recovery_runtime import protected
    from deployment.lib.completed_normal_resources import measured_spec
    from deployment.lib.migration_executor import atomic_json
    from smoke import totp
    from manage import jwt
    environment=observe()
    if environment['version']!=2:raise RuntimeError('exceptional_operator_fixture_requires_enrolled_guest')
    realm=environment['realm_id'];root=Path('/opt/madar-test/operator-fixture')
    root.mkdir(mode=0o700) # no overwriting an existing fixture/identity
    label='com.madar.operator-fixture';prefix='madar-operator-'+realm[:12]
    created=[];network=None;volume=None
    def command(args,*,data=None):
        p=subprocess.run(args,input=data,capture_output=True,timeout=90,
            env={'PATH':os.defpath,'HOME':'/nonexistent','DOCKER_HOST':'unix:///var/run/docker.sock','DOCKER_CONFIG':'/nonexistent'})
        if p.returncode:
            (root/'private-error.log').write_bytes((p.stdout+p.stderr)[-16384:]);(root/'private-error.log').chmod(0o600)
            raise RuntimeError('exceptional_operator_fixture_command_failed')
        return p.stdout.decode().strip()
    def file(name,body):
        p=root/name;p.write_text(body);p.chmod(0o600);return str(p)
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    opener=build_opener(ProxyHandler({}),NoRedirect())
    statuses=[]
    def http(method,path,body=None,token=None,*,expected=(200,)):
        req=Request(url+path,method=method,data=json.dumps(body).encode() if body is not None else None,
            headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
        with opener.open(req,timeout=5) as response:
            raw=response.read(65537)
            statuses.append({'method':method,'path':path.split('?',1)[0],'status':response.status})
            if response.status not in expected or len(raw)>65536:raise RuntimeError('exceptional_operator_fixture_auth_status_'+str(response.status))
            return json.loads(raw)
    try:
        # Immutable images already authenticated by the native provider fixture;
        # execution fencing permits no image download or external connection.
        images=json.loads(command(['docker','inspect','supabase-db','supabase-auth']))
        pg_image=next(x['Image'] for x in images if x['Name']=='/supabase-db')
        auth_image=next(x['Image'] for x in images if x['Name']=='/supabase-auth')
        network=command(['docker','network','create','--internal','--label',REALM_LABEL+'='+realm,
            '--label',label+'='+realm,prefix])
        password=secrets.token_hex(32);key=secrets.token_hex(32)
        pg_env=file('database.env','POSTGRES_PASSWORD='+password+'\nPOSTGRES_DB=operators\n')
        volume=command(['docker','volume','create','--label',REALM_LABEL+'='+realm,'--label',label+'='+realm,prefix+'-database'])
        pg=command(['docker','run','-d','--name',prefix+'-database','--label',REALM_LABEL+'='+realm,
            '--label',label+'='+realm,'--network',prefix,'--network-alias','operator-db',
            '--restart=no','--memory','256m','--cpus','.25','--pids-limit','96',
            '--mount','type=volume,src='+volume+',dst=/var/lib/postgresql/data','--env-file',pg_env,
            pg_image,'postgres','-c','max_connections=16','-c','shared_buffers=16MB'])
        created.append(pg)
        for _ in range(60):
            p=subprocess.run(['docker','exec',pg,'pg_isready','-U','postgres','-d','operators'],capture_output=True,timeout=5)
            if p.returncode==0:break
            time.sleep(1)
        else:raise RuntimeError('exceptional_operator_fixture_database_deadline')
        command(['docker','exec','-i',pg,'psql','-Xq','-v','ON_ERROR_STOP=1','-U','postgres','-d','operators'],
            data=("CREATE ROLE supabase_auth_admin LOGIN NOINHERIT CONNECTION LIMIT 8 PASSWORD '"+password+"'; CREATE SCHEMA auth AUTHORIZATION supabase_auth_admin; GRANT USAGE,CREATE ON SCHEMA public TO supabase_auth_admin; ALTER ROLE supabase_auth_admin SET search_path=auth,public; COMMENT ON DATABASE operators IS 'madar-isolated-operator-"+realm+"';").encode())
        issuer='http://infrastructure-operator.invalid/auth/v1'
        values={'GOTRUE_API_HOST':'0.0.0.0','GOTRUE_API_PORT':'9999','API_EXTERNAL_URL':issuer,
            'GOTRUE_DB_DRIVER':'postgres','GOTRUE_DB_DATABASE_URL':'postgres://supabase_auth_admin:'+password+'@operator-db:5432/operators',
            'GOTRUE_DB_NAMESPACE':'auth','GOTRUE_DB_MAX_POOL_SIZE':'4','GOTRUE_SITE_URL':'http://infrastructure-operator.invalid',
            'GOTRUE_JWT_SECRET':key,'GOTRUE_JWT_ADMIN_ROLES':'service_role','GOTRUE_JWT_AUD':'authenticated',
            'GOTRUE_JWT_DEFAULT_GROUP_NAME':'authenticated','GOTRUE_JWT_EXP':'3600','GOTRUE_JWT_ISSUER':issuer,
            'GOTRUE_EXTERNAL_EMAIL_ENABLED':'true','GOTRUE_MAILER_AUTOCONFIRM':'true','GOTRUE_DISABLE_SIGNUP':'true',
            'GOTRUE_MFA_TOTP_ENROLL_ENABLED':'true','GOTRUE_MFA_TOTP_VERIFY_ENABLED':'true'}
        auth_env=file('auth.env',''.join(k+'='+v+'\n' for k,v in values.items()))
        auth=command(['docker','run','-d','--name',prefix+'-auth','--label',REALM_LABEL+'='+realm,
            '--label',label+'='+realm,'--network',prefix,'--restart=no','--memory','128m','--cpus','.25',
            '--pids-limit','96','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true',
            '--tmpfs','/tmp:rw,noexec,nosuid,size=16m','--env-file',auth_env,auth_image]);created.append(auth)
        row=json.loads(command(['docker','inspect',auth]))[0]
        ip=row['NetworkSettings']['Networks'][prefix]['IPAddress'];url='http://'+ip+':9999'
        for _ in range(60):
            try:http('GET','/health');break
            except Exception:time.sleep(1)
        else:raise RuntimeError('exceptional_operator_fixture_auth_deadline')
        email='operator-'+secrets.token_hex(8)+'@example.invalid';user_password=secrets.token_urlsafe(32)
        user=http('POST','/admin/users',{'email':email,'password':user_password,'email_confirm':True},jwt(key,'service_role'))
        session=http('POST','/token?grant_type=password',{'email':email,'password':user_password})
        factor=http('POST','/factors',{'factor_type':'totp','friendly_name':'Disposable infrastructure operator'},session['access_token'],expected=(200,201))
        challenge=http('POST','/factors/'+factor['id']+'/challenge',{},session['access_token'])
        elevated=http('POST','/factors/'+factor['id']+'/verify',{'challenge_id':challenge['id'],'code':totp(factor['totp']['secret'])},session['access_token'])
        profile=http('GET','/user',token=elevated['access_token'])
        if profile['id']!=user['id']:raise RuntimeError('exceptional_operator_fixture_identity_changed')
        file('authentication.key',key)
        atomic_json(root/'private-session.json',{'email':email,'password':user_password,'factor_id':factor['id'],
            'totp_secret':factor['totp']['secret'],'session':elevated,'aal1_session':session})
        facts={'realm_id':realm,'operator_auth_id':user['id'],'issuer':issuer,'auth_user_url':url+'/user',
            'auth_service':{'id':auth,'image':row['Image'],'spec_sha256':measured_spec(row)},
            'authentication_key_sha256':hashlib.sha256(key.encode()).hexdigest(),'root':str(root),
            'created_container_ids':created,'network_id':network,'volume_name':volume,'production_authority':False,
            'http_statuses':statuses,'role':'synthetic infrastructure operator; no human or production approval claimed'}
        atomic_json(root/'facts.json',facts)
        return facts
    except BaseException:
        # Exact positively labeled resources only; preserve compact diagnostics.
        for identity in reversed(created):
            logs=subprocess.run(['docker','logs','--tail','40',identity],capture_output=True,timeout=10)
            q=root/('private-failed-'+identity[:12]+'.log');q.write_bytes((logs.stdout+logs.stderr)[-16384:]);q.chmod(0o600)
            row=json.loads(command(['docker','inspect',identity]))[0]
            if row['Config']['Labels'].get(label)!=realm:raise RuntimeError('exceptional_operator_fixture_cleanup_ownership_changed')
            command(['docker','rm','-f','-v',identity])
        if network is not None:
            row=json.loads(command(['docker','network','inspect',network]))[0]
            if row['Labels'].get(label)!=realm or row['Containers']:raise RuntimeError('exceptional_operator_fixture_cleanup_network_changed')
            command(['docker','network','rm',network])
        if volume is not None:
            row=json.loads(command(['docker','volume','inspect',volume]))[0]
            if row['Labels'].get(label)!=realm or command(['docker','ps','-aq','--filter','volume='+volume]):raise RuntimeError('exceptional_operator_fixture_cleanup_volume_changed')
            command(['docker','volume','rm',volume])
        for name in ('database.env','auth.env','authentication.key','private-session.json'):(root/name).unlink(missing_ok=True)
        raise


if __name__=='__main__':
    if sys.argv[1:]!=['PREPARE']:raise SystemExit('Explicit PREPARE required; no enrollment, approval or execution is performed')
    print(json.dumps(prepare(),sort_keys=True))

"""Original-account fixtures in an identified historical146 KVM application.

Uses real providers and the existing independent observer. Creates no authority,
completion history, migrations or operational admission. Credentials stay root
private. The outer guest owner must destroy the whole disposable guest on exit.
"""
import base64,hashlib,hmac,json,os,re,secrets,struct,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path

def require(value,code):
    if not value:raise RuntimeError(code)

def main():
    if os.geteuid()!=0 or subprocess.check_output(['systemd-detect-virt']).strip()!=b'kvm':
        raise RuntimeError('running146_owned_kvm_required')
    sys.path.insert(0,'/opt/madar-test/controller/web')
    from deployment.lib.provider_recovery_runtime import protected
    from deployment.lib.isolated_release_environment import observe_effect_fence
    observe_effect_fence()
    root=Path('/opt/madar-test/origin146');state=json.loads(protected(root/'private.json',private=True).read_bytes())
    seed=sys.argv[1:]==['--seed']
    if not seed and sys.argv[1:]!=['--observe']:raise RuntimeError('running146_explicit_probe_mode_required')
    if seed and (root/'original-provider-probes.json').exists():
        raise RuntimeError('running146_original_probe_already_created')
    if (Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower()!=state['guest_uuid']
            or subprocess.check_output(['hostname']).strip()!=b'madar-release-test'):
        raise RuntimeError('running146_guest_identity_changed')
    record=json.loads(Path('/var/lib/madar/releases/origin-bootstrap-adopted.json').read_bytes())
    if record.get('phase')!='bootstrap_adopted' or record.get('release_sha')!=state['origin_source_sha']:
        raise RuntimeError('running146_actual_bootstrap_required')
    realm=state['realm_id'];prefix=state['origin_prefix'];slot=record['candidate_slot']
    if not re.fullmatch('[0-9a-f-]{36}',realm):raise RuntimeError('running146_realm_invalid')
    rows=json.loads(subprocess.check_output(['docker','inspect',*[prefix+'-'+slot+'-'+role for role in (
        'backend','frontend','redis','parser-worker','remote-ingestion-worker','notification-worker','calendar-sync-worker','data-deletion-worker')]]))
    if any(r['Config'].get('Labels',{}).get('com.madar.test.realm')!=realm or not r['State']['Running']
           or r['State'].get('Health',{}).get('Status')!='healthy' for r in rows):
        raise RuntimeError('running146_eight_healthy_roles_required')
    def sql(body):
        return subprocess.check_output(['docker','exec','-i','supabase-db','psql','-XqAt','-v','ON_ERROR_STOP=1',
            '-U','supabase_admin','-d','postgres'],input=body.encode(),timeout=30).decode().strip()
    identity=sql("SELECT schema_version::text || ':' || (SELECT system_identifier::text FROM pg_control_system()) FROM public.application_schema_state WHERE contract_key='core';")
    if identity!='146:'+state['database_system_identifier']:raise RuntimeError('running146_database_changed')
    marker=sql("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname='postgres';")
    if marker!='madar-isolated-'+realm:raise RuntimeError('running146_database_realm_changed')
    if not seed:
        private=protected(root/'original-provider-probes.json',private=True)
        packet=json.loads(private.read_bytes())
        if packet.get('system_identifier')!=state['database_system_identifier']:raise RuntimeError('running146_probe_database_changed')
        verify_subjects(root,state,rows,packet['subjects'])
        return
    # This fixture owns only its fresh synthetic buckets. Existing provider
    # policies remain intact; neither service-role nor tenant RLS is relaxed.
    bucket_prefix='original-'+realm[:12]+'-'
    policy='original_'+realm.replace('-','')
    sql("CREATE POLICY \""+policy+"\" ON storage.objects FOR ALL TO authenticated "
        "USING(bucket_id LIKE '"+bucket_prefix+"%' AND owner_id=auth.uid()::text) "
        "WITH CHECK(bucket_id LIKE '"+bucket_prefix+"%' AND owner_id=auth.uid()::text AND split_part(name,'/',1)=auth.uid()::text);")
    def seed_identity(auth_id,email):
        query=("BEGIN; WITH t AS (INSERT INTO public.tenants(brand_name,owner_name) VALUES('Original synthetic tenant','Fixture owner') RETURNING tenant_id), "
          "u AS (INSERT INTO public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified,email_verified_at) "
          "SELECT '"+auth_id+"','Original','Owner','"+email+"',tenant_id,'active',true,now() FROM t RETURNING id,tenant_id), "
          "m AS (INSERT INTO public.tenant_memberships(tenant_id,user_id,auth_id,role,status) SELECT tenant_id,id,'"+auth_id+"','owner','active' FROM u) "
          "SELECT json_build_array(tenant_id,id) FROM u; COMMIT;")
        return json.loads(sql(query))
    base='http://'+subprocess.check_output(['docker','inspect','-f','{{(index .NetworkSettings.Networks "madar-local-supabase_default").IPAddress}}','supabase-envoy']).decode().strip()+':8000'
    service=state['service_key'];anon=state['anon_key']
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def call(method,path,body=None,token=None,expected=200,content='application/json'):
        headers={'Content-Type':content,'apikey':anon}
        if token:headers['Authorization']='Bearer '+token
        data=json.dumps(body).encode() if isinstance(body,dict) else body
        try:r=opener.open(urllib.request.Request(base+path,data=data,headers=headers,method=method),timeout=15)
        except urllib.error.HTTPError as e:r=e
        with r:
            raw=r.read()
            if r.status not in ((expected,) if type(expected)is int else expected):
                raise RuntimeError('running146_probe_http_'+str(r.status)+'_'+path.split('?')[0])
            return json.loads(raw) if 'application/json' in r.headers.get('Content-Type','') else raw
    email='native-'+secrets.token_hex(8)+'@example.com';password=secrets.token_urlsafe(32)
    user=call('POST','/auth/v1/admin/users',{'email':email,'password':password,'email_confirm':True},service)
    session=call('POST','/auth/v1/token?grant_type=password',{'email':email,'password':password})
    call('POST','/auth/v1/token?grant_type=password',{'email':email,'password':'incorrect'},expected=400)
    factor=call('POST','/auth/v1/factors',{'factor_type':'totp','friendly_name':'Private native acceptance'},session['access_token'])
    challenge=call('POST','/auth/v1/factors/'+factor['id']+'/challenge',{},session['access_token'])
    secret=factor['totp']['secret'];key=base64.b32decode(secret.upper()+'='*(-len(secret)%8));digest=hmac.new(key,struct.pack('>Q',int(time.time())//30),hashlib.sha1).digest();offset=digest[-1]&15;code=f'{(struct.unpack(">I",digest[offset:offset+4])[0]&0x7fffffff)%1000000:06d}'
    elevated=call('POST','/auth/v1/factors/'+factor['id']+'/verify',{'challenge_id':challenge['id'],'code':code},session['access_token'])
    claims=json.loads(base64.urlsafe_b64decode(elevated['access_token'].split('.')[1]+'=='));require(claims['aal']=='aal2','running146_aal2_required')
    refresh=call('POST','/auth/v1/token?grant_type=refresh_token',{'refresh_token':elevated['refresh_token']});require(refresh['refresh_token']!=elevated['refresh_token'],'running146_refresh_rotation_required')
    bucket='native-private-'+secrets.token_hex(8);call('POST','/storage/v1/bucket',{'id':bucket,'name':bucket,'public':False},service)
    data=secrets.token_bytes(257);call('POST','/storage/v1/object/'+bucket+'/fixture.bin',data,service,content='application/octet-stream')
    require(call('GET','/storage/v1/object/'+bucket+'/fixture.bin',token=service)==data,'running146_object_bytes_changed')
    call('GET','/storage/v1/object/'+bucket+'/fixture.bin',token=anon,expected=(400,403,404))
    require(isinstance(call('GET','/rest/v1/tenants?select=tenant_id&limit=1',token=service),list),'running146_rest_unavailable')
    subjects=[]
    for index in range(2):
        if index==0:
            person,person_email,person_password,person_factor,person_secret,person_token=user,email,password,factor,secret,elevated['access_token']
        else:
            person_email='original-'+secrets.token_hex(8)+'@example.com';person_password=secrets.token_urlsafe(32)
            person=call('POST','/auth/v1/admin/users',{'email':person_email,'password':person_password,'email_confirm':True},service)
            person_session=call('POST','/auth/v1/token?grant_type=password',{'email':person_email,'password':person_password})
            person_factor=call('POST','/auth/v1/factors',{'factor_type':'totp','friendly_name':'Preserved original fixture'},person_session['access_token'])
            person_secret=person_factor['totp']['secret']
            person_challenge=call('POST','/auth/v1/factors/'+person_factor['id']+'/challenge',{},person_session['access_token'])
            person_key=base64.b32decode(person_secret+'='*(-len(person_secret)%8))
            person_digest=hmac.new(person_key,struct.pack('>Q',int(time.time())//30),hashlib.sha1).digest();person_offset=person_digest[-1]&15
            person_code=f'{(struct.unpack(">I",person_digest[person_offset:person_offset+4])[0]&0x7fffffff)%1000000:06d}'
            person_verified=call('POST','/auth/v1/factors/'+person_factor['id']+'/verify',{'challenge_id':person_challenge['id'],'code':person_code},person_session['access_token'])
            person_token=person_verified['access_token']
        # Fixed SQL and freshly generated UUID/email values; never production input.
        require(re.fullmatch('[0-9a-f-]{36}',person['id']) and re.fullmatch('[a-z0-9-]+@example.com',person_email),'running146_seed_identity_invalid')
        tenant,person_id=seed_identity(person['id'],person_email)
        person_bucket=bucket_prefix+secrets.token_hex(8)
        call('POST','/storage/v1/bucket',{'id':person_bucket,'name':person_bucket,'public':False},service)
        person_object=person['id']+'/original.bin';person_bytes=secrets.token_bytes(257)
        call('POST','/storage/v1/object/'+person_bucket+'/'+person_object,person_bytes,person_token,content='application/octet-stream')
        subjects.append({'auth_id':person['id'],'user_id':person_id,'tenant_id':tenant,'email':person_email,
            'password':person_password,'factor_id':person_factor['id'],'totp_secret':person_secret,
            'bucket':person_bucket,'object':person_object,'object_sha256':hashlib.sha256(person_bytes).hexdigest()})
    private=root/'original-provider-probes.json'
    if private.exists():raise RuntimeError('running146_original_probe_already_created')
    private.write_text(json.dumps({'version':1,'system_identifier':state['database_system_identifier'],'subjects':subjects},sort_keys=True))
    private.chmod(0o600)
    verify_subjects(root,state,rows,subjects)


def verify_subjects(root,state,rows,subjects):
    sys.path.insert(0,'/opt/madar-test/controller/web')
    from deployment.lib.completed_normal_private_acceptance import observe_subjects
    endpoints={}
    for name,port in (('auth',9999),('rest',3000),('storage',5000)):
        row=json.loads(subprocess.check_output(['docker','inspect','supabase-'+name]))[0]
        endpoints[name]='http://'+row['NetworkSettings']['Networks']['madar-local-supabase_default']['IPAddress']+':'+str(port)
    observed=observe_subjects(subjects,endpoints,state['anon_key'])
    # Exercise the historical application itself, not only its Auth provider.
    # Loopback HTTP is internal to this KVM guest; the emitted browser cookie
    # must still be Secure. No browser/TLS or production acceptance is claimed.
    from http.cookies import SimpleCookie
    person=subjects[0]
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request=urllib.request.Request('http://127.0.0.1:8001/auth/login',
        data=json.dumps({k:person[k] for k in ('email','password')}).encode(),method='POST',
        headers={'Content-Type':'application/json','Origin':'https://hardening.test','X-Forwarded-Proto':'https'})
    with opener.open(request,timeout=20) as response:
        body=json.load(response);cookies=SimpleCookie()
        for value in response.headers.get_all('Set-Cookie',[]):cookies.load(value)
    if (body.get('user',{}).get('id')!=person['user_id'] or not body.get('csrf_token')
            or not cookies.get('madar_access_token') or not cookies['madar_access_token']['secure']):
        raise RuntimeError('running146_backend_login_required')
    request=urllib.request.Request('http://127.0.0.1:8001/auth/user_status',headers={
        'Cookie':'; '.join(k+'='+v.value for k,v in cookies.items()),
        'Origin':'https://hardening.test','X-Forwarded-Proto':'https'})
    with opener.open(request,timeout=20) as response:
        if response.status!=200:raise RuntimeError('running146_backend_session_required')
        response.read()
    result={'scope':'genuine historical146 bootstrap and original-provider acceptance only',
        'source_sha':state['origin_source_sha'],'database_system_identifier':state['database_system_identifier'],
        'schema':146,'healthy_application_roles':len(rows),'bootstrap_receipt_sha256':hashlib.sha256(Path('/var/lib/madar/releases/origin-bootstrap-adopted.json').read_bytes()).hexdigest(),
        'password_and_mfa_and_refresh_and_private_storage_and_tenant_isolation':True,
        'historical_backend_login_session_secure_cookie_csrf':True,
        'subjects':observed,'protected_upgrade_executed':False,'write_authority_issued':False}
    p=root/'original-acceptance.json';p.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');p.chmod(0o600)
    print(json.dumps(result))

if __name__=='__main__':main()

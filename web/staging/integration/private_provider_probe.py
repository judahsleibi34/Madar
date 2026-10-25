"""Native private transport assertions, executed inside the accepted backend image.

Creates synthetic identities/objects only in private_provider_transport's owned
empty guest. Not an operational acceptance guard or release authority issuer.
"""
import base64,hashlib,hmac,json,os,secrets,socket,struct,time,urllib.request,urllib.error
from services.calendar_mutation_service import transport_status
base=os.environ['SUPABASE_URL'];service=os.environ['SUPABASE_SERVICE_KEY'];anon=os.environ['SUPABASE_ANON_KEY']
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def call(method,path,body=None,token=None,expected=200,content='application/json'):
    headers={'Content-Type':content}
    if token:headers['Authorization']='Bearer '+token
    data=json.dumps(body).encode() if isinstance(body,dict) else body
    request=urllib.request.Request(base+path,data=data,headers=headers,method=method)
    try:r=opener.open(request,timeout=15)
    except urllib.error.HTTPError as e:r=e
    with r:
        raw=r.read()
        if r.status not in ((expected,) if type(expected)is int else expected):raise RuntimeError('probe_http_'+str(r.status)+'_'+path.split('?')[0])
        return json.loads(raw) if 'application/json' in r.headers.get('Content-Type','') else raw
email='native-'+secrets.token_hex(8)+'@example.invalid';password=secrets.token_urlsafe(32)
user=call('POST','/auth/v1/admin/users',{'email':email,'password':password,'email_confirm':True},service)
session=call('POST','/auth/v1/token?grant_type=password',{'email':email,'password':password})
call('POST','/auth/v1/token?grant_type=password',{'email':email,'password':'incorrect'},expected=400)
factor=call('POST','/auth/v1/factors',{'factor_type':'totp','friendly_name':'Private native acceptance'},session['access_token'])
challenge=call('POST','/auth/v1/factors/'+factor['id']+'/challenge',{},session['access_token'])
secret=factor['totp']['secret'];key=base64.b32decode(secret.upper()+'='*(-len(secret)%8));digest=hmac.new(key,struct.pack('>Q',int(time.time())//30),hashlib.sha1).digest();offset=digest[-1]&15;code=f'{(struct.unpack(">I",digest[offset:offset+4])[0]&0x7fffffff)%1000000:06d}'
elevated=call('POST','/auth/v1/factors/'+factor['id']+'/verify',{'challenge_id':challenge['id'],'code':code},session['access_token'])
claims=json.loads(base64.urlsafe_b64decode(elevated['access_token'].split('.')[1]+'=='));assert claims['aal']=='aal2'
refresh=call('POST','/auth/v1/token?grant_type=refresh_token',{'refresh_token':elevated['refresh_token']});assert refresh['refresh_token']!=elevated['refresh_token']
bucket='native-private-'+secrets.token_hex(8);call('POST','/storage/v1/bucket',{'id':bucket,'name':bucket,'public':False},service)
data=secrets.token_bytes(257);call('POST','/storage/v1/object/'+bucket+'/fixture.bin',data,service,content='application/octet-stream')
assert call('GET','/storage/v1/object/'+bucket+'/fixture.bin',token=service)==data
call('GET','/storage/v1/object/'+bucket+'/fixture.bin',token=anon,expected=(400,403,404))
assert isinstance(call('GET','/rest/v1/tenants?select=tenant_id&limit=1',token=service),list)
calendar=transport_status()
assert calendar=='ok'
identity=os.environ['MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER'];os.environ['MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER']=str(int(identity)+1)
assert transport_status()=='unavailable'
os.environ['MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER']=identity
assert transport_status()=='ok'
try:socket.getaddrinfo('supabase-db',5432)
except socket.gaierror:pass
else:raise RuntimeError('backend_direct_native_database_dns_exposed')
# Designated original-account fixtures for the actual source-owned observer.
# This process runs only under the empty, root-marked disposable VM fixture.
from services.calendar_mutation_service import connect,_verify_connection
subjects=[]
for index in range(2):
    if index==0:
        person,person_email,person_password,person_factor,person_secret,person_token=user,email,password,factor,secret,elevated['access_token']
    else:
        person_email='original-'+secrets.token_hex(8)+'@example.invalid';person_password=secrets.token_urlsafe(32)
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
    with connect() as db:
        with db.transaction():
            _verify_connection(db)
            tenant=db.execute("insert into public.tenants(brand_name,owner_name) values('Native original fixture','Synthetic owner') returning tenant_id").fetchone()[0]
            person_id=db.execute("insert into public.users(auth_id,first_name,last_name,email,tenant_id,account_status,email_verified,email_verified_at) values(%s,'Native','Owner',%s,%s,'active',true,now()) returning id",(person['id'],person_email,tenant)).fetchone()[0]
            db.execute("insert into public.tenant_memberships(tenant_id,user_id,auth_id,role,status) values(%s,%s,%s,'owner','active')",(tenant,person_id,person['id']))
    person_bucket='native-owned-'+secrets.token_hex(8)
    call('POST','/storage/v1/bucket',{'id':person_bucket,'name':person_bucket,'public':False},service)
    person_object=person['id']+'/original.bin';person_bytes=secrets.token_bytes(257)
    call('POST','/storage/v1/object/'+person_bucket+'/'+person_object,person_bytes,person_token,content='application/octet-stream')
    subjects.append({'auth_id':person['id'],'user_id':person_id,'tenant_id':tenant,'email':person_email,
        'password':person_password,'factor_id':person_factor['id'],'totp_secret':person_secret,
        'bucket':person_bucket,'object':person_object,'object_sha256':hashlib.sha256(person_bytes).hexdigest()})
print(json.dumps({'password_login_and_wrong_password_refusal':True,'mfa_aal2':True,'refresh_rotation':True,'private_storage_bytes_sha256':hashlib.sha256(data).hexdigest(),'anonymous_storage_denial':True,'postgrest_query':True,'calendar_transport':calendar,'wrong_system_identifier_refused':True,'backend_direct_native_dns_isolated':True,'gateway_host':base.split('//')[1],'original_schema':146,'private_subjects':subjects}))

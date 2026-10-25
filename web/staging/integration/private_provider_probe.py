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
print(json.dumps({'password_login_and_wrong_password_refusal':True,'mfa_aal2':True,'refresh_rotation':True,'private_storage_bytes_sha256':hashlib.sha256(data).hexdigest(),'anonymous_storage_denial':True,'postgrest_query':True,'calendar_transport':calendar,'wrong_system_identifier_refused':True,'backend_direct_native_dns_isolated':True,'gateway_host':base.split('//')[1],'original_schema':146}))

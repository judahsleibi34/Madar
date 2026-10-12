"""Approved noncustomer account; real public login and persistent profile write.

Never impersonates an existing account or changes a customer password. Native
admin confirmation/disable are restricted to the newly registered exact fixture.
Passwords/tokens remain in process memory; only fixture IDs and outcomes persist.
"""
import http.cookiejar
import json
import secrets
import urllib.request
import uuid


def run(actor,scope,plan_hash,expected_gateway):
    from deployment.lib.emergency_routing_repair import exclusive,encoded
    kernel=actor.candidate();kernel.round(normal=True)
    email='release-check-'+plan_hash[:16]+'@madar.example.com'
    password='Release-'+secrets.token_urlsafe(24)+'-Aa7!'
    auth_id=None;service=None;gateway=None
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    def browser():
        return urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(opener,path,method='GET',body=None,csrf=None):
        headers={'Origin':'https://madarportal.com','User-Agent':'Madar-release-validation/1'}
        if csrf:headers['X-CSRF-Token']=csrf
        if body is not None:headers['Content-Type']='application/json'
        with opener.open(urllib.request.Request('https://madarportal.com/api'+path,
                data=json.dumps(body).encode() if body is not None else None,method=method,headers=headers),timeout=20) as result:
            return json.loads(result.read(65536))
    def admin(body,*,create=False):
        if service is None or gateway is None or (not create and auth_id is None):raise RuntimeError('live_write_fixture_admin_scope_missing')
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        with opener.open(urllib.request.Request(gateway+'/auth/v1/admin/users'+('' if create else '/'+auth_id),
                data=json.dumps(body).encode(),method='POST' if create else 'PUT',
                headers={'apikey':service,'Authorization':'Bearer '+service,'Content-Type':'application/json'}),timeout=15) as result:
            if result.status not in {200,201}:raise RuntimeError('live_write_fixture_admin_failed')
            return json.loads(result.read(65536))
    try:
        rows=kernel.bindings();env=dict(x.split('=',1) for x in rows['backend']['Config']['Env'] if '=' in x)
        service=env['SUPABASE_SERVICE_KEY']
        gateway_row=actor.runtime.inspect(['supabase-envoy'])['supabase-envoy']
        from deployment.lib.completed_normal_resources import measured_spec
        if (gateway_row['Id']!=expected_gateway['id'] or gateway_row['Image']!=expected_gateway['image']
                or measured_spec(gateway_row)!=expected_gateway['spec_sha256']):
            raise RuntimeError('live_write_native_gateway_identity_changed')
        endpoint=gateway_row['NetworkSettings']['Networks'].get(actor.contract['database']['network_name'])
        if (gateway_row['Config'].get('Labels',{}).get('com.docker.compose.service')!='api-gw'
                or gateway_row['Config'].get('Labels',{}).get('com.docker.compose.project')!='madar-local-supabase'
                or not gateway_row['State']['Running'] or endpoint is None
                or endpoint['NetworkID']!=actor.contract['database']['network_id']):
            raise RuntimeError('live_write_native_gateway_changed')
        gateway='http://'+endpoint['IPAddress']+':8000'
        # The approved synthetic identity is created confirmed through native
        # Auth admin, never by changing an existing account. Public signup's
        # verified-orphan flow then performs ordinary tenant provisioning.
        # This avoids depending on external email delivery for a release test.
        raw=actor.runtime.command(['docker','exec',actor.contract['database']['container_id'],
            'psql','-XqAt','-v','ON_ERROR_STOP=1','-U','postgres','-d','postgres','-c',
            "BEGIN READ ONLY; SELECT count(*) FROM auth.users WHERE email='"+email+"'; COMMIT;"])
        if raw.strip()!='0':raise RuntimeError('live_write_fixture_identity_exists')
        created=admin({'email':email,'password':password,'email_confirm':True},create=True)
        auth_id=str(uuid.UUID(created['id']))
        if created.get('email')!=email:raise RuntimeError('live_write_fixture_identity_changed')
        exclusive(scope/'live-test-fixture.json',encoded({'auth_id':auth_id,'email':email,'customer_account_used':False}))
        opener=browser()
        request(opener,'/auth/signup','POST',{'first_name':'Release','last_name':'Verification','email':email,
            'password':password,'business_name':'Noncustomer release validation','subdomain':'release-check-'+plan_hash[:12],
            'terms_accepted':True})
        login=request(opener,'/auth/login','POST',{'email':email,'password':password})
        user_id=login['user']['id'];csrf=login['csrf_token'];phone='970590'+plan_hash[:6].translate(str.maketrans('abcdef','123456'))
        request(opener,'/users/'+str(user_id)+'/profile','PUT',{'phone':phone},csrf)
        # A fresh authenticated session must read the committed mutation.
        reader=browser();request(reader,'/auth/login','POST',{'email':email,'password':password})
        observed=request(reader,'/users/'+str(user_id)+'/info')
        if observed.get('user',{}).get('phone')!=phone:raise RuntimeError('live_write_authenticated_readback_failed')
        raw=actor.runtime.command(['docker','exec',actor.contract['database']['container_id'],
            'psql','-XqAt','-v','ON_ERROR_STOP=1','-U','postgres','-d','postgres','-c',
            "BEGIN READ ONLY; SELECT phone FROM public.users WHERE auth_id='"+auth_id+"'; COMMIT;"])
        if raw.strip()!=phone:raise RuntimeError('live_write_native_persistence_failed')
        return {'authenticated_login':True,'http_profile_mutation':True,'fresh_session_readback':True,
                'native_database_readback':True,'auth_id':auth_id,'user_id':user_id,'customer_account_used':False,
                'fixture_retained_disabled':True,'existing_customer_mfa_modified':False}
    finally:
        if auth_id is not None and service is not None and gateway is not None:
            admin({'ban_duration':'87600h'})

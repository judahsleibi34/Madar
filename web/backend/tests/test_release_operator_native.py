"""Opt-in genuine GoTrue password/TOTP/current-user tests; no release authority.

Runner provides an internal, owned network and fresh read-only root container.
No business realm, customer records, controller state or host Docker mounted.
"""
import base64
from datetime import datetime,timedelta,timezone
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler,HTTPServer
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import struct
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request,build_opener,ProxyHandler
from deployment.lib import control_plane_upgrade_authorization as auth

ENABLED=os.getenv('MADAR_NATIVE_OPERATOR_IDENTITY')=='1'


@unittest.skipUnless(ENABLED,'Requires the fresh owned native operator identity harness')
class NativeOperatorIdentityTests(unittest.TestCase):
    @classmethod
    def request(cls,method,path,body=None,token=None):
        request=Request('http://auth:9999'+path,method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
        try:response=build_opener(ProxyHandler({})).open(request,timeout=10)
        except HTTPError as error:response=error
        with response:
            value=response.read(512*1024+1)
            if len(value)>512*1024:raise RuntimeError('native_operator_provider_response_limit')
            if response.status not in {200,201,204}:
                raise RuntimeError('native_operator_provider_http_'+str(response.status))
            return json.loads(value) if value else {}

    @classmethod
    def setUpClass(cls):
        if (os.geteuid()!=0 or socket.gethostname()!='madar-operator-native'
                or not os.statvfs('/').f_flag&os.ST_RDONLY
                or not any(r.split()[4]=='/etc/madar' and ' - tmpfs ' in r for r in Path('/proc/self/mountinfo').read_text().splitlines())):
            raise RuntimeError('native_operator_fresh_root_fixture_required')
        cls.key=os.environ['NATIVE_OPERATOR_KEY'].encode()
        now=int(time.time())
        def token(claims):
            encode=lambda v:base64.urlsafe_b64encode(json.dumps(v,separators=(',',':')).encode()).decode().rstrip('=')
            head=encode({'alg':'HS256','typ':'JWT'});body=encode(claims)
            sig=base64.urlsafe_b64encode(hmac.new(cls.key,(head+'.'+body).encode(),hashlib.sha256).digest()).decode().rstrip('=')
            return head+'.'+body+'.'+sig
        cls.admin=token({'role':'service_role','iss':'https://operator.test/auth/v1','aud':'authenticated','iat':now,'exp':now+300})
        password=secrets.token_urlsafe(24);email='operator-'+secrets.token_hex(6)+'@example.test'
        created=cls.request('POST','/admin/users',{'email':email,'password':password,'email_confirm':True},cls.admin)
        cls.identity=created['id'];cls.session=cls.request('POST','/token?grant_type=password',{'email':email,'password':password})
        factor=cls.request('POST','/factors',{'factor_type':'totp','friendly_name':'Independent native test'},cls.session['access_token'])
        cls.factor=factor['id'];challenge=cls.request('POST','/factors/'+cls.factor+'/challenge',{},cls.session['access_token'])
        key=base64.b32decode(factor['totp']['secret'].upper()+'='*(-len(factor['totp']['secret'])%8))
        body=hmac.new(key,struct.pack('>Q',int(time.time())//30),hashlib.sha1).digest();offset=body[-1]&15
        code=str((struct.unpack('>I',body[offset:offset+4])[0]&0x7fffffff)%1000000).zfill(6)
        cls.elevated=cls.request('POST','/factors/'+cls.factor+'/verify',{'challenge_id':challenge['id'],'code':code},cls.session['access_token'])
        # TLS endpoint transparently relays the genuine provider response. It
        # never creates a profile, changes claims, or decides authorization.
        class Proxy(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path!='/user':self.send_error(404);return
                request=Request('http://auth:9999/user',headers={'Authorization':self.headers.get('Authorization','')})
                try:response=build_opener(ProxyHandler({})).open(request,timeout=5)
                except HTTPError as error:response=error
                with response:
                    data=response.read(65537);self.send_response(response.status);self.end_headers();self.wfile.write(data)
            def log_message(self,*args):pass
        cls.server=HTTPServer(('127.0.0.1',443),Proxy)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain('/test-certificate/cert.pem','/test-certificate/key.pem')
        cls.server.socket=context.wrap_socket(cls.server.socket,server_side=True)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.policy={'version':1,'repository':'judahsleibi34/Madar','environment_id':'isolated-operator-native',
            'database_system_identifier':os.environ['NATIVE_OPERATOR_DATABASE_IDENTIFIER'],'controller_sha':'c'*40,
            'operator_auth_ids':[cls.identity],'issuer':'https://operator.test/auth/v1','audience':'authenticated',
            'auth_user_url':'https://127.0.0.1/user','auth_service':None,'key_sha256':hashlib.sha256(cls.key).hexdigest(),
            'valid_until':now+240,'max_token_age_seconds':240,'max_mfa_age_seconds':120}
        auth.RELEASE_OPERATOR_KEY.write_bytes(cls.key);auth.RELEASE_OPERATOR_KEY.chmod(0o600)
        cls.persist()

    @classmethod
    def persist(cls):
        auth.RELEASE_OPERATOR_POLICY.write_text(json.dumps(cls.policy));auth.RELEASE_OPERATOR_POLICY.chmod(0o600)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=2)
        auth.RELEASE_OPERATOR_KEY.unlink();auth.RELEASE_OPERATOR_POLICY.unlink()

    def authenticate(self,token=None,**change):
        return auth.authenticate_release_operator(token or self.elevated['access_token'],
            **dict(environment_id='isolated-operator-native',database_system_identifier=self.policy['database_system_identifier'],
                   controller_sha='c'*40,business_auth_key_sha256='f'*64,**change))

    def test_01_real_password_and_totp_current_provider_observe_infrastructure_identity(self):
        result=self.authenticate()
        self.assertEqual(result['operator_auth_id'],self.identity);self.assertEqual(result['aal'],'aal2')
        self.assertNotIn('authority',result);self.assertNotIn('token',result)

    def test_02_real_password_only_session_refuses(self):
        with self.assertRaisesRegex(RuntimeError,'identity_or_mfa_refused'):self.authenticate(self.session['access_token'])

    def test_03_same_business_key_and_foreign_database_refuse(self):
        with self.assertRaisesRegex(RuntimeError,'business_realm'):
            auth.authenticate_release_operator(self.elevated['access_token'],environment_id='isolated-operator-native',
                database_system_identifier=self.policy['database_system_identifier'],controller_sha='c'*40,
                business_auth_key_sha256=hashlib.sha256(self.key).hexdigest())
        with self.assertRaisesRegex(RuntimeError,'policy_invalid'):
            auth.authenticate_release_operator(self.elevated['access_token'],environment_id='isolated-operator-native',
                database_system_identifier='999999',controller_sha='c'*40,business_auth_key_sha256='f'*64)

    def test_05_current_provider_global_logout_refuses_revoked_session(self):
        self.request('POST','/logout?scope=global',token=self.elevated['access_token'])
        with self.assertRaisesRegex(RuntimeError,'current_identity_unverified'):self.authenticate()

    def test_03b_actual_world_readable_policy_is_refused_before_provider(self):
        auth.RELEASE_OPERATOR_POLICY.chmod(0o644)
        try:
            with self.assertRaisesRegex(RuntimeError,'configuration_unprotected'):self.authenticate()
        finally:auth.RELEASE_OPERATOR_POLICY.chmod(0o600)

    def test_03c_actual_hardlinked_verification_key_is_refused(self):
        reference=auth.RELEASE_OPERATOR_KEY.with_name('key-reference')
        os.link(auth.RELEASE_OPERATOR_KEY,reference)
        try:
            with self.assertRaisesRegex(RuntimeError,'configuration_unprotected'):self.authenticate()
        finally:reference.unlink()

    def test_04_current_provider_ban_refuses_even_signed_recent_aal2(self):
        self.request('PUT','/admin/users/'+self.identity,{'ban_duration':'1h'},self.admin)
        try:
            with self.assertRaisesRegex(RuntimeError,'current_identity_unverified'):self.authenticate()
        finally:self.request('PUT','/admin/users/'+self.identity,{'ban_duration':'none'},self.admin)
        self.assertEqual(self.authenticate()['operator_auth_id'],self.identity)


if __name__=='__main__':unittest.main()

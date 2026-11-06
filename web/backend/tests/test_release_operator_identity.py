"""MODEL auth-provider/key fixtures; no real administrator or release approval."""
import base64
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch

from deployment.lib import control_plane_upgrade_authorization as auth
from deployment.lib import control_plane_upgrade as upgrade


class OperatorIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.key=b'synthetic-independent-operator-key-only-0123456789'
        self.identity='11111111-1111-4111-8111-111111111111';now=int(time.time())
        self.policy={'version':1,'repository':'judahsleibi34/Madar','environment_id':'synthetic-model',
            'database_system_identifier':'123456789','controller_sha':'c'*40,'operator_auth_ids':[self.identity],
            'issuer':'https://operator-identity.example/auth/v1','audience':'authenticated',
            'auth_user_url':'https://operator-identity.example/auth/v1/user','auth_service':None,
            'key_sha256':hashlib.sha256(self.key).hexdigest(),'valid_until':now+300,
            'max_token_age_seconds':300,'max_mfa_age_seconds':120}
        self.claims={'sub':self.identity,'iss':self.policy['issuer'],'aud':'authenticated','role':'authenticated',
            'aal':'aal2','iat':now,'exp':now+300,'amr':[{'method':'password','timestamp':now},{'method':'totp','timestamp':now}],
            'session_id':'22222222-2222-4222-8222-222222222222'}
        self.policy_file=self.root/'operator.json';self.key_file=self.root/'key';self.key_file.write_bytes(self.key);self.key_file.chmod(0o600)
        self.enterContext(patch.object(auth,'RELEASE_OPERATOR_POLICY',self.policy_file))
        self.enterContext(patch.object(auth,'RELEASE_OPERATOR_KEY',self.key_file))
        self.enterContext(patch.object(auth.os,'geteuid',return_value=0))
        # MODEL file ownership only. Native root filesystem tests are separate;
        # this does not grant the test process root or bypass a real reader.
        original_fstat=os.fstat
        def metadata(fd):
            original=original_fstat(fd)
            return SimpleNamespace(st_mode=original.st_mode,st_uid=0,st_nlink=original.st_nlink,st_size=original.st_size)
        self.enterContext(patch.object(auth.os,'fstat',side_effect=metadata))
        self.enterContext(patch.object(Path,'lstat',return_value=SimpleNamespace(st_uid=0,st_mode=0o40755)))
        self.response=MagicMock();self.response.status=200;self.response.__enter__.return_value=self.response
        self.response.read.return_value=json.dumps({'id':self.identity,'factors':[{'factor_type':'totp','status':'verified'}]}).encode()
        self.opener=MagicMock();self.opener.open.return_value=self.response
        self.enterContext(patch('urllib.request.build_opener',return_value=self.opener))

    def token(self,*,claims=None,header=None,key=None):
        def encode(value):return base64.urlsafe_b64encode(json.dumps(value,separators=(',',':')).encode()).decode().rstrip('=')
        head=encode(header or {'alg':'HS256','typ':'JWT'});body=encode(self.claims if claims is None else claims)
        signature=hmac.new(key or self.key,(head+'.'+body).encode(),hashlib.sha256).digest()
        return head+'.'+body+'.'+base64.urlsafe_b64encode(signature).decode().rstrip('=')

    def authenticate(self,token=None,**changes):
        self.policy_file.write_text(json.dumps(self.policy));self.policy_file.chmod(0o600)
        arguments={'environment_id':'synthetic-model','database_system_identifier':'123456789',
            'controller_sha':'c'*40,'business_auth_key_sha256':'f'*64};arguments.update(changes)
        return auth.authenticate_release_operator(token or self.token(),**arguments)

    def test_independent_whitelisted_recent_aal2_identity_is_observed_not_authorized(self):
        result=self.authenticate()
        self.assertEqual(result['operator_auth_id'],self.identity);self.assertEqual(result['aal'],'aal2')
        self.assertNotIn('authority',result);self.assertNotIn('token',result)
        self.assertNotIn(self.token(),json.dumps(result));self.assertNotIn(self.key.decode(),json.dumps(result))
        request=self.opener.open.call_args.args[0]
        self.assertEqual(request.full_url,self.policy['auth_user_url'])
        self.assertEqual(self.opener.open.call_args.kwargs['timeout'],5)

    def test_tenant_administrator_missing_mfa_stale_wrong_issuer_or_role_refuse_before_network(self):
        cases=[{'sub':'33333333-3333-4333-8333-333333333333','user_metadata':{'role':'infrastructure_admin'}},
            {'aal':'aal1'},{'amr':[{'method':'password','timestamp':int(time.time())}]},
            {'amr':[{'method':'totp','timestamp':int(time.time())-1000}]},
            {'iat':int(time.time())-1000},{'exp':int(time.time())-1},
            {'iss':'https://business-identity.example/auth/v1'},{'aud':'service_role'},
            {'role':'service_role'},{'session_id':'not-a-session'},{'iat':True}]
        for changes in cases:
            with self.subTest(changes=changes),self.assertRaises(RuntimeError):self.authenticate(self.token(claims=dict(self.claims,**changes)))
        self.opener.open.assert_not_called()

    def test_forged_signature_algorithm_key_and_same_business_realm_refuse(self):
        for token in (self.token(key=b'another-key'),self.token(header={'alg':'none','typ':'JWT'}),
                      self.token(header={'alg':'HS256','typ':'JWT','jku':'https://attacker.invalid'}),'not-a-token'):
            with self.subTest(token=token[:20]),self.assertRaises(RuntimeError):self.authenticate(token)
        with self.assertRaisesRegex(RuntimeError,'business_realm'):
            self.authenticate(business_auth_key_sha256=hashlib.sha256(self.key).hexdigest())
        self.opener.open.assert_not_called()

    def test_foreign_environment_database_controller_and_expired_policy_refuse(self):
        for changes in ({'environment_id':'production'},{'database_system_identifier':'987654321'},
                        {'controller_sha':'d'*40}):
            with self.assertRaises(RuntimeError):self.authenticate(**changes)
        self.policy['valid_until']=int(time.time())-1
        with self.assertRaises(RuntimeError):self.authenticate()
        self.opener.open.assert_not_called()

    def test_current_provider_denial_foreign_identity_and_ban_refuse(self):
        for profile in ({'id':'33333333-3333-4333-8333-333333333333'},
                        {'id':self.identity,'banned_until':'2999-01-01T00:00:00Z'},
                        {'id':self.identity,'factors':[]},
                        {'id':self.identity,'factors':[{'factor_type':'totp','status':'verified'}],'is_anonymous':True}):
            self.response.read.return_value=json.dumps(profile).encode()
            with self.assertRaisesRegex(RuntimeError,'current_identity_unverified'):self.authenticate()
        self.opener.open.side_effect=OSError('synthetic private bearer must not enter diagnostics')
        with self.assertRaisesRegex(RuntimeError,'current_identity_unverified') as error:self.authenticate()
        self.assertNotIn('bearer',str(error.exception))

    def test_http_cannot_bypass_live_isolated_environment_observation(self):
        self.policy['auth_user_url']='http://10.0.0.5:9999/user'
        with patch('deployment.lib.isolated_release_environment.observe',side_effect=RuntimeError('synthetic_foreign_guest')):
            with self.assertRaisesRegex(RuntimeError,'foreign_guest'):self.authenticate()
        self.opener.open.assert_not_called()

    def test_unprivileged_caller_never_reads_private_configuration(self):
        with patch.object(auth.os,'geteuid',return_value=1000),patch.object(auth.os,'open') as opened:
            with self.assertRaisesRegex(RuntimeError,'root_reader_required'):self.authenticate()
            opened.assert_not_called()


class OperatorCliTests(unittest.TestCase):
    def test_identity_cli_does_not_install_issue_authority_or_leak_token(self):
        operations=MagicMock();operations.authenticate_operator.return_value={'operator_auth_id':'synthetic-identity','aal':'aal2'}
        output=io.StringIO()
        with patch.object(upgrade.os,'geteuid',return_value=0),patch.object(upgrade,'SystemOperations',return_value=operations),\
                patch.object(upgrade.sys,'stdin',io.StringIO('synthetic-sensitive-access-token\n')),patch.object(upgrade.sys,'stdout',output):
            self.assertEqual(upgrade.main(['c'*40,'--authenticate-operator']),0)
        operations.authenticate_operator.assert_called_once_with('synthetic-sensitive-access-token')
        operations.prepare_upgrade_roots.assert_not_called();operations.write_authorization.assert_not_called()
        result=json.loads(output.getvalue());self.assertFalse(result['authority_issued']);self.assertFalse(result['release_approved'])
        self.assertNotIn('sensitive',output.getvalue())


if __name__=='__main__':unittest.main()

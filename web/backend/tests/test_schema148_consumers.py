import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib.schema148_consumers import foreign_service_credential,unrelated_consumers,host_processes


def token(secret,*,role='service_role',expiry=1,algorithm='HS256'):
    encode=lambda value:base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
    body=encode({'alg':algorithm})+'.'+encode({'role':role,'exp':expiry})
    return body+'.'+base64.urlsafe_b64encode(hmac.new(secret.encode(),body.encode(),hashlib.sha256).digest()).decode().rstrip('=')


class ConsumerScopeTests(unittest.TestCase):
    def test_different_jwt_is_not_different_signing_authority_even_if_expired(self):
        secret='synthetic-target-secret-not-production'*2
        for expiry in (1,9999999999):self.assertFalse(foreign_service_credential(token(secret,expiry=expiry),secret))
        self.assertTrue(foreign_service_credential(token('synthetic-other-secret'*2),secret))
    def test_malformed_unknown_role_algorithm_and_signing_scheme_refuse(self):
        secret='synthetic-target-secret-not-production'*2
        for value in (None,'malformed',token(secret,role='anon'),token(secret,algorithm='none')):
            with self.subTest(value_type=type(value).__name__),self.assertRaises(RuntimeError):foreign_service_credential(value,secret)
        for key in ('short','{"keys":[]}','@/unknown/key-file-which-is-not-an-inline-key'):
            with self.assertRaises(RuntimeError):foreign_service_credential(token(secret),key)
    def fixture(self):
        native={'Id':'a'*64,'Image':'sha256:'+'1'*64,'Name':'/supabase-db','Config':{'Hostname':'native-db','Env':[]},
            'NetworkSettings':{'Networks':{'native':{'NetworkID':'b'*64,'Aliases':['db']}}}}
        rest={'Id':'c'*64,'Name':'/supabase-rest','Image':'sha256:'+'4'*64,'State':{'Running':True},'Config':{'Env':['PGRST_DB_URI=postgres://fixture@db:5432/postgres','PGRST_JWT_SECRET='+'synthetic-native-secret'*2]},
            'NetworkSettings':{'Networks':{'native':{'NetworkID':'b'*64,'IPAddress':'172.20.0.2'}}}}
        other={'Id':'d'*64,'Image':'sha256:'+'2'*64,'Config':{'Env':['SUPABASE_SERVICE_KEY='+token('synthetic-other-secret'*2)]}}
        contract={'database':{'container_id':native['Id'],'image':native['Image'],'network_id':'b'*64}}
        bindings={other['Id']:{'image':other['Image'],'spec_sha256':'e'*64}}
        candidate={'Id':'f'*64,'Config':{'Env':['SUPABASE_SERVICE_KEY='+token('synthetic-native-secret'*2)]}}
        return [native,rest,other,candidate],contract,bindings
    def test_reviewed_different_authority_scope_leaves_unrelated_worker_untouched(self):
        rows,contract,bindings=self.fixture()
        with patch('deployment.lib.completed_normal_resources.measured_spec_matches',return_value=True),patch('deployment.lib.schema148_consumers.authorization_probe',side_effect=[(200,[{'schema_version':146}]),(401,{'code':'PGRST301'})]):
            self.assertEqual(unrelated_consumers(rows,contract,bindings,candidate_ids={'f'*64},target_rest_binding={'id':'c'*64,'image':'sha256:'+'4'*64,'spec_sha256':'e'*64}),{'d'*64})
    def test_shared_secret_direct_database_credentials_and_changed_spec_refuse(self):
        for reason in ('shared','direct','spec','base64','database'):
            rows,contract,bindings=self.fixture()
            if reason=='shared':rows[2]['Config']['Env']=['SUPABASE_SERVICE_KEY='+token('synthetic-native-secret'*2)]
            elif reason=='direct':rows[2]['Config']['Env'].append('DATABASE_URL=synthetic-direct-credential')
            elif reason=='base64':rows[1]['Config']['Env'].append('PGRST_JWT_SECRET_IS_BASE64=true')
            elif reason=='database':contract['database']['image']='sha256:'+'9'*64
            with patch('deployment.lib.completed_normal_resources.measured_spec_matches',return_value=reason!='spec'),patch('deployment.lib.schema148_consumers.authorization_probe',return_value=(200,[{'schema_version':146}])):
                with self.subTest(reason=reason),self.assertRaises(RuntimeError):unrelated_consumers(rows,contract,bindings,candidate_ids={'f'*64},target_rest_binding={'id':'c'*64,'image':'sha256:'+'4'*64,'spec_sha256':'e'*64})
    def test_manual_host_worker_or_docker_exec_in_unrelated_container_refuses(self):
        identifier='a'*64
        for group in ('0::/user.slice/session.scope','0::/docker/'+'b'*64):
            runtime=SimpleNamespace(command=lambda args:'123 python notification_worker.py' if args[0]=='ps' else group)
            with self.subTest(group_kind=group[:10]),self.assertRaises(RuntimeError):host_processes(runtime,{identifier},required_pids={123})
    def test_positive_process_visibility_control_is_required(self):
        identifier='a'*64
        runtime=SimpleNamespace(command=lambda args:'123 python -m workers.notification_worker' if args[0]=='ps' else '0::/system.slice/docker-'+identifier+'.scope')
        self.assertEqual(host_processes(runtime,{identifier},required_pids={123}),1)
        runtime.command=lambda args:''
        with self.assertRaisesRegex(RuntimeError,'visibility_unverified'):host_processes(runtime,{identifier},required_pids={123})


class LiveConsumerCollectorTests(ConsumerScopeTests):
    # Reuse the fixture only; do not repeat the parent class's assertions here.
    test_different_jwt_is_not_different_signing_authority_even_if_expired=None
    test_malformed_unknown_role_algorithm_and_signing_scheme_refuse=None
    test_reviewed_different_authority_scope_leaves_unrelated_worker_untouched=None
    test_shared_secret_direct_database_credentials_and_changed_spec_refuse=None
    test_manual_host_worker_or_docker_exec_in_unrelated_container_refuses=None
    test_positive_process_visibility_control_is_required=None

    def test_native_collection_excludes_only_bound_foreign_worker_and_requires_host_visibility(self):
        from deployment.lib.schema148_release import live_consumer_inventory
        rows,contract,bindings=self.fixture()
        old='9'*64;new='f'*64;foreign='d'*64
        contract.update(origin={'images':{'backend':'sha256:'+'7'*64}},candidate={'images':{'backend':'sha256:'+'8'*64}})
        rows[-1].update(Image=contract['candidate']['images']['backend'],Name='/candidate',State={'Running':True,'Pid':777},HostConfig={'RestartPolicy':{'Name':'no'}})
        rows[-1]['Config']['Cmd']=['python','-m','workers.notification_worker']
        rows[-2].update(Name='/unrelated',State={'Running':True,'Pid':888},HostConfig={'RestartPolicy':{'Name':'always'}})
        rows[-2]['Config']['Cmd']=['python','-m','workers.notification_worker']
        rows.append({'Id':old,'Image':contract['origin']['images']['backend'],'Name':'/origin','Config':{'Env':[],'Cmd':['python','-m','workers.notification_worker']},'State':{'Running':False,'Pid':0},'HostConfig':{'RestartPolicy':{'Name':'no'}}})
        policy={'version':1,'operation':'notification-protocol2-exclusive-cutover','legacy_consumers':{old:contract['origin']['images']['backend']},
            'unrelated_consumers':bindings,'target_rest':{'id':'c'*64,'image':'sha256:'+'4'*64,'spec_sha256':'e'*64}}
        def command(args):
            if args[0]=='ps':return '777 python -m workers.notification_worker\n888 python -m workers.notification_worker'
            return '0::/docker/'+(new if '/777/' in args[1] else foreign)
        runtime=SimpleNamespace(command=command)
        with patch('deployment.lib.completed_normal_resources.measured_spec_matches',return_value=True),patch('deployment.lib.schema148_consumers.authorization_probe',side_effect=[(200,[{'schema_version':146}]),(401,{'code':'PGRST301'})]):
            result=live_consumer_inventory(runtime,contract,policy,{new},rows=rows)
            self.assertEqual((result['unrelated_consumers_verified'],result['host_processes_verified']),(1,2))
        # A mere expired/claims-denied credential is not cryptographic separation.
        with patch('deployment.lib.completed_normal_resources.measured_spec_matches',return_value=True),patch('deployment.lib.schema148_consumers.authorization_probe',side_effect=[(200,[{'schema_version':146}]),(401,{'code':'PGRST303'})]):
            with self.assertRaises(RuntimeError):live_consumer_inventory(runtime,contract,policy,{new},rows=rows)

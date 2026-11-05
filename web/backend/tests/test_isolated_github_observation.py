"""Real signatures and request filesystem; network/process observations modeled."""
import base64,copy,hashlib,json,tempfile,time,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from deployment.lib import isolated_github_observation as g
from deployment.lib.migration_inventory import canonical,digest


class GitHubObservationTests(unittest.TestCase):
    def setUp(self):
        self.now=int(time.time());self.key=Ed25519PrivateKey.generate()
        self.public=self.key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self.endpoint='repos/judahsleibi34/Madar/commits/'+'a'*40
        self.p={'version':1,'kind':'isolated-parent-github-observation','environment_id':'isolated-'+str(uuid.uuid4()),
            'guest_uuid':str(uuid.uuid4()),'machine_id':'b'*32,'root_filesystem_uuid':str(uuid.uuid4()),
            'database_system_identifier':'123456789','controller_sha':'a'*40,'controller_tree_sha256':'c'*64,
            'test_public_key_sha256':hashlib.sha256(self.public).hexdigest(),'expires_at':self.now+300,
            'denied_database_identifiers':['987654321'],'endpoints':[self.endpoint]}
        self.request={'version':1,'kind':'isolated-read-only-github-query','policy_sha256':digest(self.p),
            **{k:self.p[k] for k in g.SCOPE},'nonce':str(uuid.uuid4()),'endpoint':self.endpoint,
            'created_at':self.now,'expires_at':self.now+60}
        self.value={'sha':'a'*40,'commit':{'tree':{'sha':'d'*40}}}

    def packet(self,request=None,value=None):
        payload={'version':1,'kind':'isolated-parent-github-response','request':request or self.request,
            'observed_at':self.now,'response':value or self.value,'response_sha256':digest(value or self.value)}
        return {'payload':payload,'signature':base64.b64encode(self.key.sign(canonical(payload))).decode()}

    def test_real_signature_authenticates_metadata_not_a_deployment_approval(self):
        self.assertEqual(g.verify_response(self.packet(),self.request,self.p,self.public,now=self.now),self.value)
        self.assertNotIn('approval',self.packet()['payload'])

    def test_wrong_nonce_commit_policy_database_guest_and_expiry_are_not_reusable(self):
        for key,value in (('nonce',str(uuid.uuid4())),('endpoint',self.endpoint[:-1]+'f'),
                ('database_system_identifier','555555555'),('guest_uuid',str(uuid.uuid4())),
                ('controller_sha','f'*40),('policy_sha256','f'*64),('expires_at',self.now)):
            request=dict(self.request,**{key:value})
            with self.subTest(key=key),self.assertRaises(RuntimeError):
                g.verify_response(self.packet(request=request),self.request,self.p,self.public,now=self.now)
        with self.assertRaises(RuntimeError):g.verify_response(self.packet(),self.request,self.p,self.public,now=self.now+61)

    def test_forged_signature_wrong_key_and_changed_api_response_refuse(self):
        packet=self.packet();packet['payload']['response']['sha']='f'*40
        for altered in (packet,dict(self.packet(),signature=base64.b64encode(b'x'*64).decode())):
            with self.assertRaisesRegex(RuntimeError,'signature'):g.verify_response(altered,self.request,self.p,self.public,now=self.now)
        with self.assertRaisesRegex(RuntimeError,'envelope'):
            g.verify_response(self.packet(),self.request,self.p,b'x'*32,now=self.now)

    def test_unknown_hosts_mutation_routes_and_caller_query_options_are_refused(self):
        for endpoint in ('https://evil.invalid/api','repos/attacker/Madar/commits/'+'a'*40,
                self.endpoint+'?token=secret','repos/judahsleibi34/Madar/pulls/221/merge',
                'repos/judahsleibi34/Madar/actions/artifacts/1/zip',self.endpoint+'\n--method=POST'):
            with self.subTest(endpoint=endpoint):self.assertFalse(g.endpoint_allowed(endpoint))
        for workflow in ('backend-check','frontend-check','migration-safety','full-provider-staging','schema148-artifacts'):
            self.assertTrue(g.endpoint_allowed('repos/judahsleibi34/Madar/actions/workflows/'+workflow+'.yml/runs?head_sha='+'a'*40+'&per_page=100'))

    def test_parent_must_execute_fixed_real_api_not_sign_caller_supplied_response(self):
        answer=SimpleNamespace(returncode=0,stdout=canonical(self.value))
        with patch.object(g.subprocess,'run',return_value=answer) as query:
            packet=g.observe_on_parent(self.request,self.p,self.key)
        self.assertEqual(g.verify_response(packet,self.request,self.p,self.public,now=int(time.time())),self.value)
        self.assertEqual(query.call_args.args[0],['/usr/bin/gh','api','--hostname','github.com','--method','GET',self.endpoint])
        self.assertNotIn('GH_HOST',query.call_args.kwargs['env']);self.assertNotIn('GH_TOKEN',query.call_args.kwargs['env'])
        with patch.object(g.subprocess,'run') as query:
            with self.assertRaisesRegex(RuntimeError,'parent_key_changed'):g.observe_on_parent(self.request,self.p,Ed25519PrivateKey.generate())
            query.assert_not_called()

    def test_parent_errors_duplicate_keys_and_expiration_after_query_refuse(self):
        for result in (SimpleNamespace(returncode=1,stdout=b''),SimpleNamespace(returncode=0,stdout=b'{"sha":1,"sha":2}')):
            with self.subTest(result=result),patch.object(g.subprocess,'run',return_value=result),self.assertRaises((RuntimeError,ValueError)):
                g.observe_on_parent(self.request,self.p,self.key)
        with patch.object(g.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'{}')),\
                patch.object(g.time,'time',side_effect=[self.now,self.now,self.now,self.now,self.now+61]),self.assertRaisesRegex(RuntimeError,'freshness'):
            g.observe_on_parent(self.request,self.p,self.key)

    def test_transient_get_retries_same_nonce_then_verifies_real_signature(self):
        failed=SimpleNamespace(returncode=1,stdout=b'',stderr=b'gh: unavailable (HTTP 503)')
        success=SimpleNamespace(returncode=0,stdout=canonical(self.value))
        with patch.object(g.subprocess,'run',side_effect=[failed,success]) as run,patch.object(g.time,'sleep'):
            packet=g.observe_on_parent(self.request,self.p,self.key)
        self.assertEqual(run.call_count,2)
        self.assertEqual(run.call_args_list[0].args,run.call_args_list[1].args)
        self.assertLessEqual(run.call_args.kwargs['timeout'],15)
        self.assertEqual(g.verify_response(packet,self.request,self.p,self.public,now=self.now),self.value)

    def test_permanent_api_errors_never_retry_or_expose_stderr(self):
        for status in (401,403,404,422):
            with self.subTest(status=status),patch.object(g.subprocess,'run',return_value=SimpleNamespace(
                    returncode=1,stdout=b'',stderr=f'PRIVATE TOKEN (HTTP {status})'.encode())) as run:
                with self.assertRaises(g.ParentObservationError) as caught:g.observe_on_parent(self.request,self.p,self.key)
                self.assertEqual(run.call_count,1);self.assertNotIn('PRIVATE',str(caught.exception))
                self.assertEqual(caught.exception.diagnostic['http_status'],status)

    def test_transient_attempts_are_bounded_and_do_not_sign_failure(self):
        with patch.object(g.subprocess,'run',side_effect=g.subprocess.TimeoutExpired('gh',15)) as run,patch.object(g.time,'sleep'):
            with self.assertRaisesRegex(g.ParentObservationError,'transport_timeout:attempts=3'):
                g.observe_on_parent(self.request,self.p,self.key)
            self.assertEqual(run.call_count,3)

    def test_retry_revalidates_original_expiry_and_never_renews_it(self):
        now=[self.now]
        def expire(_):now[0]=self.request['expires_at']
        with patch.object(g.time,'time',side_effect=lambda:now[0]),patch.object(g.time,'sleep',side_effect=expire),\
                patch.object(g.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout=b'',stderr=b'(HTTP 502)')) as run:
            with self.assertRaisesRegex(RuntimeError,'freshness'):g.observe_on_parent(self.request,self.p,self.key)
            self.assertEqual(run.call_count,1)
        self.assertEqual(self.request['expires_at'],self.now+60)

    def test_insufficient_transport_budget_refuses_without_query(self):
        request=dict(self.request,expires_at=self.now+1)
        with patch.object(g.subprocess,'run') as run,self.assertRaisesRegex(g.ParentObservationError,'deadline'):
            g.observe_on_parent(request,self.p,self.key)
        run.assert_not_called()

    def test_root_query_waits_for_nonce_bound_signature_and_preserves_compact_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);policy=root/'policy';policy.write_text('{}')
            def respond(delay):
                paths=list(root.glob('*.request.json'));self.assertEqual(len(paths),1)
                request=json.loads(paths[0].read_bytes())
                (root/(request['nonce']+'.response.json')).write_bytes(canonical(self.packet(request=request)))
            with patch.object(g,'POLICY',policy),patch.object(g,'ROOT',root),patch.object(g,'policy',return_value=(self.p,self.public)),\
                    patch.object(g,'protected',lambda p,**kw:Path(p)),patch.object(g.time,'sleep',side_effect=respond),\
                    patch('deployment.lib.control_plane_upgrade.require_root_directory'):
                self.assertEqual(g.api(self.endpoint,operations=object()),self.value)
                self.assertFalse(list(root.glob('*.request.json')));self.assertFalse(list(root.glob('*.response.json')))
                audit=json.loads(next(root.glob('*.audit.json')).read_bytes())
                self.assertEqual(audit['result'],'OBSERVED');self.assertFalse(audit['deployment_authority_issued'])
                with self.assertRaisesRegex(RuntimeError,'not_enrolled'):
                    g.api(self.endpoint[:-1]+'f',operations=object())

    def test_missing_policy_preserves_existing_direct_observer_and_invalid_policy_cannot_fallback(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(g,'POLICY',Path(tmp)/'absent'):
            ops=SimpleNamespace(command=Mock(return_value=SimpleNamespace(stdout=json.dumps(self.value))))
            self.assertEqual(g.api(self.endpoint,operations=ops),self.value)
            self.assertEqual(ops.command.call_args.args[1],['/usr/sbin/runuser','-u','madar','--','/usr/bin/gh','api',self.endpoint])
            g.POLICY.write_text('{}');ops.command.reset_mock()
            with patch.object(g,'policy',side_effect=RuntimeError('bad root policy')),self.assertRaisesRegex(RuntimeError,'bad root policy'):
                g.api(self.endpoint,operations=ops)
            ops.command.assert_not_called()

    def test_policy_cannot_target_denied_database_or_unbounded_query_set(self):
        self.assertEqual(g.validate_policy(self.p,now=self.now),self.p)
        for key,value in (('database_system_identifier','987654321'),('expires_at',self.now+10801),
                ('version',True),('endpoints',[self.endpoint,self.endpoint]),('guest_uuid',str(uuid.uuid4()).upper())):
            p=dict(self.p,**{key:value})
            with self.subTest(key=key),self.assertRaises(RuntimeError):g.validate_policy(p,now=self.now)

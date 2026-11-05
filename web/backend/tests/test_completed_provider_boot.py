"""Modeled boot ordering; real KVM reboot remains a separate mandatory gate."""
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from deployment.lib import completed_normal_boot_actor as boot
from deployment.lib import completed_normal_database as database
from deployment.lib.compatible_normal_boot import CompatibleNormalBoot, WORKERS
from deployment.lib.completed_normal_profile import RECONCILED, LEGACY


class CompletedProviderBootTests(unittest.TestCase):
    def setUp(self):
        self.actor = boot.CompletedNormalBootActor.__new__(boot.CompletedNormalBootActor)
        self.actor.profile = RECONCILED
        self.actor.contract = {'source_roles':{'origin_kind':'independently-enrolled-historical-bootstrap-origin'}}
        self.actor.root = Path('/nonexistent/modeled-completed-scope')
        self.calls = []
        self.protocols = '[2,2,2]'
        self.actor.guard = lambda: self.calls.append('guard')
        self.actor.event = lambda *a,**k: self.calls.append('ready')
        self.actor.native = lambda: self.calls.append('schema') or 160
        self.rows = {role:{'Id':role, 'State':{'Running':False,'Health':{'Status':'healthy'}},
                     'NetworkSettings':{'Networks':{'madar-local-supabase_default':{'IPAddress':'172.19.0.5'}}}}
                     for role in ('native:db','native:auth','native:rest','native:storage','native:gateway')}
        self.actor.completed_provider_rows = lambda: self.rows
        def command(args):
            if args[:2]==['docker','exec']:
                self.calls.append('protocols');return self.protocols
            self.calls.append(tuple(args)); self.rows[args[-1]]['State']['Running'] = True
        self.actor.runtime = SimpleNamespace(command=command,budget=lambda _:1,
            http_status=lambda url:self.calls.append('http:'+url))
        self.enterContext(patch.object(boot,'verification_window',lambda *_:nullcontext()))
        self.enterContext(patch.object(boot,'runtime_mutation_lock',lambda *_:nullcontext()))
        self.completion = self.enterContext(patch.object(database,'require_manual_normal_completion',side_effect=lambda *_:self.calls.append('completion')))
        self.authority = self.enterContext(patch.object(boot,'require_candidate_authority',side_effect=lambda *a,**k:self.calls.append('authority')))
        self.boundary = self.enterContext(patch.object(boot,'require_normal_migration_boundary',side_effect=lambda *_:self.calls.append('boundary')))

    def test_completion_and_authority_before_database_then_schema_before_providers(self):
        self.actor.resume_completed_providers()
        starts = [c for c in self.calls if isinstance(c,tuple)]
        self.assertEqual([c[-1] for c in starts],list(self.rows))
        self.assertLess(self.calls.index('completion'),self.calls.index(starts[0]))
        self.assertLess(self.calls.index('authority'),self.calls.index(starts[0]))
        self.assertLess(self.calls.index('boundary'),self.calls.index(starts[1]))
        self.assertEqual(self.calls[-1],'ready')

    def test_missing_completion_and_grant_issue_no_start(self):
        for guard in (self.completion,self.authority):
            guard.side_effect=RuntimeError('refused')
            with self.assertRaisesRegex(RuntimeError,'refused'):self.actor.resume_completed_providers()
            self.assertFalse(any(isinstance(c,tuple) for c in self.calls))
            guard.side_effect=None

    def test_wrong_committed_schema_never_starts_provider(self):
        self.actor.native=lambda:159
        with self.assertRaisesRegex(RuntimeError,'schema_changed'):self.actor.resume_completed_providers()
        self.assertEqual([c[-1] for c in self.calls if isinstance(c,tuple)],['native:db'])

    def test_missing_or_incompatible_protocols_never_start_other_providers(self):
        for value in ('[2,2,0]', '[2,1,2]', '[]', '{}'):
            self.protocols=value
            for row in self.rows.values():row['State']['Running']=False
            self.calls.clear()
            with self.subTest(protocols=value),self.assertRaises(RuntimeError):self.actor.resume_completed_providers()
            self.assertEqual([c[-1] for c in self.calls if isinstance(c,tuple)],['native:db'])

    def test_unknown_commit_never_starts_provider(self):
        self.boundary.side_effect=RuntimeError('uncertain_commit')
        with self.assertRaisesRegex(RuntimeError,'uncertain_commit'):self.actor.resume_completed_providers()
        self.assertEqual([c[-1] for c in self.calls if isinstance(c,tuple)],['native:db'])

    def test_changed_inventory_and_interruption_do_not_advance(self):
        self.actor.completed_provider_rows=lambda:(_ for _ in ()).throw(RuntimeError('inventory_changed'))
        with self.assertRaisesRegex(RuntimeError,'inventory_changed'):self.actor.resume_completed_providers()
        self.assertFalse(any(isinstance(c,tuple) for c in self.calls))

    def test_restart_reobserves_without_duplicate_starts(self):
        self.actor.resume_completed_providers();self.calls.clear();self.actor.resume_completed_providers()
        self.assertFalse(any(isinstance(c,tuple) for c in self.calls))
        self.assertIn('boundary',self.calls)

    def test_ordinary_origin_unchanged(self):
        self.actor.profile=LEGACY;self.actor.resume_completed_providers();self.assertEqual(self.calls,[])

    def test_actual_native_roles_without_docker_healthchecks_can_converge(self):
        for role in ('native:rest','native:storage','native:gateway'):
            self.rows[role]['State'].pop('Health')
        self.actor.resume_completed_providers()
        self.assertEqual(sum(c.startswith('http:') for c in self.calls if isinstance(c,str)),6)
        self.assertEqual(self.calls[-1],'ready')

    def test_private_gateway_before_backend_and_consumers(self):
        actor=CompatibleNormalBoot.__new__(CompatibleNormalBoot);calls=[]
        actor.source_guard=lambda:None
        rows={k:{'Id':k} for k in ('redis','parser-worker','provider-gateway','remote-ingestion-worker','backend','frontend',*WORKERS)}
        actor.runtime=SimpleNamespace(inspect=lambda ids:{ids[0]:{'Id':ids[0],'State':{'Running':False}}},command=lambda args:calls.append(args[-1]))
        actor._start(rows)
        self.assertLess(calls.index('provider-gateway'),calls.index('backend'))
        self.assertLess(calls.index('provider-gateway'),calls.index('notification-worker'))


class CompletedProviderReadinessTests(unittest.TestCase):
    def setUp(self):
        self.urls=[]
        self.runtime=SimpleNamespace(http_status=self.urls.append)
        self.row={'State':{'Running':True},'NetworkSettings':{'Networks':{
            'madar-local-supabase_default':{'IPAddress':'172.19.0.8'}}}}

    def test_gateway_requires_all_three_fixed_routes(self):
        self.assertTrue(boot.completed_provider_ready(self.runtime,'native:gateway',self.row))
        self.assertEqual(self.urls,[f'http://172.19.0.8:8000{path}' for path in
            ('/auth/v1/health','/rest/v1/','/storage/v1/status')])

    def test_unready_transport_retries_but_redirect_or_denial_refuses(self):
        for error, transient in ((boot.AvailabilityFailure('pending'),True),(RuntimeError('http_unavailable'),False)):
            self.runtime.http_status=lambda url:(_ for _ in ()).throw(error)
            if transient:self.assertFalse(boot.completed_provider_ready(self.runtime,'native:storage',self.row))
            else:
                with self.assertRaisesRegex(RuntimeError,'http_unavailable'):
                    boot.completed_provider_ready(self.runtime,'native:storage',self.row)

    def test_database_and_auth_still_require_real_docker_health(self):
        for role in ('native:db','native:auth'):
            with self.assertRaisesRegex(RuntimeError,'health_contract_changed'):
                boot.completed_provider_ready(self.runtime,role,self.row)
        self.row['State']['Health']={'Status':'starting'}
        self.assertFalse(boot.completed_provider_ready(self.runtime,'native:rest',self.row))
        self.assertEqual(self.urls,[])

    def test_stopped_foreign_network_and_unknown_role_do_not_probe(self):
        self.row['State']['Running']=False
        self.assertFalse(boot.completed_provider_ready(self.runtime,'native:storage',self.row))
        self.row['State']['Running']=True
        for address in ('8.8.8.8','127.0.0.1','::1','169.254.169.254',''):
            self.row['NetworkSettings']['Networks']['madar-local-supabase_default']['IPAddress']=address
            with self.subTest(address=address),self.assertRaisesRegex(RuntimeError,'probe_network_invalid'):
                boot.completed_provider_ready(self.runtime,'native:storage',self.row)
        with self.assertRaisesRegex(RuntimeError,'role_invalid'):
            boot.completed_provider_ready(self.runtime,'unknown',self.row)
        self.assertEqual(self.urls,[])


class CompletedProviderInventoryTests(unittest.TestCase):
    def setUp(self):
        import tempfile, json
        from deployment.lib.completed_normal_resources import measured_spec
        from test_schema150_actor_inventory import historical_fixture, repin, row
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        actor=self.actor=boot.CompletedNormalBootActor.__new__(boot.CompletedNormalBootActor)
        actor.root=Path(temp.name);actor.profile=RECONCILED
        (data,binding),self.rows=historical_fixture()
        for actual in self.rows:
            actual['HostConfig']['RestartPolicy']['Name']='no'
            actual['State'].update(Running=False,Status='exited')
            record=next(r for r in data['containers'].values() if r['id']==actual['Id'])
            record['spec_sha256']=measured_spec(actual)
            for state in record['states'].values():state['restart']='no'
        data,binding=repin(data,binding)
        actor.contract={'operation':binding['operation'],'candidate':{'source_sha':binding['source_sha'],'controller_sha':binding['controller_sha']},
            'writer_inventory_sha256':binding['inventory_sha256'],'database':{'system_identifier':binding['system_identifier']}}
        extra=row('f'*64,'candidate-backend');extra['State']['Status']='exited';self.rows.append(extra)
        self.inventory=data
        (actor.root/'provider-inventory.json').write_text(json.dumps(data))
        (actor.root/'normal-publication.json').write_text(json.dumps({'runtimes':{'backend':{'id':extra['Id']}}}))
        self.enterContext(patch.object(boot,'protected',lambda p,**_:p))
        self.ownership=self.enterContext(patch('deployment.lib.completed_normal_resources.verify_runtime_binding'))
        def command(args):
            if args[:3]==['docker','ps','-aq']:return '\n'.join(r['Id'] for r in self.rows)
            if args[:3]==['docker','network','inspect']:
                return json.dumps([{'Id':data['target_networks'][args[3]]}])
            self.fail('Unexpected effect '+repr(args))
        actor.runtime=SimpleNamespace(command=command,inspect=lambda ids:{r['Id']:r for r in self.rows if r['Id'] in ids})

    def test_complete_cold_inventory_verified_without_effects(self):
        self.assertEqual(set(self.actor.completed_provider_rows()),{'native:db','native:auth','native:rest','native:storage','native:gateway'})
        self.ownership.assert_called_once()

    def test_foreign_actor_rejected(self):
        from test_schema150_actor_inventory import row
        self.rows.append(row('9'*64,'foreign'))
        with self.assertRaisesRegex(RuntimeError,'inventory_changed'):self.actor.completed_provider_rows()

    def test_changed_identity_spec_and_network_refuse(self):
        import copy
        original=copy.deepcopy(self.rows)
        for case in ('image','spec','network'):
            self.rows=copy.deepcopy(original)
            target=next(r for r in self.rows if r['Id']==self.inventory['containers']['native:auth']['id'])
            if case=='image':target['Image']='sha256:'+'1'*64
            elif case=='spec':target['Config']['Env']=['CHANGED=yes']
            else:next(iter(target['NetworkSettings']['Networks'].values()))['NetworkID']='8'*64
            with self.subTest(case=case),self.assertRaisesRegex(RuntimeError,'actor_changed|network_changed'):
                self.actor.completed_provider_rows()

    def test_original_writer_running_refuses(self):
        target=self.inventory['containers']['origin:backend']['id']
        next(r for r in self.rows if r['Id']==target)['State']['Running']=True
        with self.assertRaisesRegex(RuntimeError,'actor_changed'):self.actor.completed_provider_rows()

    def test_ingress_and_candidate_writers_cannot_precede_database(self):
        for target,code in ((self.inventory['containers']['proxy']['id'],'ingress_not_fenced'),('f'*64,'writers_not_fenced')):
            row=next(r for r in self.rows if r['Id']==target);row['State']['Running']=True
            with self.subTest(target=target),self.assertRaisesRegex(RuntimeError,code):self.actor.completed_provider_rows()
            row['State']['Running']=False

    def test_ambiguous_worker_ownership_refuses_before_inventory_effect(self):
        self.ownership.side_effect=RuntimeError('worker_owner_changed')
        with self.assertRaisesRegex(RuntimeError,'worker_owner_changed'):self.actor.completed_provider_rows()

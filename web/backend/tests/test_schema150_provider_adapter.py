"""Concrete adapter component regressions with synthetic observations.

No Docker, SQL, systemd, production credentials or native effects execute here.
Transport/authorization fixtures isolate call ordering and refusal semantics;
owned temporary files exercise actual flock observation and journal publication.
These tests do not certify the privileged installation or operational profile.
"""
import copy
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import schema150_provider_adapter as adapter
from deployment.lib import schema150_provider_lifecycle as lifecycle
from deployment.lib import schema149_provider_lifecycle as retained
from deployment.lib import schema150_actor_inventory as inventory
from test_schema150_actor_inventory import fixture, phase_rows, repin, row


class ConcreteAdapterTests(unittest.TestCase):
    def component(self, *, stage='prepared', candidates=False):
        """Real adapter methods, synthetic transport and explicit guard injection."""
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        root = Path(temporary.name); root.chmod(0o700)
        journal_root = root/'provider-journal'; journal_root.mkdir(mode=0o700)
        stack = ExitStack(); self.addCleanup(stack.close)
        stack.enter_context(patch.object(retained, 'protected', lambda path, **kwargs: Path(path)))
        stack.enter_context(patch.object(retained, 'require_root_directory', lambda path: None))
        (data, scope), rows = fixture(candidates=candidates)
        actor = adapter.Schema150ProviderAdapter.__new__(adapter.Schema150ProviderAdapter)
        actor.binding, actor.inventory, actor.root = scope, data, root
        actor.contract = {'rehearsal_sha256': '8'*64, 'database': {'container_id': data['containers']['native:db']['id'],
                          'image': data['containers']['native:db']['image']}}
        actor.barrier = root/'provider-barrier.json'
        actor.dropin_name = '99zzzzzz-schema150-'+scope['context_sha256'][:12]+'.conf'
        actor.runtime = Mock(); actor.runtime.command.side_effect = AssertionError('synthetic transport not configured')
        actor.source_guard = Mock()
        actor.lock_descriptors = (101, 102)
        actor.acceptance_guard = Mock(return_value=True)
        actor.activation_guard = Mock(return_value={'target_write_authority': True})
        actor._database_identity = Mock(return_value=150)
        journal = lifecycle.ProtectedProviderJournal(journal_root)
        preimage = {'ingress': {'fixture': True}, 'supervisors': {'sessions': []},
                    'objects': {'roots': data['object_roots']}, 'roles': {'fixture': True}}
        journal.append('prepared', {'binding': scope, 'preimage': preimage, 'proof': {'fixture': True}})
        if stage in {'fenced','private','activating'}:
            for step in lifecycle.FENCE_STEPS:
                journal.append('effect_intent', {'step': step}); journal.append('effect_complete', {'step': step})
        if stage in {'private','activating'}:
            for step in lifecycle.PRIVATE_STEPS:
                journal.append('effect_intent', {'step': step}); journal.append('effect_complete', {'step': step})
            journal.append('private_ready', {'binding_sha256': lifecycle.digest(scope)})
        if stage == 'activating':
            journal.append('effect_intent', {'step': 'resume_accepted_workers'})
        phase = 'prepared' if stage == 'prepared' else 'fenced' if stage == 'fenced' else 'private'
        observed = phase_rows(data, rows, phase)
        if stage == 'activating':
            for value in observed:
                logical = next(k for k,r in data['containers'].items() if r['id']==value['Id'])
                if logical.startswith('candidate:'):
                    value['State']['Running'] = data['containers'][logical]['states']['active']['running']
        actor._rows = Mock(return_value=observed)
        stack.enter_context(patch.object(adapter.os, 'geteuid', return_value=0))
        stack.enter_context(patch.object(adapter, 'require_upgrade_authorization'))
        stack.enter_context(patch.object(adapter, 'require_owned_lock'))
        def private_json(path):
            if Path(path) == adapter.UPGRADE_INTERLOCK:
                return {'status': 'authorized_cycle', 'rehearsal_sha256': actor.contract['rehearsal_sha256']}
            if Path(path) == root/'provider-inventory.json': return copy.deepcopy(data)
            return json.loads(Path(path).read_bytes())
        stack.enter_context(patch.object(adapter, 'private_json', private_json))
        actor._verify_barrier = Mock(side_effect=lambda: None if actor.barrier.exists() else
                                     (_ for _ in ()).throw(RuntimeError('fixture_persistent_barrier_missing')))
        if stage != 'prepared': actor.barrier.write_text('{}')
        return actor, scope, preimage, journal

    def test_initial_fence_guard_precedes_first_persistent_barrier_effect(self):
        actor, scope, _, journal = self.component()
        self.assertEqual([r['event'] for r in journal.read()], ['prepared'])
        self.assertFalse(actor.barrier.exists())
        # The model calls this guard BEFORE recording/performing arm_boot_interlock.
        # An exact prepared journal may enter fence, but no effect can skip arm.
        actor.require_authority(scope, purpose='fence')
        actor.runtime.command.assert_not_called()

    def test_postgrant_activation_evidence_accepts_already_started_accepted_workers(self):
        actor, scope, preimage, _ = self.component(stage='activating', candidates=True)
        result = actor.activation_evidence(scope, preimage)
        self.assertIs(result['target_write_authority'], True)
        actor.activation_guard.assert_called_once_with(scope, private=True)
        actor.runtime.command.assert_not_called()


    def test_default_fresh_credential_validator_refuses_before_transport(self):
        from deployment.lib import control_plane_upgrade_authorization as authorization
        actor, scope, _, _ = self.component()
        missing = actor.root/'unissued-interlock.json'
        # Actual credential validator; only select a synthetic nonexistent path.
        with patch.object(adapter, 'require_upgrade_authorization',
                          lambda sha, **kw: authorization.require_upgrade_authorization(sha, interlock=missing, **kw)):
            with self.assertRaisesRegex(RuntimeError, 'authorization_required'):
                actor.require_authority(scope, purpose='prepare')
        actor.runtime.command.assert_not_called()
        actor._database_identity.assert_not_called()

    def test_scope_nonroot_unknown_purpose_and_wrong_binding_refuse_before_transport(self):
        actor, scope, _, _ = self.component()
        bad = dict(scope, context_sha256='0'*64)
        for binding, purpose in ((bad,'prepare'), (scope,'arbitrary-shell'), (dict(scope,system_identifier='9'),'prepare')):
            with self.subTest(purpose=purpose, binding=binding), self.assertRaisesRegex(RuntimeError, 'effect_scope_invalid'):
                actor.require_authority(binding, purpose=purpose)
        with patch.object(adapter.os, 'geteuid', return_value=1000), self.assertRaisesRegex(RuntimeError, 'effect_scope_invalid'):
            actor.require_authority(scope,purpose='prepare')
        actor.runtime.command.assert_not_called(); actor.source_guard.assert_not_called()

    def test_source_identity_change_refuses_before_any_transport(self):
        actor, scope, _, _ = self.component()
        actor.source_guard.side_effect = RuntimeError('fixture_exact_source_changed')
        with self.assertRaisesRegex(RuntimeError, 'exact_source_changed'):
            actor.require_authority(scope,purpose='prepare')
        actor.runtime.command.assert_not_called(); actor._database_identity.assert_not_called()

    def test_wrong_fresh_rehearsal_or_cycle_status_refuses_before_transport(self):
        actor, scope, _, _ = self.component()
        for authority in ({'status':'consumed','rehearsal_sha256':actor.contract['rehearsal_sha256']},
                          {'status':'authorized_cycle','rehearsal_sha256':'0'*64}):
            with patch.object(adapter,'private_json', return_value=authority):
                with self.assertRaisesRegex(RuntimeError,'fresh_authority_required'):
                    actor.require_authority(scope,purpose='prepare')
        actor.runtime.command.assert_not_called(); actor._database_identity.assert_not_called()

    def test_mutated_inventory_cannot_be_reread_as_new_authority(self):
        actor, scope, _, _ = self.component()
        original = adapter.private_json
        changed = copy.deepcopy(actor.inventory); changed['roles']['authenticator']['login']=False
        def read(path):
            return changed if Path(path).name=='provider-inventory.json' else original(path)
        with patch.object(adapter,'private_json', side_effect=read):
            with self.assertRaisesRegex(RuntimeError,'digest_changed'):
                actor.require_authority(scope,purpose='prepare')
        actor.runtime.command.assert_not_called(); actor._database_identity.assert_not_called()

    def test_unknown_or_substituted_container_refuses_guard_before_mutating_transport(self):
        actor, scope, _, _ = self.component()
        original = copy.deepcopy(actor._rows.return_value)
        unknown = row('f'*64,'unregistered-actor')
        unknown['NetworkSettings']['Networks'] = {inventory.DEFAULT_NETWORK:{'NetworkID':'1'*64,'IPAddress':'','EndpointID':''}}
        for observed in (original+[unknown], [dict(r,Image='sha256:'+'0'*64) if r['Name']=='/supabase-auth' else r for r in original]):
            actor._rows.return_value = observed
            with self.assertRaises(RuntimeError): actor.require_authority(scope,purpose='prepare')
        actor.runtime.command.assert_not_called()

    def test_changed_mount_network_credential_scope_and_source_are_immutable(self):
        actor, scope, _, _ = self.component()
        original = copy.deepcopy(actor._rows.return_value)
        for kind in ('mount','network','credential','source'):
            rows = copy.deepcopy(original); subject=next(r for r in rows if r['Name']=='/supabase-auth')
            if kind=='mount': subject['Mounts']=[{'Type':'bind','Source':'/unexpected','Destination':'/data','RW':True}]
            if kind=='network': subject['NetworkSettings']['Networks']['unknown']={'NetworkID':'9'*64,'IPAddress':'','EndpointID':''}
            if kind=='credential': subject['Config']['Env'].append('INJECTED_CREDENTIAL=other')
            if kind=='source': subject['Config']['Labels']['org.opencontainers.image.revision']='0'*40
            actor._rows.return_value=rows
            with self.subTest(kind=kind), self.assertRaises(RuntimeError): actor.require_authority(scope,purpose='prepare')
        actor.runtime.command.assert_not_called()

    def test_actual_database_identity_checks_cluster_schema_container_and_image(self):
        actor, _, _, _ = self.component()
        del actor._database_identity
        actor._sql=Mock()
        for observed in (['other-cluster',146],[actor.binding['system_identifier'],151],
                         [actor.binding['system_identifier'],True],[actor.binding['system_identifier'],'150']):
            actor._sql.return_value=json.dumps(observed)
            with self.subTest(observed=observed), self.assertRaisesRegex(RuntimeError,'database_identity_changed'):
                actor._database_identity()
        actor._sql.return_value=json.dumps([actor.binding['system_identifier'],150])
        self.assertEqual(actor._database_identity(),150)
        for key,value in (('container_id','0'*64),('image','sha256:'+'0'*64)):
            original=actor.contract['database'][key];actor.contract['database'][key]=value
            with self.assertRaisesRegex(RuntimeError,'database_substitution'):actor._database_identity()
            actor.contract['database'][key]=original
        actor.runtime.command.assert_not_called()

    def test_actual_flock_observation_requires_owned_exclusive_same_inode_without_acquiring(self):
        # This test restores the actual observer; temporary path ownership policy
        # is injected, but fstat, /proc fdinfo and kernel flock are real.
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'owned.lock'; other=Path(directory)/'other.lock'
            descriptor=os.open(path,os.O_CREAT|os.O_RDWR,0o600)
            other_descriptor=os.open(other,os.O_CREAT|os.O_RDWR,0o600)
            try:
                with patch.object(adapter,'protected',lambda value,**kwargs:Path(value)):
                    with self.assertRaisesRegex(RuntimeError,'not_held'):adapter.require_owned_lock(descriptor,path)
                    fcntl.flock(other_descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    with self.assertRaisesRegex(RuntimeError,'lock_changed'):adapter.require_owned_lock(other_descriptor,path)
                    fcntl.flock(descriptor,fcntl.LOCK_SH|fcntl.LOCK_NB)
                    with self.assertRaisesRegex(RuntimeError,'not_held'):adapter.require_owned_lock(descriptor,path)
                    fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    adapter.require_owned_lock(descriptor,path)
                    for invalid in (-1,True,'3'):
                        with self.subTest(invalid=invalid), self.assertRaisesRegex(RuntimeError,'lock_required'):
                            adapter.require_owned_lock(invalid,path)
                    fcntl.flock(descriptor,fcntl.LOCK_UN)
                    with self.assertRaisesRegex(RuntimeError,'not_held'):adapter.require_owned_lock(descriptor,path)
                    # A second FD can still acquire: observation did not acquire it.
                    independent=os.open(path,os.O_RDWR)
                    try:fcntl.flock(independent,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    finally:os.close(independent)
            finally:os.close(descriptor);os.close(other_descriptor)

    def test_role_measurement_pins_all_attributes_memberships_and_login_separately(self):
        roles={'roles':{'postgres':{'rolcanlogin':True,'rolsuper':True,'rolpassword':'synthetic-private-verifier'},
                        'authenticator':{'rolcanlogin':True,'rolsuper':False}},'memberships':[
                        {'role':'postgres','member':'authenticator','grantor':'postgres','admin_option':False}]}
        measured=adapter.role_measurements(roles)
        self.assertNotIn('synthetic-private-verifier',json.dumps(measured))
        for kind in ('password','superuser','membership','login'):
            changed=copy.deepcopy(roles)
            if kind=='password':changed['roles']['postgres']['rolpassword']='synthetic-other-verifier'
            elif kind=='superuser':changed['roles']['postgres']['rolsuper']=False
            elif kind=='membership':changed['memberships'][0]['admin_option']=True
            else:changed['roles']['postgres']['rolcanlogin']=False
            self.assertNotEqual(adapter.role_measurements(changed),measured)
        reversed_roles=copy.deepcopy(roles);reversed_roles['memberships'].reverse()
        self.assertEqual(adapter.role_measurements(reversed_roles),measured)

    def test_capture_preimage_refuses_changed_full_roles_and_unknown_sessions(self):
        actor, scope, _, _ = self.component()
        actor.require_authority=Mock();actor._attest=Mock()
        roles={'roles':{name:{'rolcanlogin':True,'rolsuper':name=='postgres'} for name in inventory.MINIMUM_ROLES},'memberships':[]}
        actor.inventory['roles']=adapter.role_measurements(roles)
        actor._roles=Mock(return_value=copy.deepcopy(roles));actor._sessions=Mock(return_value=[])
        actor._unit=Mock(return_value={'fixture':'effective-unit'});actor._known_sessions=Mock(return_value=True)
        # This role-capture component test has synthetic paths. Real read-only
        # filesystem measurements are independently exercised in object tests.
        actor._object_measurement=Mock(return_value={'version':1,'phase':'identity','roots':{}})
        archive='-- synthetic independent roles-only archive\nCREATE ROLE synthetic;\n'
        actor.runtime.command.side_effect=None;actor.runtime.command.return_value=archive
        result=actor.capture_preimage(scope)
        self.assertEqual(result['roles']['original'],roles)
        actor._object_measurement.assert_called_once_with(phase='identity')
        self.assertEqual(result['roles']['sha256'],hashlib.sha256(archive.encode()).hexdigest())
        actor.runtime.command.reset_mock();actor._roles.return_value['roles']['postgres']['rolsuper']=False
        with self.assertRaisesRegex(RuntimeError,'measured_role_scope_changed'):actor.capture_preimage(scope)
        actor.runtime.command.assert_not_called()
        actor._roles.return_value=roles;actor._known_sessions.return_value=False
        with self.assertRaisesRegex(RuntimeError,'unknown_session'):actor.capture_preimage(scope)

    def test_backup_uses_preserved_original_full_role_archive_not_current_nologin(self):
        actor, scope, _, _ = self.component(stage='fenced')
        roles={'roles':{name:{'rolcanlogin':True,'rolsuper':False} for name in inventory.MINIMUM_ROLES},'memberships':[]}
        actor.inventory['roles']=adapter.role_measurements(roles)
        archive='-- original roles with original login and private verifier\n'
        original={'original':roles,'archive':archive,'sha256':hashlib.sha256(archive.encode()).hexdigest()}
        original_read=adapter.private_json
        def read(path):
            if Path(path).name=='0000.json':return {'payload':{'preimage':{'roles':original}}}
            return original_read(path)
        actor.observe_quiescence=Mock(return_value={name:0 for name in lifecycle.COUNTERS})
        with patch.object(adapter,'private_json',side_effect=read):
            self.assertEqual(actor.backup_role_archive(scope),archive.encode())
            original['archive']+='tamper'
            with self.assertRaisesRegex(RuntimeError,'original_role_archive_changed'):actor.backup_role_archive(scope)
            original['archive']=archive;original['original']['roles']['authenticator']['rolsuper']=True
            with self.assertRaisesRegex(RuntimeError,'original_role_archive_scope_changed'):actor.backup_role_archive(scope)
        actor.runtime.command.assert_not_called()

    def test_surviving_known_session_fails_drain_without_pid_termination_or_replay(self):
        actor, scope, preimage, _ = self.component(stage='fenced')
        actor.require_authority=Mock()
        session={'pid':701,'start':'synthetic-start','role':'authenticator','address':'10.1.0.2','database':'postgres'}
        preimage['supervisors']['sessions']=[session];actor._sessions=Mock(return_value=[session])
        with patch.object(adapter.time,'monotonic',side_effect=[0,11]):
            with self.assertRaisesRegex(RuntimeError,'session_drain_incomplete'):actor.drain_sessions(scope,preimage)
        actor.runtime.command.assert_not_called()
        self.assertFalse(hasattr(actor,'terminate_session'))
        actor._sessions.return_value=[dict(session,start='reused-pid-other-start')]
        with self.assertRaisesRegex(RuntimeError,'new_or_unknown_session'):actor.drain_sessions(scope,preimage)
        actor.runtime.command.assert_not_called()

    def test_known_session_scope_requires_exact_target_role_and_nonnull_actor_address(self):
        actor, _, _, _ = self.component()
        rows=actor._rows.return_value
        rows[0]['NetworkSettings']['Networks']={'fixture':{'NetworkID':'1'*64,'IPAddress':'10.1.0.2','EndpointID':'x'}}
        session={'pid':701,'start':'fixture','role':'authenticator','address':'10.1.0.2','database':'postgres'}
        self.assertTrue(actor._known_sessions([session]))
        for mutation in ({'role':'unregistered'},{'address':None},{'address':'10.2.0.7'}):
            self.assertFalse(actor._known_sessions([dict(session,**mutation)]))

    def test_effective_supervisor_enablement_fragment_and_dropins_are_remeasured(self):
        actor, _, _, _ = self.component()
        name=next(iter(actor.inventory['supervisors']))
        fragment=actor.root/'synthetic.service';fragment.write_bytes(b'[Service]\nExecStart=/bin/false\n')
        expected=actor.inventory['supervisors'][name]
        expected.update(fragment_sha256=hashlib.sha256(fragment.read_bytes()).hexdigest(),dropins_sha256=lifecycle.digest({}))
        fields={'FragmentPath':str(fragment),'DropInPaths':'','UnitFileState':'enabled','ActiveState':'inactive'}
        actor.runtime.command.side_effect=lambda *args,**kwargs:'\n'.join(k+'='+v for k,v in fields.items())
        with patch.object(adapter,'protected',lambda path,**kwargs:Path(path)):
            self.assertEqual(actor._unit(name)['UnitFileState'],'enabled')
            fields['UnitFileState']='disabled'
            with self.assertRaisesRegex(RuntimeError,'enablement_changed'):actor._unit(name)
            fields['UnitFileState']='enabled';fragment.write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError,'fragment_changed'):actor._unit(name)

    def test_persistent_barrier_requires_effective_condition_and_exact_preimage(self):
        actor, scope, preimage, _ = self.component(stage='fenced')
        del actor._verify_barrier
        actor.inventory['supervisors']={'madar-auto-deploy.service':next(iter(actor.inventory['supervisors'].values()))}
        name='madar-auto-deploy.service'; units=actor.root/'synthetic-systemd';units.mkdir()
        target=units/(name+'.d');target.mkdir();dropin=target/actor.dropin_name
        dropin.write_text('[Unit]\nConditionPathExists=!'+str(actor.barrier)+'\n')
        actor.barrier.write_text(json.dumps({'binding':scope,'preimage_sha256':lifecycle.digest(preimage)}))
        actor._unit=Mock(return_value={'DropInPaths':str(dropin)})
        condition={'type':'a(sbbsi)','data':[['ConditionPathExists',False,True,str(actor.barrier),0]]}
        def response(command,**kwargs):
            if 'GetUnit' in command:return json.dumps({'type':'o','data':['/org/freedesktop/systemd1/unit/synthetic_2eservice']})
            return json.dumps(condition)
        actor.runtime.command.side_effect=response
        with patch.object(adapter,'UNITS',units),patch.object(adapter,'protected',lambda path,**kwargs:Path(path)):
            actor._verify_barrier()
            condition['data']=[]
            with self.assertRaisesRegex(RuntimeError,'effective_boot_condition_missing'):actor._verify_barrier()
            condition['data']=[['ConditionPathExists',False,True,str(actor.barrier),0]]
            actor._unit.return_value={'DropInPaths':''}
            with self.assertRaisesRegex(RuntimeError,'effective_boot_barrier_missing'):actor._verify_barrier()
            actor._unit.return_value={'DropInPaths':str(dropin)}
            actor.barrier.write_text(json.dumps({'binding':scope,'preimage_sha256':'0'*64}))
            with self.assertRaisesRegex(RuntimeError,'persistent_barrier_changed'):actor._verify_barrier()


    def constructor_inputs(self):
        from test_schema150_admission import deletion_contract
        contract=deletion_contract();(data,scope),rows=fixture()
        contract['candidate'].update(source_sha=scope['source_sha'],controller_sha=scope['controller_sha'])
        contract['database'].update(container_id=data['containers']['native:db']['id'],
                                    image=data['containers']['native:db']['image'],system_identifier=scope['system_identifier'])
        contract['writer_inventory_sha256']=scope['inventory_sha256']
        scope['context_sha256']=adapter.contract_digest(contract)
        return contract,scope,data,rows

    def test_constructor_uses_actual_preparation_validator_and_exact_bindings(self):
        contract,scope,data,_=self.constructor_inputs()
        kwargs={'source_guard':Mock(),'lock_descriptors':(101,102),'acceptance_guard':Mock(),'activation_guard':Mock()}
        with patch.object(adapter,'private_json',return_value=data):
            actor=adapter.Schema150ProviderAdapter(contract,scope,Mock(),**kwargs)
            self.assertEqual(actor.binding,scope)
            for key,bad in (('context_sha256','0'*64),('source_sha','0'*40),('controller_sha','0'*40),
                            ('inventory_sha256','0'*64),('system_identifier','9')):
                with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'adapter_binding_invalid'):
                    adapter.Schema150ProviderAdapter(contract,dict(scope,**{key:bad}),Mock(),**kwargs)
            changed=copy.deepcopy(contract);changed['candidate']['compatible_max']=149
            with self.assertRaises(RuntimeError):adapter.Schema150ProviderAdapter(changed,scope,Mock(),**kwargs)
        contract['candidate']['source_sha']='f'*40
        self.assertEqual(actor.contract['candidate']['source_sha'],'b'*40)

    def test_constructor_cannot_accept_caller_callbacks_as_authority_or_live_exclusion_proof(self):
        contract,scope,data,_=self.constructor_inputs()
        kwargs={'source_guard':Mock(),'lock_descriptors':(101,102),'acceptance_guard':Mock(),'activation_guard':Mock()}
        for key,value in (('source_guard',True),('acceptance_guard',{'PASS':True}),('activation_guard','approved'),('lock_descriptors',[101,102])):
            bad=dict(kwargs,**{key:value})
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'adapter_binding_invalid'):
                adapter.Schema150ProviderAdapter(contract,scope,Mock(),**bad)
        data['exclusions']={'f'*64:{'image':'sha256:'+'e'*64,'spec_sha256':'8'*64,'proof_sha256':'7'*64}}
        data,scope=repin(data,scope);contract['writer_inventory_sha256']=scope['inventory_sha256']
        scope['context_sha256']=adapter.contract_digest(contract)
        with patch.object(adapter,'private_json',return_value=data),self.assertRaisesRegex(RuntimeError,'live_exclusion_proofs_required'):
            adapter.Schema150ProviderAdapter(contract,scope,Mock(),**kwargs)

    def test_initial_fence_exception_does_not_admit_missing_barrier_after_an_intent(self):
        actor,scope,_,journal=self.component()
        journal.append('effect_intent',{'step':'arm_boot_interlock'})
        for purpose in ('fence','fence_ingress','fence_roles','reconcile'):
            with self.subTest(purpose=purpose),self.assertRaisesRegex(RuntimeError,'persistent_barrier_missing'):
                actor.require_authority(scope,purpose=purpose)
        actor.runtime.command.assert_not_called()

    def test_initial_fence_exception_rejects_partially_fenced_actors_without_barrier(self):
        actor,scope,_,_=self.component()
        actor._rows.return_value=phase_rows(actor.inventory,actor._rows.return_value,'fenced')
        with self.assertRaisesRegex(RuntimeError,'actor_state_changed'):actor.require_authority(scope,purpose='fence')
        actor.runtime.command.assert_not_called()

    def test_old_worker_resurrection_blocks_every_active_boundary_guard(self):
        actor,scope,_,_=self.component(stage='activating',candidates=True)
        target=next(r for r in actor._rows.return_value if r['Name']=='/madar-blue-notification-worker')
        target['State']['Running']=True
        for purpose in ('observe_activation','resume_accepted_workers','restore_ingress','activate_after_grant','reconcile'):
            with self.subTest(purpose=purpose),self.assertRaisesRegex(RuntimeError,'actor_state_changed'):
                actor.require_authority(scope,purpose=purpose)
        actor.runtime.command.assert_not_called()

    def test_private_provider_boundary_allows_exact_private_providers_but_no_candidate_extension(self):
        actor,scope,_,_=self.component(stage='private')
        actor.require_authority(scope,purpose='prepare_private_activation')
        candidate,other_scope,_,_=self.component(stage='private',candidates=True)
        # The optional initial inventory is not an independently sealed future
        # candidate extension; private candidate activation remains deliberately
        # blocked rather than borrowing caller PASS evidence.
        with self.assertRaisesRegex(RuntimeError,'actor_state_changed'):
            candidate.require_authority(other_scope,purpose='prepare_private_activation')
        actor.runtime.command.assert_not_called();candidate.runtime.command.assert_not_called()

    def test_provider_resume_refuses_published_ports_even_with_injected_original_roles(self):
        actor,scope,preimage,_=self.component(stage='fenced')
        actor.require_authority=Mock();actor._roles=Mock(return_value={'fixture':'original'})
        actor._expected_roles=Mock(return_value={'fixture':'original'})
        target=next(r for r in actor._rows.return_value if r['Name']=='/supabase-auth')
        target['HostConfig']['PortBindings']={'9999/tcp':[{'HostIp':'0.0.0.0','HostPort':'9999'}]}
        with self.assertRaisesRegex(RuntimeError,'private_port_exposed'):actor.resume_providers_private(scope,preimage)
        actor.runtime.command.assert_not_called()

    def test_restore_and_worker_start_require_existing_target_authority_without_issuing(self):
        actor,scope,preimage,_=self.component(stage='activating',candidates=True)
        actor.require_authority=Mock();actor.activation_guard.return_value={'target_write_authority':False}
        for method in (actor.resume_accepted_workers,actor.restore_ingress):
            with self.assertRaisesRegex(RuntimeError,'target_authority_required'):method(scope,preimage)
        actor.runtime.command.assert_not_called()
        self.assertFalse(hasattr(actor,'issue_authority'))

    def test_private_acceptance_requires_exact_database_protocols_and_real_acceptance_delegate(self):
        actor,scope,preimage,_=self.component(stage='fenced')
        actor.require_authority=Mock();actor._sql=Mock(return_value='[2,2,2]')
        actor.acceptance_guard.return_value=False
        with self.assertRaisesRegex(RuntimeError,'native_acceptance_failed'):actor.verify_native_acceptance(scope,preimage)
        actor.acceptance_guard.return_value=True
        for protocols in ('[2,2,1]','[2,1,2]','[1,2,2]','[2,2,true]'):
            actor._sql.return_value=protocols
            with self.subTest(protocols=protocols),self.assertRaises(RuntimeError):actor.verify_native_acceptance(scope,preimage)
        actor.runtime.command.assert_not_called()

    def test_actual_container_discovery_is_full_bounded_and_requires_all_rows(self):
        actor,_,_,_=self.component();del actor._rows
        for listing in ('','f'*63,' '.join(f'{i:064x}' for i in range(1025))):
            actor.runtime.command.side_effect=None;actor.runtime.command.return_value=listing
            with self.subTest(length=len(listing)),self.assertRaisesRegex(RuntimeError,'inventory_unbounded'):actor._rows()
        actor.runtime.command.side_effect=['1'*64,json.dumps([{'Id':'1'*64,'fixture':'unfiltered'}])]
        self.assertEqual(actor._rows(),[{'Id':'1'*64,'fixture':'unfiltered'}])
        self.assertEqual(actor.runtime.command.call_args_list[-2].args[0],['docker','ps','-aq','--no-trunc'])
        self.assertEqual(actor.runtime.command.call_args_list[-1].args[0],['docker','inspect','1'*64])


    def test_effective_condition_must_match_exact_negative_barrier_not_substring(self):
        actor,scope,preimage,_=self.component(stage='fenced');del actor._verify_barrier
        actor.inventory['supervisors']={'madar-auto-deploy.service':next(iter(actor.inventory['supervisors'].values()))}
        name='madar-auto-deploy.service';units=actor.root/'synthetic-systemd';units.mkdir()
        target=units/(name+'.d');target.mkdir();dropin=target/actor.dropin_name
        dropin.write_text('[Unit]\nConditionPathExists=!'+str(actor.barrier)+'\n')
        actor.barrier.write_text(json.dumps({'binding':scope,'preimage_sha256':lifecycle.digest(preimage)}))
        actor._unit=Mock(return_value={'DropInPaths':str(dropin)})
        condition={'type':'a(sbbsi)','data':[]}
        def response(command,**kwargs):
            if 'GetUnit' in command:return json.dumps({'type':'o','data':['/org/freedesktop/systemd1/unit/synthetic_2eservice']})
            return json.dumps(condition)
        actor.runtime.command.side_effect=response
        with patch.object(adapter,'UNITS',units),patch.object(adapter,'protected',lambda path,**kwargs:Path(path)):
            for wrong in ([['ConditionPathExists',False,True,str(actor.barrier)+'-other',0]],
                          [['ConditionPathExists',False,False,str(actor.barrier),0]],
                          [['ConditionPathExists',True,True,str(actor.barrier),0]],
                          [['ConditionPathExists',False,True,str(actor.barrier)+'-other',0],
                           ['ConditionPathExists',False,True,'/unrelated',0]],
                          [['OtherCondition',False,True,str(actor.barrier),0]],
                          [['ConditionPathExists',0,1,str(actor.barrier),0]]):
                condition['data']=wrong
                with self.subTest(condition=wrong),self.assertRaisesRegex(RuntimeError,'effective_boot_condition_missing'):
                    actor._verify_barrier()


    def test_real_journal_flock_serializes_two_model_actors_before_adapter_effects(self):
        actor,scope,_,journal=self.component()
        first=lifecycle.ProviderMaintenance150(scope,journal,actor)
        second=lifecycle.ProviderMaintenance150(scope,journal,actor)
        with first._locked():
            with self.assertRaisesRegex(RuntimeError,'actor_already_active'):second.fence()
        actor.runtime.command.assert_not_called();actor.source_guard.assert_not_called()

    def test_lost_clear_acknowledgement_can_be_observed_without_recreating_barrier(self):
        actor,scope,_,journal=self.component(stage='private')
        for step in lifecycle.ACTIVATE_STEPS:
            journal.append('effect_intent',{'step':step})
            if step!='clear_boot_interlock':journal.append('effect_complete',{'step':step})
        actor._rows.return_value=phase_rows(actor.inventory,actor._rows.return_value,'active')
        actor.barrier.unlink()
        # Observe already committed clear; never replay creation or invoke an
        # issuer. No blanket missing-barrier exception exists for earlier steps.
        self.assertIs(actor.verify_effect('clear_boot_interlock',scope,{}),True)
        actor._verify_barrier.assert_not_called();actor.runtime.command.assert_not_called()


    def native_database_rows(self):
        (_, _),rows=fixture()
        rows=[r for r in rows if r['Name'] in ('/supabase-db','/supabase-auth','/supabase-rest','/supabase-storage')]
        database=next(r for r in rows if r['Name']=='/supabase-db')
        for index,r in enumerate(rows):
            endpoint=r['NetworkSettings']['Networks'][inventory.DEFAULT_NETWORK]
            endpoint.update(IPAddress='10.1.0.'+str(index+2),Aliases=['db','supabase-db'] if r is database else [r['Name'].lstrip('/')])
            mapping={'/supabase-rest':('PGRST_DB_URI','authenticator'),'/supabase-auth':('GOTRUE_DB_DATABASE_URL','supabase_auth_admin'),
                     '/supabase-storage':('DATABASE_URL','supabase_storage_admin')}
            if r['Name'] in mapping:
                key,role=mapping[r['Name']]
                r['Config']['Env']=[key+'=postgresql://'+role+':synthetic-fixture-password@db:5432/postgres?sslmode=disable']
        return rows,database['Id']

    def test_provider_database_uri_binds_exact_cluster_network_alias_role_and_database(self):
        rows,identifier=self.native_database_rows()
        self.assertIs(adapter.require_provider_database_bindings(rows,identifier),True)
        for value in ('postgresql://authenticator:synthetic@other-db:5432/postgres',
                      'postgresql://postgres:synthetic@db:5432/postgres',
                      'postgresql://authenticator:synthetic@db:6432/postgres',
                      'postgresql://authenticator:synthetic@db:5432/foreign-db',
                      'postgresql://authenticator:synthetic@db:5432/postgres?host=foreign-db',
                      'postgresql://authenticator:synthetic@db:5432/postgres?options=search_path%3Devil',
                      'postgresql://authenticator:synthetic@db:5432/postgres?sslmode=disable&sslmode=require',
                      'postgresql://authenticator:synthetic@db:5432/postgres#fragment',
                      'https://authenticator:synthetic@db:5432/postgres'):
            bad=copy.deepcopy(rows);rest=next(r for r in bad if r['Name']=='/supabase-rest')
            rest['Config']['Env']=['PGRST_DB_URI='+value]
            with self.subTest(uri_kind=value.split(':',1)[0]),self.assertRaisesRegex(RuntimeError,'database_uri_scope_invalid') as failure:
                adapter.require_provider_database_bindings(bad,identifier)
            self.assertNotIn('synthetic',str(failure.exception))

    def test_provider_database_alias_collision_dns_override_mount_and_network_substitution_refuse(self):
        rows,identifier=self.native_database_rows()
        for kind in ('alias','extra-host','dns','dns-search','hosts-mount','network','missing-database'):
            bad=copy.deepcopy(rows);rest=next(r for r in bad if r['Name']=='/supabase-rest')
            if kind=='alias':
                rest['NetworkSettings']['Networks'][inventory.DEFAULT_NETWORK]['Aliases'].append('db')
            elif kind=='extra-host':rest['HostConfig']['ExtraHosts']=['db:10.9.9.9']
            elif kind=='dns':rest['HostConfig']['Dns']=['10.9.9.9']
            elif kind=='dns-search':rest['HostConfig']['DnsSearch']=['external.example']
            elif kind=='hosts-mount':rest['Mounts']=[{'Destination':'/etc/hosts'}]
            elif kind=='network':rest['NetworkSettings']['Networks'][inventory.DEFAULT_NETWORK]['NetworkID']='9'*64
            else:bad=[r for r in bad if r['Id']!=identifier]
            with self.subTest(kind=kind),self.assertRaisesRegex(RuntimeError,'database_(uri_scope_invalid|binding_missing)'):
                adapter.require_provider_database_bindings(bad,identifier)

    def test_effective_bus_unit_and_conditions_malformed_types_fail_closed(self):
        actor,scope,preimage,_=self.component(stage='fenced');del actor._verify_barrier
        actor.inventory['supervisors']={'madar-auto-deploy.service':next(iter(actor.inventory['supervisors'].values()))}
        name='madar-auto-deploy.service';units=actor.root/'synthetic-systemd';units.mkdir()
        directory=units/(name+'.d');directory.mkdir();dropin=directory/actor.dropin_name
        dropin.write_text('[Unit]\nConditionPathExists=!'+str(actor.barrier)+'\n')
        actor.barrier.write_text(json.dumps({'binding':scope,'preimage_sha256':lifecycle.digest(preimage)}))
        actor._unit=Mock(return_value={'DropInPaths':str(dropin)})
        valid_unit={'type':'o','data':['/org/freedesktop/systemd1/unit/synthetic_2eservice']}
        valid_conditions={'type':'a(sbbsi)','data':[['ConditionPathExists',False,True,str(actor.barrier),0]]}
        state={'unit':valid_unit,'conditions':valid_conditions}
        actor.runtime.command.side_effect=lambda command,**kwargs:json.dumps(state['unit'] if 'GetUnit' in command else state['conditions'])
        with patch.object(adapter,'UNITS',units),patch.object(adapter,'protected',lambda path,**kwargs:Path(path)):
            actor._verify_barrier()
            for bad in (None,[],{'type':'s','data':valid_unit['data']},{'type':'o','data':[]},
                        {'type':'o','data':[valid_unit['data'][0],valid_unit['data'][0]]},
                        {'type':'o','data':['/org/freedesktop/systemd1/unit/../manager']},
                        {'type':'o','data':[True]}):
                state['unit']=bad
                with self.subTest(unit=bad),self.assertRaisesRegex(RuntimeError,'effective_boot_unit_invalid'):actor._verify_barrier()
            state['unit']=valid_unit
            for bad in (None,[],{'type':'a(sbbsi)','data':True},{'type':'invalid','data':valid_conditions['data']},
                        {'type':'a(sbbsi)','data':[['ConditionPathExists',False,True,str(actor.barrier),True]]},
                        {'type':'a(sbbsi)','data':[['ConditionPathExists',False,True,str(actor.barrier)]]}):
                state['conditions']=bad
                with self.subTest(conditions=bad),self.assertRaisesRegex(RuntimeError,'effective_boot_condition_missing'):actor._verify_barrier()


    def object_component(self):
        from deployment.lib.schema150_object_inventory import measure_roots
        actor,scope,preimage,journal=self.component(stage='fenced')
        parent=actor.root/'owned-objects';parent.mkdir()
        for logical,root in actor.inventory['object_roots'].items():
            path=parent/logical;path.mkdir();root['source']=str(path)
        (parent/'avatars'/'synthetic.bin').write_bytes(b'synthetic-content')
        preimage['objects']=measure_roots(actor.inventory['object_roots'])
        actor._database_identity.return_value=146
        return actor,scope,preimage,journal,parent

    def test_actual_object_preimage_capture_is_separate_fenced_and_never_overwritten(self):
        actor,scope,preimage,_,_=self.object_component()
        first=actor._object_preservation(scope,preimage,capture=True)
        path=actor.root/'provider-object-preservation.json';before=path.read_bytes()
        self.assertEqual(first['phase'],'fenced');self.assertIsNone(first['roots']['database']['content'])
        self.assertEqual(json.loads(before),{'binding':scope,'measurement':first})
        actor._database_identity.return_value=150
        self.assertEqual(actor._object_preservation(scope,preimage),first)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(path.stat().st_mode&0o777,0o600)
        actor.runtime.command.assert_not_called()

    def test_missing_object_preimage_cannot_be_recaptured_after_sql_or_prior_quiescence(self):
        actor,scope,preimage,journal,_=self.object_component()
        for schema in (147,148,149,150):
            actor._database_identity.return_value=schema
            with self.subTest(schema=schema),self.assertRaisesRegex(RuntimeError,'object_preimage_required'):
                actor._object_preservation(scope,preimage,capture=True)
        actor._database_identity.return_value=146
        journal.append('quiescence',{'schema':146})
        with self.assertRaisesRegex(RuntimeError,'object_preimage_required'):
            actor._object_preservation(scope,preimage,capture=True)
        self.assertFalse((actor.root/'provider-object-preservation.json').exists())
        actor.runtime.command.assert_not_called()

    def test_wrong_object_binding_and_content_drift_never_relabel_or_refresh_capture(self):
        actor,scope,preimage,_,parent=self.object_component()
        actor._object_preservation(scope,preimage,capture=True)
        path=actor.root/'provider-object-preservation.json';original=path.read_bytes()
        value=json.loads(original);value['binding']['context_sha256']='0'*64;path.write_text(json.dumps(value))
        with self.assertRaisesRegex(RuntimeError,'object_preimage_changed'):
            actor._object_preservation(scope,preimage)
        path.write_bytes(original)
        (parent/'avatars'/'synthetic.bin').write_bytes(b'unexpected-content')
        with self.assertRaisesRegex(RuntimeError,'preservation_changed'):
            actor._object_preservation(scope,preimage)
        self.assertEqual(path.read_bytes(),original)
        actor.runtime.command.assert_not_called()

    def test_identity_only_checkpoint_is_not_accepted_as_fenced_object_history(self):
        actor,scope,preimage,_,_=self.object_component()
        path=actor.root/'provider-object-preservation.json'
        path.write_text(json.dumps({'binding':scope,'measurement':preimage['objects']}))
        actor._database_identity.return_value=150
        with self.assertRaisesRegex(RuntimeError,'object_preimage_changed'):
            actor._object_preservation(scope,preimage)
        self.assertEqual(json.loads(path.read_bytes())['measurement']['phase'],'identity')
        actor.runtime.command.assert_not_called()


if __name__ == '__main__': unittest.main()

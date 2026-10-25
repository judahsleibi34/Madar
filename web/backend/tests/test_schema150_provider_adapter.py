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
import subprocess
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


@unittest.skipUnless(os.getenv('MADAR_NATIVE_CANDIDATE_REDIS_ID'), 'owned native Redis fixture required')
class NativeCandidateRedisTests(unittest.TestCase):
    """Native Docker identity; other actors/credentials remain explicit models.

    The harness creates/removes its own networkless, never-started Redis. This
    test only inspects it; it never selects a runtime by production service name.
    It is not protected controller, issuer or application acceptance.
    """
    def test_native_created_redis_without_madar_label_remains_exactly_bound(self):
        from deployment.lib.completed_normal_resources import measured_spec
        identifier=os.environ['MADAR_NATIVE_CANDIDATE_REDIS_ID']
        self.assertRegex(identifier,r'^[0-9a-f]{64}$')
        rows=json.loads(subprocess.check_output(['docker','inspect',identifier],text=True))
        self.assertEqual(len(rows),1)
        actual=rows[0]
        self.assertEqual(actual['Id'],identifier)
        self.assertRegex(actual['Name'],r'^/madar-schema150-binding-[0-9a-f]+$')
        self.assertEqual(actual['Config']['Labels'].get('madar.test.scope'),'schema150-candidate-binding')
        self.assertEqual(actual['HostConfig']['NetworkMode'],'none')
        self.assertEqual(actual['State']['Status'],'created')
        self.assertNotIn('org.opencontainers.image.revision',actual['Config']['Labels'])
        actor,_,_,_=ConcreteAdapterTests.component(self,stage='fenced',candidates=True)
        # Docker has not allocated endpoints for a CREATED container. Preserve
        # the measured declared network object's identity, as the real model
        # validator does, instead of treating its empty endpoint ID as a hash.
        declared=json.loads(subprocess.check_output(['docker','network','inspect','none'],text=True))
        self.assertEqual(len(declared),1)
        self.assertEqual(set(actual['NetworkSettings']['Networks']),{'none'})
        old=actor.inventory['containers']['candidate:redis']
        observed=actor._rows.return_value
        observed[:]=[actual if r['Id']==old['id'] else r for r in observed]
        record=dict(old,name=actual['Name'].lstrip('/'),id=identifier,image=actual['Image'],
            spec_sha256=measured_spec(actual),mounts=inventory._actual_mounts(actual),
            networks={'none':declared[0]['Id']})
        actor.inventory['containers']['candidate:redis']=record
        actor.contract['candidate']['redis_image']=actual['Image']
        stage=json.loads((actor.root/'candidate-staged-runtime.json').read_text())
        stage['runtimes']['redis']={**{k:record[k] for k in ('id','image','spec_sha256','networks')},
            'network_aliases':{k:v.get('Aliases') or [] for k,v in actual['NetworkSettings']['Networks'].items()}}
        stage['preparation_mode']='created-fenced'
        for role,sealed in stage['runtimes'].items():sealed['name']=actor.inventory['containers']['candidate:'+role]['name']
        (actor.root/'candidate-staged-runtime.json').write_text(json.dumps(stage))
        for key in list(actor.inventory['containers']):
            if key.startswith('candidate:'):del actor.inventory['containers'][key]
        actor.inventory,actor.binding=repin(actor.inventory,actor.binding)
        actor.original_inventory=copy.deepcopy(actor.inventory)
        with patch('deployment.lib.completed_normal_admission.credential_witness',return_value=stage):
            actor.verify_candidate_stage()
            actor._attest('fenced')
            actual['Image']='sha256:'+'0'*64
            with self.assertRaisesRegex(RuntimeError,'candidate_identity_changed'):
                actor.verify_candidate_stage()
        actor.runtime.command.assert_not_called()


class ConcreteAdapterTests(unittest.TestCase):
    def private_handoff_component(self, *, normal=False, target=160):
        """Real guard/journal/inventory; native providers are explicit models."""
        actor,scope,preimage,journal=self.component(stage='private',candidates=True,target=target)
        actor.contract['candidate']['slot']='green'
        stage=json.loads((actor.root/'candidate-staged-runtime.json').read_text())
        stage['preparation_mode']='created-fenced'
        for role,sealed in stage['runtimes'].items():sealed['name']=actor.inventory['containers']['candidate:'+role]['name']
        (actor.root/'candidate-staged-runtime.json').write_text(json.dumps(stage))
        patcher=patch('deployment.lib.completed_normal_admission.credential_witness',return_value=stage)
        patcher.start();self.addCleanup(patcher.stop)
        actor._roles=Mock(return_value={'original':'synthetic'})
        actor._expected_roles=Mock(return_value={'original':'synthetic'})
        actor._sessions=Mock(return_value=[]);actor._known_sessions=Mock(return_value=True)
        actor._supervisors_stopped=Mock(return_value=True);actor._object_preservation=Mock()
        actor._sql=Mock(side_effect=lambda sql: '[2,2,2]' if 'json_build_array' in sql else '0')
        grant={'mode':'NORMAL' if normal else 'READ_ONLY','schema':target if normal else 146}
        patcher=patch('deployment.lib.completed_normal_admission.require_candidate_authority',return_value=grant)
        patcher.start();self.addCleanup(patcher.stop)
        actor.activation_guard=Mock(return_value={'binding_sha256':lifecycle.digest(scope),'schema':target,
            'delivery_protocol':2,'outbox_protocol':2,'deletion_protocol':2,
            'target_write_authority':normal,'write_authority_sha256':lifecycle.digest(grant) if normal else None,
            **{k:True for k in lifecycle.PRE_GRANT_GATES}})
        version={'release_sha':scope['source_sha'],'release_slot':'green',
            'schema_compatible_min':146,'schema_compatible_max':target,'schema_excluded_versions':[]}
        recovery={'restricted':not normal,'business_writes_enabled':normal}
        actor.runtime.json_http.side_effect=lambda url:version if url.endswith('/health/version') else recovery
        components={key:'ok' for key in ('database','auth','schema','storage','redis','environment',
            'admin_mfa_policy','parser_isolation','calendar_configuration')}
        components['notification_worker']='unavailable'
        actor.runtime.fetch.return_value=(503,json.dumps({'ready':False,'components':components}).encode())
        return actor,scope,stage,preimage,journal,grant,version,components

    def test_private_handoff_observes_application_without_starting_or_claiming_workers(self):
        for target,normal in ((150,False),(150,True),(160,False),(160,True)):
            with self.subTest(target=target,normal=normal):
                actor,scope,stage,_,journal,grant,_,_=self.private_handoff_component(normal=normal,target=target)
                result=actor.verify_private_handoff(normal=normal)
                self.assertEqual(result['mode'],grant['mode'])
                self.assertEqual(result['candidate_stage_sha256'],lifecycle.digest(stage))
                self.assertEqual(result['provider_journal_sha256'],lifecycle.digest(journal.read()))
                self.assertFalse(result['workers_started']);self.assertFalse(result['ingress_restored'])
                self.assertEqual(actor.runtime.denied.call_count,0 if normal else 2)
                actor.runtime.command.assert_not_called()
                self.assertFalse((actor.root/'normal-publication.json').exists())

    def test_private_handoff_rejects_pending_journal_missing_acceptance_and_started_consumer(self):
        for fault in ('pending','missing_private_acceptance','started_worker','role','session','protocol','object'):
            with self.subTest(fault=fault):
                actor,_,stage,_,journal,_,_,_=self.private_handoff_component()
                if fault=='pending':journal.append('effect_intent',{'step':'resume_accepted_workers'})
                elif fault=='missing_private_acceptance':(journal.root/'0019.json').unlink()
                elif fault=='started_worker':
                    next(r for r in actor._rows.return_value if r['Id']==stage['runtimes']['notification-worker']['id'])['State']['Running']=True
                elif fault=='role':actor._roles.return_value={'wrong':'roles'}
                elif fault=='session':actor._known_sessions.return_value=False
                elif fault=='protocol':actor._sql.side_effect=lambda sql:'[2,1,2]' if 'json_build_array' in sql else '0'
                else:actor._object_preservation.side_effect=RuntimeError('synthetic_object_changed')
                with self.assertRaises((RuntimeError,FileNotFoundError)):actor.verify_private_handoff(normal=False)
                actor.runtime.command.assert_not_called()

    def test_private_handoff_rejects_changed_source_missing_core_and_unready_parser(self):
        for fault in ('source','missing_core','parser','calendar','premature_normal'):
            with self.subTest(fault=fault):
                actor,_,_,_,_,_,version,components=self.private_handoff_component()
                if fault=='source':version['release_sha']='0'*40
                elif fault=='missing_core':del components['auth']
                elif fault=='parser':components['parser_isolation']='unavailable'
                elif fault=='calendar':components['calendar_configuration']='unavailable'
                else:actor.activation_guard.return_value['target_write_authority']=True
                actor.runtime.fetch.return_value=(503,json.dumps({'components':components}).encode())
                with self.assertRaises(RuntimeError):actor.verify_private_handoff(normal=False)
                actor.runtime.command.assert_not_called()

    def component(self, *, stage='prepared', candidates=False, target=150):
        """Real adapter methods, synthetic transport and explicit guard injection."""
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        root = Path(temporary.name); root.chmod(0o700)
        journal_root = root/'provider-journal'; journal_root.mkdir(mode=0o700)
        stack = ExitStack(); self.addCleanup(stack.close)
        stack.enter_context(patch.object(retained, 'protected', lambda path, **kwargs: Path(path)))
        stack.enter_context(patch.object(retained, 'require_root_directory', lambda path: None))
        (data, scope), rows = fixture(candidates=candidates)
        if target==160:
            from test_schema160_private_parser import canonical_parser
            data,scope=canonical_parser(data,scope,rows)
        actor = adapter.Schema150ProviderAdapter.__new__(adapter.Schema150ProviderAdapter)
        actor.binding, actor.inventory, actor.root = scope, data, root
        actor.original_inventory=data
        actor.contract = {'operation': scope['operation'], 'version': 8 if target==160 else 7, 'rehearsal_sha256': '8'*64, 'database': {'container_id': data['containers']['native:db']['id'],
                          'image': data['containers']['native:db']['image']}}
        actor.contract['candidate']={'images':{'backend':'sha256:'+'e'*64,'frontend':'sha256:'+'e'*64}}
        actor.contract['candidate']['redis_image']='sha256:'+'e'*64
        actor.barrier = root/'provider-barrier.json'
        actor.dropin_name = '99zzzzzz-schema150-'+scope['context_sha256'][:12]+'.conf'
        actor.runtime = Mock(); actor.runtime.command.side_effect = AssertionError('synthetic transport not configured')
        actor.source_guard = Mock()
        actor.lock_descriptors = (101, 102)
        actor.acceptance_guard = Mock(return_value=True)
        actor.activation_guard = Mock(return_value={'target_write_authority': True})
        actor._database_identity = Mock(return_value=target)
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
        if candidates:
            candidate_stage={'operation':scope['operation'],'context_sha256':scope['context_sha256'],
                'source_sha':scope['source_sha'],'images':actor.contract['candidate']['images'],
                'runtimes':{role:{**{k:data['containers']['candidate:'+role][k] for k in
                    ('id','image','spec_sha256','networks')},'network_aliases':{
                        k:v.get('Aliases') or [] for k,v in next(r for r in observed
                            if r['Id']==data['containers']['candidate:'+role]['id'])['NetworkSettings']['Networks'].items()}}
                    for role in inventory.APP_ROLES},
                'networks':{},'worker_generation':'f'*64,'origin_workers':[]}
            (root/'candidate-staged-runtime.json').write_text(json.dumps(candidate_stage))
            stack.enter_context(patch('deployment.lib.completed_normal_admission.credential_witness',return_value=copy.deepcopy(candidate_stage)))
        return actor, scope, preimage, journal

    def candidate_extension(self, *, phase='fenced'):
        actor,scope,preimage,journal=self.component(stage='fenced',candidates=True)
        stage_path=actor.root/'candidate-staged-runtime.json'
        stage=json.loads(stage_path.read_text())
        stage['preparation_mode']='created-fenced'
        for role,sealed in stage['runtimes'].items():sealed['name']=actor.inventory['containers']['candidate:'+role]['name']
        stage_path.write_text(json.dumps(stage))
        original=copy.deepcopy(actor.inventory)
        full=copy.deepcopy(original)
        for key in list(original['containers']):
            if key.startswith('candidate:'):del original['containers'][key]
        original,scope=repin(original,scope)
        actor.inventory.clear();actor.inventory.update(original)
        actor.original_inventory=copy.deepcopy(original)
        actor.binding=scope
        actor._rows.return_value=phase_rows(full,actor._rows.return_value,phase)
        witness=patch('deployment.lib.completed_normal_admission.credential_witness',return_value=copy.deepcopy(stage))
        witness.start();self.addCleanup(witness.stop)
        return actor,scope,stage,preimage,journal

    def test_candidate_extension_keeps_original_admission_hash_and_covers_every_actor(self):
        actor,scope,stage,_,_=self.candidate_extension()
        original=copy.deepcopy(actor.original_inventory)
        actor.require_authority(scope,purpose='observe_quiescence')
        self.assertEqual(actor.original_inventory,original)
        self.assertEqual(inventory.inventory_digest(original),scope['inventory_sha256'])
        self.assertEqual(len(actor.inventory['containers']),len(original['containers'])+8)
        self.assertEqual(actor.verify_candidate_stage(),stage)
        actor._attest('fenced')
        self.assertEqual(actor._row(actor.inventory['containers']['candidate:backend']['name'])['Id'],stage['runtimes']['backend']['id'])

    def test_candidate_extension_survives_adapter_restart_using_issuer_bound_stage(self):
        actor,scope,stage,_,_=self.candidate_extension(phase='private')
        actor._attest('private-boundary')
        identities=copy.deepcopy(actor.inventory['containers'])
        actor.inventory=copy.deepcopy(actor.original_inventory)
        actor._attest('private-boundary')
        self.assertEqual(actor.inventory['containers'],identities)
        actor.verify_candidate_stage()
        actor.runtime.command.assert_not_called()

    def test_candidate_extension_rejects_missing_stale_or_unmarked_stage(self):
        for fault in ('missing','stale','unmarked'):
            with self.subTest(fault=fault):
                actor,_,stage,_,_=self.candidate_extension()
                if fault=='missing':(actor.root/'candidate-staged-runtime.json').unlink()
                elif fault=='stale':
                    stage['source_sha']='0'*40
                    (actor.root/'candidate-staged-runtime.json').write_text(json.dumps(stage))
                else:
                    del stage['preparation_mode']
                    (actor.root/'candidate-staged-runtime.json').write_text(json.dumps(stage))
                    with patch('deployment.lib.completed_normal_admission.credential_witness',return_value=stage):
                        with self.assertRaises(RuntimeError):actor._attest('fenced')
                    continue
                with self.assertRaises(RuntimeError):actor._attest('fenced')
                actor.runtime.command.assert_not_called()

    def test_candidate_extension_cannot_adopt_unknown_partial_or_premature_actors(self):
        for fault in ('extra','partial','running_worker','mount','network','duplicate_id','rename','prepared_boundary'):
            with self.subTest(fault=fault):
                actor,_,stage,_,_=self.candidate_extension()
                candidate=next(r for r in actor._rows.return_value if r['Id']==stage['runtimes']['notification-worker']['id'])
                if fault=='extra':actor._rows.return_value.append(row('f'*64,'madar-unknown-late-worker'))
                elif fault=='partial':actor._rows.return_value.remove(candidate)
                elif fault=='running_worker':candidate['State']['Running']=True
                elif fault=='mount':candidate['Mounts'].append({'Type':'bind','Source':'/unapproved','Destination':'/unapproved','RW':True})
                elif fault=='network':next(iter(candidate['NetworkSettings']['Networks'].values()))['NetworkID']='f'*64
                elif fault=='duplicate_id':actor._rows.return_value.append(copy.deepcopy(candidate))
                elif fault=='rename':candidate['Name']='/madar-unapproved-renamed-worker'
                with self.assertRaises(RuntimeError):actor._attest('prepared' if fault=='prepared_boundary' else 'fenced')
                self.assertEqual(actor.inventory,actor.original_inventory)
                actor.runtime.command.assert_not_called()

    def test_candidate_name_cannot_change_after_restart_from_a_valid_stage(self):
        actor,_,stage,_,_=self.candidate_extension(phase='private')
        actor._attest('private-boundary')
        actor.inventory=copy.deepcopy(actor.original_inventory)
        candidate=next(r for r in actor._rows.return_value if r['Id']==stage['runtimes']['backend']['id'])
        candidate['Name']='/madar-unapproved-after-restart'
        with self.assertRaises(RuntimeError):actor._attest('private-boundary')
        actor.runtime.command.assert_not_called()

    def test_stage_inventory_agreement_cannot_substitute_an_unapproved_role_image(self):
        from deployment.lib.completed_normal_resources import measured_spec
        for role in inventory.APP_ROLES:
            with self.subTest(role=role):
                actor,_,_,_=self.component(stage='fenced',candidates=True)
                stage=json.loads((actor.root/'candidate-staged-runtime.json').read_text())
                record=actor.inventory['containers']['candidate:'+role]
                actual=next(r for r in actor._rows.return_value if r['Id']==record['id'])
                actual['Image']='sha256:'+'9'*64
                record.update(image=actual['Image'],spec_sha256=measured_spec(actual))
                stage['runtimes'][role].update(image=record['image'],spec_sha256=record['spec_sha256'])
                (actor.root/'candidate-staged-runtime.json').write_text(json.dumps(stage))
                with patch('deployment.lib.completed_normal_admission.credential_witness',return_value=stage):
                    with self.assertRaisesRegex(RuntimeError,'candidate_identity_changed'):
                        actor.verify_candidate_stage()
                actor.runtime.command.assert_not_called()

    def test_stage_does_not_swap_approved_backend_frontend_or_redis_images(self):
        from deployment.lib.completed_normal_resources import measured_spec
        for role in inventory.APP_ROLES:
            with self.subTest(role=role):
                actor,_,_,_=self.component(stage='fenced',candidates=True)
                approved={'backend':'sha256:'+'1'*64,'frontend':'sha256:'+'2'*64}
                actor.contract['candidate']['images']=approved
                actor.contract['candidate']['redis_image']='sha256:'+'3'*64
                stage=json.loads((actor.root/'candidate-staged-runtime.json').read_text())
                stage['images']=approved
                for kind,sealed in stage['runtimes'].items():
                    record=actor.inventory['containers']['candidate:'+kind]
                    actual=next(r for r in actor._rows.return_value if r['Id']==record['id'])
                    actual['Image']=actor.contract['candidate']['redis_image'] if kind=='redis' else approved['frontend' if kind=='frontend' else 'backend']
                    if kind==role:
                        actual['Image']=approved['backend' if kind in ('frontend','redis') else 'frontend']
                    record.update(image=actual['Image'],spec_sha256=measured_spec(actual))
                    sealed.update(image=record['image'],spec_sha256=record['spec_sha256'])
                (actor.root/'candidate-staged-runtime.json').write_text(json.dumps(stage))
                with patch('deployment.lib.completed_normal_admission.credential_witness',return_value=stage):
                    with self.assertRaisesRegex(RuntimeError,'candidate_identity_changed'):
                        actor.verify_candidate_stage()
                actor.runtime.command.assert_not_called()

    def test_internal_sql_pins_catalog_before_role_or_quiescence_observation(self):
        actor,_,_,_=self.component()
        actor.runtime.command.side_effect=None; actor.runtime.command.return_value='synthetic'
        actor._sql('SELECT 1;')
        body=actor.runtime.command.call_args.kwargs['input']
        self.assertTrue(body.startswith('SET search_path=pg_catalog,public,extensions;'))
        self.assertLess(body.index('SET search_path'),body.index('SELECT 1;'))

    def test_existing_executor_cursor_reaches_the_fenced_lifecycle_guard(self):
        from deployment.lib.migration_executor import Migration
        from deployment.lib.schema150_release import SQL_SHA256
        actor,scope,_,journal=self.component(stage='fenced')
        cursor=Mock();cursor.fetchone.return_value=(True,)
        observed={'system_identifier':scope['system_identifier'],'schema':149,
                  **{name:0 for name in lifecycle.COUNTERS},**{name:True for name in lifecycle.FENCES}}
        actor.observe_quiescence=Mock(return_value=observed)
        migration=Migration(150,Path('/unused-source-path'),SQL_SHA256[150],149,150,'coordinated')
        result=actor.migration_guard(cursor,migration)
        self.assertEqual(result,observed)
        actor.observe_quiescence.assert_called_once_with(scope,cursor=cursor)
        self.assertEqual(journal.read()[-1]['event'],'quiescence')
        self.assertIn('pg_catalog.pg_locks',cursor.execute.call_args.args[0])

    def test_migration_hook_refuses_wrong_contract_or_unowned_database_lock(self):
        from deployment.lib.migration_executor import Migration
        from deployment.lib.schema150_release import SQL_SHA256
        actor,_,_,journal=self.component(stage='fenced')
        cursor=Mock();cursor.fetchone.return_value=(False,)
        before=journal.read()
        valid=Migration(150,Path('/unused-source-path'),SQL_SHA256[150],149,150,'coordinated')
        with self.assertRaisesRegex(RuntimeError,'migration_lock_required'):actor.migration_guard(cursor,valid)
        cursor.reset_mock()
        for wrong in (object(),Migration(150,valid.path,'0'*64,149,150,'coordinated'),
                      Migration(151,valid.path,'0'*64,150,151,'coordinated'),
                      Migration(150,valid.path,valid.sha256,148,150,'coordinated')):
            with self.subTest(wrong=wrong),self.assertRaisesRegex(RuntimeError,'migration_contract_changed'):
                actor.migration_guard(cursor,wrong)
        cursor.execute.assert_not_called()
        self.assertEqual(journal.read(),before)

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

    def test_private_boundary_measures_background_writers_instead_of_assuming_zero(self):
        actor,scope,_,_=self.component(stage='private')
        actor._supervisors_stopped=Mock();actor._sessions=Mock(return_value=[])
        actor.activation_guard.return_value={'target_write_authority':False}
        def query(body):
            if adapter.BACKGROUND_WRITER_SQL in body:return '1'
            if 'pg_prepared_xacts' in body:return '0'
            raise AssertionError('Unexpected SQL')
        actor._sql=Mock(side_effect=query)
        observed=actor.observe_private_boundary(scope)
        self.assertEqual(observed['unknown_writers'],1)
        self.assertEqual(observed['unknown_client_sessions'],0)


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
        actor._sql=Mock(return_value='0')
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
        actor._known_sessions.return_value=True;actor._sql.return_value='1'
        with self.assertRaisesRegex(RuntimeError,'unknown_background_writer'):actor.capture_preimage(scope)
        actor.runtime.command.assert_not_called()

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

    def test_private_provider_boundary_requires_independent_stage_for_candidate_extension(self):
        actor,scope,_,_=self.component(stage='private')
        actor.require_authority(scope,purpose='prepare_private_activation')
        candidate,other_scope,_,_=self.component(stage='private',candidates=True)
        candidate.require_authority(other_scope,purpose='prepare_private_activation')
        (candidate.root/'candidate-staged-runtime.json').unlink()
        with self.assertRaisesRegex(RuntimeError,'private_candidate_stage_required'):
            candidate.require_authority(other_scope,purpose='prepare_private_activation')
        actor.runtime.command.assert_not_called();candidate.runtime.command.assert_not_called()

    def test_private_candidate_stage_rejects_substituted_source_container_spec_or_alias(self):
        actor,scope,_,_=self.component(stage='private',candidates=True)
        original=copy.deepcopy(actor._rows.return_value)
        candidate=next(r for r in actor._rows.return_value if r['Id']==actor.inventory['containers']['candidate:backend']['id'])
        for mutate in (lambda:candidate.update(Id='f'*64),lambda:candidate['Config']['Env'].append('SUBSTITUTED=1'),
                lambda:next(iter(candidate['NetworkSettings']['Networks'].values())).update(Aliases=['foreign'])):
            mutate()
            with self.assertRaisesRegex(RuntimeError,'private_candidate_identity_changed'):
                actor.require_authority(scope,purpose='prepare_private_activation')
            actor._rows.return_value=copy.deepcopy(original)
            candidate=next(r for r in actor._rows.return_value if r['Id']==actor.inventory['containers']['candidate:backend']['id'])

    def test_private_resume_starts_only_provider_trio_then_sealed_app_without_workers_or_proxy(self):
        actor,scope,preimage,_=self.component(stage='fenced',candidates=True)
        actor._roles=Mock(return_value={});actor._expected_roles=Mock(return_value={})
        by_id={r['Id']:r for r in actor._rows.return_value}
        def start(arguments):
            self.assertEqual(arguments[:2],['docker','start']);by_id[arguments[2]]['State']['Running']=True
        actor.runtime.command.side_effect=start
        actor.resume_providers_private(scope,preimage)
        expected=['native:auth','native:rest','native:storage','candidate:redis','candidate:backend','candidate:frontend']
        self.assertEqual([c.args[0][2] for c in actor.runtime.command.call_args_list],
            [actor.inventory['containers'][key]['id'] for key in expected])
        actor._attest('private')
        self.assertTrue(all(not by_id[record['id']]['State']['Running'] for logical,record in actor.inventory['containers'].items()
            if logical=='proxy' or logical.startswith('candidate:') and logical.split(':',1)[1] in inventory.WORKER_ROLES))

    def test_private_start_failure_does_not_continue_to_application_or_ingress(self):
        actor,scope,preimage,_=self.component(stage='fenced',candidates=True)
        actor._roles=Mock(return_value={});actor._expected_roles=Mock(return_value={})
        actor.runtime.command.side_effect=RuntimeError('synthetic_provider_start_failed')
        with self.assertRaisesRegex(RuntimeError,'provider_start_failed'):actor.resume_providers_private(scope,preimage)
        self.assertEqual(actor.runtime.command.call_count,1)

    def test_canonical_private_resume_starts_bounded_parser_before_backend_and_no_consumers(self):
        actor,scope,preimage,_=self.component(stage='fenced',candidates=True,target=160)
        actor._roles=Mock(return_value={});actor._expected_roles=Mock(return_value={})
        by_id={r['Id']:r for r in actor._rows.return_value}
        def start(arguments):
            self.assertEqual(arguments[:2],['docker','start']);by_id[arguments[2]]['State']['Running']=True
        actor.runtime.command.side_effect=start
        actor.resume_providers_private(scope,preimage)
        expected=['native:auth','native:rest','native:storage','candidate:redis','candidate:parser-worker',
            'candidate:backend','candidate:frontend']
        self.assertEqual([c.args[0][2] for c in actor.runtime.command.call_args_list],
            [actor.inventory['containers'][key]['id'] for key in expected])
        actor._attest('private')
        for role in inventory.consuming_worker_roles(scope):
            self.assertFalse(by_id[actor.inventory['containers']['candidate:'+role]['id']]['State']['Running'])
        self.assertFalse(by_id[actor.inventory['containers']['proxy']['id']]['State']['Running'])

    def test_canonical_private_resume_refuses_credentialed_parser_before_any_provider_start(self):
        actor,scope,preimage,_=self.component(stage='fenced',candidates=True,target=160)
        row=next(r for r in actor._rows.return_value
            if r['Id']==actor.inventory['containers']['candidate:parser-worker']['id'])
        row['Config']['Env'].append('SUPABASE_SERVICE_KEY=synthetic-forbidden')
        with self.assertRaises(RuntimeError):actor.resume_providers_private(scope,preimage)
        actor.runtime.command.assert_not_called()

    def test_activation_starts_only_workers_then_supporting_native_actors_and_proxy_last(self):
        actor,scope,preimage,_=self.component(stage='private',candidates=True)
        actor.require_authority=Mock();actor.activation_guard.return_value={'target_write_authority':True}
        self.route_transport(actor)
        stage=json.loads((actor.root/'candidate-staged-runtime.json').read_text())
        actor.contract.update(source_roles={'application_sha':'a'*40},origin={'slot':'blue'})
        owner={'owner':'CANDIDATE','generation':stage['worker_generation'],
            'old':{'sha':'a'*40,'slot':'blue'},'candidate':{'sha':scope['source_sha'],'slot':'green'}}
        patcher=patch('deployment.lib.runtime_authority.load_worker_authority',return_value=owner)
        patcher.start();self.addCleanup(patcher.stop)
        by_id={r['Id']:r for r in actor._rows.return_value}
        def start(arguments):by_id[arguments[2]]['State']['Running']=True
        actor.runtime.command.side_effect=start
        actor.resume_accepted_workers(scope,preimage)
        workers={record['id'] for logical,record in actor.inventory['containers'].items()
            if logical.startswith('candidate:') and logical.split(':',1)[1] in inventory.WORKER_ROLES}
        self.assertEqual({c.args[0][2] for c in actor.runtime.command.call_args_list},workers)
        actor.runtime.command.reset_mock();actor.restore_ingress(scope,preimage)
        started=[c.args[0][2] for c in actor.runtime.command.call_args_list]
        self.assertEqual(started[-1],actor.inventory['containers']['proxy']['id'])
        self.assertFalse(set(started)&{r['id'] for r in actor.inventory['containers'].values() if r['generation']=='candidate'})
        self.assertEqual(actor.route_file.read_bytes(),actor.target_route())
        actor.verify_target_route()

    def route_transport(self, actor):
        """Real private route/receipt/fsync/flock; explicit modeled Nginx/HTTP."""
        from deployment.lib import emergency_routing_repair as routing
        actor.route_file=actor.root/'active-upstreams.conf'
        actor.route_file.write_bytes(b'synthetic obsolete origin route\n')
        actor.contract['candidate']['slot']='green'
        patcher=patch.object(routing,'UPSTREAM',actor.route_file);patcher.start();self.addCleanup(patcher.stop)
        patcher=patch.object(adapter,'LOCKS',(actor.root/'upgrade.lock',actor.root/'deploy.lock'))
        patcher.start();self.addCleanup(patcher.stop)
        patcher=patch.object(adapter,'readonly_configuration',lambda p,**kw:Path(p))
        patcher.start();self.addCleanup(patcher.stop)
        patcher=patch('deployment.lib.completed_normal_admission.require_candidate_authority',
            return_value={'schema':actor.binding['target_schema'],'mode':'NORMAL'})
        patcher.start();self.addCleanup(patcher.stop)
        actor.runtime.publish.side_effect=lambda body:routing.atomic(actor.route_file,body,0o644)
        actor.runtime.verify_maintenance.side_effect=lambda:self.assertEqual(actor.route_file.read_bytes(),routing.MAINTENANCE)
        version={'release_sha':actor.binding['source_sha'],'release_slot':'green','schema_compatible_min':146,
            'schema_compatible_max':actor.binding['target_schema'],'schema_excluded_versions':[]}
        actor.public_version=version
        actor.runtime.json_http.side_effect=lambda url:(version if url.endswith('/health/version') else
            {'ready':True} if url.endswith('/health/ready') else {'restricted':False,'business_writes_enabled':True})
        return actor.route_file

    def route_component(self):
        actor,scope,preimage,journal=self.component(stage='private',candidates=True,target=160)
        actor.require_authority=Mock();actor.activation_guard.return_value={'target_write_authority':True,'public_acceptance':True}
        by_id={r['Id']:r for r in actor._rows.return_value}
        for logical,record in actor.inventory['containers'].items():
            if logical.startswith('candidate:'):by_id[record['id']]['State']['Running']=True
        def command(args):
            self.assertIn(args[0:2],(['docker','start'],['docker','stop']))
            by_id[args[2]]['State']['Running']=args[1]=='start'
        actor.runtime.command.side_effect=command
        path=self.route_transport(actor)
        return actor,scope,preimage,journal,path

    def test_proxy_starts_in_maintenance_before_exact_target_publication(self):
        from deployment.lib.emergency_routing_repair import MAINTENANCE
        actor,scope,preimage,_,path=self.route_component()
        proxy=actor.inventory['containers']['proxy']['id'];command=actor.runtime.command.side_effect
        def observe(args):
            if args==['docker','start',proxy]:self.assertEqual(path.read_bytes(),MAINTENANCE)
            command(args)
        actor.runtime.command.side_effect=observe
        actor.restore_ingress(scope,preimage)
        self.assertEqual((actor.root/'target-route-preimage.conf').read_bytes(),b'synthetic obsolete origin route\n')
        self.assertEqual(path.read_bytes(),actor.target_route())
        actor.verify_target_route()
        actor.runtime.nginx_preflight.assert_called_once_with(actor.target_route(),actor.root)
        original=(actor.root/'target-route-publication.json').read_bytes()
        with self.assertRaises(FileExistsError):actor.restore_ingress(scope,preimage)
        self.assertEqual((actor.root/'target-route-publication.json').read_bytes(),original)

    def test_route_preflight_observation_and_receipt_failure_keep_maintenance(self):
        from deployment.lib.emergency_routing_repair import MAINTENANCE
        for fault in ('preflight','wrong_public_source','receipt'):
            with self.subTest(fault=fault):
                actor,scope,preimage,_,path=self.route_component()
                if fault=='preflight':actor.runtime.nginx_preflight.side_effect=RuntimeError('synthetic_preflight_failed')
                elif fault=='wrong_public_source':actor.public_version['release_sha']='0'*40
                original=adapter.exclusive
                def write(destination,body):
                    if fault=='receipt' and destination.name=='target-route-publication.json':
                        raise OSError('synthetic_receipt_failed')
                    original(destination,body)
                with patch.object(adapter,'exclusive',side_effect=write),self.assertRaises((RuntimeError,OSError)):
                    actor.restore_ingress(scope,preimage)
                self.assertEqual(path.read_bytes(),MAINTENANCE)
                self.assertFalse((actor.root/'target-route-publication.json').exists())
                self.assertTrue((actor.root/'target-route-preimage.conf').exists())

    def test_failed_maintenance_reload_stops_only_the_exact_ingress_actors(self):
        actor,scope,preimage,_,_=self.route_component()
        actor.runtime.reload.side_effect=RuntimeError('synthetic_reload_failed')
        with self.assertRaisesRegex(RuntimeError,'synthetic_reload_failed'):actor.restore_ingress(scope,preimage)
        stops=[c.args[0] for c in actor.runtime.command.call_args_list if c.args[0][1]=='stop']
        self.assertEqual(stops,[['docker','stop',actor.inventory['containers']['native:gateway']['id']],
            ['docker','stop',actor.inventory['containers']['proxy']['id']]])
        self.assertFalse((actor.root/'target-route-publication.json').exists())

    def test_changed_target_route_or_publication_blocks_boot_release(self):
        actor,scope,preimage,_,path=self.route_component();actor.restore_ingress(scope,preimage)
        original=path.read_bytes();path.write_bytes(b'synthetic substituted route')
        with self.assertRaisesRegex(RuntimeError,'target_route_changed'):actor.verify_target_route()
        path.write_bytes(original)
        record=actor.root/'target-route-publication.json'
        value=json.loads(record.read_bytes());value['candidate_stage_sha256']='0'*64
        record.write_text(json.dumps(value))
        with self.assertRaisesRegex(RuntimeError,'publication_changed'):actor.clear_boot_interlock(scope,preimage)
        self.assertTrue(actor.barrier.exists())

    def test_target_authority_alone_cannot_open_ingress_before_workers_are_running(self):
        actor,scope,preimage,_=self.component(stage='private',candidates=True)
        actor.require_authority=Mock();actor.activation_guard.return_value={'target_write_authority':True}
        with self.assertRaisesRegex(RuntimeError,'candidate_activation_incomplete'):actor.restore_ingress(scope,preimage)
        actor.runtime.command.assert_not_called()

    def test_target_grant_without_the_childs_positive_owner_cannot_start_workers(self):
        actor,scope,preimage,_=self.component(stage='private',candidates=True,target=160)
        with patch('deployment.lib.runtime_authority.load_worker_authority',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'accepted_worker_owner_required'):
                actor.resume_accepted_workers(scope,preimage)
        actor.runtime.command.assert_not_called()

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
        actor,scope,preimage,journal=self.component(stage='private',candidates=True,target=160)
        self.route_transport(actor)
        actor._rows.return_value=phase_rows(actor.inventory,actor._rows.return_value,'active')
        actor.runtime.command.side_effect=None
        actor.restore_ingress(scope,preimage)
        actor.runtime.command.reset_mock();actor._verify_barrier.reset_mock()
        for step in lifecycle.ACTIVATE_STEPS:
            journal.append('effect_intent',{'step':step})
            if step!='clear_boot_interlock':journal.append('effect_complete',{'step':step})
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

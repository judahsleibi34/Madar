"""Real private journal/locking with injected effects; no production adapter.

These are source state-machine tests. They do not certify installed systemd,
host reboot, provider transport, replica acceptance or operational authorization.
"""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib import schema149_provider_lifecycle as retained
from deployment.lib import schema150_provider_lifecycle as lifecycle


def binding():
    return {'operation': 'completed-normal-schema146-150-coordinated-release',
            'context_sha256': 'a'*64, 'source_sha': 'b'*40, 'controller_sha': 'c'*40,
            'inventory_sha256': 'd'*64, 'system_identifier': '123456789',
            'source_schema': 146, 'target_schema': 150}


class Actor:
    def __init__(self):
        self.calls, self.effects = [], set()
        self.authorized, self.crash, self.before_effect = True, None, False
        self.observed = {'system_identifier': '123456789', 'schema': 146,
                         **{key: 0 for key in lifecycle.COUNTERS},
                         **{key: True for key in lifecycle.FENCES}}
        self.activation = {'binding_sha256': lifecycle.digest(binding()), 'schema': 150,
                           'delivery_protocol': 2, 'outbox_protocol': 2, 'deletion_protocol': 2,
                           'target_write_authority': False, 'write_authority_sha256': None,
                           **{key: True for key in lifecycle.PRE_GRANT_GATES}}
        self.boundary = {'binding_sha256': lifecycle.digest(binding()), 'ingress_fenced': True,
                         'workers_fenced': True, 'boot_interlock_armed': True, 'candidate_read_only': True,
                         'unknown_writers': 0, 'unknown_client_sessions': 0, 'prepared_transactions': 0}

    def require_authority(self, expected, *, purpose):
        if not self.authorized or expected != binding():
            raise RuntimeError('fixture_fresh_protected_authority_missing')
        self.calls.append(('guard', purpose))

    def positive_identity_probes(self, expected):
        self.calls.append(('positive_probes',))
        return {'binding_sha256': lifecycle.digest(expected), 'postgrest': True,
                'auth_scope': True, 'storage_scope': True, 'database_scope': True}

    def capture_preimage(self, expected):
        self.calls.append(('preimage',))
        return {'ingress': {'route': 'original'}, 'supervisors': {'restart': 'original'},
                'objects': {'mount': 'original'}, 'roles': {'provider': {'login': True, 'role_ddl_sha256': 'e'*64}}}

    def effect(self, step, expected, preimage):
        self.calls.append(('effect', step))
        if self.crash == step and self.before_effect: raise RuntimeError('fixture_crash')
        self.effects.add(step)
        if self.crash == step: raise RuntimeError('fixture_crash')

    def verify_effect(self, step, expected, preimage):
        self.calls.append(('verify', step))
        return step in self.effects

    def observe_quiescence(self, expected): return copy.deepcopy(self.observed)
    def observe_private_boundary(self, expected): return copy.deepcopy(self.boundary)
    def activation_evidence(self, expected, preimage): return copy.deepcopy(self.activation)

    def observe_existing_grant(self):
        # Fixture ONLY. The model itself has no issuer or grant-writing method.
        self.activation.update(target_write_authority=True, write_authority_sha256='f'*64)


for _step in lifecycle.STEPS:
    setattr(Actor, _step, lambda self, expected, preimage, step=_step: self.effect(step, expected, preimage))


class Provider150LifecycleTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        root = Path(temporary.name); root.chmod(0o700)
        # Only protected path ownership policy is substituted for this owned temp
        # directory. Real journal publication, fsync, hash chain and flock remain.
        for name, replacement in (('require_root_directory', lambda path: None),
                                  ('protected', lambda path, **kwargs: Path(path))):
            guard = patch.object(retained, name, replacement); guard.start(); self.addCleanup(guard.stop)
        journal = lifecycle.ProtectedProviderJournal(root)
        actor = Actor()
        return lifecycle.ProviderMaintenance150(binding(), journal, actor), actor, journal

    def fenced(self):
        driver, actor, journal = self.fixture(); driver.prepare(); driver.fence()
        return driver, actor, journal

    def private_ready(self):
        driver, actor, journal = self.fenced(); actor.observed['schema'] = 150
        driver.prepare_private_activation()
        return driver, actor, journal

    def test_binding_is150_only_detached_and_historical149_still_rejects150(self):
        for key, invalid in (('operation', 'completed-normal-schema146-149-coordinated-release'),
                             ('target_schema', 149), ('target_schema', True), ('source_schema', 149),
                             ('source_sha', 'bad'), ('inventory_sha256', 'x'*64)):
            bad = binding(); bad[key] = invalid
            with self.subTest(key=key, invalid=invalid), self.assertRaises(RuntimeError): lifecycle.validate_binding(bad)
        with self.assertRaises(RuntimeError): retained.validate_binding(binding())
        original = binding(); detached = lifecycle.validate_binding(original); original['source_sha'] = '9'*40
        self.assertEqual(detached['source_sha'], 'b'*40)

    def test_positive_probes_original_preimages_and_intents_precede_effects(self):
        driver, actor, journal = self.fenced()
        first = next(index for index, call in enumerate(actor.calls) if call[0] == 'effect')
        self.assertLess(actor.calls.index(('positive_probes',)), first)
        self.assertLess(actor.calls.index(('preimage',)), first)
        records = journal.read()
        self.assertTrue(records[0]['payload']['preimage']['roles']['provider']['login'])
        events = [(record['event'], record['payload'].get('step')) for record in records]
        for step in lifecycle.FENCE_STEPS:
            self.assertLess(events.index(('effect_intent', step)), events.index(('effect_complete', step)))
        self.assertTrue(all((path.stat().st_mode & 0o777) == 0o600 for path in journal.root.iterdir()))

    def test_missing_fresh_authority_or_positive_probes_never_fences(self):
        driver, actor, journal = self.fixture(); actor.authorized = False
        with self.assertRaisesRegex(RuntimeError, 'fresh_protected_authority_missing'): driver.prepare()
        self.assertEqual(journal.read(), [])
        actor.authorized = True; actor.positive_identity_probes = lambda _: {}
        with self.assertRaisesRegex(RuntimeError, 'positive_probes_required'): driver.prepare()
        self.assertEqual(actor.effects, set())

    def test_two_actors_cannot_overlap_even_with_same_binding(self):
        driver, actor, journal = self.fixture(); driver.prepare()
        second = lifecycle.ProviderMaintenance150(binding(), journal, actor)
        with driver._locked():
            with self.assertRaisesRegex(RuntimeError, 'actor_already_active'): second.fence()
        second.fence()
        self.assertEqual(driver._state()[1], list(lifecycle.FENCE_STEPS))
        with self.assertRaisesRegex(RuntimeError, 'already_prepared'): second.prepare()

    def test_each_quiescence_counter_including_orphan_steps_and_unknown_writer_blocks(self):
        driver, actor, journal = self.fenced(); original = copy.deepcopy(actor.observed)
        for key in lifecycle.COUNTERS + lifecycle.FENCES:
            actor.observed = copy.deepcopy(original)
            actor.observed[key] = False if key in lifecycle.FENCES else 1
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'not_quiescent'):
                driver.migration_entry(146, 147)
        actor.observed = original; actor.observed['unknown_writers'] = False
        with self.assertRaisesRegex(RuntimeError, 'not_quiescent'): driver.migration_entry(146, 147)

    def test_exact_migration_boundaries_and_no_intermediate_private_activation(self):
        driver, actor, journal = self.fenced()
        for pair in ((146,150), (149,148), (150,151), (True,147)):
            with self.subTest(pair=pair), self.assertRaisesRegex(RuntimeError, 'migration_order'): driver.migration_entry(*pair)
        for source, target in ((146,147), (147,148), (148,149), (149,150)):
            actor.observed['schema'] = source; driver.migration_entry(source, target)
        for schema in (146,147,148,149):
            actor.observed['schema'] = schema
            with self.subTest(schema=schema), self.assertRaises(RuntimeError): driver.prepare_private_activation()
        self.assertFalse(any(step in actor.effects for step in lifecycle.PRIVATE_STEPS))

    def test_private_native_probes_finish_before_any_grant_or_public_resumption(self):
        driver, actor, journal = self.private_ready()
        self.assertIs(actor.activation['target_write_authority'], False)
        self.assertEqual(driver._state()[1], list(lifecycle.FENCE_STEPS + lifecycle.PRIVATE_STEPS))
        with self.assertRaisesRegex(RuntimeError, 'not_authorized'): driver.activate_after_grant()
        self.assertFalse(any(step in actor.effects for step in lifecycle.ACTIVATE_STEPS))
        actor.observe_existing_grant(); result = driver.activate_after_grant()
        self.assertFalse(result['production_authorization_issued'])
        self.assertFalse(result['customer_database_restored'])
        self.assertEqual(driver._state()[1], list(lifecycle.STEPS))
        with self.assertRaisesRegex(RuntimeError, 'already_completed'): driver.activate_after_grant()

    def test_premature_or_missing_private_acceptance_never_enables_old_workers(self):
        driver, actor, journal = self.fenced(); actor.observed['schema'] = 150
        actor.observe_existing_grant()
        with self.assertRaisesRegex(RuntimeError, 'not_authorized'): driver.prepare_private_activation()
        with self.assertRaisesRegex(RuntimeError, 'private_acceptance_required'): driver.activate_after_grant()
        self.assertFalse(any(step in actor.effects for step in lifecycle.PRIVATE_STEPS + lifecycle.ACTIVATE_STEPS))

    def test_worker_and_ingress_activation_keeps_boot_barrier_until_separate_completion(self):
        driver, actor, journal = self.private_ready(); actor.observe_existing_grant()
        result=driver.activate_after_grant(clear_boot=False)
        self.assertFalse(result['provider_lifecycle_complete'])
        self.assertEqual(driver._state()[1],list(lifecycle.STEPS[:-1]))
        self.assertNotIn('clear_boot_interlock',actor.effects)
        actor.authorized=False
        with self.assertRaisesRegex(RuntimeError,'fresh_protected_authority_missing'):
            driver.activate_after_grant()
        self.assertNotIn('clear_boot_interlock',actor.effects)
        actor.authorized=True
        restarted=lifecycle.ProviderMaintenance150(binding(),journal,actor)
        self.assertTrue(restarted.activate_after_grant()['provider_lifecycle_complete'])
        for step in lifecycle.ACTIVATE_STEPS:
            self.assertEqual(actor.calls.count(('effect',step)),1)
        with self.assertRaisesRegex(RuntimeError,'boot_completion_invalid'):
            restarted.activate_after_grant(clear_boot=1)

    def test_private_boundary_rejects_unknown_sessions_prepared_transactions_and_public_open(self):
        for key in ('unknown_writers', 'unknown_client_sessions', 'prepared_transactions',
                    'ingress_fenced', 'workers_fenced', 'boot_interlock_armed', 'candidate_read_only'):
            driver, actor, journal = self.fenced(); actor.observed['schema'] = 150
            actor.boundary[key] = 1 if key in ('unknown_writers', 'unknown_client_sessions', 'prepared_transactions') else False
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'private_boundary_not_fenced'):
                driver.prepare_private_activation()
            self.assertNotIn('restore_roles_private', actor.effects)

    def test_every_gate_and_exact_protocol_is_required_before_private_recovery(self):
        for key in lifecycle.PRE_GRANT_GATES + ('schema', 'delivery_protocol', 'outbox_protocol', 'deletion_protocol', 'binding_sha256'):
            driver, actor, journal = self.fenced(); actor.observed['schema'] = 150
            actor.activation[key] = False
            with self.subTest(key=key), self.assertRaises(RuntimeError): driver.prepare_private_activation()
            self.assertNotIn('restore_roles_private', actor.effects)

    def test_all_fence_crashes_require_observation_and_never_replay(self):
        for step in lifecycle.FENCE_STEPS:
            driver, actor, journal = self.fixture(); driver.prepare(); actor.crash = step
            with self.subTest(step=step), self.assertRaisesRegex(RuntimeError, 'fixture_crash'): driver.fence()
            restarted = lifecycle.ProviderMaintenance150(binding(), journal, actor)
            with self.assertRaisesRegex(RuntimeError, 'interrupted_effect'): restarted.fence()
            actor.authorized = False
            with self.assertRaisesRegex(RuntimeError, 'fresh_protected_authority_missing'): restarted.reconcile_pending()
            actor.authorized = True; restarted.reconcile_pending(); actor.crash = None; restarted.fence()
            self.assertEqual(actor.calls.count(('effect', step)), 1)

    def test_unapplied_uncertain_effect_is_not_replayed_or_cleared(self):
        driver, actor, journal = self.fixture(); driver.prepare()
        actor.crash, actor.before_effect = 'fence_ingress', True
        with self.assertRaisesRegex(RuntimeError, 'fixture_crash'): driver.fence()
        with self.assertRaisesRegex(RuntimeError, 'uncertain_effect'): driver.reconcile_pending()
        self.assertEqual(driver._state()[2], 'fence_ingress')
        self.assertEqual(actor.calls.count(('effect', 'fence_ingress')), 1)

    def test_private_and_postgrant_crashes_reconcile_without_repeating_effect(self):
        for step in lifecycle.PRIVATE_STEPS + lifecycle.ACTIVATE_STEPS:
            driver, actor, journal = self.fenced(); actor.observed['schema'] = 150
            if step in lifecycle.ACTIVATE_STEPS:
                driver.prepare_private_activation(); actor.observe_existing_grant()
            actor.crash = step
            operation = driver.prepare_private_activation if step in lifecycle.PRIVATE_STEPS else driver.activate_after_grant
            with self.subTest(step=step), self.assertRaisesRegex(RuntimeError, 'fixture_crash'): operation()
            restarted = lifecycle.ProviderMaintenance150(binding(), journal, actor)
            method = restarted.prepare_private_activation if step in lifecycle.PRIVATE_STEPS else restarted.activate_after_grant
            with self.assertRaisesRegex(RuntimeError, 'interrupted_effect'): method()
            restarted.reconcile_pending(); actor.crash = None
            if step != lifecycle.ACTIVATE_STEPS[-1]: method()
            self.assertEqual(actor.calls.count(('effect', step)), 1)

    def test_authority_or_worker_identity_loss_blocks_next_effect(self):
        for key in ('accepted_images', 'worker_ownership', 'target_write_authority', 'write_authority_sha256'):
            driver, actor, journal = self.private_ready(); actor.observe_existing_grant()
            original = actor.resume_accepted_workers
            def mutate(expected, preimage):
                original(expected, preimage); actor.activation[key] = False
            actor.resume_accepted_workers = mutate
            with self.subTest(key=key), self.assertRaises(RuntimeError): driver.activate_after_grant()
            self.assertNotIn('restore_ingress', actor.effects)

    def test_restart_requires_original_binding_and_fresh_authority_not_journal_pass(self):
        driver, actor, journal = self.private_ready(); actor.observe_existing_grant(); actor.authorized = False
        with self.assertRaisesRegex(RuntimeError, 'fresh_protected_authority_missing'): driver.activate_after_grant()
        actor.authorized = True
        changed = binding(); changed['context_sha256'] = '9'*64
        alternate = lifecycle.ProviderMaintenance150(changed, journal, actor)
        with self.assertRaises(RuntimeError): alternate.activate_after_grant()
        self.assertNotIn('resume_accepted_workers', actor.effects)

    def test_unknown_or_partial_journal_records_never_become_authority(self):
        driver, actor, journal = self.fenced()
        journal.append('effect_intent', {'step': 'arbitrary_sql'})
        with self.assertRaisesRegex(RuntimeError, 'journal_sequence'): driver.reconcile_pending()
        path = journal.root/'0000.json'; record = json.loads(path.read_text())
        record['payload']['binding']['source_sha'] = 'f'*40; path.write_text(json.dumps(record))
        with self.assertRaisesRegex(RuntimeError, 'journal_chain'): driver.fence()


if __name__ == '__main__': unittest.main()

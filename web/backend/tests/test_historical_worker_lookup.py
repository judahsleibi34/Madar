"""Real release CLI lookup; credential delivery is modeled, not authority."""
import copy
import unittest
from unittest.mock import patch
from deployment.lib import completed_normal_admission as admission
from deployment.lib import historical_origin as history
from deployment.lib.completed_normal_profile import RECONCILED
import test_historical_origin as fixtures
from test_release_bootstrap import release_cli


class HistoricalWorkerLookupTests(unittest.TestCase):
    def setUp(self):
        fixtures.HistoricalControllerConsumerTests.setUp(self)
        self.projection=history.history_witness(self.contract)
        self.witness=copy.deepcopy(self.projection['original_runtime'])
        self.ops=object.__new__(release_cli.DockerGitOperations)
        self.ops.completed_normal_admission=self.contract
        self.enterContext(patch.object(release_cli,'profile',return_value=RECONCILED))
        self.enterContext(patch('deployment.lib.completed_normal_profile.profile',return_value=RECONCILED))
        self.enterContext(patch.object(admission.os,'geteuid',return_value=1000))
        self.fresh=self.enterContext(patch.object(admission,'require_fresh_authorization'))
        self.enterContext(patch.object(admission,'credential_witness',side_effect=self.credential))

    def credential(self,name,digest):
        return self.witness if name=='origin_runtime' else self.projection

    def lookup(self):
        return self.ops._worker_names(self.contract['origin']['slot'])

    def test_historical_ids_without_fabricated_context_or_completion(self):
        self.assertNotIn('completion_root',self.contract['source_roles'])
        self.assertNotIn('context_sha256',self.witness)
        self.assertEqual(self.lookup(),[self.witness['runtimes'][role]['id'] for role in
            ('notification-worker','calendar-sync-worker','data-deletion-worker')])
        self.fresh.assert_called_once_with(self.contract)

    def test_ownership_observer_accepts_stopped_exact_original_workers(self):
        # Existing ownership state algorithm, with explicitly modeled Docker.
        with patch.object(self.ops,'_container_state',return_value=('id','exited','none')):
            result=self.ops.worker_ownership({'slot':self.contract['origin']['slot']},
                {'slot':self.contract['candidate']['slot']})
        self.assertEqual(result,'none')
        self.fresh.assert_called_once()

    def test_changed_actor_or_source_or_generation_refuses(self):
        for field,value in [('source_sha','f'*40),('worker_generation','f'*64),
                            ('images',{}),('runtimes',{})]:
            saved=self.witness;self.witness=dict(saved,**{field:value})
            with self.subTest(field=field),self.assertRaisesRegex(RuntimeError,'origin_worker_runtime_changed'):
                self.lookup()
            self.witness=saved

    def test_changed_successor_or_database_cannot_reuse_history(self):
        for field in ('source_roles','database','origin','historical_files'):
            saved=self.projection;self.projection=dict(saved,**{field:{}})
            with self.subTest(field=field),self.assertRaisesRegex(RuntimeError,'child_history_changed'):
                self.lookup()
            self.projection=saved

    def test_missing_fresh_authority_refuses_before_lookup(self):
        self.fresh.side_effect=RuntimeError('expired_child_authority')
        with self.assertRaisesRegex(RuntimeError,'expired_child_authority'):self.lookup()

    def test_ambiguous_actor_projection_refuses(self):
        roles=self.projection['original_runtime']['runtimes']
        roles['frontend']['id']=roles['backend']['id']
        with self.assertRaisesRegex(RuntimeError,'actor_ambiguous'):self.lookup()

    def test_modern_origin_still_requires_exact_completion_context(self):
        self.contract['source_roles'].pop('origin_kind')
        self.contract['source_roles']['completion_root']='/fixture/'+'a'*64
        self.witness['context_sha256']='a'*64
        self.assertEqual(len(self.lookup()),3)
        self.fresh.assert_not_called()
        self.witness['context_sha256']='b'*64
        with self.assertRaisesRegex(RuntimeError,'origin_worker_runtime_changed'):self.lookup()

    def test_modern_origin_without_completion_never_falls_back(self):
        self.contract['source_roles'].pop('origin_kind')
        with self.assertRaises(KeyError):self.lookup()
        self.fresh.assert_not_called()


if __name__=='__main__':unittest.main()

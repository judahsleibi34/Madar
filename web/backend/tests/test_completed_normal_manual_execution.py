"""Actual coordinator control flow with isolated transports, not Docker PASS."""
import json
import unittest
from unittest.mock import patch

import test_completed_normal_execution as fixture
from test_completed_normal_manual_profile import manual_contract
from deployment.lib import completed_normal_resources


class ManualExecutionTests(unittest.TestCase):
    source_schema=136
    target_schema=144
    make_contract=staticmethod(manual_contract)
    seal_completion=fixture.ExecutionTests.seal_completion

    def setUp(self):
        fixture.ExecutionTests.setUp(self)
        def retire(*args,**kwargs):
            self.effect('retire_exact_blue')
            return {'stopped_ids':['owned-fixture-blue'],'volumes_deleted':False,'customer_database_restored':False}
        p=patch.object(completed_normal_resources,'retire_bound_resources',retire);p.start();self.addCleanup(p.stop)
        p=patch.object(fixture.m,'enter_manual_maintenance',lambda actor:{'api_http':503,'customer_database_restored':False});p.start();self.addCleanup(p.stop)
        self.driver.actor.publish_restricted_bridge=lambda:self.effect('publish_target_read_only')

    def test_only_target_grant_follows_verified_backup_and_actual_sql_completion(self):
        result=self.driver.execute()
        self.assertEqual(result['schema'],144)
        self.assertNotIn('grant_136',self.calls)
        self.assertEqual(self.calls.count('grant_144'),1)
        self.assertLess(self.calls.index('retire_exact_blue'),self.calls.index('service_prepare'))
        self.assertLess(self.calls.index('fence_origin'),self.calls.index('service_activate'))
        self.assertLess(self.calls.index('backup_pre-migration'),self.calls.index('service_migrate'))
        self.assertLess(self.calls.index('customer_preservation'),self.calls.index('grant_144'))
        self.assertLess(self.calls.index('seal_sql_completion'),self.calls.index('grant_144'))
        self.assertEqual((self.mode,self.owners,self.backup_count),('NORMAL',1,2))

    def test_pre_migration_failures_never_grant_normal(self):
        self.failure='backup_pre-migration'
        with self.assertRaises(RuntimeError):self.driver.execute()
        self.assertEqual((self.mode,self.schema),('READ_ONLY',136))
        self.assertNotIn('service_migrate',self.calls);self.assertNotIn('grant_144',self.calls)

    def test_post_migration_failure_preserves144_and_revokes_writes(self):
        self.failure='backup_post-migration'
        with self.assertRaises(RuntimeError):self.driver.execute()
        self.assertEqual((self.schema,self.mode,self.owners),(144,'READ_ONLY',1))
        evidence=json.loads((self.root/'failure.json').read_text())
        self.assertFalse(evidence['customer_database_restored'])
        self.assertNotIn('PRIVATE VALUE',json.dumps(evidence))
        self.assertNotIn('restore_timers',self.calls)

    def test_changed_retirement_stops_before_candidate_and_sql(self):
        self.failure='retire_exact_blue'
        with self.assertRaises(RuntimeError):self.driver.execute()
        self.assertNotIn('service_prepare',self.calls);self.assertNotIn('service_migrate',self.calls)
        self.assertEqual(self.schema,136)


if __name__=='__main__':unittest.main()

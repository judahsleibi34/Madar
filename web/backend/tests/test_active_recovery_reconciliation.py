"""Synthetic read-only SQL scope regressions; no customer database access."""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_reconciliation import CurrentLocalReconciliation,identifier

class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.sql=[];self.catalog=[{'schema':'public','table':'example'}]
        self.roots=[{'table':'example','count':2,'sha256':'a'*64},{'schema':115}]
        self.changed=False
        def command(args):
            self.sql.append(args[-1])
            result=self.catalog if 'FROM pg_class c' in args[-1] else self.roots
            if self.changed and len(self.sql)==3:result=[]
            return '\n'.join(json.dumps(row) for row in result)
        self.r=CurrentLocalReconciliation(None,Path('/synthetic'),SimpleNamespace(command=command),lambda:None,lambda:None)
    def test_all_roots_and_schema_share_read_only_repeatable_snapshot(self):
        packet,sha=self.r.snapshot()
        self.assertEqual(len(sha),64);self.assertEqual(packet['schema'],115)
        self.assertFalse(packet['customer_data_modified']);self.assertFalse(packet['migration_executed'])
        body=self.sql[1]
        self.assertTrue(body.startswith('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;'))
        self.assertIn('public.application_schema_state',body);self.assertIn('sha256',body)
        self.assertNotIn('INSERT ',body);self.assertNotIn('UPDATE ',body)
    def test_changed_catalog_aborts(self):
        self.changed=True
        with self.assertRaisesRegex(RuntimeError,'catalog_changed'):self.r.snapshot()
    def test_schema_or_missing_table_root_aborts(self):
        self.roots[-1]={'schema':116}
        with self.assertRaisesRegex(RuntimeError,'snapshot_invalid'):self.r.snapshot()
    def test_identifier_quoting_does_not_create_sql_statements(self):
        self.assertEqual(identifier('example";DROP TABLE x;--'),'"example"";DROP TABLE x;--"')
        with self.assertRaises(RuntimeError):identifier('example\x00')
    def test_duplicate_rows_are_not_lost_by_distinct_aggregation(self):
        self.r.snapshot();self.assertIn('string_agg(row_sha',self.sql[1]);self.assertNotIn('DISTINCT',self.sql[1])
    def test_readonly_observer_does_not_issue_an_authorization(self):
        source=(WEB/'scripts'/'observe_current_local_reconciliation.py').read_text()
        self.assertNotIn('.fence_retained_hosted_writers(',source)
        self.assertNotIn('.grant(',source)

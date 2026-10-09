"""Execution-provenance fixtures; these are not production evidence."""
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.active_recovery_execution import actual_inline_execution
from deployment.lib.provider_recovery_runtime import file_digest

class ActualExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.entry='web/scripts/test_execution.py';source=self.root/self.entry
        source.parent.mkdir(parents=True);source.write_text('# test fixture');source.chmod(0o500)
        now=datetime.now(timezone.utc)
        self.record={'operation':'fixture-execution','exit_code':0,'stderr':'',
            'argv':['/usr/bin/python3','-I','-B',str(source)],
            'source_files':{self.entry:file_digest(source)},'started_at':(now-timedelta(seconds=2)).isoformat(),
            'finished_at':(now-timedelta(seconds=1)).isoformat(),'stdout':'{"stage":"actual"}\n{"result":"fixture"}\n'}
        self.path=self.root/'actual-execution.json';self.save()
        p=patch('deployment.lib.active_recovery_execution.protected',side_effect=lambda p,**kw:p);p.start();self.addCleanup(p.stop)
    def save(self):self.path.write_text(json.dumps(self.record));self.hash=file_digest(self.path)
    def verify(self):return actual_inline_execution(self.path,self.hash,'fixture-execution',self.entry)
    def test_exact_successful_execution_preserves_original(self):
        old=self.path.read_bytes();self.assertEqual(self.verify()[0],{'result':'fixture'});self.assertEqual(self.path.read_bytes(),old)
    def test_agent_pass_packet_without_actual_invocation_is_rejected(self):
        self.record={'operation':'fixture-execution','status':'PASS'};self.save()
        with self.assertRaisesRegex(RuntimeError,'not_successful'):self.verify()
    def test_modified_transcript_breaks_approved_hash(self):
        self.path.write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'record_changed'):self.verify()
    def test_failed_execution_or_stderr_is_rejected(self):
        for key,value in [('exit_code',1),('exit_code',False),('stderr','fixture error')]:
            previous=self.record.copy();self.record[key]=value;self.save()
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'not_successful'):self.verify()
            self.record=previous
    def test_mutable_or_modified_executed_source_is_rejected(self):
        source=self.root/self.entry;source.chmod(0o700)
        with self.assertRaisesRegex(RuntimeError,'source_changed'):self.verify()
        source.write_text('changed fixture');source.chmod(0o500)
        with self.assertRaisesRegex(RuntimeError,'source_changed'):self.verify()
    def test_nonisolated_or_foreign_entry_is_rejected(self):
        for argv in [['/usr/bin/python3',str(self.root/self.entry)],['/usr/bin/python3','-I','-B','/mutable/entry.py']]:
            self.record['argv']=argv;self.save()
            with self.assertRaisesRegex(RuntimeError,'not_successful'):self.verify()
    def test_missing_source_inventory_is_rejected(self):
        self.record['source_files']={};self.save()
        with self.assertRaisesRegex(RuntimeError,'source_missing'):self.verify()
    def test_source_path_escape_is_rejected(self):
        self.record['source_files']['../escape']='a'*64;self.save()
        with self.assertRaisesRegex(RuntimeError,'source_invalid'):self.verify()
    def test_future_or_naive_timing_is_rejected(self):
        for finish in [datetime.now().isoformat(),(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()]:
            self.record['finished_at']=finish;self.save()
            with self.assertRaisesRegex(RuntimeError,'time_invalid'):self.verify()
    def test_stdout_must_be_json_execution_rows(self):
        self.record['stdout']='PASS';self.save()
        with self.assertRaisesRegex(RuntimeError,'transcript_invalid'):self.verify()

    def test_fixed_source_subdirectory_layout_is_bound_to_argv(self):
        target=self.root/'source'/self.entry;target.parent.mkdir(parents=True);target.write_bytes((self.root/self.entry).read_bytes());target.chmod(0o500)
        self.record['argv'][-1]=str(target);self.save()
        report,_=actual_inline_execution(self.path,self.hash,'fixture-execution',self.entry,source_directory='source')
        self.assertEqual(report,{'result':'fixture'})
        with self.assertRaisesRegex(RuntimeError,'not_successful'):self.verify()
        with self.assertRaisesRegex(RuntimeError,'layout_invalid'):
            actual_inline_execution(self.path,self.hash,'fixture-execution',self.entry,source_directory='../escape')

class ReconciliationScopeTests(unittest.TestCase):
    def test_compensated_execution_has_its_own_source_bound_record(self):
        from types import SimpleNamespace
        from deployment.lib.active_recovery_execution import verify_local_reconciliation_execution,PREPARATION
        from deployment.lib.provider_recovery_runtime import digest
        packet={'schema':115,'migration_executed':False,'customer_data_modified':False,
            'database_restore_performed':False,'table_roots':[{'table':'fixture','count':1,'sha256':'a'*64}]}
        inputs={'fixture':'b'*64}
        report={'operation':'actual-current-local-read-only-reconciliation','retained_inputs':inputs,'schema':115,
            'production_modified':False,'consumers_started':False,'business_writes_enabled':False,'authorization_issued':False,
            'snapshot':packet,'snapshot_sha256':digest(packet)}
        plan=SimpleNamespace(source_sha='c'*40,candidate_destination={'post_compensation':{'baseline_sha256':'d'*64}},
            retained_inputs=inputs,reconciliation_execution_sha256='e'*64)
        with patch('deployment.lib.active_recovery_execution.actual_inline_execution',return_value=(report,{})) as actual:
            self.assertEqual(verify_local_reconciliation_execution(plan)['tables'],1)
            self.assertEqual(actual.call_args.args[0],PREPARATION/('local-post-compensation-reconciliation-'+'c'*40)/'actual-execution.json')
            report['retained_inputs']={'historical':'b'*64}
            with self.assertRaisesRegex(RuntimeError,'scope_invalid'):verify_local_reconciliation_execution(plan)
    def test_original_recovery_record_path_remains_unchanged(self):
        from types import SimpleNamespace
        from deployment.lib.active_recovery_execution import verify_local_reconciliation_execution,RECONCILIATION
        plan=SimpleNamespace(candidate_destination={},reconciliation_execution_sha256='e'*64)
        with patch('deployment.lib.active_recovery_execution.actual_inline_execution',side_effect=RuntimeError('fixture')) as actual:
            with self.assertRaisesRegex(RuntimeError,'fixture'):verify_local_reconciliation_execution(plan)
            self.assertEqual(actual.call_args.args[0],RECONCILIATION)
    def test_compensated_source_cannot_select_an_arbitrary_path(self):
        from types import SimpleNamespace
        from deployment.lib.active_recovery_execution import verify_local_reconciliation_execution
        plan=SimpleNamespace(source_sha='../foreign',candidate_destination={'post_compensation':{'fixture':True}})
        with self.assertRaisesRegex(RuntimeError,'source_invalid'):verify_local_reconciliation_execution(plan)

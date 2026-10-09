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

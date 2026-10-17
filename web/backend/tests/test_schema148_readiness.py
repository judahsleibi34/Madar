import copy
from datetime import datetime,timedelta,timezone
from pathlib import Path
import os
import sys
import unittest
sys.path.insert(0,os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib.schema148_readiness import evaluate,GATES

class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc);self.sha='a'*40
        self.record={'status':'PASS','source_sha':self.sha,'sha256':'b'*64,'scope':'production','observed_at':self.now.isoformat()}
    def evaluate(self,values):return evaluate(values,source_sha=self.sha,environment='production',now=self.now)
    def test_missing_evidence_is_not_pass(self):
        result=self.evaluate({});self.assertEqual(result['assessment'],'NOT READY')
        self.assertTrue(all(row['status']=='NOT TESTED' for row in result['gates'].values()))
    def test_complete_technical_packet_still_cannot_authorize_production(self):
        result=self.evaluate({gate:dict(self.record) for gate in GATES})
        self.assertEqual(result['assessment'],'TECHNICALLY READY FOR OPERATOR REVIEW')
        self.assertFalse(result['production_authorized'])
        self.assertEqual(result['gates']['operator.authorization']['status'],'BLOCKED')
    def test_worker_quiescence_cannot_substitute_for_provider_writer_quiescence(self):
        packet={gate:dict(self.record) for gate in GATES if gate!='database.provider_quiescence'}
        result=self.evaluate(packet)
        self.assertEqual(result['gates']['database.quiescence']['status'],'PASS')
        self.assertEqual(result['gates']['database.provider_quiescence']['status'],'NOT TESTED')
        self.assertEqual(result['assessment'],'NOT READY')
        packet['database.provider_quiescence']=dict(self.record,scope='staging')
        result=self.evaluate(packet)
        self.assertEqual(result['gates']['database.provider_quiescence']['status'],'PARTIAL')
        self.assertEqual(result['assessment'],'NOT READY')
    def test_synthetic_evidence_does_not_satisfy_production_gate(self):
        record=dict(self.record,scope='staging')
        self.assertEqual(self.evaluate({'recovery.independent_application':record})['gates']['recovery.independent_application']['status'],'PARTIAL')
    def test_stale_future_missing_timestamps_block(self):
        for instant in (self.now-timedelta(minutes=6),self.now+timedelta(seconds=1),None):
            row=dict(self.record,observed_at=instant.isoformat() if instant else None)
            self.assertEqual(self.evaluate({'database.quiescence':row})['gates']['database.quiescence']['status'],'BLOCKED')
    def test_forged_status_wrong_source_missing_digest_fail(self):
        for field,value in (('status','GREEN'),('source_sha','c'*40),('sha256','')):
            row=dict(self.record);row[field]=value
            self.assertEqual(self.evaluate({'security.controller':row})['gates']['security.controller']['status'],'FAIL')
    def test_unknown_gate_or_identity_refuses(self):
        with self.assertRaises(ValueError):self.evaluate({'arbitrary.exec':self.record})
        with self.assertRaises(ValueError):evaluate({},source_sha='branch',environment='production')

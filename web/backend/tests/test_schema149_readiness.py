import copy
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0,os.getenv('MADAR_TEST_REPOSITORY_ROOT') or str(Path(__file__).resolve().parents[2]))
from deployment.lib.schema149_readiness import evaluate,GATES


class ReadinessTests(unittest.TestCase):
    def test_missing_evidence_never_passes(self):
        result=evaluate('a'*40)
        self.assertEqual(result['assessment'],'NOT READY');self.assertFalse(result['production_authorized'])
        self.assertEqual(result['gates']['backup']['status'],'NOT TESTED')
        self.assertFalse(result['actions_performed'])
    def test_forged_all_pass_packet_cannot_clear_source_blockers(self):
        evidence={'version':1,'source_sha':'a'*40,'gates':{key:{'status':'PASS','evidence_sha256':'b'*64} for key in GATES}}
        result=evaluate('a'*40,evidence)
        self.assertEqual(result['gates']['deletion_ownership']['status'],'FAIL')
        self.assertEqual(result['gates']['production_authorization']['status'],'BLOCKED')
        self.assertEqual(result['assessment'],'NOT READY');self.assertFalse(result['production_authorized'])
    def test_unknown_different_source_malformed_or_sensitive_fields_reject(self):
        good={'version':1,'source_sha':'a'*40,'gates':{}}
        for value in ({**good,'source_sha':'c'*40},{**good,'version':True},{**good,'gates':{'unknown':{}}},
                      {**good,'gates':{'backup':{'status':'PASS','password':'secret'}}}):
            with self.subTest(keys=list(value)),self.assertRaises(ValueError):evaluate('a'*40,value)

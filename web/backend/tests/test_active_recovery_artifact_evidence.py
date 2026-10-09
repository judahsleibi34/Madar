"""Exact-source actual-execution binding regressions; no authorization evidence."""
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib import active_recovery_artifact_evidence as module

class ArtifactEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.plan=SimpleNamespace(acceptance_execution_sha256='a'*64,source_sha='b'*40,
            candidate_images={'backend':'sha256:'+'c'*64,'frontend':'sha256:'+'d'*64},
            checkpoint_manifest_sha256='e'*64,retained_inputs={'local_configuration':'f'*64})
        self.report={'operation':'actual-final-application-artifact-acceptance','source_sha':self.plan.source_sha,
            'images':self.plan.candidate_images,'checkpoint_manifest_sha256':'e'*64,'local_configuration_sha256':'f'*64,
            'schema':115,'production_modified':False,'migrations_executed':False,'private_fixture_only':True,
            'cases':{case:{'verified':True,'observations':{'synthetic_fixture':True}} for case in module.CASES},
            'node1_replica':{'host':'madar-node1-lan','filesystem_uuid':'1'*8+'-'+ '2'*4+'-'+ '3'*4+'-'+ '4'*4+'-'+ '5'*12,'configuration_sha256':'6'*64}}
        self.files={'web/scripts/verify_final_application_artifacts.py':hashlib.sha256(b'reviewed').hexdigest()}
        self.record={'source_files':self.files}
        class Index:
            def read_text(self):return json.dumps({'execution':str(module.PREPARATION/'artifact-acceptance/run-111111111111/execution.json')})
        for p in [patch.object(module,'protected',return_value=Index()),patch.object(module,'readonly_configuration',return_value=Path('/synthetic')),
            patch.object(module,'file_digest',return_value='6'*64),patch.object(module,'actual_inline_execution',return_value=(self.report,self.record)),
            patch('subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=b'reviewed'))]:
            p.start();self.addCleanup(p.stop)
    def test_exact_actual_execution_scope_accepted(self):self.assertEqual(module.verify_artifact_acceptance(self.plan),self.report)
    def test_agent_pass_claim_is_insufficient(self):
        self.report['cases']={case:'PASS' for case in module.CASES}
        with self.assertRaisesRegex(RuntimeError,'incomplete'):module.verify_artifact_acceptance(self.plan)
    def test_missing_mandatory_case_denied(self):
        self.report['cases'].pop('original_mfa_aal2')
        with self.assertRaises(RuntimeError):module.verify_artifact_acceptance(self.plan)
    def test_different_image_cannot_reuse_execution(self):
        self.report['images']={'backend':'sha256:'+'0'*64,'frontend':self.plan.candidate_images['frontend']}
        with self.assertRaises(RuntimeError):module.verify_artifact_acceptance(self.plan)
    def test_migrations_or_production_modification_denied(self):
        for key in ['migrations_executed','production_modified']:
            self.report[key]=True
            with self.subTest(key=key),self.assertRaises(RuntimeError):module.verify_artifact_acceptance(self.plan)
            self.report[key]=False
    def test_all_executed_source_files_must_match_final_revision(self):
        self.files['web/deployment/lib/fixture.py']=hashlib.sha256(b'older_source').hexdigest()
        with self.assertRaisesRegex(RuntimeError,'source_revision_changed'):module.verify_artifact_acceptance(self.plan)
    def test_changed_replica_configuration_denied(self):
        with patch.object(module,'file_digest',return_value='0'*64),self.assertRaisesRegex(RuntimeError,'replica_configuration_changed'):
            module.verify_artifact_acceptance(self.plan)

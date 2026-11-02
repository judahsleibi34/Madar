"""Source integrity of unselected167; no SQL or runtime authority is issued."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from test_bi_report_delivery_lifecycle_candidate import source_path

SPEC=importlib.util.spec_from_file_location('unadmitted_account_recovery',source_path('web/scripts/check_account_recovery_candidate.py'))
candidate=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(candidate)


class UnadmittedAccountCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.sql='web/database/migrations/167_add_account_recovery_hold.sql'
        self.mirror='web/supabase/migrations/167_add_account_recovery_hold.sql'
        self.manifest='web/deployment/releases/migrations-166-167-account-recovery.json'
        self.bridge='web/deployment/releases/schema-166-167-account-recovery-bridge.json'
        for name in (self.sql,self.mirror,self.manifest,self.bridge):
            target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source_path(name),target)
    def test_candidate_presence_preserves_blocked_admission_and_exact_checksum(self):
        row,=candidate.validated_entries(self.root)
        self.assertEqual((row['from_schema'],row['to_schema'],row['compatibility']),(166,167,'coordinated'))
        self.assertEqual(row['sha256'],candidate.SQL_SHA256)
        active=json.loads(source_path('web/deployment/releases/release.json').read_text())
        self.assertEqual(active['schema']['target'],146)
    def test_changed_or_self_rehashed_sql_cannot_rewrite_candidate_pin(self):
        body=(self.root/self.sql).read_bytes()+b'\n-- changed fixture\n'
        (self.root/self.sql).write_bytes(body);(self.root/self.mirror).write_bytes(body)
        import hashlib
        manifest=json.loads((self.root/self.manifest).read_text());manifest['migrations'][0]['sha256']=hashlib.sha256(body).hexdigest()
        (self.root/self.manifest).write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'checksum_invalid'):candidate.validated_entries(self.root)
    def test_mirror_drift_and_unblocked_execution_policy_refuse(self):
        original=(self.root/self.mirror).read_bytes();(self.root/self.mirror).write_bytes(b'wrong SQL')
        with self.assertRaisesRegex(ValueError,'mirror_invalid'):candidate.validated_entries(self.root)
        (self.root/self.mirror).write_bytes(original)
        bridge=json.loads((self.root/self.bridge).read_text());bridge['migration_policy']='automatic-after-known-good-backup-first-forward-repair'
        (self.root/self.bridge).write_text(json.dumps(bridge))
        with self.assertRaisesRegex(ValueError,'must_remain_blocked'):candidate.validated_entries(self.root)
    def test_wrong_predecessor_or_manifest_release_identity_refuses(self):
        path=self.root/self.manifest;original=json.loads(path.read_text())
        for key,value in (('from_schema',160),('number',168)):
            changed=json.loads(json.dumps(original));changed['migrations'][0][key]=value;path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError,'transition_invalid'):candidate.validated_entries(self.root)
        original['release_sha']='CURRENT';path.write_text(json.dumps(original))
        with self.assertRaisesRegex(ValueError,'manifest_invalid'):candidate.validated_entries(self.root)

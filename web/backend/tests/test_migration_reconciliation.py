"""Immutable published history and explicitly non-executable release contracts."""
import hashlib
import json
import os
from pathlib import Path
import sys
import shutil
import tempfile
import unittest

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
sys.path.insert(0,str(WEB/'scripts'))
from check_reconciled_history import validated_entries
from deployment.lib.migration_executor import MigrationManifest


class MigrationReconciliationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.web=self.root/'web'
        shutil.copytree(WEB/'deployment',self.web/'deployment')
        for tree in ('database','supabase'):
            source=WEB/tree if (WEB/tree).exists() else Path('/'+tree)
            shutil.copytree(source,self.web/tree)

    def test_published_main_and_archived_architecture_are_pinned(self):
        rows=validated_entries(self.root)
        self.assertEqual([r['number'] for r in rows],[157,158,159,160])
        for row in rows:
            old=self.web/'database/historical-architecture-146-150'/Path(row['path']).name.replace(str(row['number']),str(row['number']-10),1)
            self.assertEqual(hashlib.sha256(old.read_bytes()).hexdigest(),row['historical_source']['sha256'])
            self.assertEqual(row['historical_source']['number'],row['number']-10)

    def test_original_contracts_and_reconciled_contract_cannot_execute(self):
        for name in ('migrations-147-148-coordinated.json','migrations-147-149-coordinated.json',
                'migrations-147-150-coordinated.json','migrations-147-148-reservation-capacity.json',
                'migrations-157-160-reconciled.json'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'not executable'):
                MigrationManifest.load(WEB/'deployment/releases'/name,WEB.parent)

    def test_target_protocol_is_exact_and_active_selection_is_not_retargeted(self):
        sql=(self.web/'database/migrations/160_fence_data_deletion_ownership.sql').read_text()
        self.assertIn("contract_key = 'core')=160 then 2 else 0",sql)
        active=json.loads((WEB/'deployment/releases/release.json').read_bytes())
        self.assertEqual(active['schema']['target'],146)
        self.assertEqual(active['migration_manifest'],'migrations-145-146-commercial.json')

    def test_checksum_tamper_and_self_declared_approval_cannot_admit_new_history(self):
        rows=validated_entries(self.root)
        path=self.root/rows[-1]['path'];path.write_bytes(path.read_bytes()+b'\n-- substituted SQL\n')
        with self.assertRaisesRegex(ValueError,'forward_sql_changed'):validated_entries(self.root)
        path=self.web/'deployment/releases/migrations-157-160-reconciled.json'
        raw=json.loads(path.read_bytes());raw['execution_status']='approved'
        path.write_text(json.dumps(raw))
        with self.assertRaisesRegex(ValueError,'not executable'):MigrationManifest.load(path,self.root)

import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB))
from deployment.lib.migration_executor import MigrationManifest

spec = importlib.util.spec_from_file_location('notification_fencing_candidate',WEB/'scripts/notification_fencing_candidate.py')
candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)


class NotificationFencingReleaseContractTests(unittest.TestCase):
    def fixture(self, directory):
        root=Path(directory)
        for relative in ('deployment/releases/migrations-146-147-notification-fencing.json',
                         'deployment/releases/schema-146-147-notification-fencing.json',
                         'database/historical-architecture-146-150/147_fence_notification_delivery_claims.sql',
                         'supabase/historical-architecture-146-150/147_fence_notification_delivery_claims.sql'):
            source=WEB/relative
            if not source.exists():source=Path('/workspace')/relative
            target=root/'web'/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
        return root

    def test_exact_candidate_is_coordinated_and_never_selected_implicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            root=self.fixture(directory)
            entries=candidate.validated_entries(root)
            self.assertEqual([(v['from_schema'],v['to_schema'],v['compatibility']) for v in entries],[(146,147,'coordinated')])
        active=json.loads((WEB/'deployment/releases/release.json').read_text())
        self.assertEqual(active['schema']['target'],146)
        self.assertNotEqual(active['migration_manifest'],'migrations-146-147-notification-fencing.json')

    def test_automatic_executor_rejects_coordinated_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root=self.fixture(directory)
            manifest=root/'web/deployment/releases/migrations-146-147-notification-fencing.json'
            with self.assertRaisesRegex(ValueError,'not executable'):
                MigrationManifest.load(manifest,root)

    def test_sql_mirror_and_descriptor_tampering_rejected(self):
        for path in ('web/deployment/releases/migrations-146-147-notification-fencing.json',
                     'web/deployment/releases/schema-146-147-notification-fencing.json',
                     'web/database/historical-architecture-146-150/147_fence_notification_delivery_claims.sql',
                     'web/supabase/historical-architecture-146-150/147_fence_notification_delivery_claims.sql'):
            with self.subTest(path=path),tempfile.TemporaryDirectory() as directory:
                root=self.fixture(directory);target=root/path
                target.write_bytes(target.read_bytes()+b'\n')
                with self.assertRaises(ValueError):candidate.validated_entries(root)

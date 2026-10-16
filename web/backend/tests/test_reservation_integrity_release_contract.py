import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
spec=importlib.util.spec_from_file_location('reservation_integrity_candidate',WEB/'scripts/reservation_integrity_candidate.py')
candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)


class ReservationIntegrityReleaseContractTests(unittest.TestCase):
    def fixture(self,directory):
        root=Path(directory)
        for relative in ('deployment/releases/migrations-147-148-reservation-capacity.json',
                         'deployment/releases/schema-147-148-reservation-capacity.json',
                         'database/migrations/148_guard_reservation_reactivation_capacity.sql',
                         'supabase/migrations/148_guard_reservation_reactivation_capacity.sql'):
            source=WEB/relative
            if not source.exists():source=Path('/workspace')/relative
            target=root/'web'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        return root

    def test_exact_following_transition_is_unselected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=self.fixture(directory)
            entries=candidate.validated_entries(root)
            self.assertEqual([(v['from_schema'],v['to_schema']) for v in entries],[(147,148)])
            bridge=json.loads((root/'web/deployment/releases/schema-147-148-reservation-capacity.json').read_text())
            self.assertEqual(bridge['migration_policy'],'none')
        self.assertEqual(json.loads((WEB/'deployment/releases/release.json').read_text())['schema']['target'],146)

    def test_every_new_binding_is_checksum_protected(self):
        for relative in ('web/deployment/releases/migrations-147-148-reservation-capacity.json',
                         'web/deployment/releases/schema-147-148-reservation-capacity.json',
                         'web/database/migrations/148_guard_reservation_reactivation_capacity.sql',
                         'web/supabase/migrations/148_guard_reservation_reactivation_capacity.sql'):
            with self.subTest(path=relative),tempfile.TemporaryDirectory() as directory:
                root=self.fixture(directory);p=root/relative;p.write_bytes(p.read_bytes()+b'\n')
                with self.assertRaises(ValueError):candidate.validated_entries(root)

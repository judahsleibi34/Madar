"""Current forward release rejects immutable-lineage and namespace regressions."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
SCRIPT = WEB / 'scripts/check_forward_release.py'
spec = importlib.util.spec_from_file_location('forward_release_validation',SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ForwardReleaseLineageTests(unittest.TestCase):
    def fixture(self, root):
        web = root / 'web'
        shutil.copytree(WEB / 'deployment/releases',web / 'deployment/releases')
        for tree in ('database','supabase'):
            source = WEB / tree / 'migrations'
            if not source.is_dir():source = Path('/') / tree / 'migrations'
            shutil.copytree(source,web / tree / 'migrations')
        return root

    def test_canonical_production_based_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            self.assertEqual(module.validate(root),[])

    def test_immutable_production_history_cannot_be_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            path = root / 'web/database/migrations/098_create_site_visit_counters.sql'
            path.write_bytes(path.read_bytes()+b'\n-- altered historical migration\n')
            self.assertTrue(any('immutable production migration changed' in error for error in module.validate(root)))

    def test_namespace_and_order_reject_collision_or_future_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            path = root / 'web/database/migrations/102_unreviewed.sql'
            path.write_text('select 1;')
            self.assertTrue(any('namespace' in error for error in module.validate(root)))
            path.unlink()
            path = root / 'web/deployment/releases/migrations-100-101.json'
            manifest = json.loads(path.read_text());manifest['migrations'].reverse();path.write_text(json.dumps(manifest))
            self.assertTrue(any('ordered 100 then 101' in error for error in module.validate(root)))

    def test_bridge_must_serve_production_099_and_bound_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(Path(directory))
            path = root / 'web/deployment/releases/release.json'
            metadata = json.loads(path.read_text());metadata['schema']['compatible_min']=100;path.write_text(json.dumps(metadata))
            self.assertTrue(any('bridge production 099' in error for error in module.validate(root)))

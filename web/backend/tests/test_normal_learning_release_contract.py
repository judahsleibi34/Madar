"""Exact manual136→144 selection; no live SQL or release mutation."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

WEB = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB))
sys.path.insert(0, str(WEB / "backend"))
from deployment.lib import learning_migration_path as route
from deployment.lib.migration_executor import MigrationManifest
from deployment.lib.release_deployer import Compatibility
from services.runtime_config import schema_excluded_versions
from services import business_write_authority as authority
from services import provider_recovery


class NormalLearningReleaseContractTests(unittest.TestCase):
    def source(self, relative):
        for path in [WEB.parent/relative,WEB/relative.removeprefix('web/'),
                     Path('/app')/relative.removeprefix('web/')]:
            if path.is_file():return path
        raise FileNotFoundError(relative)

    def setUp(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root=self.copy_fixture(directory.name)

    def copy_fixture(self, directory):
        root = Path(directory)
        descriptor = json.loads(self.source(route.NORMAL_CONTRACT_PATH).read_text())
        files = [route.CONTRACT_PATH, route.NORMAL_CONTRACT_PATH, route.NORMAL_MANIFEST_PATH, route.NORMAL_BRIDGE_PATH]
        for item in descriptor["migrations"]:
            files.extend([item["path"],item["path"].replace("/database/","/supabase/")])
        for relative in files:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.source(relative), target)
        return root

    def test_exact_source_manifest_and_declared_branch(self):
        manifest = MigrationManifest.load(self.root / route.NORMAL_MANIFEST_PATH, self.root)
        self.assertEqual([m.number for m in manifest.migrations],[137,138,139,140,141,143,144])
        self.assertEqual(manifest.excluded_schemas,(142,))
        for version in [136,137,138,139,140,141,143,144]:
            self.assertTrue(manifest.accepts_schema(version))
        for version in [135,142,145]:
            self.assertFalse(manifest.accepts_schema(version))

    def test_matches_existing_reviewed_entries_without_rewriting_history(self):
        releases = WEB / 'deployment/releases'
        old = json.loads((releases/'migrations-115-141.json').read_text())['migrations']
        expected = [e for e in old if e['from_schema'] >= 136]
        expected += json.loads((releases/'migrations-141-143-learning.json').read_text())['migrations']
        expected += json.loads((releases/'migrations-143-144-forms.json').read_text())['migrations']
        actual = json.loads((self.root/route.NORMAL_MANIFEST_PATH).read_text())['migrations']
        self.assertEqual(actual,expected)
        self.assertEqual(json.loads((releases/'release.json').read_text())['schema']['target'],136)

    def test_no_arbitrary_path_can_borrow_branch_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_fixture(directory)
            wrong = root/'other.json'
            shutil.copyfile(root/route.NORMAL_MANIFEST_PATH,wrong)
            with self.assertRaises(ValueError):MigrationManifest.load(wrong,root)

    def test_mutated_manifest_descriptor_bridge_sql_or_mirror_rejected(self):
        contract = json.loads((self.root/route.NORMAL_CONTRACT_PATH).read_text())
        paths = [route.NORMAL_CONTRACT_PATH,route.NORMAL_MANIFEST_PATH,route.NORMAL_BRIDGE_PATH,
                 contract['migrations'][0]['path'],contract['migrations'][0]['path'].replace('/database/','/supabase/')]
        for relative in paths:
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as directory:
                root=self.copy_fixture(directory); path=root/relative
                path.write_bytes(path.read_bytes()+b'\n')
                with self.assertRaises(ValueError):MigrationManifest.load(root/route.NORMAL_MANIFEST_PATH,root)

    def test_missing_exclusion_wrong_schema_and_rollback_above136_rejected(self):
        path = self.root/route.NORMAL_BRIDGE_PATH
        compatibility = Compatibility.load(path)
        self.assertTrue(compatibility.accepts_schema(136))
        self.assertTrue(compatibility.accepts_schema(144))
        self.assertFalse(compatibility.accepts_schema(142))
        self.assertFalse(compatibility.accepts_schema(137,rollback=True))
        with tempfile.TemporaryDirectory() as directory:
            raw=json.loads(path.read_text());raw['schema'].pop('excluded_versions')
            altered=Path(directory)/'bridge.json';altered.write_text(json.dumps(raw))
            with self.assertRaises(ValueError):Compatibility.load(altered)
        with patch.dict(os.environ,{'SCHEMA_EXCLUDED_VERSIONS':'142'}):
            self.assertEqual(schema_excluded_versions(136,144),(142,))
            with self.assertRaises(ValueError):schema_excluded_versions(135,144)
        with patch.dict(os.environ,{'SCHEMA_EXCLUDED_VERSIONS':''}):
            with self.assertRaises(ValueError):schema_excluded_versions(136,144)

    def test_fresh_grant_fences_and_accepts_only_reviewed_native_branch(self):
        # Unit filesystem ownership double; real root mounts still need acceptance.
        path=self.root/'authority.json'
        grant={'version':2,'compatible_min':136,'compatible_max':144,'schema':136,
               'release_sha':'b'*40,'contract_digest':'a'*64,'mode':'READ_ONLY'}
        env={'MADAR_BUSINESS_WRITE_AUTHORITY':str(path),'MADAR_BUSINESS_WRITE_CONTRACT':'a'*64,
             'MADAR_RELEASE_SHA':'b'*40,'SCHEMA_COMPATIBLE_MIN':'136',
             'SCHEMA_COMPATIBLE_MAX':'144','SCHEMA_EXCLUDED_VERSIONS':'142',
             'SUPABASE_URL':'http://madar-supabase:8000',
             'MADAR_SUPABASE_CLIENT_NETWORK':'madar-supabase-client','MADAR_RECOVERY_PROFILE':''}
        with patch.dict(os.environ,env),patch.object(authority,'AUTHORITY_PATH',path), \
             patch.object(Path,'lstat',return_value=SimpleNamespace(st_uid=0,st_mode=0o100644)), \
             patch.object(Path,'is_symlink',return_value=False):
            for schema in [136,137,138,139,140,141,143,144]:
                grant.update(schema=schema,mode='READ_ONLY');path.write_text(json.dumps(grant))
                provider_recovery.validate_configuration()
                self.assertFalse(provider_recovery.worker_consumption_allowed())
                grant['mode']='NORMAL';path.write_text(json.dumps(grant))
                self.assertTrue(provider_recovery.worker_consumption_allowed())
            for key,value in [('schema',142),('schema',145),('schema',True),
                              ('compatible_min',135),('compatible_max',145),
                              ('release_sha','c'*40),('contract_digest','d'*64)]:
                altered=dict(grant);altered[key]=value;path.write_text(json.dumps(altered))
                with self.assertRaises(RuntimeError):authority.read_authority()
            path.write_text(json.dumps(grant))
            with patch.dict(os.environ,{'SCHEMA_EXCLUDED_VERSIONS':''}):
                with self.assertRaises(RuntimeError):authority.read_authority()
            legacy=dict(grant,compatible_min=115,compatible_max=136,schema=136)
            path.write_text(json.dumps(legacy))
            with self.assertRaises(RuntimeError):authority.read_authority()


if __name__ == '__main__': unittest.main()

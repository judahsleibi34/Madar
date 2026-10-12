"""Pinned manual STAGING placeholder binds to the authorized application."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
import test_completed_normal_compose as fixture
from test_completed_normal_manual_profile import manual_contract
from test_completed_normal_admission import fixture_contract
from deployment.lib.completed_normal_migration import bind_manifest
from deployment.lib.migration_executor import MigrationManifest


class StagingManifestTests(unittest.TestCase):
    def setUp(self):
        self.contract=manual_contract()
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.repository=Path(temp.name)
        relative=['web/deployment/releases/'+name for name in ('migrations-137-144-learning.json',
            'learning-136-144-path.json','schema-136-144-learning-bridge.json','migrations-116-136.json')]
        entries=json.loads((fixture.WEB/'deployment/releases/migrations-137-144-learning.json').read_text())['migrations']
        relative += [entry['path'] for entry in entries]+[entry['path'].replace('/database/','/supabase/') for entry in entries]
        for name in relative:
            source=fixture.WEB/name.removeprefix('web/')
            if not source.exists():source=Path('/app')/name.removeprefix('web/')
            target=self.repository/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
        self.manifest=MigrationManifest.load(self.repository/'web/deployment/releases/migrations-137-144-learning.json',self.repository)

    def test_actual_reviewed_manifest_binds_placeholder_without_changing_sql(self):
        self.assertEqual(self.manifest.release_sha,'STAGING')
        bound=bind_manifest(self.manifest,self.contract)
        self.assertEqual(bound.release_sha,self.contract['candidate']['source_sha'])
        self.assertEqual(bound.migrations,self.manifest.migrations)
        self.assertEqual([m.number for m in bound.migrations],[137,138,139,140,141,143,144])
        self.assertEqual(bound.excluded_schemas,(142,))

    def test_other_source_missing_migration_or_added142_rejected(self):
        for value in (replace(self.manifest,release_sha='f'*40),replace(self.manifest,migrations=self.manifest.migrations[:-1]),
                      replace(self.manifest,migrations=tuple(reversed(self.manifest.migrations)))):
            with self.subTest(value=value),self.assertRaisesRegex(RuntimeError,'migration_chain_invalid'):bind_manifest(value,self.contract)

    def test_legacy_profile_does_not_gain_manual_placeholder_authority(self):
        contract=fixture_contract()
        manifest=MigrationManifest.load(self.repository/'web/deployment/releases/migrations-116-136.json',self.repository)
        with self.assertRaisesRegex(RuntimeError,'migration_chain_invalid'):bind_manifest(replace(manifest,release_sha='STAGING'),contract)


if __name__=='__main__':unittest.main()

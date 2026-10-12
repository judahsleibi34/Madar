"""Pinned manual STAGING placeholder binds to the authorized application."""
from dataclasses import replace
import unittest
import test_completed_normal_compose as fixture
from test_completed_normal_manual_profile import manual_contract
from test_completed_normal_admission import fixture_contract
from deployment.lib.completed_normal_migration import bind_manifest
from deployment.lib.migration_executor import MigrationManifest


class StagingManifestTests(unittest.TestCase):
    def setUp(self):
        self.contract=manual_contract()
        self.manifest=MigrationManifest.load(fixture.WEB/'deployment/releases/migrations-137-144-learning.json',fixture.WEB.parent)

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
        manifest=MigrationManifest.load(fixture.WEB/'deployment/releases/migrations-116-136.json',fixture.WEB.parent)
        with self.assertRaisesRegex(RuntimeError,'migration_chain_invalid'):bind_manifest(replace(manifest,release_sha='STAGING'),contract)


if __name__=='__main__':unittest.main()

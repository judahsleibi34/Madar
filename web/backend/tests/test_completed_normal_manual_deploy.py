"""Real deployment entrypoint adapters; no production Docker mutations."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_completed_normal_compose as fixture
from test_completed_normal_manual_profile import manual_contract
from deployment.lib import completed_normal_admission as admission
from deployment.lib.completed_normal_execution import manual_maintenance_route


class ManualDeployTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.contract=manual_contract()
        self.ops=fixture.cli.DockerGitOperations(fixture.WEB.parent,Path(self.tmp.name),Path(self.tmp.name)/'environment',
            fixture.cli.Compatibility.load(fixture.WEB/'deployment/releases/schema-136-144-learning-bridge.json'),
            metadata_filename='schema-136-144-learning-bridge.json')
        self.ops.completed_normal_admission=self.contract
        self.ops.release_root=fixture.WEB.parent

    def test_origin_worker_names_are_protected_exact_ids_not_canonical_prefix(self):
        roles=('notification-worker','calendar-sync-worker','data-deletion-worker')
        witness={'source_sha':self.contract['source_roles']['application_sha'],
            'worker_generation':self.contract['origin']['worker_generation'],
            'context_sha256':Path(self.contract['source_roles']['completion_root']).name,
            'images':self.contract['origin']['images'],
            'runtimes':{k:{'id':str(i)*64} for i,k in enumerate(roles,1)}}
        with patch.object(admission,'credential_witness',return_value=witness):
            self.assertEqual(self.ops._worker_names(self.contract['origin']['slot']),[str(i)*64 for i in (1,2,3)])
        for changed in ({'source_sha':'f'*40},{'worker_generation':'f'*64},{'images':{}},{'runtimes':{}}):
            with patch.object(admission,'credential_witness',return_value=dict(witness,**changed)):
                with self.subTest(changed=changed),self.assertRaisesRegex(RuntimeError,'origin_worker_runtime_changed'):
                    self.ops._worker_names(self.contract['origin']['slot'])
        with patch.object(admission,'credential_witness',side_effect=RuntimeError('credential_witness_missing')):
            with self.assertRaises(RuntimeError):self.ops._worker_names(self.contract['origin']['slot'])

    def test_accepted_manual_tags_are_reused_without_build_or_retag(self):
        sha=self.contract['candidate']['source_sha'];tags=[]
        def existing(tag,*args,**kwargs):
            tags.append(tag)
            role='backend' if tag.startswith('madar-backend') else 'frontend'
            return tag+'@'+self.contract['candidate']['images'][role],'accepted-time'
        self.ops.verify_source=lambda sha:None;self.ops._existing_artifact=existing
        self.ops.run=lambda *args,**kwargs:self.fail('accepted artifact attempted a Docker mutation')
        with patch.dict(os.environ,{'VITE_API_URL':'/api','PUBLIC_SITE_DOMAIN':'madarportal.com','MADAR_COMPOSE_OVERRIDE':''}):
            result=self.ops.build(sha,self.contract['candidate']['slot'])
        self.assertEqual(tags,[f'madar-backend:{sha}',f'madar-frontend:{sha}'])
        self.assertTrue(result['artifact_reused'])
        self.ops._existing_artifact=lambda *args,**kwargs:None
        with patch.dict(os.environ,{'VITE_API_URL':'/api','PUBLIC_SITE_DOMAIN':'madarportal.com','MADAR_COMPOSE_OVERRIDE':''}):
            with self.assertRaisesRegex(RuntimeError,'accepted_artifact_changed'):self.ops.build(sha,self.contract['candidate']['slot'])

    def test_maintenance_allows_only_version_probes_and_blocks_mutations(self):
        text=manual_maintenance_route(self.contract).decode()
        self.assertEqual(text.count('location = '),2)
        self.assertIn('location / { return 503; }',text)
        self.assertIn('location = /health/version',text)
        self.assertIn('location = /api/health/version',text)
        self.assertNotIn('/auth/',text)
        self.assertNotIn('/builder/',text)

    def test_manual_migration_dispatch_uses_checksum_selected_bounds_and_exclusion(self):
        from deployment.lib import completed_normal_migration
        with patch.object(completed_normal_migration,'run_migration',return_value={'schema':144}) as run:
            self.ops.verify_source=lambda sha:None
            result=fixture.cli.automatic_migrate_known_good(sha=self.contract['candidate']['source_sha'],
                state_root=self.ops.state_root,compatibility=self.ops.compatibility,operations=self.ops)
            self.assertEqual(result,{'schema':144})
            run.assert_called_once_with(self.contract,self.ops.release_root,self.ops.state_root,self.ops)
        for bounds in ((115,136,136,()),(136,144,144,()),(136,144,143,(142,))):
            with patch.object(completed_normal_migration,'run_migration') as run:
                changed=copy.copy(self.ops.compatibility)
                for name,value in zip(('schema_min','schema_max','target_schema','excluded_schemas'),bounds):
                    object.__setattr__(changed,name,value)
                with self.subTest(bounds=bounds),self.assertRaisesRegex(RuntimeError,'release_binding_invalid'):
                    fixture.cli.automatic_migrate_known_good(sha=self.contract['candidate']['source_sha'],
                        state_root=self.ops.state_root,compatibility=changed,operations=self.ops)
                run.assert_not_called()


if __name__=='__main__':unittest.main()

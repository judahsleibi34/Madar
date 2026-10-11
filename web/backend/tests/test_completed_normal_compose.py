"""Check the actual release Compose builder, including optional Docker config.

Config renders create no Docker resources, attach no networks and read only a
synthetic environment file. These tests do not claim a deployment rehearsal.
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]).resolve()
loader = importlib.machinery.SourceFileLoader('completed_normal_compose_fixture',str(WEB/'deployment/bin/madar-release-deploy'))
spec = importlib.util.spec_from_loader(loader.name,loader)
cli = importlib.util.module_from_spec(spec);loader.exec_module(cli)
from deployment.lib import completed_normal_admission as admission
from test_completed_normal_admission import fixture_contract


class CompletedNormalComposeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.envfile = Path(self.temp.name)/'fixture.env'
        self.envfile.write_text('SUPABASE_URL=http://madar-supabase:8000\nSUPABASE_SERVICE_KEY=madar-ci-placeholder-service-not-a-secret\nSUPABASE_ANON_KEY=madar-ci-placeholder-anon-not-a-secret\n')
        self.contract = fixture_contract()
        self.images = {'backend':'backend@sha256:'+'5'*64,'frontend':'frontend@sha256:'+'6'*64,'worker':'backend@sha256:'+'5'*64,'build_timestamp':'2026-10-10T20:12:11Z'}
        self.ops = cli.DockerGitOperations(WEB.parent,Path(self.temp.name),self.envfile,cli.Compatibility(115,136,136,'forward-compatible',115,115))
        self.ops.release_root = WEB.parent;self.ops.schema_version = lambda:115
        self.ops.completed_normal_admission = self.contract
        for p in (patch.object(admission,'require_admission',return_value=self.contract),
                  patch.object(admission,'require_candidate_authority',return_value={'mode':'READ_ONLY'}),
                  patch.dict(os.environ,{'MADAR_STORAGE_ROOT':str(Path(self.temp.name)/'storage')})):
            p.start();self.addCleanup(p.stop)

    def test_actual_environment_always_carries_root_fence_for_candidate_and_workers(self):
        for active in (False,True):
            value = self.ops._environment('c'*40,'green',self.images,workers_active=active)
            self.assertEqual(value['MADAR_BUSINESS_WRITE_AUTHORITY'],'/run/madar/business-write-authority/authority.json')
            self.assertEqual(value['MADAR_BUSINESS_WRITE_CONTRACT'],admission.digest(self.contract))
            self.assertEqual(value['MADAR_BUSINESS_WRITE_AUTHORITY_ROOT'],str(admission.ADMISSIONS/admission.digest(self.contract)/'write-authority'))
            self.assertEqual(value['SCHEMA_COMPATIBLE_MAX'],'136')

    def test_changed_context_rejected_before_any_compose_command(self):
        with patch.object(admission,'require_admission',return_value={}):
            with self.assertRaisesRegex(RuntimeError,'admission_changed'):
                self.ops._environment('c'*40,'green',self.images)

    def test_bridge_uses_current_backup_state_mount_instead_of_legacy_provider_marker(self):
        previous='/var/lib/madar-control-plane/provider402/preparation-backup-verification.json'
        with patch.dict(os.environ,{'BACKUP_FRESHNESS_MARKER':previous,'BACKUP_FRESHNESS_REQUIRED':'true'}):
            value=self.ops._environment('c'*40,'green',self.images,workers_active=True)
            self.assertEqual(value['BACKUP_FRESHNESS_MARKER'],'/var/lib/madar/backup-state/latest.json')
            self.assertEqual(os.environ['BACKUP_FRESHNESS_MARKER'],previous)
            self.ops.completed_normal_admission=None
            ordinary=self.ops._environment('c'*40,'green',self.images)
            self.assertEqual(ordinary['BACKUP_FRESHNESS_MARKER'],previous)

    def test_modified_image_and_wrong_slot_fail_before_staging(self):
        changed = dict(self.images, backend='backend@sha256:'+'e'*64)
        with self.assertRaisesRegex(RuntimeError,'accepted_artifact_changed'):
            self.ops._environment('c'*40,'green',changed)
        with self.assertRaisesRegex(RuntimeError,'accepted_artifact_changed'):
            self.ops._environment('c'*40,'blue',self.images)

    def test_missing_or_modified_grant_rejected_before_staging(self):
        self.ops.run = lambda *args,**kw: self.fail('a command ran before the write fence was verified')
        with patch.object(admission,'require_candidate_authority',side_effect=RuntimeError('candidate_authority_changed')):
            with self.assertRaisesRegex(RuntimeError,'candidate_authority_changed'):
                self.ops.preflight('c'*40,'green',self.images,115)

    def test_preauthorization_render_uses_same_model_without_issuing_or_reading_a_grant(self):
        self.ops.read_only_model_contract=self.contract
        commands=[];self.ops.run=lambda args,**kw:commands.append(args)
        with (patch.object(admission,'require_admission',side_effect=AssertionError('no admission before approval')),
              patch.object(admission,'require_candidate_authority',side_effect=AssertionError('no grant before approval'))):
            self.ops._compose('c'*40,'green',self.images,'config','--format','json',workers_active=True)
        self.assertEqual(len(commands),1);self.assertEqual(commands[0][-3:],['config','--format','json'])

    def test_render_context_cannot_be_repurposed_for_resource_mutation(self):
        self.ops.read_only_model_contract=self.contract
        self.ops.run=lambda *args,**kw:self.fail('mutation reached Docker')
        for args in [('up','-d'),('create',),('down',),('exec','backend','sh'),('config','--quiet')]:
            with self.subTest(args=args),self.assertRaisesRegex(RuntimeError,'render_mutation_denied'):
                self.ops._compose('c'*40,'green',self.images,*args)

    def test_real_compose_merge_keeps_security_and_root_mount_on_all_business_roles(self):
        if not shutil.which('docker'):
            self.skipTest('Docker Compose unavailable; actual render runs separately on deployment host')
        version = subprocess.run(['docker','compose','version'],capture_output=True,text=True)
        if version.returncode:
            self.skipTest('Docker Compose unavailable; actual render runs separately on deployment host')
        captured = []
        def run(command,*,cwd=None,env=None,**kwargs):
            result = subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,'Docker Compose failed to render the synthetic configuration')
            captured.append(json.loads(result.stdout));return result.stdout
        self.ops.run = run
        self.ops._compose('c'*40,'green',self.images,'config','--format','json',workers_active=True)
        services = captured[0]['services']
        from deployment.lib.completed_normal_resources import allocation
        selected=allocation(self.contract,'green')
        for role in ('backend','frontend','parser-worker','remote-ingestion-worker','redis','notification-worker','calendar-sync-worker','data-deletion-worker'):
            self.assertEqual(services[role]['restart'],'no')
            self.assertEqual(services[role]['container_name'],selected['containers'][role])
        self.assertFalse(any(n['name'].startswith('madar-release-') for n in captured[0]['networks'].values() if not n.get('external')))
        for name in ('backend','notification-worker','calendar-sync-worker','data-deletion-worker'):
            with self.subTest(name=name):
                role = services[name]
                mounts = [v for v in role['volumes'] if v['target']=='/run/madar/business-write-authority']
                self.assertEqual(len(mounts),1)
                self.assertTrue(mounts[0]['read_only'])
                self.assertFalse(mounts[0]['bind']['create_host_path'])
                self.assertEqual(role['environment']['MADAR_BUSINESS_WRITE_CONTRACT'],admission.digest(self.contract))
                self.assertEqual(str(role['environment']['SCHEMA_COMPATIBLE_MAX']),'136')
                self.assertTrue(role['read_only'])
                self.assertIn('ALL',role['cap_drop'])
                self.assertEqual(role['restart'],'no')
                self.assertTrue(any(s.startswith('no-new-privileges') for s in role['security_opt']))
        marker=services['backend']['environment']['BACKUP_FRESHNESS_MARKER']
        self.assertEqual(marker,'/var/lib/madar/backup-state/latest.json')
        mounts=services['backend']['volumes']
        self.assertTrue(any(v['source']=='/var/lib/madar/backup-state'
            and v['target']=='/var/lib/madar/backup-state' and v['read_only'] for v in mounts))
        self.assertFalse(any(v.get('target')=='/run/madar/business-write-authority' for v in services['parser-worker']['volumes']))


if __name__=='__main__':unittest.main()

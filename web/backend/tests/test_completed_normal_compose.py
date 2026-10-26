"""Check the actual release Compose builder, including optional Docker config.

Config renders create no Docker resources, attach no networks and read only a
synthetic environment file. These tests do not claim a deployment rehearsal.
"""
import importlib.machinery
import importlib.util
import hashlib
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

    def test_real_compose_passes_private_calendar_transport_only_to_backend(self):
        if not shutil.which('docker'):self.skipTest('Docker Compose render exercised on development host')
        version=subprocess.run(['docker','compose','version'],capture_output=True,text=True)
        if version.returncode:self.skipTest('Docker Compose unavailable')
        self.ops.completed_normal_admission=None
        dsn='postgresql://authenticator:synthetic_calendar_password@synthetic-db:5432/postgres'
        with self.envfile.open('a') as stream:
            stream.write('CALENDAR_FEATURE_ENABLED=true\nMADAR_CALENDAR_DATABASE_DSN='+dsn+
                '\nMADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER=123456789\n')
        captured=[]
        def run(command,*,cwd=None,env=None,**kwargs):
            result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,'Synthetic Compose configuration failed')
            captured.append(json.loads(result.stdout));return result.stdout
        self.ops.run=run
        self.ops._compose('c'*40,'green',self.images,'config','--format','json',workers_active=True)
        services=captured[0]['services'];backend=services['backend']['environment']
        self.assertEqual(str(backend['CALENDAR_FEATURE_ENABLED']).lower(),'true')
        self.assertEqual(backend.get('MADAR_CALENDAR_DATABASE_DSN'),dsn)
        self.assertEqual(str(backend.get('MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER')),'123456789')
        for role,service in services.items():
            if role=='backend':continue
            self.assertFalse(service.get('environment',{}).get('MADAR_CALENDAR_DATABASE_DSN'))
            self.assertFalse(service.get('environment',{}).get('MADAR_CALENDAR_DATABASE_SYSTEM_IDENTIFIER'))


    def selected_144_environment(self):
        from deployment.lib import learning_migration_path as route
        descriptor=WEB/route.NORMAL_CONTRACT_PATH.removeprefix('web/')
        self.assertEqual(hashlib.sha256(descriptor.read_bytes()).hexdigest(),route.NORMAL_CONTRACT_SHA256)
        contract=json.loads(descriptor.read_text())
        path=WEB/route.NORMAL_BRIDGE_PATH.removeprefix('web/')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),contract['bridge_sha256'])
        manifest=WEB/route.NORMAL_MANIFEST_PATH.removeprefix('web/')
        self.assertEqual(hashlib.sha256(manifest.read_bytes()).hexdigest(),contract['manifest_sha256'])
        self.assertEqual([item['number'] for item in json.loads(manifest.read_text())['migrations']],
                         [137,138,139,140,141,143,144])
        self.ops.compatibility=cli.Compatibility.load(path)
        self.ops.completed_normal_admission=None
        stale={'SCHEMA_COMPATIBLE_MIN':'115','SCHEMA_COMPATIBLE_MAX':'136',
               'SCHEMA_EXCLUDED_VERSIONS':''}
        with patch.dict(os.environ,stale):
            return self.ops._environment('c'*40,'blue',self.images)

    def test_actual_environment_uses_selected_144_contract_not_stale_values(self):
        environment=self.selected_144_environment()
        self.assertEqual(environment['SCHEMA_COMPATIBLE_MIN'],'136')
        self.assertEqual(environment['SCHEMA_COMPATIBLE_MAX'],'144')
        self.assertEqual(environment['SCHEMA_EXCLUDED_VERSIONS'],'142')

    def test_historical_admission_cannot_authorize_selected_144_contract(self):
        self.ops.compatibility=cli.Compatibility.load(WEB/'deployment/releases/schema-136-144-learning-bridge.json')
        self.ops.run=lambda *args,**kwargs:self.fail('Docker reached with incompatible historical admission')
        with self.assertRaisesRegex(RuntimeError,'completed_normal_compatibility_changed'):
            self.ops._compose('c'*40,'green',self.images,'config','--format','json')

    def test_real_compose_preserves_selected_144_contract_despite_stale_env_file(self):
        if not shutil.which('docker'):
            self.skipTest('Docker Compose unavailable; source render exercised on deployment host')
        version = subprocess.run(['docker','compose','version'],capture_output=True,text=True)
        if version.returncode:
            self.skipTest('Docker Compose unavailable; actual render runs separately on deployment host')
        environment=self.selected_144_environment()
        # Render-only allocation and authority identifiers. This does not issue
        # a grant, change admission, or make the missing144 handoff executable.
        environment.update({
            'MADAR_BUSINESS_WRITE_CONTRACT':'a'*64,
            'MADAR_BUSINESS_WRITE_AUTHORITY_ROOT':str(Path(self.temp.name)/'authority'),
            'MADAR_CONTAINER_PREFIX':'fixture-schema144',
            'MADAR_REDIS_IMAGE':'redis@sha256:'+'7'*64,
            'MADAR_ALLOCATION_DEFAULT_NETWORK':'fixture-schema144-default',
            'MADAR_ALLOCATION_PARSER_NETWORK':'fixture-schema144-parser',
            'MADAR_ALLOCATION_REMOTE_INTERNAL_NETWORK':'fixture-schema144-remote-internal',
            'MADAR_ALLOCATION_REMOTE_EGRESS_NETWORK':'fixture-schema144-remote-egress',
        })
        with self.envfile.open('a') as stream:
            stream.write('SCHEMA_COMPATIBLE_MIN=115\nSCHEMA_COMPATIBLE_MAX=136\nSCHEMA_EXCLUDED_VERSIONS=\n')
        command=['docker','compose','--project-name','fixture-schema144','--env-file',str(self.envfile),
                 '-f',str(WEB/'docker-compose.yml'),
                 '-f',str(WEB/'deployment/docker-compose.release.yml'),
                 '-f',str(WEB/'deployment/docker-compose.write-authority.yml'),
                 '--profile','workers','--profile','deletion-worker','config','--format','json']
        result=subprocess.run(command,cwd=WEB,env=environment,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,'Private Compose configuration failed')
        services=json.loads(result.stdout)['services']
        for name in ('backend','notification-worker','calendar-sync-worker','data-deletion-worker'):
            role=services[name]
            self.assertEqual(str(role['environment']['SCHEMA_COMPATIBLE_MIN']),'136')
            self.assertEqual(str(role['environment']['SCHEMA_COMPATIBLE_MAX']),'144')
            self.assertEqual(str(role['environment']['SCHEMA_EXCLUDED_VERSIONS']),'142')
            self.assertEqual(role['environment']['MADAR_BUSINESS_WRITE_CONTRACT'],'a'*64)
            mounts=[v for v in role['volumes'] if v['target']=='/run/madar/business-write-authority']
            self.assertEqual(len(mounts),1)
            self.assertTrue(mounts[0]['read_only'])
            self.assertFalse(mounts[0]['bind']['create_host_path'])
            self.assertTrue(role['read_only']);self.assertIn('ALL',role['cap_drop'])
            self.assertEqual(role['restart'],'no')

    def test_real_compose_rejects_missing_explicit_authority_bounds(self):
        if not shutil.which('docker'):
            self.skipTest('Docker Compose unavailable; actual render runs separately on deployment host')
        version = subprocess.run(['docker','compose','version'],capture_output=True,text=True)
        if version.returncode:
            self.skipTest('Docker Compose unavailable; actual render runs separately on deployment host')
        original=self.ops._environment
        for missing in ('SCHEMA_COMPATIBLE_MIN','SCHEMA_COMPATIBLE_MAX'):
            with self.subTest(missing=missing):
                def environment(*args,**kwargs):
                    value=original(*args,**kwargs)
                    value.pop(missing)
                    return value
                def run(command,*,cwd=None,env=None,**kwargs):
                    result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,timeout=30)
                    self.assertNotEqual(result.returncode,0)
                    self.assertIn(missing,result.stderr)
                    return result.stdout
                self.ops._environment=environment;self.ops.run=run
                self.ops._compose('c'*40,'green',self.images,'config','--format','json',workers_active=True)


if __name__=='__main__':unittest.main()

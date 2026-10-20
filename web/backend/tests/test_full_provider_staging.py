"""Read-only/MODEL transport and real filesystem exclusions, not provider PASS."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB/'staging/integration'));sys.path.insert(0,str(WEB/'scripts'))
import full_provider_staging as staging
import fetch_full_provider_artifacts as fetch
from test_schema150_restore_configuration import valid_plan,IMAGES,SHA,PROJECT,OWNER


class FullStagingSafetyTests(unittest.TestCase):
    def test_mutable_source_and_production_host_refuse_before_any_effect(self):
        for source in ('main','../../escape','a'*39,True):
            with self.assertRaises(RuntimeError):staging.identity(source)
        environment={'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','GITHUB_REPOSITORY':'judahsleibi34/Madar'}
        with patch.dict(os.environ,environment),patch.object(staging.socket,'gethostname',return_value='madar-gpu'),patch.object(staging,'source_plan') as plan:
            with self.assertRaisesRegex(RuntimeError,'isolated_host_required'):
                staging.main('REHEARSE',Path.home()/'unused',SHA,'b'*40)
            plan.assert_not_called()

    def test_unknown_host_or_outside_home_refuses(self):
        with patch.dict(os.environ,{},clear=True),patch.object(staging.socket,'gethostname',return_value='unknown'):
            with self.assertRaises(RuntimeError):staging.require_host(Path.home()/staging.identity(SHA))
        with patch.object(staging.socket,'gethostname',return_value='madar-staging'):
            with self.assertRaises(RuntimeError):staging.require_host(Path('/tmp')/staging.identity(SHA))

    def test_target_context_restores_existing_global_bindings_after_failure(self):
        keys=('PROJECT','OWNER','MARKER','RUNTIME','HERE','require_staging_host','compose')
        before={key:getattr(staging.manage,key) for key in keys};urls=(staging.smoke.PROVIDER,staging.smoke.APPLICATION)
        with patch.object(staging,'require_host'):
            with self.assertRaisesRegex(RuntimeError,'injected'):
                with staging.target(SHA,153):
                    self.assertEqual(staging.manage.PROJECT,staging.identity(SHA))
                    self.assertEqual(staging.smoke.PROVIDER,'http://127.0.0.1:22081')
                    raise RuntimeError('injected')
        self.assertEqual({key:getattr(staging.manage,key) for key in keys},before)
        self.assertEqual((staging.smoke.PROVIDER,staging.smoke.APPLICATION),urls)

    def test_cross_source_staging_lock_is_exclusive_and_releases(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(Path,'home',return_value=Path(directory)):
            with staging.lease():
                with self.assertRaisesRegex(RuntimeError,'staging_busy'):
                    with staging.lease():self.fail('concurrent staging')
            with staging.lease():pass
            path=Path(directory)/'.madar-full-provider-staging.lock';path.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError,'lock_untrusted'):
                with staging.lease():self.fail('shared lock')

    def test_symlink_lock_refuses_without_opening_target_for_mutation(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(Path,'home',return_value=Path(directory)):
            root=Path(directory);original=root/'other';original.write_text('preserve')
            (root/'.madar-full-provider-staging.lock').symlink_to(original)
            with self.assertRaises(OSError):
                with staging.lease():self.fail('symlink lock')
            self.assertEqual(original.read_text(),'preserve')

    def test_consumed_attempt_and_insufficient_resources_refuse_before_docker(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'attempt';root.mkdir()
            with patch.object(staging.manage,'docker') as docker:
                with self.assertRaisesRegex(RuntimeError,'attempt_consumed'):staging.admission_headroom(root,'owned')
                docker.assert_not_called()
            root.rmdir()
            with patch.object(staging.shutil,'disk_usage',return_value=SimpleNamespace(free=1)),patch.object(staging.manage,'docker') as docker:
                with self.assertRaisesRegex(RuntimeError,'disk_headroom'):staging.admission_headroom(root,'owned')
                docker.assert_not_called()
            with patch.object(staging.shutil,'disk_usage',return_value=SimpleNamespace(free=10*1024**3)),patch.object(Path,'read_text',return_value='MemAvailable: 1024 kB'),patch.object(staging.manage,'docker') as docker:
                with self.assertRaisesRegex(RuntimeError,'memory_headroom'):staging.admission_headroom(root,'owned')
                docker.assert_not_called()

    def test_future_protocol_refusal_never_starts_or_fakes_a_worker(self):
        for schema,result in ((151,'151:2:2:0'),(150,'149:2:2:2'),(152,'152:2:1:2')):
            with patch.object(staging.manage,'sql',return_value=result),patch.object(staging.manage,'docker') as docker:
                with self.assertRaisesRegex(RuntimeError,'worker_protocol_mismatch'):staging.require_protocols(schema)
                docker.assert_not_called()
        with patch.object(staging.manage,'sql',return_value='150:2:2:2'):staging.require_protocols(150)

    def test_unknown_actor_or_unbounded_restart_policy_blocks(self):
        row={'Config':{'Labels':{'com.docker.compose.service':'unexpected','com.madar.staging.owner':'owned'}}}
        with patch.object(staging.manage,'attest_resources'),patch.object(staging.manage,'OWNER','owned'),patch.object(staging.manage,'docker',side_effect=[b'fixture',json.dumps([row]).encode()]) as docker:
            with self.assertRaisesRegex(RuntimeError,'unknown_actor'):staging.actors(IMAGES,complete=False)
            self.assertTrue(all('stop' not in c.args for c in docker.call_args_list))

    def test_future_schema_is_data_in_retained_configuration_validator(self):
        root=Path('/private/owned');plan=valid_plan(root)
        for name in ('backend','notification-worker','deletion-worker'):
            plan['services'][name]['environment'].update(SCHEMA_COMPATIBLE_MIN='153',SCHEMA_COMPATIBLE_MAX='153')
        staging.configuration.validate(plan,root,SHA,IMAGES,PROJECT,OWNER,target_schema=153)
        with self.assertRaises(RuntimeError):staging.configuration.validate(plan,root,SHA,IMAGES,PROJECT,OWNER)
        for target in (True,0,10**9):
            with self.assertRaises(RuntimeError):staging.configuration.validate(plan,root,SHA,IMAGES,PROJECT,OWNER,target_schema=target)

    def test_destructive_plan_cannot_enter_lease_or_prepare(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(Path,'home',return_value=Path(directory)):
            home=Path(directory);artifacts=home/'artifacts';artifacts.mkdir(mode=0o700)
            for name,value in {'artifact.json':{},'run.json':{},'receipt.json':{'images':IMAGES},'backend-check.yml.json':{},'frontend-check.yml.json':{}}.items():
                (artifacts/name).write_text(json.dumps(value))
            plan=SimpleNamespace(document=lambda:{'target_schema':153,'risk_class':'D'},sha256='a'*64)
            with patch.object(staging,'require_host'),patch.object(staging,'source_plan',return_value=(None,plan)),patch.object(staging,'verify_required_ci'),patch.object(staging,'lease') as lease,patch.object(staging.configuration,'generate') as generate:
                with self.assertRaisesRegex(RuntimeError,'exceptional_sql_requires_separate_review'):
                    staging.main('REHEARSE',artifacts,SHA,'b'*40)
                lease.assert_not_called();generate.assert_not_called()


class CandidateFetchTests(unittest.TestCase):
    def row(self,**changes):
        value={'id':10,'head_sha':SHA,'path':'.github/workflows/backend-check.yml','status':'completed','conclusion':'success',
            'repository':{'full_name':'judahsleibi34/Madar'},'head_repository':{'full_name':'judahsleibi34/Madar'}}
        value.update(changes);return value

    def test_latest_failed_or_incomplete_ci_cannot_reuse_older_success(self):
        path='.github/workflows/backend-check.yml';good=self.row()
        self.assertEqual(fetch.select_run({'workflow_runs':[good]},SHA,path),good)
        self.assertIsNone(fetch.select_run({'workflow_runs':[good,self.row(id=11,status='in_progress')]},SHA,path))
        with self.assertRaisesRegex(RuntimeError,'ci_failed'):
            fetch.select_run({'workflow_runs':[good,self.row(id=11,conclusion='failure')]},SHA,path)

    def test_wrong_source_repository_workflow_and_id_refuse(self):
        for change in ({'head_sha':'b'*40},{'path':'untrusted'},{'repository':{'full_name':'foreign/repo'}},
                {'head_repository':{'full_name':'foreign/repo'}},{'id':True}):
            with self.subTest(change=change),self.assertRaises(RuntimeError):
                fetch.select_run({'workflow_runs':[self.row(**change)]},SHA,'.github/workflows/backend-check.yml')

    def test_fetch_cannot_target_unknown_directory_or_mutable_source(self):
        with patch.object(fetch,'api') as api:
            for source,directory in (('main',Path.home()/'unknown'),(SHA,Path('/tmp')/'unknown')):
                with self.assertRaises(RuntimeError):fetch.fetch(source,directory)
            api.assert_not_called()

"""PhaseVII fresh acceptance isolation; no containers, provider or SQL effects."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

WEB = Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB/'staging/integration'))
import phase7_schema150_acceptance as rehearsal
from test_schema150_restore_configuration import valid_plan, PROJECT as OLD_PROJECT, OWNER as OLD_OWNER, IMAGES, SHA

STAMP = '2026-10-18T00:00:00Z'


def plan(runtime, *, translated=True):
    value = json.dumps(valid_plan(runtime)).replace(OLD_PROJECT,rehearsal.PROJECT).replace(OLD_OWNER,rehearsal.OWNER)
    if translated:
        for current,reference in rehearsal.REFERENCE_PORTS.items(): value=value.replace(reference,current)
    result=json.loads(value)
    for name in ('backend','notification-worker','deletion-worker'):
        result['services'][name]['environment']['FRONTEND_URLS']='http://127.0.0.1:23080,https://127.0.0.1:23443' if translated else 'http://127.0.0.1:22080,https://127.0.0.1:22443'
    return result


class Phase7AcceptanceSafetyTests(unittest.TestCase):
    def snapshot(self):
        return (rehearsal.manage.PROJECT,rehearsal.manage.OWNER,rehearsal.manage.MARKER,
            rehearsal.manage.RUNTIME,rehearsal.manage.HERE,rehearsal.manage.compose,
            rehearsal.acceptance.PROJECT,rehearsal.acceptance.OWNER,rehearsal.acceptance.MARKER,
            rehearsal.acceptance.PORTS,rehearsal.acceptance.target,rehearsal.acceptance.prepare,
            rehearsal.smoke.PROVIDER,rehearsal.smoke.APPLICATION,
            rehearsal.previous.PROJECT,rehearsal.previous.OWNER,rehearsal.previous.MARKER,rehearsal.previous.PORTS)

    def test_invalid_mode_or_mutable_sha_refuses_before_access(self):
        with patch.object(rehearsal.manage,'require_staging_host') as host,patch.object(rehearsal,'require_source') as source:
            for mode,sha in (('EXECUTE',SHA),('REHEARSE','main')):
                with self.assertRaises(RuntimeError): rehearsal.main(mode,Path.home()/'private',sha)
            host.assert_not_called();source.assert_not_called()

    def test_primary_host_refuses_before_source_artifacts_or_docker(self):
        with patch.object(rehearsal.manage.socket,'gethostname',return_value='madar-gpu'),patch.object(rehearsal,'require_source') as source,patch.object(rehearsal.previous,'artifacts') as artifact,patch.object(rehearsal.manage,'docker') as docker:
            with self.assertRaises(RuntimeError): rehearsal.main('REHEARSE',Path.home()/'private',SHA)
            for value in (source,artifact,docker):value.assert_not_called()

    def test_inspect_uses_only_phase7_endpoints_and_restores_all_nested_globals(self):
        original=self.snapshot()
        def captured(_root):
            self.assertEqual(rehearsal.manage.PROJECT,rehearsal.PROJECT)
            self.assertEqual(rehearsal.smoke.PROVIDER,'http://127.0.0.1:23081')
            self.assertEqual(rehearsal.smoke.APPLICATION,'http://127.0.0.1:23080/api')
            self.assertEqual(rehearsal.previous.PROJECT,original[-4])
            return {},{number:b'synthetic immutable SQL' for number in (147,148,149,150)}
        with patch.object(rehearsal.manage,'require_staging_host'),patch.object(rehearsal,'require_source'),patch.object(rehearsal.acceptance,'captured_source',side_effect=captured),patch.object(rehearsal.previous,'artifacts',return_value=({}, {}, IMAGES, {})),patch.object(rehearsal,'prepare') as prepare,patch.object(rehearsal.manage,'docker') as docker:
            result=rehearsal.main('INSPECT',Path.home()/'private',SHA)
            self.assertFalse(result['mutations_executed']);self.assertEqual(result['ports'],rehearsal.PORTS)
            self.assertEqual(result['project'],rehearsal.PROJECT)
            prepare.assert_not_called();docker.assert_not_called()
        self.assertEqual(self.snapshot(),original)

    def test_interrupted_nested_scope_restores_all_globals(self):
        original=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'interrupt'):
            with rehearsal.namespace(Path.home()/rehearsal.PROJECT):
                with rehearsal.target(Path.home()/rehearsal.PROJECT):raise RuntimeError('interrupt')
        self.assertEqual(self.snapshot(),original)

    def test_namespace_and_existing_target_refuse_legacy_projects(self):
        with self.assertRaises(RuntimeError):
            with rehearsal.namespace(Path.home()/'madar-schema150-phase6-20261018'):pass
        with tempfile.TemporaryDirectory() as directory,patch.object(Path,'home',return_value=Path(directory)),patch.object(rehearsal.manage,'docker') as docker:
            root=Path(directory)/rehearsal.PROJECT;root.mkdir()
            with self.assertRaisesRegex(RuntimeError,'existing_or_ambiguous'):
                rehearsal.prepare(root,Path('/unused'),SHA,IMAGES,{}, {})
            docker.assert_not_called()

    def test_clean_exact_source_is_required_without_inheriting_git_environment(self):
        for output in ((b'b'*40+b'\n',b''),(SHA.encode()+b'\n',b' M modified\n')):
            with patch.object(rehearsal.subprocess,'run',side_effect=[SimpleNamespace(returncode=0,stdout=value) for value in output]) as command:
                with self.assertRaises(RuntimeError):rehearsal.require_source(SHA)
                self.assertNotIn('GIT_DIR',command.call_args.kwargs['env'])

    def test_port_conflict_is_read_only_and_fails_closed(self):
        header='sl local_address rem_address st\n'
        line='0: 0100007F:'+format(23080,'04X')+' 00000000:0000 0A\n'
        with patch.object(Path,'read_text',return_value=header+line),patch.object(rehearsal.manage,'docker') as docker:
            with self.assertRaisesRegex(RuntimeError,'port_already_owned'):rehearsal.require_ports_free()
            docker.assert_not_called()

    def test_existing_project_resources_reject_before_any_create_or_start(self):
        for result in ((b'existing-container',),(b'',b'existing-network'),(b'',b'',b'existing-volume')):
            with self.subTest(result=result),patch.object(rehearsal.manage,'docker',side_effect=result) as docker:
                with self.assertRaisesRegex(RuntimeError,'existing_project_resources'):rehearsal.require_resources_absent()
                self.assertTrue(all('create' not in call.args and 'start' not in call.args for call in docker.call_args_list))

    def test_phase7_plan_keeps_strict_retained_validator_and_does_not_mutate_input(self):
        runtime=Path('/private/phase7');value=plan(runtime);before=copy.deepcopy(value)
        rehearsal.validate_plan(value,runtime,SHA,IMAGES,STAMP)
        self.assertEqual(value,before)
        for mutate in (lambda p:p['services']['gateway']['ports'][0].update(published='21081'),
                       lambda p:p['services']['frontend']['ports'][0].update(host_ip='0.0.0.0'),
                       lambda p:p['volumes']['database'].update(name='madar-schema150-phase6-20261018_database'),
                       lambda p:p['services']['backend']['environment'].update(SUPABASE_URL='https://foreign.invalid'),
                       lambda p:p['services']['auth']['environment'].update(GOTRUE_SITE_URL='http://127.0.0.1:22080'),
                       lambda p:p['services']['backend'].update(privileged=True)):
            changed=copy.deepcopy(value);mutate(changed)
            with self.assertRaises(RuntimeError):rehearsal.validate_plan(changed,runtime,SHA,IMAGES,STAMP)

    def test_compose_consumes_verified_bytes_and_refuses_scope_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime=Path(directory);body=json.dumps(plan(runtime)).encode()
            (runtime/'verified-compose.json').write_bytes(body)
            (runtime/'configuration-receipt.json').write_text(json.dumps({'source_sha':SHA,'images':IMAGES,'sha256':hashlib.sha256(body).hexdigest(),'build_timestamp':STAMP}))
            with patch.object(rehearsal.manage,'RUNTIME',runtime),patch.object(rehearsal.manage,'state'),patch.object(rehearsal.manage,'docker',return_value=b'observed') as docker:
                self.assertEqual(rehearsal.compose('--file',str(runtime/'acceptance-compose.json'),'ps','-q','postgres'),b'observed')
                self.assertEqual(docker.call_args.args,('compose','--project-name',rehearsal.PROJECT,'--file','-','ps','-q','postgres'))
                self.assertEqual(docker.call_args.kwargs['data'],body)
                docker.reset_mock()
                for override in ('--file=/foreign','-f/foreign','--project-name=foreign','-pforeign','--env-file=/foreign','--profile=foreign'):
                    with self.assertRaises(RuntimeError):rehearsal.compose(override,'up')
                docker.assert_not_called()
                (runtime/'verified-compose.json').write_bytes(body+b' ')
                with self.assertRaisesRegex(RuntimeError,'configuration_changed'):rehearsal.compose('up')
                docker.assert_not_called()

    def test_archive_origin_retains_only_hex_credentials_not_mutable_application_config(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(Path,'home',return_value=Path(directory)):
            root=Path(directory)/rehearsal.previous.SOURCE_PROJECT;root.mkdir(mode=0o700)
            (root/'owner.json').write_text(json.dumps({'project':rehearsal.previous.SOURCE_PROJECT,'owner':'architecture-hardening-20261016','marker':'madar-hardening-synthetic-148-independent'}))
            buffer=io.BytesIO()
            with tarfile.open(fileobj=buffer,mode='w'):pass
            captured={'roles.sql':b'synthetic roles','database.dump':b'synthetic dump','objects.tar':buffer.getvalue()}
            for name,value in captured.items():(root/name).write_bytes(value)
            (root/'capture-checkpoint.json').write_text(json.dumps({'archive_sha256':{name:hashlib.sha256(value).hexdigest() for name,value in captured.items()}}))
            (root/'compose.env').write_text('DATABASE_PASSWORD='+'a'*64+'\nJWT_SECRET='+'b'*64+'\nMALICIOUS_PROVIDER_URL=https://foreign.invalid\n')
            (root/'application.env').symlink_to('/nonexistent/never-read')
            (root/'compose.yaml').write_text('privileged: true')
            observed,_,credentials=rehearsal.archive_origin()
            self.assertEqual(observed,captured);self.assertEqual(credentials,{'DATABASE_PASSWORD':'a'*64,'JWT_SECRET':'b'*64})
            (root/'database.dump').write_bytes(b'tampered')
            with self.assertRaisesRegex(RuntimeError,'digest mismatch'):rehearsal.archive_origin()

    def test_preparation_translates_only_new_generated_target_and_captures_actual230_ports(self):
        _,snapshots=rehearsal.acceptance.captured_source(rehearsal.manage.REPOSITORY)
        captured={'database.dump':b'synthetic dump','roles.sql':b'synthetic roles','objects.tar':b'synthetic objects'}
        credentials={'DATABASE_PASSWORD':'a'*64,'JWT_SECRET':'b'*64}
        with tempfile.TemporaryDirectory() as directory,patch.object(Path,'home',return_value=Path(directory)):
            runtime=Path(directory)/rehearsal.PROJECT
            def generate(*args):
                runtime.mkdir(mode=0o700)
                (runtime/'verified-compose.json').write_text(json.dumps(plan(runtime,translated=False)))
                (runtime/'application.env').write_text('MADAR_RELEASE_SHA='+SHA+'\nFRONTEND_URLS=http://127.0.0.1:22080,https://127.0.0.1:22443\n')
            original_read=Path.read_text
            def read(path,*args,**kwargs):
                return 'MemAvailable: 3000000 kB\n' if str(path)=='/proc/meminfo' else original_read(path,*args,**kwargs)
            with rehearsal.namespace(runtime),patch.object(rehearsal,'require_ports_free'),patch.object(rehearsal,'require_resources_absent'),patch.object(rehearsal,'archive_origin',return_value=(captured,{'synthetic':True},credentials)),patch.object(rehearsal.shutil,'disk_usage',return_value=SimpleNamespace(free=16*1024**3)),patch.object(Path,'read_text',read),patch.object(rehearsal.configuration,'generate',side_effect=generate) as generated,patch.object(rehearsal.manage,'attest_resources'),patch.object(rehearsal.manage,'docker') as docker:
                observed,_=rehearsal.prepare(runtime,Path('/unused-artifacts'),SHA,IMAGES,{'build_timestamp':STAMP},snapshots)
                self.assertEqual(observed,captured)
                generated.assert_called_once_with(runtime,SHA,IMAGES,{'build_timestamp':STAMP},credentials,rehearsal.PROJECT,rehearsal.OWNER)
                body=(runtime/'verified-compose.json').read_bytes()
                rehearsal.validate_plan(json.loads(body),runtime,SHA,IMAGES,STAMP)
                self.assertNotIn('22080',(runtime/'application.env').read_text())
                self.assertEqual(json.loads((runtime/'configuration-receipt.json').read_bytes())['sha256'],hashlib.sha256(body).hexdigest())
                docker.assert_not_called()


if __name__=='__main__':unittest.main()

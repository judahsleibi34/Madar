import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load_manager():
    root = Path(os.environ.get("MADAR_TEST_REPOSITORY_ROOT", Path(__file__).resolve().parents[2]))
    spec = importlib.util.spec_from_file_location("integration_staging_manager", root / "staging/integration/manage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IntegrationStagingSafetyTests(unittest.TestCase):
    def setUp(self):
        self.manager = load_manager()
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.runtime = Path(self.directory) / "runtime"
        self.enterContext(patch.object(self.manager, "RUNTIME", self.runtime))
        self.enterContext(patch.object(self.manager.Path, "home", return_value=Path(self.directory)))
        self.enterContext(patch.object(self.manager.socket, "gethostname", return_value="madar-staging"))
        # Certificate generation is exercised by the native VM/browser drill;
        # config/ownership unit tests do not require a host OpenSSL executable.
        self.enterContext(patch.object(self.manager, "ensure_tls"))

    def test_primary_host_rejects_before_docker_or_filesystem_mutation(self):
        with patch.object(self.manager.socket, "gethostname", return_value="madar-gpu"), \
             patch.object(self.manager.subprocess, "run") as process:
            for operation in (lambda: self.manager.prepare("a" * 40), self.manager.up,
                              self.manager.schema, self.manager.down):
                with self.assertRaisesRegex(RuntimeError, "dedicated"):
                    operation()
            process.assert_not_called()
            self.assertFalse(self.runtime.exists())

    def test_prepare_rejects_missing_commit_and_existing_runtime(self):
        with self.assertRaisesRegex(RuntimeError, "committed source"):
            self.manager.prepare("main")
        self.runtime.mkdir()
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            self.manager.prepare("a" * 40)

    def test_generated_credentials_are_private_and_provider_targets_are_internal(self):
        self.manager.prepare("a" * 40)
        self.assertEqual((self.runtime / "compose.env").stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.runtime.stat().st_mode & 0o777, 0o700)
        values = dict(line.split("=", 1) for line in (self.runtime / "application.env").read_text().splitlines())
        self.assertEqual(values["APP_ENV"], "staging")
        self.assertEqual(values["SUPABASE_URL"], "http://gateway:8081")
        self.assertEqual(values["REDIS_URL"], "redis://redis:6379/0")
        self.assertNotEqual(values["SUPABASE_ANON_KEY"], values["SUPABASE_SERVICE_KEY"])
        self.assertEqual(values["COMMERCIAL_ENTITLEMENTS_ENFORCED"], "true")
        self.assertEqual(values["EMAIL_CHANNEL_ENABLED"], "false")

    def test_unowned_resources_reject_before_compose_mutation(self):
        self.manager.prepare("a" * 40)
        resource = {"Config": {"Labels": {"com.madar.staging.owner": "other-owner"}}}
        with patch.object(self.manager, "docker", side_effect=[b"container-id", json.dumps([resource]).encode()]), \
             patch.object(self.manager, "compose") as compose:
            with self.assertRaisesRegex(RuntimeError, "unowned"):
                self.manager.down()
            compose.assert_not_called()

    def test_migrations_reject_unmarked_database_before_reading_sql(self):
        with patch.object(self.manager, "sql", return_value="production:unrelated") as query:
            with self.assertRaisesRegex(RuntimeError, "unverified"):
                self.manager.schema()
            self.assertEqual(query.call_count, 1)

    def test_source_selection_preserves_credentials_and_binds_both_environments(self):
        self.manager.prepare("a" * 40)
        before = dict(line.split("=", 1) for line in (self.runtime / "application.env").read_text().splitlines())
        self.manager.select_source("b" * 40)
        after = dict(line.split("=", 1) for line in (self.runtime / "application.env").read_text().splitlines())
        self.assertEqual(self.manager.state()["source_sha"], "b" * 40)
        self.assertEqual(after["MADAR_RELEASE_SHA"], "b" * 40)
        self.assertEqual(after["SUPABASE_SERVICE_KEY"], before["SUPABASE_SERVICE_KEY"])
        self.assertEqual(after["CSRF_SECRET"], before["CSRF_SECRET"])

    def test_partial_source_binding_rejects_before_container_mutation(self):
        self.manager.prepare("a" * 40)
        self.manager.private_write("compose.env", "SOURCE_SHA=" + "b" * 40 + "\n")
        with patch.object(self.manager, "docker") as docker:
            with self.assertRaisesRegex(RuntimeError, "binding mismatch"):
                self.manager.up()
            docker.assert_not_called()

    def test_unmarked_database_stops_before_native_provider_migrations(self):
        self.manager.prepare("a" * 40)
        images = [b"sha256:3e97770112fda376932c3ddfec9d7f9a80fb014b4bd25476c544b52e85999b28",
                  b"sha256:9889c69c8d3526c94abcf36d4099d5d47fb80dd03c4954ddc5051faab9ba6467", b""]
        with patch.object(self.manager, "attest_resources"), \
             patch.object(self.manager, "docker", side_effect=images), \
             patch.object(self.manager, "compose") as compose, \
             patch.object(self.manager, "require_database_marker", side_effect=RuntimeError("unverified")):
            with self.assertRaisesRegex(RuntimeError, "unverified"):
                self.manager.up()
        compose.assert_called_once_with("up", "-d", "--wait", "--wait-timeout", "90", "postgres", "redis")

    def test_schema146_rejects_before_new_consumer_recreation(self):
        self.manager.prepare('a'*40)
        images=[b'sha256:3e97770112fda376932c3ddfec9d7f9a80fb014b4bd25476c544b52e85999b28',
                b'sha256:9889c69c8d3526c94abcf36d4099d5d47fb80dd03c4954ddc5051faab9ba6467',b'']
        with patch.object(self.manager,'attest_resources'),patch.object(self.manager,'docker',side_effect=images), \
             patch.object(self.manager,'compose') as compose,patch.object(self.manager,'require_database_marker'), \
             patch.object(self.manager,'configure_provider_access'),patch.object(self.manager,'sql',side_effect=['t','146']):
            with self.assertRaisesRegex(RuntimeError,'explicit upgrade'):self.manager.up()
        self.assertEqual(compose.call_count,2)
        self.assertTrue(all('notification-worker' not in call.args and 'backend' not in call.args for call in compose.call_args_list))

    def load_upgrade(self):
        import sys
        from types import SimpleNamespace
        root=Path(os.environ.get('MADAR_TEST_REPOSITORY_ROOT',Path(__file__).resolve().parents[2]))
        spec=importlib.util.spec_from_file_location('synthetic_notification_upgrade',root/'staging/integration/upgrade_notifications.py')
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'manage':self.manager,'restore':SimpleNamespace(write_binary=lambda *_:None)}):
            spec.loader.exec_module(module)
        return module

    def test_upgrade_unmarked_database_rejects_before_stop_or_candidate_selection(self):
        tool=self.load_upgrade()
        with patch.object(self.manager,'require_database_marker',side_effect=RuntimeError('unverified')), \
             patch.object(self.manager,'compose') as compose,patch.object(tool,'entries') as entries:
            with self.assertRaisesRegex(RuntimeError,'unverified'):tool.main()
        compose.assert_not_called();entries.assert_not_called()

    def test_interrupted_upgrade_resumes_old_worker_only_before147_commit(self):
        self.manager.prepare('a'*40)
        source=Path(self.directory)/'source';source.mkdir()
        (source/'147.sql').write_text('SQL147')
        (source/'148.sql').write_text('SQL148')
        tool=self.load_upgrade()
        for committed in (0,147,148):
            with self.subTest(committed=committed):
                observed=[146]
                def sql(statement,**_):
                    if statement.startswith('select schema_version'):return str(observed[0])
                    if statement.startswith('select count'):return '0'
                    if statement.lstrip().startswith('begin;\ncreate temporary table notification_upgrade_preservation'):
                        return '{"tables":{},"sequences":{}}' if observed[0]!=148 else '{"tables":{"changed":{}},"sequences":{}}'
                    if statement=='SQL147':
                        if not committed:raise RuntimeError('synthetic interruption')
                        observed[0]=147;return ''
                    if statement=='SQL148':
                        if committed==148:observed[0]=148;return ''
                        raise RuntimeError('synthetic interruption')
                    raise AssertionError('unexpected SQL')
                def docker(*args,**_):
                    if args[0]=='inspect':return json.dumps([{'State':{'Running':True}}]).encode()
                    if args[0]=='exec':return b'synthetic dump'
                    raise AssertionError('unexpected Docker call')
                with patch.object(self.manager,'REPOSITORY',source),patch.object(self.manager,'attest_resources'), \
                     patch.object(self.manager,'require_database_marker'),patch.object(self.manager,'sql',side_effect=sql), \
                     patch.object(self.manager,'compose',return_value=b'owned-worker') as compose, \
                     patch.object(self.manager,'docker',side_effect=docker), \
                     patch.object(tool,'entries',side_effect=[[
                        {'from_schema':146,'to_schema':147,'path':'147.sql','sha256':'a'*64}],
                        [{'from_schema':147,'to_schema':148,'path':'148.sql','sha256':'b'*64}]]):
                    with self.assertRaisesRegex(RuntimeError,'synthetic interruption|preservation mismatch'):tool.main()
                started=any(call.args and call.args[0]=='start' for call in compose.call_args_list)
                self.assertEqual(started,not committed,'Old worker must never resume after147 commits')

    def test_unverified_committed_upgrade_blocks_consumer_admission(self):
        self.manager.prepare('a'*40)
        self.manager.private_write('notification-upgrade.json',json.dumps({'schema':148,'backup':'synthetic.dump'}))
        with self.assertRaisesRegex(RuntimeError,'preservation remains unverified'):
            self.manager.configure_application_schema()

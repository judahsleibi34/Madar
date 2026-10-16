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

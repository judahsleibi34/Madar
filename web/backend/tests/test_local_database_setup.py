import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from run_local import configure_local_environment

spec = importlib.util.spec_from_file_location("local_database_setup", Path(__file__).resolve().parents[2] / "scripts/start_local_database.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class LocalDatabaseSetupTests(unittest.TestCase):
    def test_local_launcher_uses_release_contract_instead_of_stale_health_defaults(self):
        environment = {"APP_ENV": "development", "SUPABASE_URL": "http://127.0.0.1:54321", "SUPABASE_DB_URL": "postgresql://127.0.0.1/postgres", "SCHEMA_COMPATIBLE_MIN": "81", "SCHEMA_COMPATIBLE_MAX": "83"}
        contract = json.dumps({"schema": {"compatible_min": 114, "compatible_max": 118, "target": 118}})
        with patch.dict(os.environ, environment, clear=True), patch("run_local.Path.is_file", return_value=True), patch("run_local.load_dotenv"), patch("run_local.Path.read_text", return_value=contract):
            configure_local_environment(local_database=True)
            self.assertEqual(os.environ["SCHEMA_COMPATIBLE_MIN"], "114")
            self.assertEqual(os.environ["SCHEMA_COMPATIBLE_MAX"], "118")
        invalid = json.dumps({"schema": {"compatible_min": 114, "compatible_max": 117, "target": 118}})
        with patch.dict(os.environ, environment, clear=True), patch("run_local.Path.is_file", return_value=True), patch("run_local.load_dotenv"), patch("run_local.Path.read_text", return_value=invalid):
            with self.assertRaisesRegex(RuntimeError, "Invalid local release"):
                configure_local_environment(local_database=True)

    def test_launcher_rejects_hosted_database_in_local_mode(self):
        with patch.dict(os.environ, {"APP_ENV": "development", "SUPABASE_URL": "https://shared.supabase.co", "SUPABASE_DB_URL": "postgresql://localhost/postgres"}, clear=True), patch("run_local.Path.is_file", return_value=True), patch("run_local.load_dotenv"):
            with self.assertRaisesRegex(RuntimeError, "loopback SUPABASE_URL"):
                configure_local_environment(local_database=True)

    def test_launcher_does_not_fall_back_when_local_file_is_missing(self):
        with patch.dict(os.environ, {}, clear=True), patch("run_local.Path.is_file", return_value=False), patch("run_local.load_dotenv") as load:
            with self.assertRaisesRegex(RuntimeError, "configuration is missing"):
                configure_local_environment(local_database=True)
            load.assert_not_called()

    def test_setup_rejects_remote_docker_before_starting_cli(self):
        with patch.dict(os.environ, {"DOCKER_HOST": "ssh://production.example"}, clear=True), patch.object(setup.shutil, "which", return_value="/usr/bin/docker"), patch.object(setup, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "remote Docker is refused"):
                setup.main()
            run.assert_not_called()

    def test_writes_only_local_credentials_after_schema_verification(self):
        status = {"API_URL": "http://127.0.0.1:54321", "DB_URL": "postgresql://postgres:local@127.0.0.1:54322/postgres", "ANON_KEY": "local-anon", "SERVICE_ROLE_KEY": "local-service"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            releases = root / "deployment/releases"
            releases.mkdir(parents=True)
            (releases / "release.json").write_text(json.dumps({"schema": {"target": 117}}))
            with patch.object(setup, "WEB_ROOT", root), patch.object(setup, "verify_database") as verify:
                setup.write_environment(status)
                verify.assert_called_once_with(status["API_URL"], status["SERVICE_ROLE_KEY"], 117)
            output = root / ".env.database.local"
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertIn('SUPABASE_SERVICE_KEY="local-service"', output.read_text())
            self.assertFalse((root / ".env").exists())
            with output.open("a") as file:
                file.write('MADAR_TEST_EMAIL="testing@example.com"\nMADAR_TEST_PASSWORD="local-password"\nMADAR_TEST_AUTO_LOGIN="true"\n')
            with patch.object(setup, "WEB_ROOT", root), patch.object(setup, "verify_database"):
                setup.write_environment(status)
            self.assertIn('MADAR_TEST_PASSWORD="local-password"', output.read_text())
            output.unlink()
            with patch.object(setup, "WEB_ROOT", root), patch.object(setup, "verify_database", side_effect=RuntimeError("Schema mismatch")):
                with self.assertRaisesRegex(RuntimeError, "Schema mismatch"):
                    setup.write_environment(status)
            self.assertFalse(output.exists())

    def test_setup_rejects_hosted_status(self):
        with self.assertRaisesRegex(RuntimeError, "non-local API"):
            setup.write_environment({"API_URL": "https://shared.supabase.co"})

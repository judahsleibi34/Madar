import json
import os
import shlex
import subprocess
import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT", Path(__file__).resolve().parents[2]))
WORKFLOW = ROOT / ".github" / "workflows" / "backend-check.yml"
REQUIRED_DATABASE_ENV = {
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_KEY",
}
MUTABLE_STORAGE_ENV = {
    "PUBLIC_UPLOADS_DIR",
    "DATA_UPLOAD_DIR",
    "PRIVATE_CHARTS_DIR",
    "MADAR_UPLOAD_WORKSPACE_DIR",
    "MPLCONFIGDIR",
    "XDG_CACHE_HOME",
}


def _named_run_command(workflow: Path, step_name: str) -> str:
    lines = workflow.read_text(encoding="utf-8").splitlines()
    name_index = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == f"- name: {step_name}"
    )
    step_indent = len(lines[name_index]) - len(lines[name_index].lstrip())
    run_index = next(
        index
        for index in range(name_index + 1, len(lines))
        if lines[index].strip() == "run: |"
    )
    command_lines = []
    for line in lines[run_index + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= step_indent:
            break
        command_lines.append(line.strip())
    return "\n".join(command_lines).replace("\\\n", " ")


def _docker_environment(command: str) -> dict[str, str]:
    tokens = shlex.split(command)
    environment = {}
    for index, token in enumerate(tokens):
        if token != "--env":
            continue
        name, separator, value = tokens[index + 1].partition("=")
        if not separator:
            raise AssertionError(f"CI environment entry {name!r} has no deterministic value")
        environment[name] = value
    return environment


class BackendCiEnvironmentTests(unittest.TestCase):
    def test_backend_ci_uses_safe_complete_hermetic_environment(self):
        command = _named_run_command(WORKFLOW, "Run backend tests")
        tokens = shlex.split(command)
        environment = _docker_environment(command)

        self.assertEqual(REQUIRED_DATABASE_ENV - environment.keys(), set())
        self.assertEqual(MUTABLE_STORAGE_ENV - environment.keys(), set())
        self.assertEqual(environment.get("APP_ENV"), "test")
        self.assertEqual(environment.get("PYGWALKER_TELEMETRY_ENABLED"), "false")

        storage_paths = {
            name: Path(environment[name])
            for name in MUTABLE_STORAGE_ENV
        }
        for name, path in storage_paths.items():
            with self.subTest(name=name):
                self.assertTrue(path.is_absolute())
                self.assertTrue(path.is_relative_to(Path("/tmp/madar-ci")))
                self.assertNotIn("/app", str(path))
                self.assertNotIn("/home", str(path))
        self.assertEqual(len(set(storage_paths.values())), len(storage_paths))

        separated_paths = {
            storage_paths["PUBLIC_UPLOADS_DIR"],
            storage_paths["DATA_UPLOAD_DIR"],
            storage_paths["PRIVATE_CHARTS_DIR"],
            storage_paths["MADAR_UPLOAD_WORKSPACE_DIR"],
        }
        self.assertEqual(len(separated_paths), 4)
        public_path = storage_paths["PUBLIC_UPLOADS_DIR"]
        for private_name in ("DATA_UPLOAD_DIR", "PRIVATE_CHARTS_DIR"):
            private_path = storage_paths[private_name]
            self.assertNotEqual(public_path, private_path)
            self.assertNotIn(public_path, private_path.parents)

        url = urlsplit(environment["SUPABASE_URL"])
        self.assertEqual(url.scheme, "http")
        self.assertIn(url.hostname, {"127.0.0.1", "localhost", "::1"})
        self.assertNotIn("supabase.co", environment["SUPABASE_URL"])

        anon_key = environment["SUPABASE_ANON_KEY"]
        service_key = environment["SUPABASE_SERVICE_KEY"]
        self.assertNotEqual(anon_key, service_key)
        for value in (anon_key, service_key):
            self.assertTrue(value.startswith("madar-ci-placeholder-"))
            self.assertIn("not-a-secret", value)
            self.assertNotIn("eyJ", value)

        self.assertIn("scripts/run_tests_no_external_network.py", tokens)
        self.assertNotIn("--privileged", tokens)
        self.assertNotIn("--user", tokens)
        self.assertNotIn("chmod", tokens)
        self.assertNotIn("777", tokens)
        tmpfs_index = tokens.index("--tmpfs")
        self.assertEqual(tokens[tmpfs_index + 1], "/tmp:rw,nosuid,nodev,size=1g,mode=1777")

    def test_application_import_uses_writable_ci_storage_as_non_root(self):
        command = _named_run_command(WORKFLOW, "Run backend tests")
        ci_environment = _docker_environment(command)
        environment = os.environ.copy()
        environment.update(ci_environment)
        backend_root = Path(__file__).resolve().parents[1]
        script = """
import json
import os
from pathlib import Path
import app

paths = [
    app.PUBLIC_UPLOADS_DIR,
    app.DATA_UPLOAD_DIR,
    app.PRIVATE_CHARTS_DIR,
    Path(os.environ["MADAR_UPLOAD_WORKSPACE_DIR"]),
]
for path in paths:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".madar-ci-write-probe"
    probe.write_text("test", encoding="utf-8")
    probe.unlink()
print(json.dumps({
    "uid": os.geteuid(),
    "app_writable": os.access("/app", os.W_OK),
    "paths": [str(path) for path in paths],
}))
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=backend_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        details = json.loads(result.stdout.splitlines()[-1])
        self.assertNotEqual(details["uid"], 0)
        self.assertFalse(details["app_writable"])
        for path in details["paths"]:
            self.assertTrue(Path(path).is_relative_to(Path("/tmp/madar-ci")))

    def test_production_storage_defaults_are_not_redirected_to_tmp(self):
        environment = os.environ.copy()
        for name in MUTABLE_STORAGE_ENV | {"UPLOADS_DIR", "GENERATED_CHARTS_DIR"}:
            environment.pop(name, None)
        environment["APP_ENV"] = "production"
        backend_root = Path(__file__).resolve().parents[1]
        script = """
import json
from services.upload_config import get_data_upload_dir, get_private_charts_dir, get_public_uploads_dir
print(json.dumps([
    str(get_public_uploads_dir()),
    str(get_data_upload_dir()),
    str(get_private_charts_dir()),
]))
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=backend_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        defaults = [Path(value) for value in json.loads(result.stdout)]
        self.assertEqual(
            [path.name for path in defaults],
            ["uploads", "private_uploads", "private_generated_charts"],
        )
        for path in defaults:
            self.assertFalse(path.is_relative_to(Path("/tmp")))

    def test_database_still_fails_closed_without_required_configuration(self):
        backend_root = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        for name in REQUIRED_DATABASE_ENV:
            environment.pop(name, None)
        environment.update(
            {
                "APP_ENV": "production",
                "MADAR_ENV_FILE": "/tmp/madar-ci-deliberately-missing.env",
            }
        )

        result = subprocess.run(
            [sys.executable, "-c", "import database"],
            cwd=backend_root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing Supabase environment variables", result.stderr)


if __name__ == "__main__":
    unittest.main()

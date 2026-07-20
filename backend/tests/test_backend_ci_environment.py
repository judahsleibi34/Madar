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
        environment = _docker_environment(command)

        self.assertEqual(REQUIRED_DATABASE_ENV - environment.keys(), set())
        self.assertEqual(environment.get("APP_ENV"), "test")
        self.assertEqual(environment.get("PYGWALKER_TELEMETRY_ENABLED"), "false")
        self.assertEqual(environment.get("MPLCONFIGDIR"), "/tmp/matplotlib")
        self.assertTrue(environment.get("XDG_CACHE_HOME", "").startswith("/tmp/"))

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

        self.assertIn("scripts/run_tests_no_external_network.py", shlex.split(command))

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

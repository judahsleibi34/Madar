import os
import sys
import tempfile
import unittest
from pathlib import Path


WEB_ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB_ROOT))

from deployment.lib.environment_file import load_environment_file


class DeploymentEnvironmentFileTests(unittest.TestCase):
    def write_environment(self, root: str, text: str, mode: int = 0o600) -> Path:
        path = Path(root) / "runtime.env"
        path.write_text(text, encoding="utf-8")
        path.chmod(mode)
        return path

    def test_loads_equals_and_yaml_style_without_overwriting_unit_values(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.write_environment(
                root,
                'NORMAL=value\nQUOTED="protected value"\nYAML_STYLE: "opaque"\n',
            )
            environment = {"NORMAL": "unit-wins"}
            names = load_environment_file(path, environ=environment)
        self.assertEqual(names, {"NORMAL", "QUOTED", "YAML_STYLE"})
        self.assertEqual(environment["NORMAL"], "unit-wins")
        self.assertEqual(environment["QUOTED"], "protected value")
        self.assertEqual(environment["YAML_STYLE"], "opaque")

    def test_rejects_broad_permissions_without_reading_values(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.write_environment(root, "SECRET=opaque\n", mode=0o640)
            with self.assertRaisesRegex(RuntimeError, "permissions_too_broad"):
                load_environment_file(path, environ={})

    def test_non_secret_path_contract_may_be_root_readable(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.write_environment(
                root, "MADAR_STORAGE_ROOT=/var/lib/madar/storage\n", mode=0o644,
            )
            environment = {}
            load_environment_file(
                path, environ=environment, require_private=False,
            )
        self.assertEqual(
            environment["MADAR_STORAGE_ROOT"], "/var/lib/madar/storage",
        )

    def test_errors_report_line_number_not_value(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.write_environment(root, "VALID=ok\nnot an assignment\n")
            with self.assertRaisesRegex(RuntimeError, "line_invalid:2") as raised:
                load_environment_file(path, environ={})
        self.assertNotIn("not an assignment", str(raised.exception))


if __name__ == "__main__":
    unittest.main()

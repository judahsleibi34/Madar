import json
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_dependency_locks", ROOT / "scripts" / "check_dependency_locks.py")
dependency_locks = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(dependency_locks)
validate_node = dependency_locks.validate_node
validate_python = dependency_locks.validate_python


class DependencyLockingTests(unittest.TestCase):
    def test_python_unpinned_and_constraint_drift_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            requirements = Path(root) / "requirements.txt"
            constraints = Path(root) / "constraints.txt"
            requirements.write_text("fastapi\nrequests==2.0.0\n", encoding="utf-8")
            constraints.write_text("requests==1.0.0\n", encoding="utf-8")
            errors = validate_python(requirements, constraints)
        self.assertTrue(any("exact == pin" in error for error in errors))
        self.assertTrue(any("must match direct pin" in error for error in errors))

    def test_node_root_dependency_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            package = Path(root) / "package.json"
            lock = Path(root) / "package-lock.json"
            package.write_text(json.dumps({"dependencies": {"react": "1"}}), encoding="utf-8")
            lock.write_text(json.dumps({"lockfileVersion": 3, "packages": {"": {"dependencies": {"react": "2"}}}}), encoding="utf-8")
            errors = validate_node(package, lock)
        self.assertIn("package-lock.json: root dependencies drifted from package.json", errors)


if __name__ == "__main__":
    unittest.main()

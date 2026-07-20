import unittest
from unittest.mock import patch

from backend.scripts.verify_installed_constraints import installed_drift


class Distribution:
    def __init__(self, name, version):
        self.metadata = {"Name": name}
        self.version = version


class InstalledConstraintTests(unittest.TestCase):
    def test_unlocked_and_mismatched_packages_are_reported(self):
        distributions = [Distribution("Known_Package", "2"), Distribution("Untracked", "1")]
        with patch("backend.scripts.verify_installed_constraints.importlib.metadata.distributions", return_value=distributions):
            errors = installed_drift({"known-package": "1"})
        self.assertIn("installed dependency drift: known-package==2, expected 1", errors)
        self.assertIn("installed dependency is not constrained: untracked==1", errors)


if __name__ == "__main__":
    unittest.main()

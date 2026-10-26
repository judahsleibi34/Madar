import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path


def source_path(relative):
    local = Path(__file__).resolve()
    for parent in local.parents:
        candidate_path = parent / relative
        if candidate_path.exists():
            return candidate_path
    mappings = {
        "web/database/": Path("/app/database"),
        "web/supabase/": Path("/app/supabase"),
        "web/deployment/": Path("/test-repository/deployment"),
        "web/scripts/": Path("/scripts"),
    }
    for prefix, base in mappings.items():
        if relative.startswith(prefix):
            return base / relative.removeprefix(prefix)
    raise FileNotFoundError(relative)


SPEC = importlib.util.spec_from_file_location(
    "automated_reporting_candidate", source_path("web/scripts/automated_reporting_candidate.py")
)
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)


class AutomatedReportingCandidateTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        for relative in (
            "web/database/migrations/164_add_automated_reporting.sql",
            "web/supabase/migrations/164_add_automated_reporting.sql",
            "web/deployment/releases/migrations-163-164-automated-reporting.json",
            "web/deployment/releases/schema-163-164-automated-reporting-bridge.json",
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path(relative), target)
        return temporary, root

    def test_candidate_artifacts_and_safety_contract(self):
        temporary, root = self.fixture()
        with temporary:
            entries = candidate.validated_entries(root)
        self.assertEqual(entries[0]["number"], 164)

    def test_candidate_metadata_does_not_select_a_release(self):
        bridge = source_path(
            "web/deployment/releases/schema-163-164-automated-reporting-bridge.json"
        ).read_text()
        self.assertIn("active release remains schema146", bridge)
        self.assertNotIn('"selected": true', bridge.lower())


if __name__ == "__main__":
    unittest.main()

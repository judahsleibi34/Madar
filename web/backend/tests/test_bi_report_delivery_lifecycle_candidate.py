import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path


def source_path(relative):
    local = Path(__file__).resolve()
    for parent in local.parents:
        candidate = parent / relative
        if candidate.exists(): return candidate
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


SPEC = importlib.util.spec_from_file_location("candidate", source_path("web/scripts/bi_report_delivery_lifecycle_candidate.py"))
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)


class ReportDeliveryLifecycleCandidateTests(unittest.TestCase):
    def test_artifacts_and_safety_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (
                "web/database/migrations/166_add_bi_report_delivery_lifecycle.sql",
                "web/supabase/migrations/166_add_bi_report_delivery_lifecycle.sql",
                "web/deployment/releases/migrations-165-166-bi-report-delivery-lifecycle.json",
                "web/deployment/releases/schema-165-166-bi-report-delivery-lifecycle-bridge.json",
            ):
                target = root / relative; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path(relative), target)
            self.assertEqual(candidate.validated_entries(root)[0]["number"], 166)

    def test_active_release_is_not_selected(self):
        bridge = source_path("web/deployment/releases/schema-165-166-bi-report-delivery-lifecycle-bridge.json").read_text()
        self.assertIn("active release remains schema146", bridge)
        self.assertNotIn('"selected": true', bridge.lower())


if __name__ == "__main__": unittest.main()

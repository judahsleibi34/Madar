import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def source_path(relative):
    local = Path(__file__).resolve()
    for parent in local.parents:
        candidate = parent / relative
        if candidate.exists():
            return candidate
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


SPEC = importlib.util.spec_from_file_location("bi_dashboard_candidate", source_path("web/scripts/bi_dashboard_candidate.py"))
CANDIDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CANDIDATE)


class BiDashboardCandidateTests(unittest.TestCase):
    def fixture(self, mutation=lambda value: value, *, mirror=True):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        relatives = (
            "web/database/migrations/163_add_bi_dashboards.sql",
            "web/supabase/migrations/163_add_bi_dashboards.sql",
            "web/deployment/releases/migrations-162-163-bi-dashboards.json",
            "web/deployment/releases/schema-162-163-bi-dashboards-bridge.json",
        )
        for relative in relatives:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path(relative), target)
        original = root / relatives[0]
        changed = mutation(original.read_text())
        original.write_text(changed)
        if mirror:
            (root / relatives[1]).write_text(changed)
        manifest = root / relatives[2]
        value = json.loads(manifest.read_text())
        value["migrations"][0]["sha256"] = hashlib.sha256(original.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(value, indent=2) + "\n")
        return temporary, root, hashlib.sha256(manifest.read_bytes()).hexdigest()

    def validate(self, root, digest):
        bridge = root / "web/deployment/releases/schema-162-163-bi-dashboards-bridge.json"
        with patch.object(CANDIDATE, "MANIFEST_SHA256", digest), patch.object(
            CANDIDATE, "BRIDGE_SHA256", hashlib.sha256(bridge.read_bytes()).hexdigest(),
        ):
            return CANDIDATE.validated_entries(root)

    def test_exact_candidate_passes(self):
        temporary, root, digest = self.fixture()
        with temporary:
            self.assertEqual(self.validate(root, digest)[0]["to_schema"], 163)

    def test_predecessor_guard_and_state_lock_are_mandatory(self):
        for mutation in (
            lambda sql: sql.replace("v_schema_version<>162", "v_schema_version<>161", 1),
            lambda sql: sql.replace("  for update;", ";", 1),
        ):
            temporary, root, digest = self.fixture(mutation)
            with temporary, self.assertRaises(ValueError):
                self.validate(root, digest)

    def test_required_private_dashboard_contract_is_mandatory(self):
        temporary, root, digest = self.fixture(
            lambda sql: sql.replace("alter table public.bi_dashboards enable row level security;", "", 1))
        with temporary, self.assertRaises(ValueError):
            self.validate(root, digest)

    def test_migration_mirror_mismatch_fails(self):
        temporary, root, digest = self.fixture(lambda sql: sql + "\n-- mismatch\n", mirror=False)
        with temporary, self.assertRaises(ValueError):
            self.validate(root, digest)


if __name__ == "__main__":
    unittest.main()

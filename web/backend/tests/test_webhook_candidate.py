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


SPEC = importlib.util.spec_from_file_location("webhook_candidate", source_path("web/scripts/webhook_candidate.py"))
CANDIDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CANDIDATE)


class WebhookCandidateTests(unittest.TestCase):
    def fixture(self, sql_mutation=lambda value: value, *, mirror=True, duplicate=False):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        for relative in (
            "web/database/migrations/162_add_secure_webhook_ingestion.sql",
            "web/supabase/migrations/162_add_secure_webhook_ingestion.sql",
            "web/deployment/releases/migrations-161-162-webhooks.json",
            "web/deployment/releases/schema-161-162-webhooks-bridge.json",
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path(relative), target)
        original = root / "web/database/migrations/162_add_secure_webhook_ingestion.sql"
        changed = sql_mutation(original.read_text())
        original.write_text(changed)
        if mirror:
            (root / "web/supabase/migrations/162_add_secure_webhook_ingestion.sql").write_text(changed)
        manifest_path = root / "web/deployment/releases/migrations-161-162-webhooks.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["migrations"][0]["sha256"] = hashlib.sha256(original.read_bytes()).hexdigest()
        if duplicate:
            manifest["migrations"].append(dict(manifest["migrations"][0]))
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        return temporary, root, hashlib.sha256(manifest_path.read_bytes()).hexdigest()

    def validate(self, root, manifest_digest):
        bridge = root / "web/deployment/releases/schema-161-162-webhooks-bridge.json"
        with patch.object(CANDIDATE, "MANIFEST_SHA256", manifest_digest), patch.object(
            CANDIDATE, "BRIDGE_SHA256", hashlib.sha256(bridge.read_bytes()).hexdigest(),
        ):
            return CANDIDATE.validated_entries(root)

    def test_correct_transition_and_whitespace_variation_pass(self):
        temporary, root, digest = self.fixture(lambda sql: sql.replace("begin;", "begin;\n\n", 1))
        with temporary:
            self.assertEqual(self.validate(root, digest)[0]["to_schema"], 162)

    def test_missing_schema_lock_fails_even_if_comment_spoofs_it(self):
        temporary, root, digest = self.fixture(
            lambda sql: sql.replace("  for update;", "  -- for update;", 1))
        with temporary, self.assertRaises(ValueError):
            self.validate(root, digest)

    def test_wrong_predecessor_fails(self):
        temporary, root, digest = self.fixture(lambda sql: sql.replace("v_schema_version<>161", "v_schema_version<>160", 1))
        with temporary, self.assertRaises(ValueError):
            self.validate(root, digest)

    def test_missing_core_contract_fails(self):
        temporary, root, digest = self.fixture(lambda sql: sql.replace("contract_key = 'core'", "contract_key = 'wrong'", 1))
        with temporary, self.assertRaises(ValueError):
            self.validate(root, digest)

    def test_unrelated_lock_cannot_replace_transition_lock(self):
        def mutation(sql):
            return sql.replace("  for update;", "  ;", 1).replace(
                "create table public.data_source_webhook_endpoints",
                "select 1 from public.tenants for update;\ncreate table public.data_source_webhook_endpoints", 1)
        temporary, root, digest = self.fixture(mutation)
        with temporary, self.assertRaises(ValueError):
            self.validate(root, digest)

    def test_duplicate_transition_and_mismatched_mirror_fail(self):
        temporary, root, digest = self.fixture(duplicate=True)
        with temporary, self.assertRaises(ValueError):
            self.validate(root, digest)
        temporary, root, digest = self.fixture(lambda sql: sql + "\n-- mirror mismatch\n", mirror=False)
        with temporary, self.assertRaises(ValueError):
            self.validate(root, digest)


if __name__ == "__main__":
    unittest.main()

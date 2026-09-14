import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(
    os.getenv("MADAR_TEST_REPOSITORY_ROOT")
    or Path(__file__).resolve().parents[2]
).resolve()
SCRIPT = ROOT / "deployment/lib/supabase_ledger_reconciliation.py"


def load_module():
    spec = importlib.util.spec_from_file_location("supabase_ledger_reconciliation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeRunner:
    def __init__(self, root, sha):
        self.root = root
        self.sha = sha
        self.remote = {96}
        self.repairs = 0

    def __call__(self, arguments, **_kwargs):
        if arguments[0] == "git":
            if "--show-toplevel" in arguments:
                output = f"{self.root}\n"
            elif "status" in arguments:
                output = ""
            else:
                output = f"{self.sha}\n"
        elif "list" in arguments:
            rows = [f" {version:03d} | {version:03d} | {version:03d}" for version in sorted(self.remote)]
            rows.append(" 097 |     | 097")
            output = "Local | Remote | Time (UTC)\n" + "\n".join(rows)
        else:
            self.repairs += 1
            self.remote.add(97)
            output = "repaired"
        return subprocess.CompletedProcess(arguments, 0, output, "")


class SupabaseLedgerReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.sha = "a" * 40

    def fixture(self, root):
        repository = root / "repository"
        web = repository / "web"
        release_dir = web / "deployment/releases"
        migration = web / "database/migrations/097_fixture.sql"
        release_dir.mkdir(parents=True)
        migration.parent.mkdir(parents=True)
        (web / "supabase/.temp").mkdir(parents=True)
        (web / "supabase/.temp/project-ref").write_text("fixture-project\n", encoding="utf-8")
        migration.write_text("begin; select 97; commit;\n", encoding="utf-8")
        checksum = hashlib.sha256(migration.read_bytes()).hexdigest()
        (release_dir / "release.json").write_text(json.dumps({"schema": {"target": 97}, "migration_manifest": "migrations-097.json"}))
        (release_dir / "migrations-097.json").write_text(json.dumps({"release_sha": "CURRENT", "migrations": [{"number": 97, "from_schema": 96, "to_schema": 97, "path": "web/database/migrations/097_fixture.sql", "sha256": checksum}]}))
        state_root = root / "state"
        migration_state = state_root / "migrations" / self.sha
        migration_state.mkdir(parents=True)
        (state_root / "state.json").write_text(json.dumps({"active_slot": "green", "known_good_release": {"sha": self.sha, "slot": "green", "schema": 97}, "history": [{"release_sha": self.sha, "phase": "post_migration_workers_refreshed", "schema": {"observed": 97}}]}))
        (migration_state / "automation.json").write_text(json.dumps({"status": "completed", "phase": "post_migration_validation_complete", "observed_schema": 97}))
        (migration_state / "execution.json").write_text(json.dumps({"status": "completed", "phase": "complete", "observed_schema": 97, "migrations": [{"number": 97, "status": "applied", "checksum": checksum}]}))
        return repository, state_root, checksum

    def reader(self, url, _headers):
        if "application_schema_state" in url:
            return [{"schema_version": self.live_schema}]
        if url.endswith("/health/version"):
            return {"release_sha": self.sha}
        return {"ready": True}

    def test_repair_is_checksum_guarded_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = self.fixture(Path(directory))
            runner = FakeRunner(repository, self.sha)
            self.live_schema = 97
            arguments = dict(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation=f"097:{checksum}", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"}, runner=runner, json_reader=self.reader)
            first = self.module.run(**arguments)
            second = self.module.run(**arguments)
        self.assertEqual(first["action"], "reconciled")
        self.assertEqual(second["action"], "already_reconciled")
        self.assertEqual(runner.repairs, 1)
        self.assertFalse(first["tenant_data_touched"])

    def test_live_schema_must_reach_target_before_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = self.fixture(Path(directory))
            runner = FakeRunner(repository, self.sha)
            self.live_schema = 96
            with self.assertRaisesRegex(RuntimeError, "live_schema_not_at_target"):
                self.module.run(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation=f"097:{checksum}", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"}, runner=runner, json_reader=self.reader)
        self.assertEqual(runner.repairs, 0)

    def test_completed_coordinator_evidence_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = self.fixture(Path(directory))
            automation = state_root / "migrations" / self.sha / "automation.json"
            automation.write_text(json.dumps({"status": "running", "phase": "post_migration_validation"}))
            runner = FakeRunner(repository, self.sha)
            self.live_schema = 97
            with self.assertRaisesRegex(RuntimeError, "automation_not_complete"):
                self.module.run(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation=f"097:{checksum}", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"}, runner=runner, json_reader=self.reader)
        self.assertEqual(runner.repairs, 0)

    def test_wrong_linked_project_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = self.fixture(Path(directory))
            runner = FakeRunner(repository, self.sha)
            self.live_schema = 97
            with self.assertRaisesRegex(RuntimeError, "linked_project_mismatch"):
                self.module.run(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation=f"097:{checksum}", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "different-project"}, runner=runner, json_reader=self.reader)
        self.assertEqual(runner.repairs, 0)

    def test_wrong_release_version_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = self.fixture(Path(directory))
            release = repository / "web/deployment/releases/release.json"
            release.write_text(json.dumps({"schema": {"target": 98}, "migration_manifest": "migrations-097.json"}))
            runner = FakeRunner(repository, self.sha)
            self.live_schema = 97
            with self.assertRaisesRegex(RuntimeError, "release_contract_invalid"):
                self.module.run(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation=f"097:{checksum}", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"}, runner=runner, json_reader=self.reader)
        self.assertEqual(runner.repairs, 0)

    def test_wrong_migration_checksum_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = self.fixture(Path(directory))
            (repository / "web/database/migrations/097_fixture.sql").write_text("begin; select 98; commit;\n", encoding="utf-8")
            runner = FakeRunner(repository, self.sha)
            self.live_schema = 97
            with self.assertRaisesRegex(RuntimeError, "migration_checksum_mismatch"):
                self.module.run(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation=f"097:{checksum}", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"}, runner=runner, json_reader=self.reader)
        self.assertEqual(runner.repairs, 0)

    def test_wrong_candidate_commit_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = self.fixture(Path(directory))
            runner = FakeRunner(repository, "b" * 40)
            self.live_schema = 97
            with self.assertRaisesRegex(RuntimeError, "release_sha_mismatch"):
                self.module.run(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation=f"097:{checksum}", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"}, runner=runner, json_reader=self.reader)
        self.assertEqual(runner.repairs, 0)

    def test_wrong_confirmation_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, _checksum = self.fixture(Path(directory))
            runner = FakeRunner(repository, self.sha)
            self.live_schema = 97
            with self.assertRaisesRegex(RuntimeError, "confirmation_mismatch"):
                self.module.run(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation="097:wrong", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"}, runner=runner, json_reader=self.reader)
        self.assertEqual(runner.repairs, 0)


if __name__ == "__main__":
    unittest.main()

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
        self.remote = {97}
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
            rows.append(" 098 |     | 098")
            output = "Local | Remote | Time (UTC)\n" + "\n".join(rows)
        else:
            self.repairs += 1
            self.remote.add(int(arguments[-1]))
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
        migration = web / "database/migrations/098_fixture.sql"
        release_dir.mkdir(parents=True)
        migration.parent.mkdir(parents=True)
        (web / "supabase/.temp").mkdir(parents=True)
        (web / "supabase/.temp/project-ref").write_text("fixture-project\n", encoding="utf-8")
        migration.write_text("begin; select 98; commit;\n", encoding="utf-8")
        mirror = web / "supabase/migrations" / migration.name
        mirror.parent.mkdir(parents=True)
        mirror.write_bytes(migration.read_bytes())
        checksum = hashlib.sha256(migration.read_bytes()).hexdigest()
        (release_dir / "release.json").write_text(json.dumps({"schema": {"target": 98}, "migration_manifest": "migrations-098.json"}))
        (release_dir / "migrations-098.json").write_text(json.dumps({"release_sha": "CURRENT", "migrations": [{"number": 98, "from_schema": 97, "to_schema": 98, "path": "web/database/migrations/098_fixture.sql", "sha256": checksum}]}))
        state_root = root / "state"
        migration_state = state_root / "migrations" / self.sha
        migration_state.mkdir(parents=True)
        (state_root / "state.json").write_text(json.dumps({"active_slot": "green", "known_good_release": {"sha": self.sha, "slot": "green", "schema": 98}, "history": [{"release_sha": self.sha, "phase": "post_migration_workers_refreshed", "schema": {"observed": 98}}]}))
        (migration_state / "automation.json").write_text(json.dumps({"status": "completed", "phase": "post_migration_validation_complete", "observed_schema": 98}))
        (migration_state / "execution.json").write_text(json.dumps({"status": "completed", "phase": "complete", "observed_schema": 98, "migrations": [{"number": 98, "status": "applied", "checksum": checksum}]}))
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
            self.live_schema = 98
            arguments = dict(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation=f"098:{checksum}", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"}, runner=runner, json_reader=self.reader)
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
            self.live_schema = 97
            with self.assertRaisesRegex(RuntimeError, "live_schema_not_at_target"):
                self.module.run(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation=f"098:{checksum}", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"}, runner=runner, json_reader=self.reader)
        self.assertEqual(runner.repairs, 0)

    def test_completed_coordinator_evidence_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = self.fixture(Path(directory))
            automation = state_root / "migrations" / self.sha / "automation.json"
            automation.write_text(json.dumps({"status": "running", "phase": "post_migration_validation"}))
            runner = FakeRunner(repository, self.sha)
            self.live_schema = 98
            with self.assertRaisesRegex(RuntimeError, "automation_not_complete"):
                self.module.run(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation=f"098:{checksum}", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"}, runner=runner, json_reader=self.reader)
        self.assertEqual(runner.repairs, 0)

    def test_wrong_linked_project_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = self.fixture(Path(directory))
            runner = FakeRunner(repository, self.sha)
            self.live_schema = 98
            with self.assertRaisesRegex(RuntimeError, "linked_project_mismatch"):
                self.module.run(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation=f"098:{checksum}", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "different-project"}, runner=runner, json_reader=self.reader)
        self.assertEqual(runner.repairs, 0)

    def test_wrong_release_version_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = self.fixture(Path(directory))
            release = repository / "web/deployment/releases/release.json"
            release.write_text(json.dumps({"schema": {"target": 99}, "migration_manifest": "migrations-098.json"}))
            runner = FakeRunner(repository, self.sha)
            self.live_schema = 98
            with self.assertRaisesRegex(RuntimeError, "manifest_transition_invalid"):
                self.module.run(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation=f"098:{checksum}", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"}, runner=runner, json_reader=self.reader)
        self.assertEqual(runner.repairs, 0)

    def test_wrong_migration_checksum_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = self.fixture(Path(directory))
            (repository / "web/database/migrations/098_fixture.sql").write_text("begin; select 99; commit;\n", encoding="utf-8")
            runner = FakeRunner(repository, self.sha)
            self.live_schema = 98
            with self.assertRaisesRegex(RuntimeError, "migration_checksum_mismatch"):
                self.module.run(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation=f"098:{checksum}", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"}, runner=runner, json_reader=self.reader)
        self.assertEqual(runner.repairs, 0)

    def test_wrong_candidate_commit_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = self.fixture(Path(directory))
            runner = FakeRunner(repository, "b" * 40)
            self.live_schema = 98
            with self.assertRaisesRegex(RuntimeError, "release_sha_mismatch"):
                self.module.run(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation=f"098:{checksum}", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"}, runner=runner, json_reader=self.reader)
        self.assertEqual(runner.repairs, 0)

    def test_wrong_confirmation_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, _checksum = self.fixture(Path(directory))
            runner = FakeRunner(repository, self.sha)
            self.live_schema = 98
            with self.assertRaisesRegex(RuntimeError, "confirmation_mismatch"):
                self.module.run(release_sha=self.sha, repository_root=repository, state_root=state_root, supabase_bin="supabase", confirmation="098:wrong", dry_run=False, environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"}, runner=runner, json_reader=self.reader)
        self.assertEqual(runner.repairs, 0)

    def test_remote_only_rows_are_not_hidden(self):
        self.assertEqual(self.module.migration_ledger("Local | Remote | Time\n 099 | 099 | time\n     | 100 | time\n"), {99, 100})

    @unittest.skipIf(os.name == "nt", "POSIX host deployment lock")
    def test_busy_deployment_lock_refuses_reconciliation(self):
        import fcntl
        with tempfile.TemporaryDirectory() as directory:
            arguments, entries = self.sequential_fixture(Path(directory))
            with (arguments["state_root"] / "deploy.lock").open("w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    self.module.run(**dict(arguments, migration_version=97, confirmation=f'097:{entries[0]["sha256"]}'))
            self.assertEqual(arguments["runner"].repairs, 0)

    def sequential_fixture(self, root):
        repository, state, _ = self.fixture(root)
        release_dir = repository / "web/deployment/releases"
        entries = []
        for number in (97, 98, 99):
            migration = repository / f"web/database/migrations/{number:03d}_fixture.sql"
            migration.write_text(f"begin; select {number}; commit;\n")
            (repository / "web/supabase/migrations" / migration.name).write_bytes(migration.read_bytes())
            entries.append({"number": number, "from_schema": number - 1, "to_schema": number,
                            "path": str(migration.relative_to(repository)).replace("\\", "/"),
                            "sha256": hashlib.sha256(migration.read_bytes()).hexdigest()})
        (release_dir / "release.json").write_text(json.dumps({"schema": {"target": 99}, "migration_manifest": "migrations-097-099.json"}))
        (release_dir / "migrations-097-099.json").write_text(json.dumps({"release_sha": "CURRENT", "migrations": entries}))
        release_state = json.loads((state / "state.json").read_text())
        release_state["known_good_release"]["schema"] = 99
        release_state["history"][0]["schema"]["observed"] = 99
        (state / "state.json").write_text(json.dumps(release_state))
        migration_state = state / "migrations" / self.sha
        (migration_state / "automation.json").write_text(json.dumps({"status": "completed", "phase": "post_migration_validation_complete", "observed_schema": 99}))
        (migration_state / "execution.json").write_text(json.dumps({"status": "completed", "phase": "complete", "observed_schema": 99, "migrations": [{"number": e["number"], "status": "applied", "checksum": e["sha256"]} for e in entries]}))
        runner = FakeRunner(repository, self.sha)
        runner.remote = {96}
        self.live_schema = 99
        arguments = dict(release_sha=self.sha, repository_root=repository, state_root=state,
                         supabase_bin="supabase", dry_run=False,
                         environ={"SUPABASE_URL": "https://project.invalid", "SUPABASE_SERVICE_KEY": "secret", "MADAR_SUPABASE_PROJECT_REF": "fixture-project"},
                         runner=runner, json_reader=self.reader)
        return arguments, entries

    def test_sequential_097_098_099_and_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            arguments, entries = self.sequential_fixture(Path(directory))
            for entry in entries:
                with self.subTest(version=entry["number"]):
                    call = dict(arguments, migration_version=entry["number"], confirmation=f'{entry["number"]:03d}:{entry["sha256"]}')
                    self.assertEqual(self.module.run(**call)["action"], "reconciled")
                    audit = arguments["state_root"] / f'ledger-reconciliations/{entry["number"]:03d}.json'
                    original = audit.read_bytes()
                    self.assertEqual(json.loads(original)["project_ref"], "fixture-project")
                    if os.name != "nt":
                        self.assertEqual(audit.stat().st_mode & 0o777, 0o600)
                    self.assertEqual(self.module.run(**call)["action"], "already_reconciled")
                    self.assertEqual(audit.read_bytes(), original)
            self.assertEqual(arguments["runner"].repairs, 3)
            first = entries[0]
            self.assertEqual(self.module.run(**dict(arguments, migration_version=97, confirmation=f'097:{first["sha256"]}'))["action"], "already_reconciled")

    def test_wrong_order_refuses_098_and_099(self):
        with tempfile.TemporaryDirectory() as directory:
            arguments, entries = self.sequential_fixture(Path(directory))
            for entry in entries[1:]:
                with self.subTest(version=entry["number"]), self.assertRaisesRegex(RuntimeError, "predecessor_missing"):
                    self.module.run(**dict(arguments, migration_version=entry["number"], confirmation=f'{entry["number"]:03d}:{entry["sha256"]}'))
            self.assertEqual(arguments["runner"].repairs, 0)

    def test_097_refuses_incomplete_final_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            arguments, entries = self.sequential_fixture(Path(directory))
            self.live_schema = 98
            with self.assertRaisesRegex(RuntimeError, "live_schema_not_at_target"):
                self.module.run(**dict(arguments, migration_version=97, confirmation=f'097:{entries[0]["sha256"]}'))
            self.assertEqual(arguments["runner"].repairs, 0)

    def test_audit_cannot_be_reused_for_another_project(self):
        with tempfile.TemporaryDirectory() as directory:
            arguments, entries = self.sequential_fixture(Path(directory))
            call = dict(arguments, migration_version=97, confirmation=f'097:{entries[0]["sha256"]}')
            self.module.run(**call)
            audit = arguments["state_root"] / "ledger-reconciliations/097.json"
            record = json.loads(audit.read_text())
            record["project_ref"] = "different"
            audit.write_text(json.dumps(record))
            with self.assertRaisesRegex(RuntimeError, "audit_identity_mismatch"):
                self.module.run(**call)


if __name__ == "__main__":
    unittest.main()

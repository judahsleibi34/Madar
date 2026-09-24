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

SCRIPT = (
    ROOT
    / "deployment/lib/supabase_ledger_reconciliation.py"
)

SOURCE = 102
FIRST = 103
TARGET = 104


def load_module():
    spec = importlib.util.spec_from_file_location(
        "supabase_ledger_reconciliation",
        SCRIPT,
    )

    module = importlib.util.module_from_spec(spec)

    assert spec.loader is not None
    spec.loader.exec_module(module)

    return module


class FakeRunner:
    def __init__(self, root, sha):
        self.root = root
        self.sha = sha

        # Migration 103 is already present remotely.
        # The reconciliation operation repairs 104 only.
        self.remote = {FIRST}
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
            rows = [
                (
                    f" {version:03d} | "
                    f"{version:03d} | "
                    f"{version:03d}"
                )
                for version in sorted(self.remote)
            ]

            rows.append(
                f" {TARGET:03d} |     | {TARGET:03d}"
            )

            output = (
                "Local | Remote | Time (UTC)\n"
                + "\n".join(rows)
            )

        else:
            self.repairs += 1
            self.remote.add(TARGET)
            output = "repaired"

        return subprocess.CompletedProcess(
            arguments,
            0,
            output,
            "",
        )


class SupabaseLedgerReconciliationTests(unittest.TestCase):

    def setUp(self):
        self.module = load_module()
        self.sha = "a" * 40

    def fixture(self, root):
        repository = root / "repository"
        web = repository / "web"

        release_dir = web / "deployment/releases"
        database_dir = web / "database/migrations"
        supabase_dir = web / "supabase/migrations"
        temp_dir = web / "supabase/.temp"

        release_dir.mkdir(parents=True)
        database_dir.mkdir(parents=True)
        supabase_dir.mkdir(parents=True)
        temp_dir.mkdir(parents=True)

        (
            temp_dir / "project-ref"
        ).write_text(
            "fixture-project\n",
            encoding="utf-8",
        )

        migrations = {}

        for version in (FIRST, TARGET):
            filename = f"{version:03d}_fixture.sql"

            database = database_dir / filename
            mirror = supabase_dir / filename

            payload = (
                f"begin; select {version}; commit;\n"
            )

            database.write_text(
                payload,
                encoding="utf-8",
            )

            mirror.write_bytes(
                database.read_bytes()
            )

            migrations[version] = {
                "filename": filename,
                "checksum": hashlib.sha256(
                    database.read_bytes()
                ).hexdigest(),
            }

        (
            release_dir / "release.json"
        ).write_text(
            json.dumps({
                "schema": {
                    "target": TARGET,
                    "migration_class": "expand-only",
                },
                "migration_policy":
                    "automatic-after-known-good-backup-first-forward-repair",
                "migration_manifest":
                    "migrations-103-104.json",
            }),
            encoding="utf-8",
        )

        (
            release_dir / "migrations-103-104.json"
        ).write_text(
            json.dumps({
                "release_sha": "CURRENT",
                "migrations": [
                    {
                        "number": FIRST,
                        "from_schema": SOURCE,
                        "to_schema": FIRST,
                        "compatibility": "expand-only",
                        "path": (
                            "web/database/migrations/"
                            + migrations[FIRST]["filename"]
                        ),
                        "sha256":
                            migrations[FIRST]["checksum"],
                    },
                    {
                        "number": TARGET,
                        "from_schema": FIRST,
                        "to_schema": TARGET,
                        "compatibility":
                            "forward-compatible",
                        "path": (
                            "web/database/migrations/"
                            + migrations[TARGET]["filename"]
                        ),
                        "sha256":
                            migrations[TARGET]["checksum"],
                    },
                ],
            }),
            encoding="utf-8",
        )

        state_root = root / "state"

        migration_state = (
            state_root
            / "migrations"
            / self.sha
        )

        migration_state.mkdir(parents=True)

        (
            state_root / "state.json"
        ).write_text(
            json.dumps({
                "active_slot": "green",
                "known_good_release": {
                    "sha": self.sha,
                    "slot": "green",
                    "schema": TARGET,
                },
                "history": [
                    {
                        "release_sha": self.sha,
                        "status": "known_good",
                        "phase":
                            "post_migration_workers_refreshed",
                        "schema": {
                            "observed": TARGET,
                        },
                    }
                ],
            }),
            encoding="utf-8",
        )

        (
            migration_state / "automation.json"
        ).write_text(
            json.dumps({
                "release_sha": self.sha,
                "status": "completed",
                "phase":
                    "post_migration_validation_complete",
                "observed_schema": TARGET,
            }),
            encoding="utf-8",
        )

        (
            migration_state / "execution.json"
        ).write_text(
            json.dumps({
                "release_sha": self.sha,
                "status": "completed",
                "phase": "complete",
                "observed_schema": TARGET,
                "migrations": [
                    {
                        "number": FIRST,
                        "status": "applied",
                        "checksum":
                            migrations[FIRST]["checksum"],
                    },
                    {
                        "number": TARGET,
                        "status": "applied",
                        "checksum":
                            migrations[TARGET]["checksum"],
                    },
                ],
            }),
            encoding="utf-8",
        )

        return (
            repository,
            state_root,
            migrations[TARGET]["checksum"],
        )

    def reader(self, url, _headers):
        if "application_schema_state" in url:
            return [
                {
                    "schema_version":
                        self.live_schema
                }
            ]

        if url.endswith("/health/version"):
            return {
                "release_sha": self.sha
            }

        return {"ready": True}

    def arguments(
        self,
        repository,
        state_root,
        runner,
        checksum,
        **overrides,
    ):
        values = {
            "release_sha": self.sha,
            "repository_root": repository,
            "state_root": state_root,
            "supabase_bin": "supabase",
            "confirmation":
                f"{TARGET:03d}:{checksum}",
            "dry_run": False,
            "environ": {
                "SUPABASE_URL":
                    "https://project.invalid",
                "SUPABASE_SERVICE_KEY":
                    "secret",
                "MADAR_SUPABASE_PROJECT_REF":
                    "fixture-project",
            },
            "runner": runner,
            "json_reader": self.reader,
        }

        values.update(overrides)
        return values

    def test_repair_is_checksum_guarded_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = (
                self.fixture(Path(directory))
            )

            runner = FakeRunner(
                repository,
                self.sha,
            )

            self.live_schema = TARGET

            arguments = self.arguments(
                repository,
                state_root,
                runner,
                checksum,
            )

            first = self.module.run(**arguments)
            second = self.module.run(**arguments)

        self.assertEqual(
            first["action"],
            "reconciled",
        )

        self.assertEqual(
            second["action"],
            "already_reconciled",
        )

        self.assertEqual(
            runner.repairs,
            1,
        )

        self.assertFalse(
            first["tenant_data_touched"]
        )

        self.assertEqual(
            first["migration"],
            TARGET,
        )

    def test_live_schema_must_reach_target_before_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = (
                self.fixture(Path(directory))
            )

            runner = FakeRunner(
                repository,
                self.sha,
            )

            self.live_schema = FIRST

            with self.assertRaisesRegex(
                RuntimeError,
                "live_schema_not_at_target",
            ):
                self.module.run(
                    **self.arguments(
                        repository,
                        state_root,
                        runner,
                        checksum,
                    )
                )

        self.assertEqual(
            runner.repairs,
            0,
        )

    def test_completed_coordinator_evidence_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = (
                self.fixture(Path(directory))
            )

            automation = (
                state_root
                / "migrations"
                / self.sha
                / "automation.json"
            )

            automation.write_text(
                json.dumps({
                    "status": "running",
                    "phase":
                        "post_migration_validation",
                }),
                encoding="utf-8",
            )

            runner = FakeRunner(
                repository,
                self.sha,
            )

            self.live_schema = TARGET

            with self.assertRaisesRegex(
                RuntimeError,
                "automation_not_complete",
            ):
                self.module.run(
                    **self.arguments(
                        repository,
                        state_root,
                        runner,
                        checksum,
                    )
                )

        self.assertEqual(
            runner.repairs,
            0,
        )

    def test_wrong_linked_project_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = (
                self.fixture(Path(directory))
            )

            runner = FakeRunner(
                repository,
                self.sha,
            )

            self.live_schema = TARGET

            environment = {
                "SUPABASE_URL":
                    "https://project.invalid",
                "SUPABASE_SERVICE_KEY":
                    "secret",
                "MADAR_SUPABASE_PROJECT_REF":
                    "different-project",
            }

            with self.assertRaisesRegex(
                RuntimeError,
                "linked_project_mismatch",
            ):
                self.module.run(
                    **self.arguments(
                        repository,
                        state_root,
                        runner,
                        checksum,
                        environ=environment,
                    )
                )

        self.assertEqual(
            runner.repairs,
            0,
        )

    def test_wrong_release_version_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = (
                self.fixture(Path(directory))
            )

            release = (
                repository
                / "web/deployment/releases/release.json"
            )

            contract = json.loads(
                release.read_text(
                    encoding="utf-8"
                )
            )

            contract["schema"]["target"] = (
                TARGET + 1
            )

            release.write_text(
                json.dumps(contract),
                encoding="utf-8",
            )

            runner = FakeRunner(
                repository,
                self.sha,
            )

            self.live_schema = TARGET

            with self.assertRaisesRegex(
                RuntimeError,
                "release_contract_invalid",
            ):
                self.module.run(
                    **self.arguments(
                        repository,
                        state_root,
                        runner,
                        checksum,
                    )
                )

        self.assertEqual(
            runner.repairs,
            0,
        )

    def test_wrong_migration_checksum_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = (
                self.fixture(Path(directory))
            )

            migration = (
                repository
                / "web/database/migrations"
                / f"{TARGET:03d}_fixture.sql"
            )

            migration.write_text(
                "begin; select 999; commit;\n",
                encoding="utf-8",
            )

            runner = FakeRunner(
                repository,
                self.sha,
            )

            self.live_schema = TARGET

            with self.assertRaisesRegex(
                RuntimeError,
                "migration_checksum_mismatch",
            ):
                self.module.run(
                    **self.arguments(
                        repository,
                        state_root,
                        runner,
                        checksum,
                    )
                )

        self.assertEqual(
            runner.repairs,
            0,
        )

    def test_wrong_candidate_commit_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = (
                self.fixture(Path(directory))
            )

            runner = FakeRunner(
                repository,
                "b" * 40,
            )

            self.live_schema = TARGET

            with self.assertRaisesRegex(
                RuntimeError,
                "release_sha_mismatch",
            ):
                self.module.run(
                    **self.arguments(
                        repository,
                        state_root,
                        runner,
                        checksum,
                    )
                )

        self.assertEqual(
            runner.repairs,
            0,
        )

    def test_wrong_confirmation_is_refused_before_ledger_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            repository, state_root, checksum = (
                self.fixture(Path(directory))
            )

            runner = FakeRunner(
                repository,
                self.sha,
            )

            self.live_schema = TARGET

            with self.assertRaisesRegex(
                RuntimeError,
                "confirmation_mismatch",
            ):
                self.module.run(
                    **self.arguments(
                        repository,
                        state_root,
                        runner,
                        checksum,
                        confirmation=f"{TARGET:03d}:wrong",
                    )
                )

        self.assertEqual(
            runner.repairs,
            0,
        )


if __name__ == "__main__":
    unittest.main()

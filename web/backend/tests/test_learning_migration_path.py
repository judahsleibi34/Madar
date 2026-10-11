"""Preparation contract: preserve142 and reject unreviewed branch execution."""
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

WEB_ROOT = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(WEB_ROOT))
from deployment.lib import learning_migration_path as route
from deployment.lib.migration_executor import MigrationManifest, LockedMigrationExecutor
from test_migration_executor import FakeConnection


class LearningMigrationPathTests(unittest.TestCase):
    def test_privileged_standalone_executor_import_remains_supported(self):
        library = str(WEB_ROOT / "deployment/lib")
        result = subprocess.run([sys.executable, "-I", "-c",
            f"import sys; sys.path.insert(0, {library!r}); from migration_executor import MigrationManifest"],
            capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def fixture(self, root):
        descriptor = root / route.CONTRACT_PATH
        descriptor.parent.mkdir(parents=True)
        descriptor.write_bytes((WEB_ROOT / "deployment/releases/learning-141-143-path.json").read_bytes())
        manifest = root / route.MANIFEST_PATH
        entry = {"number": 143, "from_schema": 141, "to_schema": 143,
                 "path": route.SQL_PATH, "sha256": "a" * 64,
                 "compatibility": "forward-compatible"}
        manifest.write_text(json.dumps({"release_sha": "STAGING", "migrations": [entry]}))
        return manifest

    def finalized_fixture(self, root):
        manifest = self.fixture(root)
        sql = root / route.SQL_PATH
        sql.parent.mkdir(parents=True)
        sql.write_text("-- MIGRATION_TO=143\n")
        mirror = root / route.SQL_PATH.replace("/database/", "/supabase/")
        mirror.parent.mkdir(parents=True)
        mirror.write_bytes(sql.read_bytes())
        raw = json.loads(manifest.read_text())
        raw["migrations"][0]["sha256"] = hashlib.sha256(sql.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(raw))
        bridge = root / route.BRIDGE_PATH
        bridge.write_bytes((WEB_ROOT / 'deployment/releases/schema-141-143-learning-bridge.json').read_bytes())
        contract = route.load_contract(root)
        contract.update(status="finalized", execution_authority=True,
                        sql_sha256=raw["migrations"][0]["sha256"],
                        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
        return manifest, contract

    def test_finalized_source_route_is_exact_and_remains_unselected(self):
        installer = (WEB_ROOT / "deployment/bin/madar-install-control-plane").read_text()
        self.assertIn("lib/learning_migration_path.py",installer)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for relative in [route.CONTRACT_PATH,route.MANIFEST_PATH,route.BRIDGE_PATH,route.SQL_PATH,route.SQL_PATH.replace('/database/','/supabase/')]:
                source=WEB_ROOT/relative.removeprefix('web/')
                if not source.exists():source=Path('/app')/relative.removeprefix('web/')
                target=root/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
            contract=route.load_contract(root)
            self.assertEqual(contract['status'],'finalized')
            manifest=MigrationManifest.load(root/route.MANIFEST_PATH,root)
            self.assertEqual([item.number for item in manifest.migrations],[143])
            self.assertEqual(manifest.excluded_schemas,(142,))
        active=json.loads((WEB_ROOT/'deployment/releases/release.json').read_text())
        self.assertEqual(active['schema']['target'],115)
        self.assertNotIn('migration_manifest',active)

    def test_reserved_descriptor_still_rejects_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest=self.fixture(root)
            contract=route.load_contract(root)
            contract.update(status='reserved',execution_authority=False,manifest_sha256=None,sql_sha256=None)
            with patch.object(route,'load_contract',return_value=contract):
                with self.assertRaisesRegex(ValueError,'reserved, not executable'):
                    MigrationManifest.load(manifest,root)

    def test_descriptor_mutation_cannot_activate_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            path = root / route.CONTRACT_PATH
            raw = json.loads(path.read_text())
            raw.update(status="finalized", execution_authority=True)
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                route.load_contract(root)

    def test_unknown_gap_remains_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.fixture(root)
            raw = json.loads(path.read_text())
            raw["migrations"][0].update(number=144, to_schema=144)
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "transition is invalid"):
                MigrationManifest.load(path, root)

    def test_future_finalized_contract_executes_only143_and_rejects142(self):
        # Fake connections test executor control flow. Real SQL preservation is
        # exercised separately by the marked disposable rehearsal.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, contract = self.finalized_fixture(root)
            with patch.object(route, "load_contract", return_value=contract):
                manifest = MigrationManifest.load(path, root)
            self.assertTrue(manifest.accepts_schema(141))
            self.assertTrue(manifest.accepts_schema(143))
            self.assertFalse(manifest.accepts_schema(142))
            for schema in (140, 142, 144):
                connection = FakeConnection(schema=schema)
                with self.assertRaisesRegex(RuntimeError, "unexpected_schema"):
                    LockedMigrationExecutor(connection_factory=lambda: connection,
                        manifest=manifest, state_file=root / "state.json", backup_dir=root,
                        backup_verifier=lambda _: None).run()
                self.assertEqual(connection.applied, [])
            connection = FakeConnection(schema=141)
            events = []
            result = LockedMigrationExecutor(connection_factory=lambda: connection,
                manifest=manifest, state_file=root / "state.json", backup_dir=root,
                backup_verifier=lambda _: events.append("backup_verified")).run()
            self.assertEqual(events, ["backup_verified"])
            self.assertEqual(connection.applied, [143])
            self.assertEqual(result["observed_schema"], 143)
            resumed = FakeConnection(schema=143)
            result = LockedMigrationExecutor(connection_factory=lambda: resumed,
                manifest=manifest, state_file=root / "resume.json", backup_dir=root,
                backup_verifier=lambda _: None).run()
            self.assertEqual(resumed.applied, [])
            self.assertEqual(result["migrations"][0]["status"], "already_applied")

    def test_future_contract_still_requires_verified_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, contract = self.finalized_fixture(root)
            with patch.object(route, "load_contract", return_value=contract):
                manifest = MigrationManifest.load(path, root)
            with self.assertRaisesRegex(RuntimeError, "backup_not_verified"):
                LockedMigrationExecutor(connection_factory=lambda: self.fail("DB must not open"),
                    manifest=manifest, state_file=root / "state.json", backup_dir=root,
                    backup_verifier=lambda _: (_ for _ in ()).throw(RuntimeError("backup_not_verified"))).run()

    def test_future_contract_rejects_wrong_manifest_and_sql(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, contract = self.finalized_fixture(root)
            with patch.object(route, "load_contract", return_value=contract):
                wrong = path.with_name("migrations-other.json")
                wrong.write_bytes(path.read_bytes())
                with self.assertRaisesRegex(ValueError, "manifest path invalid"):
                    MigrationManifest.load(wrong, root)
                (root / route.SQL_PATH).write_text("changed SQL")
                with self.assertRaisesRegex(ValueError, "SQL checksum/mirror mismatch"):
                    MigrationManifest.load(path, root)

    def test_exchange_cannot_be_inserted_into_future_learning_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, contract = self.finalized_fixture(root)
            raw = json.loads(path.read_text())
            raw["migrations"].insert(0, {**raw["migrations"][0], "number": 142,
                                       "from_schema": 141, "to_schema": 142})
            path.write_text(json.dumps(raw))
            contract["manifest_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            with patch.object(route, "load_contract", return_value=contract):
                with self.assertRaisesRegex(ValueError, "manifest transition invalid"):
                    MigrationManifest.load(path, root)

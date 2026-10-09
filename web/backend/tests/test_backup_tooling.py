import hashlib
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
REHEARSAL_PATH = ROOT / "scripts" / "rehearse_backup.py"
spec = importlib.util.spec_from_file_location("rehearse_backup", REHEARSAL_PATH)
rehearsal = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(rehearsal)


class CoordinatedCheckpointTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('coordinated_backup_support', ROOT/'scripts/backup_support.py')
        self.backup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.backup)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root/'coordinated'
        self.directory.mkdir(mode=0o700)
        purposes = ['database_dump', 'roles', 'native_storage', 'native_configuration',
                    'function_cache', 'managed_storage', 'production_configuration',
                    'controller_state', 'images', 'schema_ledgers', 'auth_metadata',
                    'independent_restore']
        self.entries = []
        for purpose in purposes:
            path = self.directory/purpose
            path.write_bytes(b'unit-test-only recovery artifact')
            path.chmod(0o600)
            self.entries.append({'purpose':purpose,'path':purpose,'size':path.stat().st_size,
                                 'sha256':self.backup.digest(path)})
        checks = ['schema115', 'all_public_tables', 'auth', 'mfa', 'foreign_keys',
                  'storage_metadata', 'storage_bytes', 'storage_xattrs', 'asset_delivery',
                  'tenant_isolation', 'runtime_readiness', 'no_migrations', 'no_workers',
                  'no_email', 'private_topology']
        self.proof = {'checks':dict.fromkeys(checks, True),
                      'database_dump_sha256':self.entries[0]['sha256']}
        self.write_proof()
        self.manifest = {'schema':115,'restore_verified':True,'files':self.entries}
        self.write_manifest()

    def write_manifest(self):
        path = self.directory/'manifest.json'
        path.write_text(json.dumps(self.manifest))
        path.chmod(0o600)

    def write_proof(self):
        path = self.directory/'independent_restore'
        path.write_text(json.dumps(self.proof))
        entry = next(x for x in self.entries if x['purpose']=='independent_restore')
        entry.update(size=path.stat().st_size, sha256=self.backup.digest(path))

    def test_logical_native_role_names_are_nologin_only(self):
        import importlib.util
        script = Path(__file__).resolve().parents[2] / "scripts" / "rehearse_backup.py"
        spec = importlib.util.spec_from_file_location("native_role_rehearsal", script)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        result = module.logical_role_prerequisites(Path("/unused"), {}, additional_roles=("supabase_auth_admin", "postgres"))
        self.assertIn('CREATE ROLE "supabase_auth_admin" NOLOGIN;', result)
        self.assertNotIn('CREATE ROLE "postgres"', result)
        with self.assertRaises(module.RehearsalError):
            module.logical_role_prerequisites(Path("/unused"), {}, additional_roles=("unsafe;SQL",))

    def test_complete_bound_private_checkpoint(self):
        self.backup.verify_coordinated_checkpoint(self.root)

    def test_corrupt_native_storage_rejected(self):
        (self.directory/'native_storage').write_bytes(b'changed')
        with self.assertRaisesRegex(self.backup.BackupError,'integrity_failed'):
            self.backup.verify_coordinated_checkpoint(self.root)

    def test_missing_configuration_rejected(self):
        self.manifest['files'] = [e for e in self.entries if e['purpose']!='native_configuration']
        self.write_manifest()
        with self.assertRaisesRegex(self.backup.BackupError,'incomplete'):
            self.backup.verify_coordinated_checkpoint(self.root)

    def test_changed_dump_invalidates_restore_proof(self):
        self.proof['database_dump_sha256'] = '0'*64
        self.write_proof(); self.write_manifest()
        with self.assertRaisesRegex(self.backup.BackupError,'restore_proof_invalid'):
            self.backup.verify_coordinated_checkpoint(self.root)

    def test_failed_runtime_or_unverified_restore_rejected(self):
        self.proof['checks']['runtime_readiness'] = False
        self.write_proof(); self.write_manifest()
        with self.assertRaisesRegex(self.backup.BackupError,'restore_proof_invalid'):
            self.backup.verify_coordinated_checkpoint(self.root)
        self.manifest['restore_verified'] = False; self.write_manifest()
        with self.assertRaisesRegex(self.backup.BackupError,'restore_unverified'):
            self.backup.verify_coordinated_checkpoint(self.root)

    def test_public_escrow_and_path_escape_rejected(self):
        (self.directory/'native_configuration').chmod(0o644)
        with self.assertRaisesRegex(self.backup.BackupError,'integrity_failed'):
            self.backup.verify_coordinated_checkpoint(self.root)
        self.entries[3]['path']='../native_configuration'; self.write_manifest()
        with self.assertRaisesRegex(self.backup.BackupError,'path_invalid'):
            self.backup.verify_coordinated_checkpoint(self.root)

    def test_exact_loopback_provider_with_session_database_is_supported(self):
        environment = {'SUPABASE_URL':'http://127.0.0.1:18000',
            'SUPABASE_SERVICE_KEY':'synthetic-only', 'PGHOST':'127.0.0.1',
            'PGPORT':'15432', 'PGDATABASE':'postgres', 'PGSSLMODE':'disable',
            'PGUSER':'postgres.synthetic'}
        with mock.patch.dict(os.environ, environment, clear=True):
            # Validation reaches inventory access; no network or secret is used.
            with self.assertRaises(FileNotFoundError):
                self.backup.provider_snapshot(self.root, 'madar-20261008T000000Z')

    def test_plaintext_provider_requires_exact_loopback_and_session_route(self):
        environment = {'SUPABASE_URL':'http://127.0.0.1:18000',
            'SUPABASE_SERVICE_KEY':'synthetic-only', 'PGHOST':'127.0.0.1',
            'PGPORT':'15432', 'PGDATABASE':'postgres', 'PGSSLMODE':'disable',
            'PGUSER':'postgres.synthetic'}
        for override in ({'SUPABASE_URL':'http://example.invalid'},
                         {'SUPABASE_URL':'http://127.0.0.1:18001'},
                         {'PGPORT':'16543'}, {'PGHOST':'example.invalid'},
                         {'PGUSER':'postgres'}, {'PGDATABASE':'other'},
                         {'PGSSLMODE':'require'}):
            with self.subTest(override=override), mock.patch.dict(
                    os.environ, {**environment, **override}, clear=True):
                with self.assertRaisesRegex(self.backup.BackupError,'provider_configuration_invalid'):
                    self.backup.provider_snapshot(self.root, 'madar-20261008T000000Z')


class BackupToolingTests(unittest.TestCase):
    def run_script(self, name, *args, env=None):
        return subprocess.run(
            ["bash", str(ROOT / "scripts" / name), *map(str, args)],
            cwd=ROOT,
            env={"PATH": os.environ.get("PATH", ""), **(env or {})},
            text=True,
            capture_output=True,
            check=False,
        )

    def fixture(self, root):
        backup = Path(root) / "madar-20260720T000000Z"
        for name in ("builder-assets", "private-uploads", "generated-artifacts", "avatars"):
            (backup / "files" / name).mkdir(parents=True)
        (backup / "database.dump").write_bytes(b"fixture database")
        (backup / "backup.env").write_text("MADAR_BACKUP_FORMAT=1\n", encoding="utf-8")
        lines = []
        for path in sorted(p for p in backup.rglob("*") if p.is_file()):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.relative_to(backup)}\n")
        (backup / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")
        return backup

    def backup_environment(self, root, timestamp="20260720T000000Z"):
        root = Path(root)
        source_root = root / "source"
        environment = {
            "MADAR_BACKUP_DIR": str(root / "backups"),
            "PGHOST": "source.invalid",
            "PGPORT": "5432",
            "PGUSER": "backup",
            "PGPASSWORD": "synthetic-test-password",
            "PGDATABASE": "madar",
            "MADAR_BACKUP_TIMESTAMP": timestamp,
            "MADAR_PROVIDER_BACKUP_REQUIRED": "false",
        }
        for key, name in (
            ("MADAR_BUILDER_ASSETS_DIR", "builder-assets"),
            ("MADAR_PRIVATE_UPLOADS_DIR", "private-uploads"),
            ("MADAR_GENERATED_ARTIFACTS_DIR", "generated-artifacts"),
            ("MADAR_AVATARS_DIR", "avatars"),
        ):
            source = source_root / name
            source.mkdir(parents=True)
            (source / "fixture.txt").write_text(name, encoding="utf-8")
            environment[key] = str(source)
        return environment

    def fake_postgres_tools(self, root, *, succeeds=True):
        fake_bin = Path(root) / "fake-bin"
        fake_bin.mkdir()
        executable = fake_bin / "pg_dump"
        if succeeds:
            executable.write_text(
                "#!/bin/sh\n"
                "for arg in \"$@\"; do\n"
                "  case \"$arg\" in --file=*) printf fixture > \"${arg#*=}\";; esac\n"
                "done\n",
                encoding="utf-8",
            )
        else:
            executable.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        executable.chmod(0o700)
        pg_restore = fake_bin / "pg_restore"
        pg_restore.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        pg_restore.chmod(0o700)
        psql = fake_bin / "psql"
        psql.write_text(
            "#!/bin/sh\n"
            "case \"$*\" in *server_version*) printf '17.6\\n';; *) printf '82\\n';; esac\n",
            encoding="utf-8",
        )
        psql.chmod(0o700)
        return f"{fake_bin}:{os.environ.get('PATH', '')}"

    def test_backup_requires_environment(self):
        result = self.run_script("backup_madar.sh", "--dry-run")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MADAR_BACKUP_DIR", result.stderr)

    def test_exported_snapshot_preserves_archive_ownership_and_acl(self):
        with tempfile.TemporaryDirectory() as root:
            env = self.backup_environment(root)
            env["PATH"] = self.fake_postgres_tools(root)
            env["MADAR_BACKUP_SNAPSHOT"] = "00000001-00000002-1"
            arguments = Path(root) / "dump-arguments"
            executable = Path(root) / "fake-bin" / "pg_dump"
            executable.write_text(
                "#!/bin/sh\n"
                f"printf '%s\\n' \"$@\" > '{arguments}'\n"
                "for arg in \"$@\"; do\n"
                "  case \"$arg\" in --file=*) printf fixture > \"${arg#*=}\";; esac\n"
                "done\n"
            )
            result = self.run_script("backup_madar.sh", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            actual = arguments.read_text().splitlines()
            self.assertIn("--snapshot=00000001-00000002-1", actual)
            self.assertIn("--format=custom", actual)
            self.assertNotIn("--no-owner", actual)
            self.assertNotIn("--no-acl", actual)

    def test_invalid_exported_snapshot_is_not_published(self):
        with tempfile.TemporaryDirectory() as root:
            env = self.backup_environment(root)
            env["PATH"] = self.fake_postgres_tools(root)
            env["MADAR_BACKUP_SNAPSHOT"] = "invalid snapshot"
            result = self.run_script("backup_madar.sh", env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid exported snapshot", result.stderr)
            self.assertFalse((Path(root) / "backups" / "madar-20260720T000000Z").exists())

    def test_backup_dry_run_constructs_commands_without_executing(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.run_script("backup_madar.sh", "--dry-run", env={
                "MADAR_BACKUP_DIR": root,
                "PGHOST": "source.invalid",
                "PGPORT": "5432",
                "PGUSER": "backup",
                "PGPASSWORD": "synthetic-test-password",
                "PGDATABASE": "madar",
                "MADAR_BACKUP_TIMESTAMP": "20260720T000000Z",
            })
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pg_dump --format=custom", result.stdout)
        self.assertNotIn("source.invalid", result.stdout)

    def test_backup_is_published_only_after_verified_completion(self):
        with tempfile.TemporaryDirectory() as root:
            env = self.backup_environment(root)
            env["PATH"] = self.fake_postgres_tools(root)
            result = self.run_script("backup_madar.sh", env=env)
            published = Path(root) / "backups" / "madar-20260720T000000Z"

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((published / "BACKUP_COMPLETE").is_file())
            self.assertIn("MADAR_BACKUP_FORMAT=3", (published / "backup.env").read_text())
            self.assertTrue((published / "manifest.json").is_file())
            self.assertFalse(list((Path(root) / "backups").glob(".*.incomplete.*")))
            verified = self.run_script("verify_backup.sh", published, env={"PATH": env["PATH"]})
            self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_failed_backup_never_occupies_final_recovery_path(self):
        with tempfile.TemporaryDirectory() as root:
            env = self.backup_environment(root)
            env["PATH"] = self.fake_postgres_tools(root, succeeds=False)
            result = self.run_script("backup_madar.sh", env=env)
            backup_root = Path(root) / "backups"

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((backup_root / "madar-20260720T000000Z").exists())
            self.assertEqual(len(list(backup_root.glob(".*.incomplete.*"))), 0)

    def test_verifier_rejects_missing_member_and_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            backup = self.fixture(root)
            (backup / "files" / "avatars").rmdir()
            missing = self.run_script("verify_backup.sh", backup)
            self.assertIn("missing backup member", missing.stderr)
            (backup / "files" / "avatars").mkdir()
            (backup / "database.dump").write_bytes(b"tampered")
            mismatch = self.run_script("verify_backup.sh", backup)
            self.assertIn("checksum verification failed", mismatch.stderr)

    def test_restore_refuses_same_database_and_unsafe_target(self):
        with tempfile.TemporaryDirectory() as root:
            backup = self.fixture(root)
            common = {
                "MADAR_SOURCE_DATABASE_ID": "source",
                "MADAR_RESTORE_DATABASE_ID": "source",
                "MADAR_RESTORE_PGHOST": "localhost",
                "MADAR_RESTORE_PGPORT": "5432",
                "MADAR_RESTORE_PGUSER": "restore",
                "MADAR_RESTORE_PGPASSWORD": "synthetic-test-password",
                "MADAR_RESTORE_PGDATABASE": "madar_restore_test",
                "MADAR_RESTORE_CONFIRM_ISOLATED": "YES",
            }
            same = self.run_script("restore_madar.sh", "--dry-run", backup, env=common)
            self.assertIn("must differ", same.stderr)
            common["MADAR_RESTORE_DATABASE_ID"] = "other"
            common["MADAR_RESTORE_PGHOST"] = "prod.example.com"
            unsafe = self.run_script("restore_madar.sh", "--dry-run", backup, env=common)
            self.assertIn("not recognizably isolated", unsafe.stderr)

    def test_restore_dry_run_verifies_fixture(self):
        with tempfile.TemporaryDirectory() as root:
            backup = self.fixture(root)
            env = {
                "MADAR_SOURCE_DATABASE_ID": "production",
                "MADAR_RESTORE_DATABASE_ID": "isolated-test",
                "MADAR_RESTORE_PGHOST": "localhost",
                "MADAR_RESTORE_PGPORT": "5432",
                "MADAR_RESTORE_PGUSER": "restore",
                "MADAR_RESTORE_PGPASSWORD": "synthetic-test-password",
                "MADAR_RESTORE_PGDATABASE": "madar_restore_test",
                "MADAR_RESTORE_CONFIRM_ISOLATED": "YES",
                "PATH": self.fake_postgres_tools(root),
            }
            for name in ("BUILDER_ASSETS", "PRIVATE_UPLOADS", "GENERATED_ARTIFACTS", "AVATARS"):
                env[f"MADAR_RESTORE_{name}_DIR"] = str(Path(root) / name.lower())
            result = self.run_script("restore_madar.sh", "--dry-run", backup, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("pg_restore", result.stdout)

    def test_restore_preload_launches_no_scheduled_jobs(self):
        with tempfile.TemporaryDirectory() as root:
            backup = Path(root)
            (backup/'database.dump').write_bytes(b'unit fixture')
            (backup/'manifest.json').write_text('{"backup_id":"fixture","created_at":"fixture","database":{"schema_version":115}}')
            calls=[]
            def run(command, *, phase, **kwargs):
                calls.append((command,phase,kwargs))
                if phase == 'disabled_background_jobs': return 'f\n'
                return ''
            with mock.patch.object(rehearsal, 'run', side_effect=run), mock.patch.object(
                    rehearsal.subprocess, 'run', return_value=SimpleNamespace(returncode=0)):
                with self.assertRaisesRegex(rehearsal.RehearsalError, 'background_jobs_not_disabled'):
                    rehearsal.rehearse(backup,'postgres@sha256:'+'a'*64,postgres_preload=('pg_cron','pg_net'))
            startup=next(command for command,phase,_ in calls if phase=='database_start')
            self.assertIn('cron.launch_active_jobs=off', startup[-1])
            self.assertIn('pg_net.database_name=madar_restore_disabled', startup[-1])
            self.assertNotIn('role_prerequisites',[phase for _,phase,_ in calls])

    def test_restore_refuses_arbitrary_preload_code(self):
        with self.assertRaisesRegex(rehearsal.RehearsalError, 'unsupported_restore_preload'):
            rehearsal.rehearse(Path('/unneeded'), 'postgres@sha256:'+'a'*64, postgres_preload=('untrusted',))

    def test_coordinated_logical_roles_are_nologin_and_never_replay_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory)
            coordinated = backup / "coordinated"
            coordinated.mkdir()
            roles = coordinated / "1-roles.sql"
            roles.write_text("CREATE ROLE postgres;\nCREATE ROLE anon;\nCREATE ROLE authenticated;\n"
                             "CREATE ROLE service_role;\nCREATE ROLE supabase_auth_admin;\n"
                             "ALTER ROLE supabase_auth_admin PASSWORD 'fixture-secret';\n")
            import hashlib
            packet = {"files": [{"path": "1-roles.sql", "size": roles.stat().st_size,
                                  "sha256": hashlib.sha256(roles.read_bytes()).hexdigest()}]}
            (coordinated / "manifest.json").write_text(json.dumps(packet))
            sql = rehearsal.logical_role_prerequisites(backup, {"coordinated_checkpoint": "coordinated/manifest.json"})
            self.assertIn('CREATE ROLE "supabase_auth_admin" NOLOGIN;', sql)
            self.assertNotIn('CREATE ROLE "postgres"', sql)
            self.assertNotIn('PASSWORD', sql)
            self.assertNotIn('fixture-secret', sql)
            roles.write_text(roles.read_text() + '-- changed\n')
            with self.assertRaisesRegex(rehearsal.RehearsalError, 'inventory_changed'):
                rehearsal.logical_role_prerequisites(backup, {"coordinated_checkpoint": "coordinated/manifest.json"})

    def test_restore_failure_records_only_fixed_sanitized_category(self):
        result = SimpleNamespace(returncode=1, stdout='', stderr='role "fixture-secret" does not exist\nCOPY private values')
        with mock.patch.object(rehearsal.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(rehearsal.RehearsalError, '^restore:exit_1:missing_role$'):
                rehearsal.run(['fixture-command'], phase='restore')

    def test_rehearsal_attaches_stdin_only_for_stdin_driven_psql(self):
        with tempfile.TemporaryDirectory() as root:
            backup = Path(root) / "backup"
            for name in ("builder-assets", "private-uploads", "generated-artifacts", "avatars"):
                (backup / "files" / name).mkdir(parents=True)
            (backup / "database.dump").write_bytes(b"fixture database")
            (backup / "manifest.json").write_text(
                '{"backup_id":"fixture","created_at":"2026-09-22T00:00:00Z",'
                '"database":{"schema_version":102,"public_tables":0}}',
                encoding="utf-8",
            )
            migration = Path(root) / "migration.sql"
            migration.write_text("SELECT 1;\n", encoding="utf-8")
            outputs = {
                "restored_schema": "102\n",
                "metadata_validation": "schema=104\npublic_tables=0\ninvalid_indexes=0\nauth_users=0\n",
            }

            with (
                mock.patch.object(
                    rehearsal, "run",
                    side_effect=lambda command, *, phase, **kwargs: outputs.get(phase, ""),
                ) as run_mock,
                mock.patch.object(
                    rehearsal.subprocess, "run",
                    return_value=SimpleNamespace(returncode=0),
                ),
            ):
                rehearsal.rehearse(
                    backup,
                    "supabase/postgres@sha256:" + "a" * 64,
                    migration,
                    target_schema=104,
                )

            calls = {call.kwargs["phase"]: call for call in run_mock.call_args_list}
            stdin_call = calls["role_prerequisites"]
            self.assertIn("-i", stdin_call.args[0])
            self.assertIn("CREATE ROLE", stdin_call.kwargs["input"])
            migration_call = calls["isolated_migration"]
            self.assertNotIn("-i", migration_call.args[0])
            self.assertEqual(migration_call.args[0][-2:], ["--file", "/migration.sql"])

    def test_offhost_replication_refuses_an_unmounted_local_directory(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            backup = root / "madar-20260720T000000Z"
            mount = root / "drive"
            recipients = root / "recipients.txt"
            backup.mkdir()
            mount.mkdir()
            recipients.write_text("age1synthetic-public-recipient\n", encoding="utf-8")
            result = self.run_script("replicate_backup_offhost.sh", backup, env={
                "MADAR_OFFHOST_MOUNT": str(mount),
                "MADAR_OFFHOST_VOLUME_ID": "expected-drive",
                "MADAR_BACKUP_AGE_RECIPIENTS_FILE": str(recipients),
            })
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not a mounted filesystem", result.stderr)
            self.assertFalse((mount / "madar-encrypted").exists())

    def test_offhost_replication_requires_exact_volume_identity_before_writing(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            backup = root / "madar-20260720T000000Z"
            mount = root / "drive"
            recipients = root / "recipients.txt"
            fake_bin = root / "fake-bin"
            backup.mkdir()
            mount.mkdir()
            fake_bin.mkdir()
            recipients.write_text("age1synthetic-public-recipient\n", encoding="utf-8")
            (mount / ".madar-backup-volume").write_text("wrong-drive\n", encoding="utf-8")
            mountpoint = fake_bin / "mountpoint"
            mountpoint.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            mountpoint.chmod(0o700)
            findmnt = fake_bin / "findmnt"
            findmnt.write_text(f"#!/bin/sh\nprintf '%s\\n' '{mount}'\n", encoding="utf-8")
            findmnt.chmod(0o700)
            result = self.run_script("replicate_backup_offhost.sh", backup, env={
                "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
                "MADAR_OFFHOST_MOUNT": str(mount),
                "MADAR_OFFHOST_VOLUME_ID": "expected-drive",
                "MADAR_BACKUP_AGE_RECIPIENTS_FILE": str(recipients),
            })
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("identity does not match", result.stderr)
            self.assertFalse((mount / "madar-encrypted").exists())


if __name__ == "__main__":
    unittest.main()

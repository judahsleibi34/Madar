import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

WEB_ROOT=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
SCRIPT=WEB_ROOT/'scripts/check_forward_release.py'
spec=importlib.util.spec_from_file_location('local_supabase_release_validator',SCRIPT)
validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)


def initialize_history_fixture(root):
    """Real disposable Git history; never stages/commits the owner checkout.

    Original architecture, canonical main, and reconciliation are separate real
    commits. Test-only trusted boundaries refer to those independently built
    objects; no Git command or production integrity check is mocked.
    """
    import subprocess
    def git(*args):
        return subprocess.check_output(["git", "-c", "core.hooksPath=/dev/null", *args],
            cwd=root, stderr=subprocess.PIPE).decode().strip()
    def commit():
        git("add", "web"); git("commit", "-qm", "Independent synthetic history fixture")
        return git("rev-parse", "HEAD")
    git("init", "-q")
    git("config", "user.name", "Synthetic Test")
    git("config", "user.email", "synthetic@example.invalid")
    git("config", "commit.gpgsign", "false")
    git("remote", "add", "origin", "https://github.com/judahsleibi34/Madar.git")
    active = {p: p.read_bytes() for tree in ("database", "supabase")
              for p in (root / "web" / tree / "migrations").glob("*.sql")}
    for p in active:
        if int(p.name.split("_", 1)[0]) >= 147:
            p.unlink()
    old_paths = []
    for tree in ("database", "supabase"):
        for archived in (root / "web" / tree / "historical-architecture-146-150").glob("*.sql"):
            p = root / "web" / tree / "migrations" / archived.name
            p.write_bytes(archived.read_bytes()); old_paths.append(p)
    original = commit()
    for p in old_paths:
        p.unlink()
    for p, body in active.items():
        if int(p.name.split("_", 1)[0]) <= 156:
            p.write_bytes(body)
    canonical = commit()
    for p, body in active.items():
        p.write_bytes(body)
    record = root / "web/deployment/migration-history-reconciliation.json"
    value = json.loads(record.read_bytes()); value["authoritative_main"] = canonical
    record.write_text(json.dumps(value))
    evidence = commit()
    blob = git("rev-parse", evidence + ":web/deployment/migration-history-reconciliation.json")
    return {"ARCHITECTURE_HISTORY": original, "CANONICAL_HISTORY": canonical,
            "RECONCILIATION_EVIDENCE": evidence, "RECONCILIATION_RECORD_BLOB": blob}


class LocalSupabaseReleaseContractTests(unittest.TestCase):
    def test_unselected_schema115_bridge_preserves_every_historical_sql_binding(self):
        from hashlib import sha256
        releases=WEB_ROOT/'deployment/releases'
        old_path=releases/'migrations-115-136.json'
        self.assertEqual(sha256(old_path.read_bytes()).hexdigest(),
                         '7ce4527369df9f48be3830074e94838686bd74f9895d4a5480d67b78f5860e7f')
        old=json.loads(old_path.read_text())
        new=json.loads((releases/'migrations-116-136.json').read_text())
        self.assertEqual(new['migrations'],old['migrations'][1:])
        self.assertEqual([entry['number'] for entry in new['migrations']],list(range(116,137)))
        self.assertEqual(new['migrations'][0]['from_schema'],115)
        bridge=json.loads((releases/'schema-115-136-bridge.json').read_text())
        self.assertTrue(validator.schema115_bridge_valid(bridge))
        self.assertEqual(json.loads((releases/'schema-114-136-bridge.json').read_text())['schema']['compatible_min'],114)
        for key,value in [('compatible_min',114),('compatible_max',135),('target',135),('rollback_compatible_max',136)]:
            self.assertFalse(validator.schema115_bridge_valid({**bridge,'schema':{**bridge['schema'],key:value}}))
        self.assertFalse(validator.schema115_bridge_valid({**bridge,'migration_manifest':'migrations-115-136.json'}))

    def test_retained_exact_schema115_candidate_does_not_select_migrations(self):
        release=json.loads((WEB_ROOT/'deployment/releases/schema-115-local.json').read_text())
        self.assertEqual(release['deployment_profile'],'local-supabase-schema115')
        self.assertEqual(release['migration_policy'],'none')
        self.assertNotIn('migration_manifest',release)
        self.assertEqual(release['schema'],{'compatible_min':115,'compatible_max':115,'target':115,'migration_class':'none','rollback_compatible_min':115,'rollback_compatible_max':115})

    def test_retained_schema115_to136_contract_remains_exact(self):
        release=json.loads((WEB_ROOT/'deployment/releases/schema-115-136-bridge.json').read_text())
        self.assertTrue(validator.schema115_bridge_valid(release))
        self.assertEqual(release['migration_manifest'],'migrations-116-136.json')

    def test_validator_rejects_automatic_policy_and_schema_drift(self):
        import shutil
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);release_dir=root/'web/deployment/releases';release_dir.mkdir(parents=True)
            shutil.copytree(WEB_ROOT/'deployment/releases',release_dir,dirs_exist_ok=True)
            for tree in ['database','supabase']:
                target=WEB_ROOT/tree
                if not target.exists():target=Path('/workspace')/tree
                shutil.copytree(target,root/'web'/tree)
            # The new captured-source gate deliberately rejects mutable path
            # aliases: use real fixture trees while retaining every assertion.
            self.assertEqual(validator.validate(root),[])
            original=json.loads((release_dir/'schema-115-local.json').read_text())
            for field,value in [('migration_policy','automatic-after-known-good-backup-first-forward-repair'),('migration_manifest','migrations-115-116.json')]:
                edited={**original,field:value};(release_dir/'release.json').write_text(json.dumps(edited))
                self.assertTrue(validator.validate(root))
            for field in ['target','compatible_min','compatible_max','rollback_compatible_min','rollback_compatible_max']:
                edited={**original,'schema':{**original['schema'],field:116}};(release_dir/'release.json').write_text(json.dumps(edited))
                self.assertTrue(validator.validate(root))

    def test_exact_new_bridge_selection_is_valid_but_history_rewrite_is_not(self):
        import shutil
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);release_dir=root/'web/deployment/releases';release_dir.mkdir(parents=True)
            shutil.copytree(WEB_ROOT/'deployment/releases',release_dir,dirs_exist_ok=True)
            for tree in ('database','supabase'):
                source=WEB_ROOT/tree
                if not source.exists():source=Path('/workspace')/tree
                shutil.copytree(source,root/'web'/tree)
            bridge=json.loads((release_dir/'schema-115-136-bridge.json').read_text())
            (release_dir/'release.json').write_text(json.dumps(bridge))
            self.assertEqual(validator.validate(root),[])
            path=release_dir/'migrations-116-136.json';new=json.loads(path.read_text())
            new['migrations'].insert(0,json.loads((release_dir/'migrations-115-136.json').read_text())['migrations'][0])
            path.write_text(json.dumps(new))
            self.assertTrue(validator.validate(root))


    def test_exact_candidate_policy_cannot_create_backup_or_execute_SQL(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from test_automatic_migration_control_plane import load_release_cli
        module=load_release_cli()
        release=json.loads((WEB_ROOT/'deployment/releases/schema-115-local.json').read_text())
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);release_dir=root/'web/deployment/releases';release_dir.mkdir(parents=True)
            (release_dir/'release.json').write_text(json.dumps(release))
            state=root/'state';state.mkdir()
            sha='a'*40
            (state/'state.json').write_text(json.dumps({'active_slot':'green','known_good_release':{'sha':sha,'slot':'green'},'in_progress_release':None,'rollback_failure':None}))
            def forbidden(*args,**kwargs):raise AssertionError('database or backup execution is forbidden')
            operations=SimpleNamespace(release_root=root,verify_source=lambda sha:None,schema_version=forbidden)
            compatibility=module.Compatibility.load(release_dir/'release.json')
            with patch.object(module,'WEB_ROOT',root/'web'),patch.object(module,'LockedMigrationExecutor',side_effect=forbidden),patch.object(module,'_create_verified_migration_backup',side_effect=forbidden):
                result=module.automatic_migrate_known_good(sha=sha,state_root=state,compatibility=compatibility,operations=operations)
            self.assertEqual(result['status'],'not_requested')
            self.assertFalse((state/'migrations').exists())

    def test_retained_main_bridge_stays_checksum_valid_without_being_selected(self):
        from hashlib import sha256
        releases = WEB_ROOT / 'deployment/releases'
        manifest = releases / 'migrations-115-135.json'
        self.assertEqual(sha256(manifest.read_bytes()).hexdigest(),
                         'fe1258bab5f6359a598edc9d34f66e20555f93c5ce5fe911ec13d88b8bd4d7ae')
        bridge = json.loads((releases / 'schema-114-135-bridge.json').read_text())
        self.assertEqual(bridge['schema']['target'], 135)
        self.assertEqual(bridge['migration_manifest'], manifest.name)
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'web').mkdir()
            shutil.copytree(WEB_ROOT/'deployment',root/'web/deployment')
            for tree in ['database','supabase']:
                target=WEB_ROOT/tree
                if not target.exists():target=Path('/workspace')/tree
                shutil.copytree(target,root/'web'/tree)
            self.assertEqual(validator.validate(root), [])

    def test_future_namespace_tampering_is_rejected_by_both_validators(self):
        import shutil
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for subtree in ['deployment/releases', 'database/migrations', 'supabase/migrations', 'database/historical-architecture-146-150', 'supabase/historical-architecture-146-150']:
                source = WEB_ROOT / subtree
                if not source.exists(): source = Path('/workspace') / subtree
                shutil.copytree(source, root / 'web' / subtree)
            shutil.copyfile(WEB_ROOT/'deployment/migration-history-reconciliation.json',root/'web/deployment/migration-history-reconciliation.json')
            spec = importlib.util.spec_from_file_location('namespace_validator', WEB_ROOT / 'scripts/check_migrations.py')
            namespace = importlib.util.module_from_spec(spec); spec.loader.exec_module(namespace)
            boundaries = initialize_history_fixture(root)
            trees = {label:root / 'web' / label / 'migrations' for label in ['database', 'supabase']}
            def namespace_errors():
                errors=[]
                with patch.object(namespace, 'REPO_ROOT', root / 'web'), patch.object(namespace, 'TREE_PATHS', trees), patch.multiple(namespace, **boundaries):
                    namespace.check_production_lineage(errors)
                return errors
            self.assertEqual(namespace_errors(), [])
            for number in [116, 117, 135, 136, 137, 138, 139, 140, 141, 142]:
                path = next(trees['database'].glob(str(number) + '_*.sql'))
                original = path.read_bytes()
                path.write_bytes(original + b'\n-- unreviewed alteration\n')
                self.assertTrue(validator.validate(root))
                self.assertTrue(namespace_errors())
                path.write_bytes(original)
            unexpected = trees['database'] / '143_unreviewed.sql'
            unexpected.write_text('begin; commit;')
            self.assertTrue(validator.validate(root)); self.assertTrue(namespace_errors())
            unexpected.unlink()
            manifest = root / 'web/deployment/releases/migrations-115-135.json'
            manifest.write_text(manifest.read_text() + '\n')
            self.assertTrue(validator.validate(root)); self.assertTrue(namespace_errors())


class RelocationBoundaryTests(unittest.TestCase):
    """Independent synthetic bytes; no golden result generated by the validator."""
    def setUp(self):
        import sys
        sys.path.insert(0, str(WEB_ROOT))
        spec = importlib.util.spec_from_file_location("relocation_namespace", WEB_ROOT / "scripts/check_migrations.py")
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)

    def fixture(self):
        from hashlib import sha256
        h = lambda b: sha256(b).hexdigest()
        # Independently spelled names, not imported from production mapping.
        names = ["147_fence_notification_delivery_claims.sql", "148_guard_reservation_reactivation_capacity.sql",
                 "149_fence_notification_outbox_claims.sql", "150_fence_data_deletion_ownership.sql"]
        old, archives, canonical = {}, {}, {}
        for tree in ("database", "supabase"):
            old[f"web/{tree}/migrations/001_original.sql"] = b"original immutable SQL"
            canonical[f"web/{tree}/migrations/001_original.sql"] = b"original immutable SQL"
            for i, name in enumerate(names):
                old[f"web/{tree}/migrations/{name}"] = f"architecture original {i}".encode()
                archives[f"web/{tree}/historical-architecture-146-150/{name}"] = f"architecture original {i}".encode()
            for n in range(147, 157):
                canonical[f"web/{tree}/migrations/{n}_canonical.sql"] = f"canonical SQL {n}".encode()
        current = dict(canonical)
        rows = []
        for n in range(157, 161):
            body = f"separately reviewed forward SQL {n}".encode()
            p = f"web/database/migrations/{n}_forward.sql"
            current[p] = current[f"web/supabase/migrations/{n}_forward.sql"] = body
            rows.append({"number": n, "from_schema": n-1, "to_schema": n, "path": p, "sha256": h(body)})
        forward = json.dumps({"execution_status":"blocked_pending_protected_controller_reconciliation", "migrations":rows}).encode()
        lock = {"historical":{p:h(b) for p,b in archives.items()},
                "published_main":{p:h(b) for p,b in canonical.items() if "/001_" not in p},
                "forward_manifest_sha256":h(forward)}
        return dict(original=old, current=current, archived=archives, canonical=canonical, lock=lock, forward=forward)

    def test_exact_approved_relocation_and_forward_adaptation(self):
        self.module.verify_relocated_history(**self.fixture())

    def test_independent_negative_cases(self):
        import copy
        f = self.fixture()
        old = "web/database/migrations/147_fence_notification_delivery_claims.sql"
        arc = "web/database/historical-architecture-146-150/147_fence_notification_delivery_claims.sql"
        original = "web/database/migrations/001_original.sql"
        canonical = "web/database/migrations/147_canonical.sql"
        forward = "web/database/migrations/157_forward.sql"
        cases = {
            "unapproved_missing": lambda x: x["current"].pop(original),
            "unapproved_content": lambda x: x["current"].update({original:b"tampered"}),
            "old_path_reintroduced": lambda x: x["current"].update({old:x["original"][old]}),
            "old_path_collision": lambda x: x["current"].update({old:b"different SQL"}),
            "archive_missing": lambda x: x["archived"].pop(arc),
            "archive_changed": lambda x: x["archived"].update({arc:b"tampered"}),
            "archive_extra": lambda x: x["archived"].update({arc+".extra":b"extra"}),
            "archive_alias": lambda x: x["archived"].update({arc.replace("147_", "247_"):x["archived"][arc]}),
            "active_duplicate": lambda x: x["current"].update({"web/database/migrations/168_duplicate.sql":x["archived"][arc]}),
            "original_changed": lambda x: x["original"].update({old:b"tampered original"}),
            "canonical_missing": lambda x: x["current"].pop(canonical),
            "canonical_changed": lambda x: x["current"].update({canonical:b"tampered"}),
            "forward_changed": lambda x: x["current"].update({forward:b"tampered"}),
            "forward_missing": lambda x: x["current"].pop(forward),
            "forward_manifest_changed": lambda x: x.update(forward=x["forward"]+b" "),
            "lock_historical_changed": lambda x: x["lock"]["historical"].update({arc:"0"*64}),
            "lock_canonical_changed": lambda x: x["lock"]["published_main"].update({canonical:"0"*64}),
            "lock_forward_changed": lambda x: x["lock"].update(forward_manifest_sha256="0"*64),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                value = copy.deepcopy(f); mutate(value)
                with self.assertRaises(RuntimeError):
                    self.module.verify_relocated_history(**value)


class AccountRecoveryNamespaceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for subtree in ('deployment', 'database', 'supabase'):
            shutil.copytree(WEB_ROOT / subtree, self.root / 'web' / subtree)
        self.db = self.root / 'web/database/migrations/167_add_account_recovery_hold.sql'
        self.mirror = self.root / 'web/supabase/migrations' / self.db.name
        self.manifest = self.root / 'web/deployment/releases/migrations-166-167-account-recovery.json'
        self.bridge = self.root / 'web/deployment/releases/schema-166-167-account-recovery-bridge.json'

    def test_existing_exact_candidate_is_source_valid_but_not_executable(self):
        self.assertEqual(validator.validate(self.root), [])
        from deployment.lib.migration_executor import MigrationManifest
        with self.assertRaises(ValueError):
            MigrationManifest.load(self.manifest, self.root)
        self.assertEqual(json.loads(self.bridge.read_bytes())['migration_policy'],
                         'blocked-pending-account-erasure-acceptance')

    def test_missing_changed_duplicate_renamed_and_future_sql(self):
        original = self.db.read_bytes()
        for target in (self.db, self.mirror):
            with self.subTest(target=target.parent.name, change='missing'):
                target.unlink(); self.assertTrue(validator.validate(self.root)); target.write_bytes(original)
            with self.subTest(target=target.parent.name, change='modified'):
                target.write_bytes(original + b'\n-- changed\n')
                self.assertTrue(validator.validate(self.root)); target.write_bytes(original)
        for name in ('167_duplicate.sql', '168_unapproved.sql', '169_unapproved.sql'):
            with self.subTest(name=name):
                paths = [self.db.with_name(name), self.mirror.with_name(name)]
                for p in paths: p.write_bytes(original)
                self.assertTrue(validator.validate(self.root))
                for p in paths: p.unlink()
        renamed = self.db.with_name('167_wrong_identity.sql')
        self.db.rename(renamed)
        self.assertTrue(validator.validate(self.root))
        renamed.rename(self.db)
        self.db.write_bytes(original + b'\n-- same tamper in both mirrors\n')
        self.mirror.write_bytes(self.db.read_bytes())
        self.assertTrue(validator.validate(self.root))

    def test_manifest_and_blocked_bridge_identity_tampering(self):
        original = self.manifest.read_bytes(); bridge = self.bridge.read_bytes()
        changes = [('number', 168), ('from_schema', 165), ('to_schema', 168),
                   ('path', 'web/database/migrations/167_other.sql'),
                   ('sha256', '0' * 64), ('compatibility', 'forward-compatible')]
        for key, value in changes:
            with self.subTest(field=key):
                body = json.loads(original); body['migrations'][0][key] = value
                self.manifest.write_text(json.dumps(body)); self.assertTrue(validator.validate(self.root))
        self.manifest.write_bytes(original)
        for key, value in [('release_sha', 'CURRENT'), ('manifest_version', True), ('migrations', [])]:
            with self.subTest(field=key):
                body = json.loads(original); body[key] = value
                self.manifest.write_text(json.dumps(body)); self.assertTrue(validator.validate(self.root))
        self.manifest.write_bytes(original)
        for key, value in [('migration_policy', 'automatic'), ('deployment_profile', 'admitted'),
                           ('migration_manifest', 'other.json'), ('schema', {}),
                           ('release_metadata_version', True)]:
            with self.subTest(field=key):
                body = json.loads(bridge); body[key] = value
                self.bridge.write_text(json.dumps(body)); self.assertTrue(validator.validate(self.root))
        self.bridge.write_bytes(bridge)
        self.manifest.write_bytes(original.replace(b'"manifest_version": 1', b'"manifest_version": 1, "manifest_version": 1'))
        self.assertTrue(validator.validate(self.root))
        self.manifest.write_bytes(original)
        self.db.unlink(); self.db.symlink_to(self.mirror)
        self.assertTrue(validator.validate(self.root))


class RelocationGitIntegrationTests(unittest.TestCase):
    def setUp(self):
        import sys
        sys.path.insert(0, str(WEB_ROOT))
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for subtree in ('deployment', 'database', 'supabase'):
            shutil.copytree(WEB_ROOT / subtree, self.root / 'web' / subtree)
        self.boundaries = initialize_history_fixture(self.root)
        spec = importlib.util.spec_from_file_location('real_git_namespace', WEB_ROOT / 'scripts/check_migrations.py')
        self.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)

    def git(self, *args):
        import subprocess
        return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null', *args],
                                       cwd=self.root, stderr=subprocess.PIPE).decode().strip()

    def validate(self):
        from unittest.mock import patch
        with patch.multiple(self.module, **self.boundaries):
            return self.module.discover_reconciled_history(self.root)

    def commit(self):
        self.git('add', 'web'); self.git('commit', '-qm', 'Independent negative fixture')

    def test_real_history_passes_and_wrong_record_blob_fails(self):
        self.assertEqual(self.validate().target, 167)
        self.boundaries['RECONCILIATION_RECORD_BLOB'] = self.git('rev-parse', 'HEAD^{tree}')
        with self.assertRaisesRegex(RuntimeError, 'record_blob_changed'): self.validate()

    def test_missing_required_object_fails(self):
        sha = self.boundaries['ARCHITECTURE_HISTORY']
        (self.root / '.git/objects' / sha[:2] / sha[2:]).unlink()
        with self.assertRaisesRegex(RuntimeError, 'git_verification_failed'): self.validate()

    def test_shallow_ancestry_fails(self):
        (self.root / '.git/shallow').write_text(self.boundaries['RECONCILIATION_EVIDENCE'] + '\n')
        with self.assertRaisesRegex(RuntimeError, 'git_verification_failed'): self.validate()

    def test_self_consistent_candidate_manifest_cannot_redefine_trust(self):
        record = self.root / 'web/deployment/migration-history-reconciliation.json'
        value = json.loads(record.read_bytes()); value['controller_execution'] = 'APPROVED'
        record.write_text(json.dumps(value)); self.commit()
        with self.assertRaisesRegex(RuntimeError, 'evidence_changed'): self.validate()

    def test_extra_archive_rejected_even_if_not_sql(self):
        p = self.root / 'web/database/historical-architecture-146-150/extra.txt'
        p.write_text('unapproved'); self.commit()
        with self.assertRaisesRegex(RuntimeError, 'archive_evidence_changed'): self.validate()

    def test_generic_discovery_rejects_duplicate_after_relocation(self):
        source = self.root / 'web/database/migrations/167_add_account_recovery_hold.sql'
        source.with_name('167_duplicate.sql').write_bytes(b'-- duplicate numeric identity\n')
        self.commit()
        with self.assertRaisesRegex(RuntimeError, 'duplicate_or_noncanonical'): self.validate()

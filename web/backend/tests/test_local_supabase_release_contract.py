import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

WEB_ROOT=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
SCRIPT=WEB_ROOT/'scripts/check_forward_release.py'
spec=importlib.util.spec_from_file_location('local_supabase_release_validator',SCRIPT)
validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)


class LocalSupabaseReleaseContractTests(unittest.TestCase):
    def test_exact_schema115_candidate_does_not_select_migrations(self):
        release=json.loads((WEB_ROOT/'deployment/releases/release.json').read_text())
        self.assertEqual(release['deployment_profile'],'local-supabase-schema115')
        self.assertEqual(release['migration_policy'],'none')
        self.assertNotIn('migration_manifest',release)
        self.assertEqual(release['schema'],{'compatible_min':115,'compatible_max':115,'target':115,'migration_class':'none','rollback_compatible_min':115,'rollback_compatible_max':115})

    def test_validator_rejects_automatic_policy_and_schema_drift(self):
        import shutil
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);release_dir=root/'web/deployment/releases';release_dir.mkdir(parents=True)
            shutil.copytree(WEB_ROOT/'deployment/releases',release_dir,dirs_exist_ok=True)
            for tree in ['database','supabase']:
                target=WEB_ROOT/tree
                if not target.exists():target=Path('/workspace')/tree
                (root/'web'/tree).symlink_to(target,target_is_directory=True)
            self.assertEqual(validator.validate(root),[])
            original=json.loads((release_dir/'release.json').read_text())
            for field,value in [('migration_policy','automatic-after-known-good-backup-first-forward-repair'),('migration_manifest','migrations-115-116.json')]:
                edited={**original,field:value};(release_dir/'release.json').write_text(json.dumps(edited))
                self.assertTrue(validator.validate(root))
            for field in ['target','compatible_min','compatible_max','rollback_compatible_min','rollback_compatible_max']:
                edited={**original,'schema':{**original['schema'],field:116}};(release_dir/'release.json').write_text(json.dumps(edited))
                self.assertTrue(validator.validate(root))


    def test_exact_candidate_policy_cannot_create_backup_or_execute_SQL(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from test_automatic_migration_control_plane import load_release_cli
        module=load_release_cli()
        release=json.loads((WEB_ROOT/'deployment/releases/release.json').read_text())
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
        self.assertEqual(validator.validate(), [])

    def test_future_namespace_tampering_is_rejected_by_both_validators(self):
        import shutil
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for subtree in ['deployment/releases', 'database/migrations', 'supabase/migrations']:
                source = WEB_ROOT / subtree
                if not source.exists(): source = Path('/workspace') / subtree
                shutil.copytree(source, root / 'web' / subtree)
            spec = importlib.util.spec_from_file_location('namespace_validator', WEB_ROOT / 'scripts/check_migrations.py')
            namespace = importlib.util.module_from_spec(spec); spec.loader.exec_module(namespace)
            trees = {label:root / 'web' / label / 'migrations' for label in ['database', 'supabase']}
            def namespace_errors():
                errors=[]
                with patch.object(namespace, 'REPO_ROOT', root / 'web'), patch.object(namespace, 'TREE_PATHS', trees):
                    namespace.check_production_lineage(errors)
                return errors
            self.assertEqual(namespace_errors(), [])
            for number in [116, 117, 135]:
                path = next(trees['database'].glob(str(number) + '_*.sql'))
                original = path.read_bytes()
                path.write_bytes(original + b'\n-- unreviewed alteration\n')
                self.assertTrue(validator.validate(root))
                self.assertTrue(namespace_errors())
                path.write_bytes(original)
            unexpected = trees['database'] / '136_unreviewed.sql'
            unexpected.write_text('begin; commit;')
            self.assertTrue(validator.validate(root)); self.assertTrue(namespace_errors())
            unexpected.unlink()
            manifest = root / 'web/deployment/releases/migrations-115-135.json'
            manifest.write_text(manifest.read_text() + '\n')
            self.assertTrue(validator.validate(root)); self.assertTrue(namespace_errors())

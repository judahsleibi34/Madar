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

    def test_active_release_selects_only_the_exact_schema115_to136_contract(self):
        release=json.loads((WEB_ROOT/'deployment/releases/release.json').read_text())
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
                (root/'web'/tree).symlink_to(target,target_is_directory=True)
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
                (root/'web'/tree).symlink_to(source,target_is_directory=True)
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
            (root/'web/deployment').symlink_to(WEB_ROOT/'deployment',target_is_directory=True)
            for tree in ['database','supabase']:
                target=WEB_ROOT/tree
                if not target.exists():target=Path('/workspace')/tree
                (root/'web'/tree).symlink_to(target,target_is_directory=True)
            self.assertEqual(validator.validate(root), [])

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
            for number in [116, 117, 135, 136]:
                path = next(trees['database'].glob(str(number) + '_*.sql'))
                original = path.read_bytes()
                path.write_bytes(original + b'\n-- unreviewed alteration\n')
                self.assertTrue(validator.validate(root))
                self.assertTrue(namespace_errors())
                path.write_bytes(original)
            unexpected = trees['database'] / '137_unreviewed.sql'
            unexpected.write_text('begin; commit;')
            self.assertTrue(validator.validate(root)); self.assertTrue(namespace_errors())
            unexpected.unlink()
            manifest = root / 'web/deployment/releases/migrations-115-135.json'
            manifest.write_text(manifest.read_text() + '\n')
            self.assertTrue(validator.validate(root)); self.assertTrue(namespace_errors())

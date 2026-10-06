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

"""Selection/inventory separation and exact fixture enrollment (no authority)."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from deployment.lib import automatic_release_selection as selection
from deployment.lib.migration_inventory import canonical,digest,Inventory,MigrationBytes

class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.enterContext(patch.object(selection,'ROOT',self.root))
        self.enterContext(patch.object(selection,'protected',lambda p,**kw:p))
        self.inventory=SimpleNamespace(target=164,forward=lambda origin,target:())
        self.enterContext(patch.object(selection,'discover',return_value=self.inventory))
        self.ops=SimpleNamespace(repo=self.root)
        self.proof={'history_base_sha':'b'*40,'images':{'backend':'immutable'}}
        self.policy={'environment_id':'isolated-x','controller_sha':'c'*40,'environment':'isolated-test'}
        self.routine={'database_system_identifier':'123'}
        self.scope={'version':1,'environment_id':'isolated-x','controller_sha':'c'*40,'source_sha':'a'*40,
            'database_system_identifier':'123','origin_schema':160,'target_schema':160,'history':{'kind':'canonical'},
            'images_sha256':digest(self.proof['images']),'routine_policy_sha256':digest(self.routine),'plan_sha256':'d'*64}
    def load(self):return selection.select(self.ops,'a'*40,self.proof,self.policy,self.routine,160)
    def publish(self): (self.root/('a'*40+'.json')).write_bytes(canonical(self.scope))
    def test_no_selection_does_not_select_published164(self):
        inv,target,scope=self.load();self.assertIs(inv,self.inventory);self.assertEqual(target,160);self.assertIsNone(scope)
    def test_source_policy_images_origin_database_and_controller_are_bound(self):
        self.publish();self.assertEqual(self.load()[2],self.scope)
        for field,value in [('database_system_identifier','456'),('origin_schema',True),('source_sha','b'*40),
                ('images_sha256','f'*64),('routine_policy_sha256','f'*64),('controller_sha','f'*40)]:
            original=self.scope[field];self.scope[field]=value;self.publish()
            with self.subTest(field=field),self.assertRaises(RuntimeError):self.load()
            self.scope[field]=original
    def test_fixture_history_cannot_be_enrolled_by_production_policy(self):
        self.scope['history']={'kind':'isolated-fixture'};self.publish();self.policy['environment']='production'
        with self.assertRaisesRegex(RuntimeError,'history_scope_refused'):self.load()
    def test_fixture_manifest_and_sql_substitution_are_refused(self):
        path=selection.FIXTURE_PREFIX+'safe/history.json'
        sql=selection.FIXTURE_PREFIX+'safe/bootstrap.sql'
        rows=[{'number':900160+i,'path':sql.replace('bootstrap',str(i)),'sha256':hashlib.sha256(b'fixture').hexdigest()} for i in range(2)]
        manifest=canonical({'version':1,'kind':'isolated-test-only-history','initial_schema':900160,'migrations':rows})
        files={path:manifest,**{r['path']:b'fixture' for r in rows}}
        history={'kind':'isolated-fixture','manifest_path':path,'manifest_sha256':hashlib.sha256(manifest).hexdigest(),
            'canonical_schema':160,'canonical_history_sha256':'e'*64}
        git=SimpleNamespace(files=lambda *a:files)
        base=SimpleNamespace(source_sha='a'*40,history_base_sha='b'*40)
        with patch.object(selection,'history_digest',return_value='e'*64):
            inventory=selection.fixture_inventory(git,base,history)
            self.assertEqual(inventory.target,900161);self.assertTrue(inventory.history_scope)
            files[rows[1]['path']]=b'substitution'
            with self.assertRaisesRegex(RuntimeError,'sql_substituted'):selection.fixture_inventory(git,base,history)

class InstalledSelectionDependenciesTests(unittest.TestCase):
    def test_existing_installer_carries_both_automatic_sql_dependencies(self):
        import os
        web=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
        installer=web/'deployment/bin/madar-install-control-plane'
        body=installer.read_text()
        for name in ('automatic_release_selection.py','automatic_release_migration.py'):
            self.assertIn('  lib/'+name+'\n',body)
            self.assertTrue((web/'deployment/lib'/name).is_file())

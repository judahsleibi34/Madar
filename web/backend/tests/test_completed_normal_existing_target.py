"""An already committed target is no SQL, after complete manifest verification."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from test_completed_normal_compose import cli,WEB


class ExistingTargetPlanningTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);releases=self.root/'web/deployment/releases';releases.mkdir(parents=True)
        self.metadata=releases/'release.json'
        self.metadata.write_bytes((WEB/'deployment/releases/release.json').read_bytes())
        self.manifest=releases/'migrations-145-146-commercial.json'
        self.manifest.write_bytes((WEB/'deployment/releases'/self.manifest.name).read_bytes())
        self.sql=[]
        for row in json.loads(self.manifest.read_bytes())['migrations']:
            path=self.root/row['path'];path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes((WEB.parent/row['path']).read_bytes());self.sql.append(path)
        self.ops=SimpleNamespace(release_root=self.root,release_metadata_path=lambda:self.metadata)
        self.compat=cli.Compatibility.load(self.metadata)

    def plan(self,schema):
        return cli.plan_release_migrations(sha='a'*40,schema=schema,compatibility=self.compat,operations=self.ops)

    def test_origin_keeps_complete_path_and_existing_target_does_not_replay_sql(self):
        self.assertEqual(self.plan(144),[[144,145],[145,146]])
        self.assertEqual(self.plan(146),[])

    def test_intermediate_or_foreign_schema_is_not_an_already_committed_target(self):
        for schema in (115,145,147,160):
            with self.subTest(schema=schema),self.assertRaisesRegex(RuntimeError,'path_mismatch'):self.plan(schema)

    def test_existing_target_does_not_bypass_sql_or_manifest_integrity(self):
        self.sql[-1].write_bytes(self.sql[-1].read_bytes()+b'\n')
        with self.assertRaises(Exception):self.plan(146)
        raw=json.loads(self.manifest.read_bytes());raw['release_sha']='b'*40
        self.manifest.write_text(json.dumps(raw))
        with self.assertRaisesRegex(RuntimeError,'release_mismatch'):self.plan(146)


if __name__=='__main__':unittest.main()

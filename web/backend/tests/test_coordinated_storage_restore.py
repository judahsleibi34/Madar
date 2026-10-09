"""Synthetic native Storage metadata recovery; never production evidence."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2]);sys.path.insert(0,str(WEB))
from deployment.lib.coordinated_storage_restore import recover_metadata,ATTRIBUTES
class StorageRestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.rows=[{'bucket':'fixture','name':'object','version':'v2','metadata':{'mimetype':'image/png','cacheControl':'max-age=3600'}}]
    def tree(self,name):
        root=self.root/name;base=root/'stub/stub/fixture/object';base.mkdir(parents=True)
        for version in ['v1','v2']:(base/version).write_bytes(b'synthetic fixture')
        return root
    def test_exact_attributes_recovered_from_saved_database(self):
        target=self.tree('restore');source=self.tree('source')
        for file in source.rglob('*'):
            if file.is_file():
                for key,field in ATTRIBUTES.items():os.setxattr(file,key,self.rows[0]['metadata'][field].encode())
        result=recover_metadata(self.rows,target,source_root=source)
        self.assertEqual(result['files'],2);self.assertEqual(result['attributes'],4)
        self.assertTrue(result['source_bytes_and_attributes_independently_match'])
    def test_divergent_version_missing_metadata_and_traversal_denied(self):
        target=self.tree('diverged');(target/'stub/stub/fixture/object/v1').write_bytes(b'different')
        with self.assertRaisesRegex(RuntimeError,'version_diverged'):recover_metadata(self.rows,target)
        target=self.tree('incomplete');self.rows[0]['metadata'].pop('mimetype')
        with self.assertRaisesRegex(RuntimeError,'metadata_invalid'):recover_metadata(self.rows,target)
        self.rows[0]['name']='../escape'
        with self.assertRaises(RuntimeError):recover_metadata(self.rows,target)
    def test_unmapped_file_and_modified_source_denied_before_publication(self):
        target=self.tree('extra');(target/'unknown').write_bytes(b'fixture')
        with self.assertRaisesRegex(RuntimeError,'inventory_inexact'):recover_metadata(self.rows,target)
        target=self.tree('target');source=self.tree('source')
        with self.assertRaisesRegex(RuntimeError,'source_metadata_changed'):recover_metadata(self.rows,target,source_root=source)
        self.assertEqual(os.listxattr(target/'stub/stub/fixture/object/v2'),[])

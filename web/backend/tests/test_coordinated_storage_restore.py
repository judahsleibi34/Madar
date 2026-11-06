"""Synthetic native Storage metadata recovery; never production evidence."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
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
    def test_continuation_verifies_existing_attributes_without_reapplying_them(self):
        target=self.tree('continued');recover_metadata(self.rows,target)
        with patch('deployment.lib.coordinated_storage_restore.os.setxattr') as write:
            self.assertTrue(recover_metadata(self.rows,target,verify_only=True)['verification_only'])
            write.assert_not_called()
        with self.assertRaisesRegex(RuntimeError,'destination_metadata_exists'):
            recover_metadata(self.rows,target)
        file=target/'stub/stub/fixture/object/v2'
        os.setxattr(file,'user.supabase.content-type',b'changed')
        with patch('deployment.lib.coordinated_storage_restore.os.setxattr') as write:
            with self.assertRaisesRegex(RuntimeError,'metadata_mismatch'):
                recover_metadata(self.rows,target,verify_only=True)
            write.assert_not_called()
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

    def test_authenticated_nondefault_namespace_uses_exact_same_metadata_verification(self):
        target=self.root/'named';base=target/'hardening/hardening/fixture/object';base.mkdir(parents=True);(base/'v2').write_bytes(b'synthetic')
        result=recover_metadata(self.rows,target,namespace=('hardening','hardening'))
        self.assertEqual(result['files'],1)
        for namespace in (('../elsewhere','hardening'),('hardening/other','hardening'),('hardening',),('','hardening')):
            with self.subTest(namespace=namespace),self.assertRaisesRegex(RuntimeError,'namespace_invalid'):recover_metadata(self.rows,target,namespace=namespace)

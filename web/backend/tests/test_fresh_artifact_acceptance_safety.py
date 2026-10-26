import os
import hashlib
import io
from pathlib import Path
import sys
import unittest
import tempfile
import zipfile
from unittest.mock import patch

WEB=Path(os.getenv('MADAR_TEST_REPOSITORY_ROOT') or Path(__file__).resolve().parents[2])
sys.path.insert(0,str(WEB/'staging/integration'))
import fresh_artifact_acceptance as acceptance


class FreshArtifactAcceptanceSafetyTests(unittest.TestCase):
    def test_import_reads_authenticated_bytes_even_if_retained_path_is_replaced(self):
        payload=b'synthetic image bytes; no Docker invocation'
        metadata={'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as output:output.writestr('backend.tar.gz',payload)
        buffer.seek(0)
        with tempfile.TemporaryDirectory() as temporary,zipfile.ZipFile(buffer) as archive:
            path=Path(temporary)/'backend.tar.gz'
            def load(command,**kwargs):
                path.write_bytes(b'substituted after extraction')
                self.assertEqual(command[-2:],['image','load'])
                self.assertNotIn('--input',command)
                self.assertEqual(kwargs['stdin'].read(),payload)
                return type('Result',(),{'returncode':0})()
            with patch.object(acceptance.manage,'require_staging_host'),patch.object(acceptance.subprocess,'run',side_effect=load) as process:
                acceptance.import_authenticated_image(archive,'backend',metadata,path)
                self.assertEqual(process.call_count,1)

    def test_changed_member_digest_prevents_import(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as output:output.writestr('backend.tar.gz',b'changed')
        buffer.seek(0)
        with tempfile.TemporaryDirectory() as temporary,zipfile.ZipFile(buffer) as archive:
            with patch.object(acceptance.manage,'require_staging_host'),patch.object(acceptance.subprocess,'run') as process:
                with self.assertRaisesRegex(RuntimeError,'digest changed'):
                    acceptance.import_authenticated_image(archive,'backend',{'bytes':7,'sha256':'0'*64},Path(temporary)/'backend.tar.gz')
                process.assert_not_called()

    def test_import_helper_rejects_primary_before_creating_files(self):
        with patch.object(acceptance.manage.socket,'gethostname',return_value='madar-gpu'),patch.object(acceptance.os,'open') as opened:
            with self.assertRaises(RuntimeError):
                acceptance.import_authenticated_image(None,'backend',{},Path('/unused'))
            opened.assert_not_called()

    def test_primary_host_cannot_load_images_or_stop_services(self):
        with patch.object(acceptance.manage.socket,'gethostname',return_value='madar-gpu'), \
                patch.object(acceptance.manage,'docker') as docker,patch.object(acceptance.manage,'compose') as compose:
            with self.assertRaises(RuntimeError):
                acceptance.main(Path.home()/'unused-artifact-scope','a'*40,3,'REHEARSE')
            docker.assert_not_called();compose.assert_not_called()

    def test_ambiguous_scope_or_source_fails_before_resource_inspection(self):
        for path,source in ((Path('/tmp/unknown'),'a'*40),(Path.home()/'unused','development')):
            with patch.object(acceptance.manage,'require_staging_host'),patch.object(acceptance.manage,'state') as state:
                with self.subTest(path=str(path)),self.assertRaises(RuntimeError):
                    acceptance.main(path,source,3,'INSPECT')
                state.assert_not_called()

    def test_explicit_resume_cannot_adopt_a_different_selected_source(self):
        with patch.object(acceptance.manage,'require_staging_host'), \
                patch.object(acceptance.manage,'state',return_value={'source_sha':'b'*40}), \
                patch.object(acceptance.manage,'attest_resources'),patch.object(acceptance.manage,'require_database_marker'), \
                patch.object(acceptance.manage,'compose') as compose:
            with self.assertRaisesRegex(RuntimeError,'already selected exact'):
                acceptance.main(Path.home()/'unused-artifact-scope','a'*40,3,'REHEARSE',resume=True)
            compose.assert_not_called()

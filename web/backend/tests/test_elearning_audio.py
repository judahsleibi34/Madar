import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes import builder_routes, elearning_content_routes
from services import elearning_content_service, elearning_access_service
from services.builder_asset_validation import detect_builder_asset_content_type, validate_builder_asset_file, BuilderAssetValidationError
from tests.test_builder_asset_upload import BuilderAssetUploadTests, fake_context
from tests.test_asset_registry_service import Client
from services.asset_registry_service import nonproject_asset_reference_count


def wav_bytes():
    output=BytesIO()
    with wave.open(output,'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(8000);audio.writeframes(b'\x00\x00'*100)
    return output.getvalue()


class AudioValidationTests(unittest.TestCase):
    def test_actual_wav_and_mp3_frames_validate_and_truncation_fails(self):
        for content,mime in [(wav_bytes(),'audio/wav'),(b'\xff\xfb\x90\x00'+b'\x00'*413,'audio/mpeg')]:
            self.assertEqual(detect_builder_asset_content_type(content[:32]),mime)
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'media';path.write_bytes(content);validate_builder_asset_file(path,mime)
                path.write_bytes(content[:32])
                with self.assertRaises(BuilderAssetValidationError): validate_builder_asset_file(path,mime)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'media';path.write_bytes(b'ID3'+b'\x00'*40)
            with self.assertRaises(BuilderAssetValidationError): validate_builder_asset_file(path,'audio/mpeg')

    def test_live_and_archived_content_retain_media_without_public_visibility(self):
        client=Client();asset=str(uuid4());key='tenant_7/builder_assets/'+uuid4().hex+'.mp3'
        client.data['builder_assets']=[{'id':asset,'tenant_id':7,'storage_key':key}]
        client.data['elearning_content_blocks']=[{'id':str(uuid4()),'tenant_id':7,'media_id':asset,'archived_at':'2026-10-04'}]
        self.assertEqual(nonproject_asset_reference_count(tenant_id=7,storage_key=key,client=client),1)
        self.assertEqual(nonproject_asset_reference_count(tenant_id=7,storage_key=key,public_only=True,client=client),0)
        client.data['elearning_content_blocks'][0]['tenant_id']=8
        self.assertEqual(nonproject_asset_reference_count(tenant_id=7,storage_key=key,client=client),0)


class LessonMediaUploadTests(unittest.TestCase):
    tearDown = BuilderAssetUploadTests.tearDown
    def setUp(self):
        BuilderAssetUploadTests.setUp(self)
        app=FastAPI();app.include_router(elearning_content_routes.router);self.client=TestClient(app)
        self.endpoint=f'/elearning/courses/{uuid4()}/lessons/{uuid4()}/content/media/upload'
        for mock in (patch.object(elearning_access_service,'require_active_tenant_member',return_value=fake_context()),patch.object(elearning_content_service,'get_content',return_value={'editable':True}),patch.object(elearning_content_service,'require_available')):
            mock.start();self.addCleanup(mock.stop)

    # Inherit fixture setup only, not the unrelated builder route tests.
    def test_lesson_media_reuses_quota_and_returns_registry_id(self):
        response=self.client.post(self.endpoint,files={'file':('voice.wav',wav_bytes(),'audio/wav')})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['asset_id'],'asset-registry-1')
        self.assertTrue(response.json()['url'].endswith('.wav'))
        builder_routes.reserve_storage.assert_called_once()
        self.assertEqual(self.record_audit_event.call_args.kwargs['action'],'elearning.content.media_uploaded')

    def test_invalid_audio_rolls_back_storage_reservation(self):
        with patch.object(builder_routes,'release_builder_asset_reservation',return_value=True) as release:
            response=self.client.post(self.endpoint,files={'file':('voice.mp3',b'ID3'+b'\x00'*30,'audio/mpeg')})
        self.assertEqual(response.status_code,400)
        release.assert_called_once()
        builder_routes.register_builder_asset.assert_not_called()

    def test_mime_mismatch_archived_parent_and_member_are_rejected(self):
        self.assertEqual(self.client.post(self.endpoint,files={'file':('voice.mp3',wav_bytes(),'audio/mpeg')}).status_code,400)
        with patch.object(elearning_content_service,'get_content',return_value={'editable':False}):
            self.assertEqual(self.client.post(self.endpoint,files={'file':('voice.wav',wav_bytes(),'audio/wav')}).status_code,409)
        with patch.object(elearning_access_service,'require_active_tenant_member',return_value=fake_context()) as member:
            from dataclasses import replace
            member.return_value=replace(fake_context(),role='member')
            self.assertEqual(self.client.post(self.endpoint,files={'file':('voice.wav',wav_bytes(),'audio/wav')}).status_code,403)


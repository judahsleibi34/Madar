import io
import unittest
import wave
from fastapi import HTTPException
from services.elearning_recording_service import inspect_wav

class RecordingValidationTests(unittest.TestCase):
    def wav(self,frames=16000,channels=1,width=2,rate=16000):
        result=io.BytesIO()
        with wave.open(result,'wb') as stream:
            stream.setnchannels(channels);stream.setsampwidth(width);stream.setframerate(rate);stream.writeframes(b'\0'*frames*channels*width)
        return result.getvalue()

    def test_duration_comes_from_pcm_frames_not_client_claims(self):
        self.assertEqual(inspect_wav(self.wav(),'audio/wav'),1000)

    def test_signatures_mime_truncation_and_formats_are_checked(self):
        for content,mime in [(b'RIFF'+b'\0'*50,'audio/wav'),(self.wav(),'audio/mpeg'),(self.wav()[:-2],'audio/wav'),(self.wav(channels=3),'audio/wav'),(self.wav(width=1),'audio/wav'),(self.wav(rate=4000),'audio/wav')]:
            with self.subTest(mime=mime),self.assertRaises(HTTPException):inspect_wav(content,mime)

    def test_oversized_content_is_rejected_before_decode(self):
        with self.assertRaises(HTTPException):inspect_wav(b'\0'*10485761,'audio/wav')

    def test_trailing_chunks_and_forged_container_lengths_cannot_hide_audio(self):
        import struct
        original=self.wav()
        trailing=original+b'data'+struct.pack('<I',32000)+b'\0'*32000
        adjusted=bytearray(trailing);struct.pack_into('<I',adjusted,4,len(adjusted)-8)
        misleading=bytearray(original);struct.pack_into('<I',misleading,40,16000)
        for content in [trailing,bytes(adjusted),bytes(misleading)]:
            with self.subTest(size=len(content)),self.assertRaises(HTTPException):inspect_wav(content,'audio/wav')

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from hashlib import sha256
from uuid import uuid4
from services import elearning_recording_service as recording_service

class RecordingTransactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_committed_registration_timeout_preserves_bytes(self):
        await self.scenario('committed')

    async def test_failed_registration_removes_unreferenced_bytes_and_quota(self):
        await self.scenario('rejected')

    async def test_unknown_commit_never_deletes_recording_evidence(self):
        await self.scenario('unknown')

    async def scenario(self,mode):
        content=RecordingValidationTests().wav();identifier=uuid4();attempt=uuid4();question=uuid4()
        actor=SimpleNamespace(tenant_id=7,user_id=8)
        admission={'config':{'max_duration_seconds':30,'max_size_bytes':100000},'storage_key':'assessment-owned-key','existing':None}
        existing={**admission,'existing':{'sha256':sha256(content).hexdigest(),'size_bytes':len(content),'duration_ms':1000}}
        storage=Mock();file=SimpleNamespace(read=AsyncMock(return_value=content),content_type='audio/wav')
        calls=Mock(side_effect=[admission,RuntimeError('RPC response lost'),existing if mode=='committed' else RuntimeError('ownership unknown') if mode=='unknown' else admission])
        with patch.object(recording_service,'require_learning143'),patch.object(recording_service,'private_bucket',return_value=storage),patch.object(recording_service,'call',calls),patch.object(recording_service,'reserve_storage',return_value='reservation'),patch.object(recording_service,'finish_storage') as finish,patch.object(recording_service,'release_storage',return_value=True) as release:
            if mode=='committed':
                self.assertEqual(await recording_service.upload(actor,attempt,question,identifier,file),{'id':str(identifier)})
            else:
                with self.assertRaises(RuntimeError):await recording_service.upload(actor,attempt,question,identifier,file)
            file.read.assert_awaited_once_with(10485761)
            if mode=='rejected':storage.remove.assert_called_once_with(['assessment-owned-key']);release.assert_called_once()
            else:storage.remove.assert_not_called();release.assert_not_called()
            finish.assert_called_once()

class RecordingBodyLimitTests(unittest.TestCase):
    def test_large_or_chunked_recordings_use_the_bounded_request_middleware(self):
        from services.request_body_limits import select_request_body_limit,RequestBodyLimitConfig,ASSESSMENT_RECORDING_BODY_BYTES
        path='/elearning/assessment-attempts/'+str(uuid4())+'/recordings/'+str(uuid4())
        config=RequestBodyLimitConfig(12*1024*1024,252*1024*1024,3*1024*1024,256*1024,1024*1024)
        self.assertEqual(select_request_body_limit(method='POST',path=path,content_type='multipart/form-data',config=config),ASSESSMENT_RECORDING_BODY_BYTES)
        config=RequestBodyLimitConfig(1024,4096,256,64,128)
        self.assertEqual(select_request_body_limit(method='POST',path=path,content_type='multipart/form-data',config=config),1024)

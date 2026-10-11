"""Private assessment-owned WAV recordings; no Builder/Forms persistence."""
from hashlib import sha256
import io
import logging
import math
import struct
from uuid import UUID
import wave
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from database import service_supabase
from services.elearning_assessments_service import call, require_learning143
from services.storage_quota_service import reserve_storage, finish_storage, release_storage
from services.upload_config import get_data_upload_dir

BUCKET='elearning-assessment-recordings'
CATEGORY='elearning_assessment'
logger=logging.getLogger(__name__)


def inspect_wav(content: bytes, mime: str):
    if mime != 'audio/wav' or len(content) > 10485760 or len(content)<45:
        raise HTTPException(415,'Use a WAV recording within the configured size limit')
    try:
        # Browser captures are normalized to one PCM16 fmt/data pair. Reject
        # alternate/trailing chunks so playback cannot exceed inspected frames.
        if content[:4]!=b'RIFF' or content[8:12]!=b'WAVE' or content[12:16]!=b'fmt ' or content[36:40]!=b'data':
            raise ValueError('signature')
        riff_size,=struct.unpack_from('<I',content,4)
        fmt_size,codec,channels,rate,byte_rate,alignment,bits=struct.unpack_from('<IHHIIHH',content,16)
        data_size,=struct.unpack_from('<I',content,40)
        if (riff_size+8!=len(content) or fmt_size!=16 or codec!=1 or bits!=16 or channels not in (1,2)
                or alignment!=channels*2 or byte_rate!=rate*alignment or data_size!=len(content)-44 or data_size%alignment):
            raise ValueError('canonical PCM container required')
        with wave.open(io.BytesIO(content),'rb') as recording:
            if recording.getcomptype()!='NONE' or recording.getsampwidth()!=2 or recording.getnchannels() not in (1,2) or not 8000<=recording.getframerate()<=48000:
                raise ValueError('PCM recording required')
            duration=math.ceil(recording.getnframes()/recording.getframerate()*1000)
            if not 1<=duration<=300000:raise ValueError('duration')
            expected=recording.getnframes()*recording.getnchannels()*2
            if len(recording.readframes(recording.getnframes()))!=expected:raise ValueError('truncated')
        return duration
    except (wave.Error,EOFError,ValueError,ZeroDivisionError,struct.error) as error:
        raise HTTPException(422,'Invalid or truncated PCM WAV recording') from error


def private_bucket():
    try:
        bucket=service_supabase.storage.get_bucket(BUCKET)
    except Exception:
        try:service_supabase.storage.create_bucket(BUCKET,options={'public':False})
        except Exception:pass
        bucket=service_supabase.storage.get_bucket(BUCKET)
    public=bucket.get('public') if isinstance(bucket,dict) else getattr(bucket,'public',None)
    if public is not False:raise HTTPException(503,'Private assessment storage unavailable')
    return service_supabase.storage.from_(BUCKET)


async def upload(actor,attempt:UUID,question:UUID,identifier:UUID,file):
    require_learning143()
    content=await file.read(10485761)
    return await run_in_threadpool(store,actor,attempt,question,identifier,content,file.content_type)


def store(actor,attempt,question,identifier,content,mime):
    duration=inspect_wav(content,mime)
    digest=sha256(content).hexdigest()
    admission=call('get_elearning_recording_admission',actor.tenant_id,p_user_id=actor.user_id,p_attempt_id=str(attempt),p_question_id=str(question),p_id=str(identifier))
    config=admission['config'];existing=admission.get('existing')
    if existing:
        if existing['sha256']!=digest or existing['size_bytes']!=len(content) or existing['duration_ms']!=duration:
            raise HTTPException(409,'Recording identity already belongs to different content')
        return {'id':str(identifier)}
    if duration>config['max_duration_seconds']*1000 or len(content)>config['max_size_bytes']:
        raise HTTPException(422,'Recording exceeds configured question limits')
    storage=private_bucket();key=admission['storage_key']
    reservation=reserve_storage(tenant_id=actor.tenant_id,user_id=actor.user_id,category=CATEGORY,size_bytes=len(content),storage_root=get_data_upload_dir())
    stored=False
    try:
        storage.upload(path=key,file=content,file_options={'content-type':'audio/wav','cache-control':'no-store','upsert':'false'})
        stored=True
        finish_storage(reservation_id=reservation,succeeded=True,storage_key=key,sha256_hex=digest)
        call('register_elearning_recording',actor.tenant_id,p_user_id=actor.user_id,p_attempt_id=str(attempt),p_question_id=str(question),p_id=str(identifier),p_size=len(content),p_duration=duration,p_sha256=digest)
        return {'id':str(identifier)}
    except Exception:
        # A timed-out RPC may have committed ownership. Never remove referenced
        # recording bytes because its response was lost.
        if stored:
            try:
                evidence=call('get_elearning_recording_admission',actor.tenant_id,p_user_id=actor.user_id,p_attempt_id=str(attempt),p_question_id=str(question),p_id=str(identifier))
                if (evidence.get('existing') or {}).get('sha256')==digest:
                    return {'id':str(identifier)}
            except Exception:
                logger.error('learning.recording_commit_unknown',extra={'tenant_id':actor.tenant_id,'storage_key':key})
                raise
        try:
            if stored:
                storage.remove([key])
                if not release_storage(tenant_id=actor.tenant_id,category=CATEGORY,storage_key=key):
                    finish_storage(reservation_id=reservation,succeeded=False)
            else:finish_storage(reservation_id=reservation,succeeded=False)
        except Exception as cleanup:
            logger.error('learning.recording_cleanup_failed',extra={'tenant_id':actor.tenant_id,'storage_key':key,'error_type':type(cleanup).__name__})
        raise


def download(actor,identifier):
    require_learning143()
    row=call('get_elearning_recording',actor.tenant_id,p_user_id=actor.user_id,p_id=str(identifier))
    content=private_bucket().download(row['storage_key'])
    if len(content)!=row['size_bytes'] or sha256(content).hexdigest()!=row['sha256']:
        raise HTTPException(503,'Recording integrity check failed')
    return content


def cleanup(*,limit=100,apply=False):
    require_learning143()
    rows=service_supabase.rpc('prepare_elearning_recording_cleanup',{'p_limit':limit,'p_apply':apply}).execute().data or []
    completed=0
    if apply:
        storage=private_bucket()
        for row in rows:
            storage.remove([row['storage_key']])
            service_supabase.rpc('finish_elearning_recording_cleanup',{'p_tenant_id':row['tenant_id'],'p_storage_key':row['storage_key']}).execute()
            completed+=1
    return {'eligible':len(rows),'completed':completed,'dry_run':not apply}

import logging
from uuid import UUID
from fastapi import APIRouter, Request, Response, UploadFile, File
from services.elearning_access_service import require_elearning_access
from services.audit_service import record_audit_event
from services import elearning_content_service as service
from routes.elearning_structure_routes import operation

router = APIRouter(prefix='/elearning/courses', tags=['E-Learning'])
logger = logging.getLogger(__name__)


@router.get('/{course_id}/lessons/{lesson_id}/content')
def get_content(course_id: UUID, lesson_id: UUID, request: Request, response: Response):
    member = require_elearning_access(request, response, 'elearning.structure.view')
    return operation(lambda: service.get_content(member.tenant_id, course_id, lesson_id))


@router.post('/{course_id}/lessons/{lesson_id}/content/commands')
def execute_command(course_id: UUID, lesson_id: UUID, payload: service.ContentCommand, request: Request, response: Response):
    member = require_elearning_access(request, response, 'elearning.structure.manage')
    def execute():
        result = service.execute_command(member.tenant_id, course_id, lesson_id, member.user_id, payload)
        record_audit_event(request=request, actor_user_id=member.user_id, tenant_id=member.tenant_id,
                           action=f'elearning.content.{payload.action}', target_type='elearning_lesson', target_id=str(lesson_id))
        return result
    return operation(execute)


@router.post('/{course_id}/lessons/{lesson_id}/content/media/upload')
async def upload_media(course_id: UUID, lesson_id: UUID, request: Request, response: Response, file: UploadFile = File(...)):
    member = require_elearning_access(request, response, 'elearning.structure.manage')
    snapshot = operation(lambda: service.get_content(member.tenant_id, course_id, lesson_id))
    if not snapshot['editable']:
        from fastapi import HTTPException
        raise HTTPException(409, 'Archived learning content cannot be edited')
    # Reuse shared quota, reservation, validation, durable storage and registration.
    from routes.builder_routes import upload_builder_asset
    request.scope['madar_asset_usage'] = 'elearning_content'
    return await upload_builder_asset(request=request, response=response, file=file)


@router.get('/{course_id}/lessons/{lesson_id}/content/media/audio')
def existing_audio(course_id: UUID, lesson_id: UUID, request: Request, response: Response):
    member = require_elearning_access(request, response, 'elearning.structure.manage')
    operation(lambda: service.get_content(member.tenant_id, course_id, lesson_id))
    from database import service_supabase
    rows = service_supabase.table('builder_assets').select('id,original_filename,mime_type,storage_key').eq('tenant_id', member.tenant_id).in_('status', ['active', 'unreferenced']).in_('mime_type', ['audio/mpeg', 'audio/wav']).order('created_at', desc=True).limit(200).execute().data
    return {'media': [{'id': row['id'], 'filename': row['original_filename'], 'mime_type': row['mime_type'], 'url': '/uploads/' + row['storage_key']} for row in rows]}

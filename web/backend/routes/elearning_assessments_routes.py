from uuid import UUID
from fastapi import APIRouter,Request,Response
from services.elearning_access_service import require_elearning_access
from services.audit_service import record_audit_event
from services import elearning_assessments_service as service
from routes.elearning_player_routes import member
from routes.elearning_structure_routes import operation

router=APIRouter(tags=['E-Learning Assessments'])
admin='/elearning/courses/{course_id}/lessons/{lesson_id}/assessments'
learner='/elearning/my-learning/courses/{course_id}/lessons/{lesson_id}/assessments/{block_id}'


def owner(request,response):
    response.headers['Cache-Control']='private, no-store'
    return require_elearning_access(request,response,'elearning.structure.manage')


def audit(request,actor,action,result,block=None):
    record_audit_event(request=request,actor_user_id=actor.user_id,tenant_id=actor.tenant_id,action='elearning.assessment.'+action,target_type='elearning_assessment',target_id=str(result.get('assessment',{}).get('id') or block))


@router.post(admin)
def create(course_id:UUID,lesson_id:UUID,payload:service.AssessmentCreate,request:Request,response:Response):
    actor=owner(request,response)
    def execute():
        result=service.create(actor,course_id,lesson_id,payload);audit(request,actor,'created',result);return result
    return operation(execute)


@router.get(admin+'/{block_id}')
def get(course_id:UUID,lesson_id:UUID,block_id:UUID,request:Request,response:Response):
    actor=owner(request,response)
    return operation(lambda:service.author(actor,course_id,lesson_id,block_id))


@router.get(admin+'/{block_id}/preview')
def preview(course_id:UUID,lesson_id:UUID,block_id:UUID,request:Request,response:Response):
    actor=owner(request,response)
    return operation(lambda:service.author(actor,course_id,lesson_id,block_id,preview=True))


@router.post(admin+'/{block_id}/commands')
def manage(course_id:UUID,lesson_id:UUID,block_id:UUID,payload:service.AssessmentCommand,request:Request,response:Response):
    actor=owner(request,response)
    def execute():
        result=service.manage(actor,course_id,lesson_id,block_id,payload)
        action=payload.payload.get('status',payload.action) if payload.action=='settings' else payload.action
        audit(request,actor,action,result,block_id);return result
    return operation(execute)


@router.get(learner)
def runtime(course_id:UUID,lesson_id:UUID,block_id:UUID,request:Request,response:Response):
    actor=member(request,response)
    return operation(lambda:service.runtime(actor,course_id,lesson_id,block_id))


@router.post(learner+'/attempts')
def start(course_id:UUID,lesson_id:UUID,block_id:UUID,request:Request,response:Response):
    actor=member(request,response)
    return operation(lambda:service.runtime(actor,course_id,lesson_id,block_id,start=True))


@router.post(learner+'/attempts/{attempt_id}/submission')
def submit(course_id:UUID,lesson_id:UUID,block_id:UUID,attempt_id:UUID,payload:service.Submission,request:Request,response:Response):
    actor=member(request,response)
    return operation(lambda:service.runtime(actor,course_id,lesson_id,block_id,attempt=attempt_id,payload=payload))

# Section/course placements share the same engine and permission boundaries.
from fastapi import UploadFile, File, HTTPException
from services import elearning_placements_service as placements
from services import elearning_courses_service as courses

placed_admin='/elearning/courses/{course_id}/assessments'
placed_learner='/elearning/my-learning/courses/{course_id}/assessments/{block_id}'

@router.get(placed_admin)
def list_placements(course_id:UUID,request:Request,response:Response,section_id:UUID|None=None):
    actor=owner(request,response)
    return operation(lambda:placements.listing(actor,course_id,section_id))

@router.post(placed_admin)
def create_placement(course_id:UUID,payload:placements.PlacedAssessment,request:Request,response:Response):
    actor=owner(request,response)
    def execute():
        result=placements.create(actor,course_id,payload);audit(request,actor,'created',result);return result
    return operation(execute)

@router.post(placed_admin+'/attach')
def attach_placement(course_id:UUID,payload:placements.AttachAssessment,request:Request,response:Response):
    actor=owner(request,response)
    def execute():
        result=placements.create(actor,course_id,payload);audit(request,actor,'attached',result);return result
    return operation(execute)

@router.get(placed_admin+'/media/audio')
def placed_audio(course_id:UUID,request:Request,response:Response):
    actor=owner(request,response);placements.available()
    operation(lambda:courses.get_course(actor.tenant_id,course_id))
    from database import service_supabase
    rows=service_supabase.table('builder_assets').select('id,original_filename,mime_type,storage_key').eq('tenant_id',actor.tenant_id).in_('status',['active','unreferenced']).in_('mime_type',['audio/mpeg','audio/wav']).order('created_at',desc=True).limit(200).execute().data
    return {'media':[{'id':v['id'],'filename':v['original_filename'],'mime_type':v['mime_type'],'url':'/uploads/'+v['storage_key']} for v in rows]}

@router.post(placed_admin+'/media/upload')
async def placed_upload(course_id:UUID,request:Request,response:Response,file:UploadFile=File(...)):
    actor=owner(request,response);placements.available()
    snapshot=operation(lambda:courses.get_course(actor.tenant_id,course_id))
    if snapshot['status']=='archived': raise HTTPException(409,'Archived learning content cannot be edited')
    from routes.builder_routes import upload_builder_asset
    request.scope['madar_asset_usage']='elearning_content'
    return await upload_builder_asset(request=request,response=response,file=file)

@router.get(placed_admin+'/{block_id}')
def placed_author(course_id:UUID,block_id:UUID,request:Request,response:Response):
    actor=owner(request,response);placements.available()
    return operation(lambda:service.author(actor,course_id,None,block_id))

@router.get(placed_admin+'/{block_id}/preview')
def placed_preview(course_id:UUID,block_id:UUID,request:Request,response:Response):
    actor=owner(request,response);placements.available()
    return operation(lambda:service.author(actor,course_id,None,block_id,preview=True))

@router.post(placed_admin+'/{block_id}/commands')
def placed_commands(course_id:UUID,block_id:UUID,payload:service.AssessmentCommand,request:Request,response:Response):
    actor=owner(request,response);placements.available()
    def execute():
        result=service.manage(actor,course_id,None,block_id,payload);audit(request,actor,payload.payload.get('status',payload.action) if payload.action=='settings' else payload.action,result,block_id);return result
    return operation(execute)

@router.post(placed_admin+'/{block_id}/placement')
def placement_command(course_id:UUID,block_id:UUID,payload:placements.PlacementCommand,request:Request,response:Response):
    actor=owner(request,response)
    def execute():
        result=placements.manage(actor,course_id,block_id,payload);audit(request,actor,payload.action,result,block_id);return result
    return operation(execute)

@router.get(placed_learner)
def placed_runtime(course_id:UUID,block_id:UUID,request:Request,response:Response):
    actor=member(request,response);placements.available()
    return operation(lambda:service.runtime(actor,course_id,None,block_id))

@router.post(placed_learner+'/attempts')
def placed_start(course_id:UUID,block_id:UUID,request:Request,response:Response):
    actor=member(request,response);placements.available()
    return operation(lambda:service.runtime(actor,course_id,None,block_id,start=True))

@router.post(placed_learner+'/attempts/{attempt_id}/submission')
def placed_submit(course_id:UUID,block_id:UUID,attempt_id:UUID,payload:service.Submission,request:Request,response:Response):
    actor=member(request,response);placements.available()
    return operation(lambda:service.runtime(actor,course_id,None,block_id,attempt=attempt_id,payload=payload))

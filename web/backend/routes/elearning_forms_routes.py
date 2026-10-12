"""Learning form endpoints never delegate to Builder response persistence."""
import json
from datetime import datetime
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Request, Response, HTTPException, Query
from routes.elearning_assessments_routes import owner
from routes.elearning_structure_routes import operation
from services.tenant_service import require_active_tenant_member
from services.rate_limit_service import enforce_public_rate_limit, enforce_public_form_submission_rate_limit
from services import elearning_forms_service as service
from services.audit_service import record_audit_event

router=APIRouter(prefix='/elearning/forms',tags=['E-Learning Forms'])
public=APIRouter(prefix='/public/academies',tags=['E-Learning Forms'])

def audit(request,actor,action,identifier):
    record_audit_event(request=request,actor_user_id=actor.user_id,tenant_id=actor.tenant_id,action='elearning.form.'+action,target_type='elearning_form',target_id=str(identifier))

@router.get('')
def forms(request:Request,response:Response):
    return operation(lambda:service.forms(owner(request,response)))

@router.post('')
def create(payload:service.Definition,request:Request,response:Response):
    actor=owner(request,response)
    result=operation(lambda:service.save(actor,payload));audit(request,actor,'create',result['id']);return result

@router.get('/my-responses')
def applicant_responses(request:Request,response:Response,limit:int=Query(25,ge=1,le=50),offset:int=Query(0,ge=0)):
    actor=require_active_tenant_member(request,response,allow_admin_account_access=False,allow_learner=True)
    response.headers['Cache-Control']='private, no-store'
    return operation(lambda:service.applicant_responses(actor,limit,offset))

@router.get('/my-responses/{identifier}')
def applicant_response(identifier:UUID,request:Request,response:Response):
    actor=require_active_tenant_member(request,response,allow_admin_account_access=False,allow_learner=True)
    response.headers['Cache-Control']='private, no-store'
    return operation(lambda:service.applicant_response(actor,identifier))

@router.get('/responses')
def responses(request:Request,response:Response,form_id:UUID|None=None,search:str=Query('',max_length=120),unread:bool=False,date_from:datetime|None=None,date_to:datetime|None=None,identity:Literal['guest','authenticated']|None=None,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0),opportunity_id:UUID|None=None):
    actor=owner(request,response)
    return operation(lambda:service.responses(actor,form_id,search,unread,date_from,date_to,identity,limit,offset,opportunity_id))

@router.get('/responses/export')
def export(request:Request,response:Response,form_id:UUID|None=None,search:str=Query('',max_length=120),unread:bool=False,date_from:datetime|None=None,date_to:datetime|None=None,identity:Literal['guest','authenticated']|None=None,opportunity_id:UUID|None=None):
    actor=owner(request,response)
    result=operation(lambda:service.export_csv(actor,dict(form_id=form_id,search=search,unread=unread,date_from=date_from,date_to=date_to,identity=identity,opportunity_id=opportunity_id)))
    audit(request,actor,'export','responses');return Response(result,media_type='text/csv',headers={'Content-Disposition':'attachment; filename="learning-form-responses.csv"','Cache-Control':'private, no-store'})

@router.get('/responses/{identifier}')
def response_detail(identifier:UUID,request:Request,response:Response):
    actor=owner(request,response);return operation(lambda:service.response_detail(actor,identifier))

@router.put('/responses/{identifier}')
def mark(identifier:UUID,payload:service.ResponseEdit,request:Request,response:Response):
    actor=owner(request,response);service.gate(actor.tenant_id,'response_management')
    result=service.rpc('manage_elearning_form_response',{'p_tenant':actor.tenant_id,'p_user':actor.user_id,'p_id':str(identifier),'p_read':payload.read,'p_notes':payload.owner_notes});audit(request,actor,'review',identifier);return result

@router.post('/responses/{identifier}/decision')
def decision(identifier:UUID,payload:service.Decision,request:Request,response:Response):
    actor=owner(request,response)
    result=operation(lambda:service.review_response(actor,identifier,payload));audit(request,actor,'decision',identifier);return result

@router.get('/responses/{response_id}/files/{file_id}')
def download(response_id:UUID,file_id:UUID,request:Request,response:Response):
    actor=owner(request,response);row,data=operation(lambda:service.download(actor,response_id,file_id));audit(request,actor,'download',file_id)
    return Response(data,media_type=row['mime_type'],headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Disposition':'attachment; filename="'+row['filename']+'"'})

@router.get('/{identifier}')
def form(identifier:UUID,request:Request,response:Response):
    actor=owner(request,response);service.gate(actor.tenant_id,'response_management');return operation(lambda:service.definition(actor.tenant_id,identifier))

@router.put('/{identifier}')
def update(identifier:UUID,payload:service.Definition,request:Request,response:Response):
    actor=owner(request,response);result=operation(lambda:service.save(actor,payload,identifier));audit(request,actor,payload.status,identifier);return result

@router.post('/{identifier}/duplicate')
def duplicate(identifier:UUID,request:Request,response:Response):
    actor=owner(request,response);service.gate(actor.tenant_id)
    original=service.definition(actor.tenant_id,identifier)
    payload=service.Definition(name=(original['name']+' (copy)')[:160],status='inactive',schema=original['schema'])
    result=operation(lambda:service.save(actor,payload));audit(request,actor,'duplicate',result['id']);return result


def context(identifier,form_id,request,response):
    from routes.public_site_routes import resolve_website_settings
    from database import service_supabase
    from services.elearning_settings_service import get_settings
    from services.entitlement_service import require_public_runtime_entitlement
    website=resolve_website_settings(identifier,request=request);tenant=website['tenant_id']
    require_public_runtime_entitlement(website,'website_publish');service.gate(tenant)
    cfg=get_settings(tenant)
    if not cfg['enabled'] or not cfg['academy_enabled']:raise HTTPException(404,'Academy unavailable')
    rows=service_supabase.table('builder_projects').select('published_schema').eq('tenant_id',tenant).eq('id',website.get('academy_project_id')).eq('usage_profile','academy').eq('status','published').limit(1).execute().data or []
    def references(value):
        if isinstance(value,dict):return (value.get('type')=='academyForm' and value.get('academy',{}).get('formId')==str(form_id)) or any(references(v) for v in value.values())
        return isinstance(value,list) and any(references(v) for v in value)
    if not rows or not references(rows[0]['published_schema']):raise HTTPException(404,'Form not published on this academy')
    actor=None
    try:
        candidate=require_active_tenant_member(request,response,allow_admin_account_access=False,allow_learner=True)
        if candidate.tenant_id==tenant:actor=candidate
    except HTTPException as e:
        if e.status_code not in {401,403}:raise
    f=service.definition(tenant,form_id);service.public_access(tenant,f,actor)
    response.headers['Cache-Control']='private, no-store';response.headers['Vary']='Cookie'
    return tenant,f,actor

@public.get('/{identifier}/forms/{form_id}')
def render(identifier:str,form_id:UUID,request:Request,response:Response):
    enforce_public_rate_limit(request,'form_lookup',identifier)
    _,form,_=context(identifier,form_id,request,response)
    return {'id':form['id'],'version':form['version'],'schema':form['schema']}

@public.post('/{identifier}/forms/{form_id}/responses')
async def submit(identifier:str,form_id:UUID,request:Request,response:Response):
    enforce_public_form_submission_rate_limit(request,'elearning',identifier+':'+str(form_id))
    tenant,form,actor=context(identifier,form_id,request,response)
    payload,uploads=await response_payload(request)
    return await service.submit(tenant,form,actor,payload,uploads)


async def response_payload(request):
    if request.headers.get('content-type','').startswith('multipart/form-data'):
        data=await request.form(max_files=10,max_fields=2,max_part_size=250000)
        raw=data.get('payload','')
        if not isinstance(raw,str) or len(raw)>200000:raise HTTPException(413,'Response too large')
        try:payload=json.loads(raw)
        except ValueError as e:raise HTTPException(422,'Invalid response JSON') from e
        uploads=[(key[5:],value) for key,value in data.multi_items() if key.startswith('file:') and hasattr(value,'read')]
        if any(key!='payload' and not key.startswith('file:') for key,_ in data.multi_items()):raise HTTPException(422,'Unknown response parts')
    else:
        raw=await request.body()
        if len(raw)>200000:raise HTTPException(413,'Response too large')
        try:payload=json.loads(raw)
        except ValueError as e:raise HTTPException(422,'Invalid response JSON') from e
        uploads=[]
    if not isinstance(payload,dict):raise HTTPException(422,'Invalid response')
    return payload,uploads

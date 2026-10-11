"""Existing owner workspace, shared contacts and private application attachments."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Request, Response, Query, File, UploadFile, HTTPException
from routes.elearning_assessments_routes import owner
from routes.elearning_player_routes import member
from routes.elearning_structure_routes import operation
from services import academy_owner_service as service
from services.academy_capability_service import require_capability
from services.audit_service import record_audit_event
from services.rate_limit_service import enforce_public_contact_rate_limit
from database import service_supabase
from services.academy_exchange_service import Decision as ExchangeDecision

router=APIRouter(prefix='/elearning/owner',tags=['Academy Owner'])


@router.post('/payments/{checkout_id}/reconcile')
def reconcile(checkout_id:UUID,request:Request,response:Response):
    from services.learning_payment_provider import reconcile_checkout
    actor=member(request,response)
    def execute():
        result=reconcile_checkout(actor,checkout_id);audit(request,actor,'payment.reconcile',checkout_id);return result
    return operation(execute)


def audit(request,actor,action,target):
    record_audit_event(request=request,actor_user_id=actor.user_id,tenant_id=actor.tenant_id,action='academy.'+action,target_type='academy_owner',target_id=str(target))


@router.get('/dashboard')
def dashboard(request:Request,response:Response):
    actor=owner(request,response)
    return operation(lambda:service.dashboard(actor))


@router.get('/students')
def students(request:Request,response:Response,classification:Literal['institution','regular']|None=None,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    actor=owner(request,response)
    return operation(lambda:service.classified_students(actor,classification,limit,offset))


@router.get('/exchange')
def exchange(request:Request,response:Response,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    actor=owner(request,response)
    return operation(lambda:service.opportunities(actor,True,limit,offset))


@router.post('/exchange')
def create_exchange(payload:service.Opportunity,request:Request,response:Response):
    actor=owner(request,response)
    def execute():
        result=service.save_opportunity(actor,payload);audit(request,actor,'opportunity.create',result['id']);return result
    return operation(execute)


@router.put('/exchange/{identifier}')
def update_exchange(identifier:UUID,payload:service.Opportunity,request:Request,response:Response):
    actor=owner(request,response)
    def execute():
        result=service.save_opportunity(actor,payload,identifier);audit(request,actor,'opportunity.'+payload.status,identifier);return result
    return operation(execute)


@router.get('/exchange/available/for-me')
def available_exchange(request:Request,response:Response):
    actor=member(request,response)
    return operation(lambda:service.opportunities(actor))


@router.get('/applications/{application}/documents')
def documents(application:UUID,request:Request,response:Response):
    actor=member(request,response)
    return operation(lambda:service.documents(actor,application))


@router.post('/applications/{application}/documents')
async def upload_document(application:UUID,request:Request,response:Response,file:UploadFile=File(...)):
    actor=member(request,response)
    from services.rate_limit_service import enforce_builder_asset_upload_rate_limit
    enforce_builder_asset_upload_rate_limit(request,actor.user_id,actor.tenant_id)
    result=await service.upload_document(actor,application,file)
    audit(request,actor,'document.upload',result['id']);return result


@router.get('/applications/{application}/documents/{identifier}')
def download_document(application:UUID,identifier:UUID,request:Request,response:Response):
    actor=member(request,response)
    def execute():
        row,content=service.download_document(actor,application,identifier)
        audit(request,actor,'document.download',identifier)
        return Response(content,media_type=row['mime_type'],headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Disposition':'attachment; filename="'+row['filename']+'"'})
    return operation(execute)


@router.delete('/applications/{application}/documents/{identifier}')
def remove_document(application:UUID,identifier:UUID,request:Request,response:Response):
    actor=member(request,response)
    def execute():
        result=service.remove_document(actor,application,identifier);audit(request,actor,'document.remove',identifier);return result
    return operation(execute)


@router.get('/contacts')
def contacts(request:Request,response:Response,search:str=Query('',max_length=120),unread:bool=False,limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    actor=owner(request,response);require_capability(actor.tenant_id,'contact');service.require_upgrade()
    def execute():
        query=service_supabase.table('contacts').select('*').eq('tenant_id',actor.tenant_id)
        if unread:query=query.is_('read_at','null')
        if search:query=query.ilike('message','%'+search+'%')
        return {'items':query.order('created_at',desc=True).range(offset,offset+limit-1).execute().data or []}
    return operation(execute)


@router.put('/contacts/{identifier}/read')
def contact_read(identifier:int,payload:service.ContactRead,request:Request,response:Response):
    from datetime import datetime,timezone
    actor=owner(request,response);require_capability(actor.tenant_id,'contact');service.require_upgrade()
    def execute():
        rows=service_supabase.table('contacts').update({'read_at':datetime.now(timezone.utc).isoformat() if payload.read else None}).eq('tenant_id',actor.tenant_id).eq('id',identifier).execute().data or []
        if not rows:raise HTTPException(404,'Contact not found')
        audit(request,actor,'contact.read',identifier);return {'item':rows[0]}
    return operation(execute)


public=APIRouter(prefix='/public/academies',tags=['Academy Contact'])


@public.post('/{identifier}/contact')
def contact(identifier:str,payload:service.Contact,request:Request):
    from routes.public_site_routes import resolve_website_settings,resolve_tenant_id
    from routes.builder_routes import schema_contains_element_type
    from services.elearning_settings_service import get_settings
    enforce_public_contact_rate_limit(request,identifier=identifier)
    website=resolve_website_settings(identifier,request=request);tenant=resolve_tenant_id(website)
    service.require_upgrade();require_capability(tenant,'contact')
    cfg=get_settings(tenant)
    if not cfg['enabled'] or not cfg['academy_enabled']:raise HTTPException(404,'Academy not found')
    rows=service_supabase.table('builder_projects').select('id,published_schema').eq('tenant_id',tenant).eq('id',website.get('academy_project_id')).eq('usage_profile','academy').eq('status','published').limit(1).execute().data or []
    if not rows or not schema_contains_element_type(rows[0]['published_schema'],'academyContact'):raise HTTPException(404,'Contact page not published')
    service_supabase.table('contacts').insert({**payload.model_dump(mode='json'),'tenant_id':tenant,'project_id':rows[0]['id']}).execute()
    return {'success':True}


@router.get('/exchange/opportunities/{identifier}')
def exchange_detail(identifier:UUID,request:Request,response:Response):
    from services import academy_exchange_service as exchange
    actor=member(request,response)
    return operation(lambda:exchange.detail(actor,identifier))


@router.post('/exchange/opportunities/{identifier}/responses')
async def exchange_submit(identifier:UUID,request:Request,response:Response):
    from services import academy_exchange_service as exchange
    from services import elearning_forms_service as forms
    from routes.elearning_forms_routes import response_payload
    from services.rate_limit_service import enforce_public_form_submission_rate_limit
    actor=member(request,response)
    enforce_public_form_submission_rate_limit(request,'elearning-exchange',str(actor.tenant_id)+':'+str(identifier))
    opportunity=operation(lambda:exchange.opportunity(actor,identifier))
    form=operation(lambda:forms.definition(actor.tenant_id,opportunity['application_form_id']))
    payload,uploads=await response_payload(request)
    return await forms.submit(actor.tenant_id,form,actor,payload,uploads,identifier)


@router.put('/exchange/responses/{identifier}/decision')
def exchange_review(identifier:UUID,payload:ExchangeDecision,request:Request,response:Response):
    from services import academy_exchange_service as exchange
    actor=owner(request,response)
    result=operation(lambda:exchange.review(actor,identifier,payload))
    audit(request,actor,'exchange.decision',identifier)
    return result

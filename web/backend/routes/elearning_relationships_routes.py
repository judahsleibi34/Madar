from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Request,Response,Query
from services.elearning_access_service import require_elearning_access
from services.audit_service import record_audit_event
from services import elearning_relationships_service as service
from routes.elearning_structure_routes import operation
router=APIRouter(prefix='/elearning/relationships',tags=['E-Learning Assignments'])
Kind=Literal['group','course','instructor']


def context(request,response):
    response.headers['Cache-Control']='private, no-store'
    return require_elearning_access(request,response,'elearning.manage')


@router.get('/candidates')
def candidates(request:Request,response:Response,kind:Literal['users','courses','groups','instructors'],query:str=Query('',max_length=120),limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0)):
    member=context(request,response)
    def read():
        rows=service.call('get_elearning_relationship_candidates',member.tenant_id,p_kind=kind,p_query=query.strip(),p_limit=limit+1,p_offset=offset)
        return {'items':rows[:limit],'has_more':len(rows)>limit}
    return operation(read)


@router.get('/directory-summary')
def summary(request:Request,response:Response,kind:Literal['groups','instructors']):
    member=context(request,response)
    return operation(lambda:service.call('get_elearning_directory_summary',member.tenant_id,p_kind=kind))


@router.get('/{kind}/{entity_id}')
def get(kind:Kind,entity_id:UUID,request:Request,response:Response,member_query:str=Query("",max_length=120),member_offset:int=Query(0,ge=0)):
    member=context(request,response)
    return operation(lambda:service.snapshot(member.tenant_id,kind,entity_id,member_query.strip(),member_offset))


@router.post('/{kind}/{entity_id}/commands')
def command(kind:Kind,entity_id:UUID,payload:service.RelationshipCommand,request:Request,response:Response):
    member=context(request,response)
    def execute():
        result=service.execute(member,kind,entity_id,payload)
        record_audit_event(request=request,actor_user_id=member.user_id,tenant_id=member.tenant_id,action='elearning.assignment.'+payload.action,target_type='elearning_'+kind,target_id=str(entity_id),metadata={'target_id':str(payload.target_id) if payload.target_id else None,'user_ids':payload.user_ids})
        return result
    return operation(execute)

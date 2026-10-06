"""Tenant-scoped additive course grants and separate instructor assignments."""
from typing import Literal
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator
from postgrest.exceptions import APIError
from database import service_supabase
from services.elearning_settings_service import settings_available


class RelationshipCommand(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['add_members','remove_member','assign_course','remove_course','assign_group','remove_group','assign_instructor','remove_instructor','link_user','revoke_manual','revoke_free']
    target_id: UUID | None = None
    user_ids: list[int] | None = Field(default=None, min_length=1, max_length=100)
    confirmed: StrictBool = False

    @field_validator('user_ids', mode='before')
    @classmethod
    def ids(cls,value):
        if value is not None and (not isinstance(value,list) or any(type(i) is not int or i<1 for i in value) or len(set(value))!=len(value)):
            raise ValueError('Select unique existing users')
        return value

    @model_validator(mode='after')
    def shape(self):
        users=self.action in {'add_members','remove_member','link_user'}
        if users != (self.user_ids is not None) or users == (self.target_id is not None): raise ValueError('Select the correct assignment target')
        if self.action=='link_user' and len(self.user_ids)!=1: raise ValueError('Select one user')
        if self.action.startswith(('remove_','revoke_')) and not self.confirmed: raise ValueError('Confirm removal of this source only')
        return self


def call(name, tenant_id, **args):
    if not settings_available(126): raise HTTPException(503,detail={'code':'elearning_assignments_upgrade_required'})
    try: return service_supabase.rpc(name,{'p_tenant_id':tenant_id,**args}).execute().data
    except APIError as error:
        if error.code=='P0002': raise HTTPException(404,'Learning assignment or eligible user not found') from error
        if error.code=='42501': raise HTTPException(403,'Tenant owner or admin access required') from error
        if error.code=='23505': raise HTTPException(409,'This identity is already linked') from error
        if error.code in {'22023','23503','23514'}: raise HTTPException(400,'Invalid, inactive or unconfirmed assignment') from error
        raise


def snapshot(tenant_id,kind,entity,query="",offset=0):
    return call('get_elearning_relationships',tenant_id,p_kind=kind,p_entity_id=str(entity),p_member_query=query,p_member_offset=offset)


def execute(member,kind,entity,command):
    call('manage_elearning_relationships',member.tenant_id,p_actor_id=member.user_id,p_kind=kind,p_entity_id=str(entity),**{'p_'+k:v for k,v in command.model_dump(mode='json').items()})
    return snapshot(member.tenant_id,kind,entity)

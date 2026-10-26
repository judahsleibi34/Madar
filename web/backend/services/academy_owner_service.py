"""Owner tools extend existing learning, contacts, private storage and settings."""
from datetime import date, datetime
from uuid import uuid4, UUID
from typing import Literal
from pathlib import Path
from tempfile import TemporaryDirectory
from hashlib import sha256
import logging
from fastapi import HTTPException
from pydantic import Field, StrictBool, EmailStr, model_validator
from database import service_supabase
from services.academy_programme_service import Payload, available, report
from services.academy_capability_service import capabilities
from services.elearning_settings_service import settings_available, get_settings
from services.builder_asset_storage import store_builder_asset, delete_builder_asset, download_builder_asset, ensure_builder_asset_bucket, BUILDER_ASSET_BUCKET
from services.builder_asset_validation import detect_builder_asset_content_type, validate_builder_asset_file
from services.storage_quota_service import reserve_storage, finish_storage, release_storage
from services.upload_config import get_data_upload_dir

logger = logging.getLogger(__name__)


def require_upgrade():
    if not settings_available(140): raise HTTPException(503, 'Academy owner tools require the database upgrade')


def require_private_storage():
    ensure_builder_asset_bucket()
    bucket = service_supabase.storage.get_bucket(BUILDER_ASSET_BUCKET)
    public = bucket.get('public') if isinstance(bucket, dict) else getattr(bucket, 'public', None)
    if public is not False: raise HTTPException(503, 'Private document storage is unavailable')


class Opportunity(Payload):
    application_form_id: UUID | None = None
    title: str = Field(min_length=1, max_length=160)
    short_description: str = Field(default='', max_length=1200)
    description: str = Field(default='', max_length=12000)
    host_institution: str = Field(default='', max_length=200)
    location: str = Field(default='', max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    deadline: datetime | None = None
    requirements: str = Field(default='', max_length=8000)
    capacity: int | None = Field(default=None, ge=1, le=100000, strict=True)
    status: Literal['draft','published','closed','archived'] = 'draft'
    expected_revision: int = Field(default=1, ge=1, strict=True)

    @model_validator(mode='after')
    def valid_dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date: raise ValueError('End date precedes start date')
        if self.deadline and self.deadline.tzinfo is None: raise ValueError('Deadline requires a timezone')
        return self


class Contact(Payload):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    subject: str = Field(default='', max_length=200)
    message: str = Field(min_length=1, max_length=8000)
    phone: str = Field(default='', max_length=50)


class ContactRead(Payload):
    read: StrictBool


def opportunities(actor, management=False, limit=50, offset=0):
    require_upgrade();available(actor, 'exchange')
    query=service_supabase.table('academy_exchange_opportunities').select('*').eq('tenant_id',actor.tenant_id)
    if not management:
        from services.academy_exchange_service import gate
        gate(actor)
        rows=service_supabase.rpc('get_academy_open_opportunities',{'p_tenant':actor.tenant_id,'p_user':actor.user_id,'p_limit':limit}).execute().data or []
        return {'items':rows}
    return {'items':query.order('updated_at',desc=True).range(offset,offset+limit-1).execute().data or []}


def save_opportunity(actor, payload, identifier=None):
    require_upgrade();available(actor,'exchange')
    if payload.application_form_id or payload.status == 'published':
        from services.academy_exchange_service import gate
        gate(actor)
        if payload.status == 'published':
            from services.entitlement_service import require_entitlement
            require_entitlement(actor.tenant_id,'public_form_links')
    return service_supabase.rpc('manage_academy_opportunity',{'p_tenant':actor.tenant_id,'p_admin':actor.user_id,'p_id':str(identifier) if identifier else None,'p_revision':payload.expected_revision,'p_data':payload.model_dump(mode='json',exclude={'expected_revision'})}).execute().data


def application_access(actor, identifier, write=False):
    require_upgrade();available(actor,'tuition')
    rows=service_supabase.table('academy_applications').select('*').eq('tenant_id',actor.tenant_id).eq('id',str(identifier)).eq('kind','tuition').limit(1).execute().data or []
    if not rows: raise HTTPException(404,'Application not found')
    row=rows[0]
    if (write or actor.role not in {'owner','admin'}) and row['user_id'] != actor.user_id: raise HTTPException(403,'Applicant access required')
    if write and row['status'] not in {'submitted','under_review'}: raise HTTPException(403,'Documents are locked after review')
    return row


def documents(actor, application):
    application_access(actor,application)
    rows=service_supabase.table('academy_application_documents').select('id,filename,mime_type,size_bytes,created_at').eq('tenant_id',actor.tenant_id).eq('application_id',str(application)).is_('removed_at','null').order('created_at').execute().data or []
    return {'items':rows}


async def upload_document(actor, application, file):
    application_access(actor,application,True)
    data=await file.read(5*1024*1024+1)
    if not data or len(data)>5*1024*1024: raise HTTPException(413,'Document must be between 1 byte and 5 MB')
    mime=detect_builder_asset_content_type(data)
    extensions={'application/pdf':'.pdf','image/png':'.png','image/jpeg':'.jpg'}
    if mime not in extensions or file.content_type != mime: raise HTTPException(415,'Use a PDF, PNG or JPEG document')
    with TemporaryDirectory() as directory:
        path=Path(directory)/('document'+extensions[mime]);path.write_bytes(data)
        try:
            if mime=='application/pdf': validate_builder_asset_file(path,mime)
            else:
                from PIL import Image
                with Image.open(path) as image:
                    if image.width*image.height>20000000: raise ValueError('Image too large')
                    image.verify()
        except Exception as error: raise HTTPException(422,'Invalid document') from error
    identifier=uuid4();key=f'academy-private/tenant_{actor.tenant_id}/application_{application}/{identifier}'
    # Original filename is never used as a path, URL or response header.
    filename='document-'+str(identifier)[:8]+extensions[mime]
    values={'storage_key':key,'filename':filename,'mime_type':mime,'size_bytes':len(data),'sha256':sha256(data).hexdigest()}
    require_private_storage()
    reservation=reserve_storage(tenant_id=actor.tenant_id,user_id=actor.user_id,category='academy_document',size_bytes=len(data),storage_root=get_data_upload_dir())
    try:
        store_builder_asset(storage_key=key,content=data,content_type=mime)
        finish_storage(reservation_id=reservation,succeeded=True,storage_key=key,sha256_hex=values['sha256'])
    except Exception:
        delete_builder_asset(storage_key=key)
        release_storage(tenant_id=actor.tenant_id,category='academy_document',storage_key=key)
        finish_storage(reservation_id=reservation,succeeded=False)
        raise
    try:
        result=service_supabase.rpc('manage_academy_document',{'p_tenant':actor.tenant_id,'p_user':actor.user_id,'p_application':str(application),'p_id':str(identifier),'p_data':values}).execute().data
        if not isinstance(result,dict) or str(result.get('id')) != str(identifier):
            raise ValueError('Document acknowledgement identity mismatch')
        return {k:result[k] for k in ['id','filename','mime_type','size_bytes','created_at']}
    except Exception as error:
        # Transport failures and malformed replies cannot establish rollback.
        # Retain bytes AND their quota until scoped metadata reconciliation;
        # an empty follow-up read could race an in-flight metadata transaction.
        logger.error('academy.document_commit_unknown',extra={'error_type':type(error).__name__})
        raise HTTPException(503,{'code':'private_upload_outcome_unknown',
            'document_id':str(identifier),
            'message':'Document outcome is uncertain. Bytes are retained; check the application documents before uploading again.'}) from error


def document_row(actor,application,identifier):
    application_access(actor,application)
    rows=service_supabase.table('academy_application_documents').select('*').eq('tenant_id',actor.tenant_id).eq('application_id',str(application)).eq('id',str(identifier)).is_('removed_at','null').limit(1).execute().data or []
    if not rows: raise HTTPException(404,'Document not found')
    return rows[0]


def download_document(actor,application,identifier):
    row=document_row(actor,application,identifier)
    require_private_storage()
    content=download_builder_asset(storage_key=row['storage_key'])
    if sha256(content).hexdigest() != row['sha256']: raise HTTPException(503, 'Document integrity check failed')
    return row,content


def remove_document(actor,application,identifier):
    application_access(actor,application,True)
    result=service_supabase.rpc('manage_academy_document',{'p_tenant':actor.tenant_id,'p_user':actor.user_id,'p_application':str(application),'p_id':str(identifier),'p_data':None}).execute().data
    # Retain metadata for audit, remove private bytes. Removed files cannot be read
    # even if physical cleanup fails; the storage layer is never publicly mounted.
    delete_builder_asset(storage_key=result['storage_key'])
    release_storage(tenant_id=actor.tenant_id,category='academy_document',storage_key=result['storage_key'])
    return {'success':True}


def dashboard(actor):
    require_upgrade()
    grants=capabilities(actor.tenant_id)
    result=service_supabase.rpc('academy_owner_dashboard',{'p_tenant':actor.tenant_id,'p_admin':actor.user_id}).execute().data
    for field,cap in [('affiliates','affiliate'),('support_eligible','tuition'),('purchases','transactions'),('revenue','transactions'),('withdrawals','withdrawal'),('rewards','rewards'),('wallets','wallet')]:
        if not grants[cap]: result.pop(field,None)
    result['applications']=[row for row in result['applications'] if grants[row['kind']]]
    # No private finance/application activity for an unentitled module.
    allowed_activity=('learning_course','learning_topic','learning_section','learning_exam','learning_certificate','learning_enrollment')
    result['recent_activity']=[row for row in result['recent_activity'] if row['event_type'].startswith(allowed_activity)]
    if grants['reports']: result['progress']=report(actor)['summary']
    return result


def classified_students(actor, classification=None, limit=50, offset=0):
    require_upgrade()
    # Canonical user identity is joined by linked user_id and tenant membership,
    # never inferred from an editable learner contact email or frontend label.
    result=service_supabase.rpc('academy_classified_students',{'p_tenant':actor.tenant_id,'p_admin':actor.user_id,'p_classification':classification,'p_limit':limit,'p_offset':offset}).execute().data
    result['learners']=result['learners'][:limit]
    return result

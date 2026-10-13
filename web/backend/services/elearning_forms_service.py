"""Independent learning forms. Builder persistence is deliberately not imported."""
import csv
import logging
import io
import json
import math
import re
from datetime import date
from hashlib import sha256
from uuid import UUID, uuid4
from tempfile import TemporaryDirectory
from pathlib import Path
from fastapi import HTTPException
from pydantic import Field, StrictBool, model_validator
from database import service_supabase
from services.academy_programme_service import Payload
from services.elearning_settings_service import settings_available
from services.entitlement_service import require_entitlement
from services.academy_owner_service import require_private_storage
from services.builder_asset_storage import store_builder_asset, delete_builder_asset, download_builder_asset
from services.builder_asset_validation import detect_builder_asset_content_type, validate_builder_asset_file
from services.storage_quota_service import reserve_storage, finish_storage, release_storage
from services.upload_config import get_data_upload_dir
from postgrest.exceptions import APIError

logger=logging.getLogger(__name__)
TYPES={'shortText','paragraph','email','phone','number','dropdown','radio','checkboxes','date','file'}

def require_schema():
    if not settings_available(141): raise HTTPException(503,'E-Learning Forms require the database upgrade')

def gate(tenant, capability='forms'):
    require_schema();return require_entitlement(tenant,capability)

def fields(schema):
    return [field for section in schema['sections'] for field in section['fields']]

class Definition(Payload):
    name: str = Field(min_length=1,max_length=160)
    status: str = 'inactive'
    expected_version: int = Field(default=1,ge=1,strict=True)
    form_schema: dict = Field(alias="schema")

    @model_validator(mode='after')
    def valid(self):
        if self.status not in {'active','inactive','archived'}:raise ValueError('Invalid form status')
        try: validate_schema(self.form_schema)
        except (TypeError, KeyError, OverflowError) as error: raise ValueError("Invalid form schema") from error
        return self

class ResponseEdit(Payload):
    read: StrictBool
    owner_notes: str = Field(default='',max_length=4000)


def validate_schema(s):
    allowed={'title','description','sections','logicRules','submitLabel','successMessage','access','notifyOwner','confirmSubmitter','pageMode','languageMode','defaultLanguage','localized','workflow','metadata'}
    if set(s)-allowed or len(json.dumps(s))>150000:raise ValueError('Invalid form schema')
    for key,maximum in [('title',160),('description',4000),('submitLabel',120),('successMessage',1200)]:
        if not isinstance(s.get(key,''),str) or len(s.get(key,''))>maximum:raise ValueError('Invalid form text')
    if not s.get('title','').strip():raise ValueError('Form title is required')
    if s.get('languageMode','en') not in {'en','ar','bilingual'} or s.get('defaultLanguage','en') not in {'en','ar'}:
        raise ValueError('Unsupported form language')
    validate_localized(s, {'title':160,'description':4000,'submitLabel':120,'successMessage':1200})
    metadata=s.get('metadata',{})
    if not isinstance(metadata,dict) or len(metadata)>20 or any(not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',key) or not isinstance(value,str) or len(value)>500 for key,value in metadata.items()):
        raise ValueError('Invalid form metadata')
    if s.get('access','public') not in {'public','authenticated','enrolled'} or s.get('pageMode','paged') not in {'paged','single'}:raise ValueError('Invalid form access/page mode')
    if any(type(s.get(key,False)) is not bool for key in ('notifyOwner','confirmSubmitter')):raise ValueError('Invalid notification setting')
    sections=s.get('sections');ids=[]
    if not isinstance(sections,list) or not 1<=len(sections)<=10:raise ValueError('Use 1–10 form pages')
    section_ids=set()
    for section in sections:
        if not isinstance(section,dict) or set(section)-{'id','title','fields','localized'} or not isinstance(section.get('id'),str) or section['id'] in section_ids:raise ValueError('Invalid page')
        validate_localized(section, {'title':160})
        section_ids.add(section['id'])
        if not isinstance(section.get('title',''),str) or len(section.get('title',''))>160 or not isinstance(section.get('fields'),list):raise ValueError('Invalid page fields')
        for f in section['fields']:
            if not isinstance(f,dict) or set(f)-{'id','type','label','helpText','placeholder','required','options','defaultValue','validation','maxFileSizeMb','localized'}:raise ValueError('Invalid field schema')
            validate_localized(f, {'label':200,'helpText':1200,'placeholder':300,'options':200})
            if not isinstance(f.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',f['id']) or f['id'] in ids or f.get('type') not in TYPES:raise ValueError('Invalid field ID/type')
            ids.append(f['id'])
            if type(f.get('required',False)) is not bool:raise ValueError('Invalid required setting')
            for k,m in [('label',200),('placeholder',300),('helpText',1200)]:
                if not isinstance(f.get(k,''),str) or len(f.get(k,''))>m:raise ValueError('Invalid field text')
            if not f.get('label','').strip():raise ValueError('Field label required')
            options=f.get('options',[])
            if not isinstance(options,list) or len(options)>100 or any(not isinstance(x,str) or not x or len(x)>200 for x in options) or len(set(options))!=len(options):raise ValueError('Invalid options')
            if f['type'] in {'dropdown','radio','checkboxes'} and not options:raise ValueError('Choice fields need options')
            v=f.get('validation',{})
            if not isinstance(v,dict) or set(v)-{'min','max','minLength','maxLength'} or any(type(x) not in {int,float} or not math.isfinite(x) for x in v.values()):raise ValueError('Invalid validation limits')
            if any(k in v and (type(v[k]) is not int or not 0<=v[k]<=12000) for k in ['minLength','maxLength']):raise ValueError('Invalid text limits')
            for a,b in [('min','max'),('minLength','maxLength')]:
                if a in v and b in v and v[a]>v[b]:raise ValueError('Invalid validation range')
            if type(f.get('maxFileSizeMb',5)) not in {int,float} or not 0<f.get('maxFileSizeMb',5)<=5:raise ValueError('File limit exceeds 5 MB')
            if f.get('defaultValue','') not in ('',None,[]):
                if f['type']=='file':raise ValueError('File fields cannot have uploaded defaults')
                validate_value(f,f['defaultValue'])
    if not 1<=len(ids)<=100:raise ValueError('Use 1–100 fields')
    workflow=s.get('workflow',{})
    if not isinstance(workflow,dict) or set(workflow)-{'kind','termsFieldId'} or workflow.get('kind','none') not in {'none','affiliate','tuition','exchange'}:
        raise ValueError('Invalid form workflow')
    if workflow.get('kind','none')!='none':
        terms=next((field for field in fields(s) if field['id']==workflow.get('termsFieldId')),None)
        if not terms or terms['type']!='checkboxes' or not terms.get('required') or len(terms['options'])!=1:
            raise ValueError('Choose a required single-option terms acceptance field')
        if s.get('access','public')=='public':raise ValueError('Programme applications require authentication')
    rules=s.get('logicRules',[])
    if not isinstance(rules,list) or len(rules)>200:raise ValueError('Invalid conditional logic')
    for r in rules:
        if not isinstance(r,dict) or set(r)-{'id','sourceFieldId','targetFieldId','operator','value','action'} or r.get('operator','equals')!='equals' or r.get('action') not in {'show','hide'}:raise ValueError('Invalid conditional rule')
        if r.get('sourceFieldId') not in ids or r.get('targetFieldId') not in ids or ids.index(r['sourceFieldId'])>=ids.index(r['targetFieldId']):raise ValueError('Conditional source must precede target')
        if not isinstance(r.get('value',''),str) or len(r.get('value',''))>200 or next(f for f in fields(s) if f['id']==r['sourceFieldId'])['type']=='file':raise ValueError('Invalid conditional value')


def validate_localized(source, limits):
    translations=source.get('localized',{})
    if not isinstance(translations,dict) or set(translations)-set(limits):
        raise ValueError('Invalid localized presentation')
    for key, languages in translations.items():
        if not isinstance(languages,dict) or set(languages)-{'en','ar'}:
            raise ValueError('Unsupported translation language')
        for value in languages.values():
            if key=='options':
                if (not isinstance(value,list) or len(value)!=len(source.get('options',[]))
                        or any(not isinstance(item,str) or not item.strip() or len(item)>limits[key] for item in value)):
                    raise ValueError('Choice translations must match canonical options')
            elif not isinstance(value,str) or len(value)>limits[key]:
                raise ValueError('Invalid translated text')


def visible(schema, field, answers):
    result=True
    for rule in schema.get('logicRules',[]):
        if rule['targetFieldId']!=field['id']:continue
        raw=answers.get(rule['sourceFieldId'],'');text=','.join(str(x) for x in raw) if isinstance(raw,list) else str(raw)
        matched=text.strip()==rule.get('value','').strip()
        if rule['action']=='show':result=matched
        elif matched:result=False
    return result


def validate_value(f,value):
    t=f['type']
    if t=='file':
        if not isinstance(value,dict) or not {'id','name','size','type'}<=set(value):raise ValueError('Invalid file')
        UUID(value['id'])
        return
    if t=='checkboxes':
        if not isinstance(value,list) or len(value)!=len(set(value)) or any(x not in f['options'] for x in value):raise ValueError('Choose valid options')
        return
    if isinstance(value,(dict,list,bool)) or value is None:raise ValueError('Invalid field value')
    text=str(value).strip()
    if len(text)>12000:raise ValueError('Answer too long')
    if t=='email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',text):raise ValueError('Invalid email')
    if t=='phone' and (not re.fullmatch(r'[+()\d\s.-]+',text) or not 7<=len(re.sub(r'\D','',text))<=15):raise ValueError('Invalid phone')
    if t=='date':
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',text):raise ValueError('Invalid date')
        date.fromisoformat(text)
    if t in {'dropdown','radio'} and value not in f['options']:raise ValueError('Choose valid option')
    limits=f.get('validation',{})
    if t=='number':
        number=float(text)
        if not math.isfinite(number) or ('min' in limits and number<limits['min']) or ('max' in limits and number>limits['max']):raise ValueError('Number outside limits')
    if ('minLength' in limits and len(text)<limits['minLength']) or ('maxLength' in limits and len(text)>limits['maxLength']):raise ValueError('Text outside limits')


def clean_answers(schema, answers):
    if not isinstance(answers,dict) or set(answers)-{f['id'] for f in fields(schema)}:raise HTTPException(422,'Unknown form fields')
    cleaned={}
    for f in fields(schema):
        if not visible(schema,f,cleaned):continue
        value=answers.get(f['id'],f.get('defaultValue',''))
        if value in ('',None,[]):
            if f.get('required'):raise HTTPException(422,detail={'field_id':f['id'],'message':'Required field is missing'})
            continue
        try:validate_value(f,value)
        except (ValueError,TypeError,OverflowError) as e:raise HTTPException(422,detail={'field_id':f['id'],'message':str(e)}) from e
        cleaned[f['id']]=value.strip() if isinstance(value,str) else value
    return cleaned


def rpc(name,params):
    try:return service_supabase.rpc(name,params).execute().data
    except APIError as error:
        raise HTTPException({'42501':403,'40001':409,'P0002':404,'23503':404,'23505':409,'23514':422,'22023':422}.get(error.code,503),'Form request unavailable or changed; refresh and try again') from error


def definition(tenant,identifier,version=None):
    rows=service_supabase.table('elearning_forms').select('*').eq('tenant_id',tenant).eq('id',str(identifier)).limit(1).execute().data or []
    if not rows:raise HTTPException(404,'Form not found')
    f=rows[0];v=version or f['version']
    versions=service_supabase.table('elearning_form_versions').select('schema').eq('tenant_id',tenant).eq('form_id',str(identifier)).eq('version',v).limit(1).execute().data or []
    if not versions:raise HTTPException(404,'Form version not found')
    return {**f,'schema':versions[0]['schema']}


def save(actor,payload,identifier=None):
    gate(actor.tenant_id)
    kind=payload.form_schema.get('workflow',{}).get('kind','none')
    if kind!='none':
        require_reviews()
        from services.academy_programme_service import available
        available(actor,kind)
    return rpc('manage_elearning_form',{'p_tenant':actor.tenant_id,'p_user':actor.user_id,'p_id':str(identifier) if identifier else None,'p_revision':payload.expected_version,'p_name':payload.name,'p_status':payload.status,'p_schema':payload.form_schema})


def forms(actor):
    gate(actor.tenant_id,'response_management')
    query=service_supabase.table('elearning_forms').select('*').eq('tenant_id',actor.tenant_id).order('updated_at',desc=True).order('id')
    rows=[];offset=0
    while True:
        page=query.range(offset,offset+499).execute().data or []
        rows.extend(page)
        if len(page)<500:break
        offset+=500
    counts=rpc('elearning_form_counts',{'p_tenant':actor.tenant_id,'p_user':actor.user_id})
    for row in rows:row.update(counts.get(str(row['id']),{'responses':0,'unread':0}))
    return {'review_available':settings_available(144),'items':rows,'visible':any(f['status'] in {'active','archived'} or f['responses'] for f in rows)}


def public_access(tenant,form,actor,viewing=False):
    gate(tenant);require_entitlement(tenant,'public_form_links')
    if form['status']!='active':raise HTTPException(404,'Form unavailable')
    access=form['schema'].get('access','public')
    # Anyone may read published questions; submitting still requires sign-in and every eligibility check.
    if viewing:
        if form['schema'].get('workflow',{}).get('kind','none')!='none':require_reviews()
        if actor is None:return {'requires_sign_in':access!='public','locked_reason':None}
        try:public_access(tenant,form,actor)
        except HTTPException as error:
            if error.status_code!=403:raise
            eligibility=error.detail in {'Programme eligibility requirements are not met','Active course enrollment required'}
            return {'requires_sign_in':False,'locked_reason':'eligibility' if eligibility else 'unavailable'}
        return {'requires_sign_in':False,'locked_reason':None}
    if access!='public' and actor is None:raise HTTPException(401,'Sign in to complete this form')
    if actor:
        if actor.tenant_id!=tenant:raise HTTPException(403,'Form tenant mismatch')
        if access=='enrolled':
            result=rpc('elearning_form_enrolled',{'p_tenant':tenant,'p_user':actor.user_id})
            if not result:raise HTTPException(403,'Active course enrollment required')
    kind=form['schema'].get('workflow',{}).get('kind','none')
    if kind!='none':
        require_reviews()
        if actor is None:raise HTTPException(401,'Sign in to apply')
        from services.academy_programme_service import available, programme_rpc
        available(actor,kind)
        if kind in {'tuition','exchange'}:
            eligibility=programme_rpc('academy_wallet',actor)
            if not eligibility.get(kind+'_eligible'):raise HTTPException(403,'Programme eligibility requirements are not met')


def responses(actor,form_id=None,search='',unread=False,date_from=None,date_to=None,identity=None,limit=50,offset=0,opportunity_id=None):
    gate(actor.tenant_id,'response_management')
    query=service_supabase.table('elearning_form_responses').select('*').eq('tenant_id',actor.tenant_id)
    if opportunity_id:
        from services.academy_exchange_service import gate as exchange_gate
        exchange_gate(actor, 'response_management')
        query=query.eq('opportunity_id',str(opportunity_id))
    if form_id:query=query.eq('form_id',str(form_id))
    if search:query=query.ilike('search_text','%'+search+'%')
    if unread:query=query.is_('read_at','null')
    if date_from:query=query.gte('submitted_at',date_from.isoformat())
    if date_to:query=query.lte('submitted_at',date_to.isoformat())
    if identity=='guest':query=query.is_('user_id','null')
    elif identity=='authenticated':query=query.not_.is_('user_id','null')
    rows=query.order('submitted_at',desc=True).range(offset,offset+limit).execute().data or []
    return {'items':rows[:limit],'has_more':len(rows)>limit}


def response_detail(actor,identifier):
    gate(actor.tenant_id,'response_management')
    rows=service_supabase.table('elearning_form_responses').select('*').eq('tenant_id',actor.tenant_id).eq('id',str(identifier)).limit(1).execute().data or []
    if not rows:raise HTTPException(404,'Response not found')
    r=rows[0];r['definition']=definition(actor.tenant_id,r['form_id'],r['version'])
    r['files']=service_supabase.table('elearning_form_files').select('id,field_id,filename,size_bytes,mime_type').eq('tenant_id',actor.tenant_id).eq('response_id',str(identifier)).execute().data or []
    if settings_available(144):
        reviews=service_supabase.table('elearning_form_reviews').select('*').eq('tenant_id',actor.tenant_id).eq('response_id',str(identifier)).limit(1).execute().data or []
        r['review']=reviews[0] if reviews else None
        r['decision_history']=service_supabase.table('elearning_form_decision_history').select('revision,actor_id,old_status,new_status,note,created_at').eq('tenant_id',actor.tenant_id).eq('response_id',str(identifier)).order('revision').execute().data or []
        identifiers=list({entry['actor_id'] for entry in r['decision_history']})
        names={}
        if identifiers:
            people=service_supabase.table('users').select('id,first_name,last_name').eq('tenant_id',actor.tenant_id).in_('id',identifiers).execute().data or []
            names={person['id']:' '.join(filter(None,[person.get('first_name'),person.get('last_name')])) for person in people}
        for entry in r['decision_history']:entry['reviewer_name']=names.get(entry['actor_id'],'')
    if r.get('opportunity_id'):
        from services.academy_exchange_service import review_context
        try:r['exchange'] = review_context(actor,r)
        except HTTPException as error:
            # Forms history remains readable under Forms authority when a domain
            # entitlement expires; Exchange decisions keep their own gate.
            if error.status_code not in {402,403}:raise
            r['exchange'] = None
    return r


def require_reviews():
    if not settings_available(144):raise HTTPException(503,'General Forms review requires the schema144 candidate')


class Decision(Payload):
    status: str
    revision: int = Field(ge=1,strict=True)
    note: str = Field(min_length=1,max_length=4000)

    @model_validator(mode='after')
    def valid(self):
        if self.status not in {'under_review','approved','not_approved','suspended'}:raise ValueError('Invalid review status')
        return self


def review_response(actor,identifier,payload):
    require_reviews();gate(actor.tenant_id,'response_management')
    if actor.role not in {'owner','admin'}:raise HTTPException(403,'Owner or admin review required')
    response=response_detail(actor,identifier)
    kind=response['definition']['schema'].get('workflow',{}).get('kind','none')
    if kind!='none':
        from services.academy_programme_service import available
        available(actor,kind)
    return rpc('review_elearning_form_response',{'p_tenant':actor.tenant_id,'p_admin':actor.user_id,'p_response':str(identifier),'p_status':payload.status,'p_revision':payload.revision,'p_note':payload.note})


def applicant_responses(actor,limit=25,offset=0):
    require_reviews();gate(actor.tenant_id)
    rows=(service_supabase.table('elearning_form_responses')
          .select('id,form_id,version,submitted_at')
          .eq('tenant_id',actor.tenant_id).eq('user_id',actor.user_id)
          .order('submitted_at',desc=True).range(offset,offset+limit).execute()).data or []
    items=[]
    for row in rows[:limit]:
        # Reuse the canonical applicant projection so revoked membership,
        # immutable versions and private reviewer fields retain one authority.
        value=applicant_response(actor,row['id'])
        items.append({key:value[key] for key in ('id','status','submitted_at')} | {
            'title':value['schema'].get('title',''),
            'localized':{'title':value['schema'].get('localized',{}).get('title',{})},
        })
    return {'items':items,'has_more':len(rows)>limit}


def applicant_response(actor,identifier):
    require_reviews();gate(actor.tenant_id)
    return rpc('get_elearning_form_applicant_response',{'p_tenant':actor.tenant_id,'p_user':actor.user_id,'p_response':str(identifier)})


def export_csv(actor,filters):
    gate(actor.tenant_id,'data_exports')
    rows=[]
    for offset in range(0,10000,1000):
        page=responses(actor,limit=1000,offset=offset,**filters);rows.extend(page['items'])
        if not page['has_more']:break
    else:raise HTTPException(413,'Export exceeds 10000 responses; narrow the filters')
    output=io.StringIO();writer=csv.writer(output);writer.writerow(['response_id','form_id','version','submitted_at','user_id','answers','schema_snapshot'])
    snapshots={}
    for r in rows:
        snapshot_key=(r['form_id'],r['version'])
        if snapshot_key not in snapshots:snapshots[snapshot_key]=definition(actor.tenant_id,r['form_id'],r['version'])['schema']
        values=[str(r.get(k,'')) for k in ['id','form_id','version','submitted_at','user_id']]+[json.dumps(r['answers'],ensure_ascii=False),json.dumps(snapshots[snapshot_key],ensure_ascii=False)]
        writer.writerow(["'"+v if v.lstrip().startswith(('=','+','-','@')) else v for v in values])
    return output.getvalue()


async def submit(tenant,form,actor,payload,uploads,opportunity_id=None):
    public_access(tenant,form,actor)
    if opportunity_id:
        from services.academy_exchange_service import gate as exchange_gate
        if actor is None:raise HTTPException(401,'Sign in to apply')
        exchange_gate(actor)
        if actor.tenant_id != tenant:raise HTTPException(403,'Tenant mismatch')
    if set(payload)-{'answers','version','idempotency_key'} or type(payload.get('version')) is not int:raise HTTPException(422,'Invalid response')
    try:key=UUID(payload['idempotency_key'])
    except (KeyError,ValueError,TypeError) as e:raise HTTPException(422,'Invalid submission key') from e
    if payload['version']!=form['version']:raise HTTPException(409,'Form changed; refresh before submitting')
    if not isinstance(payload.get('answers',{}),dict):raise HTTPException(422,'Invalid answers')
    identifier=uuid4();answers=dict(payload.get('answers',{}));files=[];staged=[]
    if len(uploads)>10 or len({name for name,_ in uploads})!=len(uploads):raise HTTPException(422,'Use one file per field, up to ten files')
    for field_id,file in uploads:
        f=next((f for f in fields(form['schema']) if f['id']==field_id and f['type']=='file'),None)
        if not f:raise HTTPException(422,'Unknown file field')
        data=await file.read(5242881);mime=detect_builder_asset_content_type(data)
        if not data or len(data)>min(5242880,int(f.get('maxFileSizeMb',5)*1048576)):raise HTTPException(413,'File exceeds allowed size')
        ext={'application/pdf':'.pdf','image/png':'.png','image/jpeg':'.jpg'}.get(mime)
        if not ext or file.content_type!=mime:raise HTTPException(415,'Use PDF, PNG or JPEG')
        with TemporaryDirectory() as d:
            path=Path(d)/('document'+ext);path.write_bytes(data)
            try:
                if mime=='application/pdf':validate_builder_asset_file(path,mime)
                else:
                    from PIL import Image
                    with Image.open(path) as image:
                        if image.width*image.height>20000000:raise ValueError('Image too large')
                        image.verify()
            except Exception as e:raise HTTPException(422,'Invalid file content') from e
        file_id=uuid4();filename='document-'+str(file_id)[:8]+ext
        meta={'id':str(file_id),'field_id':field_id,'storage_key':f'elearning-private/tenant_{tenant}/response_{identifier}/{file_id}','filename':filename,'mime_type':mime,'size_bytes':len(data),'sha256':sha256(data).hexdigest()}
        files.append((meta,data));answers[field_id]={'id':str(file_id),'name':filename,'size':len(data),'type':mime}
    cleaned=clean_answers(form['schema'],answers)
    files=[item for item in files if item[0]['field_id'] in cleaned]
    # JSON file descriptors cannot claim uploaded objects belonging to other responses.
    if any(f['type']=='file' and f['id'] in cleaned and not any(meta['field_id']==f['id'] for meta,_ in files) for f in fields(form['schema'])):raise HTTPException(422,'File must be uploaded with this response')
    fingerprint={k:v for k,v in cleaned.items() if not any(meta['field_id']==k for meta,_ in files)}
    fingerprint['files']=[{k:meta[k] for k in ['field_id','mime_type','size_bytes','sha256']} for meta,_ in files]
    fingerprint_payload={'answers':fingerprint,'version':form['version']}
    if opportunity_id:fingerprint_payload['opportunity_id']=str(opportunity_id)
    request_hash=sha256(json.dumps(fingerprint_payload,sort_keys=True).encode()).hexdigest()
    try:
        if files:require_private_storage()
        for meta,data in files:
            reservation=reserve_storage(tenant_id=tenant,user_id=actor.user_id if actor else None,category='elearning_form',size_bytes=len(data),storage_root=get_data_upload_dir())
            staged.append((meta,reservation))
            store_builder_asset(storage_key=meta['storage_key'],content=data,content_type=meta['mime_type'])
            finish_storage(reservation_id=reservation,succeeded=True,storage_key=meta['storage_key'],sha256_hex=meta['sha256'])
        result=rpc('submit_elearning_form',{'p_tenant':tenant,'p_user':actor.user_id if actor else None,'p_form':form['id'],'p_version':form['version'],'p_id':str(identifier),'p_key':str(key),'p_hash':request_hash,'p_answers':cleaned,'p_files':[meta for meta,_ in files],**({'p_opportunity':str(opportunity_id)} if opportunity_id else {})})
        if not result['duplicate']:return result
    except Exception:
        cleanup_files(tenant,staged);raise
    cleanup_files(tenant,staged);return result


def cleanup_files(tenant,staged):
    for meta,reservation in staged:
        try:
            delete_builder_asset(storage_key=meta['storage_key'])
            released=release_storage(tenant_id=tenant,category='elearning_form',storage_key=meta['storage_key'])
            if not released:finish_storage(reservation_id=reservation,succeeded=False)
        except Exception as error:
            logger.error('learning_form.cleanup_failed',extra={'tenant_id':tenant,'storage_key':meta['storage_key'],'error_type':type(error).__name__})


def download(actor,response_id,file_id):
    response_detail(actor,response_id)
    rows=service_supabase.table('elearning_form_files').select('*').eq('tenant_id',actor.tenant_id).eq('response_id',str(response_id)).eq('id',str(file_id)).limit(1).execute().data or []
    if not rows:raise HTTPException(404,'File not found')
    row=rows[0];require_private_storage();content=download_builder_asset(storage_key=row['storage_key'])
    if sha256(content).hexdigest()!=row['sha256']:raise HTTPException(503,'File integrity failed')
    return row,content

begin;
do $$
declare v_schema_version public.application_schema_state.schema_version%TYPE;
begin
 select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
 if v_schema_version is null then raise exception 'migration_141_schema_state_missing';end if;
 if v_schema_version <> 140 then raise exception 'migration_141_expected_schema_140_got_%',v_schema_version;end if;
end $$;
create table public.elearning_forms (
 id uuid primary key default extensions.gen_random_uuid(),tenant_id integer not null references public.tenants(tenant_id) on delete restrict,
 name text not null check(length(name) between 1 and 160),status text not null default 'inactive' check(status in ('active','inactive','archived')),
 version integer not null default 1 check(version>0),created_by integer not null,created_at timestamptz not null default now(),updated_at timestamptz not null default now(),
 unique(tenant_id,id),foreign key(tenant_id,created_by) references public.tenant_memberships(tenant_id,user_id) on delete restrict
);
create table public.elearning_form_versions (
 tenant_id integer not null,form_id uuid not null,version integer not null,schema jsonb not null check(jsonb_typeof(schema)='object' and octet_length(schema::text)<=200000),
 created_by integer not null,created_at timestamptz not null default now(),primary key(tenant_id,form_id,version),
 foreign key(tenant_id,form_id) references public.elearning_forms(tenant_id,id) on delete restrict,
 foreign key(tenant_id,created_by) references public.tenant_memberships(tenant_id,user_id) on delete restrict
);
create table public.elearning_form_responses (
 id uuid primary key,tenant_id integer not null,form_id uuid not null,version integer not null,user_id integer,
 answers jsonb not null check(jsonb_typeof(answers)='object' and octet_length(answers::text)<=200000),
 idempotency_key uuid not null,request_hash text not null check(request_hash~'^[a-f0-9]{64}$'),
 search_text text generated always as (answers::text) stored,
 submitted_at timestamptz not null default now(),read_at timestamptz,owner_notes text not null default '' check(length(owner_notes)<=4000),
 unique(tenant_id,id),unique(tenant_id,form_id,idempotency_key),
 foreign key(tenant_id,form_id,version) references public.elearning_form_versions(tenant_id,form_id,version) on delete restrict,
 foreign key(tenant_id,user_id) references public.tenant_memberships(tenant_id,user_id) on delete restrict
);
create index elearning_form_responses_inbox on public.elearning_form_responses(tenant_id,submitted_at desc);
create index elearning_form_responses_form on public.elearning_form_responses(tenant_id,form_id,submitted_at desc);
create table public.elearning_form_files (
 id uuid primary key,tenant_id integer not null,response_id uuid not null,field_id text not null,storage_key text not null unique,
 filename text not null check(filename~'^document-[a-f0-9]{8}\.(pdf|png|jpg)$'),mime_type text not null check(mime_type in ('application/pdf','image/png','image/jpeg')),
 size_bytes integer not null check(size_bytes between 1 and 5242880),sha256 text not null check(sha256~'^[a-f0-9]{64}$'),
 foreign key(tenant_id,response_id) references public.elearning_form_responses(tenant_id,id) on delete restrict,
 check(storage_key='elearning-private/tenant_'||tenant_id||'/response_'||response_id||'/'||id),unique(tenant_id,response_id,field_id)
);
create function public.guard_elearning_form_history() returns trigger language plpgsql set search_path='' as $$begin
 if TG_OP='DELETE' then raise exception using errcode='42501',message='form_history_immutable';end if;
 if TG_TABLE_NAME<>'elearning_form_responses' or (to_jsonb(new)-array['read_at','owner_notes','search_text']) is distinct from (to_jsonb(old)-array['read_at','owner_notes','search_text']) then raise exception using errcode='42501',message='form_history_immutable';end if;
 return new;
end $$;
create trigger form_version_immutable before update or delete on public.elearning_form_versions for each row execute function public.guard_elearning_form_history();
create trigger form_response_immutable before update or delete on public.elearning_form_responses for each row execute function public.guard_elearning_form_history();
create trigger form_file_immutable before update or delete on public.elearning_form_files for each row execute function public.guard_elearning_form_history();
create function public.manage_elearning_form(p_tenant integer,p_user integer,p_id uuid,p_revision integer,p_name text,p_status text,p_schema jsonb) returns jsonb
language plpgsql security definer set search_path='' as $$declare f public.elearning_forms;begin
 perform public.commerce_assert_member(p_tenant,p_user,true);
 if p_id is null then insert into public.elearning_forms(tenant_id,created_by,name,status) values(p_tenant,p_user,p_name,p_status) returning * into f;
 else select * into f from public.elearning_forms where tenant_id=p_tenant and id=p_id for update;
 if not found then raise exception using errcode='P0002',message='form_not_found';end if;
 if f.version<>p_revision then raise exception using errcode='40001',message='form_revision_changed';end if;
 update public.elearning_forms set name=p_name,status=p_status,version=version+1,updated_at=now() where tenant_id=p_tenant and id=p_id returning * into f;
 end if;
 insert into public.elearning_form_versions(tenant_id,form_id,version,schema,created_by) values(p_tenant,f.id,f.version,p_schema,p_user);
 return to_jsonb(f)||jsonb_build_object('schema',p_schema);
end $$;
create function public.elearning_form_enrolled(p_tenant integer,p_user integer) returns boolean
language plpgsql stable security definer set search_path='' as $$begin
 perform public.commerce_assert_member(p_tenant,p_user);
 return exists(select 1 from public.elearning_enrollments e join public.elearning_learners l on(l.tenant_id,l.id)=(e.tenant_id,e.learner_id) join public.elearning_courses c on(c.tenant_id,c.id)=(e.tenant_id,e.course_id) where e.tenant_id=p_tenant and l.user_id=p_user and l.status='active' and c.status='published' and e.status='active' and public.elearning_enrollment_has_access(p_tenant,e.id));
end $$;
revoke all on function public.elearning_form_enrolled(integer,integer) from public,anon,authenticated;
grant execute on function public.elearning_form_enrolled(integer,integer) to service_role;
create function public.submit_elearning_form(p_tenant integer,p_user integer,p_form uuid,p_version integer,p_id uuid,p_key uuid,p_hash text,p_answers jsonb,p_files jsonb) returns jsonb
language plpgsql security definer set search_path='' as $$declare f public.elearning_forms;s jsonb;r public.elearning_form_responses;a jsonb;begin
 select * into f from public.elearning_forms where tenant_id=p_tenant and id=p_form for update;
 if not found then raise exception using errcode='P0002',message='form_not_found';end if;
 select * into r from public.elearning_form_responses where tenant_id=p_tenant and form_id=p_form and idempotency_key=p_key;
 if found then
 if r.request_hash<>p_hash or r.user_id is distinct from p_user then raise exception using errcode='40001',message='form_submission_changed';end if;
 return jsonb_build_object('id',r.id,'duplicate',true);end if;
 if f.status<>'active' or f.version<>p_version then raise exception using errcode='40001',message='form_not_active_or_changed';end if;
 select schema into s from public.elearning_form_versions where tenant_id=p_tenant and form_id=p_form and version=p_version;
 if p_user is not null then perform public.commerce_assert_member(p_tenant,p_user);end if;
 if coalesce(s->>'access','public')<>'public' and p_user is null then raise exception using errcode='42501',message='form_login_required';end if;
 if s->>'access'='enrolled' and not public.elearning_form_enrolled(p_tenant,p_user) then raise exception using errcode='42501',message='form_enrollment_required';end if;
 insert into public.elearning_form_responses(id,tenant_id,form_id,version,user_id,answers,idempotency_key,request_hash) values(p_id,p_tenant,p_form,p_version,p_user,p_answers,p_key,p_hash);
 for a in select value from jsonb_array_elements(p_files) loop
 insert into public.elearning_form_files(id,tenant_id,response_id,field_id,storage_key,filename,mime_type,size_bytes,sha256) values((a->>'id')::uuid,p_tenant,p_id,a->>'field_id',a->>'storage_key',a->>'filename',a->>'mime_type',(a->>'size_bytes')::integer,a->>'sha256');end loop;
 if coalesce((s->>'notifyOwner')::boolean,true) then perform public.learning_notify_owners(p_tenant,'learning_form_response','elearning_form_response',p_id::text,'New form response','/e-learning/forms/responses');end if;
 if coalesce((s->>'confirmSubmitter')::boolean,false) then perform public.enqueue_learning_notification(p_tenant,p_user,'learning_form_confirmation','elearning_form_response',p_id::text,'Your form response was received','/my-learning');end if;
 return jsonb_build_object('id',p_id,'duplicate',false);
end $$;
create function public.manage_elearning_form_response(p_tenant integer,p_user integer,p_id uuid,p_read boolean,p_notes text) returns jsonb
language plpgsql security definer set search_path='' as $$declare r public.elearning_form_responses;begin
 perform public.commerce_assert_member(p_tenant,p_user,true);
 update public.elearning_form_responses set read_at=case when p_read then now() else null end,owner_notes=p_notes where tenant_id=p_tenant and id=p_id returning * into r;
 if not found then raise exception using errcode='P0002',message='response_not_found';end if;return to_jsonb(r);
end $$;

create or replace function public.validate_academy_builder_schema(p_schema jsonb) returns boolean
language plpgsql immutable set search_path='' as $$
declare node jsonb; element jsonb; page jsonb; slugs text[]:=array[]::text[]; ids text[]:=array[]::text[]; slug text; config jsonb; selected_id jsonb; field text;
begin
 if jsonb_typeof(p_schema) <> 'object' then return false; end if;
 if jsonb_typeof(p_schema->'pages') is distinct from 'array' or jsonb_array_length(p_schema->'pages') not between 1 and 50 then return false; end if;
 for page in select value from jsonb_array_elements(p_schema->'pages') loop
  if jsonb_typeof(page)<>'object' or jsonb_typeof(page->'id') is distinct from 'string' or coalesce(page->>'id','')='' or coalesce(page->>'access','public')<>'public' then return false;end if;
  slug:=page->>'slug';
  if slug is null or slug !~ '^/([a-z0-9-]+(/[a-z0-9-]+)*)?$' or slug like '%..%' or slug=any(slugs) or (page->>'id')=any(ids) then return false;end if;
  if split_part(trim(both '/' from slug),'/',1) in ('courses','plans','login','signup','auth','my-learning','account','checkout','assessments','api','admin','dashboard','settings','builder','page-builder') then return false;end if;
  slugs:=array_append(slugs,slug);ids:=array_append(ids,page->>'id');
 end loop;
 if not '/'=any(slugs) then return false;end if;
 if coalesce(p_schema->'forms','[]')<>'[]' or coalesce(p_schema->'workflows','[]')<>'[]'
 or coalesce(p_schema->'collections','[]')<>'[]' or coalesce(p_schema->'users','[]')<>'[]'
 or coalesce(p_schema->'roles','[]')<>'[]' then return false; end if;
 -- Recursive inspection covers direct, free and legacy row/column elements.
 for node in select value from jsonb_path_query(p_schema,'$.**.elements') as q(value)
 union all select value from jsonb_path_query(p_schema,'$.**.freeElements') as q(value) loop
  if jsonb_typeof(node)<>'array' then return false;end if;
  for element in select value from jsonb_array_elements(node) loop
   if coalesce(element->>'type','') not in ('heading','text','button','image','imageButton','imageCardButton','card','carousel','logoSlider','list','divider','thinDivider','metric','academyFeaturedCourses','academyCourseCollection','academyPlans','academyContinueLearning','academyInstructors','academyContact','academyExchangeOpportunities','academyProgrammeInfo','academyForm') then return false;end if;
   if coalesce(element->>'connectedFormId','')<>'' then return false;end if;
   if element ? 'action' and jsonb_typeof(element->'action') not in ('object','null') then return false;end if;
   if coalesce(element->'action'->>'type','none') not in ('none','openUrl','scrollToSection','goToPage') then return false;end if;
   if element->>'type' like 'academy%' then
    if element - array['id','type','name','content','mode','position','styles','action','connectedFormId','academy'] <> '{}' then return false;end if;
    config:=coalesce(element->'academy','{}');
    if jsonb_typeof(config)<>'object' or config - array['heading','description','maxItems','courseIds','planIds','variant','featuredOnly','instructorIds','formId'] <> '{}' then return false;end if;
    if config ? 'formId' and coalesce(config->>'formId','')<>'' then perform (config->>'formId')::uuid;end if;
    if coalesce(config->>'variant','grid') not in ('grid','compact') then return false;end if;
    foreach field in array array['heading','description'] loop
     if config ? field and (jsonb_typeof(config->field)<>'string' or length(config->>field)>case when field='heading' then 160 else 1200 end) then return false;end if;
    end loop;
    if config ? 'featuredOnly' and jsonb_typeof(config->'featuredOnly')<>'boolean' then return false;end if;
    if config ? 'maxItems' and (jsonb_typeof(config->'maxItems')<>'number' or (config->>'maxItems') !~ '^[0-9]+$' or (config->>'maxItems')::int not between 1 and 24) then return false;end if;
    foreach field in array array['courseIds','planIds','instructorIds'] loop
     if config ? field then
      if jsonb_typeof(config->field)<>'array' or jsonb_array_length(config->field)>24 then return false;end if;
      for selected_id in select value from jsonb_array_elements(config->field) loop
       if jsonb_typeof(selected_id)<>'string' then return false;end if;
       perform (selected_id#>>'{}')::uuid;
      end loop;
     end if;
    end loop;
   end if;
  end loop;
 end loop;
 return true;
exception when others then return false;
end $$;




create function public.guard_academy_form_references() returns trigger language plpgsql set search_path='' as $$declare schema_value jsonb; component jsonb;begin
 if new.usage_profile='academy' then
 foreach schema_value in array array[new.draft_schema,new.published_schema] loop
 for component in select value from jsonb_path_query(coalesce(schema_value,'{}'),'$.** ? (@.type == "academyForm")') q(value) loop
 if coalesce(component->'academy'->>'formId','')<>'' and not exists(select 1 from public.elearning_forms where tenant_id=new.tenant_id and id=(component->'academy'->>'formId')::uuid) then raise exception using errcode='23503',message='academy_form_tenant_mismatch';end if;
 end loop;end loop;end if;return new;
end $$;
create trigger academy_form_tenant_boundary before insert or update on public.builder_projects for each row execute function public.guard_academy_form_references();
do $$declare t text;begin
 foreach t in array array['elearning_forms','elearning_form_versions','elearning_form_responses','elearning_form_files'] loop
 execute format('alter table public.%I enable row level security',t);
 execute format('revoke all on public.%I from public,anon,authenticated,service_role',t);
 execute format('grant select on public.%I to service_role',t);
 end loop;
end $$;
revoke all on function public.guard_elearning_form_history(),public.guard_academy_form_references() from public,anon,authenticated,service_role;
revoke all on function public.manage_elearning_form(integer,integer,uuid,integer,text,text,jsonb),public.submit_elearning_form(integer,integer,uuid,integer,uuid,uuid,text,jsonb,jsonb),public.manage_elearning_form_response(integer,integer,uuid,boolean,text) from public,anon,authenticated;
grant execute on function public.manage_elearning_form(integer,integer,uuid,integer,text,text,jsonb),public.submit_elearning_form(integer,integer,uuid,integer,uuid,uuid,text,jsonb,jsonb),public.manage_elearning_form_response(integer,integer,uuid,boolean,text) to service_role;
create function public.elearning_form_counts(p_tenant integer,p_user integer) returns jsonb
language plpgsql stable security definer set search_path='' as $$begin
 perform public.commerce_assert_member(p_tenant,p_user,true);
 return coalesce((select jsonb_object_agg(form_id::text,jsonb_build_object('responses',total,'unread',unread)) from(select form_id,count(*) total,count(*) filter(where read_at is null) unread from public.elearning_form_responses where tenant_id=p_tenant group by form_id) s),'{}');
end $$;
revoke all on function public.elearning_form_counts(integer,integer) from public,anon,authenticated;
grant execute on function public.elearning_form_counts(integer,integer) to service_role;
update public.application_schema_state set schema_version=141,applied_at=now() where contract_key='core';
commit;
